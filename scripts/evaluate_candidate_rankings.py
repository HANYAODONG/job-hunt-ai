"""Evaluate JSON/JSONL candidate rankings against standard label JSONL files.

Workflow 1 scope:
- Accept downstream workflow outputs in either flat JSONL or batch JSON/JSONL form.
- Compute MRR, NDCG@k, and Recall@k.
- Keep this offline and deterministic.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


DEFAULT_LABELS = Path(__file__).resolve().parents[1] / "artifacts" / "dataset_iteration_05" / "label_pairs_gold.jsonl"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "artifacts" / "dataset_iteration_05" / "jsonl_eval_report.json"


def read_json_records(path: Path) -> Iterable[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    if path.suffix.lower() == ".json":
        payload = json.loads(text)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return [payload]
        raise ValueError(f"Unsupported JSON root in {path}: {type(payload).__name__}")

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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value == "" or value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value == "" or value is None:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def query_id_of(record: dict[str, Any]) -> str:
    return str(record.get("query_id") or record.get("candidate_id") or record.get("resume_id") or "")


def flatten_ranking_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for record in records:
        if "results" in record and isinstance(record["results"], list):
            query_id = query_id_of(record)
            for item in record["results"]:
                row = dict(item)
                if query_id and not query_id_of(row):
                    row["query_id"] = query_id
                flattened.append(row)
            continue
        if "candidates" in record and isinstance(record["candidates"], list):
            query_id = query_id_of(record)
            for item in record["candidates"]:
                row = dict(item)
                if query_id and not query_id_of(row):
                    row["query_id"] = query_id
                flattened.append(row)
            continue
        flattened.append(record)
    return flattened


def load_labels(path: Path) -> dict[tuple[str, str], int]:
    labels: dict[tuple[str, str], int] = {}
    for record in read_json_records(path):
        candidate_id = query_id_of(record)
        job_id = str(record.get("job_id") or "")
        if candidate_id and job_id:
            labels[(candidate_id, job_id)] = safe_int(record.get("grade"), 0)
    return labels


def load_ranking(path: Path, score_field: str, rank_field: str | None) -> dict[str, list[dict[str, Any]]]:
    records = flatten_ranking_records(read_json_records(path))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        query_id = query_id_of(record)
        job_id = str(record.get("job_id") or "")
        if not query_id or not job_id:
            continue
        item = dict(record)
        item["_score"] = safe_float(record.get(score_field), 0.0)
        item["_rank"] = safe_int(record.get(rank_field), 10**9) if rank_field else 10**9
        grouped[query_id].append(item)

    for items in grouped.values():
        if rank_field:
            items.sort(key=lambda item: (item["_rank"], -item["_score"]))
        else:
            items.sort(key=lambda item: item["_score"], reverse=True)
    return grouped


def dcg(grades: list[int], k: int) -> float:
    score = 0.0
    for index, grade in enumerate(grades[:k], start=1):
        score += ((2**grade) - 1) / math.log2(index + 1)
    return score


def ndcg(ranked_grades: list[int], ideal_grades: list[int], k: int) -> float:
    ideal_dcg = dcg(sorted(ideal_grades, reverse=True), k)
    if ideal_dcg == 0:
        return 0.0
    return dcg(ranked_grades, k) / ideal_dcg


def recall_at_k(
    ranked_grades: list[int],
    k: int,
    positive_grade: int,
    total_positive: int,
) -> float:
    if total_positive == 0:
        return 0.0
    hit_positive = sum(1 for grade in ranked_grades[:k] if grade >= positive_grade)
    return hit_positive / total_positive


def mrr(grades: list[int], positive_grade: int) -> float:
    for index, grade in enumerate(grades, start=1):
        if grade >= positive_grade:
            return 1.0 / index
    return 0.0


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def evaluate(
    ranking: dict[str, list[dict[str, Any]]],
    labels: dict[tuple[str, str], int],
    ks: list[int],
    positive_grade: int,
) -> dict[str, Any]:
    labels_by_query: dict[str, dict[str, int]] = defaultdict(dict)
    for (query_id, job_id), grade in labels.items():
        labels_by_query[query_id][job_id] = grade

    per_query: list[dict[str, Any]] = []
    for query_id, items in sorted(ranking.items()):
        query_labels = labels_by_query.get(query_id, {})
        if not query_labels:
            continue

        ranked_grades: list[int] = []
        labeled_candidates = 0
        for item in items:
            job_id = str(item.get("job_id") or "")
            if job_id in query_labels:
                labeled_candidates += 1
            ranked_grades.append(query_labels.get(job_id, 0))

        ideal_grades = list(query_labels.values())
        total_positive = sum(1 for grade in ideal_grades if grade >= positive_grade)
        row: dict[str, Any] = {
            "query_id": query_id,
            "labeled_candidates": labeled_candidates,
            "positive_candidates": total_positive,
            "mrr": mrr(ranked_grades, positive_grade),
        }
        for k in ks:
            row[f"ndcg@{k}"] = ndcg(ranked_grades, ideal_grades, k)
            row[f"recall@{k}"] = recall_at_k(
                ranked_grades,
                k,
                positive_grade,
                total_positive,
            )
        per_query.append(row)

    aggregate: dict[str, Any] = {
        "evaluated_queries": len(per_query),
        "positive_grade_threshold": positive_grade,
    }
    if per_query:
        metric_keys = [key for key in per_query[0] if key not in {"query_id", "labeled_candidates", "positive_candidates"}]
        for key in metric_keys:
            aggregate[key] = mean([float(row[key]) for row in per_query])
        aggregate["mean_labeled_candidates"] = mean([float(row["labeled_candidates"]) for row in per_query])
        aggregate["mean_positive_candidates"] = mean([float(row["positive_candidates"]) for row in per_query])

    return {"aggregate": aggregate, "per_query": per_query}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate JSON/JSONL candidate rankings against standard labels.")
    parser.add_argument("--ranking", type=Path, required=True, help="Ranking JSON/JSONL from any downstream workflow.")
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS, help="Standard label_pairs_*.jsonl file.")
    parser.add_argument("--score-field", default="final_score", help="Score field used for descending ranking.")
    parser.add_argument("--rank-field", default=None, help="Optional rank field. If provided, lower rank wins.")
    parser.add_argument("--positive-grade", type=int, default=2)
    parser.add_argument("--ks", default="5,10,20")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    ks = [int(item.strip()) for item in args.ks.split(",") if item.strip()]
    labels = load_labels(args.labels)
    ranking = load_ranking(args.ranking, args.score_field, args.rank_field)
    report = evaluate(ranking, labels, ks, args.positive_grade)
    report["inputs"] = {
        "ranking": str(args.ranking),
        "labels": str(args.labels),
        "score_field": args.score_field,
        "rank_field": args.rank_field,
    }
    report["workflow"] = "workflow_1_data_foundation_and_label_evaluation"
    report["notes"] = [
        "Ranking may be flat JSONL, batch JSON, or batch JSONL with results/candidates arrays.",
        "Metrics are computed only over ranking rows with matching labels.",
    ]

    write_json(args.output, report)
    print(json.dumps(report["aggregate"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
