import argparse
import json
import sys
from pathlib import Path

from elasticsearch import Elasticsearch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.chinese_bm25_service import ChineseBM25Service  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search Chinese jobs with weighted BM25")
    parser.add_argument("query", help="岗位关键词或简历文本")
    parser.add_argument("--url", default="http://127.0.0.1:9200")
    parser.add_argument("--index", default=ChineseBM25Service.DEFAULT_INDEX_NAME)
    parser.add_argument("--size", type=int, default=20)
    parser.add_argument("--source-type", choices=["enterprise", "government"])
    parser.add_argument("--location")
    parser.add_argument("--include-duplicates", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = Elasticsearch(args.url, request_timeout=120)
    service = ChineseBM25Service(client, index_name=args.index)
    result = service.search(
        query_text=args.query,
        size=args.size,
        source_type=args.source_type,
        location=args.location,
        exclude_duplicates=not args.include_duplicates,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
