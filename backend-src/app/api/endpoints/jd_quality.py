from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from ...services.jd_quality_service import JdQualityService


router = APIRouter()
service = JdQualityService()


class JobQualityRequest(BaseModel):
    job_id: str | None = None
    title: str = ""
    description: str = ""
    requirements: str = ""
    responsibilities: str = ""
    standard_job: str | None = None
    job_family: str | None = None
    skills: list[str] = Field(default_factory=list)
    use_llm: bool = False


class JobQualityBatchRequest(BaseModel):
    jobs: list[dict[str, Any]] = Field(default_factory=list)
    use_llm: bool = False
    llm_limit: int = Field(default=5, ge=0, le=20)


@router.post("/audit")
def audit_job(body: JobQualityRequest):
    job = body.model_dump(exclude={"use_llm"})
    return service.audit_job(job, use_llm=body.use_llm)


@router.post("/batch")
def audit_batch(body: JobQualityBatchRequest):
    return service.audit_batch(body.jobs, use_llm=body.use_llm, llm_limit=body.llm_limit)


@router.get("/sample")
def audit_sample(
    limit: int = Query(default=30, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    use_llm: bool = False,
    llm_limit: int = Query(default=5, ge=0, le=20),
):
    jobs = service.load_sample_jobs(limit, offset)
    result = service.audit_batch(jobs, use_llm=use_llm, llm_limit=llm_limit)
    result["summary"]["sample_offset"] = offset
    result["summary"]["sample_end"] = offset + len(jobs)
    return result


@router.get("/summary")
def summary(
    limit: int = Query(default=50, ge=1, le=200),
    use_llm: bool = False,
):
    jobs = service.load_sample_jobs(limit)
    result = service.audit_batch(jobs, use_llm=False)
    return service.summarize(result["items"], use_llm=use_llm)
