"""Evaluate the real PDF pack through the public resume-upload HTTP API."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import requests

from canonical_job_title import canonical_job_title


ROOT = Path(__file__).resolve().parents[1]


def read_jobs(path: Path) -> dict[str, dict[str, Any]]:
    jobs: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            job_id = str(row.get("job_id") or row.get("id") or "")
            if job_id:
                jobs[job_id] = row
    return jobs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18089")
    parser.add_argument(
        "--pack",
        type=Path,
        default=ROOT / "artifacts" / "real_upload_matching_pack_v6_100",
    )
    parser.add_argument(
        "--jobs",
        type=Path,
        default=ROOT / "artifacts" / "canonical_role_pool_v2" / "canonical_jobs.jsonl",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "artifacts" / "real_upload_matching_api_eval_v1_100",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--parser-mode",
        choices=("auto", "local", "llm"),
        default="auto",
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((args.pack / "manifest.json").read_text(encoding="utf-8"))
    items = manifest["items"][: args.limit] if args.limit is not None else manifest["items"]
    jobs = read_jobs(args.jobs)
    endpoint = f"{args.base_url.rstrip('/')}/api/v1/jobs/search-with-resume"
    rows: list[dict[str, Any]] = []

    run_start = time.perf_counter()
    for item in items:
        pdf_path = args.pack / item["pdf"]
        started = time.perf_counter()
        row: dict[str, Any] = {
            "sample_id": item["sample_id"],
            "candidate_id": item["candidate_id"],
            "gold_role": item["gold_role"],
            "accepted_jd_ids": item.get("accepted_jd_ids") or [],
        }
        try:
            with pdf_path.open("rb") as handle:
                response = requests.post(
                    endpoint,
                    files={"resume_file": (pdf_path.name, handle, "application/pdf")},
                    data={
                        "query": "",
                        "limit": "3",
                        "parser_mode": args.parser_mode,
                        "pipeline_mode": "lightweight",
                    },
                    timeout=args.timeout,
                )
            row["http_status"] = response.status_code
            response.raise_for_status()
            payload = response.json()
            explanations = payload.get("explanations") or {}
            returned_jobs = payload.get("jobs") or []
            top_ids = [str(job.get("id") or job.get("job_id") or "") for job in returned_jobs[:3]]
            accepted = set(row["accepted_jd_ids"])
            accepted_titles = {
                canonical_job_title(jobs[job_id]) for job_id in accepted if job_id in jobs
            }
            top_titles = [canonical_job_title(jobs.get(job_id, {})) for job_id in top_ids]
            row.update(
                {
                    "predicted_role": explanations.get("selected_canonical_role_id"),
                    "runtime_pipeline_mode": explanations.get("runtime_pipeline_mode"),
                    "matching_pipeline": explanations.get("matching_pipeline"),
                    "external_services_used": explanations.get("external_services_used"),
                    "top_job_ids": top_ids,
                    "role_hit": explanations.get("selected_canonical_role_id") == item["gold_role"],
                    "jd_hit_at_1": any(job_id in accepted for job_id in top_ids[:1]),
                    "jd_hit_at_2": any(job_id in accepted for job_id in top_ids[:2]),
                    "jd_hit_at_3": any(job_id in accepted for job_id in top_ids[:3]),
                    "title_hit_at_1": any(title in accepted_titles for title in top_titles[:1]),
                    "title_hit_at_2": any(title in accepted_titles for title in top_titles[:2]),
                    "title_hit_at_3": any(title in accepted_titles for title in top_titles[:3]),
                    "error": "",
                }
            )
        except Exception as exc:  # Keep the full batch auditable after one failed upload.
            row.update(
                {
                    "role_hit": False,
                    "jd_hit_at_1": False,
                    "jd_hit_at_2": False,
                    "jd_hit_at_3": False,
                    "title_hit_at_1": False,
                    "title_hit_at_2": False,
                    "title_hit_at_3": False,
                    "error": str(exc),
                }
            )
        row["total_ms"] = round((time.perf_counter() - started) * 1000, 2)
        rows.append(row)

    successful = [row for row in rows if not row.get("error")]
    n = len(rows)
    denom = max(1, n)
    report = {
        "status": "completed" if len(successful) == n else "completed_with_errors",
        "mode": "real_pdf_http_upload_canonical_two_stage",
        "parser_mode": args.parser_mode,
        "endpoint": endpoint,
        "samples": n,
        "successful_requests": len(successful),
        "failed_requests": n - len(successful),
        "role_top1_accuracy": sum(bool(row["role_hit"]) for row in rows) / denom,
        "jd_top1_recall": sum(bool(row["jd_hit_at_1"]) for row in rows) / denom,
        "jd_top2_recall": sum(bool(row["jd_hit_at_2"]) for row in rows) / denom,
        "jd_top3_recall": sum(bool(row["jd_hit_at_3"]) for row in rows) / denom,
        "normalized_title_top1_recall": sum(bool(row["title_hit_at_1"]) for row in rows) / denom,
        "normalized_title_top2_recall": sum(bool(row["title_hit_at_2"]) for row in rows) / denom,
        "normalized_title_top3_recall": sum(bool(row["title_hit_at_3"]) for row in rows) / denom,
        "pipeline_marker_failures": sum(
            row.get("runtime_pipeline_mode") != "lightweight"
            or row.get("matching_pipeline") != "canonical_two_stage_v2"
            or row.get("external_services_used") is not False
            for row in successful
        ),
        "wall_clock_ms": round((time.perf_counter() - run_start) * 1000, 2),
        "average_request_ms": round(sum(row["total_ms"] for row in rows) / denom, 2),
        "metric_note": "All accuracy denominators include failed HTTP requests. Gold fields are read only after each API response.",
    }
    (args.out / "case_metrics.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    (args.out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
