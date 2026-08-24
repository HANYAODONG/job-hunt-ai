"""Persist and retrieve the before/after effect of a confirmed JD update."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pandas as pd

from .paths import BASE_DATABASE, GOVERNMENT_BASE_DATABASE, domain_file, resolve_domain


def capture_current_job_profile(domain: str, standard_job: str) -> list[dict[str, Any]]:
    path = domain_file(domain, "current")
    if not path.exists():
        return []
    frame = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    if frame.empty or "standard_job" not in frame.columns:
        return []
    rows = frame[frame["standard_job"].astype(str) == str(standard_job)].copy()
    if rows.empty:
        return []
    columns = [
        "skill", "kg_display_skill", "monthly_jd_count", "monthly_skill_count",
        "monthly_skill_frequency", "cumulative_jd_count", "cumulative_skill_count",
        "cumulative_skill_frequency", "snapshot_skill_status", "is_core_skill",
        "rank_in_month", "source_month", "source_type",
    ]
    for column in columns:
        if column not in rows.columns:
            rows[column] = ""
    rows["rank_in_month_sort"] = pd.to_numeric(rows["rank_in_month"], errors="coerce").fillna(999999)
    return rows.sort_values(["rank_in_month_sort", "skill"], kind="stable")[columns].to_dict(orient="records")


def build_live_update_effect(*, standard_job: str, standard_category: str, month: str,
                             before_profile: list[dict[str, Any]], after_profile: list[dict[str, Any]],
                             submitted_skills: list[str]) -> dict[str, Any]:
    before = {str(row.get("skill", "")).strip(): row for row in before_profile if str(row.get("skill", "")).strip()}
    after = {str(row.get("skill", "")).strip(): row for row in after_profile if str(row.get("skill", "")).strip()}
    changes: dict[str, list[dict[str, Any]]] = {key: [] for key in ("added", "increased", "decreased", "removed", "stable_core")}
    for skill in sorted(set(before) | set(after)):
        old, new = before.get(skill), after.get(skill)
        old_frequency = _number(old, "monthly_skill_frequency")
        new_frequency = _number(new, "monthly_skill_frequency")
        row = dict(new or old or {})
        row.update({"skill": skill, "from_monthly_skill_frequency": old_frequency if old else None,
                    "to_monthly_skill_frequency": new_frequency if new else None,
                    "frequency_delta": new_frequency - old_frequency})
        if old is None:
            changes["added"].append(row)
        elif new is None:
            changes["removed"].append(row)
        elif new_frequency > old_frequency:
            changes["increased"].append(row)
        elif new_frequency < old_frequency:
            changes["decreased"].append(row)
        elif _truthy(old.get("is_core_skill")) and _truthy(new.get("is_core_skill")):
            changes["stable_core"].append(row)
    signal_skills = list(dict.fromkeys(skill for skill in submitted_skills if skill))
    summary = {key: len(rows) for key, rows in changes.items()}
    summary["modified"] = summary["increased"] + summary["decreased"]
    summary["signal_skills"] = len(signal_skills)
    return {"standard_job": standard_job, "standard_category": standard_category, "month": month,
            "before_profile": before_profile, "after_profile": after_profile,
            "changes": changes, "signal_skills": signal_skills, "summary": summary}


def record_live_update_effect(domain: str, *, job_id: str, effect: dict[str, Any]) -> dict[str, Any]:
    database_path = GOVERNMENT_BASE_DATABASE if resolve_domain(domain) == "government" else BASE_DATABASE
    database_path.parent.mkdir(parents=True, exist_ok=True)
    effect_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    saved = {**effect, "effect_id": effect_id, "created_at": created_at}
    with sqlite3.connect(database_path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS job_update_effect_log (
                effect_id TEXT PRIMARY KEY, domain TEXT NOT NULL, job_id TEXT NOT NULL,
                standard_job TEXT NOT NULL, standard_category TEXT NOT NULL DEFAULT '', month TEXT NOT NULL,
                before_profile_json TEXT NOT NULL, after_profile_json TEXT NOT NULL,
                effect_json TEXT NOT NULL, created_at TEXT NOT NULL
            )
        """)
        connection.execute(
            "INSERT INTO job_update_effect_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (effect_id, resolve_domain(domain), job_id, effect["standard_job"], effect["standard_category"],
             effect["month"], json.dumps(effect["before_profile"], ensure_ascii=False),
             json.dumps(effect["after_profile"], ensure_ascii=False), json.dumps(saved, ensure_ascii=False), created_at),
        )
        connection.commit()
    return saved


def get_live_update_effect(domain: str, effect_id: str) -> dict[str, Any]:
    database_path = GOVERNMENT_BASE_DATABASE if resolve_domain(domain) == "government" else BASE_DATABASE
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT effect_json FROM job_update_effect_log WHERE effect_id = ? AND domain = ?",
            (effect_id, resolve_domain(domain)),
        ).fetchone()
    if row is None:
        raise KeyError(f"Live update effect not found: {effect_id}")
    return json.loads(row[0])


def _number(row: dict[str, Any] | None, key: str) -> float:
    try:
        return float((row or {}).get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def _truthy(value: object) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "y"}
