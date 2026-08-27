"""One-command Docker runner for the complete phase-6 JD quality acceptance."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    print("[workflow6]", " ".join(command), flush=True)
    subprocess.run(command, cwd=REPO_ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild and validate workflow 6")
    parser.add_argument("--skip-start", action="store_true", help="Reuse an already running backend")
    parser.add_argument("--skip-review", action="store_true", help="Reuse current DeepSeek judgments")
    parser.add_argument("--overwrite-review", action="store_true", help="Pay for a fresh 200-item review")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.skip_start:
        run(["docker", "compose", "up", "-d", "backend"])

    run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "backend",
            "python",
            "scripts/audit_jd_quality.py",
            "--input",
            "/app/artifacts/dataset_iteration_05/jobs.jsonl",
            "--output-dir",
            "/app/artifacts/jd_quality_audit",
        ]
    )

    if not args.skip_review:
        review_command = [
            "docker",
            "compose",
            "exec",
            "-T",
            "backend",
            "python",
            "scripts/review_jd_quality_with_deepseek.py",
            "--cleaned-jobs",
            "/app/artifacts/jd_quality_audit/jd_quality_cleaned.jsonl",
            "--sample",
            "/app/artifacts/jd_quality_audit/acceptance_sample_200.jsonl",
            "--output-dir",
            "/app/artifacts/jd_quality_deepseek_review",
            "--batch-size",
            "5",
            "--votes",
            "2",
            "--workers",
            "4",
            "--max-chars",
            "1000",
            "--min-confidence",
            "0.82",
        ]
        if args.overwrite_review:
            review_command.append("--overwrite")
        run(review_command)

    run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "backend",
            "python",
            "scripts/build_workflow6_acceptance_report.py",
            "--audit-dir",
            "/app/artifacts/jd_quality_audit",
            "--review-dir",
            "/app/artifacts/jd_quality_deepseek_review",
            "--output-dir",
            "/app/artifacts/workflow6_acceptance",
        ]
    )
    print(
        "[workflow6] report generated: artifacts/workflow6_acceptance/workflow6_acceptance_report.md",
        flush=True,
    )


if __name__ == "__main__":
    main()
