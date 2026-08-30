"""Compare two blind task-book annotations and emit adjudication queues."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD_DIR = REPO_ROOT / "artifacts" / "taskbook_gold_v1"

SHEETS = {
    "jd": {
        "fields": [
            "gold_required_skills",
            "gold_optional_skills",
            "gold_responsibilities",
            "is_parseable",
        ],
        "array_fields": {
            "gold_required_skills",
            "gold_optional_skills",
            "gold_responsibilities",
        },
    },
    "resume": {
        "fields": [
            "gold_name",
            "gold_skills",
            "gold_years_experience",
            "gold_education",
            "gold_experience_titles",
            "is_parseable",
        ],
        "array_fields": {"gold_skills", "gold_experience_titles"},
    },
    "matching": {
        "fields": [
            "gold_grade_0_to_3",
            "hard_constraint_pass_yes_no",
            "matched_skills",
            "missing_required_skills",
        ],
        "array_fields": {"matched_skills", "missing_required_skills"},
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize(value: str, is_array: bool) -> object:
    value = value.strip()
    if not is_array:
        return value.casefold()
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return ("invalid_json", value)
    if not isinstance(payload, list):
        return ("not_array", value)
    return tuple(sorted({str(item).strip().casefold() for item in payload if str(item).strip()}))


def compare_sheet(gold_dir: Path, name: str, output_dir: Path) -> dict[str, object]:
    config = SHEETS[name]
    rows_a = read_csv(gold_dir / f"{name}_annotation_A.csv")
    rows_b = read_csv(gold_dir / f"{name}_annotation_B.csv")
    by_id_a = {row["sample_id"]: row for row in rows_a}
    by_id_b = {row["sample_id"]: row for row in rows_b}
    if set(by_id_a) != set(by_id_b):
        raise ValueError(f"{name}: A/B sample_id sets differ")

    required = list(config["fields"]) + ["annotator"]
    blanks = [
        f"{sample_id}:{side}:{field}"
        for sample_id in sorted(by_id_a)
        for side, row in (("A", by_id_a[sample_id]), ("B", by_id_b[sample_id]))
        for field in required
        if not row.get(field, "").strip()
    ]
    if blanks:
        raise ValueError(f"{name}: {len(blanks)} blank labels; first: {', '.join(blanks[:8])}")

    disagreements: list[dict[str, str]] = []
    agreed_samples = 0
    field_agreements = {field: 0 for field in config["fields"]}
    for sample_id in sorted(by_id_a):
        row_a = by_id_a[sample_id]
        row_b = by_id_b[sample_id]
        differing_fields = []
        for field in config["fields"]:
            equal = normalize(row_a[field], field in config["array_fields"]) == normalize(
                row_b[field], field in config["array_fields"]
            )
            field_agreements[field] += int(equal)
            if not equal:
                differing_fields.append(field)
                disagreements.append(
                    {
                        "sample_id": sample_id,
                        "field": field,
                        "annotator_A": row_a[field],
                        "annotator_B": row_b[field],
                    }
                )
        agreed_samples += int(not differing_fields)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{name}_disagreements.csv"
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["sample_id", "field", "annotator_A", "annotator_B"]
        )
        writer.writeheader()
        writer.writerows(disagreements)

    total = len(by_id_a)
    return {
        "samples": total,
        "exact_sample_agreement": round(agreed_samples / total, 6) if total else 0.0,
        "field_agreement": {
            field: round(count / total, 6) if total else 0.0
            for field, count in field_agreements.items()
        },
        "disagreement_cells": len(disagreements),
        "queue": str(output_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare blind A/B task-book annotations")
    parser.add_argument("--gold-dir", type=Path, default=DEFAULT_GOLD_DIR)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir or args.gold_dir / "adjudication_queue"
    report = {
        name: compare_sheet(args.gold_dir, name, output_dir) for name in SHEETS
    }
    report_path = output_dir / "agreement_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
