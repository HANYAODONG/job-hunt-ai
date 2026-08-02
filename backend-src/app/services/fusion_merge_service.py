"""
Fusion Merge Service — 工作流4：多方分数合并与归一化

负责将工作流2（BM25/semantic）、工作流3（KG特征）的分散输出
按 (query_id, job_id) 合并为统一的 FusionInput 列表。

当前状态：
- BM25：通过 API 或 artifacts/bm25/ 文件接入 ✅
- Semantic：等叶骑瑞产出 artifacts/semantic_index/ 后接入
- KG：等魏昊朗产出 artifacts/kg/ 后接入

用法：
    from app.services.fusion_merge_service import merge_from_bm25_api

    # API 模式（在线）
    inputs = merge_from_bm25_api("resume_001", bm25_response)

    # 文件模式（离线批处理）
    inputs = merge_from_artifacts(
        bm25_candidates=bm25_records,
        # semantic_records=semantic_records,   # 后续接入
        # kg_records=kg_records,               # 后续接入
    )
"""

import logging
from typing import Any, Dict, List, Optional

from app.models.fusion import FusionInput

logger = logging.getLogger(__name__)


# ── BM25 分数归一化 ──────────────────────────────────────────────

def normalize_bm25_scores(
    candidates: List[Dict[str, Any]],
    score_key: str = "bm25_score",
) -> List[Dict[str, Any]]:
    """
    对候选集中的 BM25 原始分数做 min-max 归一化到 [0, 1]。

    BM25 原始分数无上限（Elasticsearch _score），不同查询之间不可比。
    归一化后与 semantic_score、skill_coverage 等因子处于同一量纲。

    边界情况：
    - 1条候选：归一化为 1.0
    - 全部同分：归一化为 1.0（避免除零）
    """
    if not candidates:
        return candidates

    scores = [c[score_key] for c in candidates]
    min_score = min(scores)
    max_score = max(scores)

    if max_score == min_score:
        # 全部同分或只有一条 → 统一给 1.0
        for c in candidates:
            c[f"{score_key}_raw"] = c[score_key]
            c[score_key] = 1.0
        return candidates

    for c in candidates:
        c[f"{score_key}_raw"] = c[score_key]
        c[score_key] = round((c[score_key] - min_score) / (max_score - min_score), 6)

    logger.debug(
        "BM25 normalized: %d candidates, range [%.2f, %.2f] → [0, 1]",
        len(candidates), min_score, max_score,
    )
    return candidates


# ── BM25 API 结果 → FusionInput ──────────────────────────────────

def merge_from_bm25_api(
    query_id: str,
    bm25_response: Dict[str, Any],
    include_meta: bool = True,
) -> List[FusionInput]:
    """
    从 BM25 API (/bm25/search) 的返回结果构造 FusionInput 列表。

    Args:
        query_id: 查询/简历 ID
        bm25_response: ChineseBM25Service.search() 的返回 dict
        include_meta: 是否附带岗位元数据（供前端展示）

    Returns:
        FusionInput 列表，bm25_score 已归一化，其余因子为 0.0
    """
    hits = bm25_response.get("hits", [])

    # Step 1: 提取候选分数
    candidates = [
        {
            "job_id": hit["job_id"],
            "bm25_score": hit["score"],
        }
        for hit in hits
    ]

    # Step 2: 归一化
    candidates = normalize_bm25_scores(candidates)

    # Step 3: 构造 FusionInput
    # 建立 hit 索引方便取元数据
    hit_by_job = {h["job_id"]: h for h in hits}

    inputs: List[FusionInput] = []
    for c in candidates:
        hit = hit_by_job.get(c["job_id"], {})
        inp_data: Dict[str, Any] = {
            "query_id": query_id,
            "job_id": c["job_id"],
            "bm25_score": c["bm25_score"],
            "semantic_score": 0.0,
            "skill_coverage": 0.0,
            "job_family_match": 0.0,
            "graph_relatedness": 0.0,
            "missing_skills": [],
            "evidence_paths": [],
        }
        if include_meta:
            inp_data["_meta"] = _extract_job_meta(hit)
        inputs.append(FusionInput(**inp_data))

    logger.info(
        "Merged %d BM25 candidates for query '%s' (total hits: %d)",
        len(inputs), query_id, bm25_response.get("total", 0),
    )
    return inputs


def _extract_job_meta(hit: Dict[str, Any]) -> Dict[str, Any]:
    """从 BM25 hit 中提取前端展示用的岗位元数据"""
    return {
        "title": hit.get("title", ""),
        "company": hit.get("company", ""),
        "standard_job": hit.get("standard_job", ""),
        "job_family": hit.get("job_family", ""),
        "location": hit.get("location", ""),
        "source_type": hit.get("source_type", ""),
        "bm25_score_raw": hit.get("score"),  # 保留原始分数
    }


# ── 文件模式合并（离线批处理）───────────────────────────────────

def merge_from_artifacts(
    bm25_candidates: Optional[List[Dict[str, Any]]] = None,
    semantic_candidates: Optional[List[Dict[str, Any]]] = None,
    kg_features: Optional[List[Dict[str, Any]]] = None,
    include_meta: bool = True,
) -> Dict[str, List[FusionInput]]:
    """
    从离线文件合并多方工作流输出，按 query_id 分组。

    每个工作流产出一个文件，格式见 docs/data-schema.md：

    BM25:  {query_id, candidates: [{job_id, bm25_score, bm25_rank}]}
    Semantic: {query_id, candidates: [{job_id, semantic_score, semantic_rank}]}
    KG:    {query_id, job_id, skill_coverage, job_family_match, graph_relatedness, ...}

    Args:
        bm25_candidates: 扁平化的 BM25 候选记录列表，每条包含 query_id + candidates
        semantic_candidates: 扁平化的语义候选记录列表
        kg_features: 扁平化的 KG 特征记录列表
        include_meta: 是否附带元数据

    Returns:
        {query_id: [FusionInput, ...]}  按 query_id 分组
    """
    # Step 1: 建立索引
    # (query_id, job_id) → partial scores
    merged: Dict[str, Dict[str, Dict[str, Any]]] = {}  # query_id → job_id → fields

    def _ensure(query_id: str, job_id: str) -> Dict[str, Any]:
        merged.setdefault(query_id, {})
        merged[query_id].setdefault(job_id, {
            "query_id": query_id,
            "job_id": job_id,
            "bm25_score": 0.0,
            "semantic_score": 0.0,
            "skill_coverage": 0.0,
            "job_family_match": 0.0,
            "graph_relatedness": 0.0,
            "missing_skills": [],
            "evidence_paths": [],
            "_meta": {},
            "_bm25_raw": None,  # 暂存归一化前的原始分数
        })
        return merged[query_id][job_id]

    # ── 合并 BM25 ──
    if bm25_candidates:
        for record in bm25_candidates:
            query_id = record["query_id"]
            candidates = record.get("candidates", [])
            # 先归一化
            normalized = normalize_bm25_scores(
                [{"job_id": c["job_id"], "bm25_score": c.get("bm25_score", 0)} for c in candidates]
            )
            norm_map = {c["job_id"]: c["bm25_score"] for c in normalized}
            for c in candidates:
                job_id = c["job_id"]
                entry = _ensure(query_id, job_id)
                entry["bm25_score"] = norm_map.get(job_id, 0.0)
                entry["_bm25_raw"] = c.get("bm25_score")
                entry["_meta"]["bm25_rank"] = c.get("bm25_rank")
        logger.info("Merged BM25 from %d queries", len(bm25_candidates))

    # ── 合并 Semantic ──
    if semantic_candidates:
        for record in semantic_candidates:
            query_id = record["query_id"]
            for c in record.get("candidates", []):
                job_id = c["job_id"]
                entry = _ensure(query_id, job_id)
                entry["semantic_score"] = c.get("semantic_score", 0.0)
                entry["_meta"]["semantic_rank"] = c.get("semantic_rank")
        logger.info("Merged semantic from %d queries", len(semantic_candidates))

    # ── 合并 KG 特征 ──
    if kg_features:
        for record in kg_features:
            query_id = record["query_id"]
            job_id = record["job_id"]
            entry = _ensure(query_id, job_id)
            entry["skill_coverage"] = record.get("skill_coverage", 0.0)
            entry["job_family_match"] = record.get("job_family_match", 0.0)
            entry["graph_relatedness"] = record.get("graph_relatedness", 0.0)
            entry["missing_skills"] = record.get("missing_skills", [])
            entry["evidence_paths"] = record.get("evidence_paths", [])
        logger.info("Merged KG features from %d records", len(kg_features))

    # Step 2: 转为 FusionInput 按 query 分组
    result: Dict[str, List[FusionInput]] = {}
    for query_id, jobs in merged.items():
        inputs = []
        for job_id, entry in jobs.items():
            if not include_meta:
                entry.pop("_meta", None)
                entry.pop("_bm25_raw", None)
            inputs.append(FusionInput(**entry))
        result[query_id] = inputs

    source_count = sum(
        1 for src in [bm25_candidates, semantic_candidates, kg_features] if src
    )
    total_pairs = sum(len(v) for v in result.values())
    logger.info(
        "merge_from_artifacts: %d queries, %d pairs, %d sources merged",
        len(result), total_pairs, source_count,
    )
    return result


# ── 辅助：从 artifact 文件读取 ───────────────────────────────────

def read_jsonl(path: str) -> List[Dict[str, Any]]:
    """读取 JSONL 文件，跳过空行"""
    import json
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records
