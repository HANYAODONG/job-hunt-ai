"""
Fusion Scoring Models — 工作流4：融合排序输入/输出模型

完全独立于现有 reranking 模型，遵循组长指定的字段格式。
最终接入工作流2（BM25 + semantic）和工作流3（skill_coverage + job_family + graph）的结果。
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict


# ── 单个岗位的融合输入 ──────────────────────────────────────────

class FusionInput(BaseModel):
    """组长指定的统一融合输入格式（单条 job）"""
    model_config = {"extra": "allow"}  # 允许 _meta 等辅助字段

    query_id: str = Field(..., description="查询/简历 ID")
    job_id: str = Field(..., description="岗位 ID")
    bm25_score: float = Field(default=0.0, ge=0.0, le=1.0, description="工作流2：BM25 关键词得分")
    semantic_score: float = Field(default=0.0, ge=0.0, le=1.0, description="工作流2：语义向量相似度")
    skill_coverage: float = Field(default=0.0, ge=0.0, le=1.0, description="工作流3：技能覆盖率")
    job_family_match: float = Field(default=0.0, ge=0.0, le=1.0, description="工作流3：岗位大类匹配")
    graph_relatedness: float = Field(default=0.0, ge=0.0, le=1.0, description="工作流3：知识图谱关联度")
    missing_skills: List[str] = Field(default_factory=list, description="缺失技能列表")
    evidence_paths: List[str] = Field(default_factory=list, description="KG 证据路径")


# ── 单个岗位的融合输出 ──────────────────────────────────────────

class ScoreBreakdown(BaseModel):
    """各因子得分明细"""
    bm25: float = Field(..., ge=0.0, le=1.0)
    semantic: float = Field(..., ge=0.0, le=1.0)
    skill_coverage: float = Field(..., ge=0.0, le=1.0)
    job_family: float = Field(..., ge=0.0, le=1.0)
    graph: float = Field(..., ge=0.0, le=1.0)


class FusionOutput(BaseModel):
    """组长指定的融合输出格式（单条 job）"""
    model_config = {"extra": "allow"}

    query_id: str
    job_id: str
    final_score: float = Field(..., ge=0.0, le=1.0, description="加权融合最终得分")
    rank: int = Field(default=1, ge=0, description="在当前 query 下的排名（0 表示未排序）")
    score_breakdown: ScoreBreakdown
    explanation: str = Field(..., description="推荐解释文本（中文）")
    # 以下为辅助字段（非组长要求，用于前端展示增强）
    missing_skills: List[str] = Field(default_factory=list, description="缺失技能")
    evidence_paths: List[str] = Field(default_factory=list, description="KG证据路径")
    meta: Optional[dict] = Field(default=None, description="前端展示用元数据（岗位名/公司名等）")


# ── 批量输入/输出 ────────────────────────────────────────────────

class FusionBatchInput(BaseModel):
    """批量融合请求"""
    query_id: str = Field(..., description="查询/简历 ID")
    jobs: List[FusionInput] = Field(..., min_length=1, description="待融合的岗位列表")


class FusionBatchOutput(BaseModel):
    """批量融合响应"""
    query_id: str
    results: List[FusionOutput] = Field(..., description="按 final_score 降序排列的结果")
    weights_used: Dict[str, float] = Field(..., description="本次使用的融合权重")


# ── 权重配置 ────────────────────────────────────────────────────

class FusionWeights(BaseModel):
    """融合权重配置"""
    bm25: float = Field(default=0.15, ge=0.0, le=1.0)
    semantic: float = Field(default=0.25, ge=0.0, le=1.0)
    skill_coverage: float = Field(default=0.30, ge=0.0, le=1.0)
    job_family: float = Field(default=0.15, ge=0.0, le=1.0)
    graph: float = Field(default=0.15, ge=0.0, le=1.0)

    def validate_sum(self):
        total = self.bm25 + self.semantic + self.skill_coverage + self.job_family + self.graph
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"权重之和必须为 1.0，当前为 {total:.4f}")


# ── Mock 数据生成请求 ────────────────────────────────────────────

class MockRankRequest(BaseModel):
    """Mock 融合请求：不需要真实输入，由服务端自动生成数据"""
    query_id: str = Field(default="mock_resume_001", description="模拟的简历 ID")
    num_jobs: int = Field(default=20, ge=1, le=100, description="生成的 mock 岗位数量")
    seed: Optional[int] = Field(default=None, description="随机种子（可选，用于复现结果）")
    weights: Optional[FusionWeights] = Field(default=None, description="自定义融合权重（不传则用服务端默认值）")
