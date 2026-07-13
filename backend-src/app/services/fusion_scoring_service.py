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
    FusionWeights,
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

# 运行时权重（可通过 API 修改）
_current_weights: FusionWeights = DEFAULT_WEIGHTS


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
    """获取当前融合权重"""
    return _current_weights


def update_weights(weights: FusionWeights) -> FusionWeights:
    """更新融合权重"""
    global _current_weights
    weights.validate_sum()
    _current_weights = weights
    logger.info(f"Fusion weights updated: {weights.model_dump()}")
    return _current_weights


def reset_weights() -> FusionWeights:
    """恢复默认权重"""
    global _current_weights
    _current_weights = DEFAULT_WEIGHTS
    return _current_weights


# ── 核心融合函数 ────────────────────────────────────────────────

def compute_final_score(inp: FusionInput, weights: FusionWeights = None) -> float:
    """
    加权线性融合
    final_score = Σ(factor_i × weight_i)
    """
    w = weights or _current_weights
    return (
        inp.bm25_score * w.bm25
        + inp.semantic_score * w.semantic
        + inp.skill_coverage * w.skill_coverage
        + inp.job_family_match * w.job_family
        + inp.graph_relatedness * w.graph
    )


def fuse_single(inp: FusionInput, weights: FusionWeights = None) -> FusionOutput:
    """
    单条融合：计算 final_score + score_breakdown + explanation
    """
    w = weights or _current_weights
    final_score = compute_final_score(inp, w)

    breakdown = ScoreBreakdown(
        bm25=round(inp.bm25_score, 4),
        semantic=round(inp.semantic_score, 4),
        skill_coverage=round(inp.skill_coverage, 4),
        job_family=round(inp.job_family_match, 4),
        graph=round(inp.graph_relatedness, 4),
    )

    explanation = generate_explanation(inp, final_score, w)

    return FusionOutput(
        query_id=inp.query_id,
        job_id=inp.job_id,
        final_score=round(final_score, 4),
        rank=0,  # 由 fuse_batch 统一设置
        score_breakdown=breakdown,
        explanation=explanation,
        missing_skills=inp.missing_skills,
        evidence_paths=inp.evidence_paths,
        meta=getattr(inp, '_meta', None),
    )


def fuse_batch(inputs: List[FusionInput], weights: FusionWeights = None) -> List[FusionOutput]:
    """
    批量融合：对每一条计算得分 → 按 final_score 降序排列 → 分配 rank
    """
    w = weights or _current_weights
    outputs = [fuse_single(inp, w) for inp in inputs]
    outputs.sort(key=lambda o: o.final_score, reverse=True)
    for i, out in enumerate(outputs):
        out.rank = i + 1
    return outputs


# ── 解释生成 ────────────────────────────────────────────────────

def generate_explanation(inp: FusionInput, final_score: float, weights: FusionWeights = None) -> str:
    """
    基于模板的中文解释生成。
    不依赖 LLM API，纯规则驱动。后续接入真实 LLM 时替换此函数即可。

    模板结构：
    1. 总体评价
    2. 强项（高于 0.7 的维度）
    3. 弱项（低于 0.4 的维度）
    4. 缺失技能
    5. 建议
    """
    w = weights or _current_weights

    # 各维度得分
    factor_scores = {
        "关键词匹配": (inp.bm25_score, w.bm25),
        "语义相似度": (inp.semantic_score, w.semantic),
        "技能覆盖": (inp.skill_coverage, w.skill_coverage),
        "岗位大类匹配": (inp.job_family_match, w.job_family),
        "知识图谱关联": (inp.graph_relatedness, w.graph),
    }

    strengths = [(name, score) for name, (score, _) in factor_scores.items() if score >= 0.7]
    weaknesses = [(name, score) for name, (score, _) in factor_scores.items() if score < 0.4]
    # 找出贡献最大的因子
    top_factor = max(factor_scores.items(), key=lambda x: x[1][0] * x[1][1])

    parts = []

    # 1. 总体评价
    if final_score >= 0.75:
        parts.append("该岗位与您的简历整体匹配度很高")
    elif final_score >= 0.55:
        parts.append("该岗位与您的简历匹配度良好")
    elif final_score >= 0.35:
        parts.append("该岗位与您的简历有一定匹配度")
    else:
        parts.append("该岗位与您的简历匹配度较低")

    # 2. 强项
    if strengths:
        strength_text = "、".join([f"{name}（{score:.0%}）" for name, score in strengths])
        parts.append(f"✅ 强项：{strength_text}")
    else:
        parts.append("✅ 各维度均无特别突出的优势项")

    # 3. 弱项
    if weaknesses:
        weak_text = "、".join([f"{name}（{score:.0%}）" for name, score in weaknesses])
        parts.append(f"⚠️ 弱项：{weak_text}")
    else:
        parts.append("⚠️ 无明显弱项")

    # 4. 缺失技能
    if inp.missing_skills:
        skills_text = "、".join(inp.missing_skills)
        parts.append(f"🔍 缺失技能：{skills_text}")
    else:
        parts.append("🔍 未发现明显技能缺口")

    # 5. 建议
    if inp.missing_skills:
        skills_text = "、".join(inp.missing_skills)
        parts.append(f"💡 建议：建议补充 {skills_text} 等相关技能，可显著提升匹配度")
    elif final_score < 0.5:
        parts.append(f"💡 建议：{top_factor[0]}方面有一定差距，可以考虑拓展相关经验")
    else:
        parts.append("💡 该岗位是您的良好选择，建议尽快投递")

    return "。".join(parts) + "。"


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
) -> List[FusionOutput]:
    """
    一键生成 Mock 数据并返回融合排序结果。
    供 /fusion/mock-rank 端点使用。
    """
    raw_jobs = generate_mock_inputs(query_id, num_jobs, seed)
    inputs = [FusionInput(**job) for job in raw_jobs]
    outputs = fuse_batch(inputs, weights)
    return outputs
