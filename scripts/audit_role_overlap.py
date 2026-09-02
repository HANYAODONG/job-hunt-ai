"""Screen canonical roles for excessive overlap using the accepted JD corpus.

The output is an evidence-oriented screening report, not a semantic truth
claim. It identifies pairs that require market and human review before roles
are merged or activated.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend-src"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.canonical_role_pool import CanonicalRolePool  # noqa: E402

DEFAULT_INPUT = REPO_ROOT / "artifacts" / "canonical_role_pool_v1" / "data_group_current" / "canonical_jobs.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "canonical_role_pool_v1" / "data_group_current" / "role_overlap_audit_v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def normalize(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").casefold())


def skill_set(record: dict[str, Any]) -> set[str]:
    values = record.get("skills") or record.get("required_skills") or []
    if isinstance(values, str):
        values = re.split(r"[,;，；、]", values)
    return {normalize(value) for value in values if normalize(value)}


def title_signals(record: dict[str, Any]) -> set[str]:
    title = normalize(record.get("title") or record.get("job_title"))
    # Keep meaningful Chinese phrases and ASCII terms while dropping rank,
    # internship, company, and location suffixes.
    title = re.sub(r"(实习生|校招|应届|高级|资深|专家|负责人|leader|主管)$", "", title, flags=re.I)
    parts = set(re.findall(r"[a-z0-9+#.]+|[\u4e00-\u9fff]{2,}", title, flags=re.I))
    return {part for part in parts if len(part) >= 2}


def jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def weighted_skill_overlap(left: list[set[str]], right: list[set[str]]) -> float:
    """Average best-match Jaccard, avoiding domination by one giant JD."""
    if not left or not right:
        return 0.0
    forward = sum(max((jaccard(item, other) for other in right), default=0.0) for item in left) / len(left)
    backward = sum(max((jaccard(item, other) for other in left), default=0.0) for item in right) / len(right)
    return (forward + backward) / 2


def build(input_path: Path, output_dir: Path) -> dict[str, Any]:
    pool = CanonicalRolePool()
    records = read_jsonl(input_path)
    by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        role_id = str(record.get("canonical_role_id") or "")
        if role_id and role_id in pool.roles and pool.roles[role_id].status == "active":
            by_role[role_id].append(record)

    profiles: dict[str, dict[str, Any]] = {}
    for role_id, items in by_role.items():
        skill_counts = Counter(skill for item in items for skill in skill_set(item))
        title_counts = Counter(signal for item in items for signal in title_signals(item))
        profiles[role_id] = {
            "sample_count": len(items),
            "skills": {skill for skill, count in skill_counts.items() if count >= max(2, math.ceil(len(items) * 0.02))},
            "top_skills": [skill for skill, _ in skill_counts.most_common(30)],
            "titles": {signal for signal, count in title_counts.items() if count >= max(2, math.ceil(len(items) * 0.03))},
            # A deterministic cap keeps the pairwise screen bounded while
            # retaining enough JD evidence for each role profile.
            "job_skill_sets": [skill_set(item) for item in sorted(items, key=lambda item: str(item.get("job_id") or ""))[:40]],
        }

    pairs: list[dict[str, Any]] = []
    role_ids = sorted(profiles)
    for index, role_a in enumerate(role_ids):
        for role_b in role_ids[index + 1:]:
            left, right = profiles[role_a], profiles[role_b]
            profile_skill = jaccard(left["skills"], right["skills"])
            jd_best_match = weighted_skill_overlap(left["job_skill_sets"], right["job_skill_sets"])
            title_overlap = jaccard(left["titles"], right["titles"])
            # High pair risk requires both profile-level and JD-level evidence;
            # a single shared generic skill (Python, Java, SQL) is insufficient.
            if profile_skill >= 0.28 and jd_best_match >= 0.32:
                risk = "high"
            elif profile_skill >= 0.20 or jd_best_match >= 0.25 or title_overlap >= 0.25:
                risk = "medium"
            else:
                risk = "low"
            pairs.append({
                "role_id_a": role_a,
                "role_a": pool.roles[role_a].role_name,
                "role_id_b": role_b,
                "role_b": pool.roles[role_b].role_name,
                "sample_a": left["sample_count"],
                "sample_b": right["sample_count"],
                "profile_skill_jaccard": round(profile_skill, 4),
                "jd_best_match_skill_jaccard": round(jd_best_match, 4),
                "title_signal_jaccard": round(title_overlap, 4),
                "risk": risk,
                "shared_profile_skills": sorted(left["skills"] & right["skills"]),
            })

    pairs.sort(key=lambda item: (
        -{"high": 3, "medium": 2, "low": 1}[item["risk"]],
        -item["jd_best_match_skill_jaccard"],
        -item["profile_skill_jaccard"],
    ))
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "role_overlap_pairs.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = [key for key in pairs[0] if key != "shared_profile_skills"] if pairs else []
        writer = csv.DictWriter(handle, fieldnames=fields + ["shared_profile_skills"])
        if fields:
            writer.writeheader()
            for item in pairs:
                row = {**item, "shared_profile_skills": "；".join(item["shared_profile_skills"])}
                writer.writerow(row)

    report = {
        "input": str(input_path),
        "accepted_records": len(records),
        "active_role_profiles": len(profiles),
        "role_pair_count": len(pairs),
        "risk_pair_counts": dict(sorted(Counter(item["risk"] for item in pairs).items())),
        "high_risk_pairs": [item for item in pairs if item["risk"] == "high"][:50],
        "method": {
            "profile_skill_jaccard": "Jaccard of skills appearing in at least 2% of each role's JD sample",
            "jd_best_match_skill_jaccard": "symmetric average of each JD's best skill-set match in the other role",
            "title_signal_jaccard": "Jaccard of recurring title signals after rank/location cleanup",
            "caveat": "Screening evidence only; activation or merge decisions require market-title and human JD review.",
        },
        "outputs": {"pairs_csv": str(csv_path)},
    }
    (output_dir / "role_overlap_audit_v1_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit overlap among active canonical roles.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    print(json.dumps(build(args.input, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
