"""Build a review-ready JD-to-canonical-role gold-candidate pack.

The current matching gold labels grade resume/JD relevance. They are audited as
context but are never relabelled as job-to-role gold without a reviewer.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POOL_DIR = REPO_ROOT / "artifacts" / "canonical_role_pool_v1" / "data_group_current"
DEFAULT_DATASET_DIR = REPO_ROOT / "artifacts" / "dataset_iteration_05"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _description_excerpt(record: dict[str, Any], limit: int = 800) -> str:
    return " ".join(str(record.get("description") or "").split())[:limit]


def _candidate(record: dict[str, Any], bucket: str, case_number: int) -> dict[str, Any]:
    return {
        "case_id": f"role_pool_v1_{case_number:03d}",
        "sampling_bucket": bucket,
        "job_id": str(record.get("job_id") or record.get("id") or ""),
        "source": str(record.get("source") or ""),
        "source_type": str(record.get("source_type") or ""),
        "title": str(record.get("title") or ""),
        "description_excerpt": _description_excerpt(record),
        "skills": list(record.get("skills") or record.get("required_skills") or []),
        "source_standard_job": str(record.get("source_standard_job") or record.get("standard_job") or ""),
        "proposed_canonical_role_id": str(record.get("canonical_role_id") or ""),
        "proposed_canonical_role": str(record.get("canonical_role") or record.get("standard_job") or ""),
        "proposed_domain": str(record.get("canonical_domain") or record.get("standard_category") or ""),
        "proposed_direction": str(record.get("canonical_direction") or record.get("standard_direction") or ""),
        "proposed_mapping_status": str(record.get("role_mapping_status") or ""),
        "proposed_mapping_confidence": record.get("role_mapping_confidence"),
        "proposed_review_reasons": list(record.get("role_mapping_review_reasons") or []),
        # Blank fields are intentionally reviewer-owned. This file is not gold yet.
        "review_decision": "",
        "final_canonical_role_id": "",
        "review_evidence": "",
        "annotator_id": "",
        "reviewed_at": "",
    }


def select_candidates(
    accepted: list[dict[str, Any]], review: list[dict[str, Any]], target_count: int
) -> list[tuple[dict[str, Any], str]]:
    """Cover each observed role once, then fill with balanced difficult cases."""
    selected: list[tuple[dict[str, Any], str]] = []
    selected_ids: set[str] = set()
    by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in accepted:
        by_role[str(record.get("canonical_role_id") or "")].append(record)
    for role_id in sorted(role_id for role_id in by_role if role_id):
        record = min(by_role[role_id], key=lambda item: str(item.get("job_id") or ""))
        selected.append((record, "mapped_role_coverage"))
        selected_ids.add(str(record.get("job_id") or ""))

    review_groups: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    for record in sorted(review, key=lambda item: str(item.get("job_id") or "")):
        reasons = record.get("role_mapping_review_reasons") or ["其他待裁决"]
        review_groups[str(reasons[0])].append(record)
    group_order = deque(sorted(review_groups))
    while len(selected) < target_count and group_order:
        reason = group_order.popleft()
        group = review_groups[reason]
        while group and str(group[0].get("job_id") or "") in selected_ids:
            group.popleft()
        if group:
            record = group.popleft()
            selected.append((record, f"review:{reason}"))
            selected_ids.add(str(record.get("job_id") or ""))
        if group:
            group_order.append(reason)

    # If difficult cases are insufficient, add a second deterministic example per role.
    remaining = [
        record
        for role_id in sorted(by_role)
        for record in sorted(by_role[role_id], key=lambda item: str(item.get("job_id") or ""))
        if str(record.get("job_id") or "") not in selected_ids
    ]
    for record in remaining:
        if len(selected) >= target_count:
            break
        selected.append((record, "mapped_role_second_example"))
        selected_ids.add(str(record.get("job_id") or ""))
    return selected[:target_count]


def existing_matching_gold_audit(
    matching_gold: list[dict[str, Any]], legacy_jobs: list[dict[str, Any]], canonical_jobs: list[dict[str, Any]]
) -> dict[str, Any]:
    gold_job_ids = {str(record.get("job_id") or "") for record in matching_gold}
    legacy_job_ids = {str(record.get("job_id") or "") for record in legacy_jobs}
    canonical_job_ids = {str(record.get("job_id") or "") for record in canonical_jobs}
    return {
        "asset_type": "resume_to_job_relevance_labels",
        "not_role_mapping_gold": True,
        "gold_pairs": len(matching_gold),
        "gold_grade_counts": dict(sorted(Counter(str(record.get("grade")) for record in matching_gold).items())),
        "job_id_overlap_with_legacy_jobs": len(gold_job_ids & legacy_job_ids),
        "job_id_overlap_with_current_canonical_jobs": len(gold_job_ids & canonical_job_ids),
        "conclusion": (
            "Existing labels may be retained for legacy matching analysis, but cannot evaluate the "
            "current canonical role pool until their JD identities are reconciled and role labels are reviewed."
        ),
    }


def build(
    canonical_path: Path,
    review_path: Path,
    matching_gold_path: Path,
    legacy_jobs_path: Path,
    output_dir: Path,
    target_count: int = 120,
) -> dict[str, Any]:
    accepted = read_jsonl(canonical_path)
    review = read_jsonl(review_path)
    matching_gold = read_jsonl(matching_gold_path)
    legacy_jobs = read_jsonl(legacy_jobs_path)
    selected = select_candidates(accepted, review, target_count)
    candidates = [_candidate(record, bucket, index) for index, (record, bucket) in enumerate(selected, start=1)]

    output_dir.mkdir(parents=True, exist_ok=True)
    candidates_path = output_dir / "role_mapping_gold_candidates.jsonl"
    csv_path = output_dir / "role_mapping_gold_candidates.csv"
    audit_path = output_dir / "existing_matching_gold_audit.json"
    write_jsonl(candidates_path, candidates)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(candidates[0]) if candidates else [])
        if candidates:
            writer.writeheader()
            for candidate in candidates:
                row = dict(candidate)
                for field in ("skills", "proposed_review_reasons"):
                    row[field] = "；".join(str(item) for item in row[field])
                writer.writerow(row)

    audit = existing_matching_gold_audit(matching_gold, legacy_jobs, accepted)
    mapped_candidate_role_ids = {
        item["proposed_canonical_role_id"]
        for item in candidates
        if item["proposed_mapping_status"] == "mapped" and item["proposed_canonical_role_id"]
    }
    audit.update({
        "candidate_pack_type": "jd_to_role_manual_gold_candidates",
        "candidate_count": len(candidates),
        "mapped_role_identities_covered": len(mapped_candidate_role_ids),
        "review_cases": sum(
            1 for item in candidates if item["proposed_mapping_status"] != "mapped"
        ),
        "sampling_buckets": dict(sorted(Counter(item["sampling_bucket"] for item in candidates).items())),
        "outputs": {
            "review_jsonl": str(candidates_path),
            "review_csv": str(csv_path),
        },
    })
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a human-reviewable JD-to-role gold-candidate pack.")
    parser.add_argument("--canonical-jobs", type=Path, default=DEFAULT_POOL_DIR / "canonical_jobs.jsonl")
    parser.add_argument("--review-queue", type=Path, default=DEFAULT_POOL_DIR / "role_mapping_review.jsonl")
    parser.add_argument("--matching-gold", type=Path, default=DEFAULT_DATASET_DIR / "label_pairs_gold.jsonl")
    parser.add_argument("--legacy-jobs", type=Path, default=DEFAULT_DATASET_DIR / "jobs_label_legacy.jsonl")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_POOL_DIR / "gold_candidates")
    parser.add_argument("--target-count", type=int, default=120)
    args = parser.parse_args()
    print(json.dumps(build(
        args.canonical_jobs, args.review_queue, args.matching_gold, args.legacy_jobs,
        args.output_dir, args.target_count,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
