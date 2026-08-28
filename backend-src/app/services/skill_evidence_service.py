"""Skill Evidence Service — 能力幻觉防控与技能证据链

对应分工6 §4：给 JD / 简历技能抽取结果增加证据来源，防止能力幻觉。

核心思想：
    - 每条技能都携带证据链：skill / source_type / matched_text / confidence / evidence。
    - 区分四种来源：原文显式出现(explicit) / 同义词映射(synonym) / 词典归一(dictionary) / 模型推断(inferred)。
    - 模型推断类技能降低置信度；高阶技能（大模型训练、RLHF 等）禁止推断。

该模块无数据库/模型硬依赖，纯确定性实现，可离线运行与单测。
"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── 来源类型与默认置信度 ──────────────────────────────────────────
SOURCE_LABELS: Dict[str, str] = {
    "explicit": "原文显式出现",
    "synonym": "同义词映射",
    "dictionary": "词典归一",
    "inferred": "模型推断",
}

SOURCE_CONFIDENCE: Dict[str, float] = {
    "explicit": 0.98,   # 标准技能名原文直接出现
    "synonym": 0.90,    # 别名/同义词出现在原文
    "dictionary": 0.85, # 词典归一（match_pattern / 分词命中）
    "inferred": 0.55,   # 模型推断（置信度上限，永远低于词典）
}

# 模型推断的最低相似度阈值
INFERENCE_THRESHOLD = 0.6

# ── 高阶/重技能白名单：只能靠显式/同义/词典命中，禁止推断 ──────────
# 这些能力一旦被"猜"出来，危害最大（例如简历只写了"AI 项目"就推断"大模型训练/RLHF"）。
HIGH_LEVEL_SKILLS: set[str] = {
    "大模型训练", "RLHF", "分布式训练", "SFT", "DPO", "模型量化",
    "Megatron", "DeepSpeed", "vLLM", "SGLang", "Transformer",
    "多模态大模型", "强化学习", "分布式计算", "GPU", "CUDA", "RDMA",
}


class SkillEvidenceService:
    """带证据链的技能抽取器，内建能力幻觉防控规则。"""

    def __init__(self, dictionary_path: Optional[str] = None):
        if dictionary_path is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
            dictionary_path = base_dir / "standard_skill_dictionary.csv"
        self.dictionary_path = Path(dictionary_path)
        self.alias_map: Dict[str, str] = {}      # casefold(alias) -> canonical
        self.canonical_names: List[str] = []     # 标准技能名（保持字典顺序）
        self.canonical_casefold: Dict[str, str] = {}  # casefold(canonical) -> canonical
        self.skill_meta: Dict[str, Dict[str, str]] = {}  # canonical -> {category, parent}
        self.match_patterns: Dict[str, str] = {}  # canonical -> match_pattern
        self._load_dictionary()

    # ── 词典加载 ──────────────────────────────────────────────────

    def _load_dictionary(self) -> None:
        if not self.dictionary_path.exists():
            raise FileNotFoundError(f"技能词典不存在: {self.dictionary_path}")

        with open(self.dictionary_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                canonical = (row.get("canonical_name") or "").strip()
                if not canonical:
                    continue
                if canonical not in self.skill_meta:
                    self.canonical_names.append(canonical)
                    self.skill_meta[canonical] = {
                        "category": (row.get("skill_category") or "").strip(),
                        "parent": (row.get("parent_skill") or "").strip(),
                    }
                cf = canonical.casefold()
                self.canonical_casefold[cf] = canonical
                self.alias_map.setdefault(cf, canonical)

                # 别名
                aliases = (row.get("aliases") or "").strip()
                if aliases:
                    for alias in aliases.split(";"):
                        alias = alias.strip()
                        if alias:
                            self.alias_map.setdefault(alias.casefold(), canonical)

                # match_pattern 作为词典归一匹配源
                pattern = (row.get("match_pattern") or "").strip()
                if pattern:
                    self.match_patterns[canonical] = pattern

        logger.info(
            "SkillEvidenceService 加载完成：%d 个技能，%d 个别名，%d 个匹配模式",
            len(self.canonical_names), len(self.alias_map), len(self.match_patterns),
        )

    # ── 匹配工具 ──────────────────────────────────────────────────

    @staticmethod
    def _contains_term(text_cf: str, term_cf: str) -> bool:
        """边界感知的子串匹配。

        - 纯 ASCII 术语：要求两侧为非字母数字下划线，避免 "C" 误匹配 "CSS"。
        - 含 CJK 术语：直接子串匹配（中文无词边界问题）。
        """
        if not term_cf:
            return False
        if term_cf.isascii():
            return re.search(
                rf"(?<![A-Za-z0-9_]){re.escape(term_cf)}(?![A-Za-z0-9_])", text_cf
            ) is not None
        return term_cf in text_cf

    def _category_of(self, canonical: str) -> str:
        return self.skill_meta.get(canonical, {}).get("category", "")

    def _parent_of(self, canonical: str) -> str:
        return self.skill_meta.get(canonical, {}).get("parent", "")

    # ── 核心抽取 ──────────────────────────────────────────────────

    def extract_with_report(
        self,
        text: str,
        allow_inference: bool = False,
        min_confidence: float = 0.5,
        semantic_similarity_fn: Optional[Callable[[str, str], float]] = None,
    ) -> Dict[str, Any]:
        """抽取技能并返回证据链与拦截记录。

        返回：
        {
            "skills":  [ {skill, source_type, matched_text, confidence,
                          hallucination_risk, category, parent, evidence}, ... ],
            "blocked": [ {skill, source_type, confidence, blocked_reason}, ... ],
            "summary": { ... }
        }
        """
        text = text or ""
        text_cf = text.casefold()
        results: Dict[str, Dict[str, Any]] = {}
        blocked: List[Dict[str, Any]] = []

        # 1. 原文显式 / 同义词映射：遍历别名（含标准名），边界感知匹配
        #    按长度降序优先匹配长别名，减少 "C" vs "C++" 之类冲突。
        ordered_aliases = sorted(
            self.alias_map.items(),
            key=lambda kv: len(kv[0]),
            reverse=True,
        )
        for alias_cf, canonical in ordered_aliases:
            if len(alias_cf.strip()) < 2:
                continue  # 跳过单字符别名，避免噪声（与 SkillExtractor 一致）
            if not self._contains_term(text_cf, alias_cf):
                continue
            if alias_cf == canonical.casefold():
                source = "explicit"
            else:
                source = "synonym"
            self._add(results, canonical, source, alias_cf, SOURCE_CONFIDENCE[source])

        # 2. 词典归一：match_pattern 正则命中
        for canonical, pattern in self.match_patterns.items():
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    self._add(results, canonical, "dictionary", pattern, SOURCE_CONFIDENCE["dictionary"])
            except re.error:
                continue

        # 3. 模型推断（默认关闭；开启时需提供语义相似度函数）
        if allow_inference and semantic_similarity_fn is not None:
            for canonical in self.canonical_names:
                if canonical in results:
                    continue  # 已有更强证据
                try:
                    sim = semantic_similarity_fn(canonical, text)
                except Exception:
                    continue
                if not isinstance(sim, (int, float)) or sim < INFERENCE_THRESHOLD:
                    continue

                # 高阶技能禁止推断
                if canonical in HIGH_LEVEL_SKILLS:
                    blocked.append({
                        "skill": canonical,
                        "source_type": "inferred",
                        "confidence": 0.0,
                        "similarity": round(float(sim), 2),
                        "blocked_reason": "高阶技能禁止推断，需原文显式证据",
                    })
                    continue

                conf = round(min(SOURCE_CONFIDENCE["inferred"], float(sim)), 2)
                if conf >= min_confidence:
                    self._add(results, canonical, "inferred", "", conf)

        skills = sorted(
            (item for item in results.values() if item["confidence"] >= min_confidence),
            key=lambda item: (-item["confidence"], item["skill"]),
        )

        return {
            "skills": skills,
            "blocked": blocked,
            "summary": {
                "total": len(skills),
                "explicit": sum(1 for s in skills if s["source_type"] == "explicit"),
                "synonym": sum(1 for s in skills if s["source_type"] == "synonym"),
                "dictionary": sum(1 for s in skills if s["source_type"] == "dictionary"),
                "inferred": sum(1 for s in skills if s["source_type"] == "inferred"),
                "blocked_count": len(blocked),
                "min_confidence": min_confidence,
                "allow_inference": allow_inference,
            },
        }

    def _add(
        self,
        results: Dict[str, Dict[str, Any]],
        canonical: str,
        source: str,
        matched_text: str,
        confidence: float,
    ) -> None:
        """加入或升级一条技能证据（同一技能保留最高置信度的来源）。"""
        confidence = round(float(confidence), 2)
        if canonical in results and results[canonical]["confidence"] >= confidence:
            return
        results[canonical] = {
            "skill": canonical,
            "source_type": source,
            "matched_text": matched_text,
            "confidence": confidence,
            "hallucination_risk": source == "inferred",
            "category": self._category_of(canonical),
            "parent": self._parent_of(canonical),
            "evidence": self.explain_evidence(
                canonical, source, matched_text, confidence
            ),
        }

    # ── 证据链说明 ────────────────────────────────────────────────

    @staticmethod
    def explain_evidence(canonical: str, source: str, matched_text: str, confidence: float) -> str:
        """生成'为什么有这条边 / 这个技能'的说明。"""
        label = SOURCE_LABELS.get(source, source)
        if source == "inferred":
            return f"{label}：原文未直接出现'{canonical}'，由语义相似度推断，置信度 {confidence:.2f}（已降权，存在幻觉风险）"
        return f"{label}：原文出现 '{matched_text}'，归一为标准技能 '{canonical}'，置信度 {confidence:.2f}"

    @staticmethod
    def explain_edge(evidence: Dict[str, Any]) -> str:
        """为知识图谱中的 岗位-技能 / 候选人-技能 关系生成边证据说明。"""
        return evidence.get("evidence") or SkillEvidenceService.explain_evidence(
            evidence.get("skill", ""),
            evidence.get("source_type", "dictionary"),
            evidence.get("matched_text", ""),
            evidence.get("confidence", 0.0),
        )


# ── 便捷函数 ──────────────────────────────────────────────────────

_service: Optional[SkillEvidenceService] = None


def get_evidence_service(dictionary_path: Optional[str] = None) -> SkillEvidenceService:
    global _service
    if _service is None or dictionary_path is not None:
        _service = SkillEvidenceService(dictionary_path)
    return _service


def extract_skills_with_evidence(
    text: str,
    allow_inference: bool = False,
    min_confidence: float = 0.5,
    semantic_similarity_fn: Optional[Callable[[str, str], float]] = None,
) -> Dict[str, Any]:
    """快速入口：抽取技能 + 证据链 + 拦截记录。"""
    return get_evidence_service().extract_with_report(
        text,
        allow_inference=allow_inference,
        min_confidence=min_confidence,
        semantic_similarity_fn=semantic_similarity_fn,
    )
