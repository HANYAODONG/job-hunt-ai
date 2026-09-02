"""Build a review-gated v2 canonical role pool from v1 and nontechnical JD candidates.

The v1 pool is immutable input. New records are accepted only when their
candidate bucket has an explicit role decision. Other candidates stay in the
review queue with their original source metadata and generated IDs intact.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
V1_DIR = REPO_ROOT / "artifacts" / "canonical_role_pool_v1" / "data_group_current"
INCREMENT_DIR = REPO_ROOT / "artifacts" / "canonical_role_pool_v1" / "incremental_nontechnical_20260901_v2"
DEFAULT_OUTPUT = REPO_ROOT / "artifacts" / "canonical_role_pool_v2"


ROLE_DECISIONS: dict[str, dict[str, Any]] = {
    "product_manager_new_candidate": {
        "role_id": "product_manager",
        "role_name": "产品经理",
        "status": "active",
        "domain": "数字产品与体验",
        "direction": "产品管理",
        "definition": "负责数字产品的用户问题、需求方案、迭代验证和跨团队落地",
        "boundary": "以产品需求、方案和效果迭代为主要交付；不因行业、城市或业务线单独拆岗",
    },
    "data_product_new_candidate": {
        "role_id": "data_product_manager",
        "role_name": "数据产品经理",
        "status": "active",
        "domain": "数字产品与体验",
        "direction": "产品管理",
        "definition": "负责数据资产、指标、分析平台或数据服务产品的需求与产品化落地",
        "boundary": "交付数据产品和数据服务能力；不等同于数据分析师、数据工程师或通用产品经理",
    },
    "technical_product_new_candidate": {
        "role_id": "technical_product_manager",
        "role_name": "技术产品经理",
        "status": "active",
        "domain": "数字产品与体验",
        "direction": "产品管理",
        "definition": "负责技术平台、开发者平台或基础设施产品的需求、方案和产品迭代",
        "boundary": "产品对象是技术平台/基础设施并要求技术方案理解；不等同于软件架构师或项目经理",
    },
    "security_compliance_candidate": {
        "role_id": "security_compliance_engineer",
        "role_name": "安全合规工程师",
        "status": "active",
        "domain": "云网与安全",
        "direction": "网络与网络安全",
        "definition": "负责信息安全制度、风险评估、审计认证、隐私与数据安全合规整改",
        "boundary": "以治理、审计、认证和合规整改为主要交付；不等同于安全运营或攻防研发",
    },
    "research_development_project_manager_candidate": {
        "role_id": "research_development_project_manager",
        "role_name": "研发项目经理",
        "status": "active",
        "domain": "数字产品与体验",
        "direction": "项目与交付管理",
        "definition": "负责软件、AI、数据或研发基础设施项目的计划、依赖、资源、风险和里程碑",
        "boundary": "项目对象是内部研发交付；不负责产品路线决策，也不以客户实施验收为主要产出",
    },
    "game_project_manager_candidate": {
        "role_id": "game_project_manager",
        "role_name": "游戏项目经理",
        "status": "active",
        "domain": "数字产品与体验",
        "direction": "项目与交付管理",
        "definition": "负责游戏研发、版本、发行、本地化或美术制作的计划协同与交付",
        "boundary": "项目对象明确为游戏产品；不等同于游戏策划、游戏产品经理或通用研发项目经理",
    },
    "delivery_project_manager_new_candidate": {
        "role_id": "delivery_project_manager",
        "role_name": "交付项目经理",
        "status": "active",
        "domain": "数字产品与体验",
        "direction": "项目与交付管理",
        "definition": "负责客户项目实施、部署、上线、验收和交付问题闭环",
        "boundary": "客户实施和交付结果是主要产出；不等同于内部研发项目计划管理",
    },
    "technical_project_manager_new_candidate": {
        "role_id": "it_project_manager",
        "role_name": "IT项目经理",
        "status": "active",
        "domain": "数字产品与体验",
        "direction": "项目与交付管理",
        "definition": "负责企业信息化、IT系统、云计算、数据中心或IT安全项目的需求、方案、治理和交付",
        "boundary": "项目对象是企业IT建设与治理；不等同于研发项目经理或仅负责客户验收的交付项目经理",
    },
    "ui_ux_design_candidate": {
        "role_id": "ui_ux_design",
        "role_name": "UI/UX设计师",
        "status": "active",
        "domain": "数字产品与体验",
        "direction": "用户体验设计",
        "definition": "负责数字产品的界面、交互和用户体验方案并跟进设计落地",
        "boundary": "以界面/交互/体验设计交付为主；不等同于前端开发或游戏策划",
    },
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def key_for(row: dict[str, Any]) -> str:
    title = str(row.get("title") or row.get("job_title") or "").strip().casefold()
    description = str(row.get("description") or "").strip().casefold()
    return hashlib.sha256(f"{title}\n{description}".encode("utf-8")).hexdigest()


def enrich_candidate(row: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(row)
    enriched.update(
        {
            "canonical_role_id": decision["role_id"],
            "canonical_role": decision["role_name"],
            "canonical_domain": decision["domain"],
            "canonical_direction": decision["direction"],
            "role_specialization": "",
            "standard_job": decision["role_name"],
            "job_family": decision["role_name"],
            "standard_category": decision["domain"],
            "standard_direction": decision["direction"],
            "role_mapping_status": "mapped" if decision["status"] == "active" else "review_required",
            "role_mapping_confidence": 0.78 if decision["status"] == "active" else 0.62,
            "role_mapping_requires_jd_validation": decision["status"] != "active",
            "role_mapping_review_reasons": []
            if decision["status"] == "active"
            else ["新岗位候选待完成样本量、边界和近邻混淆审核"],
            "v2_role_decision": decision["status"],
        }
    )
    return enriched


def decision_for_candidate(row: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve project-manager subtypes from title evidence, not source counts."""
    bucket = str(row.get("proposed_role_bucket") or "unclassified_review")
    if bucket == "project_manager_new_candidate":
        title = str(row.get("title") or "")
        game_terms = ("游戏", "英雄联盟", "使命召唤", "逆战", "三角洲", "洛克王国", "NBA2K", "射击", "美术项目", "版本项目", "Publishing")
        bucket = "game_project_manager_candidate" if any(term.casefold() in title.casefold() for term in game_terms) else "research_development_project_manager_candidate"
    elif bucket == "technical_project_manager_new_candidate":
        # The local title explicitly says technical PM; keep it in the IT PM
        # review role rather than inventing a generic "technical PM" identity.
        bucket = "technical_project_manager_new_candidate"
    return ROLE_DECISIONS.get(bucket)


def build(output_dir: Path) -> dict[str, Any]:
    base = read_jsonl(V1_DIR / "canonical_jobs.jsonl")
    old_review = read_jsonl(V1_DIR / "role_mapping_review.jsonl")
    candidates = read_jsonl(INCREMENT_DIR / "normalized_candidate_jobs.jsonl")

    existing_keys = {key_for(row) for row in base}
    seen_candidate_keys: set[str] = set()
    duplicates: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    bucket_stats: Counter[str] = Counter()
    for row in candidates:
        key = key_for(row)
        if key in existing_keys or key in seen_candidate_keys:
            duplicates.append({"job_id": row.get("job_id"), "title": row.get("title"), "duplicate_key": key})
            continue
        seen_candidate_keys.add(key)
        bucket = str(row.get("proposed_role_bucket") or "unclassified_review")
        decision = decision_for_candidate(row)
        if decision is None:
            review.append({**row, "v2_role_decision": "review_only", "role_mapping_status": "review_required", "role_mapping_review_reasons": ["候选岗位尚未形成可激活的职责边界"]})
            bucket_stats["unclassified_review"] += 1
            continue
        mapped = enrich_candidate(row, decision)
        bucket_stats[decision["role_id"]] += 1
        (accepted if decision["status"] == "active" else review).append(mapped)

    # Preserve v1 review queue and append v2 review records. v1 records remain
    # untouched, so no historical source label or audit decision is lost.
    all_review = old_review + review
    all_jobs = base + accepted
    role_rows = []
    with (REPO_ROOT / "backend-src/app/data/canonical_role_pool/v1/canonical_roles.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        role_rows = list(csv.DictReader(handle))
    known_ids = {row["role_id"] for row in role_rows}
    for decision in ROLE_DECISIONS.values():
        if decision["role_id"] in known_ids:
            continue
        role_rows.append(
            {
                "role_id": decision["role_id"],
                "domain": decision["domain"],
                "direction": decision["direction"],
                "role_name": decision["role_name"],
                "role_definition": decision["definition"],
                "core_boundary": decision["boundary"],
                "status": decision["status"],
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "canonical_jobs.jsonl", all_jobs)
    write_jsonl(output_dir / "role_mapping_review.jsonl", all_review)
    with (output_dir / "canonical_roles.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["role_id", "domain", "direction", "role_name", "role_definition", "core_boundary", "status"])
        writer.writeheader()
        writer.writerows(role_rows)
    (output_dir / "deduplication_report.json").write_text(json.dumps({"candidate_records": len(candidates), "deduplicated_records": len(duplicates), "duplicates": duplicates}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    active_ids = {row["role_id"] for row in role_rows if row["status"] == "active"}
    report = {
        "version": "canonical_role_pool_v2",
        "status": "review_gated_release_candidate",
        "base_v1_records": len(base),
        "v1_review_records_preserved": len(old_review),
        "incremental_candidate_records": len(candidates),
        "incremental_exact_duplicates_removed": len(duplicates),
        "incremental_active_records_added": len(accepted),
        "incremental_review_records_added": len(review),
        "canonical_records": len(all_jobs),
        "review_records": len(all_review),
        "defined_roles": len(role_rows),
        "active_roles": len(active_ids),
        "new_role_decisions": {decision["role_id"]: decision["status"] for decision in ROLE_DECISIONS.values()},
        "incremental_role_counts": dict(sorted(bucket_stats.items())),
        "input_sha256": {
            "v1_canonical_jobs": hashlib.sha256((V1_DIR / "canonical_jobs.jsonl").read_bytes()).hexdigest(),
            "v1_review_queue": hashlib.sha256((V1_DIR / "role_mapping_review.jsonl").read_bytes()).hexdigest(),
            "incremental_candidates": hashlib.sha256((INCREMENT_DIR / "normalized_candidate_jobs.jsonl").read_bytes()).hexdigest(),
        },
        "quality_gates": [
            "v1 canonical jobs are copied without mutation",
            "only roles marked active contribute to canonical_jobs.jsonl",
            "review_only candidates remain in role_mapping_review.jsonl",
            "exact title+description duplicates are excluded from the active input",
            "indexes and graph imports must be rebuilt only after this release candidate is accepted",
        ],
        "outputs": {
            "canonical_jobs": str(output_dir / "canonical_jobs.jsonl"),
            "review_queue": str(output_dir / "role_mapping_review.jsonl"),
            "canonical_roles": str(output_dir / "canonical_roles.csv"),
            "deduplication_report": str(output_dir / "deduplication_report.json"),
            "report": str(output_dir / "role_pool_report.json"),
        },
    }
    (output_dir / "role_pool_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build(args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
