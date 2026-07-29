"""Collect raw skill names from normalized workflow JSONL files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def collect_from(path: Path) -> set[str]:
    skills: set[str] = set()
    if not path.exists():
        return skills
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            data = json.loads(line)
            for skill in data.get("skills", []):
                if skill:
                    skills.add(str(skill).strip())
    return skills


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect skills from jobs and candidate profiles")
    parser.add_argument("--dataset-dir", type=Path, default=REPO_ROOT / "artifacts" / "dataset_iteration_05")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "artifacts" / "kg" / "skills_temp.txt")
    args = parser.parse_args()

    skills = set()
    skills.update(collect_from(args.dataset_dir / "jobs.jsonl"))
    skills.update(collect_from(args.dataset_dir / "candidate_profiles.jsonl"))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for skill in sorted(skills):
            handle.write(skill + "\n")
    print(f"Collected {len(skills)} skills into {args.output}")


if __name__ == "__main__":
    main()