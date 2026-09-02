"""Normalize newly collected non-technical JD CSVs into a review-gated snapshot.

The output is deliberately a candidate snapshot, not an active canonical pool:
new roles require market-name and overlap review before they can affect graph or
matching results.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "artifacts" / "canonical_role_pool_v1" / "incremental_nontechnical_20260901"
DEFAULT_INPUTS = [
    Path(r"C:\Users\糊涂涂\xwechat_files\wxid_09z3hkwazuyt22_cfcc\msg\file\2026-09\产品及经理类岗位.csv"),
    Path(r"C:\Users\糊涂涂\xwechat_files\wxid_09z3hkwazuyt22_cfcc\msg\file\2026-09\游戏技术美术及UI类岗位.csv"),
    Path(r"C:\Users\糊涂涂\xwechat_files\wxid_09z3hkwazuyt22_cfcc\msg\file\2026-09\安全合规工程师岗位.csv"),
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def first_url(text: str) -> str:
    match = re.search(r"https?://[^\s；,，)）]+", text or "")
    return match.group(0).rstrip(".;，。,；") if match else ""


def stable_id(prefix: str, row: dict[str, str], source_name: str) -> tuple[str, bool]:
    source_id = str(row.get("job_id") or "").strip()
    if source_id:
        return f"{prefix}-{source_id}", False
    raw = "\x1f".join(str(row.get(field) or "").strip() for field in ("job_name", "job_description", "job_requirement", "cities"))
    digest = hashlib.sha256((source_name + "\x1f" + raw).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-HASH-{digest}", True


def candidate_bucket(title: str, category: str, description: str) -> tuple[str, str]:
    title_text = title.casefold()
    evidence = f"{title} {category} {description}".casefold()
    if re.search(r"技术美术|technical artist|shader|unity|unreal|ue5|游戏特效", evidence):
        return "game_technical_artist_candidate", "游戏技术美术/引擎美术职责信号"
    if re.search(r"\bui\b|\bux\b|交互设计|视觉设计|用户体验设计|产品体验设计|体验设计|美术设计", title_text):
        return "ui_ux_design_candidate", "UI/UX/视觉或交互设计职责信号"
    if re.search(r"安全合规|隐私合规|数据合规|信息安全合规", title_text):
        return "security_compliance_candidate", "安全合规/隐私治理职责信号"
    if re.search(r"数据科学家|data scientist", title_text):
        return "data_scientist_existing_candidate", "可与现有数据科学家岗位核验"
    if re.search(r"数据分析师|数据分析", title_text) and not re.search(r"数据产品", title_text):
        return "data_analysis_existing_candidate", "可与现有数据分析师岗位核验"
    if re.search(r"数据产品", title_text):
        return "data_product_new_candidate", "数据产品职责，现有池无独立数据产品经理角色"
    if re.search(r"技术产品|平台产品|研发产品|产品架构", title_text):
        return "technical_product_new_candidate", "技术/平台产品职责，需与 AI 产品经理区分"
    if re.search(r"ai|aigc|agent|智能体|大模型|模型产品", title_text):
        return "ai_product_existing_candidate", "可与现有 AI 产品经理岗位核验"
    if re.search(r"产品经理|产品专家|产品策划", title_text):
        return "product_manager_new_candidate", "通用产品职责，需补充现实市场岗位证据"
    if re.search(r"技术项目经理|技术项目管理", title_text):
        return "technical_project_manager_new_candidate", "技术项目管理职责，现有池未覆盖"
    if re.search(r"交付项目经理|交付项目管理", title_text):
        return "delivery_project_manager_new_candidate", "交付项目管理职责，现有池未覆盖"
    if re.search(r"\bIT项目经理\b|IT项目管理", title_text):
        return "it_project_manager_new_candidate", "IT 项目管理职责，现有池未覆盖"
    if re.search(r"项目经理|项目管理|pm[o]?|交付", title_text):
        return "project_manager_new_candidate", "项目/交付管理职责，现有池未覆盖"
    if re.search(r"运营|增长|商业化", title_text):
        return "technical_operation_new_candidate", "运营/增长职责，需确认是否属于 IT 功能岗位"
    return "unclassified_review", "标题和职责未形成可靠映射"


def normalize(path: Path, rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    if path.name.startswith("产品及经理类岗位"):
        prefix = "BT-PM"
    elif path.name.startswith("游戏技术美术及UI类岗位"):
        prefix = "BT-GAME"
    elif path.name.startswith("安全合规工程师岗位"):
        prefix = "SEC"
    else:
        prefix = "NEW"
    output: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        title = str(row.get("job_name") or "").strip()
        description = str(row.get("job_description") or "").strip()
        requirement = str(row.get("job_requirement") or "").strip()
        full_text = "\n\n".join(part for part in (description, requirement) if part)
        job_id, generated_id = stable_id(prefix, row, path.name)
        bucket, reason = candidate_bucket(title, str(row.get("category") or ""), full_text)
        source_url = str(row.get("job_url") or "").strip() or first_url(full_text)
        output.append({
            "job_id": job_id,
            "title": title,
            "description": full_text,
            "company": "字节跳动" if prefix.startswith("BT-") else "",
            "location": str(row.get("cities") or "").strip(),
            "category_raw": str(row.get("category") or "").strip(),
            "department": str(row.get("department") or "").strip(),
            "product_name": str(row.get("product_name") or "").strip(),
            "education": str(row.get("education") or "").strip(),
            "work_years": str(row.get("work_years") or "").strip(),
            "work_type": str(row.get("work_type") or "").strip(),
            "publish_time": str(row.get("update_time") or row.get("update_time_raw") or "").strip(),
            "source_url": source_url,
            "source": "bytedance" if prefix.startswith("BT-") else "external_security_compliance",
            "source_type": "enterprise" if prefix.startswith("BT-") else "market_sample",
            "source_snapshot": {
                "source_file": path.name,
                "source_row_number": index + 1,
                "source_job_id": str(row.get("job_id") or "").strip(),
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "id_generated": generated_id,
            },
            "proposed_role_bucket": bucket,
            "proposed_role_reason": reason,
            "mapping_status": "candidate_review",
        })
    return output


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build review-gated non-technical JD snapshot")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("inputs", nargs="*", type=Path, default=DEFAULT_INPUTS)
    args = parser.parse_args()
    records: list[dict[str, Any]] = []
    source_stats: list[dict[str, Any]] = []
    for path in args.inputs:
        rows = read_rows(path)
        normalized = normalize(path, rows)
        records.extend(normalized)
        source_stats.append({
            "file": str(path),
            "rows": len(rows),
            "missing_source_job_id": sum(not str(row.get("job_id") or "").strip() for row in rows),
            "missing_source_url": sum(not (str(row.get("job_url") or "").strip() or first_url(str(row.get("job_description") or ""))) for row in rows),
        })
    ids = Counter(str(row["job_id"]) for row in records)
    title_desc = Counter((str(row["title"]), str(row["description"])) for row in records)
    review_rows = [{
        "job_id": row["job_id"],
        "title": row["title"],
        "source": row["source"],
        "proposed_role_bucket": row["proposed_role_bucket"],
        "proposed_role_reason": row["proposed_role_reason"],
        "source_url": row["source_url"],
        "review_decision": "",
        "canonical_role_id": "",
        "review_notes": "",
    } for row in records]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "normalized_candidate_jobs.jsonl", records)
    with (args.output_dir / "role_mapping_review.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = list(review_rows[0]) if review_rows else []
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(review_rows)
    report = {
        "version": "canonical_role_pool_v1_nontechnical_incremental_20260901",
        "status": "candidate_snapshot_pending_role_review",
        "records": len(records),
        "unique_job_ids": len(ids),
        "duplicate_job_ids": sum(count - 1 for count in ids.values() if count > 1),
        "exact_title_description_duplicates": sum(count - 1 for count in title_desc.values() if count > 1),
        "source_stats": source_stats,
        "proposed_role_buckets": dict(sorted(Counter(row["proposed_role_bucket"] for row in records).items())),
        "quality_flags": {
            "records_without_source_url": sum(not row["source_url"] for row in records),
            "records_with_generated_id": sum(row["source_snapshot"]["id_generated"] for row in records),
            "records_without_description": sum(not row["description"] for row in records),
            "records_without_requirement": sum(not str(row["description"]).strip() for row in records),
        },
        "activation_gate": [
            "Do not merge candidate_snapshot into active canonical_jobs.jsonl yet.",
            "Review proposed role bucket against market-recognizable job names and responsibilities.",
            "Assign canonical_role_id only after boundary and overlap review.",
            "Rebuild indexes and regression tests only after an accepted version is produced.",
        ],
        "outputs": {
            "normalized_jobs": "normalized_candidate_jobs.jsonl",
            "mapping_review": "role_mapping_review.csv",
            "report": "incremental_report.json",
        },
    }
    (args.output_dir / "incremental_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
