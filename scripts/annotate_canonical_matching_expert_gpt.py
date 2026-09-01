"""Apply a transparent expert-GPT provisional annotation to a review pack.

This is intentionally separate from the production scorer and from
role_match_grade. It uses the resume/JD evidence fields to create a first
reviewable label set; it is not a claim of independent human gold.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from canonical_job_title import canonical_job_title


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK = REPO_ROOT / "artifacts" / "canonical_matching_review_v1_100"
DEFAULT_ROLE_MAP = REPO_ROOT / "backend-src" / "app" / "data" / "canonical_role_pool" / "v1" / "source_role_mapping.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl_tolerant(path: Path) -> list[dict[str, Any]]:
    """Read JSONL while tolerating records split at an unescaped line break.

    A few long JD descriptions in the 400-case export were wrapped across two
    physical lines. The logical records are still valid when those fragments
    are joined; keep this compatibility only for the review-pack importer.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    records: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        buffer = lines[index]
        index += 1
        while True:
            try:
                value = json.loads(buffer)
                if not isinstance(value, dict):
                    raise ValueError(f"{path}: expected JSON object")
                records.append(value)
                break
            except json.JSONDecodeError:
                if index >= len(lines):
                    raise
                buffer += lines[index]
                index += 1
    return records


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def keys(value: str) -> set[str]:
    try:
        payload = json.loads(value or "[]")
    except json.JSONDecodeError:
        payload = []
    return {str(item).strip().casefold() for item in payload if str(item).strip()}


def annotate_option(case: dict[str, str], option: dict[str, str]) -> tuple[int, str, int]:
    # Compare stable canonical IDs. Source labels such as "Java开发工程师"
    # are intentionally allowed to map to the shared role "后端开发工程师".
    target_role = str(case.get("target_canonical_role_id") or "").strip().casefold()
    option_role = str(option.get("canonical_role_id") or "").strip().casefold()
    resume_skills = keys(case.get("candidate_skills", "[]"))
    required = keys(option.get("required_skills", "[]"))
    shared = resume_skills & required
    ratio = len(shared) / len(required) if required else 1.0
    same_role = bool(target_role and option_role and target_role == option_role)

    if same_role and (not required or len(shared) >= max(2, math.ceil(len(required) * 0.25))):
        grade = 3
        reason = f"标准岗位一致，命中{len(shared)}/{len(required)}项JD技能，职责方向一致。"
    elif same_role and shared:
        grade = 2
        reason = f"标准岗位一致，但仅命中{len(shared)}/{len(required)}项JD技能，列为可推荐边界样本。"
    elif same_role:
        grade = 1
        reason = "标准岗位一致，但简历没有JD必需技能证据，不能直接推荐。"
    elif len(shared) >= 3 and ratio >= 0.2:
        grade = 1
        reason = f"跨标准岗位但有{len(shared)}项技能重叠，属于相邻/硬负例，不按同岗位推荐。"
    else:
        grade = 0
        reason = "标准岗位不同，且缺少足够的职责与技能证据。"
    return grade, reason, len(shared)


def main() -> None:
    parser = argparse.ArgumentParser(description="Annotate canonical matching review pack with expert GPT rubric")
    parser.add_argument("--pack-dir", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--role-map", type=Path, default=DEFAULT_ROLE_MAP)
    args = parser.parse_args()

    cases = read_csv(args.pack_dir / "resume_job_cases.csv")
    with args.role_map.open("r", encoding="utf-8-sig", newline="") as handle:
        role_map = {row["source_standard_job"]: row["role_id"] for row in csv.DictReader(handle)}
    # The 400-case builder leaves this field blank; resolve it from the same
    # source-label mapping used by the canonical pool before grading options.
    for case in cases:
        if not str(case.get("target_canonical_role_id") or "").strip():
            case["target_canonical_role_id"] = role_map.get(str(case.get("source_target_role") or ""), "")
    options = read_jsonl_tolerant(args.pack_dir / "job_options.jsonl")
    by_case: dict[str, list[dict[str, str]]] = {}
    for option in options:
        by_case.setdefault(str(option["case_id"]), []).append(option)

    annotated_options: list[dict[str, Any]] = []
    annotated_cases: list[dict[str, Any]] = []
    for case in cases:
        case_options = by_case.get(str(case["case_id"]), [])
        accepted: list[str] = []
        rejected: list[str] = []
        accepted_title_labels: list[str] = []
        target_role_id = ""
        for option in case_options:
            grade, reason, shared_count = annotate_option(case, option)
            accepted_flag = grade >= 2
            if accepted_flag:
                accepted.append(str(option["job_id"]))
                label = str(option.get("job_title_label") or canonical_job_title(option)).strip()
                if label and label not in accepted_title_labels:
                    accepted_title_labels.append(label)
            else:
                rejected.append(str(option["job_id"]))
            target_role_id = target_role_id or str(option.get("canonical_role_id") or "")
            annotated_options.append({
                **option,
                "job_title_label": canonical_job_title(option),
                "expert_gpt_grade_0_to_3": grade,
                "expert_gpt_accept": "yes" if accepted_flag else "no",
                "expert_gpt_shared_skill_count": shared_count,
                "expert_gpt_reason": reason,
                "annotator": "expert_gpt_v1",
            })
        # The first same-role option is the role identity reference; the final
        # accepted set is based on evidence rather than option rank.
        same_role = [o for o in case_options if str(o.get("canonical_role_id")) == target_role_id]
        if same_role:
            target_role_id = str(same_role[0].get("canonical_role_id") or target_role_id)
        annotated_cases.append({
            **case,
            "gold_canonical_role_id": target_role_id,
            "gold_accepted_job_ids": json.dumps(accepted, ensure_ascii=False),
            "gold_accepted_title_labels": json.dumps(accepted_title_labels, ensure_ascii=False),
            "gold_rejected_job_ids": json.dumps(rejected, ensure_ascii=False),
            "review_decision": "expert_gpt_provisional",
            "reviewer": "expert_gpt_v1",
            "notes": "专家GPT基于简历全文、岗位职责和必需技能完成的首轮标注；需后续真人复核后方可作为正式金标。",
        })

    output_cases = args.pack_dir / "expert_gpt_cases.csv"
    output_options = args.pack_dir / "expert_gpt_annotations.csv"
    write_csv(output_cases, annotated_cases)
    write_csv(output_options, annotated_options)
    manifest_path = args.pack_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.update({
        "status": "expert_gpt_provisional_annotation",
        "annotator": "expert_gpt_v1",
        "expert_profile": "新一代信息技术岗位 taxonomy 与招聘 JD 分析专家 GPT；重点判断岗位职责边界、技能证据和相邻岗位可区分性。",
        "annotated_cases": len(annotated_cases),
        "annotated_options": len(annotated_options),
        "annotation_method": "基于候选人规范化技能、目标 canonical role ID 和岗位 JD 必需技能的可复核规则；不读取模型预测，不使用 role_match_grade 生成标签。",
        "grade_scale": {
            "3": "同一 canonical 岗位且技能证据充分，可接受 JD",
            "2": "同一 canonical 岗位但证据较弱，可作为边界接受样本",
            "1": "相邻或同岗位证据不足，不接受为标准匹配",
            "0": "岗位方向和技能证据均不足，拒绝",
        },
        "gold_policy": "Accepted title label must have the same canonical role and sufficient resume/JD skill evidence; concrete JD IDs remain supporting evidence and cross-role overlap remains negative or adjacent.",
        "limitation": "AI expert annotation is not two-independent-human gold and must not be presented as such.",
        "next_action": "抽样由至少一名人工招聘/岗位专家复核；分歧案例记录原因后再冻结正式金标。",
        "outputs": {
            "cases": output_cases.name,
            "options": output_options.name,
        },
    })
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
