"""Build evidence-backed skill profiles for standardized job families.

The script is an offline baseline inspired by job-skill knowledge graph
research. Each JD contributes at most one vote per skill. Skill support is
combined with an IDF-style factor so that broadly shared skills do not crowd
out skills that distinguish one job family from another.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = REPO_ROOT / "artifacts" / "dataset_iteration_05" / "jobs.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "job_skill_analysis"
TERM_SPLIT_PATTERN = re.compile(r"[;；,，、|\n]+")


@dataclass(frozen=True)
class ProfileConfig:
    min_family_jobs: int = 5
    core_support: float = 0.30
    bonus_support: float = 0.10
    new_skill_support: float = 0.05
    top_k: int = 20
    evidence_limit: int = 5

    def validate(self) -> None:
        if self.min_family_jobs < 1:
            raise ValueError("min_family_jobs must be at least 1")
        if not 0 <= self.bonus_support <= self.core_support <= 1:
            raise ValueError(
                "support thresholds must satisfy "
                "0 <= bonus_support <= core_support <= 1"
            )
        if not 0 <= self.new_skill_support <= 1:
            raise ValueError("new_skill_support must be between 0 and 1")
        if self.top_k < 1 or self.evidence_limit < 1:
            raise ValueError("top_k and evidence_limit must be at least 1")


def first_text(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def split_terms(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_values = value
    elif value is None:
        raw_values = []
    else:
        raw_values = TERM_SPLIT_PATTERN.split(str(value))

    terms: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        term = str(raw_value).strip()
        key = term.casefold()
        if term and key not in seen:
            seen.add(key)
            terms.append(term)
    return terms


def unique_terms(*groups: Iterable[Any]) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for raw_value in group:
            term = str(raw_value).strip()
            key = term.casefold()
            if term and key not in seen:
                seen.add(key)
                terms.append(term)
    return terms


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Invalid JSONL at {path}:{line_number}: {exc}"
                    ) from exc
                if isinstance(payload, dict):
                    records.append(payload)
        return records

    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict) and isinstance(payload.get("jobs"), list):
            return [
                item for item in payload["jobs"] if isinstance(item, dict)
            ]
        raise ValueError("JSON input must be a list or contain a jobs list")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_job(record: dict[str, Any], row_number: int) -> dict[str, Any]:
    primary_skills = split_terms(
        record.get("skills") or record.get("required_skills")
    )
    traditional_skills = split_terms(record.get("traditional_skills"))
    new_skills = split_terms(record.get("new_skills"))
    return {
        "job_id": first_text(record, "job_id", "id")
        or f"row_{row_number:06d}",
        "job_family": first_text(record, "standard_job", "job_family"),
        "skills": unique_terms(
            primary_skills, traditional_skills, new_skills
        ),
        "new_skills": new_skills,
    }


def normalize_jobs(records: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        normalize_job(record, index)
        for index, record in enumerate(records, start=1)
    ]


def skill_payload(
    skill: str,
    count: int,
    family_job_count: int,
    family_document_frequency: int,
    family_count: int,
    evidence: Sequence[str],
    new_skill_count: int,
) -> dict[str, Any]:
    support = count / family_job_count
    idf = math.log((family_count + 1) / (family_document_frequency + 1)) + 1
    distinctive_score = support * idf
    return {
        "skill": skill,
        "job_count": count,
        "support": round(support, 6),
        "idf": round(idf, 6),
        "distinctive_score": round(distinctive_score, 6),
        "new_skill_job_count": new_skill_count,
        "new_skill_support": round(new_skill_count / family_job_count, 6),
        "evidence_job_ids": list(evidence),
    }


def build_profiles(
    jobs: Sequence[dict[str, Any]],
    config: ProfileConfig,
) -> dict[str, Any]:
    config.validate()

    family_jobs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    skipped_missing_family = 0
    for job in jobs:
        family = str(job.get("job_family") or "").strip()
        if not family:
            skipped_missing_family += 1
            continue
        family_jobs[family].append(job)

    eligible_families = {
        family: rows
        for family, rows in family_jobs.items()
        if len(rows) >= config.min_family_jobs
    }

    skill_family_frequency: Counter[str] = Counter()
    skill_display_names: dict[str, str] = {}
    for rows in eligible_families.values():
        family_skills: set[str] = set()
        for job in rows:
            for skill in unique_terms(job.get("skills", [])):
                key = skill.casefold()
                family_skills.add(key)
                skill_display_names.setdefault(key, skill)
        skill_family_frequency.update(family_skills)

    family_count = len(eligible_families)
    profiles: list[dict[str, Any]] = []
    statistics: list[dict[str, Any]] = []

    for family in sorted(eligible_families):
        rows = eligible_families[family]
        skill_counts: Counter[str] = Counter()
        new_skill_counts: Counter[str] = Counter()
        evidence: dict[str, list[str]] = defaultdict(list)

        for job in rows:
            job_id = str(job["job_id"])
            for skill in unique_terms(job.get("skills", [])):
                key = skill.casefold()
                skill_display_names.setdefault(key, skill)
                skill_counts[key] += 1
                if len(evidence[key]) < config.evidence_limit:
                    evidence[key].append(job_id)
            for skill in unique_terms(job.get("new_skills", [])):
                new_skill_counts[skill.casefold()] += 1

        ranked_skills = [
            skill_payload(
                skill=skill_display_names[key],
                count=count,
                family_job_count=len(rows),
                family_document_frequency=skill_family_frequency[key],
                family_count=family_count,
                evidence=evidence[key],
                new_skill_count=new_skill_counts[key],
            )
            for key, count in skill_counts.items()
        ]
        ranked_skills.sort(
            key=lambda item: (
                -item["distinctive_score"],
                -item["support"],
                item["skill"].casefold(),
            )
        )

        by_support = sorted(
            ranked_skills,
            key=lambda item: (
                -item["support"],
                -item["distinctive_score"],
                item["skill"].casefold(),
            ),
        )
        core_skills = [
            item
            for item in by_support
            if item["support"] >= config.core_support
        ][: config.top_k]
        bonus_skills = [
            item
            for item in by_support
            if config.bonus_support
            <= item["support"]
            < config.core_support
        ][: config.top_k]
        new_skill_signals = [
            item
            for item in ranked_skills
            if item["new_skill_support"] >= config.new_skill_support
        ][: config.top_k]

        for rank, item in enumerate(ranked_skills, start=1):
            statistics.append(
                {
                    "job_family": family,
                    "family_job_count": len(rows),
                    "skill": item["skill"],
                    "skill_rank": rank,
                    "job_count": item["job_count"],
                    "support": item["support"],
                    "idf": item["idf"],
                    "distinctive_score": item["distinctive_score"],
                    "new_skill_job_count": item["new_skill_job_count"],
                    "new_skill_support": item["new_skill_support"],
                }
            )

        profiles.append(
            {
                "job_family": family,
                "job_count": len(rows),
                "core_skills": core_skills,
                "bonus_skills": bonus_skills,
                "distinctive_skills": ranked_skills[: config.top_k],
                "new_skill_signals": new_skill_signals,
            }
        )

    return {
        "profiles": profiles,
        "statistics": statistics,
        "summary": {
            "input_jobs": len(jobs),
            "jobs_with_family": len(jobs) - skipped_missing_family,
            "jobs_missing_family": skipped_missing_family,
            "observed_job_families": len(family_jobs),
            "profiled_job_families": family_count,
            "families_below_minimum": len(family_jobs) - family_count,
            "unique_profiled_skills": len(skill_family_frequency),
            "config": {
                "min_family_jobs": config.min_family_jobs,
                "core_support": config.core_support,
                "bonus_support": config.bonus_support,
                "new_skill_support": config.new_skill_support,
                "top_k": config.top_k,
                "evidence_limit": config.evidence_limit,
            },
        },
    }


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(
                json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            )
            handle.write("\n")
            count += 1
    return count


def write_statistics_csv(
    path: Path, records: Sequence[dict[str, Any]]
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "job_family",
        "family_job_count",
        "skill",
        "skill_rank",
        "job_count",
        "support",
        "idf",
        "distinctive_score",
        "new_skill_job_count",
        "new_skill_support",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    return len(records)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build job-family skill profiles using support and IDF"
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-family-jobs", type=int, default=5)
    parser.add_argument("--core-support", type=float, default=0.30)
    parser.add_argument("--bonus-support", type=float, default=0.10)
    parser.add_argument("--new-skill-support", type=float, default=0.05)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--evidence-limit", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = ProfileConfig(
        min_family_jobs=args.min_family_jobs,
        core_support=args.core_support,
        bonus_support=args.bonus_support,
        new_skill_support=args.new_skill_support,
        top_k=args.top_k,
        evidence_limit=args.evidence_limit,
    )
    records = read_records(args.input.resolve())
    jobs = normalize_jobs(records)
    result = build_profiles(jobs, config)

    output_dir = args.output_dir.resolve()
    profiles_path = output_dir / "job_skill_profiles.jsonl"
    statistics_path = output_dir / "skill_statistics.csv"
    report_path = output_dir / "profile_report.json"

    profile_count = write_jsonl(profiles_path, result["profiles"])
    statistic_count = write_statistics_csv(
        statistics_path, result["statistics"]
    )
    report = {
        **result["summary"],
        "input_path": str(args.input.resolve()),
        "outputs": {
            "profiles": str(profiles_path),
            "statistics": str(statistics_path),
        },
        "written_profiles": profile_count,
        "written_statistics": statistic_count,
        "notes": [
            "Each JD contributes at most one vote per skill.",
            "new_skill_signals reflect source labels and are not proof of temporal emergence.",
            "Thresholds are baseline values and must be calibrated with expert review.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
