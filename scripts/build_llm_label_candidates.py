"""Build LLM labeling candidate pairs for workflow 1.

This script keeps workflow 1 offline and deterministic:
- read normalized jobs and candidate profiles
- retrieve candidate jobs with a lightweight BM25 implementation
- sample top, middle, and random cross-family jobs for LLM labeling
- write JSONL batches that can be sent to an LLM or human reviewer

It does not call any model API and does not train models.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "artifacts"
DEFAULT_ITERATION_DIR = DEFAULT_ARTIFACT_ROOT / "dataset_iteration_05"
DEFAULT_OUTPUT = DEFAULT_ITERATION_DIR / "llm_label_candidates.jsonl"
DEFAULT_REPORT = DEFAULT_ITERATION_DIR / "llm_label_candidate_report.json"


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9+#.]+|[\u4e00-\u9fff]")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
    return records


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
            count += 1
    return count


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def tokenize(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_PATTERN.findall(text or "") if token.strip()]


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(as_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(as_text(item) for item in value.values())
    return str(value)


def job_id_of(job: dict[str, Any]) -> str:
    return str(job.get("job_id") or job.get("id") or "")


def candidate_id_of(candidate: dict[str, Any]) -> str:
    return str(candidate.get("candidate_id") or candidate.get("resume_id") or candidate.get("query_id") or "")


def job_family_of(record: dict[str, Any]) -> str:
    return str(record.get("job_family") or record.get("standard_category") or record.get("target_job_family") or "")


def build_job_text(job: dict[str, Any]) -> str:
    fields = [
        job.get("title"),
        job.get("standard_job"),
        job.get("job_family"),
        job.get("description"),
        job.get("responsibilities"),
        job.get("requirements"),
        job.get("detailed"),
        job.get("skills"),
        job.get("required_skills"),
        job.get("traditional_skills"),
        job.get("new_skills"),
        job.get("domain_context"),
        job.get("company"),
        job.get("location"),
    ]
    return " ".join(as_text(field) for field in fields if field)


def build_candidate_text(candidate: dict[str, Any]) -> str:
    fields = [
        candidate.get("summary"),
        candidate.get("target_job_family"),
        candidate.get("preferred_location"),
        candidate.get("skills"),
        candidate.get("experience"),
        candidate.get("projects"),
        candidate.get("education"),
    ]
    return " ".join(as_text(field) for field in fields if field)


class BM25Index:
    def __init__(self, jobs: list[dict[str, Any]], k1: float = 1.5, b: float = 0.75) -> None:
        self.jobs = jobs
        self.k1 = k1
        self.b = b
        self.doc_tokens: list[list[str]] = []
        self.doc_term_counts: list[Counter[str]] = []
        self.doc_lengths: list[int] = []
        self.document_frequency: Counter[str] = Counter()

        for job in jobs:
            tokens = tokenize(build_job_text(job))
            counts = Counter(tokens)
            self.doc_tokens.append(tokens)
            self.doc_term_counts.append(counts)
            self.doc_lengths.append(len(tokens))
            self.document_frequency.update(counts.keys())

        self.avg_doc_length = sum(self.doc_lengths) / max(1, len(self.doc_lengths))

    def idf(self, term: str) -> float:
        n_docs = len(self.jobs)
        df = self.document_frequency.get(term, 0)
        return math.log(1 + (n_docs - df + 0.5) / (df + 0.5))

    def search(self, query_text: str, limit: int | None = None) -> list[dict[str, Any]]:
        query_terms = Counter(tokenize(query_text))
        scored: list[dict[str, Any]] = []
        for index, job in enumerate(self.jobs):
            doc_len = self.doc_lengths[index] or 1
            counts = self.doc_term_counts[index]
            score = 0.0
            for term, qf in query_terms.items():
                tf = counts.get(term, 0)
                if tf <= 0:
                    continue
                denom = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self.avg_doc_length, 1e-9))
                score += self.idf(term) * (tf * (self.k1 + 1) / denom) * qf
            if score > 0:
                scored.append(
                    {
                        "job": job,
                        "job_id": job_id_of(job),
                        "bm25_score": round(score, 6),
                    }
                )
        scored.sort(key=lambda item: item["bm25_score"], reverse=True)
        for rank, item in enumerate(scored, start=1):
            item["bm25_rank"] = rank
        return scored[:limit] if limit else scored


def compact_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": job_id_of(job),
        "title": job.get("title") or job.get("standard_job") or "",
        "company": job.get("company") or job.get("company_name") or "",
        "job_family": job_family_of(job),
        "skills": job.get("skills") or job.get("required_skills") or [],
        "description_preview": as_text(job.get("description") or job.get("requirements") or "")[:500],
    }


def select_candidates_for_profile(
    candidate: dict[str, Any],
    ranked_jobs: list[dict[str, Any]],
    all_jobs: list[dict[str, Any]],
    *,
    top_n: int,
    middle_n: int,
    random_n: int,
    middle_start: int,
    middle_end: int,
    rng: random.Random,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_job_ids: set[str] = set()

    def append_item(item: dict[str, Any], bucket: str) -> None:
        job_id = item["job_id"]
        if not job_id or job_id in seen_job_ids:
            return
        seen_job_ids.add(job_id)
        job = item["job"]
        selected.append(
            {
                "job_id": job_id,
                "selection_bucket": bucket,
                "bm25_score": item.get("bm25_score", 0.0),
                "bm25_rank": item.get("bm25_rank"),
                "job_family": job_family_of(job),
                "job_snapshot": compact_job(job),
            }
        )

    for item in ranked_jobs[:top_n]:
        append_item(item, "bm25_top")

    middle_pool = ranked_jobs[max(0, middle_start - 1) : max(middle_start - 1, middle_end)]
    for item in middle_pool[:middle_n]:
        append_item(item, "bm25_middle")

    candidate_family = job_family_of(candidate)
    job_lookup = {job_id_of(job): job for job in all_jobs}
    ranked_ids = {item["job_id"] for item in ranked_jobs}
    random_pool = [
        job
        for job in all_jobs
        if job_id_of(job)
        and job_id_of(job) not in ranked_ids
        and (not candidate_family or job_family_of(job) != candidate_family)
    ]
    if len(random_pool) < random_n:
        random_pool = [job for job in all_jobs if job_id_of(job) and job_id_of(job) not in seen_job_ids]
    rng.shuffle(random_pool)
    for job in random_pool[:random_n]:
        item = {
            "job": job,
            "job_id": job_id_of(job),
            "bm25_score": 0.0,
            "bm25_rank": None,
        }
        append_item(item, "cross_family_random")

    # If retrieval is sparse, backfill from ranked jobs first, then any remaining job.
    if len(selected) < top_n + middle_n + random_n:
        for item in ranked_jobs:
            append_item(item, "backfill_ranked")
            if len(selected) >= top_n + middle_n + random_n:
                break
    if len(selected) < top_n + middle_n + random_n:
        for job_id, job in job_lookup.items():
            if job_id in seen_job_ids:
                continue
            append_item({"job": job, "job_id": job_id, "bm25_score": 0.0, "bm25_rank": None}, "backfill_any")
            if len(selected) >= top_n + middle_n + random_n:
                break

    return selected


def build_batches(
    candidates: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    *,
    top_n: int,
    middle_n: int,
    random_n: int,
    middle_start: int,
    middle_end: int,
    seed: int,
    max_profiles: int | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rng = random.Random(seed)
    bm25 = BM25Index(jobs)
    selected_profiles = candidates[:max_profiles] if max_profiles else candidates
    batches: list[dict[str, Any]] = []
    bucket_counts: Counter[str] = Counter()
    candidate_counts: list[int] = []

    for candidate in selected_profiles:
        candidate_id = candidate_id_of(candidate)
        if not candidate_id:
            continue
        query_text = build_candidate_text(candidate)
        ranked_jobs = bm25.search(query_text)
        selected = select_candidates_for_profile(
            candidate,
            ranked_jobs,
            jobs,
            top_n=top_n,
            middle_n=middle_n,
            random_n=random_n,
            middle_start=middle_start,
            middle_end=middle_end,
            rng=rng,
        )
        bucket_counts.update(item["selection_bucket"] for item in selected)
        candidate_counts.append(len(selected))
        batches.append(
            {
                "query_id": candidate_id,
                "candidate_id": candidate_id,
                "candidate_snapshot": {
                    "summary": as_text(candidate.get("summary"))[:800],
                    "skills": candidate.get("skills") or [],
                    "target_job_family": candidate.get("target_job_family") or "",
                    "preferred_location": candidate.get("preferred_location") or "",
                },
                "query_text": query_text,
                "candidates": selected,
                "labeling_instruction": "Use docs/llm-labeling-guidelines.md to assign grade 0-3 and evidence fields.",
            }
        )

    report = {
        "profiles_total": len(candidates),
        "profiles_selected": len(batches),
        "jobs_total": len(jobs),
        "target_pairs_per_profile": top_n + middle_n + random_n,
        "actual_pairs_total": sum(candidate_counts),
        "actual_pairs_min": min(candidate_counts) if candidate_counts else 0,
        "actual_pairs_max": max(candidate_counts) if candidate_counts else 0,
        "bucket_counts": dict(bucket_counts),
        "seed": seed,
        "notes": [
            "This file is an LLM labeling candidate pool, not gold labels.",
            "Gold labels require manual review before formal evaluation.",
        ],
    }
    return batches, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build BM25-based LLM labeling candidates for workflow 1.")
    parser.add_argument("--jobs", type=Path, default=DEFAULT_ITERATION_DIR / "jobs.jsonl")
    parser.add_argument("--candidates", type=Path, default=DEFAULT_ITERATION_DIR / "candidate_profiles.jsonl")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--top-n", type=int, default=8)
    parser.add_argument("--middle-n", type=int, default=8)
    parser.add_argument("--random-n", type=int, default=4)
    parser.add_argument("--middle-start", type=int, default=50)
    parser.add_argument("--middle-end", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260722)
    parser.add_argument("--max-profiles", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.jobs.exists():
        raise FileNotFoundError(f"Missing jobs file: {args.jobs}")
    if not args.candidates.exists():
        raise FileNotFoundError(f"Missing candidate profiles file: {args.candidates}")

    jobs = read_jsonl(args.jobs)
    candidates = read_jsonl(args.candidates)
    batches, report = build_batches(
        candidates,
        jobs,
        top_n=args.top_n,
        middle_n=args.middle_n,
        random_n=args.random_n,
        middle_start=args.middle_start,
        middle_end=args.middle_end,
        seed=args.seed,
        max_profiles=args.max_profiles,
    )
    write_jsonl(args.output, batches)
    write_json(args.report, report)

    print(f"Wrote LLM candidate batches: {args.output}")
    print(f"Wrote candidate report: {args.report}")
    print(f"Profiles: {report['profiles_selected']} | Pairs: {report['actual_pairs_total']}")


if __name__ == "__main__":
    main()
