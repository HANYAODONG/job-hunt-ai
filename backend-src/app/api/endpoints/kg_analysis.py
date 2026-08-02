import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.services.knowledge_graph_service import KnowledgeGraphService

logger = logging.getLogger(__name__)
router = APIRouter()
kg_service = KnowledgeGraphService()


class GapAnalysisRequest(BaseModel):
    candidate_id: str
    job_id: str


class GapAnalysisResponse(BaseModel):
    query_id: str
    job_id: str
    resume_skills: List[str]
    job_required_skills: List[str]
    matched_skills: List[str]
    missing_skills: List[str]
    skill_coverage: float
    job_family_match: float
    graph_relatedness: float
    evidence_paths: List[str]


@router.post("/analyze", response_model=GapAnalysisResponse)
async def analyze_gap(request: GapAnalysisRequest):
    """
    分析简历与岗位之间的能力差距
    """
    try:
        candidate_id = request.candidate_id
        job_id = request.job_id
        
        # 从Neo4j查询岗位要求的技能列表和岗位族
        job_skills = []
        job_family = None
        with kg_service.neo4j.get_session() as session:
            job_query = """
            MATCH (j:Job {id: $job_id})
            OPTIONAL MATCH (j)-[:REQUIRES_SKILL]->(s:Skill)
            RETURN s.name AS skill, j.job_family AS job_family
            """
            result = session.run(job_query, {"job_id": job_id})
            records = list(result)
            if records:
                job_family = records[0].get("job_family")
                job_skills = [record["skill"] for record in records if record.get("skill")]
        
        # 从Neo4j查询候选人拥有的技能列表和目标岗位族
        resume_skills = []
        target_job_family = None
        with kg_service.neo4j.get_session() as session:
            resume_query = """
            MATCH (c:Candidate {id: $candidate_id})
            OPTIONAL MATCH (c)-[:HAS_SKILL]->(s:Skill)
            RETURN s.name AS skill, c.target_job_family AS target_job_family
            """
            result = session.run(resume_query, {"candidate_id": candidate_id})
            records = list(result)
            if records:
                target_job_family = records[0].get("target_job_family")
                resume_skills = [record["skill"] for record in records if record.get("skill")]
        
        # 如果没有找到岗位技能，返回空结果
        if not job_skills:
            return GapAnalysisResponse(
                query_id=candidate_id,
                job_id=job_id,
                resume_skills=resume_skills,
                job_required_skills=[],
                matched_skills=[],
                missing_skills=[],
                skill_coverage=0.0,
                job_family_match=0.0,
                graph_relatedness=0.0,
                evidence_paths=[]
            )
        
        # 计算匹配和缺失技能
        resume_skills_set = set(resume_skills)
        job_skills_set = set(job_skills)
        matched = list(resume_skills_set & job_skills_set)
        missing = list(job_skills_set - resume_skills_set)
        coverage = len(matched) / len(job_skills_set) if job_skills_set else 0.0
        
        # 构建证据路径
        evidence_paths = []
        for skill in matched:
            path = f"Candidate -> HAS_SKILL -> {skill} <- REQUIRES_SKILL <- Job"
            evidence_paths.append(path)
        
        # 用 Jaccard 相似度计算 graph_relatedness
        if job_skills_set:
            union_skills = resume_skills_set | job_skills_set
            graph_relatedness = len(matched) / len(union_skills) if union_skills else 0.0
        else:
            graph_relatedness = 0.0
        
        # 计算 job_family_match：如果两者都有值且相同则为1.0，否则为0.0
        job_family_match = 0.0
        if job_family and target_job_family and job_family == target_job_family:
            job_family_match = 1.0
        
        return GapAnalysisResponse(
            query_id=candidate_id,
            job_id=job_id,
            resume_skills=resume_skills,
            job_required_skills=job_skills,
            matched_skills=matched,
            missing_skills=missing,
            skill_coverage=round(coverage, 2),
            job_family_match=job_family_match,
            graph_relatedness=round(graph_relatedness, 4),
            evidence_paths=evidence_paths
        )
        
    except Exception as e:
        logger.error(f"能力差距分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))