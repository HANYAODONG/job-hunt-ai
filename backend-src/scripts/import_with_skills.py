"""Import normalized jobs into Neo4j with extracted or existing skills."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.models.job import ExperienceLevel, Job, JobType, Location
from app.services.knowledge_graph_service import KnowledgeGraphService
from app.services.skill_extractor import SkillExtractor


def import_jobs_with_skills(file_path: Path) -> int:
    extractor = SkillExtractor()
    kg = KnowledgeGraphService()
    imported = 0
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            data = json.loads(line)
            job_id = data.get("job_id") or data.get("id")
            if not job_id:
                continue
            skills = data.get("skills") or []
            if not skills:
                skills = extractor.extract(f"{data.get('title', '')} {data.get('description', '')}")
            if not skills:
                continue
            job = Job(
                id=job_id,
                title=data.get("title", ""),
                description=data.get("description", ""),
                company_name=data.get("company") or data.get("company_name", "未知"),
                location=Location(city="", state="", country="中国"),
                job_type=JobType.FULL_TIME,
                experience_level=ExperienceLevel.ENTRY,
                salary=None,
                benefits=[],
                required_skills=skills,
                preferred_skills=[],
                responsibilities=[],
                requirements=[],
                posted_date=datetime.now(),
                remote_allowed=False,
                visa_sponsorship=False,
                source_url=None,
                job_family=data.get("job_family", ""),
                source=data.get("source", "direct_import"),
            )
            if kg.create_job_node(job):
                imported += 1
    return imported


def main() -> None:
    parser = argparse.ArgumentParser(description="Import jobs into the knowledge graph with skills")
    parser.add_argument("--input", type=Path, default=REPO_ROOT / "artifacts" / "dataset_iteration_05" / "jobs.jsonl")
    args = parser.parse_args()
    print(f"Imported {import_jobs_with_skills(args.input)} jobs into Neo4j")


if __name__ == "__main__":
    main()