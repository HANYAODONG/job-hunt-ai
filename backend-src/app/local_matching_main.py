"""Minimal local API for testing the resume upload matching flow.

This entry point exposes the local `/jobs` matcher and the file-backed graph
router. It allows the frontend recommendation and role-galaxy pages to be
exercised without starting the optional Elasticsearch, Neo4j, vector, and
Fusion application services. Production and algorithm-team deployments can
continue to use ``app.main:app`` when those services are available.
"""

import os
from typing import List, Optional

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from .models.candidate import CandidateProfile
from .models.job import JobSearchQuery, JobSearchResult
from .core.config import settings
from .services.canonical_two_stage_matching_service import CanonicalTwoStageMatchingService
from .services.resume_service import ResumeService
from .api.endpoints import graph


# Do not initialize Neo4j for the local fallback runtime.
resume_service = ResumeService(persist_to_kg=False)
matching_service = CanonicalTwoStageMatchingService()
router = APIRouter()


async def _candidate_from_upload(resume_file: UploadFile, parser_mode: str) -> CandidateProfile:
    candidate_id = f"local_{hash(resume_file.filename)}"
    file_content = await resume_file.read()
    upload_record = await resume_service.save_uploaded_file(file_content, resume_file.filename, candidate_id)
    file_path = os.path.join(resume_service.upload_dir, upload_record.file_name)
    return await resume_service.process_resume_file(file_path, candidate_id, mode=parser_mode)


@router.post("/search-with-resume", response_model=JobSearchResult)
async def search_jobs_with_resume(
    resume_file: UploadFile = File(...),
    query: str = Form(""),
    location: Optional[str] = Form(None),
    min_salary: Optional[int] = Form(None),
    max_salary: Optional[int] = Form(None),
    job_type: Optional[str] = Form(None),
    experience_level: Optional[str] = Form(None),
    remote_allowed: Optional[bool] = Form(None),
    visa_sponsorship: Optional[bool] = Form(None),
    required_skills: List[str] = Form([]),
    preferred_skills: List[str] = Form([]),
    limit: int = Form(20),
    parser_mode: str = Form("auto"),
    pipeline_mode: str = Form("lightweight"),
):
    if (pipeline_mode or "lightweight").strip().lower() == "full":
        raise HTTPException(
            status_code=503,
            detail="完整链路需要使用 app.main 并启动 Elasticsearch、Neo4j、向量与 Fusion 服务；当前是轻量本地运行时。",
        )
    profile = await _candidate_from_upload(resume_file, parser_mode)
    search_query = JobSearchQuery(
        query=query,
        location=location,
        min_salary=min_salary,
        max_salary=max_salary,
        job_type=job_type,
        experience_level=experience_level,
        remote_allowed=remote_allowed,
        visa_sponsorship=visa_sponsorship,
        required_skills=required_skills,
        preferred_skills=preferred_skills,
    )
    result = matching_service.match(profile.candidate, search_query, limit=limit)
    if result.explanations is None:
        result.explanations = {}
    result.explanations.update({
        "runtime_pipeline_mode": "lightweight",
        "parser_mode": parser_mode or "auto",
    })
    return result


@router.post("/upload-resume", response_model=CandidateProfile)
async def upload_and_process_resume(
    resume_file: UploadFile = File(...),
    candidate_id: Optional[str] = None,
    parser_mode: str = Form("auto"),
):
    if candidate_id:
        # Keep explicit IDs useful for local API callers while sharing the
        # same save/process implementation as the search endpoint.
        file_content = await resume_file.read()
        upload_record = await resume_service.save_uploaded_file(file_content, resume_file.filename, candidate_id)
        file_path = os.path.join(resume_service.upload_dir, upload_record.file_name)
        return await resume_service.process_resume_file(file_path, candidate_id, mode=parser_mode)
    return await _candidate_from_upload(resume_file, parser_mode)


app = FastAPI(title="Job Matching Local Runtime", version="v2-local")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api/v1/jobs", tags=["jobs"])
app.include_router(graph.router, prefix="/api/v1", tags=["graph"])


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Job Matching Local Runtime",
        "role_pool_version": "v2",
        "resume_matching_pipeline": "canonical_two_stage",
        "runtime_pipeline_options": ["lightweight"],
        "default_parser_mode": "auto",
        "llm_resume_parser_enabled": bool(settings.ENABLE_LLM_RESUME_PARSER and settings.LLM_RESUME_API_KEY),
        "external_services_used": False,
    }
