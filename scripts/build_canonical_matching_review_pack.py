"""Build a resume review pack for canonical-pool matching evaluation.

The pack is intentionally an annotation pack, not a frozen gold set. It selects
unique test-split candidate profiles and real canonical JD options while leaving
the final human-accepted role/JD fields blank.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from canonical_job_title import canonical_job_title


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JOBS = REPO_ROOT / "artifacts" / "canonical_role_pool_v1" / "data_group_current" / "canonical_jobs.jsonl"
DEFAULT_CANDIDATES = REPO_ROOT / "artifacts" / "dataset_iteration_05" / "candidate_profiles.jsonl"
DEFAULT_ROLE_MAP = REPO_ROOT / "backend-src" / "app" / "data" / "canonical_role_pool" / "v1" / "source_role_mapping.csv"
DEFAULT_OUTPUT = REPO_ROOT / "artifacts" / "canonical_matching_review_v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def read_role_map(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row["source_standard_job"]: row for row in csv.DictReader(handle)}


def skill_keys(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {str(value).strip().casefold() for value in values if str(value).strip()}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def choose_candidates(
    profiles: list[dict[str, Any]],
    role_map: dict[str, dict[str, str]],
    available_role_ids: set[str],
    count: int,
    seed: int,
) -> list[dict[str, Any]]:
    groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for profile in profiles:
        source_role = str(profile.get("target_job_family") or "").strip()
        role_id = str(role_map.get(source_role, {}).get("role_id") or "")
        if role_id in available_role_ids:
            groups[role_id].append(profile)
    if not groups:
        raise ValueError("No test profiles map to active canonical roles")

    rng = random.Random(seed)
    role_ids = sorted(groups)
    selected: list[dict[str, Any]] = []
    # Round-robin sampling preserves rare active roles without duplicating profiles.
    shuffled = {role_id: sorted(rows, key=lambda row: str(row.get("candidate_id"))) for role_id, rows in groups.items()}
    while len(selected) < count:
        progressed = False
        for role_id in role_ids:
            rows = shuffled[role_id]
            if not rows:
                continue
            index = rng.randrange(len(rows)) if len(rows) > 1 else 0
            selected.append(rows.pop(index))
            progressed = True
            if len(selected) == count:
                break
        if not progressed:
            break
    if len(selected) < count:
        raise ValueError(f"Only {len(selected)} eligible profiles available; need {count}")
    return selected


def select_job_options(
    profile: dict[str, Any],
    jobs_by_role: dict[str, list[dict[str, Any]]],
    all_jobs: list[dict[str, Any]],
    role_id: str,
    limit_same: int,
    limit_negative: int,
) -> list[dict[str, Any]]:
    profile_skills = skill_keys(profile.get("skills_normalized") or profile.get("skills"))
    same_role = jobs_by_role.get(role_id, [])

    def overlap(job: dict[str, Any]) -> tuple[float, int]:
        required = skill_keys(job.get("required_skills") or job.get("skills"))
        shared = len(profile_skills & required)
        ratio = shared / len(required) if required else 0.0
        return ratio, shared

    ranked_same = sorted(same_role, key=lambda job: (-overlap(job)[0], -overlap(job)[1], str(job.get("job_id"))))
    if len(ranked_same) <= limit_same:
        options = ranked_same
    else:
        # Keep a strong, middle, and weak same-role example for boundary review.
        indexes = sorted({0, len(ranked_same) // 2, len(ranked_same) - 1})[:limit_same]
        options = [ranked_same[index] for index in indexes]

    other = [job for job in all_jobs if str(job.get("canonical_role_id") or "") != role_id]
    # Prefer cross-role jobs with overlapping skills: these are useful hard negatives.
    ranked_other = sorted(other, key=lambda job: (-overlap(job)[0], -overlap(job)[1], str(job.get("job_id"))))
    options.extend(ranked_other[:limit_negative])
    return options


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build canonical matching annotation pack")
    parser.add_argument("--jobs", type=Path, default=DEFAULT_JOBS)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--role-map", type=Path, default=DEFAULT_ROLE_MAP)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--count", type=int, default=400)
    parser.add_argument("--seed", type=int, default=20260831)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    jobs = [row for row in read_jsonl(args.jobs) if row.get("role_mapping_status") == "mapped"]
    profiles = [row for row in read_jsonl(args.candidates) if row.get("split") == "test"]
    role_map = read_role_map(args.role_map)
    available_role_ids = {str(row.get("canonical_role_id") or "") for row in jobs}
    selected = choose_candidates(profiles, role_map, available_role_ids, args.count, args.seed)

    jobs_by_role: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for job in jobs:
        jobs_by_role[str(job.get("canonical_role_id") or "")].append(job)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    case_rows: list[dict[str, Any]] = []
    option_rows: list[dict[str, Any]] = []
    for index, profile in enumerate(selected, start=1):
        candidate_id = str(profile.get("candidate_id") or "")
        source_role = str(profile.get("target_job_family") or "")
        role_id = str(role_map[source_role]["role_id"])
        case_id = f"CM-{index:03d}"
        case_rows.append({
            "case_id": case_id,
            "candidate_id": candidate_id,
            "source_target_role": source_role,
            "target_canonical_role_id": role_id,
            "candidate_text": profile.get("profile_text") or profile.get("summary") or "",
            "candidate_skills": json.dumps(profile.get("skills_normalized") or profile.get("skills") or [], ensure_ascii=False),
            "years_experience": profile.get("years_experience"),
            "gold_canonical_role_id": "",
            "gold_accepted_job_ids": "",
            "gold_rejected_job_ids": "",
            "review_decision": "",
            "reviewer": "",
            "notes": "",
        })
        options = select_job_options(profile, jobs_by_role, jobs, role_id, limit_same=3, limit_negative=2)
        for option_index, job in enumerate(options, start=1):
            option_rows.append({
                "case_id": case_id,
                "option_rank": option_index,
                "job_id": job.get("job_id", ""),
                "job_title": job.get("title", ""),
                "job_title_label": canonical_job_title(job),
                "canonical_role_id": job.get("canonical_role_id", ""),
                "canonical_role": job.get("canonical_role", ""),
                "standard_category": job.get("standard_category", ""),
                "standard_direction": job.get("standard_direction", ""),
                "required_skills": json.dumps(job.get("required_skills") or job.get("skills") or [], ensure_ascii=False),
                "job_description": job.get("description", ""),
                "human_accept": "",
                "human_reason": "",
            })

    cases_path = args.output_dir / "resume_job_cases.csv"
    options_path = args.output_dir / "job_options.jsonl"
    write_csv(cases_path, case_rows)
    with options_path.open("w", encoding="utf-8") as handle:
        for row in option_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    manifest = {
        "version": "canonical_matching_review_v1",
        "status": "pending_human_annotation",
        "purpose": f"{len(case_rows)} independent resume cases with real canonical JD options",
        "resume_source": str(args.candidates),
        "resume_source_note": "The current candidate profiles originate from synthetic_detailed_resumes_experience_30k.csv; replace with de-identified real resumes before claiming a real-resume benchmark.",
        "jobs_source": str(args.jobs),
        "cases": len(case_rows),
        "job_options": len(option_rows),
        "unique_candidates": len({row["candidate_id"] for row in case_rows}),
        "active_role_ids_in_cases": len({str(row["canonical_role_id"]) for row in option_rows if row["option_rank"] == 1}),
        "annotation_rule": "Human reviewer must choose the canonical role and one or more acceptable normalized job title labels from the full resume/JD evidence; concrete JD IDs remain evidence records, not the final label.",
        "job_title_label_rule": "Use canonical role name as the closed-set title; retain an explicit programming-language prefix only for backend titles.",
        "outputs": {
            "cases": cases_path.name,
            "job_options": options_path.name,
        },
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output_dir / "source_hashes.json").write_text(json.dumps({
        "jobs": sha256(args.jobs),
        "candidates": sha256(args.candidates),
        "role_map": sha256(args.role_map),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
