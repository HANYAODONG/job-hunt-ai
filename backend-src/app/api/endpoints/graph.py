import hashlib
import time
from collections import Counter, defaultdict

from fastapi import APIRouter

from app.services.role_taxonomy import (
    DIRECTIONS_BY_CATEGORY,
    get_canonical_taxonomy,
)
from app.services.talent_data_service import TalentDataService


router = APIRouter()
talent_data_service = TalentDataService()
GRAPH_CACHE_TTL_SECONDS = 60
SPARSE_DIRECTION_POSTING_THRESHOLD = 100
_graph_cache = None
_graph_cache_at = 0.0


def _node_id(kind: str, *parts: str) -> str:
    digest = hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{kind}_{digest}"


def _top_skills(counter: Counter[str], limit: int = 6) -> list[str]:
    return [skill for skill, _ in counter.most_common(limit)]


def _sorted_categories(categories: set[str]) -> list[str]:
    known = [category for category in DIRECTIONS_BY_CATEGORY if category in categories]
    return known + sorted(categories - set(known))


def build_standard_role_graph(records: list[dict]) -> dict:
    """Aggregate job postings into category -> direction -> standard role."""
    roles: dict[tuple[str, str, str], dict] = {}
    category_skills: defaultdict[str, Counter[str]] = defaultdict(Counter)
    direction_skills: defaultdict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    distinct_skills: set[str] = set()
    relationship_count = 0

    for record in records:
        category = str(record.get("standard_category") or "").strip()
        role = str(record.get("standard_role") or record.get("job_family") or "").strip()
        if not category or not role:
            continue
        canonical_category, inferred_direction = get_canonical_taxonomy(category, role)
        direction = str(record.get("standard_direction") or inferred_direction).strip()
        skills = [str(skill).strip() for skill in record.get("skills") or [] if str(skill).strip()]
        key = (canonical_category, direction, role)
        role_data = roles.setdefault(key, {"count": 0, "skills": Counter(), "needs_review": 0})
        role_data["count"] += 1
        role_data["skills"].update(skills)
        role_data["needs_review"] += int(bool(record.get("needs_review")))
        category_skills[canonical_category].update(skills)
        direction_skills[(canonical_category, direction)].update(skills)
        distinct_skills.update(skills)
        relationship_count += len(skills)

    grouped: defaultdict[str, defaultdict[str, list[tuple[str, dict]]]] = defaultdict(lambda: defaultdict(list))
    for (category, direction, role), role_data in roles.items():
        grouped[category][direction].append((role, role_data))

    tree = {
        "id": "root",
        "label": "岗位银河",
        "type": "root",
        "count": len(roles),
        "growth": "+0%",
        "detail": f"当前图谱包含 {len(roles)} 个标准岗位，来自 {sum(item['count'] for item in roles.values())} 条招聘数据。",
        "skills": ["标准岗位分类", "能力映射", "岗位演化"],
        "children": [],
    }

    family_count = 0
    for category in _sorted_categories(set(grouped)):
        directions = grouped[category]
        category_total = sum(data["count"] for role_list in directions.values() for _, data in role_list)
        category_node = {
            "id": _node_id("category", category),
            "label": category,
            "type": "domain",
            "count": category_total,
            "growth": "+0%",
            "detail": f"一级标准分类，包含 {len(directions)} 个岗位方向与 {sum(len(items) for items in directions.values())} 个标准岗位。",
            "skills": _top_skills(category_skills[category]),
            "children": [],
        }
        for direction in sorted(directions):
            role_items = sorted(directions[direction], key=lambda item: (-item[1]["count"], item[0]))
            family_total = sum(data["count"] for _, data in role_items)
            role_count = len(role_items)
            is_single_role = role_count == 1
            taxonomy_status = (
                "当前数据暂不足以细分"
                if is_single_role and family_total < SPARSE_DIRECTION_POSTING_THRESHOLD
                else "单岗位方向"
                if is_single_role
                else "多岗位方向"
            )
            category_node["children"].append({
                "id": _node_id("direction", category, direction),
                "label": direction,
                "type": "family",
                "count": family_total,
                "role_count": role_count,
                "is_single_role": is_single_role,
                "taxonomy_status": taxonomy_status,
                "growth": "+0%",
                "detail": (
                    f"岗位方向，当前数据包含 1 个标准岗位、{family_total} 条招聘数据；"
                    f"{taxonomy_status}。"
                    if is_single_role
                    else f"岗位方向，包含 {role_count} 个标准岗位。"
                ),
                "skills": _top_skills(direction_skills[(category, direction)]),
                "children": [
                    {
                        "id": _node_id("role", category, direction, role),
                        "label": role,
                        "type": "role",
                        "standard_category": category,
                        "standard_direction": direction,
                        "standard_role": role,
                        "count": data["count"],
                        "growth": "+0%",
                        "detail": (
                            f"标准岗位，汇总 {data['count']} 条招聘数据。"
                            if not data["needs_review"]
                            else f"临时标准岗位，汇总 {data['count']} 条待补充分类的岗位数据。"
                        ),
                        "skills": _top_skills(data["skills"], 5),
                        "needs_review": bool(data["needs_review"]),
                    }
                    for role, data in role_items
                ],
            })
            family_count += 1
        tree["children"].append(category_node)

    stacks = [category for category in ("算法与智能", "AI应用", "软件研发", "数据智能", "基础设施") if category in grouped]
    return {
        "tree": tree,
        "summary": {
            "domains": len(tree["children"]),
            "families": family_count,
            "roles": len(roles),
            "job_postings": sum(data["count"] for data in roles.values()),
            "needs_review": sum(data["needs_review"] for data in roles.values()),
            "single_role_families": sum(
                1 for domain in tree["children"] for family in domain["children"] if family["is_single_role"]
            ),
            "sparse_single_role_families": sum(
                1 for domain in tree["children"] for family in domain["children"]
                if family["taxonomy_status"] == "当前数据暂不足以细分"
            ),
            "skills": len(distinct_skills),
            "relationships": relationship_count,
        },
        "stacks": stacks,
        "jobs": [role for _, _, role in sorted(roles)],
        "source": "canonical_standard_role_taxonomy",
    }


@router.get("/graph")
async def get_capability_graph():
    """Return a cached standard-role taxonomy, never raw recruitment titles."""
    global _graph_cache, _graph_cache_at
    now = time.monotonic()
    if _graph_cache is not None and now - _graph_cache_at < GRAPH_CACHE_TTL_SECONDS:
        return _graph_cache
    _graph_cache = build_standard_role_graph(talent_data_service.list_standard_role_records())
    _graph_cache_at = now
    return _graph_cache


@router.get("/graph/role-jobs")
async def get_standard_role_jobs(
    category: str,
    direction: str,
    role: str,
    limit: int = 20,
    offset: int = 0,
):
    """Return the current JD views behind one third-level graph node."""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    return talent_data_service.list_standard_role_jobs(category, direction, role, limit, offset)


def invalidate_capability_graph_cache():
    global _graph_cache, _graph_cache_at
    _graph_cache = None
    _graph_cache_at = 0.0
    talent_data_service.invalidate_runtime_state_cache()
