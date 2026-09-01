"""Classify the newly added project-manager JDs conservatively.

This is an evidence report only. It does not activate any canonical role.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OLD = REPO_ROOT / "artifacts" / "canonical_role_pool_v1" / "incremental_nontechnical_20260901"
DEFAULT_NEW = REPO_ROOT / "artifacts" / "canonical_role_pool_v1" / "incremental_nontechnical_20260901_v2"
DEFAULT_OUTPUT = DEFAULT_NEW / "project_role_split.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def classify(title: str) -> tuple[str, str, str]:
    text = title.casefold()
    if not re.search(r"项目经理|项目管理|publishing pm", text, re.I):
        return "not_project_manager", "非项目经理标题", "保留原岗位分组"
    if re.search(r"交付项目经理|交付项目管理", text, re.I):
        return "delivery_project_manager_candidate", "交付职责明确", "交付项目经理"
    if re.search(r"游戏|3a|英雄联盟|和平精英|使命召唤|三角洲|逆战|nba2k|og项目|pc/console|ue5", text, re.I):
        return "game_project_manager_candidate", "游戏研发/版本/发行/本地化项目职责", "游戏项目经理"
    if re.search(r"研发|模型|aigc|大模型|ai|数据|浏览器|云|会议|infra|版本", text, re.I):
        return "research_development_project_manager_candidate", "研发、AI、数据或平台项目职责", "研发项目经理"
    return "project_manager_review", "项目经理标题但技术/交付边界不足", "项目经理待审核"


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze added project-manager JD split")
    parser.add_argument("--old-product", type=Path, default=Path(r"C:\Users\糊涂涂\xwechat_files\wxid_09z3hkwazuyt22_cfcc\msg\file\2026-09\产品及经理类岗位.csv"))
    parser.add_argument("--new-product", type=Path, default=Path(r"C:\Users\糊涂涂\xwechat_files\wxid_09z3hkwazuyt22_cfcc\msg\file\2026-09\产品及经理类岗位(1).csv"))
    parser.add_argument("--old-game", type=Path, default=Path(r"C:\Users\糊涂涂\xwechat_files\wxid_09z3hkwazuyt22_cfcc\msg\file\2026-09\游戏技术美术及UI类岗位.csv"))
    parser.add_argument("--new-game", type=Path, default=Path(r"C:\Users\糊涂涂\xwechat_files\wxid_09z3hkwazuyt22_cfcc\msg\file\2026-09\游戏技术美术及UI类岗位(1).csv"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    old_ids = {row["job_id"] for path in (args.old_product, args.old_game) for row in read_csv(path)}
    added: list[dict[str, Any]] = []
    for path in (args.new_product, args.new_game):
        for row in read_csv(path):
            if row["job_id"] not in old_ids and re.search(r"项目经理|项目管理|publishing pm", row["job_name"], re.I):
                bucket, reason, proposed_name = classify(row["job_name"])
                added.append({
                    "source_job_id": row["job_id"],
                    "title": row["job_name"],
                    "category": row.get("category", ""),
                    "proposed_bucket": bucket,
                    "reason": reason,
                    "proposed_market_name": proposed_name,
                })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = list(added[0]) if added else []
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(added)

    counts = Counter(row["proposed_bucket"] for row in added)
    report = {
        "added_project_jds": len(added),
        "bucket_counts": dict(sorted(counts.items())),
        "recommendation": {
            "activate_now": [],
            "candidate_roles": [
                {"role_id": "research_development_project_manager", "market_name": "研发项目经理", "evidence_count": counts.get("research_development_project_manager_candidate", 0)},
                {"role_id": "game_project_manager", "market_name": "游戏项目经理", "evidence_count": counts.get("game_project_manager_candidate", 0)},
                {"role_id": "delivery_project_manager", "market_name": "交付项目经理", "evidence_count": counts.get("delivery_project_manager_candidate", 0)},
            ],
            "not_create_yet": "IT项目经理：本批没有明确 IT 项目经理标题证据；与研发项目经理职责交集较大，继续采集后再决定是否拆分。",
        },
        "decision_rule": "标题优先，职责作为复核证据；不按预设数量强行拆分岗位。",
        "output": str(args.output),
    }
    report_path = args.output.with_name("project_role_split_report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
