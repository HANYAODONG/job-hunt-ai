"""Evaluate task-book extraction results against frozen human-adjudicated gold.

This script intentionally refuses incomplete adjudication sheets. It is the
single reproducible entry point for the task-book's >=90% acceptance metrics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend-src"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.nlp_service import NLPService


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "unknown"
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_array(value: str, field: str, sample_id: str) -> list[str]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{sample_id}: {field} must be a JSON array") from exc
    if not isinstance(payload, list):
        raise ValueError(f"{sample_id}: {field} must be a JSON array")
    return [str(item).strip() for item in payload if str(item).strip()]


def norm(values: list[str]) -> set[str]:
    return {value.strip().casefold() for value in values if value.strip()}


def counts(predicted: list[str], gold: list[str]) -> tuple[int, int, int]:
    predicted_set = norm(predicted)
    gold_set = norm(gold)
    return (
        len(predicted_set & gold_set),
        len(predicted_set - gold_set),
        len(gold_set - predicted_set),
    )


def score(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
    }


def require_complete(rows: list[dict[str, str]], fields: list[str], sheet: str) -> None:
    missing = [
        f"{row.get('sample_id', '?')}:{field}"
        for row in rows
        for field in fields
        if not str(row.get(field, "")).strip()
    ]
    if missing:
        preview = ", ".join(missing[:10])
        raise ValueError(f"{sheet} is not frozen: {len(missing)} blank labels ({preview})")


def evaluate_jd(rows: list[dict[str, str]], service: NLPService) -> dict[str, Any]:
    require_complete(rows, ["gold_required_skills", "is_parseable", "annotator"], "JD gold")
    tp = fp = fn = 0
    parseable = 0
    for row in rows:
        if row["is_parseable"].strip().casefold() != "yes":
            continue
        parseable += 1
        gold = parse_array(row["gold_required_skills"], "gold_required_skills", row["sample_id"])
        gold += parse_array(row.get("gold_optional_skills", "[]") or "[]", "gold_optional_skills", row["sample_id"])
        predicted = service.extract_job_requirements(row["description"]).get("required_skills", [])
        row_tp, row_fp, row_fn = counts(predicted, gold)
        tp += row_tp
        fp += row_fp
        fn += row_fn
    return {"samples": len(rows), "parseable_samples": parseable, "skill_micro": score(tp, fp, fn)}


def evaluate_resume(rows: list[dict[str, str]], service: NLPService) -> dict[str, Any]:
    require_complete(rows, ["gold_skills", "is_parseable", "annotator"], "resume gold")
    tp = fp = fn = 0
    years_total = years_correct = parseable = 0
    for row in rows:
        if row["is_parseable"].strip().casefold() != "yes":
            continue
        parseable += 1
        gold = parse_array(row["gold_skills"], "gold_skills", row["sample_id"])
        prediction = service.extract_candidate_profile(row["resume_text"])
        row_tp, row_fp, row_fn = counts(prediction.get("skills", []), gold)
        tp += row_tp
        fp += row_fp
        fn += row_fn
        if row.get("gold_years_experience", "").strip():
            years_total += 1
            expected = float(row["gold_years_experience"])
            actual = prediction.get("years_experience")
            years_correct += int(actual is not None and abs(float(actual) - expected) < 0.01)
    return {
        "samples": len(rows),
        "parseable_samples": parseable,
        "skill_micro": score(tp, fp, fn),
        "years_exact_accuracy": round(years_correct / years_total, 6) if years_total else None,
        "years_labeled_samples": years_total,
    }


def validate_matching(rows: list[dict[str, str]]) -> dict[str, Any]:
    require_complete(
        rows,
        ["gold_grade_0_to_3", "hard_constraint_pass_yes_no", "annotator"],
        "matching gold",
    )
    grades = [int(row["gold_grade_0_to_3"]) for row in rows]
    if any(grade not in {0, 1, 2, 3} for grade in grades):
        raise ValueError("matching grades must be integers from 0 to 3")
    return {
        "samples": len(rows),
        "positive_samples_grade_ge_2": sum(grade >= 2 for grade in grades),
        "negative_samples_grade_lt_2": sum(grade < 2 for grade in grades),
        "status": "gold_validated; pass --matching-predictions for model scoring",
    }


def evaluate_matching_predictions(
    gold_rows: list[dict[str, str]], prediction_path: Path
) -> dict[str, Any]:
    prediction_rows = read_csv(prediction_path)
    predictions = {row["sample_id"]: row for row in prediction_rows}
    expected_ids = {row["sample_id"] for row in gold_rows}
    if set(predictions) != expected_ids:
        raise ValueError("matching predictions must contain exactly the adjudicated sample_id set")
    correct = tp = fp = fn = 0
    for row in gold_rows:
        expected = int(row["gold_grade_0_to_3"]) >= 2
        predicted = int(predictions[row["sample_id"]]["predicted_grade_0_to_3"]) >= 2
        correct += int(expected == predicted)
        tp += int(expected and predicted)
        fp += int(not expected and predicted)
        fn += int(expected and not predicted)
    result = score(tp, fp, fn)
    result["accuracy"] = round(correct / len(gold_rows), 6)
    result["prediction_sha256"] = sha256(prediction_path)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate frozen task-book human gold")
    parser.add_argument("--gold-dir", type=Path, default=REPO_ROOT / "artifacts" / "taskbook_gold_v1")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "artifacts" / "taskbook_acceptance_20260830" / "human_gold_metrics.json")
    parser.add_argument("--matching-predictions", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = {
        "jd": args.gold_dir / "jd_annotation_adjudicated.csv",
        "resume": args.gold_dir / "resume_annotation_adjudicated.csv",
        "matching": args.gold_dir / "matching_annotation_adjudicated.csv",
    }
    rows = {name: read_csv(path) for name, path in paths.items()}
    annotators = sorted(
        {
            row.get("annotator", "").strip()
            for sheet_rows in rows.values()
            for row in sheet_rows
            if row.get("annotator", "").strip()
        }
    )
    is_provisional = any("provisional" in annotator.casefold() for annotator in annotators)
    approval_path = args.gold_dir / "human_review_approval_manifest.json"
    approval = (
        json.loads(approval_path.read_text(encoding="utf-8"))
        if approval_path.exists()
        else None
    )
    is_human_approved = bool(
        approval and approval.get("status") == "human_review_approved"
    )
    service = NLPService()
    result: dict[str, Any] = {
        "status": (
            "provisional_machine_assisted_baseline_not_formal_acceptance"
            if is_provisional
            else "human_reviewed_acceptance_evaluation"
        ),
        "formal_acceptance_eligible": not is_provisional and is_human_approved,
        "annotators": annotators,
        "human_review_approval": approval,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "gold_files": {name: {"path": str(path), "sha256": sha256(path)} for name, path in paths.items()},
        "jd_parsing": evaluate_jd(rows["jd"], service),
        "resume_extraction": evaluate_resume(rows["resume"], service),
        "matching": validate_matching(rows["matching"]),
    }
    if args.matching_predictions:
        result["matching"]["model_scores"] = evaluate_matching_predictions(
            rows["matching"], args.matching_predictions
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
