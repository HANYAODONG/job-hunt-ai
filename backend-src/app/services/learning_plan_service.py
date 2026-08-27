"""Learning Plan Service — 工作流：求职者端学习路径生成

将诊断产出的能力缺口（missing_skills）转化为有前置关系、可交付、可复诊的学习阶段。

最小输出契约（对应分工5 §7.3）：
    target_role
    missing_skills
    priority
    learning_stage
    suggestion
    resources

本模块为纯函数实现，无数据库/模型依赖，可离线运行与单测。
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 优先级排序（high -> medium -> low）
PRIORITY_ORDER: Dict[str, int] = {"high": 0, "medium": 1, "low": 2}
PRIORITY_LABELS: Dict[str, str] = {"high": "高", "medium": "中", "low": "低"}


# ── 常用 AI/数据岗位技能的建议库（无 LLM 时的确定性回退）────────────
# 键为技能名（可模糊匹配），值为建议与资源。用于在缺少外部资源时仍能产出可用路径。

_SKILL_SUGGESTION_LIBRARY: Dict[str, Dict[str, Any]] = {
    "agent": {
        "title": "Agent 工作流专项实践",
        "suggestion": "先完成一个可解释的 Agent 工作流：实现工具调用、记忆与失败回退，并保留一次完整运行记录作为项目证据。",
        "resources": [
            "LangChain / AutoGen 官方文档（工具调用与记忆章节）",
            "《Building Agents》实践手册",
            "开源项目：轻量 Agent 框架源码阅读",
        ],
    },
    "rag": {
        "title": "RAG 质量评测专项实践",
        "suggestion": "从 30 条真实问答开始建立可复现的 RAG 质量评测：分别记录检索召回、答案忠实度和业务结果。",
        "resources": [
            "RAGAS 评测框架文档",
            "《Retrieval-Augmented Generation》论文",
            "LangChain 检索评测教程",
        ],
    },
    "评测": {
        "title": "模型评测专项实践",
        "suggestion": "建立可复现的 RAG 质量评测，从 30 条真实问答开始记录检索召回、答案忠实度和业务结果。",
        "resources": [
            "RAGAS / TruLens 评测框架",
            "《Evaluating RAG》行业实践",
        ],
    },
    "可观测": {
        "title": "生产化与可观测性实践",
        "suggestion": "为工作流补充链路追踪、成本记录和用户反馈闭环，让项目从演示原型走向可诊断系统。",
        "resources": [
            "OpenTelemetry 官方文档",
            "LangSmith / Phoenix 观测平台",
        ],
    },
    "prompt": {
        "title": "Prompt 工程与调优实践",
        "suggestion": "围绕提示词设计、少样本示例与效果评估形成可复用的 Prompt 资产与评测集。",
        "resources": [
            "OpenAI Prompt Engineering Guide",
            "LangSmith 提示词实验记录",
        ],
    },
    "向量": {
        "title": "向量检索与召回排序实践",
        "suggestion": "实现向量化、ANN 召回与重排，对比不同嵌入模型和索引参数对 Recall/MRR 的影响。",
        "resources": [
            "FAISS / Milvus 官方文档",
            "HNSW 论文与调参实践",
        ],
    },
    "python": {
        "title": "Python 工程化实践",
        "suggestion": "围绕 FastAPI/数据处理链路完成一个可测试、可复现的 Python 服务，并补齐类型标注与测试。",
        "resources": [
            "FastAPI 官方教程",
            "pytest 测试实践",
        ],
    },
    "sql": {
        "title": "SQL 与数据建模实践",
        "suggestion": "完成数据建模、指标口径设计与复杂查询实践，沉淀可复用查询模板。",
        "resources": [
            "《SQL 必知必会》",
            "LeetCode SQL 题库",
        ],
    },
}


def _match_suggestion(skill: str) -> Dict[str, Any]:
    """按技能名模糊匹配建议库，未命中时返回通用模板。"""
    key = str(skill or "").strip().casefold()
    if not key:
        return {
            "title": "能力提升实践",
            "suggestion": "围绕该能力完成一个可运行、可评测、可复盘的专项实践。",
            "resources": ["官方文档", "权威教程 / 书籍", "开源项目源码"],
        }

    # 精确命中
    if key in _SKILL_SUGGESTION_LIBRARY:
        return _SKILL_SUGGESTION_LIBRARY[key]

    # 包含匹配（技能名包含库键）
    for lib_key, payload in _SKILL_SUGGESTION_LIBRARY.items():
        if lib_key in key or key in lib_key:
            return payload

    # 中文字段回退
    return {
        "title": f"{skill}专项实践",
        "suggestion": f"围绕{skill}完成一个可运行、可评测、可复盘的专项实践，并记录任务目标、实现过程、评测结果与复盘说明。",
        "resources": ["官方文档", "权威教程 / 书籍", "开源项目源码"],
    }


def _normalize_missing_skill(skill: Any) -> Optional[Dict[str, Any]]:
    """将输入归一化为 {skill, priority, reason}。"""
    if isinstance(skill, str):
        return {"skill": skill.strip(), "priority": "high", "reason": ""} if skill.strip() else None

    if isinstance(skill, dict):
        name = str(skill.get("skill") or skill.get("name") or "").strip()
        if not name:
            return None
        priority = str(skill.get("priority") or "high").strip().lower()
        if priority not in PRIORITY_ORDER:
            priority = "high"
        return {
            "skill": name,
            "priority": priority,
            "reason": str(skill.get("reason") or skill.get("gap_reason") or ""),
        }

    name = str(skill).strip()
    return {"skill": name, "priority": "high", "reason": ""} if name else None


def _sort_missing_skills(skills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """按优先级排序，同优先级保持原序。"""
    return sorted(skills, key=lambda item: PRIORITY_ORDER.get(item["priority"], 9))


def build_learning_plan(
    target_role: str,
    missing_skills: List[Any],
    candidate_name: Optional[str] = None,
    target_version: Optional[str] = None,
    match_score: Optional[float] = None,
    max_stages: int = 5,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """由能力缺口构建学习计划。

    返回结构同时满足：
    1. 分工5 §7.3 的最小输出字段（target_role / missing_skills / priority /
       learning_stage / suggestion / resources）；
    2. 前端 `/learning` 页面可直接消费的 stages 结构。
    """
    normalized = [item for item in (_normalize_missing_skill(s) for s in missing_skills) if item]
    ordered = _sort_missing_skills(normalized)[:max_stages]

    stages: List[Dict[str, Any]] = []
    for index, gap in enumerate(ordered):
        suggestion = _match_suggestion(gap["skill"])
        # 新生成的计划：首个阶段标记为“进行中”，其余为“未开始”
        status = "进行中" if index == 0 else "未开始"
        stages.append(
            {
                "id": f"stage-{index + 1}",
                "phase": f"阶段 {index + 1}",
                "learning_stage": f"阶段 {index + 1}",
                "title": suggestion["title"],
                "skill": gap["skill"],
                "priority": gap["priority"],
                "duration": "1 周",
                "status": status,
                "goal": suggestion["suggestion"],
                "suggestion": suggestion["suggestion"],
                "tasks": [
                    f"梳理{gap['skill']}的岗位要求",
                    f"完成{gap['skill']}最小实践",
                    "记录评测结果与改进说明",
                ],
                "outcome": f"{gap['skill']}实践项目与复盘说明",
                "resources": suggestion["resources"],
            }
        )

    progress = round((1 / max(len(stages), 1)) * 100) if stages else 0
    current_stage = next(
        (stage["learning_stage"] for stage in stages if stage["status"] == "进行中"),
        (stages[0]["learning_stage"] if stages else "未开始"),
    )

    return {
        "target_role": target_role,
        "missing_skills": [
            {"skill": gap["skill"], "priority": gap["priority"], "reason": gap["reason"]}
            for gap in ordered
        ],
        "stages": stages,
        "resources": sorted(
            {resource for stage in stages for resource in stage["resources"]}
        ),
        "profile": candidate_name or "求职者",
        "target_version": target_version or "当前 JD",
        "match_score": match_score,
        "progress": progress,
        "current_stage": current_stage,
        "gap_count": len(stages),
        "updated_at": (now or datetime.now()).strftime("%Y-%m-%d %H:%M"),
    }
