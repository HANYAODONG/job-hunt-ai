"""Run Workflow 5 end to end and write a reproducible execution report."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from elasticsearch import Elasticsearch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_DIR = REPO_ROOT / "dataset" / "incoming"
DEFAULT_DATASET_OUTPUT = REPO_ROOT / "artifacts" / "dataset_iteration_05"
DEFAULT_BM25_OUTPUT = REPO_ROOT / "artifacts" / "bm25" / "bm25_top200.jsonl"
DEFAULT_REPORT = REPO_ROOT / "artifacts" / "bm25" / "workflow5_run_report.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def run_command(name: str, command: list[str], cwd: Path) -> dict[str, Any]:
    started = time.perf_counter()
    print(f"\n[workflow5] {name}")
    print(" ".join(command))
    completed = subprocess.run(command, cwd=cwd, check=False)
    duration = round(time.perf_counter() - started, 3)
    stage = {
        "name": name,
        "command": command,
        "return_code": completed.returncode,
        "duration_seconds": duration,
        "status": "completed" if completed.returncode == 0 else "failed",
    }
    if completed.returncode != 0:
        raise RuntimeError(f"Stage {name!r} failed with code {completed.returncode}")
    return stage


def wait_for_elasticsearch(url: str, timeout_seconds: int = 120) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    client = Elasticsearch(url, request_timeout=10)
    while time.monotonic() < deadline:
        try:
            if client.ping():
                info = client.info()
                return {
                    "url": url,
                    "version": info["version"]["number"],
                    "cluster_name": info.get("cluster_name"),
                }
        except Exception:
            pass
        time.sleep(2)
    raise ConnectionError(
        f"Elasticsearch did not become available at {url} "
        f"within {timeout_seconds} seconds"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Workflow 5 BM25 pipeline")
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--dataset-output", type=Path, default=DEFAULT_DATASET_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_BM25_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--url", default="http://127.0.0.1:9200")
    parser.add_argument("--index", default="bigcompany_jobs_v1")
    parser.add_argument("--top-k", type=int, default=200, choices=range(1, 201))
    parser.add_argument("--limit", type=int, default=0, help="0 processes all profiles")
    parser.add_argument("--max-skills", type=int, default=30)
    parser.add_argument("--source-type", default="enterprise")
    parser.add_argument("--start-elasticsearch", action="store_true")
    parser.add_argument("--skip-adapter", action="store_true")
    parser.add_argument("--skip-index", action="store_true")
    parser.add_argument("--no-recreate", action="store_true")
    parser.add_argument(
        "--require-labels",
        action="store_true",
        help="Fail instead of completing without a formal baseline report.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report_path = args.report.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "workflow": "workflow_5_bm25_recall",
        "status": "running",
        "started_at": utc_now(),
        "stages": [],
        "configuration": {
            "dataset_dir": str(args.dataset_dir.resolve()),
            "dataset_output": str(args.dataset_output.resolve()),
            "output": str(args.output.resolve()),
            "elasticsearch_url": args.url,
            "index": args.index,
            "top_k": args.top_k,
            "limit": args.limit,
            "source_type": args.source_type,
        },
    }

    try:
        if args.start_elasticsearch:
            report["stages"].append(
                run_command(
                    "start_elasticsearch",
                    ["docker", "compose", "up", "-d", "elasticsearch"],
                    REPO_ROOT,
                )
            )
        report["elasticsearch"] = wait_for_elasticsearch(args.url)

        dataset_output = args.dataset_output.resolve()
        if not args.skip_adapter:
            adapter_command = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "dataset_adapter.py"),
                "--dataset-dir",
                str(args.dataset_dir.resolve()),
                "--output-dir",
                str(dataset_output),
            ]
            if not args.require_labels:
                adapter_command.append("--allow-missing-labels")
            report["stages"].append(
                run_command(
                    "adapt_dataset",
                    adapter_command,
                    REPO_ROOT,
                )
            )

        jobs_path = dataset_output / "jobs.jsonl"
        profiles_path = dataset_output / "candidate_profiles.jsonl"
        labels_path = dataset_output / "label_pairs_gold.jsonl"
        for required_path in (jobs_path, profiles_path):
            if not required_path.exists():
                raise FileNotFoundError(f"Required workflow input missing: {required_path}")

        if not args.skip_index:
            index_command = [
                sys.executable,
                str(BACKEND_ROOT / "scripts" / "index_chinese_jobs.py"),
                "--input",
                str(jobs_path),
                "--url",
                args.url,
                "--index",
                args.index,
            ]
            if not args.no_recreate:
                index_command.append("--recreate")
            report["stages"].append(
                run_command("index_jobs", index_command, REPO_ROOT)
            )

        output_path = args.output.resolve()
        retrieve_command = [
            sys.executable,
            str(BACKEND_ROOT / "scripts" / "retrieve_bm25_candidates.py"),
            "--input",
            str(profiles_path),
            "--output",
            str(output_path),
            "--url",
            args.url,
            "--index",
            args.index,
            "--size",
            str(args.top_k),
            "--max-skills",
            str(args.max_skills),
            "--source-type",
            args.source_type,
        ]
        if args.limit > 0:
            retrieve_command.extend(["--limit", str(args.limit)])
        report["stages"].append(
            run_command("retrieve_candidates", retrieve_command, REPO_ROOT)
        )

        label_count = count_jsonl(labels_path)
        evaluation_path = output_path.parent / "bm25_baseline_eval_report.json"
        if label_count:
            report["stages"].append(
                run_command(
                    "evaluate_baseline",
                    [
                        sys.executable,
                        str(
                            REPO_ROOT
                            / "scripts"
                            / "evaluate_candidate_rankings.py"
                        ),
                        "--ranking",
                        str(output_path),
                        "--labels",
                        str(labels_path),
                        "--score-field",
                        "bm25_score",
                        "--rank-field",
                        "bm25_rank",
                        "--positive-grade",
                        "2",
                        "--ks",
                        "10,100,200",
                        "--output",
                        str(evaluation_path),
                    ],
                    REPO_ROOT,
                )
            )
            report["evaluation"] = {
                "status": "completed",
                "label_count": label_count,
                "report": str(evaluation_path),
                "metrics": json.loads(evaluation_path.read_text(encoding="utf-8"))[
                    "aggregate"
                ],
            }
            report["status"] = "completed"
        else:
            report["evaluation"] = {
                "status": "blocked_missing_gold_labels",
                "label_count": 0,
                "labels_path": str(labels_path),
                "message": (
                    "Retrieval is complete, but formal Recall/MRR/NDCG requires "
                    "Workflow 1 gold labels."
                ),
            }
            if args.require_labels:
                raise RuntimeError(
                    f"Gold labels are required but empty or missing: {labels_path}"
                )
            report["status"] = "completed_without_formal_evaluation"

        report["outputs"] = {
            "jobs": count_jsonl(jobs_path),
            "profiles": count_jsonl(profiles_path),
            "ranking_queries": count_jsonl(output_path),
            "ranking_path": str(output_path),
            "index_document_count": Elasticsearch(
                args.url, request_timeout=30
            ).count(index=args.index)["count"],
        }
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        report["finished_at"] = utc_now()
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n[workflow5] report: {report_path}")
        print(json.dumps({"status": report["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
