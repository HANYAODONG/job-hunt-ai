"""Fill adjudication sheets with provisional, machine-assisted reference labels.

These labels are useful for exercising the evaluation pipeline, but they are
not independent human gold. Blind A/B sheets are intentionally left untouched.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend-src"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.nlp_service import NLPService
from app.services.role_taxonomy import role_match_grade

DEFAULT_DATASET = REPO_ROOT / "artifacts" / "dataset_iteration_05"
DEFAULT_GOLD_DIR = REPO_ROOT / "artifacts" / "taskbook_gold_v1"
DEFAULT_MATCHING_PRELABELS = REPO_ROOT / "scripts" / "taskbook_matching_codex_prelabels.json"
ANNOTATOR = "codex_provisional_prelabel"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    rows: list[dict[str, Any]] = []
    index = 0
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        row, index = decoder.raw_decode(text, index)
        if isinstance(row, dict):
            rows.append(row)
    return rows


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def json_array(values: Any) -> str:
    if not isinstance(values, list):
        values = []
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value).strip()
        if item and item.casefold() not in seen:
            seen.add(item.casefold())
            result.append(item)
    return json.dumps(result, ensure_ascii=False)


def explicitly_present(text: str, values: Any) -> list[str]:
    """Keep source skills with literal evidence in the original text."""
    if not isinstance(values, list):
        return []
    text_cf = text.casefold()
    result = []
    for value in values:
        skill = str(value).strip()
        if not skill:
            continue
        skill_cf = skill.casefold()
        if skill.isascii():
            present = re.search(
                rf"(?<![A-Za-z0-9_]){re.escape(skill_cf)}(?![A-Za-z0-9_])",
                text_cf,
            ) is not None
        else:
            present = skill_cf in text_cf
        if present:
            result.append(skill)
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rubric_matching_grade(candidate: dict[str, Any], job: dict[str, Any]) -> int:
    return role_match_grade(
        str(candidate.get("target_job_family") or ""),
        str(job.get("title") or ""),
        str(job.get("job_family") or ""),
    )


def prefill_jd(
    gold_dir: Path, jobs: dict[str, dict[str, Any]], nlp_service: NLPService
) -> Path:
    path = gold_dir / "jd_annotation_adjudicated.csv"
    fields, rows = read_csv(path)
    for row in rows:
        source = jobs[row["job_id"]]
        source_skills = explicitly_present(
            row.get("description", ""),
            source.get("required_skills") or source.get("skills") or [],
        )
        evidence_skills = nlp_service.extract_job_requirements(
            row.get("description", "")
        ).get("required_skills", [])
        row["gold_required_skills"] = json_array(source_skills + evidence_skills)
        row["gold_optional_skills"] = "[]"
        row["gold_responsibilities"] = json_array(source.get("responsibilities") or [])
        row["is_parseable"] = "yes" if row.get("description", "").strip() else "no"
        row["annotator"] = ANNOTATOR
        row["notes"] = "临时预标注：结构字段原文核验与技能证据词典合并，待双人独立人工标注与裁决替换"
    write_csv(path, fields, rows)
    return path


def prefill_resume(gold_dir: Path, candidates: dict[str, dict[str, Any]]) -> Path:
    path = gold_dir / "resume_annotation_adjudicated.csv"
    fields, rows = read_csv(path)
    for row in rows:
        source = candidates[row["candidate_id"]]
        row["gold_name"] = "unknown"
        row["gold_skills"] = json_array(
            explicitly_present(
                row.get("resume_text", ""),
                source.get("skills_normalized") or source.get("skills") or [],
            )
        )
        years = source.get("years_experience")
        row["gold_years_experience"] = "" if years is None else str(years)
        education = source.get("education") or {}
        row["gold_education"] = json.dumps(education, ensure_ascii=False)
        titles = [
            item.get("role") or item.get("position") or ""
            for item in source.get("experience") or []
            if isinstance(item, dict)
        ]
        row["gold_experience_titles"] = json_array(titles)
        row["is_parseable"] = "yes" if row.get("resume_text", "").strip() else "no"
        row["annotator"] = ANNOTATOR
        row["notes"] = "临时预标注：来自标准候选人结构化字段，待双人独立人工标注与裁决替换"
    write_csv(path, fields, rows)
    return path


def prefill_matching(
    gold_dir: Path,
    labels_by_pair: dict[str, dict[str, Any]],
    codex_grades: dict[str, int],
    candidates: dict[str, dict[str, Any]],
    jobs: dict[str, dict[str, Any]],
    matching_mode: str,
) -> Path:
    path = gold_dir / "matching_annotation_adjudicated.csv"
    fields, rows = read_csv(path)
    for row in rows:
        source = labels_by_pair[row["pair_id"]]
        candidate = candidates[row["candidate_id"]]
        job = jobs[row["job_id"]]
        grade = (
            codex_grades[row["sample_id"]]
            if matching_mode == "codex-map"
            else rubric_matching_grade(candidate, job)
        )
        candidate_skills = {
            str(skill).strip().casefold()
            for skill in candidate.get("skills_normalized") or candidate.get("skills") or []
            if str(skill).strip()
        }
        required_skills = [
            str(skill).strip()
            for skill in job.get("required_skills") or job.get("skills") or []
            if str(skill).strip()
        ]
        matched = [skill for skill in required_skills if skill.casefold() in candidate_skills]
        missing = [skill for skill in required_skills if skill.casefold() not in candidate_skills]
        target_role = str(candidate.get("target_job_family") or "").strip()
        job_title = str(job.get("title") or "").strip()
        years = candidate.get("years_experience")
        row["gold_grade_0_to_3"] = str(grade)
        hard_pass = (
            str(source.get("hard_constraint_pass") or "unknown").strip().casefold()
            if matching_mode == "codex-map"
            else ("yes" if grade >= 2 else "no" if grade == 0 else "unknown")
        )
        row["hard_constraint_pass_yes_no"] = hard_pass
        row["matched_skills"] = json_array(source.get("matched_skills") or matched)
        row["missing_required_skills"] = json_array(
            source.get("missing_required_skills") or missing
        )
        row["annotator"] = (
            "codex_provisional_manual_review"
            if matching_mode == "codex-map"
            else "codex_provisional_role_rubric"
        )
        row["notes"] = (
            f"临时预标：等级{grade}；目标岗位={target_role or '未给出'}；"
            f"岗位标题={job_title or '未给出'}；命中技能{len(matched)}项；"
            f"缺失技能{len(missing)}项；经验={years if years is not None else '未知'}年。"
            "待双人独立人工标注与裁决替换"
        )
    write_csv(path, fields, rows)
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create provisional task-book adjudication labels")
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--gold-dir", type=Path, default=DEFAULT_GOLD_DIR)
    parser.add_argument(
        "--matching-mode",
        choices=("codex-map", "rubric"),
        default="codex-map",
        help="Use the reviewed 100-row map or the consistent role-family rubric",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    jobs = {row["job_id"]: row for row in read_jsonl(args.dataset_dir / "jobs.jsonl")}
    candidates = {
        row["candidate_id"]: row
        for row in read_jsonl(args.dataset_dir / "candidate_profiles.jsonl")
    }
    labels_by_pair = {
        row["pair_id"]: row for row in read_jsonl(args.dataset_dir / "label_pairs_gold.jsonl")
    }
    codex_payload = json.loads(DEFAULT_MATCHING_PRELABELS.read_text(encoding="utf-8"))
    codex_grades = codex_payload["grades"]
    nlp_service = NLPService()
    outputs = [
        prefill_jd(args.gold_dir, jobs, nlp_service),
        prefill_resume(args.gold_dir, candidates),
        prefill_matching(
            args.gold_dir,
            labels_by_pair,
            codex_grades,
            candidates,
            jobs,
            args.matching_mode,
        ),
    ]
    manifest_path = args.gold_dir / "provisional_prelabel_manifest.json"
    manifest = {
        "status": "provisional_machine_assisted_not_human_gold",
        "annotator": ANNOTATOR,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_policy": (
            "source fields with literal text evidence; JD draft also uses the project "
            f"evidence dictionary; matching mode={args.matching_mode}"
        ),
        "replacement_required": "Replace with independent A/B human annotations and third-person adjudication before final reporting",
        "outputs": {
            path.name: {"rows": len(read_csv(path)[1]), "sha256": sha256(path)}
            for path in outputs
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
