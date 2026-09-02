"""Finalize a fully adjudicated JD-to-role gold draft from a review candidate pack."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend-src"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.canonical_role_pool import CanonicalRolePool  # noqa: E402


DEFAULT_CANDIDATES = (
    REPO_ROOT / "artifacts" / "canonical_role_pool_v1" / "data_group_current" /
    "gold_candidates" / "role_mapping_gold_candidates.jsonl"
)
DEFAULT_ANNOTATIONS = REPO_ROOT / "backend-src" / "app" / "data" / "canonical_role_pool" / "v1" / "role_mapping_gold_annotations_v1.csv"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "canonical_role_pool_v1" / "data_group_current" / "role_mapping_gold_v1"

DECISIONS_REQUIRING_ROLE = {"accept_proposal", "replace_existing"}
VALID_DECISIONS = DECISIONS_REQUIRING_ROLE | {
    "new_role_candidate",
    "exclude_out_of_scope",
    "insufficient_evidence",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_annotations(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        result: dict[str, dict[str, str]] = {}
        for row in csv.DictReader(handle):
            case_id = str(row.get("case_id") or "").strip()
            if not case_id or case_id in result:
                raise ValueError(f"Invalid or duplicate annotation case ID: {case_id!r}")
            result[case_id] = {key: str(value or "").strip() for key, value in row.items()}
        return result


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def build(candidates_path: Path, annotations_path: Path, output_dir: Path) -> dict[str, Any]:
    candidates = read_jsonl(candidates_path)
    annotations = read_annotations(annotations_path)
    candidate_ids = {str(candidate.get("case_id") or "") for candidate in candidates}
    if candidate_ids != set(annotations):
        raise ValueError(
            "Candidate/annotation case IDs differ: "
            f"missing={sorted(candidate_ids - set(annotations))}, "
            f"extra={sorted(set(annotations) - candidate_ids)}"
        )

    pool = CanonicalRolePool()
    gold_records: list[dict[str, Any]] = []
    for candidate in candidates:
        annotation = annotations[candidate["case_id"]]
        decision = annotation["review_decision"]
        role_id = annotation["final_canonical_role_id"]
        new_role = annotation["new_role_candidate_name"]
        if decision not in VALID_DECISIONS:
            raise ValueError(f"Invalid decision for {candidate['case_id']}: {decision}")
        if decision in DECISIONS_REQUIRING_ROLE:
            role = pool.roles.get(role_id)
            if role is None or role.status != "active":
                raise ValueError(f"Decision {decision} requires an active role ID for {candidate['case_id']}")
        elif role_id:
            raise ValueError(f"Decision {decision} must not set a canonical role ID for {candidate['case_id']}")
        if decision == "new_role_candidate" and not new_role:
            raise ValueError(f"New role candidate must name the proposed role for {candidate['case_id']}")
        if decision != "new_role_candidate" and new_role:
            raise ValueError(f"Only new_role_candidate may name a new role for {candidate['case_id']}")

        role = pool.roles.get(role_id)
        gold_records.append({
            **candidate,
            "review_decision": decision,
            "final_canonical_role_id": role_id,
            "final_canonical_role": role.role_name if role else "",
            "final_domain": role.domain if role else "",
            "final_direction": role.direction if role else "",
            "new_role_candidate_name": new_role,
            "review_evidence": annotation["review_evidence"],
            "annotator_id": "codex_role_pool_adjudication",
            "reviewed_at": "2026-08-31",
            "label_source": "codex_adjudicated_gold_draft",
            "label_status": "requires_human_signoff_before_external_claims",
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "role_mapping_gold_v1.jsonl"
    write_jsonl(output_path, gold_records)
    changed = sum(
        1
        for record in gold_records
        if record["review_decision"] == "replace_existing"
    )
    report = {
        "label_type": "jd_to_canonical_role",
        "label_source": "codex_adjudicated_gold_draft",
        "label_status": "requires_human_signoff_before_external_claims",
        "records": len(gold_records),
        "decision_counts": dict(sorted(Counter(record["review_decision"] for record in gold_records).items())),
        "accepted_existing_roles": len({
            record["final_canonical_role_id"]
            for record in gold_records if record["final_canonical_role_id"]
        }),
        "proposal_replacements": changed,
        "new_role_candidates": sorted({
            record["new_role_candidate_name"]
            for record in gold_records if record["new_role_candidate_name"]
        }),
        "output": str(output_path),
    }
    (output_dir / "role_mapping_gold_v1_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Finalize an adjudicated JD-to-role gold draft.")
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATIONS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    print(json.dumps(build(args.candidates, args.annotations, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
