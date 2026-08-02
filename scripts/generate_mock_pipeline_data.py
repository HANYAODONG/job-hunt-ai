"""
生成 Mock 工作流2/3/5 占位数据 + 运行完整融合管道

用途：在其他工作流（W2 text2vec / W3 KG / W5 BM25重建）尚未产出时，
      用 sample 数据或全量数据生成符合 data-schema.md 格式的占位文件，
      让 W4 融合排序可以先跑通端到端链路。

占位数据策略：
  - BM25: 从标准 jobs.jsonl 随机抽样 TopK 岗位，用 jaccard 相似度模拟 score
  - Semantic: 基于简历 skills 与岗位 skills 的 jaccard overlap 模拟
  - KG: 基于简历 skills 和岗位 skills 计算覆盖率，随机生成 graph_relatedness

使用：
  # 用 sample_pack 快速测试
  python scripts/generate_mock_pipeline_data.py --mode sample

  # 全量数据（30k 简历 × 14k 岗位，BM25会非常慢）
  python scripts/generate_mock_pipeline_data.py --mode full --limit-resumes 100

输出目录：
  artifacts/bm25/          — bm25_top200.jsonl (Mock BM25候选)
  artifacts/semantic_text2vec/ — semantic_rerank_top200.jsonl (Mock 语义重排)
  artifacts/skill_graph/   — kg_features.jsonl (Mock KG特征)
  artifacts/fusion_ranking/ — fusion_*.jsonl + eval_*.json (融合结果 + 评测)
"""

import argparse
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
DATASET_DIR = ARTIFACTS_DIR / "dataset_iteration_05"

# — 输出目录 —
BM25_DIR = ARTIFACTS_DIR / "bm25"
SEMANTIC_DIR = ARTIFACTS_DIR / "semantic_text2vec"
KG_DIR = ARTIFACTS_DIR / "skill_graph"
FUSION_DIR = ARTIFACTS_DIR / "fusion_ranking"

# — 默认参数 —
DEFAULT_TOP_K = 200
DEFAULT_SEED = 42


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: List[Dict[str, Any]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_json(path: Path, payload: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def jaccard(set_a: set, set_b: set) -> float:
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def load_standard_data(mode: str) -> tuple:
    """加载标准数据，mode='sample' 用 sample_pack，'full' 用全量"""
    if mode == "sample":
        jobs = read_jsonl(DATASET_DIR / "sample_pack" / "jobs_sample.jsonl")
        resumes = read_jsonl(DATASET_DIR / "sample_pack" / "candidate_profiles_sample.jsonl")
        print(f"Sample 模式: {len(resumes)} 简历, {len(jobs)} 岗位")
    else:
        jobs = read_jsonl(DATASET_DIR / "jobs.jsonl")
        resumes = read_jsonl(DATASET_DIR / "candidate_profiles.jsonl")
        print(f"Full 模式: {len(resumes)} 简历, {len(jobs)} 岗位")
    return jobs, resumes


def generate_mock_bm25(
    resumes: List[Dict], jobs: List[Dict], top_k: int, seed: int
) -> List[Dict]:
    """
    生成 Mock BM25 候选集。
    对每份简历，从全量岗位中根据 query_text 和 job description 的
    token overlap 模拟 BM25 召回，取 top_k。
    """
    random.seed(seed)
    print(f"生成 Mock BM25 候选集 (top_k={top_k})...")

    # 预计算岗位 token 集
    job_tokens: Dict[str, set] = {}
    for job in jobs:
        jid = job["job_id"]
        text = f"{job.get('title', '')} {job.get('description', '')} {' '.join(job.get('skills', []))}"
        job_tokens[jid] = set(text.lower().split())

    bm25_records = []
    for i, resume in enumerate(resumes):
        cid = resume["candidate_id"]
        query_text = resume.get("summary", "") or resume.get("profile_text", "")
        query_tokens = set(query_text.lower().split())

        # 计算 overlap 作为 mock BM25 score
        scored = []
        for job in jobs:
            jid = job["job_id"]
            overlap = len(query_tokens & job_tokens.get(jid, set()))
            if overlap == 0:
                continue
            # 模拟 BM25: overlap + 小噪声
            noise = random.uniform(0.8, 1.2)
            score = overlap * noise
            scored.append({"job_id": jid, "bm25_score": round(score, 2)})

        # 按分数降序，取 top_k
        scored.sort(key=lambda x: x["bm25_score"], reverse=True)
        top = scored[:top_k]
        for rank, item in enumerate(top):
            item["bm25_rank"] = rank + 1

        bm25_records.append({
            "query_id": cid,
            "candidates": top if top else [
                {"job_id": jobs[0]["job_id"], "bm25_score": 0.0, "bm25_rank": 1}
            ],
        })

        if (i + 1) % 500 == 0:
            print(f"  BM25: {i + 1}/{len(resumes)} resumes done")

    print(f"  BM25: {len(bm25_records)} queries generated")
    return bm25_records


def generate_mock_semantic(
    resumes: List[Dict], bm25_records: List[Dict], jobs: List[Dict], seed: int
) -> List[Dict]:
    """
    生成 Mock 语义重排结果。
    基于简历 skills 和岗位 skills 的 jaccard + 噪声模拟 semantic_score。
    候选集 = BM25 候选集（模拟只对 BM25 候选做重排）。
    """
    random.seed(seed + 1)
    print("生成 Mock 语义重排结果...")

    # 简历 skills 索引
    resume_skills: Dict[str, set] = {}
    for r in resumes:
        resume_skills[r["candidate_id"]] = set(
            s.lower() for s in r.get("skills", []) or r.get("skills_normalized", [])
        )

    # 岗位 skills 索引
    job_skills: Dict[str, set] = {}
    for j in jobs:
        job_skills[j["job_id"]] = set(
            s.lower() for s in j.get("skills", []) or j.get("required_skills", [])
        )

    semantic_records = []
    for record in bm25_records:
        cid = record["query_id"]
        r_skills = resume_skills.get(cid, set())

        candidates = []
        for c in record.get("candidates", []):
            jid = c["job_id"]
            j_skills = job_skills.get(jid, set())
            # jaccard + noise
            base = jaccard(r_skills, j_skills)
            noise = random.uniform(0.85, 1.15)
            semantic_score = round(min(1.0, base * noise + random.uniform(0, 0.15)), 4)
            candidates.append({
                "job_id": jid,
                "semantic_score": semantic_score,
                "semantic_rank": 0,  # 后面统一排序
            })

        # 按 semantic_score 降序
        candidates.sort(key=lambda x: x["semantic_score"], reverse=True)
        for rank, item in enumerate(candidates):
            item["semantic_rank"] = rank + 1

        semantic_records.append({
            "query_id": cid,
            "candidates": candidates,
        })

    print(f"  语义重排: {len(semantic_records)} queries generated")
    return semantic_records


def generate_mock_kg(
    resumes: List[Dict], bm25_records: List[Dict], jobs: List[Dict], seed: int
) -> List[Dict]:
    """
    生成 Mock KG 特征。
    对每对 (query, job) 输出:
    - skill_coverage: 简历技能覆盖岗位技能的比例
    - job_family_match: 1.0 if 简历目标岗位族 == 岗位族 else 0.0
    - graph_relatedness: jaccard * noise
    - matched_skills / missing_skills
    """
    random.seed(seed + 2)
    print("生成 Mock KG 特征...")

    # 简历索引
    resume_index: Dict[str, Dict] = {r["candidate_id"]: r for r in resumes}
    # 岗位索引
    job_index: Dict[str, Dict] = {j["job_id"]: j for j in jobs}

    kg_records = []
    for record in bm25_records:
        cid = record["query_id"]
        resume = resume_index.get(cid, {})
        r_skills = set(s.lower() for s in resume.get("skills", []) or resume.get("skills_normalized", []))
        r_family = (resume.get("target_job_family") or "").strip()

        for c in record.get("candidates", []):
            jid = c["job_id"]
            job = job_index.get(jid, {})
            j_skills = set(s.lower() for s in job.get("skills", []) or job.get("required_skills", []))
            j_family = (job.get("job_family") or job.get("standard_job") or "").strip()

            # skill_coverage: 简历技能中在岗位技能中的比例
            if j_skills:
                matched = r_skills & j_skills
                skill_coverage = round(len(matched) / len(j_skills), 4)
            else:
                matched = set()
                skill_coverage = 0.0

            # job_family_match
            job_family_match = 1.0 if r_family and j_family and r_family == j_family else 0.0

            # graph_relatedness: jaccard + noise
            jacc = jaccard(r_skills, j_skills)
            graph_relatedness = round(min(1.0, jacc * random.uniform(0.8, 1.2)), 4)

            # matched / missing skills
            matched_list = list(matched)[:10] if matched else []
            missing_list = list(j_skills - r_skills)[:5] if j_skills else []

            # evidence_paths (mock)
            evidence = []
            if matched:
                evidence.append(
                    f"Candidate→HAS_SKILL→{matched_list[0]}←REQUIRES_SKILL←Job:{jid}"
                )
            if graph_relatedness > 0.3:
                evidence.append(
                    f"Skill:{random.choice(list(j_skills or ['General']))}"
                    f"→RELATED_TO→Skill:{random.choice(list(r_skills or ['General']))}"
                )

            kg_records.append({
                "query_id": cid,
                "job_id": jid,
                "matched_skills": matched_list,
                "missing_skills": missing_list,
                "skill_coverage": skill_coverage,
                "job_family_match": job_family_match,
                "graph_relatedness": graph_relatedness,
                "evidence_paths": evidence,
            })

        if (len(kg_records) % 5000) < len(record.get("candidates", [])):
            print(f"  KG: {len(kg_records)} pairs done")

    print(f"  KG: {len(kg_records)} pairs generated")
    return kg_records


def generate_all_mock_data(
    resumes: List[Dict], jobs: List[Dict], top_k: int, seed: int
) -> tuple:
    """一键生成所有 Mock 数据"""
    t0 = time.time()

    bm25 = generate_mock_bm25(resumes, jobs, top_k, seed)
    write_jsonl(BM25_DIR / "bm25_top200.jsonl", bm25)
    print(f"  -> {BM25_DIR / 'bm25_top200.jsonl'}")

    semantic = generate_mock_semantic(resumes, bm25, jobs, seed)
    write_jsonl(SEMANTIC_DIR / "semantic_rerank_top200.jsonl", semantic)
    print(f"  -> {SEMANTIC_DIR / 'semantic_rerank_top200.jsonl'}")

    kg = generate_mock_kg(resumes, bm25, jobs, seed)
    write_jsonl(KG_DIR / "kg_features.jsonl", kg)
    print(f"  -> {KG_DIR / 'kg_features.jsonl'}")

    elapsed = time.time() - t0
    print(f"Mock 数据生成完成，耗时 {elapsed:.1f}s")
    return bm25, semantic, kg


def run_fusion_from_mock(seed: int) -> Dict[str, Any]:
    """从 Mock 数据运行离线融合管道"""
    # 确保路径在 sys.path
    backend_src = str(REPO_ROOT / "backend-src")
    if backend_src not in sys.path:
        sys.path.insert(0, backend_src)

    from app.models.fusion import FusionWeights
    from app.services.fusion_merge_service import merge_from_artifacts, read_jsonl as merge_read
    from app.services.fusion_scoring_service import fuse_batch

    # 权重预设
    presets = {
        "bm25-only": FusionWeights(bm25=1.0, semantic=0.0, skill_coverage=0.0, job_family=0.0, graph=0.0),
        "bm25-semantic": FusionWeights(bm25=0.40, semantic=0.60, skill_coverage=0.0, job_family=0.0, graph=0.0),
        "bm25-semantic-skill": FusionWeights(bm25=0.30, semantic=0.30, skill_coverage=0.40, job_family=0.0, graph=0.0),
        "full": FusionWeights(bm25=0.15, semantic=0.25, skill_coverage=0.30, job_family=0.15, graph=0.15),
    }

    print("\n运行融合排序...")

    bm25_path = BM25_DIR / "bm25_top200.jsonl"
    semantic_path = SEMANTIC_DIR / "semantic_rerank_top200.jsonl"
    kg_path = KG_DIR / "kg_features.jsonl"

    bm25_records = merge_read(str(bm25_path)) if bm25_path.exists() else None
    semantic_records = merge_read(str(semantic_path)) if semantic_path.exists() else None
    kg_records = merge_read(str(kg_path)) if kg_path.exists() else None

    if not bm25_records:
        print("❌ BM25 占位数据不存在，请先运行 generate_mock_bm25")
        return {}

    # Flatten KG records (they're already flat, not grouped by query_id)
    # merge_from_artifacts expects them grouped, but our mock format is already flat
    # So we pass them as-is — merge_from_artifacts handles flat kg_features correctly

    merged = merge_from_artifacts(
        bm25_candidates=bm25_records,
        semantic_candidates=semantic_records,
        kg_features=kg_records,
        include_meta=False,
    )
    print(f"合并完成: {len(merged)} queries")

    summary = {}
    FUSION_DIR.mkdir(parents=True, exist_ok=True)

    for preset_name, weights in presets.items():
        batch_results = []
        for query_id, inputs in merged.items():
            outputs = fuse_batch(inputs, weights)
            batch_results.append({
                "query_id": query_id,
                "results": [
                    {
                        "job_id": o.job_id,
                        "final_score": o.final_score,
                        "rank": o.rank,
                        "score_breakdown": o.score_breakdown.model_dump(),
                        "explanation": o.explanation.model_dump(),
                        "evidence_paths": o.evidence_paths,
                    }
                    for o in outputs
                ],
            })

        # 写入结果
        output_path = FUSION_DIR / f"fusion_{preset_name}.jsonl"
        with open(output_path, "w", encoding="utf-8") as f:
            for batch in batch_results:
                f.write(json.dumps(batch, ensure_ascii=False, separators=(",", ":")) + "\n")

        # 统计
        all_scores = []
        for batch in batch_results:
            for r in batch["results"]:
                all_scores.append(r["final_score"])

        avg = sum(all_scores) / len(all_scores) if all_scores else 0
        summary[preset_name] = {
            "queries": len(batch_results),
            "pairs": len(all_scores),
            "weights": weights.model_dump(),
            "avg_score": round(avg, 4),
            "output": str(output_path),
        }
        print(f"  {preset_name}: {len(batch_results)} queries, {len(all_scores)} pairs, avg_score={avg:.4f}")

    # 汇总报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "mock_pipeline",
        "source": "generate_mock_pipeline_data.py",
        "presets": summary,
    }
    write_json(FUSION_DIR / "fusion_summary.json", report)
    print(f"汇总报告: {FUSION_DIR / 'fusion_summary.json'}")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="生成 Mock 工作流占位数据并运行融合管道 (W4)",
    )
    parser.add_argument(
        "--mode", choices=["sample", "full"], default="sample",
        help="sample: 使用 sample_pack (默认); full: 使用全量数据",
    )
    parser.add_argument(
        "--limit-resumes", type=int, default=None,
        help="[full模式] 限制处理的简历数量",
    )
    parser.add_argument(
        "--top-k", type=int, default=DEFAULT_TOP_K,
        help=f"BM25 召回 TopK (默认 {DEFAULT_TOP_K})",
    )
    parser.add_argument(
        "--seed", type=int, default=DEFAULT_SEED,
        help=f"随机种子 (默认 {DEFAULT_SEED})",
    )
    parser.add_argument(
        "--skip-fusion", action="store_true",
        help="仅生成占位数据，不运行融合排序",
    )
    parser.add_argument(
        "--skip-generate", action="store_true",
        help="仅运行融合排序（需要已有占位数据文件）",
    )
    args = parser.parse_args()

    if not args.skip_generate:
        print("=" * 60)
        print("Step 1: 生成 Mock 工作流占位数据")
        print("=" * 60)

        jobs, resumes = load_standard_data(args.mode)

        if args.limit_resumes and args.mode == "full":
            resumes = resumes[:args.limit_resumes]
            print(f"  限制为前 {len(resumes)} 份简历")

        generate_all_mock_data(resumes, jobs, args.top_k, args.seed)

    if not args.skip_fusion:
        print("=" * 60)
        print("Step 2: 运行融合排序管道")
        print("=" * 60)
        run_fusion_from_mock(args.seed)

    print("\n[Done]")
    print(f"""
产物目录:
  {BM25_DIR}/          — BM25 Mock 候选集
  {SEMANTIC_DIR}/      — 语义重排 Mock 结果
  {KG_DIR}/            — KG 特征 Mock 数据
  {FUSION_DIR}/        — 融合排序结果 + 评测

下一步 — 评估:
    python scripts/evaluate_candidate_rankings.py \\
        --ranking "{FUSION_DIR}/fusion_full.jsonl" \\
        --labels "{DATASET_DIR}/label_pairs_gold.jsonl" \\
        --score-field final_score --rank-field rank \\
        --positive-grade 2 --ks 5,10,20 \\
        --output "{FUSION_DIR}/eval_full.json"
""")


if __name__ == "__main__":
    main()
