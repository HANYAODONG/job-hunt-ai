"""Reapply the current canonical rules to the stored data-group snapshot.

The original CSV is tracked by the data group. This utility reconstructs its
source-label view from the checked-in derived artifacts, preserving the source
label stored on every JD, so a taxonomy-only change can be applied without
silently substituting the legacy mixed pool.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend-src"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.canonical_role_pool import CanonicalRolePool  # noqa: E402


DEFAULT_DIR = REPO_ROOT / "artifacts" / "canonical_role_pool_v1" / "data_group_current"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def build(pool_dir: Path) -> dict[str, Any]:
    canonical_path = pool_dir / "canonical_jobs.jsonl"
    review_path = pool_dir / "role_mapping_review.jsonl"
    report_path = pool_dir / "role_pool_report.json"
    original = read_jsonl(canonical_path) + read_jsonl(review_path)
    if len({str(row.get("job_id") or "") for row in original}) != len(original):
        raise ValueError("Snapshot contains duplicate or blank job IDs")

    pool = CanonicalRolePool()
    accepted: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    for row in original:
        source_label = str(row.get("source_standard_job") or "").strip()
        if not source_label:
            raise ValueError(f"JD has no source standard job: {row.get('job_id')}")
        source_row = dict(row)
        source_row["standard_job"] = source_label
        source_row["job_family"] = source_label
        enriched = pool.enrich(source_row)
        (accepted if enriched["role_mapping_status"] == "mapped" else review).append(enriched)

    previous = json.loads(report_path.read_text(encoding="utf-8"))
    catalog_statuses = Counter(role.status for role in pool.roles.values())
    report = {
        **previous,
        "accepted_records": len(accepted),
        "review_records": len(review),
        "review_rate": round(len(review) / len(original), 6),
        "domains": dict(sorted(Counter(row["canonical_domain"] for row in accepted).items())),
        "directions": dict(sorted(Counter(row["canonical_direction"] for row in accepted).items())),
        "canonical_roles": dict(sorted(Counter(row["canonical_role"] for row in accepted).items())),
        "role_catalog": {
            "scope": "source-bounded_core_not_complete_market_catalog",
            "defined_role_identities": len(pool.roles),
            "defined_by_status": dict(sorted(catalog_statuses.items())),
            "observed_active_role_identities": len({row["canonical_role_id"] for row in accepted}),
            "unobserved_active_role_ids": sorted(
                role_id for role_id, role in pool.roles.items()
                if role.status == "active" and all(row["canonical_role_id"] != role_id for row in accepted)
            ),
        },
        "review_reasons": dict(sorted(Counter(
            reason for row in review for reason in row["role_mapping_review_reasons"]
        ).items())),
        "refreshed_from": "stored_data_group_snapshot_with_preserved_source_standard_job",
    }
    write_jsonl(canonical_path, accepted)
    write_jsonl(review_path, review)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh canonical artifacts from their stored source snapshot.")
    parser.add_argument("--pool-dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()
    print(json.dumps(build(args.pool_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
