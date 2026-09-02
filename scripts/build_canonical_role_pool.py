"""Build the v1 graph and matching job pool from enterprise source snapshots."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend-src"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.canonical_role_pool import CanonicalRolePool  # noqa: E402


DEFAULT_INPUT = REPO_ROOT / "artifacts" / "dataset_iteration_05" / "jobs_enterprise.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "canonical_role_pool_v1"


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Expected object at {path}:{line_number}")
            yield value


def split_items(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        raw_values = value
    else:
        raw_values = str(value).replace("；", ";").replace("，", ",").replace("、", ",").split(";")
    values: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        for part in str(raw_value).replace("\n", ",").split(","):
            text = part.strip()
            key = text.casefold()
            if text and key not in seen:
                values.append(text)
                seen.add(key)
    return values


def adapt_enterprise_csv(path: Path) -> Iterable[dict[str, Any]]:
    """Read the data group's raw enterprise snapshot without the mixed-pool adapter."""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            skills = split_items(row.get("skills"))
            for field in ("traditional_skills", "new_skills"):
                for skill in split_items(row.get(field)):
                    if skill.casefold() not in {item.casefold() for item in skills}:
                        skills.append(skill)
            description = "\n".join(
                str(row.get(field) or "").strip()
                for field in ("job_responsibility", "job_requirement", "detailed", "domain_context")
                if str(row.get(field) or "").strip()
            )
            yield {
                "job_id": str(row.get("job_id") or "").strip(),
                "id": str(row.get("job_id") or "").strip(),
                "title": str(row.get("job_title") or "").strip(),
                "description": description,
                "skills": skills,
                "required_skills": skills,
                "standard_job": str(row.get("standard_job") or "").strip(),
                "job_family": str(row.get("standard_job") or "").strip(),
                "source": "data_group_job_bigcompany_final",
                "source_type": "enterprise",
                "publish_time": str(row.get("publish_time") or "").strip(),
                "domain_context": str(row.get("domain_context") or "").strip(),
                "traditional_skills": split_items(row.get("traditional_skills")),
                "new_skills": split_items(row.get("new_skills")),
                "source_snapshot": {
                    "source_file": path.name,
                    "source_standard_job": str(row.get("standard_job") or "").strip(),
                },
            }


def read_records(path: Path) -> Iterable[dict[str, Any]]:
    if path.suffix.casefold() == ".csv":
        return adapt_enterprise_csv(path)
    return read_jsonl(path)


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def build(input_path: Path, output_dir: Path) -> dict[str, Any]:
    pool = CanonicalRolePool()
    source_rows = list(read_records(input_path))
    invalid_sources = sorted({str(row.get("source_type") or "") for row in source_rows} - {"enterprise"})
    if invalid_sources:
        raise ValueError(f"Canonical enterprise role pool only accepts enterprise records: {invalid_sources}")

    accepted: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    for row in source_rows:
        enriched = pool.enrich(row)
        if enriched["role_mapping_status"] == "mapped":
            accepted.append(enriched)
        else:
            review.append(enriched)

    source_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()
    catalog_statuses = Counter(role.status for role in pool.roles.values())
    observed_role_ids = {row["canonical_role_id"] for row in accepted}
    report = {
        "version": "canonical_role_pool_v1",
        "input": str(input_path),
        "input_sha256": source_hash,
        "source_records": len(source_rows),
        "accepted_records": len(accepted),
        "review_records": len(review),
        "review_rate": round(len(review) / len(source_rows), 6) if source_rows else 0.0,
        "domains": dict(sorted(Counter(row["canonical_domain"] for row in accepted).items())),
        "directions": dict(sorted(Counter(row["canonical_direction"] for row in accepted).items())),
        "canonical_roles": dict(sorted(Counter(row["canonical_role"] for row in accepted).items())),
        "role_catalog": {
            "scope": "source-bounded_core_not_complete_market_catalog",
            "defined_role_identities": len(pool.roles),
            "defined_by_status": dict(sorted(catalog_statuses.items())),
            "observed_active_role_identities": len(observed_role_ids),
            "unobserved_active_role_ids": sorted(
                role_id
                for role_id, role in pool.roles.items()
                if role.status == "active" and role_id not in observed_role_ids
            ),
        },
        "review_reasons": dict(sorted(
            Counter(reason for row in review for reason in row["role_mapping_review_reasons"]).items()
        )),
        "quality_gate": {
            "rule": "Only records with role_mapping_status=mapped may be used by graph or matching.",
            "source_scope": "enterprise only; government and legacy records require independent source-domain mappings.",
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    report["outputs"] = {
        "canonical_jobs": str(output_dir / "canonical_jobs.jsonl"),
        "review_queue": str(output_dir / "role_mapping_review.jsonl"),
        "report": str(output_dir / "role_pool_report.json"),
    }
    write_jsonl(output_dir / "canonical_jobs.jsonl", accepted)
    write_jsonl(output_dir / "role_mapping_review.jsonl", review)
    (output_dir / "role_pool_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a review-gated canonical enterprise role pool.")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Enterprise JSONL snapshot or the data group's job_bigcompany_final.csv.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    print(json.dumps(build(args.input, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
