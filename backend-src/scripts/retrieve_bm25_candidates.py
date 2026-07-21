import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from elasticsearch import Elasticsearch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.chinese_bm25_service import ChineseBM25Service  # noqa: E402


DEFAULT_INPUT = REPO_ROOT / "artifacts" / "dataset_iteration_05" / "candidate_profiles.jsonl"
DEFAULT_OUTPUT = REPO_ROOT / "artifacts" / "bm25" / "bm25_top200.jsonl"


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc


def unique_terms(values: Iterable[Any]) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        key = item.casefold()
        if item and key not in seen:
            terms.append(item)
            seen.add(key)
    return terms


def build_query_text(profile: dict[str, Any], max_skills: int = 30) -> str:
    education = profile.get("education") if isinstance(profile.get("education"), dict) else {}
    target_family = str(profile.get("target_job_family") or "").strip()
    skills = profile.get("skills") if isinstance(profile.get("skills"), list) else []
    roles = [
        item.get("role", "")
        for item in profile.get("experience", [])
        if isinstance(item, dict)
    ]
    terms = unique_terms(
        [target_family]
        + skills[:max_skills]
        + roles
        + [education.get("major", "")]
    )
    years = profile.get("years_experience")
    if isinstance(years, int) and years > 0:
        terms.append(f"{years}年经验")
    return " ".join(terms)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieve BM25 TopK jobs for canonical candidate profiles")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--url", default="http://127.0.0.1:9200")
    parser.add_argument("--index", default=ChineseBM25Service.DEFAULT_INDEX_NAME)
    parser.add_argument("--size", type=int, default=200, choices=range(1, 201), metavar="1..200")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-skills", type=int, default=30)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = Elasticsearch(args.url, request_timeout=120)
    if not client.ping():
        raise ConnectionError(f"Cannot connect to Elasticsearch: {args.url}")

    service = ChineseBM25Service(client, index_name=args.index)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    query_count = 0
    candidate_count = 0
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for profile in read_jsonl(args.input):
            if args.limit is not None and query_count >= args.limit:
                break
            query_id = str(profile.get("candidate_id") or profile.get("resume_id") or "").strip()
            if not query_id:
                raise ValueError(f"Candidate profile #{query_count + 1} has no candidate_id")
            query_text = build_query_text(profile, max_skills=args.max_skills)
            result = service.search(query_text=query_text, size=args.size, source_type="enterprise")
            candidates = [
                {
                    "job_id": hit["job_id"],
                    "bm25_score": hit["score"],
                    "bm25_rank": hit["rank"],
                }
                for hit in result["hits"]
            ]
            record = {
                "query_id": query_id,
                "query_text": query_text,
                "took_ms": result["took_ms"],
                "candidates": candidates,
            }
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            query_count += 1
            candidate_count += len(candidates)

    print(
        json.dumps(
            {
                "index_name": args.index,
                "input": str(args.input),
                "output": str(args.output),
                "queries": query_count,
                "candidates": candidate_count,
                "top_k": args.size,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
