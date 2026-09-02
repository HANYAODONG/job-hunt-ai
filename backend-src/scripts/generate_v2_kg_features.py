"""Generate existing KG feature fields for a frozen v2 candidate set."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def normalize(value: Any) -> str:
    return str(value or "").casefold().strip()


def skill_set(row: dict[str, Any]) -> set[str]:
    values = row.get("skills_normalized") or row.get("required_skills") or row.get("skills") or []
    if not isinstance(values, list):
        values = [values]
    return {normalize(value) for value in values if normalize(value)}


def sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate v2 KG features for BM25/semantic candidates")
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    candidate_rows = list(read_jsonl(args.candidates))
    query_ids = {str(row.get("query_id") or "") for row in candidate_rows}
    query_ids.discard("")

    jobs = {
        str(row.get("job_id") or row.get("id") or ""): row
        for row in read_jsonl(args.jobs)
    }
    profiles: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(args.profiles):
        query_id = str(row.get("candidate_id") or row.get("query_id") or row.get("resume_id") or "")
        if query_id in query_ids:
            profiles[query_id] = row
            if len(profiles) == len(query_ids):
                break

    missing_profiles = sorted(query_ids - set(profiles))
    if missing_profiles:
        raise ValueError(f"Candidate profiles not found for {len(missing_profiles)} query IDs")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    feature_count = 0
    missing_jobs: set[str] = set()
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for candidate_row in candidate_rows:
            query_id = str(candidate_row["query_id"])
            profile = profiles[query_id]
            candidate_skills = skill_set(profile)
            target_role = normalize(profile.get("target_job_family"))
            for candidate in candidate_row.get("candidates", []):
                job_id = str(candidate.get("job_id") or "")
                job = jobs.get(job_id)
                if job is None:
                    missing_jobs.add(job_id)
                    continue
                required = skill_set(job)
                matched = sorted(candidate_skills & required)
                missing = sorted(required - candidate_skills)
                combined = candidate_skills | required
                role_name = normalize(job.get("canonical_role") or job.get("standard_job"))
                output = {
                    "query_id": query_id,
                    "job_id": job_id,
                    "skill_coverage": round(len(matched) / len(required), 6) if required else 0.0,
                    "job_family_match": 1.0 if target_role and target_role == role_name else 0.0,
                    "graph_relatedness": round(len(matched) / len(combined), 6) if combined else 0.0,
                    "matched_skills": matched[:20],
                    "missing_skills": missing[:20],
                    "evidence_paths": [
                        f"Candidate -> HAS_SKILL -> {skill} <- REQUIRES_SKILL <- Job"
                        for skill in matched[:5]
                    ],
                }
                handle.write(json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n")
                feature_count += 1

    if missing_jobs:
        raise ValueError(f"Candidate set references {len(missing_jobs)} jobs outside the v2 pool")

    metadata = {
        "role_pool_version": "v2",
        "algorithm": "existing_skill_coverage_and_jaccard_formula",
        "queries": len(candidate_rows),
        "features": feature_count,
        "jobs_sha256_lf_normalized": sha256_lf(args.jobs),
        "candidates_sha256_lf_normalized": sha256_lf(args.candidates),
        "output": str(args.output),
    }
    metadata_path = args.metadata or args.output.with_name("run_metadata.json")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
