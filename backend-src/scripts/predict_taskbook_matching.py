"""Predict the frozen matching holdout with a lightweight BGE classifier."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.ensemble import HistGradientBoostingClassifier

from generate_semantic_artifacts import load_jsonl


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT if (BACKEND_ROOT / "artifacts").exists() else BACKEND_ROOT.parent


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pair_texts(candidate: dict[str, Any], job: dict[str, Any]) -> tuple[str, str]:
    candidate_text = " ".join(
        [
            str(candidate.get("target_job_family") or ""),
            str(candidate.get("summary") or candidate.get("profile_text") or ""),
            " ".join(candidate.get("skills_normalized") or candidate.get("skills") or []),
        ]
    )
    job_text = " ".join(
        [
            str(job.get("title") or ""),
            str(job.get("job_family") or ""),
            str(job.get("description") or ""),
            " ".join(job.get("required_skills") or job.get("skills") or []),
        ]
    )
    return candidate_text, job_text


def static_features(candidate: dict[str, Any], job: dict[str, Any]) -> list[float]:
    family = str(candidate.get("target_job_family") or "")
    title = str(job.get("title") or "")
    job_family = str(job.get("job_family") or "")
    candidate_skills = {
        str(item).strip().casefold()
        for item in candidate.get("skills_normalized") or candidate.get("skills") or []
        if str(item).strip()
    }
    job_skills = {
        str(item).strip().casefold()
        for item in job.get("required_skills") or job.get("skills") or []
        if str(item).strip()
    }
    intersection = candidate_skills & job_skills
    return [
        SequenceMatcher(None, family, title).ratio(),
        SequenceMatcher(None, family, job_family).ratio(),
        len(intersection) / len(job_skills) if job_skills else 0.0,
        len(intersection) / len(candidate_skills) if candidate_skills else 0.0,
        float(bool(family) and family in title),
        float(bool(family) and family == job_family),
        min(len(job_skills), 30) / 30,
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Predict task-book matching holdout")
    parser.add_argument("--dataset-dir", type=Path, default=REPO_ROOT / "artifacts" / "dataset_iteration_05")
    parser.add_argument("--gold-dir", type=Path, default=REPO_ROOT / "artifacts" / "taskbook_gold_v1")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "artifacts" / "taskbook_acceptance_20260830" / "matching_bge_small")
    parser.add_argument("--model", default="BAAI/bge-small-zh-v1.5")
    parser.add_argument("--seed", type=int, default=20260830)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    jobs_path = args.dataset_dir / "jobs.jsonl"
    candidates_path = args.dataset_dir / "candidate_profiles.jsonl"
    labels_path = args.dataset_dir / "label_pairs_gold.jsonl"
    holdout_path = args.gold_dir / "matching_annotation_adjudicated.csv"
    jobs = {row["job_id"]: row for row in load_jsonl(jobs_path)}
    candidates = {row["candidate_id"]: row for row in load_jsonl(candidates_path)}
    labels = load_jsonl(labels_path)
    with holdout_path.open("r", encoding="utf-8-sig", newline="") as handle:
        holdout_rows = list(csv.DictReader(handle))
    holdout_by_pair = {row["pair_id"]: row for row in holdout_rows}
    holdout_ids = set(holdout_by_pair)
    train_labels = [row for row in labels if row["pair_id"] not in holdout_ids]
    test_labels = [row for row in labels if row["pair_id"] in holdout_ids]
    if len(test_labels) != len(holdout_rows):
        raise ValueError("holdout pair IDs do not map one-to-one to historical labels")

    ordered_labels = train_labels + test_labels
    text_pairs = [pair_texts(candidates[row["candidate_id"]], jobs[row["job_id"]]) for row in ordered_labels]
    model = SentenceTransformer(args.model)
    left = model.encode([pair[0] for pair in text_pairs], normalize_embeddings=True, show_progress_bar=True)
    right = model.encode([pair[1] for pair in text_pairs], normalize_embeddings=True, show_progress_bar=True)
    semantic = np.sum(np.asarray(left) * np.asarray(right), axis=1)
    features = np.asarray(
        [
            [float(semantic[index]), *static_features(candidates[row["candidate_id"]], jobs[row["job_id"]])]
            for index, row in enumerate(ordered_labels)
        ],
        dtype=np.float32,
    )
    target = np.asarray([int(int(row.get("grade", 0)) >= 2) for row in ordered_labels])
    train_count = len(train_labels)
    classifier = HistGradientBoostingClassifier(
        max_iter=300,
        learning_rate=0.05,
        max_leaf_nodes=15,
        l2_regularization=1.0,
        class_weight="balanced",
        random_state=args.seed,
    )
    classifier.fit(features[:train_count], target[:train_count])
    probabilities = classifier.predict_proba(features[train_count:])[:, 1]

    predictions = []
    for label, probability in zip(test_labels, probabilities):
        sample_id = holdout_by_pair[label["pair_id"]]["sample_id"]
        if probability >= 0.75:
            grade = 3
        elif probability >= 0.5:
            grade = 2
        elif probability >= 0.25:
            grade = 1
        else:
            grade = 0
        predictions.append(
            {
                "sample_id": sample_id,
                "pair_id": label["pair_id"],
                "predicted_grade_0_to_3": grade,
                "positive_probability": round(float(probability), 6),
            }
        )
    predictions.sort(key=lambda row: row["sample_id"])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / "matching_predictions.csv"
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(predictions[0]))
        writer.writeheader()
        writer.writerows(predictions)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "classifier": "HistGradientBoostingClassifier",
        "seed": args.seed,
        "train_pairs": train_count,
        "holdout_pairs": len(test_labels),
        "holdout_policy": "all taskbook pair_ids excluded from classifier training",
        "inputs": {
            "jobs_sha256": sha256(jobs_path),
            "candidates_sha256": sha256(candidates_path),
            "labels_sha256": sha256(labels_path),
            "holdout_sha256": sha256(holdout_path),
        },
        "output_sha256": sha256(output_path),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
