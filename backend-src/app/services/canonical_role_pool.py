"""Data-driven canonical role pool for graph and person-role matching."""

from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_ROLE_POOL_DATA_ROOT = Path(__file__).resolve().parents[1] / "data" / "canonical_role_pool"
_DEFAULT_ROLE_POOL_ROOT = (
    _ROLE_POOL_DATA_ROOT / "v2"
    if (_ROLE_POOL_DATA_ROOT / "v2" / "canonical_roles.csv").exists()
    else _ROLE_POOL_DATA_ROOT / "v1"
)
# Prefer the released v2 catalog when it is present. Deployments can select a
# different version through JOB_HUNT_CANONICAL_ROLE_DATA_DIR without changing
# classification or scoring logic.
ROLE_POOL_ROOT = Path(
    os.getenv("JOB_HUNT_CANONICAL_ROLE_DATA_DIR", str(_DEFAULT_ROLE_POOL_ROOT))
).expanduser()


@dataclass(frozen=True)
class CanonicalRole:
    role_id: str
    domain: str
    direction: str
    role_name: str
    role_definition: str
    core_boundary: str
    status: str


@dataclass(frozen=True)
class SourceRoleMapping:
    source_standard_job: str
    role_id: str
    specialization: str
    requires_jd_validation: bool


@dataclass(frozen=True)
class TitleRefinementRule:
    source_standard_job: str
    role_id: str
    specialization: str
    title_pattern: re.Pattern[str]


@dataclass(frozen=True)
class SkillRefinementRule:
    source_standard_job: str
    role_id: str
    specialization: str
    minimum_matches: int
    signals: tuple[str, ...]


@dataclass(frozen=True)
class RoleNeighbor:
    role_id_a: str
    role_id_b: str
    relation: str
    matching_treatment: str
    rationale: str


class CanonicalRolePool:
    """Map data-provider standard labels into a non-overlapping role taxonomy."""

    _ROLE_STATUSES = {"active", "review_only", "planned"}
    _GENERIC_ROLE_IDS = {
        "general_algorithm",
        "general_software_engineering",
        "cybersecurity_engineering",
    }
    _NON_TECHNICAL_TITLE_TERMS = (
        "客户经理",
        "销售",
        "采销",
        "采购",
        "运营",
        "商务",
        "市场",
        "招聘",
        "人力",
        "行政",
        "财务",
        "法务",
        "pmo",
        "类目",
    )
    _ROLE_CONTRADICTION_TERMS = {
        "chip_design": ("技术美术", "数据ai", "go语言", "产品经理"),
        "hardware_engineering": ("暖通", "产品经理", "紧固件质量"),
        "software_architecture": ("产品经理", "硬件系统架构"),
        "ai_platform_infra": ("教练",),
    }

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or ROLE_POOL_ROOT
        self.roles = self._load_roles(self.data_dir / "canonical_roles.csv")
        self.mappings = self._load_mappings(self.data_dir / "source_role_mapping.csv")
        self.refinement_rules = self._load_refinement_rules(self.data_dir / "title_refinement_rules.csv")
        self.skill_refinement_rules = self._load_skill_refinement_rules(
            self.data_dir / "skill_refinement_rules.csv"
        )
        self.neighbors = self._load_neighbors(self.data_dir / "role_neighbors.csv")
        self._validate()

    @staticmethod
    def _read_csv(path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    @classmethod
    def _load_roles(cls, path: Path) -> dict[str, CanonicalRole]:
        roles: dict[str, CanonicalRole] = {}
        for row in cls._read_csv(path):
            role = CanonicalRole(**row)
            if role.role_id in roles:
                raise ValueError(f"Duplicate canonical role_id: {role.role_id}")
            roles[role.role_id] = role
        return roles

    @classmethod
    def _load_mappings(cls, path: Path) -> dict[str, SourceRoleMapping]:
        mappings: dict[str, SourceRoleMapping] = {}
        for row in cls._read_csv(path):
            mapping = SourceRoleMapping(
                source_standard_job=row["source_standard_job"].strip(),
                role_id=row["role_id"].strip(),
                specialization=row["specialization"].strip(),
                requires_jd_validation=row["requires_jd_validation"].strip().lower() == "true",
            )
            if mapping.source_standard_job in mappings:
                raise ValueError(f"Duplicate source standard role: {mapping.source_standard_job}")
            mappings[mapping.source_standard_job] = mapping
        return mappings

    @classmethod
    def _load_refinement_rules(cls, path: Path) -> dict[str, list[TitleRefinementRule]]:
        rules: dict[str, list[TitleRefinementRule]] = {}
        for row in cls._read_csv(path):
            rule = TitleRefinementRule(
                source_standard_job=row["source_standard_job"].strip(),
                role_id=row["role_id"].strip(),
                specialization=row["specialization"].strip(),
                title_pattern=re.compile(row["title_pattern"].strip(), re.IGNORECASE),
            )
            rules.setdefault(rule.source_standard_job, []).append(rule)
        return rules

    @classmethod
    def _load_skill_refinement_rules(cls, path: Path) -> dict[str, list[SkillRefinementRule]]:
        rules: dict[str, list[SkillRefinementRule]] = {}
        for row in cls._read_csv(path):
            rule = SkillRefinementRule(
                source_standard_job=row["source_standard_job"].strip(),
                role_id=row["role_id"].strip(),
                specialization=row["specialization"].strip(),
                minimum_matches=int(row["minimum_matches"]),
                signals=tuple(signal.strip().casefold() for signal in row["signals"].split(";") if signal.strip()),
            )
            rules.setdefault(rule.source_standard_job, []).append(rule)
        return rules

    @classmethod
    def _load_neighbors(cls, path: Path) -> dict[frozenset[str], RoleNeighbor]:
        neighbors: dict[frozenset[str], RoleNeighbor] = {}
        for row in cls._read_csv(path):
            neighbor = RoleNeighbor(**row)
            key = frozenset((neighbor.role_id_a, neighbor.role_id_b))
            if len(key) != 2:
                raise ValueError(f"Invalid role neighbor pair: {neighbor}")
            if key in neighbors:
                raise ValueError(f"Duplicate role neighbor pair: {neighbor.role_id_a}/{neighbor.role_id_b}")
            neighbors[key] = neighbor
        return neighbors

    def _validate(self) -> None:
        if not self.roles:
            raise ValueError("Canonical role pool is empty")
        invalid_statuses = {
            role.role_id: role.status for role in self.roles.values()
            if role.status not in self._ROLE_STATUSES
        }
        if invalid_statuses:
            raise ValueError(f"Invalid canonical role statuses: {invalid_statuses}")
        if not self.mappings:
            raise ValueError("Canonical role mappings are empty")
        unknown_role_ids = {mapping.role_id for mapping in self.mappings.values()} - set(self.roles)
        unknown_role_ids |= {
            rule.role_id for rules in self.refinement_rules.values() for rule in rules
        } - set(self.roles)
        unknown_role_ids |= {
            rule.role_id for rules in self.skill_refinement_rules.values() for rule in rules
        } - set(self.roles)
        unknown_role_ids |= {
            role_id
            for neighbor in self.neighbors.values()
            for role_id in (neighbor.role_id_a, neighbor.role_id_b)
        } - set(self.roles)
        if unknown_role_ids:
            raise ValueError(f"Mappings reference unknown role ids: {sorted(unknown_role_ids)}")

    @staticmethod
    def source_standard_job(record: dict[str, Any]) -> str:
        return str(record.get("standard_job") or record.get("job_family") or "").strip()

    @staticmethod
    def _skill_evidence(record: dict[str, Any]) -> str:
        values = record.get("skills") or record.get("required_skills") or []
        if isinstance(values, str):
            values = [values]
        return " ".join(str(value) for value in values).casefold()

    @staticmethod
    def _skill_signal_matches(signal: str, evidence: str) -> bool:
        """Match short ASCII abbreviations as tokens, not arbitrary substrings."""
        if re.fullmatch(r"[a-z0-9+#.]+", signal):
            return bool(re.search(rf"(?<![a-z0-9]){re.escape(signal)}(?![a-z0-9])", evidence))
        return signal in evidence

    def classify(self, record: dict[str, Any]) -> dict[str, Any]:
        source_role = self.source_standard_job(record)
        mapping = self.mappings.get(source_role)
        if mapping is None:
            return {
                "source_standard_job": source_role,
                "role_mapping_status": "unmapped",
                "role_mapping_confidence": 0.0,
                "role_mapping_review_reasons": ["未找到数据源标准岗位映射"],
            }

        title_refinement = next(
            (rule for rule in self.refinement_rules.get(source_role, []) if rule.title_pattern.search(str(record.get("title") or record.get("job_title") or ""))),
            None,
        )
        skill_evidence = self._skill_evidence(record)
        skill_refinement = next(
            (
                rule
                for rule in self.skill_refinement_rules.get(source_role, [])
                if sum(self._skill_signal_matches(signal, skill_evidence) for signal in rule.signals) >= rule.minimum_matches
            ),
            None,
        )
        refinement = title_refinement or skill_refinement
        role_id = refinement.role_id if refinement else mapping.role_id
        specialization = refinement.specialization if refinement else mapping.specialization
        role = self.roles[role_id]
        title = str(record.get("title") or record.get("job_title") or "").casefold()
        reasons: list[str] = []
        if role.status != "active":
            reasons.append("规范岗位尚未激活，需完成市场命名与JD证据审核")
        if role_id in self._GENERIC_ROLE_IDS:
            reasons.append("来源标签为通用岗位，需由JD职责进一步细分")
        non_technical_terms = [term for term in self._NON_TECHNICAL_TITLE_TERMS if term in title]
        # “安全运营工程师” is a technical SOC/response role. Its use of
        # “运营” does not mean product or commercial operations.
        if role_id == "security_operations":
            non_technical_terms = [term for term in non_technical_terms if term != "运营"]
        if non_technical_terms:
            reasons.append("岗位标题包含非技术职能信号")
        if any(term in title for term in self._ROLE_CONTRADICTION_TERMS.get(role_id, ())):
            reasons.append("岗位标题与标准岗位核心边界冲突")

        status = "review_required" if reasons else "mapped"
        confidence = 0.55 if reasons else (
            0.9 if title_refinement else (0.84 if skill_refinement else (0.82 if mapping.requires_jd_validation else 0.96))
        )
        return {
            "source_standard_job": source_role,
            "canonical_role_id": role.role_id,
            "canonical_role": role.role_name,
            "canonical_domain": role.domain,
            "canonical_direction": role.direction,
            "role_specialization": specialization,
            "role_mapping_refined_by_title": bool(title_refinement),
            "role_mapping_refined_by_skills": bool(skill_refinement and not title_refinement),
            "role_mapping_status": status,
            "role_mapping_confidence": confidence,
            "role_mapping_requires_jd_validation": mapping.requires_jd_validation,
            "role_mapping_review_reasons": reasons,
        }

    def enrich(self, record: dict[str, Any]) -> dict[str, Any]:
        """Return a graph-ready record while preserving the provider's original label."""
        mapping = self.classify(record)
        enriched = {**record, **mapping}
        if mapping["role_mapping_status"] == "unmapped":
            return enriched
        enriched["standard_job"] = mapping["canonical_role"]
        enriched["job_family"] = mapping["canonical_role"]
        enriched["standard_category"] = mapping["canonical_domain"]
        enriched["standard_direction"] = mapping["canonical_direction"]
        return enriched

    def relation_between(self, role_id_a: str, role_id_b: str) -> dict[str, str]:
        """Return an evaluation-safe relationship between two canonical roles."""
        if role_id_a == role_id_b:
            return {"relation": "same_role", "matching_treatment": "full_credit"}
        neighbor = self.neighbors.get(frozenset((role_id_a, role_id_b)))
        if neighbor is None:
            return {"relation": "unrelated", "matching_treatment": "no_auto_credit"}
        return {
            "relation": neighbor.relation,
            "matching_treatment": neighbor.matching_treatment,
        }
