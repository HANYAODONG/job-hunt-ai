"""Audit and clean multi-source JD data for phase-6 acceptance.

The workflow is deterministic and keeps every decision traceable. It adds the
required duplicate, noise, inflation and multi-source fields while preserving
the original description as evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = REPO_ROOT / "artifacts" / "dataset_iteration_05" / "jobs.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "artifacts" / "jd_quality_audit"

NOISE_RULES = {
    "company_culture": re.compile(
        r"(企业文化|价值观|客户为先|拥抱变化|拼搏担当|加入我们|期待你的加入|与公司共同成长)",
        re.I,
    ),
    "benefits": re.compile(
        r"(五险一金|六险一金|带薪年假|节日福利|下午茶|团建|免费班车|员工旅游|年度体检|零食)",
        re.I,
    ),
    "contact_or_application": re.compile(
        r"(咨询电话|简历投递|投递邮箱|联系人|个人经历填写要求|报名方式|请将简历发送)",
        re.I,
    ),
    "generic_promotion": re.compile(
        r"(行业领先|广阔平台|无限可能|极具竞争力|高速发展|年轻有活力|扁平化管理)",
        re.I,
    ),
    "placeholder": re.compile(r"(请您详见岗位意向|未提供展开要求|岗位职责详见|岗位要求详见)", re.I),
    "malformed_template": re.compile(r"#NAME\?", re.I),
    "team_promotion": re.compile(
        r"(团队介绍[：:]|在这里[，,]|站在巨人的肩膀上|顶尖院校|最美妙的火花)",
        re.I,
    ),
    "company_profile": re.compile(
        r"(覆盖150个国家和地区|发现真实.{0,12}瞬间|全球总部位于|办公地点还包括)",
        re.I,
    ),
}

NOISE_RULE_WEIGHTS = {
    "company_culture": 0.55,
    "benefits": 0.55,
    "contact_or_application": 0.45,
    "generic_promotion": 0.55,
    "placeholder": 1.0,
    "malformed_template": 0.9,
    "team_promotion": 0.55,
    "company_profile": 0.65,
}

STRONG_REQUIREMENT_PATTERN = re.compile(
    r"(精通|熟练掌握|必须具备|必须掌握|深入理解|丰富经验|独立负责|主导过|专家级)", re.I
)
DEGREE_PATTERN = re.compile(r"(博士|硕士|研究生|本科及以上|985|211)", re.I)
YEAR_PATTERN = re.compile(r"(?:至少|不少于|具备|拥有)?\s*(\d{1,2})\s*年(?:以上)?", re.I)
NON_TEXT_PATTERN = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff]+")
SENIOR_TITLE_PATTERN = re.compile(r"(高级|资深|专家|架构|负责人|总监|研究员|主管)", re.I)
VAGUE_TITLE_PATTERN = re.compile(r"^(研发岗位|软件开发|软件开发岗|测试开发工程师)$", re.I)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_no}: {path}") from exc
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_text(value: Any) -> str:
    return NON_TEXT_PATTERN.sub("", str(value or "").lower())


def role_key(job: dict[str, Any]) -> str:
    value = job.get("job_family") or job.get("standard_job") or job.get("title") or "unknown"
    normalized = normalize_text(value)
    return normalized or "unknown"


def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    match = re.match(r"^(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def source_descriptor(row: dict[str, Any]) -> dict[str, Any]:
    published = parse_date(row.get("publish_time"))
    dataset_year = row.get("dataset_year") or (published.year if published else None)
    return {
        "job_id": row.get("job_id") or row.get("id"),
        "source_type": str(row.get("source_type") or "unknown"),
        "source_name": str(row.get("source_name") or row.get("source") or "unknown"),
        "dataset_year": dataset_year,
        "publish_time": row.get("publish_time"),
        "source_url": row.get("source_url") or row.get("url"),
        "source_file": row.get("source_file") or row.get("raw_file"),
    }


def source_evidence_key(item: dict[str, Any]) -> str:
    return f"{item['source_type']}:{item['source_name']}:{item.get('dataset_year') or 'unknown'}"


def split_segments(text: str) -> list[str]:
    return [item.strip(" ;；。") for item in re.split(r"[\r\n]+", text) if item.strip(" ;；。")]


def clean_noise(text: str, source_type: str = "") -> tuple[str, float, list[str], list[str]]:
    segments = split_segments(text)
    removed: list[str] = []
    reasons: list[str] = []
    kept: list[str] = []
    matched_weights: list[float] = []
    is_government = source_type.strip().lower() == "government"
    for segment in segments:
        matched_rules = [name for name, pattern in NOISE_RULES.items() if pattern.search(segment)]
        if is_government:
            matched_rules = [name for name in matched_rules if name != "contact_or_application"]
        if matched_rules:
            reasons.extend(matched_rules)
            matched_weights.extend(NOISE_RULE_WEIGHTS[name] for name in matched_rules)
            # Long source paragraphs often mix company copy with real duties. Keep
            # them intact as evidence and flag them instead of deleting useful JD.
            if len(segment) <= 300 or "placeholder" in matched_rules:
                removed.append(segment)
            else:
                kept.append(segment)
        else:
            kept.append(segment)

    normalized_segments = [normalize_text(item) for item in segments]
    repeated_count = len(normalized_segments) - len(set(normalized_segments))
    total_chars = max(1, sum(len(item) for item in segments))
    removed_chars = sum(len(item) for item in removed)
    noise_ratio = removed_chars / total_chars
    repeat_ratio = repeated_count / max(1, len(segments))
    short_penalty = 0.18 if len(normalize_text(text)) < 45 else 0.0
    score = min(
        1.0,
        max(
            noise_ratio * 0.72 + repeat_ratio * 0.55 + short_penalty,
            max(matched_weights, default=0.0),
        ),
    )
    if repeated_count:
        reasons.append("repeated_segment")
    if short_penalty:
        reasons.append("low_information")
    cleaned = "\n".join(kept).strip() or text.strip()
    return cleaned, round(score, 4), sorted(set(reasons)), removed[:20]


def _simhash_tokens(text: str, limit: int = 128) -> list[str]:
    english = re.findall(r"[a-z0-9+#.]{2,}", text.lower())
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    bigrams = [chinese[index : index + 2] for index in range(max(0, len(chinese) - 1))]
    return sorted(set(english + bigrams))[:limit]


def simhash32(text: str) -> int:
    counters = [0] * 32
    for token in _simhash_tokens(text):
        digest = int.from_bytes(hashlib.blake2s(token.encode("utf-8"), digest_size=4).digest(), "big")
        for bit in range(32):
            counters[bit] += 1 if digest & (1 << bit) else -1
    result = 0
    for bit, value in enumerate(counters):
        if value >= 0:
            result |= 1 << bit
    return result


def find_duplicates(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    results: dict[int, dict[str, Any]] = {}
    exact_seen: dict[str, int] = {}
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    normalized = [normalize_text(row.get("description")) for row in rows]
    hashes = [simhash32(text) for text in normalized]

    for index, text in enumerate(normalized):
        if len(text) < 30:
            continue
        exact_key = hashlib.sha1(text.encode("utf-8")).hexdigest()
        if exact_key in exact_seen:
            canonical = exact_seen[exact_key]
            results[index] = {
                "is_duplicate": True,
                "duplicate_type": "exact",
                "duplicate_of": rows[canonical].get("job_id") or rows[canonical].get("id"),
                "duplicate_similarity": 1.0,
            }
            continue
        exact_seen[exact_key] = index

        candidates: set[int] = set()
        value = hashes[index]
        for band in range(4):
            key = (band, (value >> (band * 8)) & 0xFF)
            candidates.update(buckets[key][-80:])

        best: tuple[int, float] | None = None
        for candidate in candidates:
            other = normalized[candidate]
            length_ratio = min(len(text), len(other)) / max(len(text), len(other))
            if length_ratio < 0.78 or (value ^ hashes[candidate]).bit_count() > 4:
                continue
            similarity = SequenceMatcher(None, text, other, autojunk=False).ratio()
            if similarity >= 0.86 and (best is None or similarity > best[1]):
                best = (candidate, similarity)
        if best:
            results[index] = {
                "is_duplicate": True,
                "duplicate_type": "near_duplicate",
                "duplicate_of": rows[best[0]].get("job_id") or rows[best[0]].get("id"),
                "duplicate_similarity": round(best[1], 4),
            }

        for band in range(4):
            key = (band, (value >> (band * 8)) & 0xFF)
            buckets[key].append(index)
    return results


def constraint_features(job: dict[str, Any]) -> dict[str, Any]:
    text = str(job.get("description") or "")
    title = str(job.get("title") or "")
    skills = list(dict.fromkeys(job.get("required_skills") or job.get("skills") or []))
    years = [int(value) for value in YEAR_PATTERN.findall(text) if int(value) <= 30]
    return {
        "skill_count": len(skills),
        "strong_requirement_count": len(STRONG_REQUIREMENT_PATTERN.findall(text)),
        "degree_requirement_count": len(DEGREE_PATTERN.findall(text)),
        "max_years_experience": max(years, default=0),
        "is_senior_role": bool(SENIOR_TITLE_PATTERN.search(title)),
        "is_vague_title": bool(VAGUE_TITLE_PATTERN.search(title.strip())),
    }


def inflation_score(features: dict[str, Any], family_skill_median: float) -> tuple[float, list[str]]:
    skill_count = features["skill_count"]
    strong_count = features["strong_requirement_count"]
    max_years = features["max_years_experience"]
    degree_count = features["degree_requirement_count"]
    is_senior_role = bool(features.get("is_senior_role"))
    is_vague_title = bool(features.get("is_vague_title"))
    relative_excess = max(0.0, skill_count - family_skill_median) / max(4.0, family_skill_median)
    base_score = (
        min(1.0, skill_count / 24.0) * 0.35
        + min(1.0, strong_count / 7.0) * 0.25
        + min(1.0, relative_excess) * 0.22
        + min(1.0, max(0, max_years - 5) / 7.0) * 0.12
        + min(1.0, degree_count / 3.0) * 0.06
    )
    role_mismatch_adjustment = 0.0
    if not is_senior_role and max_years >= 10:
        role_mismatch_adjustment += 0.20
    if not is_senior_role and skill_count >= 30:
        role_mismatch_adjustment += 0.10
    if is_vague_title:
        role_mismatch_adjustment += 0.08
    score = base_score + min(0.30, role_mismatch_adjustment)
    reasons = []
    if skill_count >= max(16, family_skill_median * 1.6):
        reasons.append("skill_stuffing")
    if strong_count >= 5:
        reasons.append("excessive_strong_requirements")
    if max_years >= 10:
        reasons.append("high_experience_threshold")
    if relative_excess >= 0.8:
        reasons.append("above_family_skill_baseline")
    if not is_senior_role and max_years >= 10:
        reasons.append("experience_role_mismatch")
    if not is_senior_role and skill_count >= 30:
        reasons.append("broad_skill_scope_for_role")
    if is_vague_title and role_mismatch_adjustment:
        reasons.append("vague_role_high_burden")
    return round(min(1.0, score), 4), reasons


def score_distribution(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    if not ordered:
        return {"mean": 0.0, "p50": 0.0, "p90": 0.0}
    percentile = lambda p: ordered[min(len(ordered) - 1, int((len(ordered) - 1) * p))]
    return {
        "mean": round(statistics.fmean(ordered), 4),
        "p50": round(percentile(0.5), 4),
        "p90": round(percentile(0.9), 4),
    }


def audit(rows: list[dict[str, Any]], as_of: date | None = None) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    dates = [parsed for row in rows if (parsed := parse_date(row.get("publish_time")))]
    reference_date = as_of or max(dates, default=date.today())
    duplicates = find_duplicates(rows)
    features = [constraint_features(row) for row in rows]

    family_skill_counts: dict[str, list[int]] = defaultdict(list)
    family_support: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"types": set(), "sources": set(), "years": set(), "evidence": set()}
    )
    family_evidence_details: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row, item_features in zip(rows, features):
        family = role_key(row)
        family_skill_counts[family].append(item_features["skill_count"])
        descriptor = source_descriptor(row)
        source_type = descriptor["source_type"]
        source_name = descriptor["source_name"]
        year = str(descriptor.get("dataset_year") or "unknown")
        evidence_key = source_evidence_key(descriptor)
        family_support[family]["types"].add(source_type)
        family_support[family]["sources"].add(source_name)
        family_support[family]["years"].add(year)
        family_support[family]["evidence"].add(evidence_key)
        detail = family_evidence_details[family].setdefault(
            evidence_key,
            {
                "source_type": source_type,
                "source_name": source_name,
                "dataset_year": descriptor.get("dataset_year"),
                "source_url": descriptor.get("source_url"),
                "source_file": descriptor.get("source_file"),
                "sample_job_ids": [],
                "record_count": 0,
            },
        )
        detail["record_count"] += 1
        if len(detail["sample_job_ids"]) < 3:
            detail["sample_job_ids"].append(descriptor["job_id"])

    family_medians = {
        family: statistics.median(values) if values else 0.0
        for family, values in family_skill_counts.items()
    }

    id_to_index = {
        str(row.get("job_id") or row.get("id")): index for index, row in enumerate(rows)
    }
    duplicate_groups: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        canonical = str(duplicates.get(index, {}).get("duplicate_of") or row.get("job_id") or row.get("id"))
        duplicate_groups[canonical].append(index)
        if canonical in id_to_index and id_to_index[canonical] not in duplicate_groups[canonical]:
            duplicate_groups[canonical].append(id_to_index[canonical])

    audited: list[dict[str, Any]] = []
    for index, (row, item_features) in enumerate(zip(rows, features)):
        description_raw = str(row.get("description") or "")
        cleaned, noise_score, noise_reasons, removed_segments = clean_noise(
            description_raw, str(row.get("source_type") or "")
        )
        family = role_key(row)
        inflation, inflation_reasons = inflation_score(item_features, family_medians[family])
        published = parse_date(row.get("publish_time"))
        age_days = (reference_date - published).days if published else None
        staleness_score = 0.5 if age_days is None else round(min(1.0, max(0, age_days) / 1095), 4)
        is_stale = age_days is None or age_days > 365
        duplicate = duplicates.get(
            index,
            {
                "is_duplicate": False,
                "duplicate_type": None,
                "duplicate_of": None,
                "duplicate_similarity": 0.0,
            },
        )
        support = family_support[family]
        current_source = source_descriptor(row)
        canonical_id = str(duplicate.get("duplicate_of") or row.get("job_id") or row.get("id"))
        group_indices = duplicate_groups.get(canonical_id, [index])
        record_sources_by_key: dict[str, dict[str, Any]] = {}
        for related_index in group_indices:
            descriptor = source_descriptor(rows[related_index])
            record_sources_by_key[source_evidence_key(descriptor)] = descriptor
        record_sources = sorted(
            record_sources_by_key.values(),
            key=lambda item: (
                str(item.get("dataset_year") or ""),
                item["source_type"],
                item["source_name"],
            ),
        )
        record_types = {item["source_type"] for item in record_sources}
        record_names = {item["source_name"] for item in record_sources}
        record_years = {str(item["dataset_year"]) for item in record_sources if item.get("dataset_year")}
        record_verified = len(record_types) >= 2 or (len(record_names) >= 2 and len(record_years) >= 2)
        source_count = len(support["evidence"])
        family_verified = len(support["types"]) >= 2 or (
            len(support["sources"]) >= 2 and len(support["years"] - {"unknown"}) >= 2
        )
        verified = record_verified or family_verified
        verification_scope = (
            "record_duplicate_group"
            if record_verified
            else "standard_job_family"
            if family_verified
            else "single_source"
        )
        family_examples = sorted(
            family_evidence_details[family].values(),
            key=lambda item: (-int(item["record_count"]), item["source_type"], item["source_name"]),
        )[:10]
        output = dict(row)
        output["description_raw"] = description_raw
        output["description"] = cleaned
        output["description_cleaned"] = cleaned
        output.update(duplicate)
        output.update(
            {
                "noise_score": noise_score,
                "noise_reasons": noise_reasons,
                "removed_noise_segments": removed_segments,
                "inflation_score": inflation,
                "inflation_reasons": inflation_reasons,
                "is_inflated": inflation >= 0.65,
                "staleness_score": staleness_score,
                "is_stale": is_stale,
                "age_days": age_days,
                "source_count": source_count,
                "source_type_count": len(support["types"]),
                "source_year_count": len(support["years"] - {"unknown"}),
                "record_source_count": len(record_sources),
                "verified_by_multi_source_record": record_verified,
                "verified_by_multi_source": verified,
                "verification_scope": verification_scope,
                "source_evidence": {
                    "current": current_source,
                    "record_level_matches": record_sources,
                    "job_family_key": family,
                    "job_family_support": family_examples,
                    "verification_scope": verification_scope,
                    "criteria": "cross source type, or cross source name and dataset year",
                },
                "quality_flags": sorted(
                    flag
                    for flag, active in {
                        "duplicate": duplicate["is_duplicate"],
                        "noise": noise_score >= 0.35,
                        "inflation": inflation >= 0.65,
                        "stale": is_stale,
                        "unverified": not verified,
                    }.items()
                    if active
                ),
                "quality_evidence": item_features,
            }
        )
        audited.append(output)

    counts = {
        "input_jobs": len(rows),
        "output_jobs": len(audited),
        "duplicates": sum(bool(row["is_duplicate"]) for row in audited),
        "near_duplicates": sum(row["duplicate_type"] == "near_duplicate" for row in audited),
        "noisy_jobs": sum(row["noise_score"] >= 0.35 for row in audited),
        "inflated_jobs": sum(bool(row["is_inflated"]) for row in audited),
        "stale_jobs": sum(bool(row["is_stale"]) for row in audited),
        "multi_source_verified_jobs": sum(bool(row["verified_by_multi_source"]) for row in audited),
        "record_level_multi_source_jobs": sum(
            bool(row["verified_by_multi_source_record"]) for row in audited
        ),
    }
    report = {
        "status": "pass" if len(audited) >= 100 else "insufficient_sample",
        "workflow": "phase6_jd_quality_audit",
        "reference_date": reference_date.isoformat(),
        "thresholds": {"noise": 0.35, "inflation": 0.65, "stale_days": 365, "near_duplicate": 0.86},
        "counts": counts,
        "rates": {
            key: round(value / max(1, len(audited)), 4)
            for key, value in counts.items()
            if key not in {"input_jobs", "output_jobs"}
        },
        "source_type_counts": dict(Counter(str(row.get("source_type") or "unknown") for row in audited)),
        "score_distributions": {
            "noise_score": score_distribution([row["noise_score"] for row in audited]),
            "inflation_score": score_distribution([row["inflation_score"] for row in audited]),
            "staleness_score": score_distribution([row["staleness_score"] for row in audited]),
        },
        "acceptance": {
            "minimum_jd_required": 100,
            "jd_audited": len(audited),
            "minimum_met": len(audited) >= 100,
            "required_fields_complete": all(
                all(field in row for field in ("is_duplicate", "noise_score", "inflation_score", "source_count", "verified_by_multi_source"))
                for row in audited
            ),
            "source_evidence_complete": all(
                isinstance(row.get("source_evidence"), dict)
                and isinstance(row["source_evidence"].get("current"), dict)
                and bool(row["source_evidence"]["current"].get("source_type"))
                for row in audited
            ),
        },
    }

    def case_payload(row: dict[str, Any], category: str, score: float | None) -> dict[str, Any]:
        reason_field = {
            "noise": "noise_reasons",
            "inflation": "inflation_reasons",
        }.get(category)
        reasons = list(row.get(reason_field) or []) if reason_field else list(row.get("quality_flags") or [])
        if category == "duplicates":
            reasons = [str(row.get("duplicate_type") or "duplicate"), f"duplicate_of:{row.get('duplicate_of')}"]
        elif category == "staleness":
            reasons = [f"age_days:{row.get('age_days')}", f"reference_date:{reference_date.isoformat()}"]
        elif category == "multi_source":
            reasons = [
                f"verification_scope:{row.get('verification_scope')}",
                f"source_count:{row.get('source_count')}",
            ]
        decision = {
            "duplicates": bool(row.get("is_duplicate")),
            "noise": float(row.get("noise_score") or 0) >= 0.35,
            "inflation": bool(row.get("is_inflated")),
            "staleness": bool(row.get("is_stale")),
            "multi_source": bool(row.get("verified_by_multi_source")),
        }[category]
        return {
            "job_id": row.get("job_id") or row.get("id"),
            "title": row.get("title"),
            "source_type": row.get("source_type"),
            "job_family": row.get("job_family"),
            "category": category,
            "decision": decision,
            "score": score,
            "reasons": reasons,
            "quality_flags": row.get("quality_flags"),
            "duplicate_of": row.get("duplicate_of"),
            "publish_time": row.get("publish_time"),
            "original_excerpt": str(row.get("description_raw") or "")[:600],
            "cleaned_excerpt": str(row.get("description_cleaned") or "")[:600],
            "description_excerpt": str(row.get("description_raw") or "")[:600],
            "removed_noise_segments": list(row.get("removed_noise_segments") or [])[:5],
            "source_evidence": row.get("source_evidence"),
        }

    def top(field: str, category: str, count: int = 20) -> list[dict[str, Any]]:
        return [
            case_payload(row, category, row.get(field))
            for row in sorted(audited, key=lambda item: float(item.get(field) or 0), reverse=True)[:count]
        ]

    cases = {
        "duplicates": [
            case_payload(row, "duplicates", row.get("duplicate_similarity"))
            for row in audited
            if row["is_duplicate"]
        ][:30],
        "noise": top("noise_score", "noise"),
        "inflation": top("inflation_score", "inflation"),
        "staleness": top("staleness_score", "staleness"),
        "multi_source": [
            case_payload(row, "multi_source", float(row.get("source_count") or 0))
            for row in sorted(audited, key=lambda item: item["source_count"], reverse=True)[:30]
        ],
    }
    return audited, report, cases


def build_acceptance_sample(rows: list[dict[str, Any]], size: int = 200) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    selectors = [
        lambda row: float(row.get("duplicate_similarity") or 0),
        lambda row: float(row.get("noise_score") or 0),
        lambda row: float(row.get("inflation_score") or 0),
        lambda row: float(row.get("staleness_score") or 0),
        lambda row: float(row.get("source_count") or 0),
    ]
    for selector in selectors:
        for row in sorted(rows, key=selector, reverse=True)[:40]:
            job_id = str(row.get("job_id") or row.get("id"))
            if job_id in seen:
                continue
            seen.add(job_id)
            selected.append(row)
            if len(selected) >= size:
                break
        if len(selected) >= size:
            break
    for row in rows:
        job_id = str(row.get("job_id") or row.get("id"))
        if job_id not in seen:
            seen.add(job_id)
            selected.append(row)
        if len(selected) >= size:
            break
    return [
        {
            "job_id": row.get("job_id") or row.get("id"),
            "title": row.get("title"),
            "source_type": row.get("source_type"),
            "publish_time": row.get("publish_time"),
            "is_duplicate": row.get("is_duplicate"),
            "noise_score": row.get("noise_score"),
            "inflation_score": row.get("inflation_score"),
            "is_stale": row.get("is_stale"),
            "source_count": row.get("source_count"),
            "verified_by_multi_source": row.get("verified_by_multi_source"),
            "quality_flags": row.get("quality_flags"),
            "description_excerpt": str(row.get("description_raw") or "")[:400],
            "human_label": None,
            "human_notes": "",
        }
        for row in selected[:size]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase-6 JD quality audit")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--as-of", type=str, default=None, help="YYYY-MM-DD; default is latest valid JD date")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    if args.limit > 0:
        rows = rows[: args.limit]
    as_of = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else None
    audited, report, cases = audit(rows, as_of=as_of)
    report["input"] = {
        "path": str(args.input),
        "sha256": file_sha256(args.input),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "jd_quality_cleaned.jsonl", audited)
    write_json(args.output_dir / "jd_quality_report.json", report)
    write_json(args.output_dir / "jd_quality_cases.json", cases)
    write_jsonl(args.output_dir / "acceptance_sample_200.jsonl", build_acceptance_sample(audited))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
