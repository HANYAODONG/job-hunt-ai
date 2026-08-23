import argparse
import json
import sys
from pathlib import Path

from elasticsearch import Elasticsearch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.chinese_bm25_service import ChineseBM25Service  # noqa: E402


DEFAULT_INPUT = REPO_ROOT / "artifacts" / "dataset_iteration_05" / "jobs.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Index normalized Chinese jobs into Elasticsearch")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--url", default="http://127.0.0.1:9200")
    parser.add_argument("--index", default=ChineseBM25Service.DEFAULT_INDEX_NAME)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--mode",
        choices=("sample", "full"),
        default="full",
        help="sample limits the input for a smoke run; full indexes every job",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=1000,
        help="Number of jobs used when --mode sample is selected",
    )
    parser.add_argument("--recreate", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = args.input.resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if args.sample_size < 1:
        raise ValueError("--sample-size must be at least 1")

    client = Elasticsearch(args.url, request_timeout=120)
    if not client.ping():
        raise ConnectionError(f"Cannot connect to Elasticsearch: {args.url}")

    service = ChineseBM25Service(client, index_name=args.index)
    service.create_index(recreate=args.recreate)
    limit = args.sample_size if args.mode == "sample" else None
    result = service.bulk_index(input_path, batch_size=args.batch_size, limit=limit)
    result["mode"] = args.mode
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
