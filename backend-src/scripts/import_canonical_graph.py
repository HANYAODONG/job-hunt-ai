"""Import the canonical job dataset into Neo4j without rerunning skill extraction."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from neo4j import GraphDatabase


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JOBS = REPO_ROOT / "artifacts" / "dataset_iteration_05" / "jobs.jsonl"

UPSERT_JOBS = """
UNWIND $rows AS row
MERGE (job:Job {id: row.id})
SET job.title = row.title,
    job.description = row.description,
    job.job_family = row.job_family,
    job.standard_category = row.standard_category,
    job.standard_role = row.standard_role,
    job.required_skills = row.skills,
    job.source = row.source
WITH job, row
UNWIND row.skills AS skill_name
MERGE (skill:Skill {name: skill_name})
MERGE (job)-[:REQUIRES_SKILL {required: true}]->(skill)
"""


def batches(items: list[dict], size: int):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def load_jobs(path: Path) -> list[dict]:
    jobs = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            job_id = str(item.get("job_id") or item.get("id") or "").strip()
            skills = item.get("required_skills") or item.get("skills") or []
            skills = [str(skill).strip() for skill in skills if str(skill).strip()]
            if job_id and skills:
                jobs.append({
                    "id": job_id,
                    "title": str(item.get("title") or item.get("standard_job") or job_id),
                    "description": str(item.get("description") or ""),
                    "job_family": str(item.get("job_family") or item.get("standard_job") or "未分类"),
                    "standard_category": str(item.get("standard_category") or ""),
                    "standard_role": str(item.get("standard_job") or item.get("job_family") or ""),
                    "skills": skills,
                    "source": str(item.get("source") or "canonical_dataset"),
                })
    return jobs


def main() -> None:
    parser = argparse.ArgumentParser(description="Import canonical jobs and skills into Neo4j.")
    parser.add_argument("--jobs", type=Path, default=DEFAULT_JOBS)
    parser.add_argument("--uri", default=os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--user", default=os.getenv("NEO4J_USER", "neo4j"))
    parser.add_argument("--password", default=os.getenv("NEO4J_PASSWORD", "password"))
    parser.add_argument("--batch-size", type=int, default=300)
    args = parser.parse_args()

    jobs = load_jobs(args.jobs)
    if not jobs:
        raise SystemExit(f"No importable jobs found in {args.jobs}")

    with GraphDatabase.driver(args.uri, auth=(args.user, args.password)) as driver:
        driver.verify_connectivity()
        with driver.session() as session:
            for index, batch in enumerate(batches(jobs, args.batch_size), start=1):
                session.run(UPSERT_JOBS, rows=batch).consume()
                print(f"Imported {min(index * args.batch_size, len(jobs))}/{len(jobs)} jobs")

    print(f"Completed Neo4j import: {len(jobs)} jobs from {args.jobs}")


if __name__ == "__main__":
    main()
