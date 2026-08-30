"""Generate deterministic rankings for every candidate represented in labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.nlp_service import NLPService
from scripts.generate_semantic_artifacts import (
    build_query_text,
    load_jsonl,
    rank_candidates_for_query,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rank every candidate represented in a label file")
    parser.add_argument(
        "--dataset-dir", type=Path, default=REPO_ROOT / "artifacts" / "dataset_iteration_05"
    )
    parser.add_argument(
        "--semantic-dir", type=Path, default=REPO_ROOT / "artifacts" / "semantic_index"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "artifacts" / "taskbook_acceptance_20260830" / "semantic_gold30",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profiles_path = args.dataset_dir / "candidate_profiles.jsonl"
    labels_path = args.dataset_dir / "label_pairs_gold.jsonl"
    embedding_path = args.semantic_dir / "jobs_embeddings.npy"
    embedding_ids_path = args.semantic_dir / "jobs_embedding_ids.json"
    metadata_path = args.semantic_dir / "model_metadata.json"

    profiles = {row["candidate_id"]: row for row in load_jsonl(profiles_path)}
    labels = load_jsonl(labels_path)
    query_ids = sorted({str(row["candidate_id"]) for row in labels})
    missing = [query_id for query_id in query_ids if query_id not in profiles]
    if missing:
        raise ValueError(f"{len(missing)} labeled candidates are missing from profiles: {missing[:5]}")

    job_ids = json.loads(embedding_ids_path.read_text(encoding="utf-8"))
    job_embeddings = np.load(embedding_path, mmap_mode="r")
    if len(job_ids) != len(job_embeddings):
        raise ValueError("embedding row count does not match jobs_embedding_ids.json")

    source_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    service = NLPService(sentence_transformer_model=source_metadata.get("model_name"))
    if source_metadata.get("model_name") == "char-ngram-hashing-768":
        service.sentence_transformer = None
    if service.active_embedding_model_name != source_metadata.get("model_name"):
        raise RuntimeError(
            "active query encoder does not match the stored job embedding model: "
            f"{service.active_embedding_model_name} != {source_metadata.get('model_name')}"
        )

    results = []
    for query_id in query_ids:
        candidates = rank_candidates_for_query(
            build_query_text(profiles[query_id]),
            job_ids,
            job_embeddings,
            job_ids,
            service,
        )
        results.append({"query_id": query_id, "candidates": candidates})

    output_path = args.output_dir / "semantic_rerank_output.jsonl"
    write_jsonl(output_path, results)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "command": "py backend-src/scripts/generate_gold_query_rankings.py",
        "model_name": service.active_embedding_model_name,
        "query_count": len(query_ids),
        "candidate_job_count": len(job_ids),
        "query_ids": query_ids,
        "inputs": {
            "profiles": {"path": str(profiles_path), "sha256": sha256(profiles_path)},
            "labels": {"path": str(labels_path), "sha256": sha256(labels_path)},
            "embeddings": {"path": str(embedding_path), "sha256": sha256(embedding_path)},
            "embedding_ids": {"path": str(embedding_ids_path), "sha256": sha256(embedding_ids_path)},
            "model_metadata": {"path": str(metadata_path), "sha256": sha256(metadata_path)},
        },
        "output": {"path": str(output_path), "sha256": sha256(output_path)},
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Generated {len(results)} complete rankings at {output_path}")


if __name__ == "__main__":
    main()
