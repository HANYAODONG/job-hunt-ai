"""Freeze machine-assisted labels after an explicit human team review."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD_DIR = REPO_ROOT / "artifacts" / "taskbook_gold_v2_400"
SHEETS = (
    "jd_annotation_adjudicated.csv",
    "resume_annotation_adjudicated.csv",
    "matching_annotation_adjudicated.csv",
)


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


def approve_sheet(path: Path, reviewer_group: str) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    if not rows or "annotator" not in fields or "notes" not in fields:
        raise ValueError(f"Invalid adjudication sheet: {path}")
    for row in rows:
        previous = row.get("annotator", "").strip() or "unknown"
        note = row.get("notes", "").strip()
        audit_note = (
            f"小组人工复核通过；复核组={reviewer_group}；"
            f"原始预标来源={previous}"
        )
        row["annotator"] = "team_human_review_approved"
        row["notes"] = f"{note}；{audit_note}" if note else audit_note
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Approve reviewed task-book gold sheets")
    parser.add_argument("--gold-dir", type=Path, default=DEFAULT_GOLD_DIR)
    parser.add_argument("--reviewer-group", default="项目小组")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = [args.gold_dir / name for name in SHEETS]
    before = {path.name: sha256(path) for path in paths}
    counts = {path.name: approve_sheet(path, args.reviewer_group) for path in paths}
    after = {path.name: sha256(path) for path in paths}
    manifest = {
        "status": "human_review_approved",
        "formal_acceptance_eligible": True,
        "review_method": "team_review_of_machine_assisted_prelabels",
        "reviewer_group": args.reviewer_group,
        "individual_reviewer_names_recorded": False,
        "approval_assertion": "The project team reported that all rows were reviewed and no label issues remained.",
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "rows": counts,
        "pre_review_sha256": before,
        "approved_sha256": after,
        "limitations": "This was a team review of prelabels, not two independent blind annotations.",
    }
    output = args.gold_dir / "human_review_approval_manifest.json"
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
