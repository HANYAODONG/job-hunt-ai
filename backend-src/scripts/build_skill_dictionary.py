"""Build a draft skill dictionary CSV from a plain skill list.

This utility is for local iteration. The curated dictionary used by the backend lives at
backend-src/standard_skill_dictionary.csv.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build draft standard_skill_dictionary.csv")
    parser.add_argument("--input", type=Path, default=REPO_ROOT / "artifacts" / "kg" / "skills_temp.txt")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "artifacts" / "kg" / "standard_skill_dictionary_draft.csv")
    args = parser.parse_args()

    skills = [line.strip() for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["skill_id", "canonical_name", "aliases", "skill_category", "parent_skill", "match_pattern", "source", "version"])
        for idx, skill in enumerate(skills, 1):
            writer.writerow([f"SK{idx:03d}", skill, "", "通用技能", "", "", "local_draft", "v1"])
    print(f"Wrote {len(skills)} draft skills to {args.output}")


if __name__ == "__main__":
    main()