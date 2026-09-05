"""Isolated fixture for demonstrating the new-role discovery workflow.

The fixture follows the same JD submission and review-queue path as a market
batch, but redirects every writable dependency to its own artifact directory.
It can therefore be run from the UI without changing production role data.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
import os
from pathlib import Path
import shutil
from uuid import uuid4

from . import discovery_service, job_service

from job_update.company_job_update.core.database import SQLiteJobUpdateStore
from job_update.company_job_update.core.frequency_store import FrequencyStore
from job_update.company_job_update.core.models import SkillMention
from job_update.company_job_update.core.service import JobUpdateSystem
from job_update.company_job_update.core.taxonomy import JobTaxonomy


ROOT = Path(os.getenv("JOB_HUNT_REPO_ROOT") or Path(__file__).resolve().parents[3])
BACKEND_ROOT = ROOT / "backend-src" if (ROOT / "backend-src").exists() else ROOT
FIXTURE = ROOT / "artifacts/discovery_synthetic_fixture/synthetic_new_role_jds.csv"
RUN_ROOT = ROOT / "artifacts/discovery_synthetic_fixture/runs"
REPORT = ROOT / "artifacts/discovery_synthetic_fixture/synthetic_discovery_report.json"
BASE_DICTIONARY = BACKEND_ROOT / "job_update/company_job_update/data/versions/company_large_v2/standard_job_title_dictionary.csv"


class _LowNoveltySimilarity:
    """Keep fixture titles in the conservative potential-new-job zone."""

    def score(self, _query: str, candidates: list[str]) -> list[float]:
        return [0.65 for _ in candidates]


class _FixtureSkillExtractor:
    def extract(self, _posting):
        return [
            SkillMention(
                normalized_skill="边缘智能体编排",
                kg_display_skill="边缘智能体编排",
                skill_type="method",
                confidence=0.99,
                span_text="边缘智能体编排",
            ),
            SkillMention(
                normalized_skill="端云协同",
                kg_display_skill="端云协同",
                skill_type="architecture",
                confidence=0.99,
                span_text="端云协同",
            ),
        ]


def run_synthetic_new_role_fixture() -> dict:
    """Submit 12 isolated JD signals and return the grouped review result."""
    if not FIXTURE.exists():
        raise FileNotFoundError(f"Synthetic discovery fixture not found: {FIXTURE}")
    # Every run gets its own directory.  This avoids interfering with an
    # in-flight SQLite connection from a previous UI request and preserves the
    # evidence used in a demo.
    run_dir = RUN_ROOT / f"run-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
    run_dir.mkdir(parents=True)

    dictionary = run_dir / "standard_job_title_dictionary.csv"
    if BASE_DICTIONARY.exists():
        shutil.copyfile(BASE_DICTIONARY, dictionary)
    else:
        dictionary.write_text(
            "standard_job_title,standard_category,match_keywords\n"
            "后端开发工程师,软件研发,后端|服务端|Backend\n"
            "大模型应用工程师,AI应用,大模型.*应用|LLM.*应用|智能体|Agent\n",
            encoding="utf-8-sig",
        )
    event_stream = run_dir / "job_update_event_stream.csv"
    event_stream.write_text(
        "job_id,month,standard_job,job_title,job_responsibility,job_requirement,skills\n",
        encoding="utf-8-sig",
    )
    database = run_dir / "synthetic_discovery.sqlite"
    store = SQLiteJobUpdateStore(database)
    store.migrate()

    system = JobUpdateSystem(
        taxonomy=JobTaxonomy.from_csv(dictionary),
        frequency_store=FrequencyStore(event_stream),
        similarity=_LowNoveltySimilarity(),
        skill_extractor=_FixtureSkillExtractor(),
        # Scores deliberately stay below this floor. The system therefore
        # queues a candidate without relying on an external LLM service.
        llm_job_floor=0.80,
    )

    original = {
        "job_database": job_service.BASE_DATABASE,
        "job_dictionary": job_service.BASE_TITLE_DICTIONARY,
        "job_skill_pool": job_service.BASE_SKILL_POOL,
        "job_initializer": job_service._ensure_database_initialized,
        "job_builder": job_service._build_system,
        "discovery_database": discovery_service.BASE_DATABASE,
        "discovery_stream": discovery_service.BASE_EVENT_STREAM,
        "discovery_skill_pool": discovery_service.BASE_SKILL_POOL,
    }
    try:
        job_service.BASE_DATABASE = database
        job_service.BASE_TITLE_DICTIONARY = dictionary
        job_service.BASE_SKILL_POOL = run_dir / "skill_pool.csv"
        job_service._ensure_database_initialized = store.migrate
        job_service._build_system = lambda _progress: system
        discovery_service.BASE_DATABASE = database
        discovery_service.BASE_EVENT_STREAM = event_stream
        discovery_service.BASE_SKILL_POOL = job_service.BASE_SKILL_POOL

        rows = list(csv.DictReader(FIXTURE.open("r", encoding="utf-8-sig", newline="")))
        submitted = []
        for row in rows:
            submitted.append(
                job_service.submit_one_dry_run(
                    {
                        "job_id": row["job_id"],
                        "month": row["month"],
                        "job_title": row["job_title"],
                        "responsibility": row["responsibility"],
                        "requirement": row["requirement"],
                        "source": row["source"],
                        "processing_mode": "manual",
                    }
                )
            )

        # The input batch is intentionally unclassified. It must remain a
        # candidate signal until the reviewer publishes a role definition.
        with event_stream.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["job_id", "month", "standard_job", "job_title", "job_responsibility", "job_requirement", "skills"],
            )
            for row in rows:
                writer.writerow({
                    "job_id": row["job_id"],
                    "month": row["month"],
                    "standard_job": "",
                    "job_title": row["job_title"],
                    "job_responsibility": row["responsibility"],
                    "job_requirement": row["requirement"],
                    "skills": "",
                })

        summary = discovery_service.batch_summary("2026-08", threshold=10)
        cluster = summary["candidates"][0] if summary["candidates"] else None
        result = {
            "synthetic_only": True,
            "production_state_changed": False,
            "run_directory": str(run_dir.relative_to(ROOT)),
            "fixture_jd_count": len(submitted),
            "route_statuses": sorted({item["result"]["route"]["status"] for item in submitted}),
            "batch": summary,
            "result_summary": {
                "title": cluster["title"] if cluster else "",
                "supporting_jd_count": cluster["supporting_jd_count"] if cluster else 0,
                "threshold": cluster["threshold"] if cluster else 10,
                "threshold_met": cluster["threshold_met"] if cluster else False,
                "status": cluster["status"] if cluster else "未生成候选",
            },
            "next_step": "人工审核候选岗位后，才允许提交定义、分配 canonical_role_id，并决定是否发布。",
        }
    finally:
        job_service.BASE_DATABASE = original["job_database"]
        job_service.BASE_TITLE_DICTIONARY = original["job_dictionary"]
        job_service.BASE_SKILL_POOL = original["job_skill_pool"]
        job_service._ensure_database_initialized = original["job_initializer"]
        job_service._build_system = original["job_builder"]
        discovery_service.BASE_DATABASE = original["discovery_database"]
        discovery_service.BASE_EVENT_STREAM = original["discovery_stream"]
        discovery_service.BASE_SKILL_POOL = original["discovery_skill_pool"]

    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
