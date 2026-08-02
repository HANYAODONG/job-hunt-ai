"""
Fusion API Endpoints — 工作流4：融合排序 API

提供四种融合模式：
1. /rank            — 手动传入完整 FusionInput（所有因子已就绪时使用）
2. /rank-from-query — 传入查询文本，后端自动调 BM25 → 合并 → 融合（在线模式）
3. /mock-rank       — 纯 Mock 数据，前端独立开发用
4. /load-results    — 加载离线融合排序结果（从 artifacts/fusion_ranking/ 读取）
"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

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
from app.services.fusion_merge_service import merge_from_bm25_api
from app.core.database import get_elasticsearch
from app.services.chinese_bm25_service import ChineseBM25Service

logger = logging.getLogger(__name__)

router = APIRouter()


# ── 查询模式请求模型 ─────────────────────────────────────────────

class RankFromQueryRequest(BaseModel):
    """通过查询文本驱动的融合排序请求"""
    query_text: str = Field(..., min_length=1, description="查询文本（简历 summary 或自由文本）")
    query_id: Optional[str] = Field(default=None, description="查询/简历 ID，不传则自动生成")
    size: int = Field(default=20, ge=1, le=200, description="BM25 召回数量")
    weights: Optional[FusionWeights] = Field(default=None, description="自定义融合权重（不传则用服务端默认值）")
    source_type: Optional[str] = Field(default=None, description="enterprise 或 government")


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


# ── 查询驱动融合（在线模式）──────────────────────────────────────

@router.post("/rank-from-query", response_model=FusionBatchOutput, summary="查询驱动融合排序")
async def rank_from_query(body: RankFromQueryRequest):
    """
    输入查询文本，后端自动完成 BM25 召回 → 分数归一化 → 多因子融合 → 排序。

    这是工作流4的主入口。当前 BM25 分数来自真实 Elasticsearch，
    其余因子（semantic / skill_coverage / job_family / graph）待其他工作流接入后填充。

    用法：
    ```
    POST /fusion/rank-from-query
    {
      "query_text": "熟悉 Python、SQL，有数据分析项目经验",
      "size": 50,
      "weights": {"bm25": 1.0, "semantic": 0, "skill_coverage": 0, "job_family": 0, "graph": 0}
    }
    ```
    上例设置 bm25=1.0 → 纯 BM25 排序（消融实验的 BM25 baseline）。
    """
    try:
        # 1. 获取 Elasticsearch 连接
        es_client = get_elasticsearch()
        if es_client is None:
            raise HTTPException(status_code=503, detail="Elasticsearch 不可用，无法执行 BM25 检索")

        # 2. 调 BM25 服务
        bm25_service = ChineseBM25Service(es_client)
        bm25_result = bm25_service.search(
            query_text=body.query_text,
            size=body.size,
            source_type=body.source_type,
        )

        if not bm25_result.get("hits"):
            # BM25 无结果 → 返回空列表
            query_id = body.query_id or f"query_{id(body)}"
            return FusionBatchOutput(
                query_id=query_id,
                results=[],
                weights_used=(body.weights or get_weights()).model_dump(),
            )

        # 3. Merge：BM25 结果 → FusionInput 列表（含归一化）
        query_id = body.query_id or f"query_{id(body)}"
        fusion_inputs = merge_from_bm25_api(query_id, bm25_result)

        # 4. Fuse：加权融合排序
        w = body.weights if body.weights else None
        results = fuse_batch(fusion_inputs, w)

        used_weights = w or get_weights()
        return FusionBatchOutput(
            query_id=query_id,
            results=results,
            weights_used=used_weights.model_dump(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"rank-from-query error: {e}")
        raise HTTPException(status_code=500, detail=f"查询融合排序失败: {str(e)}")


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


# ── 离线融合结果加载 ─────────────────────────────────────────────

# 默认从 artifacts/ 读取，支持 Docker（/app/artifacts/）和本地运行
_ARTIFACTS_BASE = Path(__file__).resolve().parents[4]  # backend-src/app/api/endpoints/ -> repo root
_FUSION_RESULTS_DIR = _ARTIFACTS_BASE / "artifacts" / "fusion_ranking"
_JOBS_PATH = _ARTIFACTS_BASE / "artifacts" / "dataset_iteration_05" / "jobs.jsonl"
# Docker 容器内的 fallback
if not _FUSION_RESULTS_DIR.exists():
    _FUSION_RESULTS_DIR = Path("/app/artifacts/fusion_ranking")
    _JOBS_PATH = Path("/app/artifacts/dataset_iteration_05/jobs.jsonl")

# 岗位元数据缓存
_job_meta_cache: dict[str, dict] | None = None


def _load_job_meta() -> dict[str, dict]:
    """加载 jobs.jsonl 中的岗位元数据（标题、公司、地点、薪资等）"""
    global _job_meta_cache
    if _job_meta_cache is not None:
        return _job_meta_cache

    _job_meta_cache = {}
    if _JOBS_PATH.exists():
        with open(_JOBS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                job = json.loads(line)
                jid = job.get("job_id", "")
                if jid:
                    _job_meta_cache[jid] = {
                        "title": job.get("title", ""),
                        "company": job.get("company", "") or job.get("company_name", ""),
                        "standard_job": job.get("standard_job", ""),
                        "job_family": job.get("job_family", ""),
                        "location": job.get("location", "") or job.get("location_text", ""),
                        "salary": str(job.get("salary_text", "")) if job.get("salary_text") else "",
                        "source_type": job.get("source_type", ""),
                    }
    logger.info(f"Loaded {len(_job_meta_cache)} job metadata records")
    return _job_meta_cache


def _list_query_ids() -> list[str]:
    """快速获取所有 query_id，只读每一行的 query_id 字段"""
    path = _FUSION_RESULTS_DIR / "fusion_full.jsonl"
    if not path.exists():
        candidates = sorted(_FUSION_RESULTS_DIR.glob("fusion_*.jsonl"))
        path = candidates[0] if candidates else None
        if path is None:
            return []
    ids = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            ids.append(json.loads(line)["query_id"])
    return ids


def _load_query_results(query_id: str, preset: str = "full") -> list[dict]:
    """加载单个 query 的融合结果，附带岗位元数据"""
    path = _FUSION_RESULTS_DIR / f"fusion_{preset}.jsonl"
    if not path.exists():
        return []

    job_meta = _load_job_meta()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            batch = json.loads(line)
            if batch["query_id"] == query_id:
                results = batch.get("results", [])
                for r in results:
                    r["_preset"] = preset
                    jid = r.get("job_id", "")
                    if jid and jid in job_meta:
                        r["meta"] = job_meta[jid]
                return results
    return []


@router.get("/load-results", summary="加载离线融合排序结果")
async def load_fusion_results(
    query_id: Optional[str] = Query(default=None, description="指定 query_id，不传则列出所有可用的 query_id"),
    preset: Optional[str] = Query(default="full", description="融合预设: full, bm25-only, bm25-semantic, bm25-semantic-skill"),
):
    """
    从 artifacts/fusion_ranking/ 加载离线预计算的融合排序结果。

    - 不传 query_id：返回所有可用的 query_id 列表及数量
    - 传 query_id：返回该 query 的排序结果（含分项得分和解释）

    使用场景：
    - 前端以真实离线融合数据展示 5 因子效果
    - 其他工作流暂未提供在线服务时的降级方案
    """
    try:
        if query_id is not None:
            results = _load_query_results(query_id, preset)
            if not results:
                all_ids = _list_query_ids()
                return {
                    "query_id": query_id,
                    "available": False,
                    "message": f"未找到 query_id={query_id} 的结果",
                    "available_query_ids": sorted(all_ids)[:20],
                }
            results.sort(key=lambda r: r.get("final_score", 0), reverse=True)
            return {
                "query_id": query_id,
                "preset": preset,
                "count": len(results),
                "results": results,
            }

        # 不传 query_id：返回列表
        ids = _list_query_ids()
        if not ids:
            return {
                "available": False,
                "message": "未找到离线融合结果。请先运行 run_fusion_pipeline.py",
                "expected_dir": str(_FUSION_RESULTS_DIR),
            }
        return {
            "available": True,
            "total_queries": len(ids),
            "query_ids": sorted(ids),
        }
    except Exception as e:
        logger.error(f"加载融合结果失败: {e}")
        raise HTTPException(status_code=500, detail=f"加载融合结果失败: {str(e)}")
