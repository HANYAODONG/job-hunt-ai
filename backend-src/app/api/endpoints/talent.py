"""Enterprise recruitment and candidate-pool API endpoints."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ...services.talent_data_service import TalentDataService
from .graph import invalidate_capability_graph_cache


router = APIRouter()
service = TalentDataService()


class JobUpdate(BaseModel):
    values: dict[str, Any]


class CandidateStageUpdate(BaseModel):
    status: Literal["待筛选", "待沟通", "入围", "不匹配"]


class CandidateExplanationRequest(BaseModel):
    use_llm: bool = True
    min_score: float = 55.0


@router.get("/recruitment/jobs")
def list_recruitment_jobs(
    query: str = "",
    status: str | None = None,
    source_type: str | None = "enterprise",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    try:
        return service.list_jobs(query, status, source_type, limit, offset)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/recruitment/jobs/{job_id}")
def get_recruitment_job(job_id: str):
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    return job


@router.put("/recruitment/jobs/{job_id}")
def save_recruitment_job(job_id: str, body: JobUpdate):
    try:
        saved = service.save_job(job_id, body.values)
        invalidate_capability_graph_cache()
        return saved
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save job: {exc}") from exc


@router.get("/recruitment/jobs/{job_id}/candidates")
def get_job_candidates(
    job_id: str,
    min_score: float = Query(default=55.0, ge=0, le=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=10, le=100),
    include_below_threshold: bool = False,
):
    try:
        result = service.match_candidates(
            job_id,
            min_score=min_score,
            page=page,
            page_size=page_size,
            include_below_threshold=include_below_threshold,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    return result


@router.patch("/recruitment/jobs/{job_id}/candidates/{candidate_id}/stage")
def update_candidate_stage(job_id: str, candidate_id: str, body: CandidateStageUpdate):
    if service.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    try:
        return service.update_candidate_stage(job_id, candidate_id, body.status)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save candidate stage: {exc}") from exc


@router.post("/recruitment/jobs/{job_id}/candidates/{candidate_id}/explanation")
def explain_candidate(job_id: str, candidate_id: str, body: CandidateExplanationRequest):
    try:
        result = service.explain_candidate(
            job_id,
            candidate_id,
            use_llm=body.use_llm,
            min_score=body.min_score,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="岗位或候选人不存在")
    return result


@router.get("/market/stats")
def get_market_stats():
    try:
        return service.market_stats()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
