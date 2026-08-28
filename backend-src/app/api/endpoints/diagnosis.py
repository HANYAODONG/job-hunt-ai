"""Diagnosis API — 求职者端人岗诊断

为 `/diagnosis` 提供稳定的后端契约（对应分工5 §7.2）：
    POST /api/v1/diagnosis/analyze

请求可携带候选人/岗位技能列表与可选文本，返回统一字段：
    candidate_skills / target_job_skills / matched_skills / missing_skills
    semantic_score / final_score / score_breakdown / explanation
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...services.diagnosis_service import analyze_diagnosis
from ...services.nlp_service import NLPService

logger = logging.getLogger(__name__)
router = APIRouter()

# 模块级 NLP 服务（延迟初始化，避免导入即加载模型）
_nlp_service: Optional[NLPService] = None


def _get_nlp_service() -> Optional[NLPService]:
    global _nlp_service
    if _nlp_service is None:
        try:
            _nlp_service = NLPService()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("NLPService 初始化失败，语义分将回退 Jaccard: %s", exc)
            _nlp_service = None
    return _nlp_service


class DiagnosisRequest(BaseModel):
    candidate_id: str = Field(..., description="候选人/简历 ID")
    job_id: str = Field(..., description="目标岗位 ID")
    job_title: Optional[str] = Field(default=None, description="目标岗位标题")
    candidate_skills: List[str] = Field(default_factory=list, description="候选人技能")
    job_required_skills: List[str] = Field(default_factory=list, description="岗位要求技能")
    query_text: Optional[str] = Field(default=None, description="简历摘要/查询文本")
    job_text: Optional[str] = Field(default=None, description="岗位描述文本")
    bm25_score: float = Field(default=0.0, ge=0.0, description="BM25 归一化得分（可选）")
    semantic_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="语义得分（可选，缺省自动计算）")
    job_family_match: float = Field(default=0.0, ge=0.0, le=1.0, description="岗位族匹配（可选）")


@router.post("/analyze", summary="人岗诊断分析（稳定字段契约）")
async def diagnose(request: DiagnosisRequest):
    """计算候选人技能与目标岗位技能的差距，返回语义分与综合推荐分。"""
    try:
        result = analyze_diagnosis(
            candidate_id=request.candidate_id,
            job_id=request.job_id,
            candidate_skills=request.candidate_skills,
            job_required_skills=request.job_required_skills,
            job_title=request.job_title,
            query_text=request.query_text,
            job_text=request.job_text,
            bm25_score=request.bm25_score,
            semantic_score=request.semantic_score,
            job_family_match=request.job_family_match,
            nlp_service=_get_nlp_service(),
        )
        return result
    except Exception as exc:
        logger.error("人岗诊断失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"人岗诊断失败: {str(exc)}")
