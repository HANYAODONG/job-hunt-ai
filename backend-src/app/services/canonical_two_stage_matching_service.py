"""Local canonical role-first matcher for uploaded resumes.

The service keeps matching inside the released v2 canonical JD pool. It has no
Elasticsearch, Neo4j, embedding model, or remote-model dependency: stage one
selects a third-level role from resume skills and stage two ranks concrete JDs
only within that role. The implementation mirrors the offline evaluator so the
interactive upload path and evaluation path share the same scoring logic.
"""

from __future__ import annotations

import csv
import json
import math
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models.candidate import Candidate
from ..models.job import ExperienceLevel, Job, JobSearchQuery, JobSearchResult, JobType, Location


APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(os.getenv("JOB_HUNT_REPO_ROOT", Path(__file__).resolve().parents[3]))
DEFAULT_JOBS_PATH = REPO_ROOT / "artifacts" / "canonical_role_pool_v2" / "canonical_jobs.jsonl"
DEFAULT_PROFILES_PATH = REPO_ROOT / "artifacts" / "dataset_iteration_05" / "candidate_profiles.jsonl"
DEFAULT_ROLE_MAP_PATH = APP_ROOT / "data" / "canonical_role_pool" / "v2" / "source_role_mapping.csv"

SKILL_ALIASES = {
    "golang": "go",
    "go语言": "go",
    "js": "javascript",
    "ts": "typescript",
    "python3": "python",
    "py": "python",
    "c++": "c/c++",
    "cpp": "c/c++",
    "大语言模型": "大模型",
    "large language model": "大模型",
    "llm": "大模型",
    "machine learning": "机器学习",
    "deep learning": "深度学习",
    "c／c++": "c/c++",
    "c/c++": "c/c++",
    "cpp": "c/c++",
    "reinforcement learning": "强化学习",
    "rl": "强化学习",
    "sft": "模型微调",
    "rlhf": "模型微调",
    "fine-tuning": "模型微调",
    "fine tuning": "模型微调",
    "lora": "模型微调",
    "ai agent": "agent",
    "智能体": "agent",
}

# These groups describe evidence-equivalent skills. They deliberately stay
# small and explicit: a broad skill may support a specialised requirement,
# but never receives full credit unless the resume contains that capability.
SKILL_GROUPS = {
    "c/c++": {"c", "c++", "cpp", "c/c++"},
    "python": {"python", "python3", "py"},
    "机器学习": {"机器学习", "machine learning", "ml"},
    "深度学习": {"深度学习", "deep learning"},
    "强化学习": {"强化学习", "reinforcement learning", "rl"},
    "模型微调": {"模型微调", "大模型微调", "fine-tuning", "fine tuning", "sft", "rlhf", "lora"},
    "模型预训练": {"模型预训练", "大模型预训练", "预训练", "pretraining", "pre-training"},
    "大模型": {"大模型", "大语言模型", "llm", "large language model"},
    "agent": {"agent", "ai agent", "智能体"},
    "multi-agent": {"multi-agent", "multi agent", "多智能体"},
    "tool-use": {"tool use", "tool-use", "工具使用", "工具调用"},
    "任务规划": {"任务规划", "task planning", "planning"},
    "nlp": {"nlp", "自然语言处理"},
    "cv": {"cv", "computer vision", "计算机视觉"},
}

_SKILL_TO_GROUP = {
    alias.casefold(): group
    for group, aliases in SKILL_GROUPS.items()
    for alias in aliases
}


def _normalise_skill(value: Any) -> str:
    value = str(value or "").strip().casefold()
    value = SKILL_ALIASES.get(value, value)
    return _SKILL_TO_GROUP.get(value, value)


def _skill_set(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {_normalise_skill(value) for value in values if _normalise_skill(value)}


def _skill_match_strength(candidate_skill: str, required_skill: str) -> float:
    """Return full, partial, or zero evidence for one requirement.

    Full matches include curated equivalents such as C/C++ and SFT/RLHF.
    Broad evidence (for example LLM for a specialised pre-training JD) is
    useful context but receives only partial credit.
    """
    candidate = _normalise_skill(candidate_skill)
    required = _normalise_skill(required_skill)
    if not candidate or not required:
        return 0.0
    if candidate == required:
        return 1.0
    broad_to_specialised = {
        "大模型": {"模型预训练", "模型微调", "multi-agent", "tool-use", "任务规划"},
        "agent": {"multi-agent", "tool-use", "任务规划"},
        "机器学习": {"深度学习", "强化学习"},
    }
    if required in broad_to_specialised.get(candidate, set()):
        return 0.35
    return 0.0


def _best_skill_evidence(candidate_skills: set[str], required_values: list[Any]) -> tuple[float, set[str], set[str]]:
    """Collapse overlapping JD requirements before calculating coverage."""
    required_by_group: dict[str, list[str]] = defaultdict(list)
    for value in required_values:
        label = str(value or "").strip()
        key = _normalise_skill(label)
        if key and label not in required_by_group[key]:
            required_by_group[key].append(label)

    matched: set[str] = set()
    missing: set[str] = set()
    total_weight = float(len(required_by_group))
    covered_weight = 0.0
    for key, labels in required_by_group.items():
        strengths = [(skill, _skill_match_strength(skill, key)) for skill in candidate_skills]
        best = max(strengths, key=lambda item: item[1], default=("", 0.0))
        if best[1] > 0:
            covered_weight += best[1]
            matched.update(labels)
        else:
            missing.update(labels)
    recall = covered_weight / total_weight if total_weight else 0.0
    return recall, matched, missing


class CanonicalTwoStageMatchingService:
    """Lazy, in-process implementation of the v2 closed-set matcher."""

    def __init__(
        self,
        jobs_path: Path = DEFAULT_JOBS_PATH,
        profiles_path: Path = DEFAULT_PROFILES_PATH,
        role_map_path: Path = DEFAULT_ROLE_MAP_PATH,
    ) -> None:
        self.jobs_path = jobs_path
        self.profiles_path = profiles_path
        self.role_map_path = role_map_path
        self._jobs: list[dict[str, Any]] | None = None
        self._role_weights: dict[str, dict[str, float]] | None = None
        self._role_titles: dict[str, str] = {}
        self._role_directions: dict[str, str] = {}

    def _load(self) -> None:
        if self._jobs is not None and self._role_weights is not None:
            return
        if not self.jobs_path.exists():
            raise FileNotFoundError(f"Canonical v2 JD pool not found: {self.jobs_path}")

        with self.jobs_path.open("r", encoding="utf-8") as handle:
            self._jobs = [
                row
                for line in handle
                if line.strip()
                for row in [json.loads(line)]
                if row.get("role_mapping_status") == "mapped"
            ]
        self._role_titles = {
            str(row.get("canonical_role_id") or ""): str(row.get("canonical_role") or "")
            for row in self._jobs
            if row.get("canonical_role_id")
        }
        self._role_directions = {
            str(row.get("canonical_role_id") or ""): str(row.get("canonical_direction") or "")
            for row in self._jobs
            if row.get("canonical_role_id")
        }
        self._role_weights = self._build_role_weights()

    def _build_role_weights(self) -> dict[str, dict[str, float]]:
        if not self.profiles_path.exists() or not self.role_map_path.exists():
            return {}
        with self.role_map_path.open("r", encoding="utf-8-sig", newline="") as handle:
            role_map = {
                row["source_standard_job"]: row["role_id"]
                for row in csv.DictReader(handle)
                if row.get("source_standard_job") and row.get("role_id")
            }

        role_counts: defaultdict[str, int] = defaultdict(int)
        role_skill_counts: defaultdict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
        skill_counts: defaultdict[str, int] = defaultdict(int)
        with self.profiles_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                profile = json.loads(line)
                if profile.get("split") != "train":
                    continue
                role_id = role_map.get(str(profile.get("target_job_family") or ""))
                if not role_id:
                    continue
                role_counts[role_id] += 1
                for skill in _skill_set(profile.get("skills_normalized") or profile.get("skills")):
                    role_skill_counts[role_id][skill] += 1
                    skill_counts[skill] += 1

        total = sum(role_counts.values())
        weights: dict[str, dict[str, float]] = {}
        for role_id, counts in role_skill_counts.items():
            weights[role_id] = {
                skill: math.log(
                    ((counts.get(skill, 0) + 1) / (role_counts[role_id] + 2))
                    / ((count - counts.get(skill, 0) + 1) / (total - role_counts[role_id] + 2))
                )
                for skill, count in skill_counts.items()
            }
        return weights

    @staticmethod
    def _score_job(candidate_skills: set[str], job: dict[str, Any]) -> dict[str, Any]:
        required_values = job.get("required_skills") or job.get("skills") or []
        preferred = _skill_set(job.get("preferred_skills"))
        required = _skill_set(required_values)
        shared_required = candidate_skills & required
        shared_preferred = candidate_skills & preferred
        recall, matched_labels, missing_labels = _best_skill_evidence(candidate_skills, required_values)
        # Extra resume skills should not collapse a good fit. Precision is
        # bounded by the number of distinct requirement groups, rather than
        # penalising a candidate for unrelated but valid skills.
        precision = len(shared_required) / max(1, min(len(candidate_skills), len(required)))
        f1 = 2 * recall * precision / (recall + precision) if recall + precision else 0.0
        # A sparse JD can be a valid real posting, but its perfect skill
        # coverage is not evidence that the whole canonical role is covered.
        # Keep this quality signal separate from the candidate's JD fit.
        required_group_count = len(required)
        jd_quality = "low_information" if required_group_count < 5 else "normal"
        return {
            "score": 0.75 * recall + 0.15 * f1 + 0.10 * precision,
            "required": required,
            "shared_required": shared_required,
            "shared_preferred": shared_preferred,
            "recall": recall,
            "matched_labels": matched_labels,
            "missing_labels": missing_labels,
            "required_group_count": required_group_count,
            "jd_quality": jd_quality,
        }

    def match(self, candidate: Candidate, query: JobSearchQuery, limit: int = 10) -> JobSearchResult:
        self._load()
        assert self._jobs is not None
        assert self._role_weights is not None
        candidate_skills = _skill_set([skill.name for skill in candidate.skills])
        scored: list[tuple[dict[str, Any], dict[str, Any]]] = [
            (job, self._score_job(candidate_skills, job)) for job in self._jobs
        ]
        by_role: defaultdict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
        for item in scored:
            by_role[str(item[0].get("canonical_role_id") or "")].append(item)

        role_rows: list[dict[str, Any]] = []
        for role_id, role_jobs in by_role.items():
            # Fit remains the primary key. When several JDs are equally well
            # matched, prefer the one with more explicit requirements so a
            # one-skill posting does not hide a more useful concrete JD.
            role_jobs.sort(key=lambda item: (
                -item[1]["score"],
                -item[1]["required_group_count"],
                str(item[0].get("job_id") or ""),
            ))
            top = role_jobs[:3]
            jd_role_score = 0.70 * top[0][1]["score"] + 0.30 * sum(item[1]["score"] for item in top) / len(top)
            classifier_score = sum(max(0.0, self._role_weights.get(role_id, {}).get(skill, 0.0)) for skill in candidate_skills)
            role_rows.append({
                "role_id": role_id,
                "role": top[0][0].get("canonical_role", ""),
                "classifier_score": classifier_score,
                "jd_role_score": jd_role_score,
                "jobs": role_jobs,
            })
        # Build one display score for both ranking and UI. The learned
        # role-discriminating evidence is primary; the best in-role JD score
        # is a secondary signal. This prevents a generic JD with many broad
        # skills from outranking the role classifier and keeps Top-3 monotonic.
        max_classifier = max((row["classifier_score"] for row in role_rows), default=0.0)
        for row in role_rows:
            classifier_norm = row["classifier_score"] / max_classifier if max_classifier > 0 else row["jd_role_score"]
            row["role_match_score"] = 0.80 * classifier_norm + 0.20 * row["jd_role_score"]
        role_rows.sort(key=lambda item: (-item["role_match_score"], -item["classifier_score"], item["role_id"]))
        selected = role_rows[0] if role_rows else None
        selected_jobs = selected["jobs"][:max(1, limit)] if selected else []
        selected_role_score = selected["role_match_score"] if selected else None
        jobs = [self._to_job(job, metrics, candidate_skills, selected_role_score) for job, metrics in selected_jobs]
        # The selected role remains the only scope for concrete JD ranking.
        # Expose the next distinct role candidates separately for a truthful
        # Top-3 UI; they must not be confused with more JDs for the same role.
        top_role_candidates = []
        for row in role_rows[:3]:
            best_job, best_metrics = row["jobs"][0]
            representative = self._to_job(best_job, best_metrics, candidate_skills).model_dump(mode="json")
            representative["search_metadata"]["canonical_role"] = self._role_titles.get(row["role_id"], row["role"])
            representative["search_metadata"]["canonical_direction"] = self._role_directions.get(row["role_id"], "")
            representative["search_metadata"]["role_match_score"] = round(float(row["role_match_score"]), 6)
            representative["search_metadata"]["representative_jd_score"] = round(float(best_metrics["score"]), 6)
            top_role_candidates.append({
                "canonical_role_id": row["role_id"],
                "canonical_role": self._role_titles.get(row["role_id"], row["role"]),
                "canonical_direction": self._role_directions.get(row["role_id"], ""),
                "role_score": round(float(row["role_match_score"]), 6),
                "role_confidence": round(float(row["role_match_score"]), 6),
                "representative_job": representative,
            })

        # Stage two is deliberately inspectable: these are concrete JD titles
        # ranked only inside the selected canonical role. They are not extra
        # role candidates and must not be conflated with Top-3 role discovery.
        selected_role_jd_candidates = []
        if selected:
            for raw_job, jd_metrics in selected["jobs"][: max(3, min(limit, 10))]:
                selected_role_jd_candidates.append({
                    "job_id": str(raw_job.get("job_id") or raw_job.get("id") or ""),
                    "title": str(raw_job.get("title") or raw_job.get("canonical_role") or "未命名岗位"),
                    "canonical_role_id": str(raw_job.get("canonical_role_id") or ""),
                    "canonical_role": str(raw_job.get("canonical_role") or selected.get("role") or ""),
                    "jd_fit_score": round(float(jd_metrics["score"]), 6),
                    "skill_coverage": round(float(jd_metrics["recall"]), 6),
                    "required_skill_group_count": jd_metrics["required_group_count"],
                    "jd_quality": jd_metrics["jd_quality"],
                })

        return JobSearchResult(
            jobs=jobs,
            total_count=len(selected["jobs"]) if selected else 0,
            page=query.page,
            page_size=min(max(1, limit), query.page_size),
            total_pages=1 if selected else 0,
            search_time_ms=0.0,
            explanations={
                "matching_pipeline": "canonical_two_stage_v2",
                "role_pool_version": "v2",
                "selected_canonical_role_id": selected["role_id"] if selected else None,
                "selected_canonical_role": selected["role"] if selected else None,
                "selected_role_confidence": round(float(selected["role_match_score"]), 6) if selected else None,
                "candidate_skill_count": len(candidate_skills),
                "external_services_used": False,
                "top_role_candidates": top_role_candidates,
                "selected_role_jd_candidates": selected_role_jd_candidates,
            },
        )

    @staticmethod
    def _to_job(
        raw: dict[str, Any],
        metrics: dict[str, Any],
        candidate_skills: set[str],
        role_score: float | None = None,
    ) -> Job:
        matched = sorted(metrics["shared_required"] | metrics["shared_preferred"])
        missing = sorted(metrics.get("missing_labels") or (metrics["required"] - candidate_skills))
        matched_labels = sorted(metrics.get("matched_labels") or metrics["shared_required"])
        return Job(
            id=str(raw.get("job_id") or raw.get("id")),
            title=str(raw.get("title") or raw.get("canonical_role") or "未命名岗位"),
            description=str(raw.get("description") or ""),
            company_name=str(raw.get("company_name") or raw.get("source") or "岗位数据源"),
            location=Location(city=str(raw.get("city") or "未注明"), state=str(raw.get("state") or ""), country="中国"),
            job_type=JobType.FULL_TIME,
            experience_level=ExperienceLevel.MID,
            required_skills=list(raw.get("required_skills") or raw.get("skills") or []),
            preferred_skills=list(raw.get("preferred_skills") or []),
            posted_date=datetime.now(),
            source=str(raw.get("source") or "canonical_role_pool_v2"),
            job_family=str(raw.get("canonical_role") or raw.get("job_family") or ""),
            rerank_score=round(float(metrics["score"]), 6),
            search_metadata={
                "canonical_role_id": raw.get("canonical_role_id"),
                "canonical_role": raw.get("canonical_role"),
                "canonical_direction": raw.get("canonical_direction"),
                "matching_pipeline": "canonical_two_stage_v2",
                "jd_fit_score": round(float(metrics["score"]), 6),
                "skill_coverage": round(float(metrics["recall"]), 6),
                "required_skill_group_count": metrics["required_group_count"],
                "jd_quality": metrics["jd_quality"],
                "role_match_score": round(float(role_score), 6) if role_score is not None else None,
                "role_confidence": round(float(role_score), 6) if role_score is not None else None,
                "match_explanation": {
                    "components": {
                        "Skill Match": {
                            "score": round(float(metrics["score"]), 6),
                            "details": {"matched_skills": matched_labels, "missing_skills": missing},
                        },
                        "Job Description Match": {"score": round(float(metrics["recall"]), 6), "details": {}},
                    }
                },
            },
        )
