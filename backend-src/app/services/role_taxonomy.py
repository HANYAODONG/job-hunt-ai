"""Canonical three-level taxonomy for the standard-role graph."""

from __future__ import annotations

import re


# The source dataset supplies a standard category and standard role, but no
# intermediate direction. This mapping supplies that missing level without
# using a raw recruitment title as a taxonomy node.
DIRECTIONS_BY_CATEGORY: dict[str, dict[str, set[str]]] = {
    "软件研发": {
        "服务端与通用开发": {"软件开发工程师", "后端开发工程师", "Java开发工程师", "Python开发工程师", "Go开发工程师", "C++开发工程师", "服务器开发工程师", "应用软件工程师"},
        "数据与基础软件开发": {"数据开发工程师", "大数据开发工程师", "数据库开发工程师"},
        "前端与客户端": {"前端开发工程师", "客户端开发工程师", "Android开发工程师", "iOS开发工程师", "移动开发工程师", "全栈开发工程师"},
        "架构与系统软件": {"软件架构师", "系统软件工程师", "驱动开发工程师", "嵌入式软件工程师", "平台研发工程师", "基础架构研发工程师"},
    },
    "AI算法": {
        "基础算法与机器学习": {"算法工程师", "机器学习算法工程师", "算法研究员", "强化学习算法工程师"},
        "生成式与语言智能": {"大模型算法工程师", "AIGC算法工程师", "NLP算法工程师", "语音算法工程师"},
        "视觉与具身智能": {"多模态算法工程师", "计算机视觉算法工程师", "视觉算法工程师", "机器人算法工程师", "具身智能算法工程师"},
    },
    "算法": {
        "推荐、风控与搜索算法": {"推荐算法工程师", "广告算法工程师", "搜索算法工程师", "风控算法工程师", "数据挖掘算法工程师"},
        "控制、自动驾驶与优化": {"控制算法工程师", "自动驾驶算法工程师"},
        "视觉与具身智能": {"视觉算法工程师", "机器人算法工程师"},
    },
    "AI应用": {
        "大模型与智能体应用": {"大模型应用工程师", "Agent应用工程师"},
        "AI应用工程开发": {"AI应用工程师", "AI应用前端工程师", "AI应用后端工程师", "AI应用全栈工程师"},
    },
    "基础设施": {
        "平台、云与运维": {"AI Infra工程师", "云计算工程师", "云原生工程师", "SRE工程师", "运维工程师", "DevOps工程师"},
        "网络、计算与数据基础设施": {"网络工程师", "服务器工程师", "数据库工程师", "云数据库工程师", "高性能计算工程师"},
    },
    "测试质量": {
        "软件测试开发与质量": {"测试开发工程师", "测试工程师", "性能测试工程师", "质量工程师"},
        "硬件、芯片与安全测试": {"硬件测试工程师", "芯片测试工程师", "安全测试工程师", "自动驾驶测试工程师"},
        "AI模型测试与评测": {"大模型测试工程师", "模型评测工程师"},
    },
    "硬件": {
        "芯片与硬件工程": {"硬件工程师", "电子工程师", "结构工程师", "电源工程师", "热设计工程师", "芯片设计工程师", "芯片验证工程师", "芯片测试工程师"},
        "终端、通信与多媒体": {"机器人软件工程师", "图形图像工程师", "通信工程师", "音视频工程师"},
    },
    "芯片": {
        "芯片与硬件工程": {"硬件工程师", "结构工程师", "电源工程师", "热设计工程师", "芯片设计工程师", "芯片验证工程师", "芯片测试工程师"},
    },
    "数据": {
        "数据分析": {
            "数据分析师", "数据科学家", "商业分析师", "策略与业务分析师",
            "BI分析师", "统计分析师", "数据产品分析师",
        },
        "数据工程与治理": {"数据开发工程师", "数据工程师", "数据仓库工程师", "数据平台工程师", "大数据开发工程师", "数据治理工程师"},
    },
    "安全": {
        "网络与信息安全": {"网络安全工程师", "信息安全工程师", "安全工程师", "数据安全工程师", "隐私安全工程师", "安全运营工程师", "渗透测试工程师"},
        "AI与模型安全": {"AI安全工程师", "AI模型安全工程师"},
    },
    "AI基础设施": {
        "平台、云与运维": {"AI Infra工程师", "云计算工程师", "运维工程师", "DevOps工程师"},
        "大模型算力与系统": {"大模型训练系统工程师", "大模型推理系统工程师", "大模型推理优化工程师", "大模型平台工程师", "异构计算工程师"},
    },
    "AI安全": {
        "网络与信息安全": {"网络安全工程师", "信息安全工程师", "安全工程师", "数据安全工程师", "隐私安全工程师", "安全运营工程师", "渗透测试工程师"},
        "AI与模型安全": {"AI安全工程师", "AI模型安全工程师", "AI安全研究员"},
    },
    "技术支持": {
        "技术支持与交付": {"技术支持工程师", "技术交付工程师"},
        "解决方案与售前": {"解决方案工程师", "售前技术工程师"},
    },
    "通信": {"终端、通信与多媒体": {"机器人软件工程师", "图形图像工程师", "通信工程师", "音视频工程师"}},
    "产品": {
        "智能与数据产品": {"AI产品经理", "数据产品经理"},
        "业务产品与运营": {"业务产品经理", "策略产品经理", "产品运营经理"},
    },
    "多媒体": {"终端、通信与多媒体": {"机器人软件工程师", "图形图像工程师", "通信工程师", "音视频工程师"}},
    "机器人": {"终端、通信与多媒体": {"机器人软件工程师", "图形图像工程师", "通信工程师", "音视频工程师"}, "机器人智能": {"机器人算法工程师"}},
    "自动驾驶": {"控制、自动驾驶与优化": {"控制算法工程师", "自动驾驶算法工程师"}},
}

GOVERNMENT_TECH_TAXONOMY = (
    ("cybersecurity_cryptography", "政务安全、通信与空间信息", "政务信息安全技术岗"),
    ("data_ai", "政务数据与软件", "政务数据智能技术岗"),
    ("electronics_communication", "政务安全、通信与空间信息", "政务电子通信技术岗"),
    ("geospatial_remote_sensing", "政务安全、通信与空间信息", "政务空间信息技术岗"),
    ("computer_software", "政务数据与软件", "政务软件信息化技术岗"),
)

GOVERNMENT_ROLES_BY_DIRECTION = {
    "政务数据与软件": {"政务数据智能技术岗", "政务软件信息化技术岗"},
    "政务安全、通信与空间信息": {
        "政务信息安全技术岗", "政务电子通信技术岗", "政务空间信息技术岗",
    },
}

CANONICAL_DOMAIN_BY_CATEGORY = {
    "软件研发": "软件研发",
    "AI算法": "算法与智能",
    "算法": "算法与智能",
    "机器人": "智能硬件与终端",
    "自动驾驶": "智能硬件与终端",
    "AI应用": "AI应用",
    "基础设施": "基础设施",
    "AI基础设施": "基础设施",
    "数据": "数据智能",
    "测试质量": "测试质量",
    "硬件": "智能硬件与终端",
    "芯片": "智能硬件与终端",
    "通信": "智能硬件与终端",
    "多媒体": "智能硬件与终端",
    "安全": "安全",
    "AI安全": "安全",
    "产品": "产品与技术服务",
    "技术支持": "产品与技术服务",
    "政务技术岗位": "政务技术",
}

# Refined roles can originate from a source category whose label was too broad.
# These overrides keep an evidence-derived role in the right canonical domain.
ROLE_CATEGORY_OVERRIDES = {
    "AI产品经理": "产品",
    "数据产品经理": "产品",
    "业务产品经理": "产品",
    "产品运营经理": "产品",
}

ALGORITHM_DIRECTIONS = {
    "算法工程师": "机器学习与算法研究",
    "机器学习算法工程师": "机器学习与算法研究",
    "算法研究员": "机器学习与算法研究",
    "强化学习算法工程师": "机器学习与算法研究",
    "大模型算法工程师": "生成式与语言智能",
    "AIGC算法工程师": "生成式与语言智能",
    "NLP算法工程师": "生成式与语言智能",
    "多模态算法工程师": "视觉与具身智能",
    "计算机视觉算法工程师": "视觉与具身智能",
    "语音算法工程师": "生成式与语言智能",
    "推荐算法工程师": "推荐、风控与搜索算法",
    "广告算法工程师": "推荐、风控与搜索算法",
    "搜索算法工程师": "推荐、风控与搜索算法",
    "风控算法工程师": "推荐、风控与搜索算法",
    "数据挖掘算法工程师": "推荐、风控与搜索算法",
    "控制算法工程师": "控制、自动驾驶与优化",
    "机器人算法工程师": "视觉与具身智能",
    "具身智能算法工程师": "视觉与具身智能",
    "自动驾驶算法工程师": "控制、自动驾驶与优化",
}


def refine_standard_role(category: str, role: str, *, title: str = "", skills: object = None, description: str = "") -> str:
    """Refine an over-broad source label only when the JD contains direct evidence."""
    title_evidence = str(title or "").casefold()
    skill_evidence = " ".join(str(item) for item in skills or []).casefold()

    if category == "AI应用" and role in {"AI应用工程师", "大模型应用工程师"}:
        # Keep product postings in the product domain when the source label was broad.
        if any(token in title_evidence for token in ("产品经理", "产品负责人", "产品规划", "产品专家")):
            return "AI产品经理"
        if "前端" in title_evidence:
            return "AI应用前端工程师"
        if any(token in title_evidence for token in ("全栈", "full stack", "full-stack")):
            return "AI应用全栈工程师"
        if any(token in title_evidence for token in ("后端", "服务端", "server", "backend")):
            return "AI应用后端工程师"
        if any(token in title_evidence for token in ("agent", "智能体")):
            return "Agent应用工程师"
        return "大模型应用工程师" if role == "大模型应用工程师" else role

    if category in {"软件研发", "AI基础设施"}:
        if role == "软件开发工程师":
            if any(token in title_evidence for token in ("大数据开发", "数据开发", "数据研发")):
                return "大数据开发工程师" if "大数据" in title_evidence else "数据开发工程师"
            if "服务器开发" in title_evidence:
                return "服务器开发工程师"
            if "应用软件" in title_evidence:
                return "应用软件工程师"
            if "基础架构" in title_evidence and "研发" in title_evidence:
                return "基础架构研发工程师"
            if "平台研发" in title_evidence:
                return "平台研发工程师"
        if role == "AI Infra工程师":
            if any(token in title_evidence for token in ("训练系统", "训练调度", "训练优化")):
                return "大模型训练系统工程师"
            if any(token in title_evidence for token in ("推理系统", "推理框架", "推理服务")):
                return "大模型推理系统工程师"
            if "推理优化" in title_evidence:
                return "大模型推理优化工程师"
            if any(token in title_evidence for token in ("异构计算", "异构硬件", "算力优化")):
                return "异构计算工程师"
            if "平台研发" in title_evidence or "训练平台" in title_evidence:
                return "大模型平台工程师"

    if category in {"AI算法", "算法"} and role in {"算法工程师", "算法研究员"}:
        if "强化学习" in title_evidence:
            return "强化学习算法工程师"
        if "具身智能" in title_evidence:
            return "具身智能算法工程师"
        if any(token in title_evidence for token in ("推荐算法", "推荐策略")):
            return "推荐算法工程师"
        if any(token in title_evidence for token in ("搜索算法", "搜索策略")):
            return "搜索算法工程师"
        if "广告算法" in title_evidence:
            return "广告算法工程师"
        if "风控算法" in title_evidence:
            return "风控算法工程师"
        if any(token in title_evidence for token in ("计算机视觉", "视觉算法")):
            return "视觉算法工程师"
        if "机器人算法" in title_evidence:
            return "机器人算法工程师"
        if "自动驾驶算法" in title_evidence:
            return "自动驾驶算法工程师"
        if "控制算法" in title_evidence:
            return "控制算法工程师"
        if any(token in title_evidence for token in ("大模型算法", "大语言模型算法")):
            return "大模型算法工程师"
        if "NLP算法" in title_evidence:
            return "NLP算法工程师"
        if "语音算法" in title_evidence:
            return "语音算法工程师"

    if category == "基础设施":
        if role == "云计算工程师" and "云原生" in title_evidence:
            return "云原生工程师"
        if role == "云计算工程师" and re.search(r"\bsre\b", title_evidence, re.I):
            return "SRE工程师"
        if role == "云计算工程师" and "云数据库" in title_evidence:
            return "云数据库工程师"
        if role == "云计算工程师" and "高性能计算" in title_evidence:
            return "高性能计算工程师"

    if category == "硬件" and role == "硬件工程师" and "电子工程师" in title_evidence:
        return "电子工程师"

    if category == "测试质量":
        if role in {"测试工程师", "测试开发工程师"}:
            if any(token in title_evidence for token in ("渗透测试", "安全测试")):
                return "安全测试工程师"
            if "芯片测试" in title_evidence:
                return "芯片测试工程师"
            if "硬件测试" in title_evidence:
                return "硬件测试工程师"
            if "自动驾驶" in title_evidence and "测试" in title_evidence:
                return "自动驾驶测试工程师"
            if "性能测试" in title_evidence:
                return "性能测试工程师"

    if category in {"安全", "AI安全"} and role in {"信息安全工程师", "安全工程师", "AI安全工程师"}:
        if category == "AI安全" and ("安全研究" in title_evidence or "安全攻防" in title_evidence):
            return "AI安全研究员"
        if "数据安全" in title_evidence:
            return "数据安全工程师"
        if any(token in title_evidence for token in ("隐私安全", "隐私保护", "隐私合规")):
            return "隐私安全工程师"
        if "安全运营" in title_evidence:
            return "安全运营工程师"
        if any(token in title_evidence for token in ("渗透测试", "安全攻防")):
            return "渗透测试工程师"

    if category == "测试质量":
        if any(token in title_evidence for token in ("评测", "评估", "测评")) and any(
            token in title_evidence for token in ("模型", "大模型", "agent", "算法", "ai")
        ):
            return "模型评测工程师"
        if role == "大模型测试工程师":
            return "大模型测试工程师"

    if category == "AI安全" and role == "AI安全工程师":
        if any(token in title_evidence for token in ("大模型", "模型安全", "llm")):
            return "AI模型安全工程师"
        return role

    if category == "产品" and role == "AI产品经理":
        if "数据产品" in title_evidence or "数据产品" in skill_evidence:
            return "数据产品经理"
        if any(token in title_evidence for token in ("运营", "增长")):
            return "产品运营经理"
        if "策略产品" in title_evidence:
            return "策略产品经理"
        if any(token in title_evidence for token in ("ai", "人工智能", "智能", "大模型", "机器人")):
            return "AI产品经理"
        if any(token in title_evidence for token in ("产品经理", "产品负责人", "产品总监", "产品专家", "商品经理", "商品方案")):
            return "业务产品经理"

    if category == "技术支持":
        if role == "技术支持工程师" and any(
            token in title_evidence for token in ("交付", "部署", "现场", "forward deployed", "fde")
        ):
            return "技术交付工程师"
        if role == "解决方案工程师" and any(token in title_evidence for token in ("售前", "pre-sales", "presales")):
            return "售前技术工程师"

    if category != "数据" or role != "数据分析师":
        return role

    if any(token in title_evidence for token in ("数据科学家", "数据科学", "data scientist")):
        return "数据科学家"
    if any(token in title_evidence for token in ("商业分析", "商业数据分析", "商分", "business analyst")):
        return "商业分析师"
    if any(token in title_evidence for token in ("策略分析", "经营分析", "业务分析", "策略与业务")):
        return "策略与业务分析师"
    if any(token in title_evidence for token in ("bi分析", "bi analyst", "报表分析", "数据看板", "可视化看板")):
        return "BI分析师"
    if "统计分析" in title_evidence:
        return "统计分析师"
    if any(token in title_evidence for token in ("数据产品分析", "数据分析产品", "数据产品与分析")):
        return "数据产品分析师"
    # Generic titles are refined only when the skills form a strong role signature.
    if {"因果推断", "实验设计"}.issubset(skill_evidence.split()) and any(
        token in skill_evidence for token in ("机器学习", "数理统计", "统计检验")
    ):
        return "数据科学家"
    if "power bi" in skill_evidence and any(token in skill_evidence for token in ("报表", "数据看板", "可视化")):
        return "BI分析师"
    return role


def get_role_direction(category: str, role: str) -> str:
    """Return the curated intermediate direction for a canonical role."""
    for direction, roles in DIRECTIONS_BY_CATEGORY.get(category, {}).items():
        if role in roles:
            return direction
    for direction, roles in GOVERNMENT_ROLES_BY_DIRECTION.items():
        if role in roles:
            return direction
    return "其他标准岗位"


def get_canonical_taxonomy(category: str, role: str) -> tuple[str, str]:
    """Return a real-world domain/direction while retaining only known roles."""
    if role in ALGORITHM_DIRECTIONS:
        return "算法与智能", ALGORITHM_DIRECTIONS[role]
    category = ROLE_CATEGORY_OVERRIDES.get(role, category)
    return CANONICAL_DOMAIN_BY_CATEGORY.get(category, category or "其他技术岗位"), get_role_direction(category, role)


def get_standard_role_taxonomy(role: str) -> tuple[str, str] | None:
    """Find the category and direction already defined for a standard role."""
    for category, directions in DIRECTIONS_BY_CATEGORY.items():
        for direction, roles in directions.items():
            if role in roles:
                return category, direction
    return None


def infer_government_tech_role(tech_categories: object) -> tuple[str, str, str]:
    """Classify an unmatched government technical post from its source tags."""
    categories = {str(item).strip() for item in tech_categories or []}
    for source_category, direction, role in GOVERNMENT_TECH_TAXONOMY:
        if source_category in categories:
            return "政务技术岗位", direction, role
    return "政务技术岗位", "待补充技术方向", "政务信息化技术岗"
