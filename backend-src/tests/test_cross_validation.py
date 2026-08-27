from __future__ import annotations

from pathlib import Path

import pandas as pd

from job_update.company_job_update.core.candidate_skill_store import RoleSkillCandidateStore
from job_update.company_job_update.core.cross_role_evidence import CrossRoleEvidenceResolver
from job_update.company_job_update.core.models import JobPosting, NormalizedSkill, ScoredCandidate


def _posting(job_id: str, month: str) -> JobPosting:
    return JobPosting(job_id=job_id, month=month, job_title="后端开发工程师")


def test_candidate_requires_two_jobs_in_two_months(tmp_path: Path) -> None:
    store = RoleSkillCandidateStore(tmp_path / "candidates.db")
    skill = NormalizedSkill("MCP", "大模型")
    evidence = {"mcp": {"sentence": "熟悉 MCP 协议"}}

    first = store.evaluate(posting=_posting("jd-1", "2026-08"), standard_job="后端开发工程师", skills=[skill], trusted_skills=set(), evidence_by_skill=evidence, persist=True)
    second = store.evaluate(posting=_posting("jd-2", "2026-09"), standard_job="后端开发工程师", skills=[skill], trusted_skills=set(), evidence_by_skill=evidence, persist=True)

    assert first[0].status == "candidate"
    assert second[0].status == "confirmed_dynamic"
    row = store.list_candidates(status="confirmed")[0]
    assert row["support_job_count"] == 2
    assert row["support_month_count"] == 2


class _Taxonomy:
    def score_jobs(self, job_title: str, similarity: object) -> list[ScoredCandidate]:
        return [
            ScoredCandidate("后端开发工程师", 1.0, {"category": "研发"}),
            ScoredCandidate("大模型应用工程师", 0.91, {"category": "研发"}),
            ScoredCandidate("AI Agent应用工程师", 0.86, {"category": "研发"}),
        ]


def test_cross_role_requires_recent_confirmed_peer_evidence() -> None:
    resolver = CrossRoleEvidenceResolver(
        taxonomy=_Taxonomy(),  # type: ignore[arg-type]
        similarity=object(),  # type: ignore[arg-type]
        migration=pd.DataFrame([{"skill": "MCP", "migration_confidence": "high"}]),
        spread=pd.DataFrame([
            {"skill": "MCP", "standard_job": "大模型应用工程师", "month": "2026-07", "monthly_skill_count": 1, "cumulative_skill_count": 2},
            {"skill": "MCP", "standard_job": "AI Agent应用工程师", "month": "2026-06", "monthly_skill_count": 1, "cumulative_skill_count": 2},
        ]),
    )

    evidence = resolver.resolve(standard_job="后端开发工程师", skill="MCP", observed_month="2026-08")

    assert evidence["eligible"] is True
    assert evidence["peer_job_count"] == 2
