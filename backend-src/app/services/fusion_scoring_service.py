"""
Fusion Scoring Service — 工作流4：融合排序引擎

纯函数实现，无数据库依赖，可直接在本地运行测试。
"""
import random
import logging
from typing import List, Dict

from app.models.fusion import (
    FusionInput,
    FusionOutput,
    ScoreBreakdown,
    ExplanationDetail,
    FusionWeights,
    LayeredWeights,
)

logger = logging.getLogger(__name__)

# ── 默认权重 ────────────────────────────────────────────────────
DEFAULT_WEIGHTS = FusionWeights(
    bm25=0.15,
    semantic=0.25,
    skill_coverage=0.30,
    job_family=0.15,
    graph=0.15,
)

DEFAULT_LAYERED_WEIGHTS = LayeredWeights(
    relevance_bm25=0.4,
    relevance_semantic=0.6,
    ability_skill=0.7,
    ability_graph=0.3,
    relevance_base=0.7,
    ability_multiplier=0.3,
    family_discount=1.0,
)

# 运行时权重（可通过 API 修改）
_current_weights: FusionWeights = DEFAULT_WEIGHTS
_current_layered_weights: LayeredWeights = DEFAULT_LAYERED_WEIGHTS


# ── 因子中文标签 ─────────────────────────────────────────────────
FACTOR_LABELS: Dict[str, str] = {
    "bm25": "关键词匹配",
    "semantic": "语义相似度",
    "skill_coverage": "技能覆盖",
    "job_family": "岗位大类匹配",
    "graph": "知识图谱关联",
}

FACTOR_ORDER: List[str] = ["bm25", "semantic", "skill_coverage", "job_family", "graph"]


def get_weights() -> FusionWeights:
    """获取当前融合权重（旧格式，向后兼容）"""
    return _current_weights


def get_layered_weights() -> LayeredWeights:
    """获取当前分层融合权重"""
    return _current_layered_weights


def update_weights(weights: FusionWeights) -> FusionWeights:
    """更新融合权重（旧格式，向后兼容）"""
    global _current_weights
    weights.validate_sum()
    _current_weights = weights
    logger.info(f"Fusion weights updated (legacy): {weights.model_dump()}")
    return _current_weights


def update_layered_weights(lw: LayeredWeights) -> LayeredWeights:
    """更新分层融合权重"""
    global _current_layered_weights
    lw.validate_groups()
    _current_layered_weights = lw
    logger.info(f"Layered weights updated: {lw.model_dump()}")
    return _current_layered_weights


def reset_weights() -> FusionWeights:
    """恢复默认权重"""
    global _current_weights, _current_layered_weights
    _current_weights = DEFAULT_WEIGHTS
    _current_layered_weights = DEFAULT_LAYERED_WEIGHTS
    return _current_weights


# ── 核心融合函数（第三阶段 v2：分层融合）──────────────────────────

def _normalize_within_batch(values: list[float]) -> list[float]:
    """对一批数值做 min-max 归一化到 [0, 1]。

    边界情况：
    - 单元素：返回 [0.5]（无法比较时取中间值）
    - 全部同分：全部返回 1.0
    """
    if not values:
        return []
    if len(values) == 1:
        return [0.5]
    mn, mx = min(values), max(values)
    if mx == mn:
        return [1.0] * len(values)
    return [(v - mn) / (mx - mn) for v in values]


def compute_final_score(inp: FusionInput, weights: FusionWeights = None) -> float:
    """
    [兼容旧接口] 五因子简单加权，仅在旧调用路径中使用。
    新代码请使用 compute_layered_score()。
    """
    w = weights or _current_weights
    return (
        inp.bm25_score * w.bm25
        + inp.semantic_score * w.semantic
        + inp.skill_coverage * w.skill_coverage
        + inp.job_family_match * w.job_family
        + inp.graph_relatedness * w.graph
    )


def compute_layered_score(
    inp: FusionInput,
    ability_norm: float = 0.5,  # 候选集内归一化后的能力分，单条时默认 0.5
    lw: LayeredWeights = None,
) -> float:
    """分层融合公式（第三阶段 v2）

    relevance = w_bm25 * bm25 + w_semantic * semantic
    final = relevance * (base + multiplier * ability_norm)
    若 job_family_match == 0，额外乘以 family_discount
    """
    w = lw or _current_layered_weights

    relevance = inp.bm25_score * w.relevance_bm25 + inp.semantic_score * w.relevance_semantic
    final = relevance * (w.relevance_base + w.ability_multiplier * ability_norm)

    # job_family 门控：不匹配时打折
    if inp.job_family_match < 0.5:
        final *= w.family_discount

    return max(0.0, min(1.0, final))


def fuse_single(inp: FusionInput, weights: FusionWeights = None) -> FusionOutput:
    """
    单条融合（兼容旧接口，内部走分层公式）。
    单条时 ability_norm 固定为 0.5（无候选集可比较）。
    """
    lw = _current_layered_weights
    final_score = compute_layered_score(inp, ability_norm=0.5, lw=lw)

    breakdown = ScoreBreakdown(
        bm25_score=round(inp.bm25_score, 4),
        semantic_score=round(inp.semantic_score, 4),
        skill_coverage=round(inp.skill_coverage, 4),
        job_family_match=round(inp.job_family_match, 4),
        graph_relatedness=round(inp.graph_relatedness, 4),
    )

    explanation = generate_explanation(inp, final_score)

    return FusionOutput(
        query_id=inp.query_id,
        job_id=inp.job_id,
        final_score=round(final_score, 4),
        rank=0,
        score_breakdown=breakdown,
        explanation=explanation,
        evidence_paths=inp.evidence_paths,
        meta=getattr(inp, '_meta', None),
    )


def fuse_batch(inputs: List[FusionInput], weights: FusionWeights = None) -> List[FusionOutput]:
    """
    批量融合（第三阶段 v2：分层融合 + 候选集内能力归一化）。

    流程：
    1. 对每个候选计算 relevance_score
    2. 对每个候选计算 raw_ability，然后在候选集内 min-max 归一化
    3. final_score = relevance * (base + multiplier * ability_norm)
    4. job_family_match == 0 时打折
    5. 按 final_score 降序排列，分配 rank
    """
    lw = _current_layered_weights

    # Step 1 & 2: 计算 relevance 和 raw_ability
    relevances = []
    raw_abilities = []
    for inp in inputs:
        r = inp.bm25_score * lw.relevance_bm25 + inp.semantic_score * lw.relevance_semantic
        a = inp.skill_coverage * lw.ability_skill + inp.graph_relatedness * lw.ability_graph
        relevances.append(r)
        raw_abilities.append(a)

    # Step 3: 候选集内归一化 ability
    abilities_norm = _normalize_within_batch(raw_abilities)

    # Step 4: 计算 final_score
    outputs = []
    for inp, rel, ab_norm in zip(inputs, relevances, abilities_norm):
        final_score = rel * (lw.relevance_base + lw.ability_multiplier * ab_norm)
        if inp.job_family_match < 0.5:
            final_score *= lw.family_discount
        final_score = max(0.0, min(1.0, final_score))

        breakdown = ScoreBreakdown(
            bm25_score=round(inp.bm25_score, 4),
            semantic_score=round(inp.semantic_score, 4),
            skill_coverage=round(inp.skill_coverage, 4),
            job_family_match=round(inp.job_family_match, 4),
            graph_relatedness=round(inp.graph_relatedness, 4),
        )

        explanation = generate_explanation(inp, final_score)

        outputs.append(FusionOutput(
            query_id=inp.query_id,
            job_id=inp.job_id,
            final_score=round(final_score, 4),
            rank=0,
            score_breakdown=breakdown,
            explanation=explanation,
            evidence_paths=inp.evidence_paths,
            meta=getattr(inp, '_meta', None),
        ))

    # Step 5: 排序 + 分配 rank
    outputs.sort(key=lambda o: o.final_score, reverse=True)
    for i, out in enumerate(outputs):
        out.rank = i + 1

    return outputs


# ── 解释生成 ────────────────────────────────────────────────────

def generate_explanation(inp: FusionInput, final_score: float, weights: FusionWeights = None) -> ExplanationDetail:
    """
    基于模板的中文解释生成（第三阶段 v2：分层逻辑）。

    返回 ExplanationDetail 对象。
    """
    lw = _current_layered_weights

    # 按分层逻辑分析
    relevance = inp.bm25_score * lw.relevance_bm25 + inp.semantic_score * lw.relevance_semantic
    parts = []

    # 1. 总体评价
    if final_score >= 0.80:
        parts.append("该岗位与您的简历高度匹配")
    elif final_score >= 0.60:
        parts.append("该岗位与您的简历匹配度良好")
    elif final_score >= 0.40:
        parts.append("该岗位与您的简历有一定匹配度")
    else:
        parts.append("该岗位与您的简历匹配度较低")

    # 2. 相关性分析
    if relevance >= 0.85:
        parts.append(f"相关性优秀（关键词 {inp.bm25_score:.0%}、语义 {inp.semantic_score:.0%}）")
    elif relevance >= 0.65:
        parts.append(f"相关性良好（关键词 {inp.bm25_score:.0%}、语义 {inp.semantic_score:.0%}）")
    else:
        parts.append(f"相关性一般（关键词 {inp.bm25_score:.0%}、语义 {inp.semantic_score:.0%}）")

    # 3. 技能适配
    if inp.skill_coverage >= 0.5:
        parts.append(f"技能覆盖良好（{inp.skill_coverage:.0%}），核心技能大多匹配")
    elif inp.skill_coverage >= 0.25:
        parts.append(f"技能覆盖一般（{inp.skill_coverage:.0%}），部分核心技能缺失")
    else:
        parts.append(f"技能覆盖较低（{inp.skill_coverage:.0%}），存在较大技能差距")

    # 4. 岗位族
    if inp.job_family_match < 0.5:
        parts.append("岗位族不完全一致，建议关注岗位要求的差异")

    # 5. 建议
    if inp.missing_skills:
        skills_text = "、".join(inp.missing_skills[:5])
        parts.append(f"建议补充 {skills_text} 等相关技能，可显著提升匹配度")

    # 构造 ExplanationDetail
    return ExplanationDetail(
        matched_skills=list(inp.matched_skills) if inp.matched_skills else [],
        missing_skills=list(inp.missing_skills) if inp.missing_skills else [],
        reason="。".join(parts) + "。",
    )


# ── Mock 数据生成（用于前端独立开发）────────────────────────────

# Mock 岗位标题池
_MOCK_JOB_TITLES = [
    "Senior Software Engineer",
    "Full Stack Developer",
    "Backend Engineer",
    "Frontend Developer",
    "DevOps Engineer",
    "Machine Learning Engineer",
    "Data Scientist",
    "Product Manager",
    "Software Architect",
    "Mobile Developer",
    "Cloud Engineer",
    "Security Engineer",
    "QA Engineer",
    "Technical Lead",
    "Engineering Manager",
    "Research Scientist",
    "Data Engineer",
    "Site Reliability Engineer",
    "Systems Engineer",
    "Embedded Software Engineer",
]

# Mock 技能池
_SKILL_POOL = [
    "Python", "JavaScript", "React", "Node.js", "AWS", "Docker",
    "Kubernetes", "TypeScript", "Java", "Go", "C++", "SQL",
    "MongoDB", "PostgreSQL", "TensorFlow", "PyTorch", "Machine Learning",
    "CI/CD", "Git", "REST APIs", "GraphQL", "Microservices",
    "System Design", "Agile", "Scrum", "Redis", "Kafka", "Spark",
]

# Mock 公司
_MOCK_COMPANIES = [
    "Google", "Microsoft", "Amazon", "Apple", "Meta", "Netflix",
    "Tesla", "Uber", "Airbnb", "Stripe", "Salesforce", "Adobe",
    "Oracle", "IBM", "Intel", "NVIDIA", "Spotify", "LinkedIn",
    "GitHub", "Shopify",
]


def generate_mock_inputs(
    query_id: str = "mock_resume_001",
    num_jobs: int = 20,
    seed: int = None,
) -> List[dict]:
    """
    生成 Mock 融合输入数据。
    返回原始 dict 列表（方便序列化），每条数据的分数分布模拟真实场景。
    """
    if seed is not None:
        random.seed(seed)

    mock_jobs = []
    for i in range(num_jobs):
        # 模拟不同匹配档位
        tier = random.choices(
            ["high", "medium", "low"], weights=[0.25, 0.50, 0.25], k=1
        )[0]

        if tier == "high":
            bm25 = round(random.uniform(0.70, 0.98), 2)
            semantic = round(random.uniform(0.72, 0.96), 2)
            skill_cov = round(random.uniform(0.65, 0.95), 2)
            job_family = 1.0 if random.random() < 0.7 else round(random.uniform(0.60, 0.95), 2)
            graph = round(random.uniform(0.65, 0.92), 2)
            missing_count = random.randint(0, 1)
        elif tier == "medium":
            bm25 = round(random.uniform(0.40, 0.75), 2)
            semantic = round(random.uniform(0.45, 0.78), 2)
            skill_cov = round(random.uniform(0.35, 0.70), 2)
            job_family = 1.0 if random.random() < 0.4 else round(random.uniform(0.30, 0.70), 2)
            graph = round(random.uniform(0.35, 0.72), 2)
            missing_count = random.randint(1, 3)
        else:
            bm25 = round(random.uniform(0.10, 0.50), 2)
            semantic = round(random.uniform(0.15, 0.48), 2)
            skill_cov = round(random.uniform(0.10, 0.40), 2)
            job_family = round(random.uniform(0.10, 0.55), 2)
            graph = round(random.uniform(0.10, 0.45), 2)
            missing_count = random.randint(2, 5)

        missing = random.sample(_SKILL_POOL, min(missing_count, len(_SKILL_POOL)))
        matched_count = random.randint(2, 8) if tier == "high" else random.randint(1, 4) if tier == "medium" else random.randint(0, 2)
        matched = random.sample(_SKILL_POOL, min(matched_count, len(_SKILL_POOL)))

        # 构造 evidence_paths（模拟 KG 路径）
        if graph > 0.5:
            evidence_paths = [
                f"skill:{random.choice(_SKILL_POOL)} → related_to → job:{random.choice(_SKILL_POOL)}"
                for _ in range(random.randint(1, 2))
            ]
        else:
            evidence_paths = []

        mock_jobs.append({
            "query_id": query_id,
            "job_id": f"mock_job_{i + 1:03d}",
            "bm25_score": bm25,
            "semantic_score": semantic,
            "skill_coverage": skill_cov,
            "job_family_match": job_family,
            "graph_relatedness": graph,
            "matched_skills": matched,
            "missing_skills": missing,
            "evidence_paths": evidence_paths,
            # 额外元数据（方便前端展示，非融合输入格式要求）
            "_meta": {
                "title": random.choice(_MOCK_JOB_TITLES),
                "company": random.choice(_MOCK_COMPANIES),
            },
        })

    return mock_jobs


def mock_rank(
    query_id: str = "mock_resume_001",
    num_jobs: int = 20,
    seed: int = None,
    weights: FusionWeights = None,
    layered_weights: LayeredWeights = None,
) -> List[FusionOutput]:
    """
    一键生成 Mock 数据并返回融合排序结果。
    供 /fusion/mock-rank 端点使用。
    """
    if layered_weights is not None:
        update_layered_weights(layered_weights)
    raw_jobs = generate_mock_inputs(query_id, num_jobs, seed)
    inputs = [FusionInput(**job) for job in raw_jobs]
    outputs = fuse_batch(inputs)
    return outputs
