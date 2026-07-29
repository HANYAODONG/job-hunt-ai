"""Batch extract standardized skills from normalized workflow data.

Generated CSV files are written under artifacts/kg/ by default and should stay local.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.skill_extractor import SkillExtractor


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def extract_jobs(extractor: SkillExtractor, input_path: Path, output_path: Path) -> int:
    count = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["job_id", "title", "extracted_skills", "skill_count"])
        for job in iter_jsonl(input_path):
            text = f"{job.get('title', '')} {job.get('description', '')}"
            skills = extractor.extract(text)
            writer.writerow([job.get("job_id", ""), job.get("title", ""), ";".join(skills), len(skills)])
            count += 1
    return count


def extract_resumes(extractor: SkillExtractor, input_path: Path, output_path: Path) -> int:
    count = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["candidate_id", "summary_preview", "extracted_skills", "skill_count"])
        for candidate in iter_jsonl(input_path):
            text = f"{candidate.get('summary', '')} {candidate.get('profile_text', '')}"
            skills = extractor.extract(text)
            writer.writerow([candidate.get("candidate_id", ""), candidate.get("summary", "")[:50], ";".join(skills), len(skills)])
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract skills from normalized jobs/resumes")
    parser.add_argument("--dataset-dir", type=Path, default=REPO_ROOT / "artifacts" / "dataset_iteration_05")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "artifacts" / "kg")
    args = parser.parse_args()

    extractor = SkillExtractor()
    jobs_path = args.dataset_dir / "jobs.jsonl"
    resumes_path = args.dataset_dir / "candidate_profiles.jsonl"

    if jobs_path.exists():
        print(f"Extracted job skills for {extract_jobs(extractor, jobs_path, args.output_dir / 'skills_output_jobs.csv')} records")
    else:
        print(f"Skip jobs: missing {jobs_path}")

    if resumes_path.exists():
        print(f"Extracted resume skills for {extract_resumes(extractor, resumes_path, args.output_dir / 'skills_output_resumes.csv')} records")
    else:
        print(f"Skip resumes: missing {resumes_path}")


if __name__ == "__main__":
    main()