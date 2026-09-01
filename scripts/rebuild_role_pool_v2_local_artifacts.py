"""Build local, dependency-free artifacts for a canonical role-pool release.

This utility does not change the production BM25/semantic/Fusion/KG code. It
creates import-ready data and local offline equivalents when Elasticsearch,
Neo4j or sentence-transformers are unavailable. Outputs carry their exact
algorithm/provenance so they cannot be mistaken for service-produced artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import CountVectorizer, HashingVectorizer


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JOBS = ROOT / "artifacts" / "canonical_role_pool_v2" / "canonical_jobs.jsonl"
DEFAULT_PROFILES = ROOT / "artifacts" / "dataset_iteration_05" / "candidate_profiles.jsonl"
DEFAULT_CASES = ROOT / "artifacts" / "canonical_matching_eval_v1_400" / "case_metrics.csv"
DEFAULT_OUTPUT = ROOT / "artifacts" / "role_pool_runtime" / "v2" / "local_rebuild"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fields_to_text(row: dict[str, Any]) -> str:
    skills = row.get("required_skills") or row.get("skills") or []
    if not isinstance(skills, list):
        skills = [skills]
    values = [
        row.get("title"), row.get("standard_job"), row.get("job_family"),
        " ".join(str(value) for value in skills), row.get("description"),
        row.get("responsibilities"), row.get("requirements"),
    ]
    return " ".join(str(value or "") for value in values).strip()


def profile_text(row: dict[str, Any]) -> str:
    profile = row.get("profile") if isinstance(row.get("profile"), dict) else {}
    skills = row.get("skills_normalized") or row.get("skills") or []
    if not isinstance(skills, list):
        skills = [skills]
    experience = row.get("experience") or []
    experience_text = " ".join(
        str(item.get("description") or "") for item in experience if isinstance(item, dict)
    )
    return " ".join(
        str(value or "") for value in [
            row.get("target_job_family"), profile.get("title"), profile.get("summary"),
            row.get("profile_text"), " ".join(str(item) for item in skills), experience_text,
        ]
    ).strip()


def normalize_token(value: str) -> str:
    return value.casefold().strip()


def skill_set(row: dict[str, Any]) -> set[str]:
    values = row.get("skills_normalized") or row.get("required_skills") or row.get("skills") or []
    if not isinstance(values, list):
        values = [values]
    return {normalize_token(str(value)) for value in values if normalize_token(str(value))}


def build_bm25(job_texts: list[str]) -> tuple[CountVectorizer, sparse.csr_matrix, np.ndarray, float]:
    """Create a sparse standard-BM25 document matrix for local retrieval."""
    vectorizer = CountVectorizer(
        analyzer="char", ngram_range=(2, 4), min_df=2, max_features=200_000, dtype=np.float32
    )
    counts = vectorizer.fit_transform(job_texts).tocsr()
    doc_lengths = np.asarray(counts.sum(axis=1)).ravel().astype(np.float32)
    average_length = float(doc_lengths.mean()) if len(doc_lengths) else 1.0
    doc_frequency = np.asarray((counts > 0).sum(axis=0)).ravel().astype(np.float32)
    total = counts.shape[0]
    idf = np.log1p((total - doc_frequency + 0.5) / (doc_frequency + 0.5)).astype(np.float32)
    k1, b = 1.2, 0.75
    row_scale = k1 * (1 - b + b * doc_lengths / max(1.0, average_length))
    weighted = counts.copy().astype(np.float32)
    weighted.data = weighted.data * (k1 + 1) / (weighted.data + np.repeat(row_scale, np.diff(weighted.indptr)))
    weighted = weighted.multiply(idf).tocsr()
    return vectorizer, weighted, doc_lengths, average_length


def bm25_scores(query: str, vectorizer: CountVectorizer, weighted_documents: sparse.csr_matrix) -> np.ndarray:
    query_counts = vectorizer.transform([query]).T
    return (weighted_documents @ query_counts).toarray().ravel().astype(np.float32)


def minmax(values: np.ndarray) -> np.ndarray:
    if not len(values):
        return values
    low, high = float(values.min()), float(values.max())
    if high <= low:
        return np.ones_like(values, dtype=np.float32)
    return (values - low) / (high - low)


def select_profiles(profiles: list[dict[str, Any]], cases_path: Path | None) -> list[dict[str, Any]]:
    if cases_path is None or not cases_path.exists():
        return profiles
    import csv

    with cases_path.open("r", encoding="utf-8-sig", newline="") as handle:
        case_ids = {row["candidate_id"] for row in csv.DictReader(handle)}
    selected = [profile for profile in profiles if str(profile.get("candidate_id") or profile.get("resume_id") or "") in case_ids]
    if len(selected) != len(case_ids):
        missing = len(case_ids) - len(selected)
        raise ValueError(f"Could not resolve {missing} requested evaluation profiles")
    return selected


def build_graph_import(jobs: list[dict[str, Any]], output_dir: Path) -> dict[str, int]:
    roles: dict[str, dict[str, Any]] = {}
    skills: dict[str, dict[str, str]] = {}
    edges: list[dict[str, str]] = []
    job_rows: list[dict[str, Any]] = []
    for job in jobs:
        job_id = str(job.get("job_id") or job.get("id") or "")
        role_id = str(job.get("canonical_role_id") or "")
        if not job_id or not role_id:
            continue
        job_rows.append({
            "job_id": job_id, "title": str(job.get("title") or ""), "canonical_role_id": role_id,
            "canonical_role": str(job.get("canonical_role") or ""), "domain": str(job.get("canonical_domain") or ""),
            "direction": str(job.get("canonical_direction") or ""), "description": str(job.get("description") or ""),
            "source": str(job.get("source") or ""),
        })
        roles[role_id] = {"canonical_role_id": role_id, "role_name": str(job.get("canonical_role") or ""), "domain": str(job.get("canonical_domain") or ""), "direction": str(job.get("canonical_direction") or "")}
        edges.append({"from_type": "Job", "from_id": job_id, "relationship": "INSTANCE_OF", "to_type": "CanonicalRole", "to_id": role_id})
        for skill in sorted(skill_set(job)):
            skill_id = hashlib.sha1(skill.encode("utf-8")).hexdigest()[:16]
            skills[skill_id] = {"skill_id": skill_id, "skill_name": skill}
            edges.append({"from_type": "Job", "from_id": job_id, "relationship": "REQUIRES_SKILL", "to_type": "Skill", "to_id": skill_id})
    write_jsonl(output_dir / "kg_import" / "jobs.jsonl", job_rows)
    write_jsonl(output_dir / "kg_import" / "canonical_roles.jsonl", roles.values())
    write_jsonl(output_dir / "kg_import" / "skills.jsonl", skills.values())
    write_jsonl(output_dir / "kg_import" / "relationships.jsonl", edges)
    return {"jobs": len(job_rows), "roles": len(roles), "skills": len(skills), "relationships": len(edges)}


def build_artifacts(jobs_path: Path, profiles_path: Path, cases_path: Path | None, output_dir: Path, top_k: int) -> dict[str, Any]:
    jobs = [row for row in read_jsonl(jobs_path) if row.get("role_mapping_status") == "mapped"]
    profiles = select_profiles(read_jsonl(profiles_path), cases_path)
    if not jobs or not profiles:
        raise ValueError("Jobs and profiles must both be non-empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in ("local_bm25", "semantic", "kg_features"):
        (output_dir / name).mkdir(parents=True, exist_ok=True)
    graph_stats = build_graph_import(jobs, output_dir)

    job_ids = [str(job.get("job_id") or job.get("id") or "") for job in jobs]
    job_texts = [fields_to_text(job) for job in jobs]
    bm25_vectorizer, bm25_documents, document_lengths, average_length = build_bm25(job_texts)
    sparse.save_npz(output_dir / "local_bm25" / "weighted_documents.npz", bm25_documents)
    np.savez_compressed(output_dir / "local_bm25" / "index_metadata.npz", job_ids=np.asarray(job_ids), document_lengths=document_lengths, average_length=np.asarray([average_length]))
    (output_dir / "local_bm25" / "vocabulary.json").write_text(
        json.dumps({term: int(index) for term, index in bm25_vectorizer.vocabulary_.items()}, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    (output_dir / "local_bm25" / "metadata.json").parent.mkdir(parents=True, exist_ok=True)
    (output_dir / "local_bm25" / "metadata.json").write_text(json.dumps({"algorithm": "BM25", "k1": 1.2, "b": 0.75, "tokenizer": "CountVectorizer_char_2_to_4_grams_min_df_2", "vocabulary_size": len(bm25_vectorizer.vocabulary_), "jobs_input": str(jobs_path), "job_count": len(jobs), "purpose": "local_offline_equivalent_not_elasticsearch_index"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    vectorizer = HashingVectorizer(analyzer="char", ngram_range=(2, 4), n_features=768, alternate_sign=False, norm="l2", dtype=np.float32)
    job_vectors = vectorizer.transform(job_texts).astype(np.float32)
    np.save(output_dir / "semantic" / "job_vectors.npy", job_vectors.toarray())
    (output_dir / "semantic" / "job_ids.json").parent.mkdir(parents=True, exist_ok=True)
    (output_dir / "semantic" / "job_ids.json").write_text(json.dumps(job_ids, ensure_ascii=False) + "\n", encoding="utf-8")

    bm25_rows: list[dict[str, Any]] = []
    semantic_rows: list[dict[str, Any]] = []
    kg_rows: list[dict[str, Any]] = []
    query_vectors = vectorizer.transform([profile_text(profile) for profile in profiles]).astype(np.float32)
    for profile, query_vector in zip(profiles, query_vectors):
        query_id = str(profile.get("candidate_id") or profile.get("resume_id") or profile.get("id") or "")
        query = profile_text(profile)
        lexical = bm25_scores(query, bm25_vectorizer, bm25_documents)
        lexical_top = np.argsort(-lexical, kind="stable")[:top_k]
        bm25_rows.append({"query_id": query_id, "candidates": [{"job_id": job_ids[int(index)], "bm25_score": float(lexical[int(index)]), "bm25_rank": rank} for rank, index in enumerate(lexical_top, start=1)]})
        semantic = (job_vectors @ query_vector.T).toarray().ravel()
        semantic_top = np.argsort(-semantic, kind="stable")[:top_k]
        semantic_rows.append({"query_id": query_id, "candidates": [{"job_id": job_ids[int(index)], "semantic_score": float(max(0.0, semantic[int(index)])), "semantic_rank": rank} for rank, index in enumerate(semantic_top, start=1)]})
        candidate_skills = skill_set(profile)
        target_role = normalize_token(str(profile.get("target_job_family") or ""))
        union = list(dict.fromkeys([int(index) for index in lexical_top] + [int(index) for index in semantic_top]))
        for index in union:
            job = jobs[index]
            required = skill_set(job)
            matched = sorted(candidate_skills & required)
            missing = sorted(required - candidate_skills)
            combined = candidate_skills | required
            role_name = normalize_token(str(job.get("canonical_role") or job.get("standard_job") or ""))
            kg_rows.append({
                "query_id": query_id,
                "job_id": job_ids[index],
                "skill_coverage": round(len(matched) / len(required), 6) if required else 0.0,
                "job_family_match": 1.0 if target_role and target_role == role_name else 0.0,
                "graph_relatedness": round(len(matched) / len(combined), 6) if combined else 0.0,
                "matched_skills": matched[:20],
                "missing_skills": missing[:20],
                "evidence_paths": [f"Candidate -> HAS_SKILL -> {skill} <- REQUIRES_SKILL <- Job" for skill in matched[:5]],
            })
    write_jsonl(output_dir / "local_bm25" / "bm25_topk.jsonl", bm25_rows)
    write_jsonl(output_dir / "semantic" / "semantic_topk.jsonl", semantic_rows)
    write_jsonl(output_dir / "kg_features" / "kg_features.jsonl", kg_rows)
    report = {
        "role_pool_version": "v2",
        "status": "local_artifacts_completed_service_rebuild_pending",
        "inputs": {"jobs": str(jobs_path), "profiles": str(profiles_path), "cases": str(cases_path) if cases_path else None, "jobs_sha256": sha256(jobs_path), "profiles_sha256": sha256(profiles_path)},
        "counts": {"jobs": len(jobs), "profiles": len(profiles), "top_k": top_k, "bm25_queries": len(bm25_rows), "semantic_queries": len(semantic_rows), "kg_features": len(kg_rows), **{f"kg_{key}": value for key, value in graph_stats.items()}},
        "algorithms": {"bm25": "standard_BM25_k1_1.2_b_0.75_local_tokenizer", "semantic": "existing_NLPService_fallback_equivalent_char_ngram_hashing_768", "kg_features": "existing_skill_coverage_and_jaccard_formula", "fusion": "run separately with existing backend-src/scripts/run_fusion_pipeline.py", "role_aware": "run separately with existing role_aware_matching_service adapter"},
        "blocked_service_artifacts": ["Elasticsearch index canonical_jobs_v2", "Neo4j database import"],
    }
    (output_dir / "local_rebuild_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=Path, default=DEFAULT_JOBS)
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="CSV whose candidate_id column limits profiles; omit with empty path for all profiles")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top-k", type=int, default=200)
    args = parser.parse_args()
    cases = args.cases if str(args.cases) else None
    print(json.dumps(build_artifacts(args.jobs, args.profiles, cases, args.output_dir, args.top_k), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
