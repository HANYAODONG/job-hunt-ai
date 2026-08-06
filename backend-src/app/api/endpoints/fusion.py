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
import re
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.models.fusion import (
    FusionInput,
    FusionOutput,
    FusionBatchInput,
    FusionBatchOutput,
    FusionWeights,
    LayeredWeights,
    MockRankRequest,
)
from app.services.fusion_scoring_service import (
    fuse_single,
    fuse_batch,
    mock_rank,
    get_weights,
    get_layered_weights,
    update_weights,
    update_layered_weights,
    reset_weights,
    FACTOR_LABELS,
    FACTOR_ORDER,
    DEFAULT_WEIGHTS,
    DEFAULT_LAYERED_WEIGHTS,
)
from app.services.fusion_merge_service import merge_from_bm25_api, normalize_bm25_scores
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
    weights: Optional[FusionWeights] = Field(default=None, description="[旧格式] 自定义融合权重")
    layered_weights: Optional[LayeredWeights] = Field(default=None, description="[v2] 分层融合权重，不传则用服务端默认值")
    source_type: Optional[str] = Field(default=None, description="enterprise 或 government")


class RecommendRequest(BaseModel):
    """前端统一推荐请求。candidate_id 和 query_text 至少传一个。"""

    candidate_id: Optional[str] = Field(default=None, description="标准简历/候选人 ID")
    query_text: Optional[str] = Field(default=None, description="自由查询文本或简历文本")
    top_k: int = Field(default=10, ge=1, le=50, description="最终返回数量")
    candidate_pool: int = Field(default=100, ge=1, le=200, description="召回候选池大小")
    mode: Literal["auto", "sample", "offline", "online", "mock"] = Field(
        default="auto",
        description="auto 优先在线，失败后回退；sample 使用 sample_pack 即时链路；offline 读取离线融合结果；mock 使用模拟数据",
    )
    source_type: Optional[str] = Field(default=None, description="enterprise 或 government")
    layered_weights: Optional[LayeredWeights] = Field(default=None, description="本次请求使用的分层融合权重")


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
            weights_used=get_layered_weights().model_dump(),
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
            query_id = body.query_id or f"query_{id(body)}"
            return FusionBatchOutput(
                query_id=query_id,
                results=[],
                weights_used=get_layered_weights().model_dump(),
            )

        # 3. Merge & Fuse
        query_id = body.query_id or f"query_{id(body)}"
        fusion_inputs = merge_from_bm25_api(query_id, bm25_result)

        if body.layered_weights is not None:
            update_layered_weights(body.layered_weights)
        results = fuse_batch(fusion_inputs)

        return FusionBatchOutput(
            query_id=query_id,
            results=results,
            weights_used=get_layered_weights().model_dump(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"rank-from-query error: {e}")
        raise HTTPException(status_code=500, detail=f"查询融合排序失败: {str(e)}")


@router.post("/recommend", response_model=FusionBatchOutput, summary="前端统一推荐接口")
async def recommend(body: RecommendRequest):
    """
    前端主入口：返回 TopN 推荐、分项得分和推荐解释。

    当前支持四种模式：
    - online: 调 Elasticsearch BM25 后融合；适合真实服务已启动时使用。
    - sample: 读取 dataset_iteration_05/sample_pack 即时生成一条完整链路；适合联调。
    - offline: 读取 artifacts/fusion_ranking 下的预计算结果。
    - mock: 使用服务端 Mock 数据。

    auto 会先尝试 online，失败后回退到 offline/sample，保证前端联调不中断。
    """
    try:
        if body.layered_weights is not None:
            update_layered_weights(body.layered_weights)

        query_id = body.candidate_id or "adhoc_query"

        if body.mode == "mock":
            results = mock_rank(query_id=query_id, num_jobs=body.top_k, layered_weights=body.layered_weights)
            return FusionBatchOutput(query_id=query_id, results=results[: body.top_k], weights_used=get_layered_weights().model_dump())

        if body.mode in {"online", "auto"}:
            try:
                online_results = await _recommend_online(body)
                if online_results.results or body.mode == "online":
                    return online_results
            except Exception as exc:
                if body.mode == "online":
                    raise
                logger.warning("Online recommend failed; falling back to offline/sample: %s", exc)

        if body.mode in {"offline", "auto"} and body.candidate_id:
            offline_results = _recommend_from_offline(body)
            if offline_results.results or body.mode == "offline":
                return offline_results

        return _recommend_from_standard_dataset(body)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("recommend error: %s", e)
        raise HTTPException(status_code=500, detail=f"统一推荐失败: {str(e)}")


# ── Mock 接口（前端独立开发用）────────────────────────────────────

@router.post("/mock-rank", response_model=FusionBatchOutput, summary="Mock 融合排序")
async def mock_rank_endpoint(body: MockRankRequest = MockRankRequest()):
    """
    无需任何真实数据，服务端自动生成 Mock 融合输入并返回排序结果。
    """
    try:
        results = mock_rank(
            query_id=body.query_id,
            num_jobs=body.num_jobs,
            seed=body.seed,
            layered_weights=body.layered_weights,
        )
        used_weights = get_layered_weights()
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


# ── 分层权重管理（第三阶段 v2）─────────────────────────────────────

@router.get("/weights/layered", summary="查看当前分层融合权重")
async def get_layered_fusion_weights():
    """返回当前分层融合权重和公式说明"""
    lw = get_layered_weights()
    return {
        "weights": lw.model_dump(),
        "defaults": DEFAULT_LAYERED_WEIGHTS.model_dump(),
        "formula": {
            "relevance": "relevance_score = w_bm25 * bm25 + w_semantic * semantic",
            "ability": "ability_score = normalize( w_skill * skill + w_graph * graph )  within candidates",
            "final": "final_score = relevance_score * (base + multiplier * ability_score)",
            "gate": "if job_family_match == 0: final_score *= family_discount",
        },
    }


@router.put("/weights/layered", summary="修改分层融合权重")
async def update_layered_fusion_weights(lw: LayeredWeights):
    """动态调整分层融合权重。修改后立即生效。"""
    try:
        updated = update_layered_weights(lw)
        return {
            "message": "分层权重已更新",
            "weights": updated.model_dump(),
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ── 离线融合结果加载 ─────────────────────────────────────────────

# 默认从 artifacts/ 读取，支持 Docker（/app/artifacts/）和本地运行。
# 注意：fusion_ranking 和 dataset_iteration_05 可能不是同时生成的，必须分别判断。
_ARTIFACTS_BASE = Path(__file__).resolve().parents[4]  # backend-src/app/api/endpoints/ -> repo root
_LOCAL_ARTIFACTS = _ARTIFACTS_BASE / "artifacts"
_DOCKER_ARTIFACTS = Path("/app/artifacts")

_FUSION_RESULTS_DIR = _LOCAL_ARTIFACTS / "fusion_ranking"
if not _FUSION_RESULTS_DIR.exists():
    _FUSION_RESULTS_DIR = _DOCKER_ARTIFACTS / "fusion_ranking"

_DATASET_DIR = _LOCAL_ARTIFACTS / "dataset_iteration_05"
if not _DATASET_DIR.exists():
    _DATASET_DIR = _DOCKER_ARTIFACTS / "dataset_iteration_05"

_JOBS_PATH = _DATASET_DIR / "jobs.jsonl"

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


async def _recommend_online(body: RecommendRequest) -> FusionBatchOutput:
    query_text, query_id = _resolve_query_text(body)
    rank_request = RankFromQueryRequest(
        query_text=query_text,
        query_id=query_id,
        size=body.candidate_pool,
        layered_weights=body.layered_weights,
        source_type=body.source_type,
    )
    ranked = await rank_from_query(rank_request)
    ranked.results = ranked.results[: body.top_k]
    return ranked


def _recommend_from_offline(body: RecommendRequest) -> FusionBatchOutput:
    query_id = body.candidate_id or "adhoc_query"
    results = _load_query_results(query_id, preset="full")[: body.top_k]
    return FusionBatchOutput(
        query_id=query_id,
        results=[FusionOutput(**item) for item in results],
        weights_used=get_layered_weights().model_dump(),
    )


def _recommend_from_standard_dataset(body: RecommendRequest) -> FusionBatchOutput:
    dataset_dir = _DATASET_DIR
    jobs_path = dataset_dir / "sample_pack" / "jobs_sample.jsonl"
    candidates_path = dataset_dir / "sample_pack" / "candidate_profiles_sample.jsonl"
    if body.mode not in {"sample", "auto"}:
        jobs_path = dataset_dir / "jobs.jsonl"
        candidates_path = dataset_dir / "candidate_profiles.jsonl"

    if not jobs_path.exists() or not candidates_path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "标准数据产物不存在，请先运行 scripts/dataset_adapter.py。"
                f" expected jobs={jobs_path}, candidates={candidates_path}"
            ),
        )

    jobs = _read_jsonl(jobs_path)
    candidates = _read_jsonl(candidates_path)
    candidate = _find_candidate(candidates, body.candidate_id) if body.candidate_id else None
    query_id = body.candidate_id or "adhoc_query"
    query_text = body.query_text or _candidate_text(candidate)
    if not query_text:
        raise HTTPException(status_code=422, detail="candidate_id 和 query_text 至少需要一个可用输入")

    if body.source_type:
        jobs = [job for job in jobs if str(job.get("source_type", "")).lower() == body.source_type.lower()]
    if not jobs:
        return FusionBatchOutput(query_id=query_id, results=[], weights_used=get_layered_weights().model_dump())

    fusion_inputs = _build_sample_fusion_inputs(
        query_id=query_id,
        query_text=query_text,
        candidate=candidate,
        jobs=jobs,
        candidate_pool=body.candidate_pool,
        source_label="sample_pack" if "sample_pack" in str(jobs_path) else "standard_dataset",
    )
    results = fuse_batch(fusion_inputs)[: body.top_k]
    return FusionBatchOutput(
        query_id=query_id,
        results=results,
        weights_used=get_layered_weights().model_dump(),
    )


def _resolve_query_text(body: RecommendRequest) -> tuple[str, str]:
    if body.query_text and body.query_text.strip():
        return body.query_text.strip(), body.candidate_id or "adhoc_query"

    dataset_dir = _DATASET_DIR
    candidate_paths = [
        dataset_dir / "sample_pack" / "candidate_profiles_sample.jsonl",
        dataset_dir / "candidate_profiles.jsonl",
    ]
    for path in candidate_paths:
        if not path.exists():
            continue
        candidate = _find_candidate(_read_jsonl(path), body.candidate_id)
        if candidate:
            text = _candidate_text(candidate)
            if text:
                return text, body.candidate_id or candidate.get("candidate_id", "adhoc_query")

    raise HTTPException(status_code=422, detail="online 模式需要 query_text，或可在标准数据中找到 candidate_id")


def _build_sample_fusion_inputs(
    query_id: str,
    query_text: str,
    candidate: Optional[dict[str, Any]],
    jobs: list[dict[str, Any]],
    candidate_pool: int,
    source_label: str,
) -> list[FusionInput]:
    resume_skills = _skill_set(candidate.get("skills", []) if candidate else [])
    target_family = str((candidate or {}).get("target_job_family") or "").strip()
    query_tokens = _tokenize(query_text)

    scored: list[dict[str, Any]] = []
    for job in jobs:
        job_text = _job_text(job)
        job_tokens = _tokenize(job_text)
        job_skills = _skill_set(job.get("skills") or job.get("required_skills") or [])
        token_overlap = len(query_tokens & job_tokens)
        skill_overlap = len(resume_skills & job_skills)
        bm25_score = token_overlap + skill_overlap * 3
        if bm25_score <= 0:
            bm25_score = 0.01
        scored.append({"job": job, "job_id": job.get("job_id", ""), "bm25_score": float(bm25_score)})

    scored.sort(key=lambda item: item["bm25_score"], reverse=True)
    top = scored[:candidate_pool]
    normalized = normalize_bm25_scores(
        [{"job_id": item["job_id"], "bm25_score": item["bm25_score"]} for item in top]
    )
    bm25_map = {item["job_id"]: item["bm25_score"] for item in normalized}

    inputs: list[FusionInput] = []
    for rank, item in enumerate(top, start=1):
        job = item["job"]
        job_id = str(job.get("job_id", ""))
        job_skills = _skill_set(job.get("skills") or job.get("required_skills") or [])
        matched = sorted(resume_skills & job_skills)
        missing = sorted(job_skills - resume_skills)
        skill_coverage = len(matched) / len(job_skills) if job_skills else 0.0
        union = resume_skills | job_skills
        graph_relatedness = len(matched) / len(union) if union else 0.0
        semantic_score = _jaccard(_tokenize(query_text), _tokenize(_job_text(job)))
        if resume_skills or job_skills:
            semantic_score = max(semantic_score, _jaccard(resume_skills, job_skills))

        job_family = str(job.get("job_family") or job.get("standard_job") or "").strip()
        job_family_match = 1.0 if target_family and job_family and target_family == job_family else 0.0
        if not target_family:
            job_family_match = 1.0

        inputs.append(
            FusionInput(
                query_id=query_id,
                job_id=job_id,
                bm25_score=bm25_map.get(job_id, 0.0),
                semantic_score=round(float(semantic_score), 6),
                skill_coverage=round(float(skill_coverage), 6),
                job_family_match=job_family_match,
                graph_relatedness=round(float(graph_relatedness), 6),
                matched_skills=matched[:20],
                missing_skills=missing[:20],
                evidence_paths=[f"Candidate -> HAS_SKILL -> {skill} <- REQUIRES_SKILL <- Job" for skill in matched[:5]],
                _meta={
                    "title": job.get("title", ""),
                    "company": job.get("company", "") or job.get("company_name", ""),
                    "standard_job": job.get("standard_job", ""),
                    "job_family": job_family,
                    "location": job.get("location", "") or job.get("location_text", ""),
                    "salary": str(job.get("salary_text", "")) if job.get("salary_text") else "",
                    "source_type": job.get("source_type", ""),
                    "bm25_rank": rank,
                    "recommend_source": source_label,
                },
            )
        )
    return inputs


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def _find_candidate(candidates: list[dict[str, Any]], candidate_id: Optional[str]) -> Optional[dict[str, Any]]:
    if not candidate_id:
        return candidates[0] if candidates else None
    for candidate in candidates:
        if candidate.get("candidate_id") == candidate_id or candidate.get("resume_id") == candidate_id:
            return candidate
    return None


def _candidate_text(candidate: Optional[dict[str, Any]]) -> str:
    if not candidate:
        return ""
    return "\n".join(
        str(part).strip()
        for part in [
            candidate.get("summary"),
            candidate.get("profile_text"),
            " ".join(candidate.get("skills", []) or []),
            candidate.get("target_job_family"),
        ]
        if str(part or "").strip()
    )


def _job_text(job: dict[str, Any]) -> str:
    return "\n".join(
        str(part).strip()
        for part in [
            job.get("title"),
            job.get("description"),
            job.get("job_family"),
            " ".join(job.get("skills", []) or job.get("required_skills", []) or []),
        ]
        if str(part or "").strip()
    )


def _skill_set(values: Any) -> set[str]:
    if not values:
        return set()
    if isinstance(values, str):
        parts = re.split(r"[;；,，、\n\r\t]+", values)
    else:
        parts = values
    return {str(item).strip().lower() for item in parts if str(item or "").strip()}


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9_+#.-]+|[\u4e00-\u9fff]{2,}", text or "")}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


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
