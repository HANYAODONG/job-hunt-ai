"""Learning Plan API — 求职者端学习路径生成

为 `/learning` 页面提供最小输出接口（对应分工5 §7.3）：
    POST /api/v1/learning/plan
    POST /api/v1/learning/plan-from-diagnosis
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...services.learning_plan_service import build_learning_plan

logger = logging.getLogger(__name__)
router = APIRouter()


class MissingSkillInput(BaseModel):
    skill: str = Field(..., description="缺失技能名")
    priority: Optional[str] = Field(default="high", description="优先级：high / medium / low")
    reason: Optional[str] = Field(default=None, description="缺口说明")


class LearningPlanRequest(BaseModel):
    target_role: str = Field(..., min_length=1, description="目标岗位")
    missing_skills: List[MissingSkillInput] = Field(default_factory=list, description="缺失技能及优先级")
    candidate_name: Optional[str] = Field(default=None, description="候选人姓名/画像名")
    target_version: Optional[str] = Field(default=None, description="目标岗位版本")
    match_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="综合匹配度")


class DiagnosisInput(BaseModel):
    target_role: str = Field(..., description="目标岗位")
    missing_skills: List[str] = Field(default_factory=list, description="缺失技能列表（无优先级时全部视为 high）")
    matched_skills: List[str] = Field(default_factory=list, description="匹配技能列表")
    candidate_name: Optional[str] = Field(default=None)
    target_version: Optional[str] = Field(default=None)
    match_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)


@router.post("/plan", summary="生成学习路径（最小输出）")
async def generate_learning_plan(request: LearningPlanRequest):
    """根据目标岗位与缺失技能生成可交付、可复诊的学习阶段。"""
    try:
        missing_skills = [item.model_dump() for item in request.missing_skills]
        plan = build_learning_plan(
            target_role=request.target_role,
            missing_skills=missing_skills,
            candidate_name=request.candidate_name,
            target_version=request.target_version,
            match_score=request.match_score,
        )
        return plan
    except Exception as exc:
        logger.error("学习路径生成失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"学习路径生成失败: {str(exc)}")


@router.post("/plan-from-diagnosis", summary="由诊断结果直接生成学习路径")
async def generate_plan_from_diagnosis(request: DiagnosisInput):
    """接收诊断输出的 missing_skills，直接产出学习路径。"""
    try:
        missing_skills = [{"skill": s, "priority": "high"} for s in request.missing_skills]
        plan = build_learning_plan(
            target_role=request.target_role,
            missing_skills=missing_skills,
            candidate_name=request.candidate_name,
            target_version=request.target_version,
            match_score=request.match_score,
        )
        plan["matched_skills"] = request.matched_skills
        return plan
    except Exception as exc:
        logger.error("由诊断生成学习路径失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"由诊断生成学习路径失败: {str(exc)}")
