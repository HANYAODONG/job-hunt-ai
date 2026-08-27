from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.config import settings


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


def _resolve_dataset_iteration_root() -> Path:
    candidates = [
        BACKEND_ROOT / "artifacts" / "dataset_iteration_05",
        PROJECT_ROOT / "artifacts" / "dataset_iteration_05",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


DATASET_ITERATION_ROOT = _resolve_dataset_iteration_root()


SKILL_CATEGORIES = {
    "backend": [
        "python", "java", "go", "golang", "c++", "spring", "django", "flask",
        "fastapi", "node", "microservice", "api", "redis", "mysql", "postgres",
    ],
    "frontend": [
        "javascript", "typescript", "react", "vue", "angular", "html", "css",
        "webpack", "next.js", "ui", "ux",
    ],
    "ai": [
        "llm", "rag", "agent", "machine learning", "deep learning", "nlp",
        "pytorch", "tensorflow", "transformer", "bge", "embedding", "大模型",
        "机器学习", "深度学习", "自然语言处理",
    ],
    "data": [
        "sql", "spark", "hadoop", "kafka", "etl", "warehouse", "bi",
        "tableau", "power bi", "数据仓库", "数据治理",
    ],
    "cloud_devops": [
        "aws", "azure", "gcp", "docker", "kubernetes", "k8s", "terraform",
        "ci/cd", "linux", "devops", "云原生",
    ],
    "security": [
        "security", "zero trust", "penetration", "soc", "siem", "iam",
        "安全", "攻防", "漏洞",
    ],
}


GENERIC_REQUIREMENT_PATTERNS = [
    r"strong communication",
    r"fast[- ]paced",
    r"self[- ]starter",
    r"team player",
    r"work under pressure",
    r"excellent verbal",
    r"良好的沟通",
    r"抗压",
    r"责任心",
    r"团队合作",
]


@dataclass
class JobQualityAudit:
    job_id: str
    title: str
    risk_level: str
    inflation_score: float
    noise_score: float
    evidence_risk: float
    confidence: float
    issues: list[str]
    evidence: list[str]
    suspected_inflated_skills: list[str]
    graph_policy: str
    local_summary: str
    llm_used: bool = False
    llm_summary: str | None = None
    llm_recommendation: str | None = None
    llm_warning: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "title": self.title,
            "risk_level": self.risk_level,
            "inflation_score": round(self.inflation_score, 4),
            "noise_score": round(self.noise_score, 4),
            "evidence_risk": round(self.evidence_risk, 4),
            "confidence": round(self.confidence, 4),
            "issues": self.issues,
            "evidence": self.evidence,
            "suspected_inflated_skills": self.suspected_inflated_skills,
            "graph_policy": self.graph_policy,
            "local_summary": self.local_summary,
            "llm_used": self.llm_used,
            "llm_summary": self.llm_summary,
            "llm_recommendation": self.llm_recommendation,
            "llm_warning": self.llm_warning,
        }


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = re.split(r"[,;/|，、\n]+", value)
    else:
        items = [value]
    return [str(item).strip() for item in items if str(item).strip()]


def _first_text(job: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = job.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _job_text(job: dict[str, Any]) -> str:
    fields = [
        _first_text(job, ["title", "job_title", "standard_job"]),
        _first_text(job, ["description", "job_description", "summary"]),
        _first_text(job, ["requirements", "requirement", "qualifications"]),
        _first_text(job, ["responsibilities", "responsibility"]),
        " ".join(_as_list(job.get("skills") or job.get("required_skills") or job.get("requiredSkills"))),
    ]
    return "\n".join(part for part in fields if part)


def _extract_skills(job: dict[str, Any]) -> list[str]:
    explicit = _as_list(job.get("skills") or job.get("required_skills") or job.get("requiredSkills"))
    text = _job_text(job).lower()
    inferred: list[str] = []
    for category_skills in SKILL_CATEGORIES.values():
        for skill in category_skills:
            if skill.lower() in text:
                inferred.append(skill)
    seen: set[str] = set()
    result: list[str] = []
    for skill in [*explicit, *inferred]:
        key = skill.casefold()
        if key not in seen:
            seen.add(key)
            result.append(skill)
    return result


def _skill_categories(skills: list[str]) -> list[str]:
    text = " ".join(skills).lower()
    categories = []
    for category, keywords in SKILL_CATEGORIES.items():
        if any(keyword.lower() in text for keyword in keywords):
            categories.append(category)
    return categories


def _seniority(title: str, text: str) -> str:
    value = f"{title} {text}".lower()
    if re.search(r"\b(intern|internship|实习)\b", value):
        return "intern"
    if re.search(r"\b(junior|entry|associate|初级|应届)\b", value):
        return "junior"
    if re.search(r"\b(senior|staff|principal|lead|architect|高级|资深|专家|负责人)\b", value):
        return "senior"
    return "mid"


def _max_required_years(text: str) -> int:
    years = [int(match) for match in re.findall(r"(\d{1,2})\s*(?:\+?\s*)?(?:years?|年)", text, flags=re.I)]
    return max(years or [0])


def _generic_noise_hits(text: str) -> list[str]:
    return [pattern for pattern in GENERIC_REQUIREMENT_PATTERNS if re.search(pattern, text, re.I)]


class JdQualityService:
    """Audits JD inflation and noisy requirements before skills enter the graph."""

    def load_sample_jobs(self, limit: int = 30) -> list[dict[str, Any]]:
        candidates = [
            DATASET_ITERATION_ROOT / "sample_pack" / "jobs_sample.jsonl",
            DATASET_ITERATION_ROOT / "jobs.jsonl",
        ]
        for path in candidates:
            if path.exists():
                jobs = []
                with path.open("r", encoding="utf-8-sig") as file:
                    for line in file:
                        if line.strip():
                            jobs.append(json.loads(line))
                        if len(jobs) >= limit:
                            break
                if jobs:
                    return jobs
        return self._fallback_jobs()[:limit]

    def audit_job(self, job: dict[str, Any], *, use_llm: bool = False) -> dict[str, Any]:
        audit = self._rule_audit(job)
        if use_llm:
            audit = self._attach_llm_judgement(job, audit)
        return audit.as_dict()

    def audit_batch(self, jobs: list[dict[str, Any]], *, use_llm: bool = False, llm_limit: int = 5) -> dict[str, Any]:
        items = []
        for index, job in enumerate(jobs):
            items.append(self.audit_job(job, use_llm=use_llm and index < llm_limit))
        return {
            "items": items,
            "summary": self.summarize(items, use_llm=use_llm),
        }

    def summarize(self, items: list[dict[str, Any]], *, use_llm: bool = False) -> dict[str, Any]:
        total = len(items)
        risk_counts = Counter(item["risk_level"] for item in items)
        avg_inflation = sum(item["inflation_score"] for item in items) / total if total else 0
        top_issues = Counter(issue for item in items for issue in item["issues"]).most_common(5)
        top_skills = Counter(skill for item in items for skill in item["suspected_inflated_skills"]).most_common(8)
        high_risk = [item for item in items if item["risk_level"] == "high"]
        local_summary = (
            f"本批次共审核 {total} 条 JD，高风险 {risk_counts.get('high', 0)} 条，"
            f"中风险 {risk_counts.get('medium', 0)} 条，平均通胀风险 {avg_inflation:.2f}。"
            "建议高风险 JD 暂缓直接写入能力图谱，先进入人工复核队列。"
        )
        summary = {
            "total": total,
            "risk_counts": dict(risk_counts),
            "average_inflation_score": round(avg_inflation, 4),
            "top_issues": [{"issue": issue, "count": count} for issue, count in top_issues],
            "top_suspected_skills": [{"skill": skill, "count": count} for skill, count in top_skills],
            "high_risk_examples": high_risk[:5],
            "overall_summary": local_summary,
            "llm_used": False,
            "llm_warning": None,
        }
        if use_llm:
            return self._attach_llm_summary(summary)
        return summary

    def _rule_audit(self, job: dict[str, Any]) -> JobQualityAudit:
        title = _first_text(job, ["title", "job_title", "standard_job"]) or "Untitled JD"
        job_id = _first_text(job, ["job_id", "id"]) or f"local-{abs(hash(title)) % 100000}"
        text = _job_text(job)
        skills = _extract_skills(job)
        categories = _skill_categories(skills)
        years = _max_required_years(text)
        seniority = _seniority(title, text)
        noise_hits = _generic_noise_hits(text)

        issues: list[str] = []
        evidence: list[str] = []
        inflation_points = 0.0
        noise_points = 0.0
        evidence_points = 0.0

        if len(skills) >= 14:
            inflation_points += 0.35
            issues.append("技能要求数量偏多，疑似岗位要求通胀")
            evidence.append(f"识别到 {len(skills)} 个技能要求")
        elif len(skills) >= 9:
            inflation_points += 0.2
            issues.append("技能栈较宽，需要核对是否为真实核心能力")
            evidence.append(f"识别到 {len(skills)} 个技能要求")

        if len(categories) >= 4:
            inflation_points += 0.25
            issues.append("跨技术域要求过多，可能混合了多个岗位职责")
            evidence.append(f"覆盖技术域：{', '.join(categories)}")

        if seniority in {"intern", "junior"} and years >= 3:
            inflation_points += 0.25
            issues.append("岗位级别与经验年限不匹配")
            evidence.append(f"{seniority} 岗位要求 {years}+ 年经验")

        if noise_hits:
            noise_points += min(0.35, 0.1 * len(noise_hits))
            issues.append("存在模板化软性要求，建议降低图谱权重")
            evidence.append(f"模板化表达命中 {len(noise_hits)} 项")

        if len(text) < 120:
            evidence_points += 0.3
            issues.append("JD 文本过短，技能抽取证据不足")
            evidence.append("岗位描述正文少于 120 字符")

        if len(skills) <= 2:
            evidence_points += 0.25
            issues.append("技能证据稀疏，建议先降低入图权重")
            evidence.append("显式/隐式技能数量不超过 2 个")

        if not issues:
            issues.append("未发现明显通胀或噪声风险")
            evidence.append("技能数量、岗位级别和描述长度均处于可接受范围")

        inflation_score = min(1.0, inflation_points)
        noise_score = min(1.0, noise_points)
        evidence_risk = min(1.0, evidence_points + inflation_score * 0.25)
        total_risk = max(inflation_score, noise_score, evidence_risk)
        risk_level = "high" if total_risk >= 0.55 else "medium" if total_risk >= 0.25 else "low"
        graph_policy = {
            "high": "hold_for_review",
            "medium": "downweight_and_trace",
            "low": "allow_with_trace",
        }[risk_level]
        confidence = 0.86 if text and skills else 0.62
        suspected = skills[:8] if risk_level != "low" else []
        local_summary = (
            f"{title} 的 JD 风险等级为 {risk_level}。"
            f"规则侧主要关注技能数量、跨域程度、岗位级别与经验要求是否一致。"
        )
        return JobQualityAudit(
            job_id=job_id,
            title=title,
            risk_level=risk_level,
            inflation_score=inflation_score,
            noise_score=noise_score,
            evidence_risk=evidence_risk,
            confidence=confidence,
            issues=issues,
            evidence=evidence,
            suspected_inflated_skills=suspected,
            graph_policy=graph_policy,
            local_summary=local_summary,
        )

    def _attach_llm_judgement(self, job: dict[str, Any], audit: JobQualityAudit) -> JobQualityAudit:
        api_key = os.getenv("DEEPSEEK_API_KEY") or settings.DEEPSEEK_API_KEY
        if not api_key:
            audit.llm_warning = "DEEPSEEK_API_KEY 未配置，当前为本地规则审核结果。"
            return audit
        payload = {
            "job": {
                "job_id": audit.job_id,
                "title": audit.title,
                "text": _job_text(job)[:2600],
                "skills": _extract_skills(job)[:40],
            },
            "rule_audit": audit.as_dict(),
            "task": "判断该 JD 是否存在岗位要求通胀、模板噪声或技能证据不足风险。",
        }
        try:
            data = self._call_deepseek_json(
                system_prompt=(
                    "你是岗位数据质量审核员。只能根据输入 JD 与规则审核结果判断，"
                    "不要凭空添加技能或证据。返回 JSON：summary, recommendation, adjusted_risk_level。"
                ),
                payload=payload,
                timeout=45,
            )
        except Exception as exc:  # pragma: no cover - network dependent
            audit.llm_warning = f"DeepSeek 审核失败，已保留规则结果：{exc}"
            return audit

        audit.llm_used = True
        audit.llm_summary = str(data.get("summary") or audit.local_summary)
        audit.llm_recommendation = str(data.get("recommendation") or audit.graph_policy)
        level = str(data.get("adjusted_risk_level") or "").lower()
        if level in {"low", "medium", "high"}:
            audit.risk_level = level
        return audit

    def _attach_llm_summary(self, summary: dict[str, Any]) -> dict[str, Any]:
        api_key = os.getenv("DEEPSEEK_API_KEY") or settings.DEEPSEEK_API_KEY
        if not api_key:
            return {**summary, "llm_warning": "DEEPSEEK_API_KEY 未配置，当前为规则汇总。"}
        try:
            data = self._call_deepseek_json(
                system_prompt=(
                    "你是项目答辩用的数据质量分析助手。根据统计结果输出简洁中文总结，"
                    "必须返回 JSON：overall_summary, risk_insights, recommended_actions。"
                ),
                payload={"summary": summary},
                timeout=45,
            )
        except Exception as exc:  # pragma: no cover - network dependent
            return {**summary, "llm_warning": f"DeepSeek 总结失败：{exc}"}
        return {
            **summary,
            "overall_summary": str(data.get("overall_summary") or summary["overall_summary"]),
            "risk_insights": _as_list(data.get("risk_insights"))[:5],
            "recommended_actions": _as_list(data.get("recommended_actions"))[:5],
            "llm_used": True,
            "llm_warning": None,
        }

    def _call_deepseek_json(self, *, system_prompt: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
        from job_update.company_job_update.skill_extract.extract_job_skills_api import call_chat_api

        api_key = os.getenv("DEEPSEEK_API_KEY") or settings.DEEPSEEK_API_KEY
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")
        return call_chat_api(
            api_key=api_key,
            model=settings.DEEPSEEK_MODEL,
            base_url=settings.DEEPSEEK_BASE_URL,
            system_prompt=system_prompt,
            user_payload=payload,
            timeout=timeout,
            retries=1,
            temperature=0.1,
        )

    @staticmethod
    def _fallback_jobs() -> list[dict[str, Any]]:
        return [
            {
                "job_id": "DEMO-JD-001",
                "title": "Junior Full Stack AI Engineer",
                "description": "Entry level role requiring Python, Java, React, Kubernetes, AWS, Spark, LLM, RAG, security, and 5 years experience. Strong communication and work under pressure.",
                "skills": ["Python", "Java", "React", "Kubernetes", "AWS", "Spark", "LLM", "RAG", "Security"],
            },
            {
                "job_id": "DEMO-JD-002",
                "title": "Backend Engineer",
                "description": "Build API services with Python, FastAPI, PostgreSQL and Redis. Maintain service quality and collaborate with product teams.",
                "skills": ["Python", "FastAPI", "PostgreSQL", "Redis"],
            },
        ]
