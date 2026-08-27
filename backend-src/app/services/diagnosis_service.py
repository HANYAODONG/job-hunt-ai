"""Diagnosis Service — 工作流：求职者端人岗诊断的稳定字段契约

为 `/diagnosis` 提供统一、稳定的返回字段（对应分工5 §7.2）：
    candidate_skills   候选人技能
    target_job_skills  目标岗位技能
    matched_skills     匹配技能
    missing_skills     缺失技能
    semantic_score     语义相关度
    final_score        综合推荐分
    explanation        诊断说明

该服务为纯逻辑实现：技能集合运算 + 语义相似度 + 融合评分，
不依赖 Elasticsearch / Neo4j，可在无基础设施的环境下运行与单测。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .fusion_scoring_service import fuse_single
from ..models.fusion import FusionInput

logger = logging.getLogger(__name__)

try:  # pragma: no cover - 语义模型为可选依赖
    from .nlp_service import NLPService
except Exception:  # pragma: no cover
    NLPService = None


def _normalize_skills(values: Any) -> List[str]:
    """归一化技能列表，去重保序。"""
    seen: set[str] = set()
    ordered: List[str] = []
    for value in values or []:
        if isinstance(value, dict):
            name = value.get("skill") or value.get("name") or value.get("normalized_skill") or ""
        else:
            name = str(value)
        name = name.strip()
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(name)
    return ordered


def compute_semantic_score(query_text: str, job_text: str, nlp_service: Any = None) -> float:
    """计算简历文本与岗位文本的语义相似度。

    优先使用 sentence-transformers / fallback 字符 n-gram 向量；
    若语义服务不可用，回退到词级 Jaccard 相似度。
    """
    if not query_text or not job_text:
        return 0.0

    # 1. 语义向量（NLPService 自带 fallback vectorizer，通常可用）
    if nlp_service is not None:
        try:
            embeddings = nlp_service.get_sentence_embeddings([query_text, job_text])
            if len(embeddings) == 2:
                a = embeddings[0]
                b = embeddings[1]
                import numpy as np

                a_norm = float(np.linalg.norm(a))
                b_norm = float(np.linalg.norm(b))
                if a_norm > 0 and b_norm > 0:
                    sim = float(np.dot(a, b) / (a_norm * b_norm))
                    return max(0.0, min(1.0, sim))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("语义向量计算失败，回退 Jaccard: %s", exc)

    # 2. 词级 Jaccard 回退
    q_tokens = set(query_text.split())
    j_tokens = set(job_text.split())
    union = q_tokens | j_tokens
    return len(q_tokens & j_tokens) / len(union) if union else 0.0


def analyze_diagnosis(
    candidate_id: str,
    job_id: str,
    candidate_skills: List[Any] = (),
    job_required_skills: List[Any] = (),
    job_title: Optional[str] = None,
    query_text: Optional[str] = None,
    job_text: Optional[str] = None,
    bm25_score: float = 0.0,
    semantic_score: Optional[float] = None,
    job_family_match: float = 0.0,
    nlp_service: Any = None,
) -> Dict[str, Any]:
    """执行一次人岗诊断，返回稳定字段契约。

    semantic_score 为空时自动计算；final_score 使用分层融合公式生成。
    """
    candidate = _normalize_skills(candidate_skills)
    required = _normalize_skills(job_required_skills)

    candidate_set = set(casefold(s) for s in candidate)
    required_set = set(casefold(s) for s in required)

    matched = [s for s in candidate if casefold(s) in required_set]
    missing = [s for s in required if casefold(s) not in candidate_set]

    skill_coverage = round(len(matched) / len(required), 4) if required else 0.0

    # graph_relatedness：Jaccard 相似度
    union_skills = candidate_set | required_set
    graph_relatedness = round(len(matched) / len(union_skills), 4) if union_skills else 0.0

    # 语义分：优先用传入值，否则计算
    if semantic_score is None:
        q_text = query_text or " ".join(candidate)
        j_text = job_text or " ".join([job_title or "", *required])
        semantic_score = compute_semantic_score(q_text, j_text, nlp_service)
    semantic_score = max(0.0, min(1.0, float(semantic_score)))

    # 融合评分
    fusion_input = FusionInput(
        query_id=candidate_id,
        job_id=job_id,
        bm25_score=max(0.0, float(bm25_score)),
        semantic_score=semantic_score,
        skill_coverage=skill_coverage,
        job_family_match=max(0.0, min(1.0, float(job_family_match))),
        graph_relatedness=graph_relatedness,
        matched_skills=matched,
        missing_skills=missing,
        evidence_paths=[],
    )
    fusion_output = fuse_single(fusion_input)

    explanation = (
        fusion_output.explanation.reason
        or f"匹配技能 {len(matched)} 项，待补充技能 {len(missing)} 项，综合匹配度 {round(fusion_output.final_score * 100)}%。"
    )

    return {
        "candidate_id": candidate_id,
        "job_id": job_id,
        "candidate_skills": candidate,
        "target_job_skills": required,
        "matched_skills": matched,
        "missing_skills": missing,
        "skill_coverage": skill_coverage,
        "semantic_score": round(semantic_score, 4),
        "final_score": fusion_output.final_score,
        "score_breakdown": fusion_output.score_breakdown.model_dump(),
        "explanation": explanation,
    }


def casefold(value: str) -> str:
    return str(value or "").strip().casefold()
