"""Validate that all canonical role-pool v2 ranking stages use one frozen candidate set."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc


def sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_job_ids(path: Path) -> set[str]:
    job_ids = {
        str(row.get("job_id") or row.get("id") or "").strip()
        for row in read_jsonl(path)
    }
    job_ids.discard("")
    return job_ids


def load_nested_pairs(path: Path, field: str) -> tuple[set[str], set[tuple[str, str]]]:
    queries: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    for row in read_jsonl(path):
        query_id = str(row.get("query_id") or "").strip()
        if not query_id:
            raise ValueError(f"Missing query_id in {path}")
        queries.add(query_id)
        for item in row.get(field, []):
            job_id = str(item.get("job_id") or "").strip()
            if job_id:
                pairs.add((query_id, job_id))
    return queries, pairs


def load_flat_pairs(path: Path) -> tuple[set[str], set[tuple[str, str]]]:
    queries: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    for row in read_jsonl(path):
        query_id = str(row.get("query_id") or "").strip()
        job_id = str(row.get("job_id") or "").strip()
        if not query_id or not job_id:
            raise ValueError(f"Missing query_id/job_id in {path}")
        queries.add(query_id)
        pairs.add((query_id, job_id))
    return queries, pairs


def validate(
    jobs_path: Path,
    bm25_path: Path,
    semantic_path: Path,
    kg_path: Path,
    fusion_path: Path,
) -> dict[str, Any]:
    job_ids = load_job_ids(jobs_path)
    bm25_queries, bm25_pairs = load_nested_pairs(bm25_path, "candidates")
    semantic_queries, semantic_pairs = load_nested_pairs(semantic_path, "candidates")
    kg_queries, kg_pairs = load_flat_pairs(kg_path)
    fusion_queries, fusion_pairs = load_nested_pairs(fusion_path, "results")

    query_sets = {
        "bm25": bm25_queries,
        "semantic": semantic_queries,
        "kg": kg_queries,
        "fusion": fusion_queries,
    }
    pair_sets = {
        "bm25": bm25_pairs,
        "semantic": semantic_pairs,
        "kg": kg_pairs,
        "fusion": fusion_pairs,
    }
    if any(values != bm25_queries for values in query_sets.values()):
        raise ValueError("Query IDs differ across BM25, semantic, KG, and Fusion outputs")
    if any(values != bm25_pairs for values in pair_sets.values()):
        raise ValueError("Candidate pairs differ across BM25, semantic, KG, and Fusion outputs")

    unknown_job_ids = {job_id for _, job_id in bm25_pairs} - job_ids
    if unknown_job_ids:
        raise ValueError(f"Found {len(unknown_job_ids)} job IDs outside the v2 pool")

    return {
        "status": "passed",
        "role_pool_version": "v2",
        "jobs": len(job_ids),
        "queries": len(bm25_queries),
        "candidate_pairs": len(bm25_pairs),
        "jobs_sha256_lf_normalized": sha256_lf(jobs_path),
        "stages": list(query_sets),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--bm25", type=Path, required=True)
    parser.add_argument("--semantic", type=Path, required=True)
    parser.add_argument("--kg", type=Path, required=True)
    parser.add_argument("--fusion", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = validate(args.jobs, args.bm25, args.semantic, args.kg, args.fusion)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
