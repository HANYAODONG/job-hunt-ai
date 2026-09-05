from __future__ import annotations

"""Source-backed new-role discovery workflow.

The discovery UI deliberately stops short of changing the formal role pool until
an operator publishes a reviewed definition.  This module owns that last
transition so the same source JD is retained as evidence and as a real market
event after publication.
"""

import csv
import json
import re
from collections import Counter, defaultdict
from typing import Any

from .backup_service import create_backup
from .job_service import (
    _build_system,
    _merge_summary,
    _posting_from_payload,
    _record_live_effect,
    confirm_new_job,
    reject_update,
    serialize_review_process_result,
)
from .paths import BASE_DATABASE, BASE_DATA_DIR, BASE_SKILL_POOL, BASE_TITLE_DICTIONARY
from .paths import BASE_EVENT_STREAM

from job_update.company_job_update.core.database import SQLiteJobUpdateStore
from job_update.company_job_update.core.review_queue import skill_mentions_from_decisions
from job_update.company_job_update.core.text import clean_text


_MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_FINAL_REVIEW_STATUSES = {"auto_merged", "merged_existing_job", "merged_new_job", "published_new_job"}


def list_candidates() -> list[dict[str, Any]]:
    """Return source-backed candidates in every discovery workflow stage."""
    store = SQLiteJobUpdateStore(BASE_DATABASE)
    jobs = store.list_review_items(status=None, review_type="job")
    maintenance = store.list_review_items(status=None, review_type="dictionary_maintenance")
    maintenance_by_source: dict[str, dict[str, Any]] = {}
    for item in maintenance:
        result = item.get("result", {})
        if result.get("proposal_type") != "new_standard_job":
            continue
        source_ids = result.get("source_job_review_ids") or [
            result.get("source_job_review_id") or item.get("parent_review_id")
        ]
        for source_id in source_ids:
            source_id = str(source_id or "").strip()
            if source_id:
                maintenance_by_source[source_id] = item

    rows: list[dict[str, Any]] = []
    known_sources: set[str] = set()
    for item in jobs:
        if item.get("status") in {"rejected", "merged_existing_job", "auto_merged"}:
            continue
        route = item.get("result", {}).get("route") or {}
        if route.get("status") == "existing_job" and item.get("status") == "pending":
            continue
        source_id = str(item["item_id"])
        known_sources.add(source_id)
        linked = maintenance_by_source.get(source_id)
        if linked and linked.get("status") == "rejected":
            continue
        rows.append(_candidate_from_job(item, linked))

    # Keep a maintenance item visible even if its source review was archived.
    for item in maintenance:
        if item.get("result", {}).get("proposal_type") != "new_standard_job":
            continue
        if item.get("status") == "rejected":
            continue
        source_id = str(item.get("result", {}).get("source_job_review_id") or item.get("parent_review_id") or "")
        if source_id and source_id in known_sources:
            continue
        rows.append(_candidate_from_maintenance(item))
    return sorted(rows, key=lambda row: (row["stage_order"], row["updated_at"]), reverse=True)


def clear_imported_month(month: str) -> dict[str, Any]:
    """Remove one month's unpublished imported-review batch.

    This only clears evidence sitting in ``review_queue``.  It never alters
    the canonical directory, event stream, job postings, skill analytics, or
    any candidate that has already been merged into formal state.
    """
    selected_month = clean_text(month)
    if not _MONTH_PATTERN.fullmatch(selected_month):
        raise ValueError("month must use YYYY-MM format")

    store = SQLiteJobUpdateStore(BASE_DATABASE)
    rows = store.list_review_items(status=None)
    by_id = {str(row["item_id"]): row for row in rows}

    source_ids = {
        item_id
        for item_id, item in by_id.items()
        if _is_clearable_monthly_import(item, selected_month)
    }

    # A maintenance proposal can refer to several source JDs.  It is safe to
    # delete it only when every linked source belongs to this selected batch;
    # otherwise leave both the proposal and its shared evidence intact.
    delete_ids = set(source_ids)
    protected_ids: set[str] = set()
    changed = True
    while changed:
        changed = False
        for item_id, item in by_id.items():
            if item_id in delete_ids or item.get("status") in _FINAL_REVIEW_STATUSES:
                continue
            parent_id = clean_text(item.get("parent_review_id"))
            if parent_id and parent_id in delete_ids:
                delete_ids.add(item_id)
                changed = True
                continue
            if item.get("review_type") != "dictionary_maintenance":
                continue
            linked_source_ids = _maintenance_source_ids(item)
            if linked_source_ids and linked_source_ids.issubset(source_ids):
                delete_ids.add(item_id)
                changed = True
            elif linked_source_ids & source_ids:
                protected_ids.add(item_id)

    deleted_rows = store.delete_review_items(sorted(delete_ids))
    deleted_items = [by_id[item_id] for item_id in deleted_rows]
    return {
        "month": selected_month,
        "deleted_review_items": len(deleted_rows),
        "deleted_candidates": sum(1 for item in deleted_items if item.get("review_type") == "job"),
        "deleted_maintenance_items": sum(1 for item in deleted_items if item.get("review_type") == "dictionary_maintenance"),
        "protected_shared_proposals": len(protected_ids),
        "production_state_changed": False,
        "canonical_role_pool_changed": False,
        "event_stream_changed": False,
    }


def _is_clearable_monthly_import(item: dict[str, Any], month: str) -> bool:
    """Recognize a batch root without relying on an unstructured SQL match."""
    if item.get("review_type") != "job" or item.get("status") in _FINAL_REVIEW_STATUSES:
        return False
    source = item.get("input") or {}
    if clean_text(source.get("month")) != month:
        return False
    if clean_text(source.get("import_kind")) == "monthly_csv":
        return True
    # Imports created before batch tagging used the manual web source.  Keep a
    # narrow compatibility path for their still-pending, generated review
    # records so the existing August demonstration batch can be cleared.
    return (
        clean_text(source.get("source")) == "web_app_manual"
        and clean_text(item.get("submission_mode")) == "manual"
        and clean_text(item.get("status")) == "pending"
        and clean_text(item.get("job_id")).startswith("web_")
    )


def _maintenance_source_ids(item: dict[str, Any]) -> set[str]:
    result = item.get("result") or {}
    candidates = result.get("source_job_review_ids") or [
        result.get("source_job_review_id") or item.get("parent_review_id")
    ]
    return {clean_text(value) for value in candidates if clean_text(value)}


def batch_summary(
    month: str | None = None,
    *,
    threshold: int = 10,
    standard_job: str | None = None,
) -> dict[str, Any]:
    """Build a source-backed monthly discovery snapshot for the web workbench.

    This is intentionally read-only.  It reports the evidence currently present
    in the versioned event stream and review queue; it never promotes a cluster
    or writes a new role definition.
    """
    events = _read_event_stream()
    candidates = list_candidates()
    event_months = {str(row.get("month") or "").strip() for row in events if str(row.get("month") or "").strip()}
    review_months = {
        str((row.get("source") or {}).get("month") or "").strip()
        for row in candidates
        if str((row.get("source") or {}).get("month") or "").strip()
    }
    months = sorted(event_months | review_months)
    selected_month = str(month or "").strip() or (months[-1] if months else "")
    month_events = [row for row in events if str(row.get("month") or "").strip() == selected_month]
    unique_ids = {str(row.get("job_id") or "").strip() for row in month_events if str(row.get("job_id") or "").strip()}

    # The event stream is the source of truth for a monthly batch.  A batch can
    # be fully classified while producing no new-role candidate, so these
    # facts must not be inferred from the review queue below.
    classified_events = [row for row in month_events if clean_text(row.get("standard_job"))]
    unmapped_events = [row for row in month_events if not clean_text(row.get("standard_job"))]
    role_counts = Counter(clean_text(row.get("standard_job")) for row in classified_events)
    role_distribution = [
        {"standard_job": role, "jd_count": count}
        for role, count in role_counts.most_common(12)
    ]
    monthly_roles: dict[str, set[str]] = defaultdict(set)
    monthly_input_counts: Counter[str] = Counter()
    for row in events:
        event_month = clean_text(row.get("month"))
        if not event_month:
            continue
        monthly_input_counts[event_month] += 1
        role = clean_text(row.get("standard_job"))
        if role:
            monthly_roles[event_month].add(role)
    role_history = []
    cumulative_roles: set[str] = set()
    previous_roles: set[str] = set()
    for event_month in months:
        current_roles = monthly_roles[event_month]
        new_roles = current_roles - cumulative_roles
        cumulative_roles.update(current_roles)
        role_history.append({
            "month": event_month,
            "input_jd_count": monthly_input_counts[event_month],
            "monthly_role_count": len(current_roles),
            "new_role_count": len(new_roles),
            "cumulative_role_count": len(cumulative_roles),
            "new_roles": sorted(new_roles)[:20],
        })
    selected_history = next((item for item in role_history if item["month"] == selected_month), None)
    first_history = role_history[0] if role_history else None
    previous_history = None
    if selected_history:
        selected_index = role_history.index(selected_history)
        previous_history = role_history[selected_index - 1] if selected_index else None
    replay_is_flat = bool(first_history and first_history["new_role_count"] > 0 and all(item["new_role_count"] == 0 for item in role_history[1:]))
    focus_role = clean_text(standard_job)
    profile_history = []
    if focus_role:
        previous_skill_counts: Counter[str] = Counter()
        for event_month in months:
            profile_rows = [
                row for row in events
                if clean_text(row.get("month")) == event_month and clean_text(row.get("standard_job")) == focus_role
            ]
            skill_counts: Counter[str] = Counter()
            for row in profile_rows:
                skill_counts.update(_split_skill_field(row.get("skills")))
            new_skills = [skill for skill, count in skill_counts.most_common() if count > 0 and not previous_skill_counts.get(skill)][:8]
            rising_skills = [
                {"skill": skill, "count": count, "delta": count - previous_skill_counts.get(skill, 0)}
                for skill, count in skill_counts.most_common(8)
            ]
            profile_history.append({
                "month": event_month,
                "jd_count": len(profile_rows),
                "top_skills": rising_skills,
                "new_skills": new_skills,
                "sample_titles": [clean_text(row.get("job_title")) for row in profile_rows[:3] if clean_text(row.get("job_title"))],
            })
            previous_skill_counts = skill_counts
    sample_jds = []
    for row in month_events[:8]:
        sample_jds.append({
            "job_id": clean_text(row.get("job_id")),
            "job_title": clean_text(row.get("job_title")),
            "standard_job": clean_text(row.get("standard_job")) or "待归类",
            "month": selected_month,
            "skills": clean_text(row.get("skills"))[:240],
        })

    month_candidates = [
        row for row in candidates
        if not selected_month or str(row.get("source", {}).get("month") or "").strip() in {"", selected_month}
    ]
    # Newly uploaded monthly JD files first live in the review queue, before
    # any accepted posting is written to the formal event stream. Include
    # those source records in the batch counters so an upload immediately
    # becomes visible in the discovery workbench.
    queued_ids = {
        str((row.get("source") or {}).get("job_id") or row.get("candidate_id") or "").strip()
        for row in month_candidates
    }
    queued_ids.discard("")
    queued_unmapped = [row for row in month_candidates if row.get("route_status") != "existing_job"]
    input_jd_count = len(month_events) + len(queued_ids - unique_ids)
    deduplicated_jd_count = len(unique_ids | queued_ids)
    unmapped_jd_count = len(unmapped_events) + len(queued_ids - unique_ids)
    if not month_events and month_candidates:
        sample_jds = [
            {
                "job_id": str((row.get("source") or {}).get("job_id") or row.get("candidate_id") or ""),
                "job_title": str((row.get("source") or {}).get("job_title") or row.get("title") or ""),
                "standard_job": "待归类",
                "month": selected_month,
                "skills": "; ".join(str(skill) for skill in (row.get("skills") or [])[:8]),
            }
            for row in month_candidates[:8]
        ]
    # A candidate title is only a display grouping.  The source count and
    # threshold are shown explicitly so a repeated title cannot look like a
    # formally discovered role without enough independent evidence.
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in month_candidates:
        # Source candidates expose the raw title as ``title`` while a
        # maintenance proposal may expose a proposed ``name``.  Prefer the
        # proposal name, then fall back to the source title so synthetic and
        # real batches are clustered by their actual candidate identity.
        source_title = (candidate.get("source") or {}).get("job_title")
        cluster_title = candidate.get("name") or candidate.get("title") or source_title or "未命名岗位候选"
        grouped[str(cluster_title)].append(candidate)

    cluster_rows = []
    for index, (title, rows) in enumerate(sorted(grouped.items()), start=1):
        source_ids = {
            str(
                row.get("raw", {}).get("source", {}).get("job_id")
                or row.get("source", {}).get("job_id")
                or row.get("id")
                or row.get("candidate_id")
                or ""
            ).strip()
            for row in rows
        }
        source_ids.discard("")
        evidence_count = len(source_ids) or len(rows)
        threshold_met = evidence_count > int(threshold)
        stage = rows[0].get("status") or "待审核"
        cluster_rows.append({
            "cluster_id": f"DISC-{selected_month or 'unknown'}-{index:03d}",
            "title": title,
            "supporting_jd_count": evidence_count,
            "deduplicated_jd_count": evidence_count,
            "source_count": len(source_ids) or 1,
            "threshold": int(threshold),
            "threshold_met": threshold_met,
            "status": "待人工审核" if threshold_met else "观察中",
            "workflow_stage": stage,
            "candidate": rows[0],
            "review_item_ids": [
                str(row.get("candidate_id") or row.get("id") or "").strip()
                for row in rows
                if str(row.get("candidate_id") or row.get("id") or "").strip()
            ],
            "evidence": rows[:8],
        })

    return {
        "month": selected_month,
        "available_months": months,
        "input_jd_count": input_jd_count,
        "deduplicated_jd_count": deduplicated_jd_count,
        "classified_jd_count": len(classified_events),
        "unmapped_jd_count": unmapped_jd_count,
        "role_count": len(role_counts),
        "role_distribution": role_distribution,
        "sample_jds": sample_jds,
        "role_pool_evolution": {
            "first_month": first_history["month"] if first_history else "",
            "first_month_role_count": first_history["monthly_role_count"] if first_history else 0,
            "previous_month": previous_history["month"] if previous_history else "",
            "previous_role_count": previous_history["cumulative_role_count"] if previous_history else 0,
            "current_role_count": len(role_counts),
            "new_role_count": selected_history["new_role_count"] if selected_history else 0,
            "cumulative_role_count": selected_history["cumulative_role_count"] if selected_history else len(role_counts),
            "new_roles": selected_history["new_roles"] if selected_history else [],
            "history": role_history,
            "interpretation": (
                "事件流首月已覆盖当前全部标准岗位，后续月份未记录新增标准岗位；这是一份最终标签回填流，不能单独证明历史岗位池逐月扩张。"
                if replay_is_flat else
                "按事件流中标准岗位首次出现的月份回放岗位池增量。"
            ),
        },
        "role_profile_evolution": {
            "standard_job": focus_role,
            "history": profile_history,
            "interpretation": "同一三级岗位的标签保持不变时，使用 JD 数量、技能频率和标题样例观察岗位画像变化。" if focus_role else "请选择一个三级岗位查看岗位画像按月变化。",
        },
        "data_provenance": _data_provenance(),
        "batch_status": (
            "待人工审核" if month_candidates and not month_events else
            ("暂无数据" if not month_events else ("包含待归类记录" if unmapped_events else "已完成归类"))
        ),
        "cluster_count": len(cluster_rows),
        "trigger_threshold": int(threshold),
        "threshold_rule": "去重后的同类 JD 数量 > 10，且需保留来源证据后进入人工审核",
        "method": "版本化岗位事件流 + 审核队列候选信号（只读分析）",
        "candidates": cluster_rows,
        "guardrails": [
            "候选聚类不会自动写入正式岗位池",
            "正式三级岗位必须经过人工复核并分配 canonical_role_id",
            "同一来源重复抓取不能单独满足触发阈值",
        ],
    }


def _read_event_stream() -> list[dict[str, Any]]:
    if not BASE_EVENT_STREAM.exists():
        return []
    try:
        with BASE_EVENT_STREAM.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except (OSError, csv.Error):
        return []


def _split_skill_field(value: Any) -> list[str]:
    return [item for item in (clean_text(part) for part in re.split(r"[;,；，、|]+", str(value or ""))) if item]


def _data_provenance() -> dict[str, Any]:
    manifest_path = BASE_DATA_DIR / "version_manifest.json"
    try:
        with manifest_path.open("r", encoding="utf-8-sig") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError):
        manifest = {}
    kind = clean_text(manifest.get("kind"))
    generated = "generated" in kind.lower() or "baseline" in kind.lower()
    return {
        "version": clean_text(manifest.get("version")),
        "kind": kind,
        "source_event_stream": clean_text(manifest.get("source_event_stream")),
        "source_event_rows": manifest.get("source_event_rows", 0),
        "historical_role_pool_claim": "不可由此基准流确认真实岗位池逐月扩张" if generated else "可按事件流回放岗位首次出现时间",
    }


def submit_proposal(item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Move a source JD from candidate review to formal publication review."""
    return confirm_new_job(
        item_id,
        standard_category=payload.get("standard_category", ""),
        standard_job_title=payload.get("standard_job_title", ""),
        match_keywords=payload.get("match_keywords", ""),
        merge_database=False,
        skills=payload.get("skills") or [],
        definition={
            "core_responsibilities": _clean_list(payload.get("core_responsibilities")),
            "required_skills": _clean_list(payload.get("required_skills")),
            "bonus_skills": _clean_list(payload.get("bonus_skills")),
            "application_scenarios": _clean_list(payload.get("application_scenarios")),
            "evidence_note": clean_text(payload.get("evidence_note")),
        },
    )


def reject_candidate(item_id: str) -> dict[str, Any]:
    store = SQLiteJobUpdateStore(BASE_DATABASE)
    item = store.get_review_item(item_id)
    if item.get("review_type") == "dictionary_maintenance":
        result = item.get("result", {})
        source_id = str(result.get("source_job_review_id") or item.get("parent_review_id") or "")
        rejected = store.update_review_item(
            item_id,
            status="rejected",
            decision_payload={"action": "reject_new_job_maintenance"},
        )
        if source_id:
            store.update_review_item(
                source_id,
                status="rejected",
                decision_payload={"action": "reject_new_job_maintenance", "maintenance_id": item_id},
            )
        return rejected
    return reject_update(item_id)


def publish_candidate(maintenance_id: str) -> dict[str, Any]:
    """Publish a reviewed role and process its source JD as a real event."""
    store = SQLiteJobUpdateStore(BASE_DATABASE)
    maintenance = store.get_review_item(maintenance_id)
    if maintenance["review_type"] != "dictionary_maintenance":
        raise ValueError("Only a new-job maintenance item can be published")
    result = maintenance.get("result", {})
    if result.get("proposal_type") != "new_standard_job":
        raise ValueError("This maintenance item is not a new standard job proposal")

    source_ids = list(dict.fromkeys([
        str(source_id).strip()
        for source_id in (result.get("source_job_review_ids") or [
            result.get("source_job_review_id") or maintenance.get("parent_review_id")
        ])
        if str(source_id or "").strip()
    ]))
    if not source_ids:
        raise ValueError("The proposal has no source JD review")
    sources = [store.get_review_item(source_id) for source_id in source_ids]
    proposal = result.get("proposal") or {}
    title = clean_text(proposal.get("standard_job_title"))
    category = clean_text(proposal.get("standard_category"))
    keywords = clean_text(proposal.get("match_keywords")) or title
    if not title or not category:
        raise ValueError("A published job needs a title and category")

    backup = create_backup(f"publish new job {maintenance_id}")
    _append_dictionary_row(title, category, keywords)
    try:
        skills = result.get("skills") or sources[0].get("result", {}).get("skills") or []
        mentions = skill_mentions_from_decisions(skills)
        published_sources = []
        for source in sources:
            posting = _posting_from_payload(
                {**source["input"], "job_id": source["job_id"]},
                source="web_app_new_job_published",
            )
            posting.routing_job_title = clean_text(source.get("result", {}).get("routing_job_title"))
            posting.skills = mentions
            applied = _build_system([]).process(
                posting,
                write=True,
                confirmed_standard_job=title,
                confirmed_standard_category=category,
            )
            result_payload = serialize_review_process_result(applied, skill_pool_path=BASE_SKILL_POOL)
            result_payload["merge_result"] = _merge_summary(applied)
            result_payload["backup"] = backup
            result_payload["new_job_definition"] = result.get("definition") or {}
            result_payload["live_update_effect"] = _record_live_effect(
                posting=posting,
                standard_job=title,
                standard_category=category,
                before_profile=[],
                normalized_skills=applied.normalized_skills,
            )
            published_sources.append({"review_id": source["item_id"], "job_id": source["job_id"], "result": result_payload})
        store.upsert_standard_job(
            standard_job_title=title,
            standard_category=category,
            match_keywords=keywords,
        )
    except Exception:
        _remove_dictionary_row(title)
        raise

    published = store.update_review_item(
        maintenance_id,
        status="published_new_job",
        decision_payload={
            "action": "publish_new_job",
            "standard_job_title": title,
            "standard_category": category,
        },
        result_payload={**result, "published_result": {"source_count": len(published_sources), "sources": published_sources}},
    )
    for source, published_source in zip(sources, published_sources):
        store.update_review_item(
            source["item_id"],
            status="merged_new_job",
            decision_payload={
                "action": "publish_new_job",
                "standard_job_title": title,
                "standard_category": category,
            },
            result_payload=published_source["result"],
        )
    published["result"] = {**published.get("result", {}), "published_result": {"source_count": len(published_sources), "sources": published_sources}}
    return published


def _candidate_from_job(item: dict[str, Any], maintenance: dict[str, Any] | None) -> dict[str, Any]:
    result = item.get("result", {})
    route = result.get("route") or {}
    definition = (maintenance or {}).get("result", {}).get("definition") or _derive_definition(item)
    if item.get("status") == "merged_new_job":
        stage = "published"
    else:
        stage = "awaiting_publish" if maintenance else "candidate"
    proposal = (maintenance or {}).get("result", {}).get("proposal") or {}
    return {
        "candidate_id": item["item_id"],
        "maintenance_id": (maintenance or {}).get("item_id", ""),
        "stage": stage,
        "stage_order": {"candidate": 3, "awaiting_publish": 2, "published": 1}[stage],
        "status": item.get("status", "pending"),
        "updated_at": item.get("updated_at", ""),
        "source": _source_evidence(item),
        "source_count": 1,
        "title": proposal.get("standard_job_title") or item.get("input", {}).get("job_title", ""),
        "route_status": route.get("status", ""),
        "route_reason": route.get("reason", ""),
        "best_category": (route.get("best_category") or {}).get("name", ""),
        "best_job": (route.get("best_job") or {}).get("name", ""),
        "candidate_jobs": route.get("top_jobs") or route.get("selected_jobs") or [],
        "skills": result.get("skills") or [],
        "definition": definition,
    }


def _candidate_from_maintenance(item: dict[str, Any]) -> dict[str, Any]:
    result = item.get("result", {})
    proposal = result.get("proposal") or {}
    published = item.get("status") == "published_new_job"
    return {
        "candidate_id": result.get("source_job_review_id") or item.get("parent_review_id") or item["item_id"],
        "maintenance_id": item["item_id"],
        "stage": "published" if published else "awaiting_publish",
        "stage_order": 1 if published else 2,
        "status": item.get("status", "pending"),
        "updated_at": item.get("updated_at", ""),
        "source": {"job_id": item.get("job_id", ""), "job_title": proposal.get("standard_job_title", ""), "month": ""},
        "source_count": 1,
        "title": proposal.get("standard_job_title", ""),
        "route_status": "potential_new_job",
        "route_reason": "已提交新岗位定义，等待正式发布",
        "best_category": proposal.get("standard_category", ""),
        "best_job": "",
        "candidate_jobs": [],
        "skills": result.get("skills") or [],
        "definition": result.get("definition") or {},
    }


def _source_evidence(item: dict[str, Any]) -> dict[str, Any]:
    payload = item.get("input", {})
    return {
        "job_id": item.get("job_id", ""),
        "job_title": payload.get("job_title", ""),
        "month": payload.get("month", ""),
        "responsibility": payload.get("responsibility", ""),
        "requirement": payload.get("requirement", ""),
        "submission_mode": item.get("submission_mode", ""),
    }


def _derive_definition(item: dict[str, Any]) -> dict[str, Any]:
    payload = item.get("input", {})
    result = item.get("result", {})
    responsibilities = _clean_list(payload.get("responsibility"))[:5]
    if not responsibilities:
        responsibilities = ["待人工补充：原始 JD 未提供可拆分的岗位职责"]
    required: list[str] = []
    bonus: list[str] = []
    for skill in result.get("skills") or []:
        name = clean_text(skill.get("normalized_skill") or skill.get("raw_skill") or skill.get("skill"))
        if not name:
            continue
        target = bonus if skill.get("is_new_skill_candidate") or skill.get("is_low_confidence") else required
        if name not in required and name not in bonus:
            target.append(name)
    text = " ".join(str(payload.get(key) or "") for key in ("responsibility", "requirement"))
    scenario_hints = (
        ("大模型", "大模型应用与智能体系统"), ("智能体", "智能体应用与自动化工作流"),
        ("推荐", "推荐、搜索与内容分发"), ("风控", "风险识别与智能决策"),
        ("物联网", "物联网与边缘智能"), ("芯片", "芯片与智能硬件研发"),
        ("数据", "企业数据平台与数据治理"), ("云", "云平台与企业基础设施"),
        ("安全", "网络安全与合规治理"),
    )
    scenarios = [label for hint, label in scenario_hints if hint in text]
    return {
        "core_responsibilities": responsibilities,
        "required_skills": required[:12],
        "bonus_skills": bonus[:12],
        "application_scenarios": scenarios[:5] or ["待人工补充：原始 JD 未提供明确行业应用场景"],
        "evidence_note": "定义由原始 JD 的职责、要求和技能抽取结果生成，发布前需人工核验。",
    }


def _clean_list(value: Any) -> list[str]:
    if isinstance(value, str):
        values = value.replace("；", "\n").replace("。", "\n").splitlines()
    elif isinstance(value, list):
        values = value
    else:
        values = []
    result: list[str] = []
    for entry in values:
        text = clean_text(entry).lstrip("-•· ")
        if text and text not in result:
            result.append(text)
    return result


def _append_dictionary_row(title: str, category: str, keywords: str) -> None:
    with BASE_TITLE_DICTIONARY.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or ["standard_job_title", "standard_category", "match_keywords"])
        rows = list(reader)
    if any(clean_text(row.get("standard_job_title")) == title for row in rows):
        raise ValueError(f"标准岗位已存在：{title}")
    rows.append({"standard_job_title": title, "standard_category": category, "match_keywords": keywords})
    with BASE_TITLE_DICTIONARY.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _remove_dictionary_row(title: str) -> None:
    with BASE_TITLE_DICTIONARY.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = [row for row in reader if clean_text(row.get("standard_job_title")) != title]
    with BASE_TITLE_DICTIONARY.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
