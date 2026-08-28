"""Artifact-backed enterprise job and candidate matching service."""

from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPO_ROOT = (
    BACKEND_ROOT.parent if (BACKEND_ROOT.parent / "artifacts").exists() else BACKEND_ROOT
)
REPO_ROOT = Path(os.getenv("JOB_HUNT_REPO_ROOT", DEFAULT_REPO_ROOT))
ITERATION_DIR = REPO_ROOT / "artifacts" / "dataset_iteration_05"


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} line {line_number}: {exc}") from exc
            if isinstance(value, dict):
                yield value


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        values: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = str(item.get("name") or item.get("skill") or "").strip()
            else:
                text = str(item).strip()
            if text:
                values.append(text)
        return values
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[,，;；、|]", value) if item.strip()]
    return []


def _key(value: Any) -> str:
    return re.sub(r"[\s_\-/]+", "", str(value or "").casefold())


def _sentences(value: Any, limit: int = 5) -> list[str]:
    parts = [item.strip(" -\t") for item in re.split(r"[\r\n；;。]+", str(value or ""))]
    return [item for item in parts if item][:limit]


class TalentDataService:
    """Expose canonical jobs and an explainable candidate matching baseline."""

    def __init__(
        self,
        jobs_path: Path | None = None,
        profiles_path: Path | None = None,
        state_path: Path | None = None,
        fusion_path: Path | None = None,
    ) -> None:
        self.jobs_path = jobs_path or ITERATION_DIR / "jobs.jsonl"
        self.profiles_path = profiles_path or ITERATION_DIR / "candidate_profiles.jsonl"
        self.state_path = state_path or REPO_ROOT / "artifacts" / "runtime" / "talent_state.json"
        self.fusion_path = fusion_path or (
            REPO_ROOT / "artifacts" / "candidate_fusion" / "job_candidate_top300.jsonl"
        )
        self._lock = threading.RLock()
        self._jobs: dict[str, dict[str, Any]] | None = None
        self._profiles: list[dict[str, Any]] | None = None
        self._profiles_by_id: dict[str, dict[str, Any]] | None = None
        self._state: dict[str, Any] | None = None
        self._fusion_index: dict[str, dict[str, Any]] | None = None
        self._candidate_rankings: dict[str, list[dict[str, Any]]] = {}

    def _load_jobs(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            if self._jobs is None:
                if not self.jobs_path.exists():
                    raise FileNotFoundError(f"Canonical dataset not found: {self.jobs_path}")
                self._jobs = {
                    str(row.get("job_id") or row.get("id")): row
                    for row in _read_jsonl(self.jobs_path)
                    if row.get("job_id") or row.get("id")
                }
            return self._jobs

    def _load_profiles(self) -> list[dict[str, Any]]:
        with self._lock:
            if self._profiles is None:
                if not self.profiles_path.exists():
                    raise FileNotFoundError(f"Canonical dataset not found: {self.profiles_path}")
                self._profiles = list(_read_jsonl(self.profiles_path))
            return self._profiles

    def _load_fusion_index(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            if self._fusion_index is None:
                if not self.fusion_path.exists():
                    self._fusion_index = {}
                else:
                    self._fusion_index = {
                        str(row.get("job_id") or ""): row
                        for row in _read_jsonl(self.fusion_path)
                        if row.get("job_id")
                    }
            return self._fusion_index

    def _load_state(self) -> dict[str, Any]:
        with self._lock:
            if self._state is None:
                if self.state_path.exists():
                    try:
                        self._state = json.loads(self.state_path.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError):
                        self._state = {}
                else:
                    self._state = {}
                self._state.setdefault("job_overrides", {})
                self._state.setdefault("custom_jobs", {})
                self._state.setdefault("candidate_stages", {})
                self._state.setdefault("candidate_explanations", {})
            return self._state

    def _save_state(self) -> None:
        state = self._load_state()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temp_path.replace(self.state_path)

    def invalidate_runtime_state_cache(self) -> None:
        """Force other service instances to reread persisted JD overrides."""
        with self._lock:
            self._state = None

    @staticmethod
    def _required_experience(job: dict[str, Any]) -> int:
        text = " ".join(
            str(job.get(field) or "")
            for field in ("requirements", "description", "detailed")
        )
        values = [int(value) for value in re.findall(r"(\d+)\s*年(?:以上|及以上)?", text)]
        return min(values) if values else 0

    def _job_view(self, job: dict[str, Any]) -> dict[str, Any]:
        job_id = str(job.get("job_id") or job.get("id"))
        state = self._load_state()
        override = state["job_overrides"].get(job_id, {})
        merged = {**job, **override}
        skills = _list(
            merged.get("requiredSkills")
            or merged.get("required_skills")
            or merged.get("skills")
        )
        new_skills = _list(merged.get("bonusSkills") or merged.get("new_skills"))
        source_type = str(merged.get("source_type") or "unknown")
        published_at = str(merged.get("publish_time") or merged.get("publish_time_raw") or "未知")
        responsibilities = _list(merged.get("responsibilities")) or _sentences(
            merged.get("description"), 5
        )
        summary = str(merged.get("summary") or merged.get("description") or "暂无岗位说明")
        status = str(merged.get("status") or "招聘中")
        level_base = max(62, 90 - max(0, len(skills) - 4) * 2)
        return {
            "id": job_id,
            "job_id": job_id,
            "title": str(merged.get("title") or merged.get("standard_job") or "未命名岗位"),
            "department": str(
                merged.get("department")
                or merged.get("company")
                or merged.get("company_name")
                or merged.get("standard_category")
                or "标准岗位池"
            ),
            "company": str(merged.get("company") or merged.get("company_name") or ""),
            "location": str(merged.get("location") or merged.get("location_text") or "地点未标注"),
            "employmentType": str(
                merged.get("employmentType") or ("公务员" if source_type == "government" else "全职")
            ),
            "openings": int(merged.get("openings") or 1),
            "status": status,
            "version": str(merged.get("version") or "标准数据 v5"),
            "roleVersion": str(merged.get("roleVersion") or merged.get("standard_job") or "标准岗位"),
            "publishedAt": str(merged.get("publishedAt") or published_at),
            "updatedAt": str(merged.get("updatedAt") or published_at),
            "applications": int(merged.get("applications") or 0),
            "newApplications": int(merged.get("newApplications") or 0),
            "summary": summary,
            "responsibilities": responsibilities,
            "requiredSkills": [
                {"name": skill, "level": max(55, level_base - index * 3)}
                for index, skill in enumerate(skills[:12])
            ],
            "bonusSkills": new_skills,
            "revisions": merged.get("revisions")
            or [{"version": "数据导入", "date": published_at, "note": f"来源：{merged.get('source') or source_type}"}],
            "marketSuggestion": (
                {
                    "title": "岗位出现新技能要求",
                    "detail": f"当前 JD 标记了新增技能：{'、'.join(new_skills[:4])}。建议结合市场统计确认权重。",
                    "confidence": 82,
                    "evidence": len(new_skills),
                }
                if new_skills
                else None
            ),
            "source": str(merged.get("source") or "canonical_dataset"),
            "sourceType": source_type,
            "jobFamily": str(merged.get("job_family") or merged.get("standard_job") or ""),
            "standardCategory": str(merged.get("standard_category") or ""),
            "dataSource": "live-standard-dataset",
            "publish_time": str(merged.get("publish_time") or ""),  # 新增：保留原始 publish_time
        }

    def list_jobs(
        self,
        query: str = "",
        status: str | None = None,
        source_type: str | None = "enterprise",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        jobs = list(self._load_jobs().values())
        custom_jobs = list(self._load_state()["custom_jobs"].values())
        jobs = custom_jobs + jobs
        query_key = _key(query)
        filtered: list[dict[str, Any]] = []
        for raw_job in jobs:
            view = self._job_view(raw_job)
            if source_type and view["sourceType"] != source_type:
                continue
            if status and status != "全部状态" and view["status"] != status:
                continue
            if query_key and query_key not in _key(
                " ".join([view["id"], view["title"], view["department"], view["jobFamily"]])
            ):
                continue
            filtered.append(view)
        total = len(filtered)
        return {
            "items": filtered[offset : offset + limit],
            "total": total,
            "limit": limit,
            "offset": offset,
            "source": "canonical_dataset",
        }

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        raw = self._load_state()["custom_jobs"].get(job_id) or self._load_jobs().get(job_id)
        return self._job_view(raw) if raw else None

    def list_standard_role_records(self) -> list[dict[str, Any]]:
        """Return normalized records used by the three-level role taxonomy."""
        records: list[dict[str, Any]] = []
        jobs_by_id = {**self._load_jobs(), **self._load_state()["custom_jobs"]}
        for job in jobs_by_id.values():
            # Build the graph from the same merged view used by the recruitment UI.
            # This makes saved JD skill overrides visible to the taxonomy refresh.
            view = self._job_view(job)
            category, direction, role, needs_review = self._normalized_standard_role(job)
            records.append({
                "standard_category": category,
                "standard_role": role,
                "standard_direction": direction,
                "skills": _list(view.get("requiredSkills")),
                "needs_review": needs_review,
                "job_id": view["id"],
                "publish_time": job.get("publish_time"),  # 新增：把 publish_time 传出来
            })
        return records

    @staticmethod
    def _normalized_standard_role(job: dict[str, Any]) -> tuple[str, str, str, bool]:
        from app.services.role_taxonomy import (
            get_standard_role_taxonomy,
            infer_government_tech_role,
            refine_standard_role,
        )

        category = str(job.get("standard_category") or "").strip()
        role = str(job.get("standard_job") or job.get("job_family") or "").strip()
        direction = str(job.get("standard_direction") or "").strip()
        needs_review = False
        if not category or not role:
            existing_taxonomy = get_standard_role_taxonomy(role) if role else None
            if existing_taxonomy:
                category, direction = existing_taxonomy
            else:
                metadata = job.get("search_metadata") if isinstance(job.get("search_metadata"), dict) else {}
                category, direction, role = infer_government_tech_role(metadata.get("tech_filter_categories"))
                # Keep the evidence-derived direction so government technical posts
                # participate in the same two-level family structure as enterprise jobs.
            needs_review = True
        role = refine_standard_role(
            category,
            role,
            title=str(job.get("title") or ""),
            skills=job.get("required_skills") or job.get("skills"),
            description=str(job.get("description") or ""),
        )
        if role != str(job.get("standard_job") or job.get("job_family") or "").strip():
            direction = ""
        return category, direction, role, needs_review

    def list_standard_role_jobs(
        self,
        category: str,
        direction: str,
        role: str,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Return live JD views belonging to one standard-role node."""
        from app.services.role_taxonomy import get_canonical_taxonomy

        requested_category = str(category or "").strip()
        requested_direction = str(direction or "").strip()
        requested_role = str(role or "").strip()
        jobs_by_id = {**self._load_jobs(), **self._load_state()["custom_jobs"]}
        matched: list[dict[str, Any]] = []

        for raw_job in jobs_by_id.values():
            raw_category, raw_direction, raw_role, _ = self._normalized_standard_role(raw_job)
            canonical_category, inferred_direction = get_canonical_taxonomy(raw_category, raw_role)
            normalized_direction = raw_direction or inferred_direction
            if raw_role != requested_role:
                continue
            if canonical_category != requested_category or normalized_direction != requested_direction:
                continue
            matched.append(self._job_view(raw_job))

        matched.sort(key=lambda item: (str(item.get("title") or ""), str(item.get("id") or "")))
        return {
            "items": matched[offset : offset + limit],
            "total": len(matched),
            "limit": limit,
            "offset": offset,
            "standardCategory": requested_category,
            "standardDirection": requested_direction,
            "standardRole": requested_role,
            "source": "live-standard-dataset",
        }

    def save_job(self, job_id: str, values: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            state = self._load_state()
            existing = self._load_jobs().get(job_id) or state["custom_jobs"].get(job_id)
            if existing is None:
                custom = {**values, "job_id": job_id, "id": job_id, "source_type": "enterprise", "source": "enterprise_manual"}
                state["custom_jobs"][job_id] = custom
            else:
                allowed = {
                    "title", "department", "location", "employmentType", "openings", "status",
                    "summary", "description", "responsibilities", "requiredSkills", "required_skills",
                    "bonusSkills", "new_skills", "version", "roleVersion", "publishedAt", "updatedAt",
                    "revisions", "marketSuggestion",
                }
                state["job_overrides"][job_id] = {
                    **state["job_overrides"].get(job_id, {}),
                    **{key: value for key, value in values.items() if key in allowed},
                }
            self._save_state()
            self._candidate_rankings.pop(job_id, None)
            return self.get_job(job_id) or self._job_view(state["custom_jobs"][job_id])

    @staticmethod
    def _profile_skills(profile: dict[str, Any]) -> list[str]:
        return _list(profile.get("skills_normalized") or profile.get("skills"))

    @staticmethod
    def _profile_project_skills(profile: dict[str, Any]) -> list[str]:
        values: list[str] = []
        for field in ("projects", "experience"):
            records = profile.get(field)
            if not isinstance(records, list):
                continue
            for record in records:
                if not isinstance(record, dict):
                    continue
                for key in ("tech_stack", "keywords"):
                    values.extend(_list(record.get(key)))
        return list(dict.fromkeys(values))

    @staticmethod
    def _experience_fit(years: float, required_years: int) -> float:
        if required_years <= 0:
            return min(1.0, 0.72 + min(years, 8) * 0.035)
        if years < required_years:
            return max(0.0, years / required_years)
        if years <= required_years + 2:
            return 1.0
        return max(0.72, 1.0 - (years - required_years - 2) * 0.035)

    @staticmethod
    def _score_band(score: float, threshold: float) -> str:
        if score >= threshold + 10:
            return "高度匹配"
        if score >= threshold:
            return "进入候选池"
        if score >= max(50.0, threshold - 15):
            return "待人工复核"
        return "未达准入线"

    @staticmethod
    def _recommended_threshold(ranked: list[dict[str, Any]]) -> float:
        if not ranked:
            return 55.0
        boundary_index = min(19, len(ranked) - 1)
        return round(max(0.0, min(100.0, float(ranked[boundary_index]["score"]))), 2)

    def _score_candidate(
        self,
        profile: dict[str, Any],
        job: dict[str, Any],
        *,
        job_skills: list[str] | None = None,
        required_years: int | None = None,
        stages: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        candidate_id = str(profile.get("candidate_id") or profile.get("resume_id") or "")
        if job_skills is None:
            job_skills = _list(
                job.get("requiredSkills")
                or job.get("required_skills")
                or job.get("skills")
            )
        profile_skills = self._profile_skills(profile)
        profile_by_key = {_key(skill): skill for skill in profile_skills}
        job_by_key = {_key(skill): skill for skill in job_skills}
        matched_keys = profile_by_key.keys() & job_by_key.keys()
        matched = [job_by_key[key] for key in job_by_key if key in matched_keys]
        missing = [job_by_key[key] for key in job_by_key if key not in matched_keys]
        job_keys = list(job_by_key)
        job_weights = {
            key: 1.35 - min(index, 10) * 0.035 for index, key in enumerate(job_keys)
        }
        skill_levels = profile.get("skill_levels") if isinstance(profile.get("skill_levels"), dict) else {}
        level_weights = {"精通": 1.0, "熟练": 0.95, "掌握": 0.9, "了解": 0.68}
        weighted_total = sum(job_weights.values()) or 1.0
        weighted_matched = 0.0
        focus_matched = 0.0
        profile_positions = {_key(skill): index for index, skill in enumerate(profile_skills)}
        for key in matched_keys:
            source_skill = profile_by_key[key]
            proficiency = level_weights.get(str(skill_levels.get(source_skill) or ""), 0.82)
            weighted_matched += job_weights.get(key, 1.0) * proficiency
            position = profile_positions.get(key, len(profile_skills))
            focus_matched += job_weights.get(key, 1.0) * max(0.58, 1.0 - position * 0.025)
        skill_score = weighted_matched / weighted_total
        skill_focus_score = focus_matched / weighted_total

        project_keys = {_key(skill) for skill in self._profile_project_skills(profile)}
        project_matched = set(job_by_key) & project_keys
        if project_keys:
            project_score = sum(job_weights.get(key, 1.0) for key in project_matched) / weighted_total
        else:
            project_score = skill_score * 0.8

        target_family = _key(profile.get("target_job_family"))
        job_family = _key(job.get("job_family") or job.get("standard_job"))
        profile_category = _key(profile.get("standard_category"))
        job_category = _key(job.get("standard_category"))
        if target_family and target_family == job_family:
            family_score = 1.0
        elif profile_category and profile_category == job_category:
            family_score = 0.75
        elif target_family and job_family and (target_family in job_family or job_family in target_family):
            family_score = 0.6
        else:
            family_score = 0.0

        years = float(profile.get("years_experience") or 0)
        if required_years is None:
            required_years = self._required_experience(job)
        experience_score = self._experience_fit(years, required_years)
        family_similarity = SequenceMatcher(None, target_family, job_family).ratio() if target_family and job_family else 0.0
        text_score = max(family_similarity, family_score * 0.9)
        score_breakdown = {
            "weighted_skill": min(1.0, skill_score),
            "skill_focus": min(1.0, skill_focus_score),
            "job_family": family_score,
            "project_evidence": min(1.0, project_score),
            "experience": experience_score,
            "text_relevance": min(1.0, text_score),
        }
        final_score = min(
            1.0,
            0.42 * score_breakdown["weighted_skill"]
            + 0.13 * score_breakdown["skill_focus"]
            + 0.20 * score_breakdown["job_family"]
            + 0.12 * score_breakdown["project_evidence"]
            + 0.08 * score_breakdown["experience"]
            + 0.05 * score_breakdown["text_relevance"],
        )
        education = profile.get("education") if isinstance(profile.get("education"), dict) else {}
        degree = str(education.get("education") or education.get("degree") or "学历未标注")
        major = str(education.get("major") or "")
        candidate_root = re.sub(r"_exp\d+_\d+$", "", candidate_id)
        candidate_label = candidate_root.rsplit("_", 1)[-1] or candidate_id[-8:]
        confidence = round(
            min(97.0, 62 + skill_score * 15 + project_score * 9 + family_score * 7 + min(len(profile_skills), 20) * 0.2),
            1,
        )
        job_id = str(job.get("job_id") or job.get("id") or "")
        stage_lookup = stages if stages is not None else self._load_state()["candidate_stages"]
        stage = stage_lookup.get(f"{job_id}::{candidate_id}", "待筛选")
        reason = (
            f"匹配到 {len(matched)}/{max(1, len(job_skills))} 项岗位技能"
            f"，岗位方向匹配度 {round(family_score * 100)}%，经验要求匹配度 {round(experience_score * 100)}%。"
        )
        return {
            "id": candidate_id,
            "candidate_id": candidate_id,
            "name": str(profile.get("name") or f"候选人 {candidate_label}"),
            "degree": " · ".join(item for item in (degree, major) if item),
            "experience": f"{years:g} 年" if years else "校招/无全职经验",
            "location": str(profile.get("preferred_location") or "地点未标注"),
            "score": round(final_score * 100, 2),
            "confidence": confidence,
            "status": stage,
            "appliedAt": "标准候选池",
            "resume": f"{candidate_id}.jsonl",
            "summary": str(profile.get("summary") or profile.get("profile_text") or "")[:360],
            "matchedSkills": matched[:12],
            "gaps": missing[:12],
            "dimensions": [
                {"label": "加权技能", "value": round(skill_score * 100)},
                {"label": "技能优先级", "value": round(skill_focus_score * 100)},
                {"label": "岗位方向", "value": round(family_score * 100)},
                {"label": "项目证据", "value": round(project_score * 100)},
                {"label": "经验层级", "value": round(experience_score * 100)},
            ],
            "evidence": [
                reason,
                f"简历标准技能：{'、'.join(profile_skills[:8]) or '未提取'}。",
                f"岗位必备技能：{'、'.join(job_skills[:8]) or '未标注'}。",
            ],
            "recommendation": reason,
            "scoreBreakdown": {key: round(value * 100, 2) for key, value in score_breakdown.items()},
            "dataSource": "live-explainable-retrieval-v2",
            "_has_signal": bool(matched or family_score >= 0.6),
            "_sort": (final_score, project_score, skill_focus_score, experience_score, confidence),
        }

    def _rank_candidates(self, job_id: str, job: dict[str, Any]) -> list[dict[str, Any]]:
        cached = self._candidate_rankings.get(job_id)
        if cached is not None:
            return cached
        state = self._load_state()
        job_view = self._job_view(job)
        job_skills = [item["name"] for item in job_view["requiredSkills"]]
        required_years = self._required_experience(job)
        fusion_record = self._load_fusion_index().get(job_id)
        if fusion_record and job_id not in state["job_overrides"]:
            ranked: list[dict[str, Any]] = []
            for hit in fusion_record.get("candidates") or []:
                candidate_id = str(hit.get("candidate_id") or "")
                profile = self._get_profile(candidate_id)
                if profile is None:
                    continue
                item = self._score_candidate(
                    profile,
                    job,
                    job_skills=job_skills,
                    required_years=required_years,
                    stages=state["candidate_stages"],
                )
                bm25_rank = int(hit.get("bm25_rank") or 0)
                semantic_rank = int(hit.get("text2vec_rank") or 0)
                graph_rank = int(hit.get("graph_rank") or 0)
                bm25_percent = round(100 * 61 / (60 + bm25_rank), 2) if bm25_rank else 0.0
                semantic_percent = round(float(hit.get("text2vec_raw_score") or 0) * 100, 2)
                graph_percent = round(float(hit.get("graph_score") or 0) * 100, 2)
                fusion_score = round(float(hit.get("fusion_score") or 0), 2)
                graph_matched = _list(hit.get("matched_skills"))
                graph_missing = _list(hit.get("missing_skills"))
                item.update(
                    {
                        "score": fusion_score,
                        "confidence": round(
                            min(97.0, 55 + int(hit.get("channel_count") or 0) * 9 + fusion_score * 0.12),
                            1,
                        ),
                        "matchedSkills": graph_matched or item["matchedSkills"],
                        "gaps": graph_missing or item["gaps"],
                        "dimensions": [
                            {"label": "BM25关键词", "value": round(bm25_percent)},
                            {"label": "text2vec向量", "value": round(semantic_percent)},
                            {"label": "知识图谱", "value": round(graph_percent)},
                            {"label": "三路融合", "value": round(fusion_score)},
                        ],
                        "scoreBreakdown": {
                            "bm25": bm25_percent,
                            "text2vec": semantic_percent,
                            "knowledge_graph": graph_percent,
                            "fusion": fusion_score,
                        },
                        "channelRanks": {
                            "bm25": bm25_rank or None,
                            "text2vec": semantic_rank or None,
                            "knowledge_graph": graph_rank or None,
                        },
                        "channelCount": int(hit.get("channel_count") or 0),
                        "evidence": [
                            f"BM25 岗位到候选人排名：{bm25_rank or '未进入该路召回'}。",
                            f"text2vec 余弦相似度：{semantic_percent:.2f}%，排名：{semantic_rank or '未进入该路召回'}。",
                            f"Neo4j 图谱匹配度：{graph_percent:.2f}%，排名：{graph_rank or '未进入该路召回'}。",
                            *(_list(hit.get("evidence_paths"))[:3]),
                        ],
                        "recommendation": (
                            f"BM25、text2vec 与 Neo4j 三路 RRF 融合得分 {fusion_score:.2f}，"
                            f"共有 {int(hit.get('channel_count') or 0)} 路提供有效召回证据。"
                        ),
                        "dataSource": "job-to-candidate-three-channel-fusion-v1",
                        "retrievalMethod": str(fusion_record.get("retrieval_mode") or ""),
                        "candidateUnionSize": int(fusion_record.get("candidate_union_size") or len(ranked)),
                        "retrievalRank": int(hit.get("fusion_rank") or len(ranked) + 1),
                        "_has_signal": True,
                        "_sort": (
                            fusion_score,
                            int(hit.get("channel_count") or 0),
                            semantic_percent,
                            graph_percent,
                        ),
                    }
                )
                ranked.append(item)
            ranked.sort(key=lambda item: item["_sort"], reverse=True)
            for rank, item in enumerate(ranked, start=1):
                item["retrievalRank"] = rank
                item.pop("_sort", None)
                item.pop("_has_signal", None)
            self._candidate_rankings[job_id] = ranked
            return ranked

        ranked = [
            self._score_candidate(
                profile,
                job,
                job_skills=job_skills,
                required_years=required_years,
                stages=state["candidate_stages"],
            )
            for profile in self._load_profiles()
        ]
        ranked = [item for item in ranked if item.pop("_has_signal", False)]
        ranked.sort(key=lambda item: item["_sort"], reverse=True)
        for rank, item in enumerate(ranked, start=1):
            item["retrievalRank"] = rank
            item.pop("_sort", None)
        if len(self._candidate_rankings) >= 2:
            self._candidate_rankings.pop(next(iter(self._candidate_rankings)))
        self._candidate_rankings[job_id] = ranked
        return ranked

    def match_candidates(
        self,
        job_id: str,
        limit: int | None = None,
        *,
        min_score: float = 55.0,
        page: int = 1,
        page_size: int = 50,
        include_below_threshold: bool = False,
    ) -> dict[str, Any] | None:
        started = time.perf_counter()
        if limit is not None:
            page_size = limit
        job = self._load_jobs().get(job_id) or self._load_state()["custom_jobs"].get(job_id)
        if job is None:
            return None
        state = self._load_state()
        job_view = self._job_view(job)
        ranked = self._rank_candidates(job_id, job)
        fusion_record = self._load_fusion_index().get(job_id)
        uses_fusion = bool(fusion_record and job_id not in state["job_overrides"])
        recommended_threshold = self._recommended_threshold(ranked)
        recommended_pool_count = sum(
            1 for item in ranked if item["score"] >= recommended_threshold
        )
        eligible_count = sum(1 for item in ranked if item["score"] >= min_score)
        selected_pool = ranked if include_below_threshold else ranked[:eligible_count]
        total_pages = max(1, (len(selected_pool) + page_size - 1) // page_size)
        page = min(page, total_pages)
        offset = (page - 1) * page_size
        items: list[dict[str, Any]] = []
        for cached in selected_pool[offset : offset + page_size]:
            item = dict(cached)
            item["status"] = state["candidate_stages"].get(
                f"{job_id}::{item['candidate_id']}", "待筛选"
            )
            item["isEligible"] = item["score"] >= min_score
            item["decisionBand"] = self._score_band(item["score"], min_score)
            items.append(item)
        scores = [float(item["score"]) for item in ranked]
        stage_counts = Counter(
            state["candidate_stages"].get(f"{job_id}::{item['candidate_id']}", "待筛选")
            for item in ranked[:eligible_count]
        )
        return {
            "job": job_view,
            "items": items,
            "total_candidates": len(self._load_profiles()),
            "returned": len(items),
            "method": (
                "job_to_candidate_rrf_bm25_text2vec_neo4j_v1"
                if uses_fusion
                else "explainable_candidate_retrieval_v2"
            ),
            "source": "canonical_dataset",
            "stage_counts": dict(stage_counts),
            "retrieval_stats": {
                "total_profiles": len(self._load_profiles()),
                "initial_recall_count": (
                    int(fusion_record.get("candidate_union_size") or len(ranked))
                    if uses_fusion
                    else len(ranked)
                ),
                "reranked_count": len(ranked),
                "eligible_count": eligible_count,
                "filtered_out_count": len(ranked) - eligible_count,
                "threshold": min_score,
                "recommended_threshold": recommended_threshold,
                "recommended_pool_count": recommended_pool_count,
                "threshold_mode": (
                    "fusion_top20_boundary"
                    if uses_fusion
                    else "job_score_distribution"
                ),
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "score_max": round(max(scores), 1) if scores else 0,
                "score_min": round(min(scores), 1) if scores else 0,
                "score_average": round(sum(scores) / len(scores), 1) if scores else 0,
                "took_ms": round((time.perf_counter() - started) * 1000, 2),
                "algorithm": (
                    "rrf_bm25_text2vec_neo4j_035_045_020"
                    if uses_fusion
                    else "weighted_skill_family_project_experience_v2"
                ),
            },
        }

    def update_candidate_stage(self, job_id: str, candidate_id: str, status: str) -> dict[str, str]:
        with self._lock:
            state = self._load_state()
            state["candidate_stages"][f"{job_id}::{candidate_id}"] = status
            self._save_state()
        return {"job_id": job_id, "candidate_id": candidate_id, "status": status}

    def _get_profile(self, candidate_id: str) -> dict[str, Any] | None:
        if self._profiles_by_id is None:
            self._profiles_by_id = {
                str(profile.get("candidate_id") or profile.get("resume_id") or ""): profile
                for profile in self._load_profiles()
            }
        return self._profiles_by_id.get(candidate_id)

    @staticmethod
    def _project_evidence(profile: dict[str, Any], matched_skills: list[str]) -> list[str]:
        evidence: list[str] = []
        skill_keys = {_key(skill) for skill in matched_skills}
        for project in profile.get("projects") or []:
            if not isinstance(project, dict):
                continue
            stack = _list(project.get("tech_stack"))
            if skill_keys and not ({_key(skill) for skill in stack} & skill_keys):
                continue
            text = "；".join(
                str(project.get(field) or "").strip()
                for field in ("project_name", "description", "outcome")
                if str(project.get(field) or "").strip()
            )
            if text:
                evidence.append(text[:420])
            if len(evidence) >= 3:
                break
        return evidence

    def explain_candidate(
        self,
        job_id: str,
        candidate_id: str,
        *,
        use_llm: bool = True,
        min_score: float = 55.0,
    ) -> dict[str, Any] | None:
        job = self._load_jobs().get(job_id) or self._load_state()["custom_jobs"].get(job_id)
        profile = self._get_profile(candidate_id)
        if job is None or profile is None:
            return None
        ranked = self._rank_candidates(job_id, job)
        candidate = next((item for item in ranked if item["candidate_id"] == candidate_id), None)
        if candidate is None:
            return None

        project_evidence = self._project_evidence(profile, candidate["matchedSkills"])
        fallback = {
            "job_id": job_id,
            "candidate_id": candidate_id,
            "mode": "evidence_rag_fallback",
            "model": None,
            "conclusion": self._score_band(candidate["score"], min_score),
            "summary": candidate["recommendation"],
            "matched_evidence": [
                f"技能证据：{'、'.join(candidate['matchedSkills'][:8]) or '未发现明确命中'}",
                *project_evidence,
            ][:4],
            "skill_gaps": candidate["gaps"][:8],
            "risks": [
                "当前结论来自结构化画像，仍需核对简历原文和项目职责。",
                *(["关键技能覆盖不足，建议通过技术面试验证迁移能力。"] if candidate["gaps"] else []),
            ],
            "interview_questions": [
                f"请结合真实项目说明你如何使用 {skill}，以及最终效果如何。"
                for skill in (candidate["matchedSkills"][:2] or candidate["gaps"][:2])
            ],
            "grounded_context": {
                "job_excerpt": str(job.get("description") or "")[:700],
                "resume_excerpt": str(profile.get("summary") or profile.get("profile_text") or "")[:700],
                "project_evidence": project_evidence,
            },
            "warning": None,
        }
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not use_llm or not api_key:
            if use_llm and not api_key:
                fallback["warning"] = "DEEPSEEK_API_KEY 未配置，已返回本地可追溯解释。"
            return fallback

        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        retrieval_version = str(candidate.get("dataSource") or "baseline")
        cache_key = f"candidate_rag_v2::{retrieval_version}::{job_id}::{candidate_id}::{model}"
        cached = self._load_state()["candidate_explanations"].get(cache_key)
        if isinstance(cached, dict):
            return cached

        from urllib.request import Request, urlopen

        prompt_context = {
            "job": {
                "job_id": job_id,
                "title": job.get("title") or job.get("standard_job"),
                "job_family": job.get("job_family"),
                "required_skills": _list(job.get("required_skills") or job.get("skills")),
                "description": str(job.get("description") or "")[:1600],
            },
            "candidate": {
                "candidate_id": candidate_id,
                "target_job_family": profile.get("target_job_family"),
                "years_experience": profile.get("years_experience"),
                "skills": self._profile_skills(profile),
                "summary": str(profile.get("summary") or profile.get("profile_text") or "")[:1800],
                "project_evidence": project_evidence,
            },
            "deterministic_result": {
                "score": candidate["score"],
                "score_breakdown": candidate["scoreBreakdown"],
                "matched_skills": candidate["matchedSkills"],
                "missing_skills": candidate["gaps"],
            },
        }
        payload = {
            "model": model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是企业招聘证据解释器。只能使用给定证据，不得改变确定性匹配分。"
                        "返回 JSON，字段必须为 conclusion、summary、matched_evidence、skill_gaps、risks、interview_questions。"
                        "matched_evidence 必须引用输入中真实存在的技能或项目证据。"
                    ),
                },
                {"role": "user", "content": json.dumps(prompt_context, ensure_ascii=False)},
            ],
        }
        url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/") + "/chat/completions"
        try:
            request = Request(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                method="POST",
            )
            with urlopen(request, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = str(body["choices"][0]["message"]["content"]).strip()
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.I)
            generated = json.loads(content)
            result = {
                **fallback,
                "mode": "deepseek_grounded_rag_v1",
                "model": body.get("model") or model,
                "conclusion": str(generated.get("conclusion") or fallback["conclusion"]),
                "summary": str(generated.get("summary") or fallback["summary"]),
                "matched_evidence": _list(generated.get("matched_evidence"))[:6] or fallback["matched_evidence"],
                "skill_gaps": _list(generated.get("skill_gaps"))[:8] or fallback["skill_gaps"],
                "risks": _list(generated.get("risks"))[:6] or fallback["risks"],
                "interview_questions": _list(generated.get("interview_questions"))[:6] or fallback["interview_questions"],
                "warning": None,
            }
            with self._lock:
                self._load_state()["candidate_explanations"][cache_key] = result
                self._save_state()
            return result
        except Exception as exc:
            fallback["warning"] = f"DeepSeek 调用失败，已回退本地解释：{exc}"
            return fallback

    def market_stats(self) -> dict[str, Any]:
        jobs = list(self._load_jobs().values())
        source_counts = Counter(str(job.get("source_type") or "unknown") for job in jobs)
        family_counts = Counter(str(job.get("job_family") or job.get("standard_job") or "未分类") for job in jobs)
        skill_counts: Counter[str] = Counter()
        year_counts: Counter[str] = Counter()
        for job in jobs:
            skill_counts.update(_list(job.get("required_skills") or job.get("skills")))
            match = re.search(r"20\d{2}", str(job.get("publish_time") or ""))
            if match:
                year_counts[match.group(0)] += 1
        return {
            "total_jobs": len(jobs),
            "source_type_counts": dict(source_counts),
            "top_job_families": [{"name": name, "count": count} for name, count in family_counts.most_common(20)],
            "top_skills": [{"name": name, "count": count} for name, count in skill_counts.most_common(30)],
            "publish_year_counts": dict(sorted(year_counts.items())),
            "source": "canonical_dataset",
        }