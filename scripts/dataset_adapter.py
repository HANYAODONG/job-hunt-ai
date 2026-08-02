"""Adapt dataset-group artifacts into JobMatch AI standard JSONL files.

Workflow 1 scope:
- Convert the shared raw CSV/JSONL files into stable downstream contracts.
- Emit jobs, candidate profiles, optional labels, quality reports, and samples.
- Keep the process offline and deterministic.
- Do not train models.
- Do not emit name, phone, email, or other direct PII fields.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_DIR = REPO_ROOT.parent / "database"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "dataset_iteration_05"

ENTERPRISE_JOB_CANDIDATES = (
    "job_bigcompany_final.csv",
    "job_bigcompany_final(1).csv",
)
GOVERNMENT_JOB_CANDIDATES = (
    "government_jobs_2024_2026_tech_final.csv",
    "government_jobs_2026_tech_filtered.csv",
)
RESUME_CANDIDATES = (
    "synthetic_detailed_resumes_experience_30k.csv",
    "synthetic_detailed_resumes.csv",
)
JOB_TITLE_DICTIONARY = "standard_job_title_dictionary.csv"
SILVER_LABEL_CANDIDATES = ("resume_job_silver_30.jsonl",)
GOLD_LABEL_CANDIDATES = ("金标30×20.csv", "金标30x20.csv")


def first_existing(dataset_dir: Path, filenames: Iterable[str], required: bool = False) -> Path | None:
    for filename in filenames:
        path = dataset_dir / filename
        if path.exists():
            return path
    if required:
        raise FileNotFoundError(
            f"Required input not found in {dataset_dir}: {', '.join(filenames)}"
        )
    return None


def read_csv_rows(path: Path, encodings: tuple[str, ...] = ("utf-8-sig", "utf-8", "gb18030")) -> list[dict[str, str]]:
    last_error: Exception | None = None
    for encoding in encodings:
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError as exc:
            last_error = exc
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Cannot decode {path}: {last_error}")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
    return records


def parse_json_object(text: str) -> dict[str, Any]:
    if not text or not text.strip():
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
            count += 1
    return count


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_json_field(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def split_items(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return unique_strings(value)
    if not isinstance(value, str):
        return []

    stripped = value.strip()
    parsed = parse_json_field(stripped, None)
    if isinstance(parsed, list):
        return unique_strings(parsed)

    parts = re.split(r"[;；,，、\n\r\t]+", stripped)
    return unique_strings(parts)


def unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value in ("", None):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def join_text(*parts: Any) -> str:
    return "\n".join(str(part).strip() for part in parts if str(part or "").strip())


def load_job_title_rules(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    rules: list[dict[str, str]] = []
    for row in read_csv_rows(path):
        title = row.get("standard_job_title", "").strip()
        if not title:
            continue
        rules.append(
            {
                "standard_job_title": title,
                "standard_category": row.get("standard_category", "").strip(),
                "match_keywords": row.get("match_keywords", "").strip(),
            }
        )
    return rules


def normalize_job_family(text: str, rules: list[dict[str, str]], fallback: str = "") -> tuple[str, str, str]:
    if fallback:
        for rule in rules:
            if rule["standard_job_title"] == fallback:
                return fallback, rule.get("standard_category", ""), "source_field"
        return fallback, "", "source_field"

    for rule in rules:
        pattern = rule.get("match_keywords", "")
        if not pattern:
            continue
        try:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return rule["standard_job_title"], rule.get("standard_category", ""), "dictionary_regex"
        except re.error:
            if pattern.lower() in text.lower():
                return rule["standard_job_title"], rule.get("standard_category", ""), "dictionary_text"
    return "", "", "unmatched"


def adapt_enterprise_jobs(rows: list[dict[str, str]], rules: list[dict[str, str]]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        job_id = row.get("job_id", "").strip() or f"JOB{index:05d}"
        title = row.get("job_title", "").strip()
        description = join_text(
            row.get("job_responsibility", ""),
            row.get("job_requirement", ""),
            row.get("detailed", ""),
            row.get("domain_context", ""),
        )
        skills = unique_strings(
            split_items(row.get("skills", ""))
            + split_items(row.get("traditional_skills", ""))
            + split_items(row.get("new_skills", ""))
        )
        family, category, method = normalize_job_family(
            join_text(title, description, row.get("standard_job", "")),
            rules,
            row.get("standard_job", "").strip(),
        )
        jobs.append(
            {
                "job_id": job_id,
                "id": job_id,
                "title": title,
                "description": description,
                "skills": skills,
                "required_skills": skills,
                "job_family": family,
                "standard_job": family,
                "standard_category": category,
                "company": "",
                "company_name": "",
                "location": "",
                "location_text": "",
                "source": "bigcompany_processed",
                "source_type": "enterprise",
                "publish_time": row.get("publish_time", "").strip(),
                "domain_context": row.get("domain_context", "").strip(),
                "traditional_skills": split_items(row.get("traditional_skills", "")),
                "new_skills": split_items(row.get("new_skills", "")),
                "search_metadata": {
                    "source_file": "job_bigcompany_final",
                    "source_job_id": job_id,
                    "job_family_alignment_method": method,
                },
            }
        )
    return jobs


def adapt_government_jobs(
    rows: list[dict[str, str]],
    rules: list[dict[str, str]],
    start_index: int = 1,
    source_file: str = "government_jobs",
) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=start_index):
        raw_payload = parse_json_object(row.get("raw", ""))
        job_uid = str(raw_payload.get("job_uid") or "").strip()
        dataset_year = raw_payload.get("dataset_year")
        tech_filter = raw_payload.get("tech_filter") if isinstance(raw_payload.get("tech_filter"), dict) else {}
        job_id = row.get("job_id", "").strip() or job_uid or f"GOV{index:05d}"
        title = row.get("job_title", "").strip()
        description = row.get("job_description", "").strip()
        tags = split_items(row.get("tags", ""))
        family, category, method = normalize_job_family(join_text(title, description, row.get("tags", "")), rules)
        jobs.append(
            {
                "job_id": job_id,
                "id": job_id,
                "title": title,
                "description": description,
                "skills": [],
                "required_skills": [],
                "job_family": family,
                "standard_job": family,
                "standard_category": category,
                "company": row.get("company_name", "").strip(),
                "company_name": row.get("company_name", "").strip(),
                "location": row.get("location", "").strip() or row.get("city", "").strip(),
                "location_text": row.get("location", "").strip() or row.get("city", "").strip(),
                "source": row.get("source", "").strip() or "government_jobs",
                "source_type": "government",
                "source_name": row.get("source_name", "").strip(),
                "dataset_year": dataset_year,
                "salary_text": row.get("salary_text", "").strip(),
                "tags": tags,
                "publish_time": row.get("publish_time", "").strip(),
                "source_url": row.get("source_url", "").strip(),
                "search_metadata": {
                    "source_file": source_file,
                    "source_job_id": job_id,
                    "source_job_uid": job_uid,
                    "dataset_year": dataset_year,
                    "job_family_alignment_method": method,
                    "keyword": row.get("keyword", "").strip(),
                    "tech_filter_categories": tech_filter.get("categories", []),
                    "tech_filter_reason": tech_filter.get("reason", ""),
                    "tech_filter_scope": tech_filter.get("scope", ""),
                },
            }
        )
    return jobs


def adapt_candidate_profiles(resume_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for row in resume_rows:
        resume_id = row.get("resume_id", "").strip()
        skills = split_items(row.get("skills_normalized", ""))
        skill_levels = parse_json_field(row.get("skill_levels", ""), {})
        experience = parse_json_field(row.get("experience", ""), [])
        projects = parse_json_field(row.get("projects", ""), [])
        target_family = (
            row.get("standard_job_title", "").strip()
            or row.get("standard_job", "").strip()
            or row.get("target_job_family", "").strip()
        )
        profiles.append(
            {
                "candidate_id": resume_id,
                "resume_id": resume_id,
                "source_resume_id": resume_id,
                "split": row.get("split", "").strip(),
                "summary": row.get("profile_text", "").strip(),
                "target_job_family": target_family,
                "original_target_job_family": row.get("original_target_job_family", "").strip()
                or row.get("target_job_family", "").strip(),
                "preferred_location": row.get("preferred_location", "").strip(),
                "skills": skills,
                "education": {
                    "education": row.get("education", "").strip(),
                    "degree": row.get("degree", "").strip(),
                    "school_category": row.get("school_category", "").strip(),
                    "major": row.get("major", "").strip(),
                    "english_level": row.get("english_level", "").strip(),
                },
                "years_experience": safe_int(row.get("years_experience"), 0),
                "skills_normalized": skills,
                "skill_levels": skill_levels,
                "experience": experience,
                "projects": projects,
                "profile_text": row.get("profile_text", "").strip(),
                "standard_category": row.get("standard_category", "").strip(),
                "alignment_method": row.get("alignment_method", "").strip(),
                "job_profile_skills": split_items(row.get("job_profile_skills", "")),
                "kg_display_skills": split_items(row.get("kg_display_skills", "")),
                "resume_skill_overlap_count": safe_int(row.get("resume_skill_overlap_count")),
            }
        )
    return profiles


def adapt_silver_pairs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for record in records:
        pairs.append(
            {
                "candidate_id": record.get("resume_id", ""),
                "resume_id": record.get("resume_id", ""),
                "job_id": record.get("job_id", ""),
                "pair_key": f"{record.get('resume_id', '')}::{record.get('job_id', '')}",
                "target_job_family": record.get("target_job_family", ""),
                "label_source": "silver",
                "grade": safe_int(record.get("silver_grade"), 0),
                "score": safe_float(record.get("silver_score"), 0.0),
                "bm25_rank": safe_int(record.get("bm25_rank")),
                "bm25_score": safe_float(record.get("bm25_score")),
                "semantic_rank": safe_int(record.get("semantic_rank")),
                "semantic_score": safe_float(record.get("semantic_score")),
                "family_match": safe_float(record.get("family_match"), 0.0),
                "skill_coverage": safe_float(record.get("skill_coverage"), 0.0),
                "matched_skills": record.get("matched_skills") or [],
            }
        )
    return pairs


def adapt_gold_pairs(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for row in rows:
        pairs.append(
            {
                "pair_id": row.get("pair_id", ""),
                "candidate_id": row.get("resume_id", ""),
                "resume_id": row.get("resume_id", ""),
                "job_id": row.get("job_id", ""),
                "pair_key": f"{row.get('resume_id', '')}::{row.get('job_id', '')}",
                "target_job_family": row.get("target_job_family", ""),
                "label_source": "gold",
                "grade": safe_int(row.get("relevance_grade"), 0),
                "hard_constraint_pass": row.get("hard_constraint_pass", ""),
                "matched_skills": split_items(row.get("matched_skills", "")),
                "missing_required_skills": split_items(row.get("missing_required_skills", "")),
                "missing_optional_skills": split_items(row.get("missing_optional_skills", "")),
                "transferable_skills": split_items(row.get("transferable_skills", "")),
                "resume_evidence": row.get("resume_evidence", ""),
                "job_evidence": row.get("job_evidence", ""),
                "annotator_id": row.get("annotator_id", ""),
                "notes": row.get("notes", ""),
            }
        )
    return pairs


def base_resume_id(candidate_id: Any) -> str:
    text = str(candidate_id or "").strip()
    match = re.match(r"(resume_\d+)", text)
    return match.group(1) if match else text


def build_candidate_id_map(candidate_profiles: list[dict[str, Any]]) -> dict[str, str]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for profile in candidate_profiles:
        candidate_id = str(profile.get("candidate_id", "")).strip()
        if not candidate_id:
            continue
        grouped.setdefault(base_resume_id(candidate_id), []).append(profile)

    mapping: dict[str, str] = {}
    for source_id, profiles in grouped.items():
        def candidate_sort_key(item: dict[str, Any]) -> tuple[int, str]:
            years = safe_int(item.get("years_experience"))
            return (
                years if years is not None else 999,
                str(item.get("candidate_id", "")),
            )

        ordered = sorted(
            profiles,
            key=candidate_sort_key,
        )
        mapping[source_id] = str(ordered[0].get("candidate_id", ""))
    return mapping


def normalize_label_pairs(
    pairs: list[dict[str, Any]],
    candidate_id_map: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    mapped_candidate_refs = 0
    unchanged_candidate_refs = 0
    for pair in pairs:
        source_candidate_id = str(pair.get("candidate_id", "")).strip()
        source_job_id = str(pair.get("job_id", "")).strip()
        mapped_candidate_id = candidate_id_map.get(source_candidate_id, source_candidate_id)
        if mapped_candidate_id != source_candidate_id:
            mapped_candidate_refs += 1
        else:
            unchanged_candidate_refs += 1
        pair["source_candidate_id"] = source_candidate_id
        pair["candidate_id"] = mapped_candidate_id
        pair["resume_id"] = mapped_candidate_id
        pair["source_job_id"] = source_job_id
        pair["pair_key"] = f"{mapped_candidate_id}::{source_job_id}"
        pair["id_mapping"] = {
            "candidate_id": "base_resume_id_to_experience_variant"
            if mapped_candidate_id != source_candidate_id
            else "unchanged",
            "job_id": "legacy_label_job" if source_job_id.startswith("job_") else "unchanged",
        }
    return pairs, {
        "mapped_candidate_refs": mapped_candidate_refs,
        "unchanged_candidate_refs": unchanged_candidate_refs,
    }


def legacy_job_from_label_record(
    record: dict[str, Any],
    label_source: str,
    rules: list[dict[str, str]],
) -> dict[str, Any] | None:
    job_id = str(record.get("job_id", "")).strip()
    if not job_id:
        return None
    title = str(record.get("job_title", "")).strip()
    description = str(record.get("job_description", "")).strip()
    tags = split_items(record.get("tags", "") or record.get("job_tags", ""))
    matched_skills = split_items(record.get("matched_skills", ""))
    family, category, method = normalize_job_family(
        join_text(title, description, record.get("target_job_family", "")),
        rules,
        str(record.get("target_job_family", "")).strip(),
    )
    return {
        "job_id": job_id,
        "id": job_id,
        "title": title,
        "description": description,
        "skills": matched_skills,
        "required_skills": matched_skills,
        "job_family": family,
        "standard_job": family,
        "standard_category": category,
        "company": str(record.get("company_name", "")).strip(),
        "company_name": str(record.get("company_name", "")).strip(),
        "location": str(record.get("location", "")).strip(),
        "location_text": str(record.get("location", "")).strip(),
        "source": f"{label_source}_label_legacy_job",
        "source_type": "legacy_label",
        "original_source_type": str(record.get("source_type", "")).strip(),
        "tags": tags,
        "source_url": str(record.get("source_url", "")).strip(),
        "search_metadata": {
            "source_file": label_source,
            "source_job_id": job_id,
            "job_family_alignment_method": method,
            "note": "Job reconstructed from legacy gold/silver labels because label job_id does not exist in the new normalized job corpus.",
        },
    }


def build_legacy_label_jobs(
    silver_records: list[dict[str, Any]],
    gold_rows: list[dict[str, str]],
    rules: list[dict[str, str]],
    existing_job_ids: set[str],
) -> list[dict[str, Any]]:
    jobs: dict[str, dict[str, Any]] = {}
    for record in silver_records:
        job = legacy_job_from_label_record(record, "silver", rules)
        if job and job["job_id"] not in existing_job_ids:
            jobs.setdefault(job["job_id"], job)
    for row in gold_rows:
        job = legacy_job_from_label_record(row, "gold", rules)
        if job and job["job_id"] not in existing_job_ids:
            jobs.setdefault(job["job_id"], job)
    return sorted(jobs.values(), key=lambda item: item["job_id"])


def grade_counts(records: Iterable[dict[str, Any]], key: str = "grade") -> dict[str, int]:
    counts = Counter(str(record.get(key, "")) for record in records)
    return dict(sorted(counts.items()))


def missing_field_count(records: list[dict[str, Any]], fields: list[str]) -> dict[str, int]:
    return {
        field: sum(1 for record in records if record.get(field) in (None, "", []))
        for field in fields
    }


def write_sample_pack(
    output_dir: Path,
    candidate_profiles: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    silver_pairs: list[dict[str, Any]],
    gold_pairs: list[dict[str, Any]],
) -> dict[str, int]:
    sample_dir = output_dir / "sample_pack"
    sample_candidates = candidate_profiles[:5]
    sample_candidate_ids = {item["candidate_id"] for item in sample_candidates}

    candidate_gold_pairs = [pair for pair in gold_pairs if pair.get("candidate_id") in sample_candidate_ids]
    candidate_silver_pairs = [pair for pair in silver_pairs if pair.get("candidate_id") in sample_candidate_ids]

    job_ids: list[str] = []
    for pair in candidate_gold_pairs + candidate_silver_pairs:
        job_id = str(pair.get("job_id", ""))
        if job_id and job_id not in job_ids:
            job_ids.append(job_id)
        if len(job_ids) >= 10:
            break

    if len(job_ids) < 10:
        for job in jobs:
            job_id = str(job.get("job_id", ""))
            if job_id and job_id not in job_ids:
                job_ids.append(job_id)
            if len(job_ids) >= 10:
                break

    selected_job_ids = set(job_ids[:10])
    sample_jobs = [job for job in jobs if job.get("job_id") in selected_job_ids][:10]
    sample_gold_pairs = [pair for pair in candidate_gold_pairs if pair.get("job_id") in selected_job_ids]
    sample_silver_pairs = [pair for pair in candidate_silver_pairs if pair.get("job_id") in selected_job_ids]

    counts = {
        "candidate_profiles_sample": write_jsonl(sample_dir / "candidate_profiles_sample.jsonl", sample_candidates),
        "jobs_sample": write_jsonl(sample_dir / "jobs_sample.jsonl", sample_jobs),
        "label_pairs_gold_sample": write_jsonl(sample_dir / "label_pairs_gold_sample.jsonl", sample_gold_pairs),
        "label_pairs_silver_sample": write_jsonl(sample_dir / "label_pairs_silver_sample.jsonl", sample_silver_pairs),
    }
    write_json(
        sample_dir / "sample_manifest.json",
        {
            "purpose": "small fixed sample pack for parallel workflow development",
            "counts": counts,
            "candidate_ids": sorted(sample_candidate_ids),
            "job_ids": sorted(selected_job_ids),
            "notes": [
                "Use this sample pack when downstream workflows need stable local input before full data integration.",
                "Full generated data stays under artifacts/ and is not committed by default.",
            ],
        },
    )
    return counts


def build_data_quality_report(
    candidate_profiles: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    silver_pairs: list[dict[str, Any]],
    gold_pairs: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate_ids = {profile.get("candidate_id") for profile in candidate_profiles}
    job_ids = {job.get("job_id") for job in jobs}

    def orphan_counts(pairs: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "missing_candidate_refs": sum(1 for pair in pairs if pair.get("candidate_id") not in candidate_ids),
            "missing_job_refs": sum(1 for pair in pairs if pair.get("job_id") not in job_ids),
        }

    return {
        "record_counts": {
            "candidate_profiles": len(candidate_profiles),
            "jobs": len(jobs),
            "label_pairs_silver": len(silver_pairs),
            "label_pairs_gold": len(gold_pairs),
        },
        "job_source_type_counts": dict(Counter(job.get("source_type", "") for job in jobs)),
        "resume_split_counts": dict(Counter(profile.get("split", "") for profile in candidate_profiles)),
        "missing_fields": {
            "candidate_profiles": missing_field_count(
                candidate_profiles,
                ["candidate_id", "summary", "skills", "target_job_family"],
            ),
            "jobs": missing_field_count(
                jobs,
                ["job_id", "title", "description", "job_family", "source_type"],
            ),
            "label_pairs_silver": missing_field_count(
                silver_pairs,
                ["candidate_id", "job_id", "grade", "score"],
            ),
            "label_pairs_gold": missing_field_count(
                gold_pairs,
                ["candidate_id", "job_id", "grade"],
            ),
        },
        "reference_checks": {
            "silver": orphan_counts(silver_pairs),
            "gold": orphan_counts(gold_pairs),
        },
        "label_distribution": {
            "silver_grade_counts": grade_counts(silver_pairs),
            "gold_grade_counts": grade_counts(gold_pairs),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Adapt dataset-group artifacts for JobMatch AI.")
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--skip-government", action="store_true")
    parser.add_argument("--allow-missing-labels", action="store_true")
    args = parser.parse_args()

    dataset_dir = args.dataset_dir
    output_dir = args.output_dir

    enterprise_path = first_existing(dataset_dir, ENTERPRISE_JOB_CANDIDATES, required=True)
    resume_path = first_existing(dataset_dir, RESUME_CANDIDATES, required=True)
    government_path = first_existing(dataset_dir, GOVERNMENT_JOB_CANDIDATES)
    dictionary_path = first_existing(dataset_dir, (JOB_TITLE_DICTIONARY,))
    silver_path = first_existing(dataset_dir, SILVER_LABEL_CANDIDATES)
    gold_path = first_existing(dataset_dir, GOLD_LABEL_CANDIDATES)

    rules = load_job_title_rules(dictionary_path)
    enterprise_jobs = adapt_enterprise_jobs(read_csv_rows(enterprise_path), rules)
    government_jobs: list[dict[str, Any]] = []
    if government_path is not None and not args.skip_government:
        government_jobs = adapt_government_jobs(
            read_csv_rows(government_path),
            rules,
            start_index=len(enterprise_jobs) + 1,
            source_file=government_path.stem,
        )
    candidate_profiles = adapt_candidate_profiles(read_csv_rows(resume_path))
    silver_records = read_jsonl(silver_path) if silver_path else []
    gold_rows = read_csv_rows(gold_path) if gold_path else []
    silver_pairs = adapt_silver_pairs(silver_records)
    gold_pairs = adapt_gold_pairs(gold_rows)
    candidate_id_map = build_candidate_id_map(candidate_profiles)
    silver_pairs, silver_mapping_counts = normalize_label_pairs(silver_pairs, candidate_id_map)
    gold_pairs, gold_mapping_counts = normalize_label_pairs(gold_pairs, candidate_id_map)
    legacy_label_jobs = build_legacy_label_jobs(
        silver_records,
        gold_rows,
        rules,
        {job["job_id"] for job in enterprise_jobs + government_jobs},
    )
    jobs = enterprise_jobs + government_jobs + legacy_label_jobs

    if not args.allow_missing_labels and (not silver_pairs or not gold_pairs):
        raise FileNotFoundError(
            "Label files are missing. Add resume_job_silver_30.jsonl and 金标30×20.csv, "
            "or run with --allow-missing-labels."
        )

    counts = {
        "candidate_profiles": write_jsonl(output_dir / "candidate_profiles.jsonl", candidate_profiles),
        "jobs": write_jsonl(output_dir / "jobs.jsonl", jobs),
        "jobs_enterprise": write_jsonl(output_dir / "jobs_enterprise.jsonl", enterprise_jobs),
        "jobs_government": write_jsonl(output_dir / "jobs_government.jsonl", government_jobs),
        "jobs_label_legacy": write_jsonl(output_dir / "jobs_label_legacy.jsonl", legacy_label_jobs),
        "label_pairs_silver": write_jsonl(output_dir / "label_pairs_silver.jsonl", silver_pairs),
        "label_pairs_gold": write_jsonl(output_dir / "label_pairs_gold.jsonl", gold_pairs),
    }
    sample_counts = write_sample_pack(output_dir, candidate_profiles, jobs, silver_pairs, gold_pairs)
    quality_report = build_data_quality_report(candidate_profiles, jobs, silver_pairs, gold_pairs)
    write_json(output_dir / "data_quality_report.json", quality_report)

    manifest = {
        "iteration": "05",
        "workflow": "workflow_1_data_foundation_and_label_evaluation",
        "purpose": "large_dataset_adapter_schema_samples_quality_no_training",
        "dataset_dir": str(dataset_dir),
        "output_dir": str(output_dir),
        "inputs": {
            "enterprise_jobs": str(enterprise_path),
            "government_jobs": str(government_path) if government_path else "",
            "resumes": str(resume_path),
            "job_title_dictionary": str(dictionary_path) if dictionary_path else "",
            "silver": str(silver_path) if silver_path else "",
            "gold": str(gold_path) if gold_path else "",
        },
        "counts": counts,
        "sample_counts": sample_counts,
        "resume_splits": dict(Counter(profile.get("split", "") for profile in candidate_profiles)),
        "resume_job_families_top20": dict(Counter(profile.get("target_job_family", "") for profile in candidate_profiles).most_common(20)),
        "job_source_type_counts": dict(Counter(job.get("source_type", "") for job in jobs)),
        "label_mapping_counts": {
            "silver": silver_mapping_counts,
            "gold": gold_mapping_counts,
            "legacy_label_jobs": len(legacy_label_jobs),
        },
        "silver_grade_counts": grade_counts(silver_pairs),
        "gold_grade_counts": grade_counts(gold_pairs),
        "data_quality_report": str(output_dir / "data_quality_report.json"),
        "notes": [
            "No model training is performed.",
            "PII fields such as name, phone, and email are not emitted.",
            "jobs.jsonl combines enterprise and government technical jobs.",
            "jobs_label_legacy.jsonl reconstructs legacy label jobs so old gold/silver labels can still be evaluated.",
            "jobs_enterprise.jsonl and jobs_government.jsonl are split files for workflow-specific experiments.",
            "candidate_profiles.jsonl uses the expanded experience-aware synthetic resume file when available.",
            "sample_pack contains small stable examples for downstream parallel development.",
        ],
    }
    write_json(output_dir / "dataset_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
