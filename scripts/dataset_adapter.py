"""Adapt dataset-group artifacts into JobMatch AI intermediate files.

Workflow 1 scope:
- Convert external CSV/JSONL files into stable JSONL manifests.
- Emit team-wide schema fields used by downstream workflows.
- Emit a small sample pack for parallel development.
- Keep this offline and deterministic.
- Do not train models.
- Do not emit phone/email/name fields.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


DEFAULT_DATASET_DIR = Path(__file__).resolve().parents[2] / "database"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "dataset_iteration_04"


def read_csv_rows(path: Path, encodings: tuple[str, ...] = ("utf-8-sig", "utf-8", "gb18030")) -> list[dict[str, str]]:
    last_error: Exception | None = None
    for encoding in encodings:
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return list(csv.DictReader(handle))
        except UnicodeDecodeError as exc:
            last_error = exc
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Cannot decode {path}: {last_error}")


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
            count += 1
    return count


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_json_field(value: str, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def split_semicolon(value: str) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(";") if item.strip()]


def safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value == "" or value is None:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value == "" or value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def adapt_candidate_profiles(resume_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for row in resume_rows:
        skills = parse_json_field(row.get("skills_normalized", ""), [])
        skill_levels = parse_json_field(row.get("skill_levels", ""), {})
        experience = parse_json_field(row.get("experience", ""), [])
        projects = parse_json_field(row.get("projects", ""), [])
        profiles.append(
            {
                "candidate_id": row.get("resume_id", ""),
                "resume_id": row.get("resume_id", ""),
                "source_resume_id": row.get("resume_id", ""),
                "split": row.get("split", ""),
                "summary": row.get("profile_text", ""),
                "target_job_family": row.get("target_job_family", ""),
                "preferred_location": row.get("preferred_location", ""),
                "skills": skills,
                "education": {
                    "education": row.get("education", ""),
                    "degree": row.get("degree", ""),
                    "school_category": row.get("school_category", ""),
                    "major": row.get("major", ""),
                    "english_level": row.get("english_level", ""),
                },
                "years_experience": safe_int(row.get("years_experience"), 0),
                "skills_normalized": skills,
                "skill_levels": skill_levels,
                "experience": experience,
                "projects": projects,
                "profile_text": row.get("profile_text", ""),
            }
        )
    return profiles


def adapt_jobs_from_silver(silver_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    jobs: dict[str, dict[str, Any]] = {}
    family_votes: dict[str, Counter[str]] = defaultdict(Counter)
    skill_votes: dict[str, Counter[str]] = defaultdict(Counter)

    for record in silver_records:
        job_id = str(record.get("job_id", "")).strip()
        if not job_id:
            continue
        family = str(record.get("target_job_family", "")).strip()
        if family:
            family_votes[job_id][family] += 1
        for skill in record.get("matched_skills") or []:
            if skill:
                skill_votes[job_id][str(skill)] += 1
        if job_id not in jobs:
            jobs[job_id] = {
                "job_id": job_id,
                "id": job_id,
                "title": record.get("job_title", ""),
                "description": record.get("job_description", ""),
                "company": record.get("company_name", ""),
                "company_name": record.get("company_name", ""),
                "location": record.get("location", ""),
                "location_text": record.get("location", ""),
                "source_url": record.get("source_url", ""),
                "source": record.get("source_type", "") or "dataset_group_silver_jsonl",
                "source_type": record.get("source_type", ""),
                "tags": record.get("tags", []),
                "skills": [],
                "job_family": "",
                "required_skills": [],
                "search_metadata": {
                    "source": "dataset_group_silver_jsonl",
                    "source_job_id": job_id,
                    "silver_method": record.get("silver_method", ""),
                },
            }

    adapted: list[dict[str, Any]] = []
    for job_id, job in jobs.items():
        top_family = family_votes[job_id].most_common(1)
        top_skills = [skill for skill, _ in skill_votes[job_id].most_common()]
        job["skills"] = top_skills
        job["job_family"] = top_family[0][0] if top_family else ""
        job["required_skills"] = top_skills
        job["search_metadata"]["candidate_target_job_families"] = dict(family_votes[job_id])
        job["search_metadata"]["dominant_target_job_family"] = top_family[0][0] if top_family else ""
        job["search_metadata"]["matched_skill_counts"] = dict(skill_votes[job_id])
        adapted.append(job)
    return sorted(adapted, key=lambda item: item["id"])


def adapt_silver_pairs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for record in records:
        pairs.append(
            {
                "candidate_id": record.get("resume_id", ""),
                "resume_id": record.get("resume_id", ""),
                "job_id": record.get("job_id", ""),
                "pair_key": f"{record.get('resume_id', '')}::{record.get('job_id', '')}",
                "target_job_family": record.get("target_job_family", ""),
                "label_source": "silver",
                "grade": safe_int(record.get("silver_grade"), 0),
                "score": safe_float(record.get("silver_score"), 0.0),
                "bm25_rank": safe_int(record.get("bm25_rank")),
                "bm25_score": safe_float(record.get("bm25_score")),
                "semantic_rank": safe_int(record.get("semantic_rank")),
                "semantic_score": safe_float(record.get("semantic_score")),
                "family_match": safe_float(record.get("family_match"), 0.0),
                "skill_coverage": safe_float(record.get("skill_coverage"), 0.0),
                "matched_skills": record.get("matched_skills") or [],
            }
        )
    return pairs


def adapt_gold_pairs(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for row in rows:
        pairs.append(
            {
                "pair_id": row.get("pair_id", ""),
                "candidate_id": row.get("resume_id", ""),
                "resume_id": row.get("resume_id", ""),
                "job_id": row.get("job_id", ""),
                "pair_key": f"{row.get('resume_id', '')}::{row.get('job_id', '')}",
                "target_job_family": row.get("target_job_family", ""),
                "label_source": "gold",
                "grade": safe_int(row.get("relevance_grade"), 0),
                "hard_constraint_pass": row.get("hard_constraint_pass", ""),
                "matched_skills": split_semicolon(row.get("matched_skills", "")),
                "missing_required_skills": split_semicolon(row.get("missing_required_skills", "")),
                "missing_optional_skills": split_semicolon(row.get("missing_optional_skills", "")),
                "transferable_skills": split_semicolon(row.get("transferable_skills", "")),
                "resume_evidence": row.get("resume_evidence", ""),
                "job_evidence": row.get("job_evidence", ""),
                "annotator_id": row.get("annotator_id", ""),
                "notes": row.get("notes", ""),
            }
        )
    return pairs


def grade_counts(records: Iterable[dict[str, Any]], key: str = "grade") -> dict[str, int]:
    counts = Counter(str(record.get(key, "")) for record in records)
    return dict(sorted(counts.items()))


def missing_field_count(records: list[dict[str, Any]], fields: list[str]) -> dict[str, int]:
    missing: dict[str, int] = {}
    for field in fields:
        missing[field] = sum(1 for record in records if record.get(field) in (None, "", []))
    return missing


def write_sample_pack(
    output_dir: Path,
    candidate_profiles: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    silver_pairs: list[dict[str, Any]],
    gold_pairs: list[dict[str, Any]],
) -> dict[str, int]:
    sample_dir = output_dir / "sample_pack"
    sample_candidates = candidate_profiles[:5]
    sample_candidate_ids = {item["candidate_id"] for item in sample_candidates}

    candidate_gold_pairs = [pair for pair in gold_pairs if pair.get("candidate_id") in sample_candidate_ids]
    candidate_silver_pairs = [pair for pair in silver_pairs if pair.get("candidate_id") in sample_candidate_ids]

    job_ids: list[str] = []
    for pair in candidate_gold_pairs + candidate_silver_pairs:
        job_id = str(pair.get("job_id", ""))
        if job_id and job_id not in job_ids:
            job_ids.append(job_id)
        if len(job_ids) >= 10:
            break

    if len(job_ids) < 10:
        for job in jobs:
            job_id = str(job.get("job_id", ""))
            if job_id and job_id not in job_ids:
                job_ids.append(job_id)
            if len(job_ids) >= 10:
                break

    selected_job_ids = set(job_ids[:10])
    sample_jobs = [job for job in jobs if job.get("job_id") in selected_job_ids][:10]
    sample_gold_pairs = [pair for pair in candidate_gold_pairs if pair.get("job_id") in selected_job_ids]
    sample_silver_pairs = [pair for pair in candidate_silver_pairs if pair.get("job_id") in selected_job_ids]

    counts = {
        "candidate_profiles_sample": write_jsonl(sample_dir / "candidate_profiles_sample.jsonl", sample_candidates),
        "jobs_sample": write_jsonl(sample_dir / "jobs_sample.jsonl", sample_jobs),
        "label_pairs_gold_sample": write_jsonl(sample_dir / "label_pairs_gold_sample.jsonl", sample_gold_pairs),
        "label_pairs_silver_sample": write_jsonl(sample_dir / "label_pairs_silver_sample.jsonl", sample_silver_pairs),
    }
    write_json(
        sample_dir / "sample_manifest.json",
        {
            "purpose": "small fixed sample pack for parallel workflow development",
            "counts": counts,
            "candidate_ids": sorted(sample_candidate_ids),
            "job_ids": sorted(selected_job_ids),
            "notes": [
                "Use this sample pack when downstream workflows need stable local input before full data integration.",
                "Sample files intentionally stay under artifacts/ and are not committed by default.",
            ],
        },
    )
    return counts


def build_data_quality_report(
    candidate_profiles: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    silver_pairs: list[dict[str, Any]],
    gold_pairs: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate_ids = {profile.get("candidate_id") for profile in candidate_profiles}
    job_ids = {job.get("job_id") for job in jobs}

    def orphan_counts(pairs: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "missing_candidate_refs": sum(1 for pair in pairs if pair.get("candidate_id") not in candidate_ids),
            "missing_job_refs": sum(1 for pair in pairs if pair.get("job_id") not in job_ids),
        }

    return {
        "record_counts": {
            "candidate_profiles": len(candidate_profiles),
            "jobs": len(jobs),
            "label_pairs_silver": len(silver_pairs),
            "label_pairs_gold": len(gold_pairs),
        },
        "missing_fields": {
            "candidate_profiles": missing_field_count(
                candidate_profiles,
                ["candidate_id", "summary", "skills", "target_job_family"],
            ),
            "jobs": missing_field_count(
                jobs,
                ["job_id", "title", "description", "skills", "job_family", "company", "location", "source"],
            ),
            "label_pairs_silver": missing_field_count(
                silver_pairs,
                ["candidate_id", "job_id", "grade", "score"],
            ),
            "label_pairs_gold": missing_field_count(
                gold_pairs,
                ["candidate_id", "job_id", "grade"],
            ),
        },
        "reference_checks": {
            "silver": orphan_counts(silver_pairs),
            "gold": orphan_counts(gold_pairs),
        },
        "label_distribution": {
            "silver_grade_counts": grade_counts(silver_pairs),
            "gold_grade_counts": grade_counts(gold_pairs),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Adapt dataset-group artifacts for JobMatch AI.")
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    dataset_dir = args.dataset_dir
    output_dir = args.output_dir

    resumes_path = dataset_dir / "synthetic_detailed_resumes.csv"
    silver_path = dataset_dir / "resume_job_silver_30.jsonl"
    gold_path = dataset_dir / "金标30×20.csv"

    for path in [resumes_path, silver_path, gold_path]:
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    resume_rows = read_csv_rows(resumes_path)
    silver_records = list(read_jsonl(silver_path))
    gold_rows = read_csv_rows(gold_path)

    candidate_profiles = adapt_candidate_profiles(resume_rows)
    jobs = adapt_jobs_from_silver(silver_records)
    silver_pairs = adapt_silver_pairs(silver_records)
    gold_pairs = adapt_gold_pairs(gold_rows)

    counts = {
        "candidate_profiles": write_jsonl(output_dir / "candidate_profiles.jsonl", candidate_profiles),
        "jobs": write_jsonl(output_dir / "jobs.jsonl", jobs),
        "jobs_from_silver": write_jsonl(output_dir / "jobs_from_silver.jsonl", jobs),
        "label_pairs_silver": write_jsonl(output_dir / "label_pairs_silver.jsonl", silver_pairs),
        "label_pairs_gold": write_jsonl(output_dir / "label_pairs_gold.jsonl", gold_pairs),
    }
    sample_counts = write_sample_pack(output_dir, candidate_profiles, jobs, silver_pairs, gold_pairs)
    quality_report = build_data_quality_report(candidate_profiles, jobs, silver_pairs, gold_pairs)
    write_json(output_dir / "data_quality_report.json", quality_report)

    manifest = {
        "iteration": "04",
        "workflow": "workflow_1_data_foundation_and_label_evaluation",
        "purpose": "dataset_adapter_schema_samples_quality_no_training",
        "dataset_dir": str(dataset_dir),
        "output_dir": str(output_dir),
        "inputs": {
            "resumes": str(resumes_path),
            "silver": str(silver_path),
            "gold": str(gold_path),
        },
        "counts": counts,
        "sample_counts": sample_counts,
        "resume_splits": dict(Counter(profile["split"] for profile in candidate_profiles)),
        "resume_job_families": dict(Counter(profile["target_job_family"] for profile in candidate_profiles)),
        "silver_grade_counts": grade_counts(silver_pairs),
        "gold_grade_counts": grade_counts(gold_pairs),
        "data_quality_report": str(output_dir / "data_quality_report.json"),
        "notes": [
            "No model training is performed.",
            "PII fields such as name, phone, and email are not emitted.",
            "jobs.jsonl and jobs_from_silver.jsonl currently use unique jobs observed in silver pairs, not the full 23714-job corpus.",
            "sample_pack contains 10 jobs, 5 candidate profiles, and matching labels for downstream parallel development.",
        ],
    }
    write_json(output_dir / "dataset_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()