"""Run stratified out-of-fold evaluation on frozen matching labels."""

from __future__ import annotations

import argparse
import csv
import json
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from generate_semantic_artifacts import load_jsonl
from app.services.role_taxonomy import role_affinity


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT if (BACKEND_ROOT / "artifacts").exists() else BACKEND_ROOT.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Five-fold task-book matching evaluation")
    parser.add_argument("--dataset-dir", type=Path, default=REPO_ROOT / "artifacts" / "dataset_iteration_05")
    parser.add_argument("--gold-dir", type=Path, default=REPO_ROOT / "artifacts" / "taskbook_gold_v1")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "artifacts" / "taskbook_acceptance_20260830" / "matching_bge_small_cv")
    parser.add_argument("--model", default="BAAI/bge-small-zh-v1.5")
    parser.add_argument("--seed", type=int, default=20260830)
    return parser.parse_args()


def pair_text(candidate: dict, job: dict) -> tuple[str, str]:
    left = " ".join(
        [
            str(candidate.get("target_job_family") or ""),
            " ".join(candidate.get("skills_normalized") or candidate.get("skills") or []),
            str(candidate.get("summary") or ""),
        ]
    )
    right = " ".join(
        [
            str(job.get("title") or ""),
            str(job.get("job_family") or ""),
            " ".join(job.get("required_skills") or job.get("skills") or []),
            str(job.get("description") or ""),
        ]
    )
    return left, right


def focused_pair_text(candidate: dict, job: dict) -> list[tuple[str, str]]:
    """Build compact semantic views that remain learnable with 100 samples."""
    candidate_skills = " ".join(
        candidate.get("skills_normalized") or candidate.get("skills") or []
    )
    job_skills = " ".join(job.get("required_skills") or job.get("skills") or [])
    return [
        pair_text(candidate, job),
        (
            str(candidate.get("target_job_family") or ""),
            " ".join(
                [str(job.get("title") or ""), str(job.get("job_family") or "")]
            ),
        ),
        (candidate_skills, job_skills),
        (
            str(candidate.get("summary") or ""),
            str(job.get("description") or ""),
        ),
    ]


def static_features(candidate: dict, job: dict) -> list[float]:
    family = str(candidate.get("target_job_family") or "")
    title = str(job.get("title") or "")
    job_family = str(job.get("job_family") or "")
    candidate_skills = {str(x).casefold() for x in candidate.get("skills") or []}
    job_skills = {str(x).casefold() for x in job.get("required_skills") or job.get("skills") or []}
    overlap = candidate_skills & job_skills
    return [
        SequenceMatcher(None, family, title).ratio(),
        SequenceMatcher(None, family, job_family).ratio(),
        len(overlap) / len(job_skills) if job_skills else 0.0,
        len(overlap) / len(candidate_skills) if candidate_skills else 0.0,
        float(bool(family) and family in title),
        float(bool(family) and family == job_family),
        float(candidate.get("years_experience") or 0) / 10,
        role_affinity(family, title, job_family),
    ]


def main() -> None:
    args = parse_args()
    jobs = {row["job_id"]: row for row in load_jsonl(args.dataset_dir / "jobs.jsonl")}
    candidates = {
        row["candidate_id"]: row for row in load_jsonl(args.dataset_dir / "candidate_profiles.jsonl")
    }
    gold_path = args.gold_dir / "matching_annotation_adjudicated.csv"
    with gold_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    approval_path = args.gold_dir / "human_review_approval_manifest.json"
    approval = (
        json.loads(approval_path.read_text(encoding="utf-8"))
        if approval_path.exists()
        else None
    )
    is_human_approved = bool(
        approval and approval.get("status") == "human_review_approved"
    )
    pairs = [
        focused_pair_text(candidates[row["candidate_id"]], jobs[row["job_id"]])
        for row in rows
    ]
    model = SentenceTransformer(args.model)
    semantic_features = []
    for view_index in range(len(pairs[0])):
        left = np.asarray(
            model.encode(
                [pair[view_index][0] for pair in pairs], normalize_embeddings=True
            )
        )
        right = np.asarray(
            model.encode(
                [pair[view_index][1] for pair in pairs], normalize_embeddings=True
            )
        )
        semantic_features.append(np.sum(left * right, axis=1))
    static = np.asarray(
        [static_features(candidates[row["candidate_id"]], jobs[row["job_id"]]) for row in rows]
    )
    features = np.column_stack([*semantic_features, static])
    target = np.asarray([int(int(row["gold_grade_0_to_3"]) >= 2) for row in rows])
    splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=args.seed)
    predicted = np.zeros(len(rows), dtype=int)
    probabilities = np.zeros(len(rows), dtype=float)
    fold_ids = np.zeros(len(rows), dtype=int)
    for fold, (train_index, test_index) in enumerate(splitter.split(features, target), start=1):
        classifier = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=0.1,
                max_iter=3000,
                class_weight="balanced",
                random_state=args.seed,
            ),
        )
        classifier.fit(features[train_index], target[train_index])
        probabilities[test_index] = classifier.predict_proba(features[test_index])[:, 1]
        predicted[test_index] = (probabilities[test_index] >= 0.5).astype(int)
        fold_ids[test_index] = fold

    result = {
        "status": (
            "human_reviewed_five_fold_cross_validation"
            if is_human_approved
            else "provisional_five_fold_cross_validation"
        ),
        "formal_acceptance_eligible": is_human_approved,
        "label_source": (
            "team_human_review_approved"
            if is_human_approved
            else "provisional_not_human_gold"
        ),
        "model": args.model,
        "classifier": "BGE semantic + skill/experience + role-taxonomy gate + LogisticRegression",
        "feature_count": int(features.shape[1]),
        "samples": len(rows),
        "folds": 5,
        "accuracy": round(float(accuracy_score(target, predicted)), 6),
        "precision": round(float(precision_score(target, predicted, zero_division=0)), 6),
        "recall": round(float(recall_score(target, predicted, zero_division=0)), 6),
        "f1": round(float(f1_score(target, predicted, zero_division=0)), 6),
        "meets_taskbook_90_percent_accuracy": bool(
            accuracy_score(target, predicted) >= 0.9
        ),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "oof_predictions.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        fields = [
            "sample_id",
            "gold_positive",
            "predicted_positive",
            "predicted_grade_0_to_3",
            "probability",
            "fold",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, row in enumerate(rows):
            writer.writerow(
                {
                    "sample_id": row["sample_id"],
                    "gold_positive": int(target[index]),
                    "predicted_positive": int(predicted[index]),
                    "predicted_grade_0_to_3": 2 if predicted[index] else 1,
                    "probability": round(float(probabilities[index]), 6),
                    "fold": int(fold_ids[index]),
                }
            )
    (args.output_dir / "cv_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
