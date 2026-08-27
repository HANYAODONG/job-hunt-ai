"""Build the machine-readable and human-readable phase-6 acceptance report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


REQUIRED_FIELDS = (
    "is_duplicate",
    "noise_score",
    "inflation_score",
    "source_count",
    "verified_by_multi_source",
)
CASE_CATEGORIES = ("duplicates", "noise", "inflation", "staleness", "multi_source")
PRIORITY_DIMENSIONS = ("duplicate", "noise", "stale")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def traceable_case(row: dict[str, Any]) -> bool:
    return (
        bool(row.get("job_id"))
        and isinstance(row.get("decision"), bool)
        and bool(row.get("original_excerpt"))
        and bool(row.get("cleaned_excerpt"))
        and bool(row.get("reasons"))
        and isinstance(row.get("source_evidence"), dict)
        and isinstance(row["source_evidence"].get("current"), dict)
    )


def percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def build_markdown(report: dict[str, Any]) -> str:
    standards = report["acceptance_standards"]
    metrics = report["quality_metrics"]
    counts = report["audit_summary"]["counts"]
    lines = [
        "# 工作流六最终验收报告",
        "",
        f"验收结论：**{report['overall_status'].upper()}**",
        "",
        "## 一、数据与运行入口",
        "",
        f"- 标准输入：`{report['input']['path']}`",
        f"- 输入 SHA256：`{report['input']['sha256']}`",
        f"- 一键命令：`{report['reproduction']['command']}`",
        f"- 审计 JD：{counts['output_jobs']:,} 条",
        f"- 数据来源：{json.dumps(report['audit_summary']['source_type_counts'], ensure_ascii=False)}",
        "",
        "## 二、五项验收标准",
        "",
    ]
    for item in standards:
        lines.append(
            f"{item['id']}. {'通过' if item['passed'] else '未通过'}：{item['name']}。{item['evidence']}"
        )
    lines.extend(
        [
            "",
            "## 三、全量审计统计",
            "",
            f"- 重复/近重复：{counts['duplicates']:,} / {counts['near_duplicates']:,}",
            f"- 噪音：{counts['noisy_jobs']:,}",
            f"- 要求膨胀：{counts['inflated_jobs']:,}",
            f"- 时滞：{counts['stale_jobs']:,}",
            f"- 多源验证：{counts['multi_source_verified_jobs']:,}",
            f"- 记录级跨来源直接证据：{counts.get('record_level_multi_source_jobs', 0):,}",
            "",
            "## 四、200条盲审验收指标",
            "",
            f"- 复核数：{report['llm_review']['reviewed']}，高置信一致：{report['llm_review']['accepted']}，冲突：{report['llm_review']['conflicts']}",
            f"- 五项 Macro-F1：{percent(metrics['macro_f1'])}",
        ]
    )
    for name, value in metrics["dimensions"].items():
        lines.append(
            f"- {name}：Precision {percent(value['precision'])}，Recall {percent(value['recall'])}，F1 {percent(value['f1'])}"
        )
    lines.extend(
        [
            "",
            "## 五、算法规则",
            "",
            "- 重复：标准化正文精确哈希；SimHash召回候选后用正文相似度确认近重复。",
            "- 噪音：按占位符、模板错误、企业文化、福利、投递信息和宣传文本分类赋权；政府招录必要联系方式豁免。",
            "- 要求膨胀：技能数量、强要求词、学历、年限、岗位族基线和岗位层级失配联合评分。",
            "- 时滞：发布日期缺失或相对参照日期超过365天。",
            "- 多源：优先使用同正文重复组的跨来源直接证据，否则明确降级为标准岗位族跨来源证据。",
            "",
            "## 六、错误案例与局限性",
            "",
            f"- 要求膨胀仍是最弱指标，F1为 {percent(metrics['dimensions']['inflation']['f1'])}。该判断包含岗位层级合理性，主观性高于重复和时滞。",
            f"- DeepSeek双投票仍有 {report['llm_review']['conflicts']} 条冲突样本，已保留在冲突队列。",
            "- DeepSeek标签属于可追溯伪人工金标，不等同于正式双人专家金标。",
            "- `verification_scope=standard_job_family` 表示岗位族层面的支持，不能冒充同一JD的直接跨站点印证。",
            "- 当前验收集为分层异常样本，不代表原始数据中的自然类别分布。",
            "",
            "## 七、主要产物",
            "",
        ]
    )
    lines.extend(f"- `{path}`" for path in report["outputs"].values())
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build phase-6 acceptance report")
    parser.add_argument("--audit-dir", type=Path, default=Path("artifacts/jd_quality_audit"))
    parser.add_argument(
        "--review-dir", type=Path, default=Path("artifacts/jd_quality_deepseek_review")
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/workflow6_acceptance")
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit_report = read_json(args.audit_dir / "jd_quality_report.json")
    cases = read_json(args.audit_dir / "jd_quality_cases.json")
    review_report = read_json(args.review_dir / "evaluation_report.json")

    total = complete = evidence_complete = 0
    for row in read_jsonl(args.audit_dir / "jd_quality_cleaned.jsonl"):
        total += 1
        complete += all(field in row and row[field] is not None for field in REQUIRED_FIELDS)
        source = row.get("source_evidence")
        evidence_complete += (
            isinstance(source, dict)
            and isinstance(source.get("current"), dict)
            and bool(source["current"].get("source_type"))
        )
    field_rate = complete / max(1, total)
    evidence_rate = evidence_complete / max(1, total)

    case_status = {}
    for category in CASE_CATEGORIES:
        rows = list(cases.get(category) or [])
        traceable = sum(traceable_case(row) for row in rows)
        case_status[category] = {
            "count": len(rows),
            "traceable": traceable,
            "passed": len(rows) >= 10 and traceable >= 10,
        }

    dimensions = review_report.get("metrics_on_accepted_consensus") or {}
    macro_f1 = sum(float(dimensions[name]["f1"]) for name in dimensions) / max(1, len(dimensions))
    priority_pass = all(float(dimensions[name]["f1"]) >= 0.90 for name in PRIORITY_DIMENSIONS)
    metrics_pass = macro_f1 >= 0.80 and priority_pass

    runner = "python scripts/run_workflow6_acceptance.py"
    report: dict[str, Any] = {
        "workflow": "phase6_jd_quality_acceptance",
        "overall_status": "pending",
        "input": audit_report.get("input") or {},
        "reproduction": {"command": runner, "resumable": True},
        "audit_summary": {
            "reference_date": audit_report.get("reference_date"),
            "counts": audit_report.get("counts") or {},
            "source_type_counts": audit_report.get("source_type_counts") or {},
            "thresholds": audit_report.get("thresholds") or {},
        },
        "field_validation": {
            "required_fields": list(REQUIRED_FIELDS),
            "total": total,
            "complete": complete,
            "completeness": round(field_rate, 6),
            "source_evidence_complete": evidence_complete,
            "source_evidence_completeness": round(evidence_rate, 6),
        },
        "traceable_cases": case_status,
        "llm_review": {
            "model": review_report.get("model"),
            "blind_review": review_report.get("configuration", {}).get("blind_review"),
            "sample_size": review_report.get("sample_size"),
            "reviewed": review_report.get("reviewed"),
            "accepted": review_report.get("accepted_pseudo_human_gold"),
            "conflicts": review_report.get("conflict_or_low_confidence"),
            "errors": review_report.get("errors"),
        },
        "quality_metrics": {
            "macro_f1": round(macro_f1, 4),
            "priority_dimensions_at_90": priority_pass,
            "dimensions": dimensions,
        },
        "limitations": [
            "DeepSeek consensus is pseudo-human gold, not formal expert gold.",
            "Inflation is the weakest and most subjective dimension.",
            "Job-family source support is explicitly distinguished from record-level corroboration.",
            "The 200-item set is anomaly-stratified rather than naturally distributed.",
        ],
        "outputs": {
            "cleaned_jobs": str(args.audit_dir / "jd_quality_cleaned.jsonl"),
            "cases": str(args.audit_dir / "jd_quality_cases.json"),
            "sample": str(args.audit_dir / "acceptance_sample_200.jsonl"),
            "pseudo_human_gold": str(args.review_dir / "pseudo_human_gold.jsonl"),
            "conflicts": str(args.review_dir / "conflict_review_queue.jsonl"),
            "metrics": str(args.review_dir / "evaluation_report.json"),
            "acceptance_json": str(args.output_dir / "workflow6_acceptance_report.json"),
            "acceptance_markdown": str(args.output_dir / "workflow6_acceptance_report.md"),
        },
    }

    standards = [
        {
            "id": 1,
            "name": "一条命令从标准jobs.jsonl重建结果",
            "passed": True,
            "evidence": runner,
        },
        {
            "id": 2,
            "name": "全量JD五个字段完整率100%",
            "passed": field_rate == 1.0 and evidence_rate == 1.0,
            "evidence": f"{complete}/{total}; source evidence {evidence_complete}/{total}",
        },
        {
            "id": 3,
            "name": "每类至少10条可追溯案例",
            "passed": all(value["passed"] for value in case_status.values()),
            "evidence": json.dumps(case_status, ensure_ascii=False),
        },
        {
            "id": 4,
            "name": "200条验收集核心指标达标",
            "passed": metrics_pass,
            "evidence": f"Macro-F1={macro_f1:.4f}; duplicate/noise/stale F1 all >= 0.90: {priority_pass}",
        },
        {
            "id": 5,
            "name": "形成最终验收报告",
            "passed": True,
            "evidence": str(args.output_dir / "workflow6_acceptance_report.md"),
        },
    ]
    report["acceptance_standards"] = standards
    report["overall_status"] = "pass" if all(item["passed"] for item in standards) else "fail"

    json_path = args.output_dir / "workflow6_acceptance_report.json"
    markdown_path = args.output_dir / "workflow6_acceptance_report.md"
    write_json(json_path, report)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(build_markdown(report), encoding="utf-8")
    print(json.dumps({"status": report["overall_status"], "report": str(markdown_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
