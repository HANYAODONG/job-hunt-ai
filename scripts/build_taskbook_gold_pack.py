"""Build a reproducible, blind annotation pack for task-book acceptance.

The generated A/B sheets intentionally exclude system predictions. Suggested
labels are stored in separate reference sheets so annotators can complete a
blind first pass before consulting them.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = REPO_ROOT / "artifacts" / "dataset_iteration_05"
DEFAULT_OUTPUT = REPO_ROOT / "artifacts" / "taskbook_gold_v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def allocate(total: int, groups: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    keys = sorted(groups)
    if not keys:
        return {}
    base, remainder = divmod(total, len(keys))
    counts = {key: min(base + (index < remainder), len(groups[key])) for index, key in enumerate(keys)}
    missing = total - sum(counts.values())
    while missing > 0:
        progressed = False
        for key in keys:
            if counts[key] < len(groups[key]):
                counts[key] += 1
                missing -= 1
                progressed = True
                if missing == 0:
                    break
        if not progressed:
            break
    return counts


def stratified_sample(
    rows: Iterable[dict[str, Any]],
    group_field: str,
    count: int,
    rng: random.Random,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(group_field) or "unknown")].append(row)
    counts = allocate(count, groups)
    sampled: list[dict[str, Any]] = []
    for key in sorted(groups):
        candidates = sorted(
            groups[key],
            key=lambda item: str(item.get("job_id") or item.get("candidate_id") or ""),
        )
        sampled.extend(rng.sample(candidates, counts[key]))
    rng.shuffle(sampled)
    return sampled, counts


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def jd_blind_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "sample_id": f"JD-{index:03d}",
            "job_id": row.get("job_id", ""),
            "source_type": row.get("source_type", ""),
            "title": row.get("title", ""),
            "description": row.get("description", ""),
            "gold_required_skills": "",
            "gold_optional_skills": "",
            "gold_responsibilities": "",
            "is_parseable": "",
            "annotator": "",
            "notes": "",
        }
        for index, row in enumerate(rows, start=1)
    ]


def resume_blind_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "sample_id": f"RES-{index:03d}",
            "candidate_id": row.get("candidate_id", ""),
            "target_job_family": row.get("target_job_family", ""),
            "resume_text": row.get("profile_text") or row.get("summary", ""),
            "gold_name": "",
            "gold_skills": "",
            "gold_years_experience": "",
            "gold_education": "",
            "gold_experience_titles": "",
            "is_parseable": "",
            "annotator": "",
            "notes": "",
        }
        for index, row in enumerate(rows, start=1)
    ]


def reference_rows(
    blind_rows: list[dict[str, Any]],
    originals: list[dict[str, Any]],
    kind: str,
) -> list[dict[str, Any]]:
    result = []
    for blind, source in zip(blind_rows, originals):
        item = {
            "sample_id": blind["sample_id"],
            "record_id": source.get("job_id") or source.get("candidate_id") or "",
            "reference_skills": json.dumps(
                source.get("skills") or source.get("skills_normalized") or [],
                ensure_ascii=False,
            ),
            "reference_warning": "仅供盲标完成后复核，不得直接复制为金标",
        }
        if kind == "resume":
            item["reference_years_experience"] = source.get("years_experience", "")
            item["reference_education"] = json.dumps(source.get("education") or {}, ensure_ascii=False)
        result.append(item)
    return result


def matching_blind_rows(
    labels: list[dict[str, Any]],
    candidates: dict[str, dict[str, Any]],
    jobs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for index, label in enumerate(labels, start=1):
        candidate = candidates[label["candidate_id"]]
        job = jobs[label["job_id"]]
        rows.append(
            {
                "sample_id": f"MATCH-{index:03d}",
                "pair_id": label.get("pair_id", ""),
                "candidate_id": label["candidate_id"],
                "job_id": label["job_id"],
                "candidate_target_role": candidate.get("target_job_family", ""),
                "candidate_text": candidate.get("profile_text") or candidate.get("summary", ""),
                "job_title": job.get("title", ""),
                "job_description": job.get("description", ""),
                "gold_grade_0_to_3": "",
                "hard_constraint_pass_yes_no": "",
                "matched_skills": "",
                "missing_required_skills": "",
                "annotator": "",
                "notes": "",
            }
        )
    return rows


def instructions() -> str:
    return """# 任务书金标标注说明

## 标注流程

1. 标注员A填写`jd_annotation_A.csv`、`resume_annotation_A.csv`和`matching_annotation_A.csv`。
2. 标注员B独立填写B表，标注期间不得查看A表。
3. 两人完成第一遍后才可以查看`*_reference.csv`，用于发现明显漏项，不能直接复制。
4. 脚本或负责人比较A/B结果；不一致项由第三人裁决并写入`*_adjudicated.csv`。
5. 裁决表冻结后不得继续调标签。模型调优必须另用训练集，最终只在冻结金标上运行一次。

## 字段格式

- 多值字段统一填写JSON数组，例如`["Python", "SQL"]`。
- `is_parseable`只填`yes`或`no`；无法从原文确定的字段不要猜测。
- JD技能只标原文明确要求或明确偏好的能力，分别放入必需和可选字段。
- 职责按原文语义拆分成短句数组，不补充原文不存在的职责。
- 简历年限只填写原文可核验数字；无法确定时留空。
- 匹配等级统一为0=不匹配、1=较弱、2=可推荐、3=高度匹配；必须先判断硬约束。
- 同义技能使用标准名称，但必须在`notes`记录原文写法。

## 金标要求

- 正式报告至少使用100条JD、100份简历和100组平衡人岗匹配样本。
- A/B独立标注，一致率和裁决数量需要进入最终报告。
- AI预标注只能辅助，不能由同一个模型既生成金标又接受该金标评测。
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build reproducible task-book gold annotation pack")
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--jd-count", type=int, default=100)
    parser.add_argument("--resume-count", type=int, default=100)
    parser.add_argument("--matching-count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260830)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    jobs_path = args.dataset_dir / "jobs.jsonl"
    resumes_path = args.dataset_dir / "candidate_profiles.jsonl"
    labels_path = args.dataset_dir / "label_pairs_gold.jsonl"
    jobs = read_jsonl(jobs_path)
    all_resumes = read_jsonl(resumes_path)
    resumes = [row for row in all_resumes if row.get("split") == "test"]
    matching_labels = read_jsonl(labels_path)
    rng = random.Random(args.seed)
    jd_sample, jd_groups = stratified_sample(jobs, "source_type", args.jd_count, rng)
    resume_sample, resume_groups = stratified_sample(
        resumes, "target_job_family", args.resume_count, rng
    )
    if args.matching_count < 2:
        raise ValueError("matching-count must be at least 2")
    positives = [row for row in matching_labels if int(row.get("grade", 0)) >= 2]
    negatives = [row for row in matching_labels if int(row.get("grade", 0)) < 2]
    if len(matching_labels) < args.matching_count:
        raise ValueError("Not enough source pairs for the requested matching sample")
    positive_count = min(args.matching_count // 2, len(positives))
    negative_count = args.matching_count - positive_count
    if negative_count > len(negatives):
        negative_count = len(negatives)
        positive_count = args.matching_count - negative_count
    if positive_count > len(positives):
        raise ValueError("Not enough positive and negative source pairs for the requested sample")
    matching_sample = rng.sample(positives, positive_count) + rng.sample(negatives, negative_count)
    rng.shuffle(matching_sample)

    jd_rows = jd_blind_rows(jd_sample)
    resume_rows = resume_blind_rows(resume_sample)
    candidate_map = {row["candidate_id"]: row for row in all_resumes}
    job_map = {row["job_id"]: row for row in jobs}
    matching_rows = matching_blind_rows(matching_sample, candidate_map, job_map)
    jd_fields = list(jd_rows[0])
    resume_fields = list(resume_rows[0])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ("A", "B", "adjudicated"):
        write_csv(args.output_dir / f"jd_annotation_{suffix}.csv", jd_fields, jd_rows)
        write_csv(args.output_dir / f"resume_annotation_{suffix}.csv", resume_fields, resume_rows)
        write_csv(
            args.output_dir / f"matching_annotation_{suffix}.csv",
            list(matching_rows[0]),
            matching_rows,
        )
    write_csv(
        args.output_dir / "jd_reference.csv",
        ["sample_id", "record_id", "reference_skills", "reference_warning"],
        reference_rows(jd_rows, jd_sample, "jd"),
    )
    write_csv(
        args.output_dir / "resume_reference.csv",
        [
            "sample_id",
            "record_id",
            "reference_skills",
            "reference_warning",
            "reference_years_experience",
            "reference_education",
        ],
        reference_rows(resume_rows, resume_sample, "resume"),
    )
    write_csv(
        args.output_dir / "matching_reference.csv",
        ["sample_id", "pair_id", "source_grade", "reference_warning"],
        [
            {
                "sample_id": row["sample_id"],
                "pair_id": source.get("pair_id", ""),
                "source_grade": source.get("grade", ""),
                "reference_warning": "历史迁移标签，仅供盲标完成后复核，不得直接复制为金标",
            }
            for row, source in zip(matching_rows, matching_sample)
        ],
    )
    (args.output_dir / "ANNOTATION_GUIDE.md").write_text(instructions(), encoding="utf-8")

    manifest = {
        "schema_version": "taskbook-gold-pack-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "seed": args.seed,
        "command": (
            "python scripts/build_taskbook_gold_pack.py "
            f"--output-dir {args.output_dir} "
            f"--jd-count {args.jd_count} --resume-count {args.resume_count} "
            f"--matching-count {args.matching_count} --seed {args.seed}"
        ),
        "inputs": {
            "jobs": {"path": str(jobs_path), "sha256": sha256(jobs_path), "rows": len(jobs)},
            "resumes": {
                "path": str(resumes_path),
                "sha256": sha256(resumes_path),
                "test_rows": len(resumes),
            },
            "matching_labels": {
                "path": str(labels_path),
                "sha256": sha256(labels_path) if labels_path.exists() else "",
            },
        },
        "samples": {
            "jd_count": len(jd_sample),
            "jd_group_counts": jd_groups,
            "jd_ids": [row.get("job_id") for row in jd_sample],
            "resume_count": len(resume_sample),
            "resume_group_counts": resume_groups,
            "resume_ids": [row.get("candidate_id") for row in resume_sample],
            "matching_count": len(matching_sample),
            "matching_positive_source_count": positive_count,
            "matching_negative_source_count": negative_count,
            "matching_pair_ids": [row.get("pair_id") for row in matching_sample],
        },
        "gold_policy": "two independent human annotators plus third-person adjudication",
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"output": str(args.output_dir), "samples": manifest["samples"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
