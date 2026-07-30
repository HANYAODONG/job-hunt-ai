"""Validate Workflow 1 standard dataset outputs.

This script checks whether dataset_adapter.py has produced the files and
references required by downstream BM25, semantic rerank, KG, and fusion modules.
It does not train models or call external services.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_DIR = REPO_ROOT / "artifacts" / "dataset_iteration_05"


REQUIRED_FILES = (
    "jobs.jsonl",
    "candidate_profiles.jsonl",
    "label_pairs_gold.jsonl",
    "label_pairs_silver.jsonl",
    "data_quality_report.json",
    "dataset_manifest.json",
    "sample_pack/candidate_profiles_sample.jsonl",
    "sample_pack/jobs_sample.jsonl",
    "sample_pack/label_pairs_gold_sample.jsonl",
    "sample_pack/label_pairs_silver_sample.jsonl",
    "sample_pack/sample_manifest.json",
)


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


def load_ids(records: Iterable[dict[str, Any]], field: str) -> set[str]:
    return {str(record.get(field) or "") for record in records if record.get(field)}


def missing_required_fields(records: list[dict[str, Any]], fields: tuple[str, ...]) -> dict[str, int]:
    return {
        field: sum(1 for record in records if record.get(field) in (None, "", []))
        for field in fields
    }


def validate(dataset_dir: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    files: dict[str, dict[str, Any]] = {}

    for relative in REQUIRED_FILES:
        path = dataset_dir / relative
        files[relative] = {
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else 0,
        }
        if not path.exists():
            errors.append(f"Missing required file: {relative}")

    if errors:
        return {"dataset_dir": str(dataset_dir), "files": files, "status": "fail"}, errors

    jobs = read_jsonl(dataset_dir / "jobs.jsonl")
    candidates = read_jsonl(dataset_dir / "candidate_profiles.jsonl")
    gold = read_jsonl(dataset_dir / "label_pairs_gold.jsonl")
    silver = read_jsonl(dataset_dir / "label_pairs_silver.jsonl")

    job_ids = load_ids(jobs, "job_id")
    candidate_ids = load_ids(candidates, "candidate_id")

    duplicate_job_ids = len(jobs) - len(job_ids)
    duplicate_candidate_ids = len(candidates) - len(candidate_ids)
    if duplicate_job_ids:
        errors.append(f"Duplicate job_id count: {duplicate_job_ids}")
    if duplicate_candidate_ids:
        errors.append(f"Duplicate candidate_id count: {duplicate_candidate_ids}")

    def count_missing_refs(labels: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "missing_candidate_refs": sum(
                1 for record in labels if str(record.get("candidate_id") or "") not in candidate_ids
            ),
            "missing_job_refs": sum(
                1 for record in labels if str(record.get("job_id") or "") not in job_ids
            ),
        }

    reference_checks = {
        "gold": count_missing_refs(gold),
        "silver": count_missing_refs(silver),
    }
    for label_name, checks in reference_checks.items():
        for check_name, count in checks.items():
            if count:
                errors.append(f"{label_name} {check_name}: {count}")

    report = {
        "dataset_dir": str(dataset_dir),
        "files": files,
        "counts": {
            "jobs": len(jobs),
            "candidate_profiles": len(candidates),
            "label_pairs_gold": len(gold),
            "label_pairs_silver": len(silver),
        },
        "missing_required_fields": {
            "jobs": missing_required_fields(jobs, ("job_id", "title", "description", "source_type")),
            "candidate_profiles": missing_required_fields(
                candidates, ("candidate_id", "summary", "skills", "target_job_family")
            ),
            "label_pairs_gold": missing_required_fields(gold, ("candidate_id", "job_id", "grade")),
            "label_pairs_silver": missing_required_fields(silver, ("candidate_id", "job_id", "grade")),
        },
        "reference_checks": reference_checks,
        "job_source_type_counts": Counter(str(record.get("source_type") or "unknown") for record in jobs),
        "label_distribution": {
            "gold_grade_counts": Counter(str(record.get("grade")) for record in gold),
            "silver_grade_counts": Counter(str(record.get("grade")) for record in silver),
        },
        "status": "pass" if not errors else "fail",
    }
    return report, errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    report, errors = validate(args.dataset_dir)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")

    if errors:
        print("\nValidation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
