"""
Fusion API Endpoints — 工作流4：融合排序 API

完全独立的 Mock API，不依赖 ES / Neo4j / 其他工作流。
后期接入真实 BM25、semantic、KG 分数时，替换 mock-rank 的数据源即可。
"""

import logging
from fastapi import APIRouter, HTTPException

from app.models.fusion import (
    FusionInput,
    FusionOutput,
    FusionBatchInput,
    FusionBatchOutput,
    FusionWeights,
    MockRankRequest,
)
from app.services.fusion_scoring_service import (
    fuse_single,
    fuse_batch,
    mock_rank,
    get_weights,
    update_weights,
    reset_weights,
    FACTOR_LABELS,
    FACTOR_ORDER,
    DEFAULT_WEIGHTS,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ── 核心融合接口 ─────────────────────────────────────────────────

@router.post("/score", response_model=FusionOutput, summary="单条融合评分")
async def score_single(inp: FusionInput):
    """
    接收单条融合输入，返回 final_score + score_breakdown + explanation。
    不涉及排名（rank 固定为 1）。
    """
    try:
        result = fuse_single(inp)
        result.rank = 1
        return result
    except Exception as e:
        logger.error(f"Fusion score error: {e}")
        raise HTTPException(status_code=500, detail=f"融合评分失败: {str(e)}")


@router.post("/rank", response_model=FusionBatchOutput, summary="批量融合排序")
async def rank_jobs(body: FusionBatchInput):
    """
    接收批量融合输入，按 final_score 降序排列并分配 rank。
    """
    try:
        results = fuse_batch(body.jobs)
        return FusionBatchOutput(
            query_id=body.query_id,
            results=results,
            weights_used=get_weights().model_dump(),
        )
    except Exception as e:
        logger.error(f"Fusion rank error: {e}")
        raise HTTPException(status_code=500, detail=f"批量排序失败: {str(e)}")


# ── Mock 接口（前端独立开发用）────────────────────────────────────

@router.post("/mock-rank", response_model=FusionBatchOutput, summary="Mock 融合排序")
async def mock_rank_endpoint(body: MockRankRequest = MockRankRequest()):
    """
    无需任何真实数据，服务端自动生成 Mock 融合输入并返回排序结果。

    前端直接调用此接口即可看到完整展示效果。
    后期其他工作流完成后，将前端调用切换到 /rank 即可。
    """
    try:
        weights = body.weights if body.weights else None
        results = mock_rank(
            query_id=body.query_id,
            num_jobs=body.num_jobs,
            seed=body.seed,
            weights=weights,
        )
        used_weights = weights or get_weights()
        return FusionBatchOutput(
            query_id=body.query_id,
            results=results,
            weights_used=used_weights.model_dump(),
        )
    except Exception as e:
        logger.error(f"Mock rank error: {e}")
        raise HTTPException(status_code=500, detail=f"Mock 融合排序失败: {str(e)}")


# ── 权重管理 ─────────────────────────────────────────────────────

@router.get("/weights", summary="查看当前融合权重")
async def get_fusion_weights():
    """返回当前服务端使用的融合权重和因子说明"""
    w = get_weights()
    return {
        "weights": w.model_dump(),
        "defaults": DEFAULT_WEIGHTS.model_dump(),
        "factors": {k: FACTOR_LABELS.get(k, k) for k in FACTOR_ORDER},
        "description": "各因子含义及当前权重。可通过 PUT /weights 动态调整。",
    }


@router.put("/weights", summary="修改融合权重")
async def update_fusion_weights(weights: FusionWeights):
    """
    动态调整融合权重（权重之和必须为 1.0）。
    修改后立即生效，无需重启服务。
    """
    try:
        updated = update_weights(weights)
        return {
            "message": "权重已更新",
            "weights": updated.model_dump(),
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/weights/reset", summary="恢复默认权重")
async def reset_fusion_weights():
    """恢复为系统默认的融合权重"""
    w = reset_weights()
    return {
        "message": "权重已恢复为默认值",
        "weights": w.model_dump(),
    }
