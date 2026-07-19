import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import argparse

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def resolve_repo_root() -> Path:
    env_root = os.getenv("JOBHUNT_REPO_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    script_path = Path(__file__).resolve()
    candidates = [
        Path.cwd().resolve(),
        script_path.parent.parent,  # repo root from .../backend-src/scripts
        BACKEND_ROOT.parent,
        BACKEND_ROOT,
    ]

    for candidate in candidates:
        if (candidate / "backend-src").exists() and (candidate / "artifacts").exists():
            return candidate.resolve()

    return BACKEND_ROOT


REPO_ROOT = resolve_repo_root()

from app.services.semantic_embedding_service import SemanticEmbeddingService


def find_latest_dataset_iteration_dir(base_dir: Path) -> Optional[Path]:
    artifacts_dir = base_dir / "artifacts"
    if not artifacts_dir.exists():
        return None

    preferred = artifacts_dir / "dataset_iteration_04"
    if preferred.exists() and preferred.is_dir():
        return preferred

    dataset_dirs = sorted(
        [p for p in artifacts_dir.iterdir() if p.is_dir() and re.match(r"dataset_iteration_\d+", p.name)],
        key=lambda p: p.name,
    )
    return dataset_dirs[-1] if dataset_dirs else None


def resolve_input_paths(base_dir: Path) -> Tuple[Path, Path, Path]:
    dataset_dir = find_latest_dataset_iteration_dir(base_dir)
    if dataset_dir is not None:
        jobs_path = dataset_dir / "jobs.jsonl"
        profiles_path = dataset_dir / "candidate_profiles.jsonl"
        if jobs_path.exists() and profiles_path.exists():
            return jobs_path, profiles_path, dataset_dir

    fallback_dir = base_dir
    jobs_path = fallback_dir / "jobs.jsonl"
    profiles_path = fallback_dir / "candidate_profiles.jsonl"
    return jobs_path, profiles_path, fallback_dir


def build_job_text(job: Dict[str, Any]) -> str:
    title = job.get("title") or ""
    description = job.get("description") or ""
    skills = " ".join(job.get("required_skills") or [])
    return " ".join([title, description, skills]).strip()


def build_query_text(profile: Dict[str, Any]) -> str:
    title = profile.get("profile", {}).get("title") or ""
    summary = profile.get("profile", {}).get("summary") or ""
    skills = " ".join(profile.get("skills") or [])
    return " ".join([title, summary, skills]).strip()


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    objs: List[Dict[str, Any]] = []
    idx = 0
    n = len(text)
    while True:
        # skip whitespace/newlines
        while idx < n and text[idx].isspace():
            idx += 1
        if idx >= n:
            break
        try:
            obj, end = decoder.raw_decode(text, idx)
        except json.JSONDecodeError as e:
            snippet = text[idx: idx + 200].replace('\n', '\\n')
            raise json.JSONDecodeError(f"{e.msg} (near text snippet: {snippet})", e.doc, e.pos)
        objs.append(obj)
        idx = end
    return objs


def ensure_input_files(root: Path) -> Tuple[Path, Path, Path]:
    jobs_path, profiles_path, data_dir = resolve_input_paths(root)
    candidates_path = root / "candidates_mock.json"
    if not candidates_path.exists():
        candidates_path = BACKEND_ROOT / "candidates_mock.json"

    if not jobs_path.exists():
        jobs_path.parent.mkdir(parents=True, exist_ok=True)
        jobs_path.write_text(
            "\n".join([
                json.dumps(
                    {
                        "id": "job_001",
                        "title": "Python 后端工程师",
                        "description": "负责后端服务开发与接口设计",
                        "required_skills": ["Python", "FastAPI", "MySQL"],
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "id": "job_002",
                        "title": "Java 工程师",
                        "description": "负责企业级系统开发",
                        "required_skills": ["Java", "Spring", "微服务"],
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "id": "job_003",
                        "title": "数据分析师",
                        "description": "进行数据分析和机器学习建模",
                        "required_skills": ["Python", "机器学习", "SQL"],
                    },
                    ensure_ascii=False,
                ),
            ]) + "\n",
            encoding="utf-8",
        )

    if not profiles_path.exists():
        profiles_path.parent.mkdir(parents=True, exist_ok=True)
        profiles_path.write_text(
            json.dumps(
                {
                    "query_id": "resume_001",
                    "profile": {
                        "title": "后端开发工程师",
                        "summary": "熟悉 Python 和 FastAPI，擅长系统设计",
                    },
                    "skills": ["Python", "FastAPI", "MySQL"],
                },
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )

    if not candidates_path.exists():
        candidates_path.write_text(
            json.dumps(
                {
                    "job_ids": ["job_001", "job_002", "job_003"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    return jobs_path, profiles_path, data_dir


def main(sample_limit: int | None = None, use_fallback: bool = False, sample_jobs: int | None = None, sample_profiles: int | None = None) -> None:
    jobs_path, profiles_path, data_dir = ensure_input_files(REPO_ROOT)
    artifact_dir = REPO_ROOT / "artifacts" / "semantic_index"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    candidates_path = REPO_ROOT / "candidates_mock.json"
    if not candidates_path.exists():
        candidates_path = BACKEND_ROOT / "candidates_mock.json"

    jobs = load_jsonl(jobs_path)
    profiles = load_jsonl(profiles_path)

    # Determine sampling sizes: explicit args override unified sample_limit
    jobs_sample_n = sample_jobs if (sample_jobs is not None) else (sample_limit if sample_limit and sample_limit > 0 else None)
    profiles_sample_n = sample_profiles if (sample_profiles is not None) else (sample_limit if sample_limit and sample_limit > 0 else None)

    # Apply sample limits if requested (useful for quick validations)
    if jobs_sample_n and jobs_sample_n > 0:
        jobs = jobs[:jobs_sample_n]
    if profiles_sample_n and profiles_sample_n > 0:
        profiles = profiles[:profiles_sample_n]

    service = SemanticEmbeddingService(model_name="BAAI/bge-m3")

    # Optionally force the deterministic fallback to avoid heavy model inference
    if use_fallback:
        service.model = None
        service.model_loaded = False
        service.model_status = "fallback"

    job_texts = [build_job_text(job) for job in jobs]
    job_ids = [job["id"] for job in jobs]

    job_embeddings = np.asarray(service.encode_texts(job_texts), dtype="float32")
    service.save_embeddings(job_embeddings, artifact_dir / "jobs_embeddings.npy")
    service.save_embedding_ids(job_ids, artifact_dir / "jobs_embedding_ids.json")

    # Build rerank results for each profile. Ensure files are written even when model falls back.
    rerank_results = []
    # If sampling jobs, prefer the jobs we just saved as the candidate set to ensure consistency
    if jobs_sample_n and jobs_sample_n > 0:
        candidate_job_ids = job_ids
    else:
        candidates_data = json.loads(candidates_path.read_text(encoding="utf-8"))
        candidate_job_ids = candidates_data.get("job_ids", job_ids)
    job_text_by_id = {job["id"]: build_job_text(job) for job in jobs}

    for idx, profile in enumerate(profiles):
        query_id = (
            profile.get("resume_id")
            or profile.get("candidate_id")
            or profile.get("query_id")
            or profile.get("id")
            or f"query_{idx+1}"
        )
        query_text = build_query_text(profile)

        candidate_texts = [job_text_by_id[job_id] for job_id in candidate_job_ids if job_id in job_text_by_id]
        candidate_ids = [job_id for job_id in candidate_job_ids if job_id in job_text_by_id]

        # If no candidate_texts found (e.g., candidates file refers to ids not in jobs), fallback to all jobs
        if not candidate_texts:
            candidate_texts = [build_job_text(job) for job in jobs]
            candidate_ids = [job["id"] for job in jobs]

        reranked = service.rerank_candidates(query_text, candidate_texts, candidate_ids)
        rerank_results.append({
            "query_id": query_id,
            "candidates": reranked,
        })

    (artifact_dir / "semantic_rerank_output.json").write_text(
        json.dumps(rerank_results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # When sampling, also write a small sample file for quick inspection
    try:
        sample_path = artifact_dir / "semantic_rerank_output.sample.json"
        # Prefer the number of sampled profiles when available so the sample file
        # reflects the user's requested profile sample size; fallback to 3.
        sample_n = profiles_sample_n if (profiles_sample_n and profiles_sample_n > 0) else min(3, len(rerank_results))
        sample_n = min(sample_n, len(rerank_results))
        sample_data = rerank_results[:sample_n]
        sample_path.write_text(json.dumps(sample_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote sample rerank output to {sample_path}")
    except Exception:
        pass

    # Build model comparison pairs based on the selected data so results reflect sample/full run
    def safe_text_from_job(job: Dict[str, Any]) -> str:
        # Prefer title, then description, then built job text
        return (job.get("title") or job.get("description") or build_job_text(job) or "").strip()

    def safe_text_from_profile(profile: Dict[str, Any]) -> str:
        # Prefer profile title, then summary, then built query text
        return (profile.get("profile", {}).get("title") or profile.get("profile", {}).get("summary") or build_query_text(profile) or "").strip()

    comparison_pairs: List[Tuple[str, str]] = []
    # Generate up to 5 comparison pairs, cycling through available jobs/profiles
    max_pairs = 5
    n_available = max(len(jobs), len(profiles)) if (jobs or profiles) else 0
    n_pairs = max(1, min(max_pairs, n_available))
    if n_pairs > 0:
        for i in range(n_pairs):
            left = safe_text_from_job(jobs[i % len(jobs)]) if jobs else ""
            right = safe_text_from_profile(profiles[i % len(profiles)]) if profiles else ""
            comparison_pairs.append((left, right))

    # If all pairs are empty or insufficient, fallback to defaults
    if not any(l.strip() or r.strip() for l, r in comparison_pairs):
        comparison_pairs = [
            ("Python 后端工程师", "Python 后端开发工程师"),
            ("Java 微服务工程师", "Java 分布式系统开发"),
        ]

    comparison = service.compare_models(comparison_pairs)
    comparison["model_family"] = "bge-m3"
    (artifact_dir / "embedding_model_comparison.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    metadata_path = artifact_dir / "model_metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "model_name": "BAAI/bge-m3",
                "model_family": "bge-m3",
                "pipeline": "offline_job_embedding_and_rerank",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Verification: ensure the saved rerank output matches the sampled selection
    sr_path = artifact_dir / "semantic_rerank_output.json"
    try:
        written = json.loads(sr_path.read_text(encoding="utf-8"))
        needs_fix = False
        if len(written) != len(profiles):
            needs_fix = True
        else:
            for entry in written:
                if len(entry.get("candidates", [])) != len(candidate_job_ids):
                    needs_fix = True
                    break
        if needs_fix:
            sr_path.write_text(json.dumps(rerank_results, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Rewrote {sr_path} to match selected samples (profiles={len(profiles)}, candidates={len(candidate_job_ids)})")
        else:
            print(f"Verified {sr_path} matches selected samples (profiles={len(profiles)}, candidates={len(candidate_job_ids)})")
    except Exception:
        # If reading/parsing fails, overwrite with the in-memory correct results
        sr_path.write_text(json.dumps(rerank_results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote {sr_path} (verification fallback)")

    print(f"Wrote embeddings to {artifact_dir / 'jobs_embeddings.npy'}")
    print(f"Wrote ids to {artifact_dir / 'jobs_embedding_ids.json'}")
    print(f"Wrote rerank output to {artifact_dir / 'semantic_rerank_output.json'}")
    print(f"Wrote model comparison to {artifact_dir / 'embedding_model_comparison.json'}")
    print(f"Wrote model metadata to {metadata_path}")

    # Print first 3 rerank results for quick validation
    try:
        print("\nFirst 3 rerank entries (sample):")
        print(json.dumps(rerank_results[:3], ensure_ascii=False, indent=2))
    except Exception:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate semantic artifacts (with optional sampling)")
    parser.add_argument("--sample", type=int, default=0, help="Limit number of jobs/profiles to process (0 = all)")
    parser.add_argument("--sample-jobs", type=int, default=0, help="Limit number of jobs to process (overrides --sample for jobs)")
    parser.add_argument("--sample-profiles", type=int, default=0, help="Limit number of profiles to process (overrides --sample for profiles)")
    parser.add_argument("--use-fallback", action="store_true", help="Force using deterministic fallback embeddings (fast) instead of loading large model")
    args = parser.parse_args()
    sample_limit = args.sample if args.sample and args.sample > 0 else None
    sample_jobs = args.sample_jobs if args.sample_jobs and args.sample_jobs > 0 else None
    sample_profiles = args.sample_profiles if args.sample_profiles and args.sample_profiles > 0 else None
    main(sample_limit=sample_limit, use_fallback=args.use_fallback, sample_jobs=sample_jobs, sample_profiles=sample_profiles)