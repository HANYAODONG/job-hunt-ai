"""Prepare a versioned runtime role catalog and switch manifest.

This copies taxonomy metadata only; matching/ranking implementations are not
modified. The generated manifest can be used by offline builders and the
runtime via JOB_HUNT_CANONICAL_ROLE_POOL_PATH and
JOB_HUNT_CANONICAL_ROLE_DATA_DIR.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "artifacts" / "canonical_role_pool_v2"
V1_DATA = ROOT / "backend-src" / "app" / "data" / "canonical_role_pool" / "v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(version: str, pool_dir: Path, runtime_dir: Path) -> dict[str, object]:
    if not (pool_dir / "canonical_jobs.jsonl").exists():
        raise FileNotFoundError(pool_dir / "canonical_jobs.jsonl")
    if not (pool_dir / "canonical_roles.csv").exists():
        raise FileNotFoundError(pool_dir / "canonical_roles.csv")
    runtime_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pool_dir / "canonical_roles.csv", runtime_dir / "canonical_roles.csv")
    # Reuse v1 mappings/rules/neighbours, then add canonical names for roles
    # introduced in v2 so profile target labels resolve through the same class.
    for name in ("title_refinement_rules.csv", "skill_refinement_rules.csv", "role_neighbors.csv"):
        shutil.copy2(V1_DATA / name, runtime_dir / name)
    with (V1_DATA / "source_role_mapping.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    known = {row["source_standard_job"] for row in rows}
    role_rows = list(csv.DictReader((pool_dir / "canonical_roles.csv").open("r", encoding="utf-8-sig", newline="")))
    for role in role_rows:
        if role["role_name"] in known:
            continue
        rows.append({
            "source_standard_job": role["role_name"],
            "role_id": role["role_id"],
            "specialization": "",
            "requires_jd_validation": "false" if role["status"] == "active" else "true",
        })
    with (runtime_dir / "source_role_mapping.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_standard_job", "role_id", "specialization", "requires_jd_validation"])
        writer.writeheader()
        writer.writerows(rows)

    manifest = {
        "role_pool_version": version,
        "status": "prepared_not_default",
        "jobs_path": str((pool_dir / "canonical_jobs.jsonl").resolve()),
        "roles_path": str((runtime_dir / "canonical_roles.csv").resolve()),
        "role_data_dir": str(runtime_dir.resolve()),
        "jobs_sha256": sha256(pool_dir / "canonical_jobs.jsonl"),
        "roles_sha256": sha256(runtime_dir / "canonical_roles.csv"),
        "required_environment": {
            "JOB_HUNT_CANONICAL_ROLE_POOL_PATH": str((pool_dir / "canonical_jobs.jsonl").resolve()),
            "JOB_HUNT_CANONICAL_ROLE_DATA_DIR": str(runtime_dir.resolve()),
        },
        "compatibility": {
            "core_matching_algorithm_changed": False,
            "bm25_model_changed": False,
            "semantic_model_changed": False,
            "fusion_scoring_changed": False,
            "kg_schema_changed": False,
        },
    }
    (pool_dir / "runtime_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v2")
    parser.add_argument("--pool-dir", type=Path, default=V2)
    parser.add_argument("--runtime-dir", type=Path, default=ROOT / "backend-src" / "app" / "data" / "canonical_role_pool" / "v2")
    args = parser.parse_args()
    print(json.dumps(prepare(args.version, args.pool_dir, args.runtime_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
