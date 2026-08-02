import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

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
        script_path.parent.parent,
        BACKEND_ROOT.parent,
        BACKEND_ROOT,
    ]

    for candidate in candidates:
        if (candidate / "backend-src").exists() and (candidate / "artifacts").exists():
            return candidate.resolve()

    return BACKEND_ROOT


REPO_ROOT = resolve_repo_root()

from app.services.nlp_service import NLPService


def find_latest_dataset_iteration_dir(base_dir: Path) -> Optional[Path]:
    artifacts_dir = base_dir / "artifacts"
    if not artifacts_dir.exists():
        return None

    preferred = artifacts_dir / "dataset_iteration_05"
    if preferred.exists() and preferred.is_dir():
        return preferred

    dataset_dirs = sorted(
        [p for p in artifacts_dir.iterdir() if p.is_dir() and p.name.startswith("dataset_iteration_")],
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
    return fallback_dir / "jobs.jsonl", fallback_dir / "candidate_profiles.jsonl", fallback_dir


def resolve_candidates_path(base_dir: Path, explicit_path: Optional[Path] = None) -> Optional[Path]:
    if explicit_path is not None:
        return explicit_path if explicit_path.exists() else None

    for candidate in [base_dir / "candidates_mock.json", BACKEND_ROOT / "candidates_mock.json"]:
        if candidate.exists():
            return candidate
    return None


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    objects: List[Dict[str, Any]] = []
    index = 0
    length = len(text)

    while True:
        while index < length and text[index].isspace():
            index += 1
        if index >= length:
            break
        obj, end = decoder.raw_decode(text, index)
        if isinstance(obj, dict):
            objects.append(obj)
        index = end

    return objects


def load_json_payload(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_strings(values: Iterable[Any]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for value in values:
        item = str(value).strip()
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered


def load_candidate_job_ids(path: Optional[Path], jobs: List[Dict[str, Any]]) -> List[str]:
    if path is not None and path.exists():
        if path.suffix.lower() == ".jsonl":
            records = load_jsonl(path)
            return normalize_strings(record.get("job_id", "") for record in records)

        payload = load_json_payload(path)
        if isinstance(payload, dict):
            for key in ("job_ids", "candidate_job_ids", "candidates"):
                values = payload.get(key)
                if isinstance(values, list):
                    if values and isinstance(values[0], dict):
                        return normalize_strings(item.get("job_id", "") for item in values)
                    return normalize_strings(values)
        elif isinstance(payload, list):
            if payload and isinstance(payload[0], dict):
                return normalize_strings(item.get("job_id", "") for item in payload)
            return normalize_strings(payload)

    return normalize_strings(job.get("id", "") for job in jobs)


def build_job_text(job: Dict[str, Any]) -> str:
    title = job.get("title") or ""
    description = job.get("description") or job.get("job_description") or ""
    skills = " ".join(job.get("required_skills") or job.get("skills") or [])
    responsibilities = job.get("responsibilities") or ""
    requirements = job.get("requirements") or ""
    return " ".join([title, description, responsibilities, requirements, skills]).strip()


def build_query_text(profile: Dict[str, Any]) -> str:
    title = profile.get("profile", {}).get("title") or profile.get("title") or ""
    summary = profile.get("profile", {}).get("summary") or profile.get("summary") or profile.get("profile_text") or ""
    skills = " ".join(profile.get("skills") or profile.get("skills_normalized") or [])
    experience = " ".join(
        item.get("description", "") for item in profile.get("experience", []) if isinstance(item, dict)
    )
    return " ".join([title, summary, skills, experience]).strip()


def cosine_similarity_matrix(query_embedding: np.ndarray, candidate_embeddings: np.ndarray) -> np.ndarray:
    query_norm = np.linalg.norm(query_embedding)
    if query_norm == 0:
        return np.zeros(candidate_embeddings.shape[0], dtype=np.float32)

    candidate_norms = np.linalg.norm(candidate_embeddings, axis=1, keepdims=True)
    candidate_norms[candidate_norms == 0] = 1.0
    normalized_query = query_embedding / query_norm
    normalized_candidates = candidate_embeddings / candidate_norms
    return normalized_candidates @ normalized_query


def rank_candidates_for_query(
    query_text: str,
    candidate_job_ids: List[str],
    job_embeddings: np.ndarray,
    job_ids: List[str],
    service: NLPService,
) -> List[Dict[str, Any]]:
    query_embedding_list = service.get_sentence_embeddings([query_text])
    if not query_embedding_list:
        return []

    query_embedding = np.asarray(query_embedding_list[0], dtype=np.float32)
    id_to_index = {job_id: index for index, job_id in enumerate(job_ids)}
    selected_ids = [job_id for job_id in candidate_job_ids if job_id in id_to_index]
    if not selected_ids:
        selected_ids = job_ids

    selected_indices = [id_to_index[job_id] for job_id in selected_ids]
    selected_embeddings = np.asarray(job_embeddings[selected_indices], dtype=np.float32)
    scores = cosine_similarity_matrix(query_embedding, selected_embeddings)
    order = np.argsort(-scores)

    ranked: List[Dict[str, Any]] = []
    for rank, position in enumerate(order, start=1):
        ranked.append(
            {
                "job_id": selected_ids[int(position)],
                "semantic_score": float(scores[int(position)]),
                "semantic_rank": rank,
            }
        )
    return ranked


def build_comparison_pairs(jobs: List[Dict[str, Any]], profiles: List[Dict[str, Any]], max_pairs: int = 5) -> List[Tuple[str, str]]:
    if not jobs or not profiles:
        return [("Python 后端工程师", "Python 后端开发工程师")]

    pairs: List[Tuple[str, str]] = []
    pair_count = min(max_pairs, max(len(jobs), len(profiles)))
    for index in range(pair_count):
        job_text = build_job_text(jobs[index % len(jobs)])
        profile_text = build_query_text(profiles[index % len(profiles)])
        if job_text or profile_text:
            pairs.append((job_text, profile_text))

    return pairs or [("Python 后端工程师", "Python 后端开发工程师")]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, records: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")


def main(
    sample_limit: int | None = None,
    use_fallback: bool = False,
    sample_jobs: int | None = None,
    sample_profiles: int | None = None,
    candidates_file: Optional[str] = None,
    comparison_model: str = "all-MiniLM-L6-v2",
) -> None:
    jobs_path, profiles_path, _ = resolve_input_paths(REPO_ROOT)
    artifact_dir = REPO_ROOT / "artifacts" / "semantic_index"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    if not jobs_path.exists():
        raise FileNotFoundError(f"jobs.jsonl not found: {jobs_path}")
    if not profiles_path.exists():
        raise FileNotFoundError(f"candidate_profiles.jsonl not found: {profiles_path}")

    candidates_path = resolve_candidates_path(
        REPO_ROOT,
        Path(candidates_file).expanduser().resolve() if candidates_file else None,
    )

    jobs = load_jsonl(jobs_path)
    profiles = load_jsonl(profiles_path)

    jobs_sample_n = sample_jobs if sample_jobs is not None else (sample_limit if sample_limit and sample_limit > 0 else None)
    profiles_sample_n = sample_profiles if sample_profiles is not None else (sample_limit if sample_limit and sample_limit > 0 else None)

    if jobs_sample_n and jobs_sample_n > 0:
        jobs = jobs[:jobs_sample_n]
    if profiles_sample_n and profiles_sample_n > 0:
        profiles = profiles[:profiles_sample_n]

    model_name = os.getenv("SENTENCE_TRANSFORMER_MODEL", "BAAI/bge-m3")
    service = NLPService(sentence_transformer_model=model_name)
    if use_fallback:
        service.sentence_transformer = None

    job_texts = [build_job_text(job) for job in jobs]
    job_ids = normalize_strings(job.get("id", "") for job in jobs)
    if not job_ids:
        raise RuntimeError("No job ids found in the provided jobs.jsonl input.")

    job_embeddings_list = service.get_sentence_embeddings(job_texts)
    if not job_embeddings_list:
        raise RuntimeError(
            "Could not build embeddings. Install torch/sentence-transformers or rely on the built-in fallback vectorizer."
        )

    job_embeddings = np.asarray(job_embeddings_list, dtype=np.float32)
    np.save(artifact_dir / "jobs_embeddings.npy", job_embeddings)
    write_json(artifact_dir / "jobs_embedding_ids.json", job_ids)

    candidate_job_ids = load_candidate_job_ids(candidates_path, jobs)
    if not candidate_job_ids:
        candidate_job_ids = job_ids
    if jobs_sample_n and jobs_sample_n > 0:
        candidate_job_ids = job_ids

    rerank_results: List[Dict[str, Any]] = []
    for index, profile in enumerate(profiles):
        query_id = (
            profile.get("resume_id")
            or profile.get("candidate_id")
            or profile.get("query_id")
            or profile.get("id")
            or f"query_{index + 1}"
        )
        query_text = build_query_text(profile)
        ranked_candidates = rank_candidates_for_query(query_text, candidate_job_ids, job_embeddings, job_ids, service)
        rerank_results.append(
            {
                "query_id": query_id,
                "candidates": ranked_candidates,
            }
        )

    write_json(artifact_dir / "semantic_rerank_output.json", rerank_results)
    write_jsonl(artifact_dir / "semantic_rerank_output.jsonl", rerank_results)
    sample_n = profiles_sample_n if (profiles_sample_n and profiles_sample_n > 0) else min(3, len(rerank_results))
    write_json(artifact_dir / "semantic_rerank_output.sample.json", rerank_results[:sample_n])
    write_jsonl(artifact_dir / "semantic_rerank_output.sample.jsonl", rerank_results[:sample_n])

    comparison_pairs = build_comparison_pairs(jobs, profiles)
    comparison_service = NLPService(sentence_transformer_model=comparison_model)
    comparison = service.compare_models(comparison_pairs, baseline_model_name=comparison_model)
    comparison["comparison_model"] = comparison_model
    comparison["comparison_model_loaded"] = comparison_service.sentence_transformer is not None
    comparison["model_family"] = "bge-m3"
    write_json(artifact_dir / "embedding_model_comparison.json", comparison)

    metadata_path = artifact_dir / "model_metadata.json"
    write_json(
        metadata_path,
        {
            "model_name": model_name,
            "model_family": "bge-m3",
            "pipeline": "offline_job_embedding_and_rerank",
            "candidate_source": str(candidates_path) if candidates_path else "all_jobs_fallback",
            "jobs_input": str(jobs_path),
            "profiles_input": str(profiles_path),
        },
    )

    print(f"Wrote embeddings to {artifact_dir / 'jobs_embeddings.npy'}")
    print(f"Wrote ids to {artifact_dir / 'jobs_embedding_ids.json'}")
    print(f"Wrote rerank output to {artifact_dir / 'semantic_rerank_output.json'}")
    print(f"Wrote rerank JSONL to {artifact_dir / 'semantic_rerank_output.jsonl'}")
    print(f"Wrote model comparison to {artifact_dir / 'embedding_model_comparison.json'}")
    print(f"Wrote model metadata to {metadata_path}")

    try:
        print("\nFirst 3 rerank entries (sample):")
        print(json.dumps(rerank_results[:3], ensure_ascii=False, indent=2))
    except Exception:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate semantic artifacts for workflow 2")
    parser.add_argument("--sample", type=int, default=0, help="Limit number of jobs/profiles to process (0 = all)")
    parser.add_argument("--sample-jobs", type=int, default=0, help="Limit number of jobs to process (overrides --sample for jobs)")
    parser.add_argument("--sample-profiles", type=int, default=0, help="Limit number of profiles to process (overrides --sample for profiles)")
    parser.add_argument("--use-fallback", action="store_true", help="Force using the fallback embedding path even when a transformer is available")
    parser.add_argument("--candidates-file", type=str, default=None, help="Optional candidate set file with job_ids list")
    parser.add_argument("--comparison-model", type=str, default="all-MiniLM-L6-v2", help="Optional comparison embedding model")
    args = parser.parse_args()

    sample_limit = args.sample if args.sample and args.sample > 0 else None
    sample_jobs = args.sample_jobs if args.sample_jobs and args.sample_jobs > 0 else None
    sample_profiles = args.sample_profiles if args.sample_profiles and args.sample_profiles > 0 else None

    main(
        sample_limit=sample_limit,
        use_fallback=args.use_fallback,
        sample_jobs=sample_jobs,
        sample_profiles=sample_profiles,
        candidates_file=args.candidates_file,
        comparison_model=args.comparison_model,
    )
