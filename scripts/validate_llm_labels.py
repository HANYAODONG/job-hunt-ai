"""Validate workflow 1 LLM label JSONL files.

The validator checks schema, grade distribution, evidence completeness,
duplicate pairs, and optional consistency against the candidate pool.
It does not decide label correctness; it flags records that need review.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ITERATION_DIR = REPO_ROOT / "artifacts" / "dataset_iteration_05"
DEFAULT_LABELS = DEFAULT_ITERATION_DIR / "label_pairs_llm.jsonl"
DEFAULT_CANDIDATES = DEFAULT_ITERATION_DIR / "llm_label_candidates.jsonl"
DEFAULT_OUTPUT = DEFAULT_ITERATION_DIR / "llm_label_quality_report.json"


REQUIRED_FIELDS = {
    "candidate_id",
    "job_id",
    "grade",
    "hard_constraint_pass",
    "matched_skills",
    "missing_required_skills",
    "resume_evidence",
    "job_evidence",
    "confidence",
    "label_source",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
            record["_line_number"] = line_number
            records.append(record)
    return records


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value == "" or value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_candidate_pool(path: Path | None) -> set[tuple[str, str]]:
    if not path or not path.exists():
        return set()
    pairs: set[tuple[str, str]] = set()
    for batch in read_jsonl(path):
        candidate_id = str(batch.get("candidate_id") or batch.get("query_id") or "")
        for item in batch.get("candidates", []):
            job_id = str(item.get("job_id") or "")
            if candidate_id and job_id:
                pairs.add((candidate_id, job_id))
    return pairs


def validate(records: Iterable[dict[str, Any]], candidate_pool: set[tuple[str, str]]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    pair_counts: Counter[tuple[str, str]] = Counter()
    grade_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    confidence_values: list[float] = []
    candidate_record_counts: Counter[str] = Counter()

    for record in records:
        line = record.get("_line_number")
        missing = sorted(field for field in REQUIRED_FIELDS if field not in record)
        if missing:
            issues.append({"line": line, "type": "missing_required_fields", "fields": missing})

        candidate_id = str(record.get("candidate_id") or record.get("query_id") or "")
        job_id = str(record.get("job_id") or "")
        if not candidate_id or not job_id:
            issues.append({"line": line, "type": "missing_pair_id", "candidate_id": candidate_id, "job_id": job_id})
            continue

        pair = (candidate_id, job_id)
        pair_counts[pair] += 1
        candidate_record_counts[candidate_id] += 1
        if candidate_pool and pair not in candidate_pool:
            issues.append({"line": line, "type": "pair_not_in_candidate_pool", "candidate_id": candidate_id, "job_id": job_id})

        grade = record.get("grade")
        if grade not in (0, 1, 2, 3):
            issues.append({"line": line, "type": "invalid_grade", "value": grade})
        else:
            grade_counts[str(grade)] += 1

        confidence = safe_float(record.get("confidence"))
        if confidence is None or confidence < 0 or confidence > 1:
            issues.append({"line": line, "type": "invalid_confidence", "value": record.get("confidence")})
        else:
            confidence_values.append(confidence)
            if confidence < 0.55:
                issues.append({"line": line, "type": "low_confidence_review_needed", "confidence": confidence})

        hard_constraint = record.get("hard_constraint_pass")
        if not isinstance(hard_constraint, bool):
            issues.append({"line": line, "type": "invalid_hard_constraint_pass", "value": hard_constraint})

        if grade in (2, 3) and not record.get("resume_evidence"):
            issues.append({"line": line, "type": "positive_label_missing_resume_evidence"})
        if grade in (2, 3) and not record.get("job_evidence"):
            issues.append({"line": line, "type": "positive_label_missing_job_evidence"})
        if grade == 0 and record.get("matched_skills") and not record.get("missing_required_skills"):
            issues.append({"line": line, "type": "negative_label_needs_rationale_check"})

        source_counts[str(record.get("label_source") or "")] += 1

    duplicate_pairs = [
        {"candidate_id": pair[0], "job_id": pair[1], "count": count}
        for pair, count in pair_counts.items()
        if count > 1
    ]
    for duplicate in duplicate_pairs:
        issues.append({"type": "duplicate_pair", **duplicate})

    confidence_avg = sum(confidence_values) / len(confidence_values) if confidence_values else None
    return {
        "records": sum(pair_counts.values()),
        "unique_pairs": len(pair_counts),
        "candidate_count": len(candidate_record_counts),
        "grade_counts": dict(grade_counts),
        "source_counts": dict(source_counts),
        "confidence_avg": confidence_avg,
        "confidence_min": min(confidence_values) if confidence_values else None,
        "confidence_max": max(confidence_values) if confidence_values else None,
        "duplicate_pairs": duplicate_pairs,
        "issue_count": len(issues),
        "issues": issues[:500],
        "notes": [
            "This report validates format and consistency only.",
            "Formal gold labels should be confirmed by manual review.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate workflow 1 LLM label JSONL output.")
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--candidate-pool", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.labels.exists():
        raise FileNotFoundError(f"Missing labels file: {args.labels}")
    records = read_jsonl(args.labels)
    candidate_pool = load_candidate_pool(args.candidate_pool)
    report = validate(records, candidate_pool)
    write_json(args.output, report)
    print(f"Wrote LLM label quality report: {args.output}")
    print(f"Records: {report['records']} | Issues: {report['issue_count']}")


if __name__ == "__main__":
    main()
