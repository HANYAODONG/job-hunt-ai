from __future__ import annotations

import csv
import tempfile
from pathlib import Path

from app.services.skill_evidence_service import (
    SkillEvidenceService,
    HIGH_LEVEL_SKILLS,
    extract_skills_with_evidence,
)


def test_explicit_source_with_real_dictionary():
    report = extract_skills_with_evidence("要求 Python、SQL、Spark，负责数据管道建设")
    skills = {s["skill"]: s for s in report["skills"]}
    assert "Python" in skills and skills["Python"]["source_type"] == "explicit"
    assert skills["Python"]["confidence"] == 0.98
    assert "SQL" in skills and "Spark" in skills
    assert report["summary"]["inferred"] == 0


def test_synonym_source_with_real_dictionary():
    report = extract_skills_with_evidence("熟悉 Machine Learning 与 Reinforcement Learning")
    skills = {s["skill"]: s for s in report["skills"]}
    # Machine Learning -> 机器学习（同义词映射）
    assert skills.get("机器学习", {}).get("source_type") == "synonym"
    assert skills["机器学习"]["confidence"] == 0.90


def test_boundary_matching_avoids_false_positive():
    # "CSS" 不应被拆成单字符 "C"
    report = extract_skills_with_evidence("前端开发，要求 CSS")
    skills = {s["skill"] for s in report["skills"]}
    assert "CSS" in skills
    assert "C" not in skills


def test_dictionary_source_via_match_pattern():
    """用临时词典验证 match_pattern 命中的 dictionary 来源。"""
    csv_content = (
        "skill_id,canonical_name,aliases,skill_category,parent_skill,match_pattern,source,version\n"
        'SK999,数据分析,数据分析,数据科学,,数据分析|DA,team_review,v1\n'
    )
    with tempfile.TemporaryDirectory() as tmp:
        dict_path = Path(tmp) / "dict.csv"
        dict_path.write_text(csv_content, encoding="utf-8")
        service = SkillEvidenceService(dictionary_path=str(dict_path))
        report = service.extract_with_report("本岗位主要做 DA 相关工作")
        skills = {s["skill"]: s for s in report["skills"]}
        assert skills.get("数据分析", {}).get("source_type") == "dictionary"
        assert skills["数据分析"]["confidence"] == 0.85


def _hallucinating_similarity(skill: str, text: str) -> float:
    """模拟一个"过度联想"的模型：只要提 AI/模型，就认为很多高阶技能都相关。"""
    text_cf = text.casefold()
    if "ai" in text_cf or "模型" in text:
        if skill in {"机器学习", "深度学习", "大模型训练", "RLHF", "RAG", "Prompt Engineering"}:
            return 0.9
    return 0.1


def test_inference_is_off_by_default():
    report = extract_skills_with_evidence("做过 AI 项目")
    skills = {s["skill"] for s in report["skills"]}
    # 默认不推断：不应出现高阶技能
    assert "大模型训练" not in skills
    assert "RLHF" not in skills
    assert report["summary"]["inferred"] == 0


def test_high_level_skill_inference_is_blocked():
    report = extract_skills_with_evidence(
        "做过 AI 项目",
        allow_inference=True,
        semantic_similarity_fn=_hallucinating_similarity,
    )
    blocked = [b["skill"] for b in report["blocked"]]
    # 高阶技能被拦截
    assert "大模型训练" in blocked
    assert "RLHF" in blocked
    # 拦截的技能不会进入结果
    skills = {s["skill"] for s in report["skills"]}
    assert "大模型训练" not in skills
    assert "RLHF" not in skills
    # 拦截原因明确
    assert all(b["blocked_reason"] for b in report["blocked"])


def test_inferred_skill_has_reduced_confidence():
    report = extract_skills_with_evidence(
        "做过 AI 项目",
        allow_inference=True,
        semantic_similarity_fn=_hallucinating_similarity,
    )
    skills = {s["skill"]: s for s in report["skills"]}
    # 非高阶技能可推断，但置信度被压到上限 0.55 且标记幻觉风险
    ml = skills["机器学习"]
    assert ml["source_type"] == "inferred"
    assert ml["confidence"] <= 0.55
    assert ml["hallucination_risk"] is True
    # 推断置信度永远低于词典命中（0.85）
    assert ml["confidence"] < 0.85


def test_evidence_text_present_on_every_skill():
    report = extract_skills_with_evidence("要求 Python、SQL，熟悉 Machine Learning")
    for skill in report["skills"]:
        assert skill["evidence"]
        assert skill["matched_text"] or skill["source_type"] == "inferred"


def test_explain_edge():
    evidence = {
        "skill": "PyTorch",
        "source_type": "explicit",
        "matched_text": "PyTorch",
        "confidence": 0.98,
        "evidence": "",
    }
    edge_reason = SkillEvidenceService.explain_edge(evidence)
    assert "PyTorch" in edge_reason
    assert "原文显式出现" in edge_reason


# ── 准确率评测（小规模金标集，可复现）─────────────────────────────

LABELED_SAMPLES = [
    {"text": "要求 Python、SQL、Spark，负责数据管道建设", "gold": ["Python", "SQL", "Spark", "数据管道"]},
    {"text": "熟悉 Machine Learning 与 PyTorch", "gold": ["机器学习", "PyTorch"]},
    {"text": "前端开发，要求 React、CSS", "gold": ["前端开发", "React", "CSS"]},
    {"text": "掌握 Kubernetes 与 Docker，做微服务", "gold": ["Kubernetes", "Docker", "微服务"]},
]


def _evaluate_accuracy(service: SkillEvidenceService, samples) -> dict:
    """在金标集上计算宏观 P/R/F1。"""
    precisions, recalls = [], []
    for sample in samples:
        predicted = {s["skill"] for s in service.extract_with_report(sample["text"])["skills"]}
        gold = set(sample["gold"])
        tp = len(predicted & gold)
        precisions.append(tp / len(predicted) if predicted else 0.0)
        recalls.append(tp / len(gold) if gold else 0.0)
    precision = sum(precisions) / len(precisions)
    recall = sum(recalls) / len(recalls)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "sample_size": len(samples),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def test_labeled_accuracy_harness():
    """金标集上的抽取准确率应达到 100%（样本内技能均为显式/同义词命中）。"""
    service = SkillEvidenceService()
    metrics = _evaluate_accuracy(service, LABELED_SAMPLES)
    assert metrics["sample_size"] == 4
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
