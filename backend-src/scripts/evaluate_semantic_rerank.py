"""
工作流 2 — 语义重排评测脚本

支持：
    1. 单模型评测：计算 Recall@K、MRR、NDCG@K
    2. 多模型对比：BM25 vs BM25+text2vec vs BM25+BGE-M3
    3. 资源占用报告：模型大小、编码耗时、峰值内存

用法：
    # 单模型评测（text2vec）
    python backend-src/scripts/evaluate_semantic_rerank.py \
        --ranking artifacts/semantic_text2vec/semantic_rerank_top200.jsonl \
        --labels artifacts/dataset_iteration_05/label_pairs_gold.jsonl \
        --score-field semantic_score --rank-field semantic_rank

    # 三模型对比
    python backend-src/scripts/evaluate_semantic_rerank.py --compare-all

    # 自定义对比
    python backend-src/scripts/evaluate_semantic_rerank.py \
        --compare \
        --rankings \
            artifacts/bm25/bm25_top200.jsonl:bm25_score:bm25_rank:BM25 \
            artifacts/semantic_text2vec/semantic_rerank_top200.jsonl:semantic_score:semantic_rank:text2vec \
            artifacts/semantic_bge/semantic_rerank_top200.jsonl:semantic_score:semantic_rank:BGE-M3
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

_SCRIPT_DIR = Path(__file__).resolve()
_BACKEND_ROOT = _SCRIPT_DIR.parents[1]
_REPO_ROOT = _BACKEND_ROOT.parent
if not (_REPO_ROOT / "artifacts").exists() and (_BACKEND_ROOT / "artifacts").exists():
    _REPO_ROOT = _BACKEND_ROOT
REPO_ROOT = _REPO_ROOT

DEFAULT_LABELS = REPO_ROOT / "artifacts" / "dataset_iteration_05" / "label_pairs_gold.jsonl"
DEFAULT_BM25 = REPO_ROOT / "artifacts" / "bm25" / "bm25_top200.jsonl"
DEFAULT_TEXT2VEC = REPO_ROOT / "artifacts" / "semantic_text2vec" / "semantic_rerank_top200.jsonl"
DEFAULT_BGE = REPO_ROOT / "artifacts" / "semantic_bge" / "semantic_rerank_top200.jsonl"
DEFAULT_OUT = REPO_ROOT / "artifacts" / "semantic_text2vec" / "eval_report.json"


# ══════════════════════════════════════════════════════════════════
# 数据加载
# ══════════════════════════════════════════════════════════════════

def read_json_records(path: Path) -> Iterable[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    if path.suffix.lower() == ".json":
        payload = json.loads(text)
        if isinstance(payload, list):
            yield from payload
            return
        if isinstance(payload, dict):
            yield payload
            return
        raise ValueError(f"不支持的 JSON 根类型: {type(payload).__name__}")

    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno}: {exc}") from exc


def write_json(path: Path, payload: Any) -> None:
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


def query_id_of(record: Dict[str, Any]) -> str:
    return str(
        record.get("query_id")
        or record.get("candidate_id")
        or record.get("resume_id")
        or ""
    )


# ══════════════════════════════════════════════════════════════════
# 排名解析
# ══════════════════════════════════════════════════════════════════

def flatten_ranking(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """将嵌套的 candidates/results 数组展平为单行。"""
    flattened: List[Dict[str, Any]] = []
    for rec in records:
        for key in ("candidates", "results"):
            if key in rec and isinstance(rec[key], list):
                qid = query_id_of(rec)
                for item in rec[key]:
                    row = dict(item)
                    if qid and not query_id_of(row):
                        row["query_id"] = qid
                    flattened.append(row)
                break
        else:
            flattened.append(rec)
    return flattened


def load_ranking(
    path: Path,
    score_field: str,
    rank_field: Optional[str],
) -> Dict[str, List[Dict[str, Any]]]:
    """按 query_id 分组并排序。"""
    records = flatten_ranking(read_json_records(path))
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for rec in records:
        qid = query_id_of(rec)
        jid = str(rec.get("job_id") or "")
        if not qid or not jid:
            continue
        item = dict(rec)
        item["_score"] = safe_float(rec.get(score_field), 0.0)
        item["_rank"] = safe_int(rec.get(rank_field), 10**9) if rank_field else 10**9
        grouped[qid].append(item)

    for items in grouped.values():
        if rank_field:
            items.sort(key=lambda x: (x["_rank"], -x["_score"]))
        else:
            items.sort(key=lambda x: x["_score"], reverse=True)
    return dict(grouped)


def load_labels(path: Path) -> Dict[Tuple[str, str], int]:
    """加载金标/银标文件，Key=(query_id, job_id)，Value=grade。"""
    labels: Dict[Tuple[str, str], int] = {}
    for rec in read_json_records(path):
        qid = query_id_of(rec)
        jid = str(rec.get("job_id") or "")
        if qid and jid:
            labels[(qid, jid)] = safe_int(rec.get("grade"), 0)
    return labels


# ══════════════════════════════════════════════════════════════════
# 指标计算
# ══════════════════════════════════════════════════════════════════

def dcg(grades: List[int], k: int) -> float:
    s = 0.0
    for i, g in enumerate(grades[:k], start=1):
        s += ((2**g) - 1) / math.log2(i + 1)
    return s


def ndcg(ranked: List[int], ideal: List[int], k: int) -> float:
    idcg = dcg(sorted(ideal, reverse=True), k)
    if idcg == 0:
        return 0.0
    return dcg(ranked, k) / idcg


def recall_at_k(ranked: List[int], k: int, positive: int, total_pos: int) -> float:
    if total_pos == 0:
        return 0.0
    hits = sum(1 for g in ranked[:k] if g >= positive)
    return hits / total_pos


def mrr(ranked: List[int], positive: int) -> float:
    for i, g in enumerate(ranked, start=1):
        if g >= positive:
            return 1.0 / i
    return 0.0


def mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def evaluate_single(
    ranking: Dict[str, List[Dict[str, Any]]],
    labels: Dict[Tuple[str, str], int],
    ks: List[int],
    positive_grade: int,
) -> Dict[str, Any]:
    """对单个模型的排序结果计算全部指标。"""
    labels_by_query: Dict[str, Dict[str, int]] = defaultdict(dict)
    for (qid, jid), grade in labels.items():
        labels_by_query[qid][jid] = grade

    per_query: List[Dict[str, Any]] = []
    for qid, items in sorted(ranking.items()):
        query_labels = labels_by_query.get(qid, {})
        if not query_labels:
            continue

        ranked_grades = [query_labels.get(str(it["job_id"]), 0) for it in items]
        ideal_grades = list(query_labels.values())
        total_pos = sum(1 for g in ideal_grades if g >= positive_grade)

        labeled_count = sum(
            1 for it in items if str(it["job_id"]) in query_labels
        )

        row: Dict[str, Any] = {
            "query_id": qid,
            "labeled_candidates": labeled_count,
            "positive_candidates": total_pos,
            "mrr": mrr(ranked_grades, positive_grade),
        }
        for k in ks:
            row[f"ndcg@{k}"] = ndcg(ranked_grades, ideal_grades, k)
            row[f"recall@{k}"] = recall_at_k(ranked_grades, k, positive_grade, total_pos)
        per_query.append(row)

    aggregate: Dict[str, Any] = {
        "evaluated_queries": len(per_query),
        "positive_grade_threshold": positive_grade,
    }
    if per_query:
        metric_keys = [
            key for key in per_query[0]
            if key not in {"query_id", "labeled_candidates", "positive_candidates"}
        ]
        for key in metric_keys:
            aggregate[key] = round(mean([row[key] for row in per_query]), 4)
        aggregate["mean_labeled_candidates"] = round(
            mean([row["labeled_candidates"] for row in per_query]), 1
        )
        aggregate["mean_positive_candidates"] = round(
            mean([row["positive_candidates"] for row in per_query]), 1
        )

    return {"aggregate": aggregate, "per_query": per_query}


# ══════════════════════════════════════════════════════════════════
# 多模型对比
# ══════════════════════════════════════════════════════════════════

def load_metadata(ranking_path: Path) -> Dict[str, Any]:
    """尝试读取同目录下的 run_metadata.json。"""
    meta_path = ranking_path.parent / "run_metadata.json"
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def estimate_file_size_mb(path: Path) -> float:
    """估算模型相关文件大小。"""
    parent = path.parent
    total = 0
    for f in parent.glob("*.npy"):
        total += f.stat().st_size
    return round(total / (1024 * 1024), 1)


def compare_all(
    bm25_path: Path,
    text2vec_path: Path,
    bge_path: Path,
    labels_path: Path,
    ks: List[int],
    positive_grade: int,
    output_path: Path,
) -> Dict[str, Any]:
    """三模型对比：BM25 vs BM25+text2vec vs BM25+BGE-M3。"""
    labels = load_labels(labels_path)

    configs = [
        {
            "name": "BM25",
            "path": bm25_path,
            "score_field": "bm25_score",
            "rank_field": "bm25_rank",
        },
        {
            "name": "BM25 + text2vec",
            "path": text2vec_path,
            "score_field": "semantic_score",
            "rank_field": "semantic_rank",
        },
        {
            "name": "BM25 + BGE-M3",
            "path": bge_path,
            "score_field": "semantic_score",
            "rank_field": "semantic_rank",
        },
    ]

    results: List[Dict[str, Any]] = []
    for cfg in configs:
        if not cfg["path"].exists():
            print(f"[跳过] {cfg['name']}: 文件不存在 ({cfg['path']})")
            results.append({"name": cfg["name"], "status": "missing", "path": str(cfg["path"])})
            continue

        ranking = load_ranking(cfg["path"], cfg["score_field"], cfg["rank_field"])
        eval_result = evaluate_single(ranking, labels, ks, positive_grade)

        meta = load_metadata(cfg["path"])
        file_size = estimate_file_size_mb(cfg["path"])

        results.append({
            "name": cfg["name"],
            "status": "ok",
            "path": str(cfg["path"]),
            "metrics": eval_result["aggregate"],
            "resources": {
                "encode_time_sec": meta.get("encode_time_sec"),
                "avg_query_encode_ms": meta.get("avg_query_encode_ms"),
                "peak_memory_mb": meta.get("peak_memory_mb"),
                "model_name": meta.get("model", {}).get("model_name"),
                "embedding_cache_mb": file_size,
                "embedding_dim": meta.get("embedding_dim"),
            },
        })

    report = {
        "workflow": "workflow_2_semantic_rerank_evaluation",
        "evaluation_ks": ks,
        "positive_grade_threshold": positive_grade,
        "labels_path": str(labels_path),
        "total_labeled_pairs": len(labels),
        "models": results,
    }

    # ── 对比摘要表格 ──────────────────────────────────────────────
    summary_rows: List[Dict[str, Any]] = []
    metric_names = [f"recall@{k}" for k in ks] + [f"ndcg@{k}" for k in ks] + ["mrr"]
    for r in results:
        row: Dict[str, Any] = {"模型": r["name"]}
        if r["status"] != "ok":
            row["状态"] = "文件缺失"
        else:
            for m in metric_names:
                row[m] = r["metrics"].get(m)
            res = r["resources"]
            row["编码耗时(s)"] = res.get("encode_time_sec")
            row["查询编码(ms)"] = res.get("avg_query_encode_ms")
            row["峰值内存(MB)"] = res.get("peak_memory_mb")
            row["向量缓存(MB)"] = res.get("embedding_cache_mb")
            row["模型"] = r["name"]
        summary_rows.append(row)

    report["comparison_summary"] = summary_rows
    write_json(output_path, report)

    # ── 打印对比表 ────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("工作流 2 — 语义重排评测对比报告")
    print("=" * 80)
    print(f"金标文件: {labels_path}")
    print(f"标注对总数: {len(labels)}")
    print(f"正样本阈值: grade >= {positive_grade}")
    print("-" * 80)

    headers = ["模型"] + metric_names + ["编码耗时(s)", "查询编码(ms)", "峰值内存(MB)"]
    col_widths = [max(len(h), 10) for h in headers]

    # 表头
    header_line = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    print(header_line)
    print("-" * len(header_line))

    for row in summary_rows:
        vals = [str(row.get(h, "-")) for h in headers]
        line = " | ".join(v.ljust(w) for v, w in zip(vals, col_widths))
        print(line)

    print("-" * 80)
    print(f"报告已保存: {output_path}")

    return report


def parse_ranking_spec(spec: str) -> Tuple[Path, str, Optional[str], str]:
    """解析 'path:score_field:rank_field:label' 格式。"""
    parts = spec.split(":")
    if len(parts) < 4:
        raise ValueError(f"无效的排名规格: {spec}（需要 path:score_field:rank_field:label）")
    path = Path(parts[0])
    score_field = parts[1]
    rank_field = parts[2] if parts[2] else None
    label = parts[3]
    return path, score_field, rank_field, label


# ══════════════════════════════════════════════════════════════════
# 命令行
# ══════════════════════════════════════════════════════════════════


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="工作流 2 — 语义重排评测")
    parser.add_argument("--ranking", type=Path, help="单模型排名文件路径")
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS, help="金标/银标文件")
    parser.add_argument("--score-field", default="semantic_score", help="得分字段名")
    parser.add_argument("--rank-field", default="semantic_rank", help="排名字段名（可选）")
    parser.add_argument("--positive-grade", type=int, default=2, help="正样本等级阈值")
    parser.add_argument("--ks", default="5,10,20,100", help="K 值列表，逗号分隔")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT, help="输出报告路径")
    parser.add_argument("--compare-all", action="store_true", help="三模型对比（BM25/text2vec/BGE-M3）")
    parser.add_argument("--compare", action="store_true", help="自定义多模型对比")
    parser.add_argument("--rankings", nargs="*", default=[], help="自定义对比: path:score:rank:label ...")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ks = [int(x.strip()) for x in args.ks.split(",") if x.strip()]

    # ── 三模型对比 ────────────────────────────────────────────────
    if args.compare_all:
        compare_all(
            bm25_path=DEFAULT_BM25,
            text2vec_path=DEFAULT_TEXT2VEC,
            bge_path=DEFAULT_BGE,
            labels_path=args.labels,
            ks=ks,
            positive_grade=args.positive_grade,
            output_path=args.output,
        )
        return

    # ── 自定义多模型对比 ──────────────────────────────────────────
    if args.compare:
        if not args.rankings:
            raise ValueError("--compare 需要 --rankings 参数")

        labels = load_labels(args.labels)
        results: List[Dict[str, Any]] = []
        for spec in args.rankings:
            path, score_f, rank_f, label = parse_ranking_spec(spec)
            if not path.exists():
                results.append({"name": label, "status": "missing", "path": str(path)})
                continue
            ranking = load_ranking(path, score_f, rank_f)
            eval_r = evaluate_single(ranking, labels, ks, args.positive_grade)
            results.append({
                "name": label,
                "status": "ok",
                "path": str(path),
                "metrics": eval_r["aggregate"],
            })

        report = {
            "workflow": "workflow_2_semantic_rerank_evaluation",
            "evaluation_ks": ks,
            "positive_grade_threshold": args.positive_grade,
            "labels_path": str(args.labels),
            "total_labeled_pairs": len(labels),
            "models": results,
        }
        write_json(args.output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    # ── 单模型评测 ────────────────────────────────────────────────
    if not args.ranking:
        raise ValueError("请指定 --ranking 或 --compare-all")

    labels = load_labels(args.labels)
    ranking = load_ranking(args.ranking, args.score_field, args.rank_field)
    eval_result = evaluate_single(ranking, labels, ks, args.positive_grade)
    report = {
        "workflow": "workflow_2_semantic_rerank_evaluation",
        "ranking_path": str(args.ranking),
        "labels_path": str(args.labels),
        "score_field": args.score_field,
        "rank_field": args.rank_field,
        "evaluation_ks": ks,
        "positive_grade_threshold": args.positive_grade,
        "total_labeled_pairs": len(labels),
        **eval_result,
    }
    write_json(args.output, report)
    print(json.dumps(report["aggregate"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
