"""
离线融合排序与消融实验脚本 — 工作流4

读取其他工作流的离线输出文件，执行多因子融合排序，
支持多种权重组合的消融对比实验。

用法：
    # BM25-only baseline
    python backend-src/scripts/run_fusion_pipeline.py \
        --bm25-input artifacts/bm25/bm25_top200.jsonl \
        --preset bm25-only

    # 多组消融对比（输出到不同文件）
    python backend-src/scripts/run_fusion_pipeline.py \
        --bm25-input artifacts/bm25/bm25_top200.jsonl \
        --preset all

    # 接入所有因子（等W2/W3完成后）
    python backend-src/scripts/run_fusion_pipeline.py \
        --bm25-input artifacts/bm25/bm25_top200.jsonl \
        --semantic-input artifacts/semantic_index/semantic_rerank_output.jsonl \
        --kg-input artifacts/kg/kg_features.jsonl \
        --preset all

输出：
    artifacts/fusion/fusion_{preset}.jsonl     — 融合排序结果（Batch JSONL）
    artifacts/fusion/fusion_{preset}_summary.json — 汇总统计

后续评估：
    python scripts/evaluate_candidate_rankings.py \
        --ranking artifacts/fusion/fusion_bm25-only.jsonl \
        --labels artifacts/dataset_iteration_05/label_pairs_gold.jsonl \
        --score-field final_score --rank-field rank --positive-grade 2
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# 确保 backend-src 在 sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.models.fusion import FusionWeights
from app.services.fusion_merge_service import merge_from_artifacts, read_jsonl
from app.services.fusion_scoring_service import fuse_batch


# ── 权重预设 ────────────────────────────────────────────────────

WEIGHT_PRESETS: Dict[str, FusionWeights] = {
    "bm25-only": FusionWeights(
        bm25=1.0, semantic=0.0, skill_coverage=0.0, job_family=0.0, graph=0.0,
    ),
    "default": FusionWeights(
        bm25=0.15, semantic=0.25, skill_coverage=0.30, job_family=0.15, graph=0.15,
    ),
    "bm25-semantic": FusionWeights(
        bm25=0.40, semantic=0.60, skill_coverage=0.0, job_family=0.0, graph=0.0,
    ),
    "bm25-semantic-skill": FusionWeights(
        bm25=0.30, semantic=0.30, skill_coverage=0.40, job_family=0.0, graph=0.0,
    ),
    "full": FusionWeights(
        bm25=0.15, semantic=0.25, skill_coverage=0.30, job_family=0.15, graph=0.15,
    ),
}

PRESETS_FOR_ABLATION = ["bm25-only", "bm25-semantic", "bm25-semantic-skill", "full"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="离线融合排序与消融实验",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # BM25 baseline
  python run_fusion_pipeline.py --bm25-input artifacts/bm25/bm25_top200.jsonl

  # 全部消融对比
  python run_fusion_pipeline.py --bm25-input artifacts/bm25/bm25_top200.jsonl --preset all

  # 接入所有因子
  python run_fusion_pipeline.py \\
      --bm25-input artifacts/bm25/bm25_top200.jsonl \\
      --semantic-input artifacts/semantic_index/semantic_rerank_output.jsonl \\
      --kg-input artifacts/kg/kg_features.jsonl
        """,
    )
    parser.add_argument(
        "--bm25-input", type=Path,
        help="BM25候选集文件路径 (artifacts/bm25/bm25_top200.jsonl)",
    )
    parser.add_argument(
        "--semantic-input", type=Path,
        help="语义重排输出文件路径 (可选，等W2完成后)",
    )
    parser.add_argument(
        "--kg-input", type=Path,
        help="知识图谱特征文件路径 (可选，等W3完成后)",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=REPO_ROOT / "artifacts" / "fusion",
        help="输出目录 (默认: artifacts/fusion/)",
    )
    parser.add_argument(
        "--preset", type=str, default="bm25-only",
        choices=list(WEIGHT_PRESETS.keys()) + ["all"],
        help="权重预设。'all' 表示运行全部消融对比 (bm25-only, bm25-semantic, bm25-semantic-skill, full)",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="限制处理的简历数量 (用于快速测试)",
    )
    parser.add_argument(
        "--top-k", type=int, default=200,
        help="每个 query 保留的 TopK 结果 (默认 200)",
    )
    parser.add_argument(
        "--custom-weights", type=str, default=None,
        help='自定义权重 JSON，例如: \'{"bm25":0.4,"semantic":0.6,"skill_coverage":0,"job_family":0,"graph":0}\'',
    )
    return parser.parse_args()


def load_optional(path: Optional[Path], label: str) -> Optional[List[Dict[str, Any]]]:
    """加载可选文件，不存在时打印提示"""
    if path is None:
        return None
    if not path.exists():
        print(f"⚠️  {label} 文件不存在: {path}，跳过")
        return None
    records = read_jsonl(str(path))
    print(f"✅ {label}: {len(records)} 条记录 (来自 {path})")
    return records


def run_fusion(
    merged: Dict[str, List[Any]],
    weights: FusionWeights,
    top_k: int,
) -> List[Dict[str, Any]]:
    """对合并后的数据执行融合排序，返回 Batch JSONL 格式的结果"""
    batch_results = []
    total_pairs = 0

    for query_id, inputs in merged.items():
        if not inputs:
            continue
        outputs = fuse_batch(inputs, weights)
        # 截断到 top_k
        outputs = outputs[:top_k]
        total_pairs += len(outputs)

        batch_results.append({
            "query_id": query_id,
            "results": [
                {
                    "job_id": o.job_id,
                    "final_score": o.final_score,
                    "rank": o.rank,
                    "score_breakdown": o.score_breakdown.model_dump(),
                    "explanation": o.explanation,
                    "missing_skills": o.missing_skills,
                    "evidence_paths": o.evidence_paths,
                }
                for o in outputs
            ],
        })

    print(f"  融合完成: {len(batch_results)} queries, {total_pairs} pairs, top_k={top_k}")
    return batch_results


def compute_summary(batch_results: List[Dict[str, Any]], weights: FusionWeights) -> Dict[str, Any]:
    """计算汇总统计"""
    all_scores = []
    query_top_scores = []
    query_avg_scores = []

    for batch in batch_results:
        results = batch["results"]
        if results:
            scores = [r["final_score"] for r in results]
            all_scores.extend(scores)
            query_top_scores.append(scores[0])
            query_avg_scores.append(sum(scores) / len(scores))

    if not all_scores:
        return {"queries": 0, "pairs": 0}

    return {
        "queries": len(batch_results),
        "pairs": len(all_scores),
        "weights": weights.model_dump(),
        "score_stats": {
            "mean": round(sum(all_scores) / len(all_scores), 4),
            "max": round(max(all_scores), 4),
            "min": round(min(all_scores), 4),
            "top_query_mean": round(sum(query_top_scores) / len(query_top_scores), 4),
            "avg_query_mean": round(sum(query_avg_scores) / len(query_avg_scores), 4),
        },
        "quality_distribution": {
            "excellent (>=0.75)": sum(1 for s in all_scores if s >= 0.75),
            "good (>=0.55)": sum(1 for s in all_scores if 0.55 <= s < 0.75),
            "fair (>=0.35)": sum(1 for s in all_scores if 0.35 <= s < 0.55),
            "low (<0.35)": sum(1 for s in all_scores if s < 0.35),
        },
    }


def main() -> None:
    args = parse_args()

    # 1. 加载数据
    print("=" * 60)
    print("工作流4：离线融合排序")
    print("=" * 60)

    bm25_records = load_optional(args.bm25_input, "BM25候选集")
    semantic_records = load_optional(args.semantic_input, "语义重排")
    kg_records = load_optional(args.kg_input, "知识图谱特征")

    if bm25_records is None:
        print("❌ 至少需要 --bm25-input 才能运行融合排序")
        sys.exit(1)

    # 限制数量
    if args.limit is not None and args.limit > 0:
        bm25_records = bm25_records[:args.limit]
        if semantic_records:
            semantic_records = semantic_records[:args.limit]
        print(f"🔸 限制处理前 {args.limit} 条简历")

    # 2. 合并
    print("-" * 40)
    print("合并多方工作流输出...")
    t0 = time.time()
    merged = merge_from_artifacts(
        bm25_candidates=bm25_records,
        semantic_candidates=semantic_records,
        kg_features=kg_records,
        include_meta=False,
    )
    merge_time = time.time() - t0
    print(f"合并耗时: {merge_time:.2f}s, {len(merged)} queries")

    # 3. 确定权重组合
    if args.custom_weights:
        presets_to_run = {"custom": FusionWeights(**json.loads(args.custom_weights))}
    elif args.preset == "all":
        presets_to_run = {k: WEIGHT_PRESETS[k] for k in PRESETS_FOR_ABLATION}
    else:
        presets_to_run = {args.preset: WEIGHT_PRESETS[args.preset]}

    # 4. 运行融合
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "inputs": {
            "bm25": str(args.bm25_input) if args.bm25_input else None,
            "semantic": str(args.semantic_input) if args.semantic_input else None,
            "kg": str(args.kg_input) if args.kg_input else None,
        },
        "merge_time_s": round(merge_time, 2),
        "total_queries": len(merged),
        "presets": {},
    }

    for preset_name, weights in presets_to_run.items():
        print("-" * 40)
        print(f"运行预设: {preset_name}")
        print(f"  权重: {weights.model_dump()}")

        t1 = time.time()
        batch_results = run_fusion(merged, weights, args.top_k)
        fusion_time = time.time() - t1

        # 输出结果文件
        output_path = args.output_dir / f"fusion_{preset_name}.jsonl"
        with open(output_path, "w", encoding="utf-8") as f:
            for batch in batch_results:
                f.write(json.dumps(batch, ensure_ascii=False, separators=(",", ":")) + "\n")
        print(f"  输出: {output_path} ({fusion_time:.2f}s)")

        # 汇总统计
        summary = compute_summary(batch_results, weights)
        summary["fusion_time_s"] = round(fusion_time, 2)
        summary["output_file"] = str(output_path)
        summary_report["presets"][preset_name] = summary

        # 打印摘要
        stats = summary["score_stats"]
        dist = summary["quality_distribution"]
        print(f"  统计: queries={summary['queries']}, pairs={summary['pairs']}")
        print(f"  分数: mean={stats['mean']}, max={stats['max']}, min={stats['min']}")
        print(f"  分布: 优秀={dist['excellent (>=0.75)']}, "
              f"良好={dist['good (>=0.55)']}, "
              f"一般={dist['fair (>=0.35)']}, "
              f"较低={dist['low (<0.35)']}")

    # 输出汇总报告
    summary_path = args.output_dir / "fusion_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_report, f, ensure_ascii=False, indent=2)
    print("=" * 60)
    print(f"汇总报告: {summary_path}")
    print("=" * 60)

    # 提示后续评估命令
    if args.preset != "all":
        preset_name = args.preset if not args.custom_weights else "custom"
        output_path = args.output_dir / f"fusion_{preset_name}.jsonl"
        print(f"""
下一步 — 评估排序质量：
    python scripts/evaluate_candidate_rankings.py \\
        --ranking "{output_path}" \\
        --labels "artifacts/dataset_iteration_05/label_pairs_gold.jsonl" \\
        --score-field final_score \\
        --rank-field rank \\
        --positive-grade 2 \\
        --ks 10,20,50,100,200 \\
        --output "artifacts/fusion/eval_{preset_name}.json"
""")


if __name__ == "__main__":
    main()
