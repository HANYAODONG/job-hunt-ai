from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.services import analytics_service, government_job_service, job_service
from app.services.live_update_effect_service import get_live_update_effect
from app.services.profile_override_service import save_profile_overrides
from app.models.jd_update import (
    Domain,
    ExistingJobReviewInput,
    JdSubmitInput,
    JdSubmissionInput,
    NewJobReviewInput,
    ProfileOverrideInput,
    SkillReviewInput,
)


router = APIRouter()


def _domain_payload(payload: JdSubmissionInput) -> tuple[str, dict[str, Any]]:
    data = payload.model_dump()
    domain = data.pop("domain")
    return domain, data


def _service(domain: str):
    return government_job_service if domain == "government" else job_service


@router.get("/data-sources")
def data_sources(domain: Domain = "company") -> list[dict[str, Any]]:
    return analytics_service.data_sources(domain)


@router.post("/submissions/preview")
def preview(payload: JdSubmissionInput) -> dict[str, Any]:
    domain, data = _domain_payload(payload)
    try:
        return _service(domain).preview_one(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/submissions")
def submit(payload: JdSubmitInput) -> dict[str, Any]:
    service = _service(payload.domain)
    try:
        return service.submit_preview(payload.preview_id, payload.processing_mode)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/submissions/import")
async def import_csv(
    file: UploadFile = File(...),
    domain: Domain = Query("company"),
) -> dict[str, Any]:
    try:
        frame = pd.read_csv(BytesIO(await file.read()), dtype=str, encoding="utf-8-sig").fillna("")
        return _service(domain).import_csv(frame)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/reviews")
def reviews(domain: Domain = Query("company")) -> list[dict[str, Any]]:
    return _service(domain).get_review_items()


@router.get("/live-evolution/{effect_id}")
def live_evolution(effect_id: str, domain: Domain = Query("company")) -> dict[str, Any]:
    try:
        return get_live_update_effect(domain, effect_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/reviews/{item_id}/reject")
def reject(item_id: str, domain: Domain = Query("company")) -> dict[str, Any]:
    try:
        return _service(domain).reject_update(item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reviews/{item_id}/confirm-existing")
def confirm_existing(
    item_id: str,
    payload: ExistingJobReviewInput,
    domain: Domain = Query("company"),
) -> dict[str, Any]:
    try:
        if domain == "government":
            return government_job_service.confirm_existing(
                item_id,
                standard_job_title=payload.standard_job_title,
                skills=payload.skills,
            )
        return job_service.confirm_existing(
            item_id,
            merge_database=True,
            standard_job_title=payload.standard_job_title,
            standard_category=payload.standard_category,
            skills=payload.skills,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reviews/{item_id}/submit-new-job-proposal")
def submit_new_job_proposal(
    item_id: str,
    payload: NewJobReviewInput,
    domain: Domain = Query("company"),
) -> dict[str, Any]:
    try:
        if domain == "government":
            return government_job_service.confirm_new_job(
                item_id,
                standard_category=payload.standard_category,
                standard_job_title=payload.standard_job_title,
                match_keywords=payload.match_keywords,
            )
        return job_service.confirm_new_job(
            item_id,
            standard_category=payload.standard_category,
            standard_job_title=payload.standard_job_title,
            match_keywords=payload.match_keywords,
            merge_database=True,
            skills=payload.skills,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reviews/{item_id}/review-skill")
def review_skill(
    item_id: str,
    payload: SkillReviewInput,
    domain: Domain = Query("company"),
) -> dict[str, Any]:
    try:
        return _service(domain).review_skill(
            item_id,
            decision=payload.decision,
            normalized_skill=payload.normalized_skill,
            kg_display_skill=payload.kg_display_skill,
            skill_type=payload.skill_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/analytics/jobs")
def analytics_jobs(domain: Domain = Query("company"), source_key: str | None = None) -> list[str]:
    return analytics_service.list_jobs(domain, source_key=source_key)


@router.get("/analytics/months")
def analytics_months(domain: Domain = Query("company"), source_key: str | None = None) -> list[str]:
    return analytics_service.list_months(domain, source_key=source_key)


@router.get("/analytics/overview")
def analytics_overview(domain: Domain = Query("company"), source_key: str | None = None) -> dict[str, Any]:
    return analytics_service.overview(domain, source_key=source_key)


@router.get("/analytics/job-trend")
def analytics_job_trend(
    standard_job: str | None = None,
    top_n: int = 8,
    month_start: str | None = None,
    month_end: str | None = None,
    domain: Domain = Query("company"),
    source_key: str | None = None,
) -> dict[str, Any]:
    return analytics_service.job_trend(
        standard_job,
        top_n=top_n,
        month_start=month_start,
        month_end=month_end,
        domain=domain,
        source_key=source_key,
    )


@router.get("/analytics/lifecycle")
def analytics_lifecycle(
    standard_job: str | None = None,
    status: str | None = None,
    limit: int = 120,
    domain: Domain = Query("company"),
    source_key: str | None = None,
) -> dict[str, Any]:
    return analytics_service.lifecycle(standard_job, status, limit, domain, source_key)


@router.get("/analytics/skill-migration")
def analytics_skill_migration(
    skill: str | None = None,
    limit: int = 20,
    domain: Domain = Query("company"),
    source_key: str | None = None,
) -> dict[str, Any]:
    return analytics_service.migration(skill, limit, domain, source_key)


@router.get("/analytics/monthly-rank")
def analytics_monthly_rank(
    month: str | None = None,
    rank_type: str = Query("emerging", alias="type"),
    standard_job: str | None = None,
    limit: int = 20,
    domain: Domain = Query("company"),
    source_key: str | None = None,
) -> dict[str, Any]:
    return analytics_service.monthly_rank(month, rank_type, standard_job, limit, domain, source_key)


@router.get("/analytics/profile-compare")
def analytics_profile_compare(
    standard_job: str | None = None,
    from_month: str | None = None,
    to_month: str | None = None,
    limit: int = 80,
    domain: Domain = Query("company"),
    source_key: str | None = None,
) -> dict[str, Any]:
    return analytics_service.profile_compare(standard_job, from_month, to_month, limit, domain, source_key)


@router.get("/optimization/profile")
def optimization_profile(
    standard_job: str | None = None,
    limit: int = 500,
    domain: Domain = Query("company"),
    source_key: str | None = None,
) -> dict[str, Any]:
    return analytics_service.optimization_profile(standard_job, limit, domain, source_key)


@router.get("/optimization/normalize-skill")
def normalize_skill(skill: str, domain: Domain = Query("company")) -> dict[str, Any]:
    return analytics_service.normalize_optimization_skill(skill, domain)


@router.post("/optimization/overrides")
def optimization_overrides(
    payload: ProfileOverrideInput,
    domain: Domain = Query("company"),
) -> dict[str, Any]:
    try:
        return save_profile_overrides(
            domain=domain,
            standard_job=payload.standard_job,
            changes=payload.changes,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/optimization/sources")
def optimization_sources(
    keyword: str | None = None,
    scope: str | None = None,
    limit: int = 80,
    domain: Domain = Query("company"),
) -> dict[str, Any]:
    return analytics_service.optimization_sources(keyword, scope, limit, domain)
