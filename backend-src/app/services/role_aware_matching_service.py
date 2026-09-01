"""Role-aware orchestration around the existing fusion results.

This module deliberately does not change BM25, semantic, KG, or fusion scoring.
It adds a stable role identity to already-scored JD candidates, selects the
strongest canonical role, and only then ranks JD evidence inside that role.
"""

from __future__ import annotations

from typing import Any, Iterable

from .canonical_role_pool import CanonicalRolePool


def _skills(item: dict[str, Any]) -> list[str]:
    values = item.get("required_skills") or item.get("skills") or []
    if isinstance(values, str):
        return [part.strip() for part in values.replace("；", ";").split(";") if part.strip()]
    return [str(value).strip() for value in values if str(value).strip()]


def _score(item: dict[str, Any]) -> float:
    try:
        return float(item.get("final_score") or item.get("score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _role_input(item: dict[str, Any]) -> dict[str, Any]:
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    merged = {**meta, **item}
    return {
        "standard_job": merged.get("standard_job") or merged.get("job_family") or "",
        "title": merged.get("title") or merged.get("job_title") or "",
        "skills": _skills(merged),
    }


def enrich_role_identity(
    item: dict[str, Any],
    *,
    role_pool: CanonicalRolePool | None = None,
) -> dict[str, Any]:
    """Attach canonical role metadata without changing the original score."""

    pool = role_pool or CanonicalRolePool()
    mapping = pool.classify(_role_input(item))
    enriched = dict(item)
    enriched.update(
        {
            "canonical_role_id": mapping.get("canonical_role_id"),
            "canonical_role": mapping.get("canonical_role"),
            "canonical_domain": mapping.get("canonical_domain"),
            "canonical_direction": mapping.get("canonical_direction"),
            "role_specialization": mapping.get("role_specialization"),
            "role_mapping_status": mapping.get("role_mapping_status", "unmapped"),
            "role_mapping_confidence": mapping.get("role_mapping_confidence", 0.0),
            "role_mapping_review_reasons": mapping.get("role_mapping_review_reasons", []),
        }
    )
    return enriched


def rank_role_aware(
    items: Iterable[dict[str, Any]],
    *,
    top_k: int = 3,
    role_top_k: int = 1,
    candidate_role_id: str | None = None,
    role_pool: CanonicalRolePool | None = None,
) -> dict[str, Any]:
    """Select a canonical role, then rank JD candidates inside that role.

    Unmapped records are retained for audit visibility but cannot be selected
    as the formal role gate. The original Fusion score remains the JD score.
    """

    if top_k < 1 or role_top_k < 1:
        raise ValueError("top_k and role_top_k must be positive")

    pool = role_pool or CanonicalRolePool()
    enriched = [enrich_role_identity(dict(item), role_pool=pool) for item in items]
    mapped = [item for item in enriched if item.get("role_mapping_status") == "mapped"]
    # A role gate is a formal-pool boundary. If nothing is mapped, return an
    # empty formal result so callers can make an explicit legacy fallback.
    eligible = mapped

    if candidate_role_id:
        requested = [item for item in eligible if item.get("canonical_role_id") == candidate_role_id]
        if requested:
            eligible = requested

    groups: dict[str, list[dict[str, Any]]] = {}
    for item in eligible:
        role_id = str(item.get("canonical_role_id") or "unmapped")
        groups.setdefault(role_id, []).append(item)

    role_candidates = []
    for role_id, role_items in groups.items():
        role_items.sort(key=lambda item: (-_score(item), str(item.get("job_id") or "")))
        best = role_items[0]
        role_candidates.append(
            {
                "canonical_role_id": role_id if role_id != "unmapped" else None,
                "canonical_role": best.get("canonical_role"),
                "canonical_domain": best.get("canonical_domain"),
                "canonical_direction": best.get("canonical_direction"),
                "role_mapping_status": best.get("role_mapping_status", "unmapped"),
                "role_score": _score(best),
                "jd_count": len(role_items),
            }
        )

    role_candidates.sort(key=lambda item: (-float(item["role_score"]), str(item.get("canonical_role_id") or "")))
    selected_ids = {
        str(item.get("canonical_role_id"))
        for item in role_candidates[:role_top_k]
        if item.get("canonical_role_id")
    }
    selected = [item for item in eligible if str(item.get("canonical_role_id")) in selected_ids]
    selected.sort(key=lambda item: (-_score(item), str(item.get("job_id") or "")))

    return {
        "selected_role": role_candidates[0] if role_candidates else None,
        "role_candidates": role_candidates,
        "results": selected[:top_k],
        "candidate_count": len(enriched),
        "mapped_candidate_count": len(mapped),
        "unmapped_candidate_count": len(enriched) - len(mapped),
        "source": "role-aware-adapter-v1",
    }
