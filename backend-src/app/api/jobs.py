from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
import os
from typing import List, Optional
import logging
from ..models.job import Job, JobSearchQuery, JobSearchResult
from ..models.candidate import Candidate, CandidateProfile, CandidateJobMatch
from ..services.hybrid_search_service import HybridSearchService
from ..services.resume_service import ResumeService
from ..services.elasticsearch_service import ElasticsearchService
from ..services.knowledge_graph_service import KnowledgeGraphService
from ..services.canonical_two_stage_matching_service import CanonicalTwoStageMatchingService
from ..core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# External services are intentionally lazy. The local canonical upload path
# does not require ES, Neo4j, vectors, or Fusion, so constructing them while
# importing this router would make an otherwise self-contained demo unusable.
hybrid_search_service: Optional[HybridSearchService] = None
resume_service = ResumeService()
es_service: Optional[ElasticsearchService] = None
kg_service: Optional[KnowledgeGraphService] = None
canonical_two_stage_service = CanonicalTwoStageMatchingService()


def _hybrid_service() -> HybridSearchService:
    global hybrid_search_service
    if hybrid_search_service is None:
        hybrid_search_service = HybridSearchService()
    return hybrid_search_service


def _elasticsearch_service() -> ElasticsearchService:
    global es_service
    if es_service is None:
        es_service = ElasticsearchService()
    return es_service


def _knowledge_graph_service() -> KnowledgeGraphService:
    global kg_service
    if kg_service is None:
        kg_service = KnowledgeGraphService()
    return kg_service

@router.post("/search", response_model=JobSearchResult)
async def search_jobs(query: JobSearchQuery):
    """Search for jobs using hybrid search (Elasticsearch + Knowledge Graph)"""
    try:
        results = _hybrid_service().search_jobs_with_semantic_matching(query)
        return results
    except Exception as e:
        logger.error(f"Error in job search: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during job search")

@router.post("/search-with-resume", response_model=JobSearchResult)
async def search_jobs_with_resume(
    resume_file: UploadFile = File(...),
    query: str = Form(...),
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
    # The interactive upload path uses the local canonical matcher by
    # default. Full hybrid matching is an explicit request-level opt-in.
    parser_mode: str = Form("auto"),
    pipeline_mode: str = Form("lightweight"),
):
    """Search for jobs with resume-based candidate matching"""
    try:
        # Create JobSearchQuery from form data
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
            preferred_skills=preferred_skills
        )
        
        # Process the uploaded resume
        candidate_id = f"temp_{hash(resume_file.filename)}"
        
        # Save uploaded file
        file_content = await resume_file.read()
        upload_record = await resume_service.save_uploaded_file(
            file_content, resume_file.filename, candidate_id
        )
        
        # Process resume to extract candidate profile
        file_path = os.path.join(resume_service.upload_dir, upload_record.file_name)
        candidate_profile = await resume_service.process_resume_file(
            file_path, candidate_id, mode=parser_mode
        )
        
        # The default upload path is the verified, self-contained v2
        # role-first matcher. Legacy hybrid remains opt-in for deployments
        # whose external ES/KG services are deliberately available.
        requested_pipeline = (pipeline_mode or "lightweight").strip().lower()
        if requested_pipeline not in {"lightweight", "full"}:
            raise HTTPException(status_code=422, detail="pipeline_mode must be lightweight or full")
        use_full_pipeline = requested_pipeline == "full" or settings.RESUME_MATCHING_PIPELINE == "legacy_hybrid"
        if use_full_pipeline:
            results = _hybrid_service().search_jobs_with_semantic_matching(
                search_query, candidate_profile.candidate
            )
        else:
            results = canonical_two_stage_service.match(
                candidate_profile.candidate, search_query, limit=limit
            )
        
        if results.explanations is None:
            results.explanations = {}
        results.explanations.update({
            "runtime_pipeline_mode": "full" if use_full_pipeline else "lightweight",
            "parser_mode": parser_mode or "auto",
        })
        return results
        
    except Exception as e:
        logger.error(f"Error in job search with resume: {e}")
        raise HTTPException(status_code=500, detail="Error processing resume or searching jobs")

@router.get("/{job_id}", response_model=Job)
async def get_job_by_id(job_id: str):
    """Get a specific job by ID"""
    try:
        job = _elasticsearch_service().get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{job_id}/similar", response_model=List[Job])
async def get_similar_jobs(
    job_id: str,
    limit: int = Query(default=10, ge=1, le=50)
):
    """Get similar jobs based on content similarity"""
    try:
        similar_jobs = _elasticsearch_service().get_similar_jobs(job_id, limit)
        return similar_jobs
    except Exception as e:
        logger.error(f"Error getting similar jobs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/", response_model=dict)
async def create_job(job: Job):
    """Create a new job posting"""
    try:
        # Index in Elasticsearch
        success = _elasticsearch_service().index_job(job)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to index job in Elasticsearch")
        
        # Create node in knowledge graph
        kg_success = _knowledge_graph_service().create_job_node(job)
        if not kg_success:
            logger.warning(f"Failed to create job node in knowledge graph for job {job.id}")
        
        return {"message": "Job created successfully", "job_id": job.id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/{job_id}", response_model=dict)
async def update_job(job_id: str, job: Job):
    """Update an existing job posting"""
    try:
        # Ensure the job ID matches
        job.id = job_id
        
        # Update in Elasticsearch
        success = _elasticsearch_service().index_job(job)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update job in Elasticsearch")
        
        # Update in knowledge graph (delete and recreate for simplicity)
        _knowledge_graph_service().create_job_node(job)
        
        return {"message": "Job updated successfully", "job_id": job_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/{job_id}", response_model=dict)
async def delete_job(job_id: str):
    """Delete a job posting"""
    try:
        # Delete from Elasticsearch
        success = _elasticsearch_service().delete_job(job_id)
        if not success:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return {"message": "Job deleted successfully", "job_id": job_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting job: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/bulk", response_model=dict)
async def bulk_create_jobs(jobs: List[Job]):
    """Bulk create multiple job postings"""
    try:
        # Bulk index in Elasticsearch
        result = _elasticsearch_service().bulk_index_jobs(jobs)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=f"Bulk indexing error: {result['error']}")
        
        # Create nodes in knowledge graph
        successful_jobs = []
        failed_jobs = []
        
        for job in jobs:
            kg_success = _knowledge_graph_service().create_job_node(job)
            if kg_success:
                successful_jobs.append(job.id)
            else:
                failed_jobs.append(job.id)
        
        return {
            "message": "Bulk job creation completed",
            "total_jobs": len(jobs),
            "successful_jobs": len(successful_jobs),
            "failed_jobs": len(failed_jobs),
            "failed_job_ids": failed_jobs
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk job creation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/market-trends/{skill}", response_model=dict)
async def get_market_trends(skill: str):
    """Get market trends for a specific skill"""
    try:
        trends = _hybrid_service().analyze_job_market_trends([skill])
        return trends
    except Exception as e:
        logger.error(f"Error getting market trends: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/recommendations", response_model=List[CandidateJobMatch])
async def get_job_recommendations(
    candidate: Candidate,
    limit: int = Query(default=10, ge=1, le=50)
):
    """Get personalized job recommendations for a candidate"""
    try:
        recommendations = _hybrid_service().get_job_recommendations(candidate, limit)
        return recommendations
    except Exception as e:
        logger.error(f"Error getting job recommendations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/upload-resume", response_model=CandidateProfile)
async def upload_and_process_resume(
    resume_file: UploadFile = File(...),
    candidate_id: Optional[str] = None,
    # Keep the default deterministic and local; `llm` remains an explicit
    # opt-in for offline or operator-driven experiments.
    parser_mode: str = Form("auto")
):
    """Upload and process a resume file with enhanced name extraction"""
    try:
        if not candidate_id:
            candidate_id = f"candidate_{hash(resume_file.filename)}"
        
        # Save uploaded file
        file_content = await resume_file.read()
        upload_record = await resume_service.save_uploaded_file(
            file_content, resume_file.filename, candidate_id
        )
        
        # Process resume to extract candidate profile
        file_path = os.path.join(resume_service.upload_dir, upload_record.file_name)
        candidate_profile = await resume_service.process_resume_file(
            file_path, candidate_id, mode=parser_mode
        )
        
        # Log the extracted name for verification
        extracted_name = candidate_profile.candidate.name
        logger.info(f"Extracted candidate name: '{extracted_name}' from file: {resume_file.filename}")
        
        return candidate_profile
        
    except Exception as e:
        logger.error(f"Error processing resume: {e}")
        raise HTTPException(status_code=500, detail="Error processing resume file")

@router.get("/resume-insights/{candidate_id}", response_model=dict)
async def get_resume_insights(candidate_id: str):
    """Get insights about a candidate's resume"""
    try:
        # This would typically fetch the candidate profile from a database
        # For now, we'll return a placeholder
        return {
            "message": "Resume insights endpoint - implementation needed",
            "candidate_id": candidate_id
        }
    except Exception as e:
        logger.error(f"Error getting resume insights: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
