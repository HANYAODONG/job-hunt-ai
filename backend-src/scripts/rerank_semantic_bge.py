"""
工作流 2 — BGE-M3 语义重排对照组

与 rerank_semantic_text2vec.py 使用相同的流水线结构，但使用 BGE-M3 模型。
用于公平对比 text2vec 和 BGE-M3 在相同 BM25 Top200 候选集上的效果和资源占用。

流水线：
    1. 离线阶段：读取 jobs.jsonl → 构建岗位文本 → BGE-M3 编码 → 缓存向量 + ID 映射
    2. 在线阶段：读取 BM25 Top200 候选集 → 编码简历 → 仅对 Top200 候选计算余弦相似度 → 排序输出

用法：
    python backend-src/scripts/rerank_semantic_bge.py
    python backend-src/scripts/rerank_semantic_bge.py --limit 50
    python backend-src/scripts/rerank_semantic_bge.py --job-text-mode title+requirements

输出：
    artifacts/semantic_bge/
        jobs_embeddings.npy
        jobs_embedding_ids.json
        semantic_rerank_top200.jsonl
        run_metadata.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

_SCRIPT_DIR = Path(__file__).resolve()
BACKEND_ROOT = _SCRIPT_DIR.parents[1]
_REPO_ROOT = BACKEND_ROOT.parent
if not (_REPO_ROOT / "artifacts").exists() and (BACKEND_ROOT / "artifacts").exists():
    _REPO_ROOT = BACKEND_ROOT
REPO_ROOT = _REPO_ROOT
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.semantic_embedding_service import SemanticEmbeddingService

# ── 默认路径 ──────────────────────────────────────────────────────

DEFAULT_JOBS = REPO_ROOT / "artifacts" / "dataset_iteration_05" / "jobs.jsonl"
DEFAULT_BM25 = REPO_ROOT / "artifacts" / "bm25" / "bm25_top200.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "semantic_bge"
DEFAULT_MODEL = "BAAI/bge-m3"


# ══════════════════════════════════════════════════════════════════
# 工具函数（与 text2vec 脚本保持一致）
# ══════════════════════════════════════════════════════════════════

def read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{lineno} JSON 解析失败: {exc}") from exc


def read_jsonl_all(path: Path) -> List[Dict[str, Any]]:
    return list(read_jsonl(path))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


JOB_TEXT_MODES = {
    "title_only",
    "title+requirements",
    "title+duty+requirements+skills",
}


def build_job_text(job: Dict[str, Any], mode: str) -> str:
    title = str(job.get("title") or job.get("job_title") or "")
    responsibilities = str(job.get("responsibilities") or job.get("job_responsibility") or "")
    requirements = str(job.get("requirements") or job.get("job_requirement") or "")
    description = str(job.get("description") or job.get("job_description") or "")
    detailed = str(job.get("detailed") or "")
    skills_raw = job.get("skills") or job.get("required_skills") or []
    if isinstance(skills_raw, list):
        skills_text = " ".join(str(s) for s in skills_raw if s)
    else:
        skills_text = str(skills_raw)
    if not responsibilities and not requirements and description:
        responsibilities = description
    if mode == "title_only":
        return title
    elif mode == "title+requirements":
        parts = [title, requirements or description or detailed]
        return " ".join(p for p in parts if p)
    else:
        parts = [title, responsibilities, requirements, detailed, skills_text]
        return " ".join(p for p in parts if p)


def build_query_text(profile: Dict[str, Any]) -> str:
    target_family = str(profile.get("target_job_family") or "").strip()
    summary = str(profile.get("summary") or profile.get("profile_text") or "")
    skills = profile.get("skills") or profile.get("skills_normalized") or []
    if isinstance(skills, list):
        skills_text = " ".join(str(s) for s in skills[:30])
    else:
        skills_text = str(skills)
    education = profile.get("education") or {}
    if isinstance(education, dict):
        major = str(education.get("major") or "")
    else:
        major = ""
    years = profile.get("years_experience")
    years_text = f"{years}年经验" if isinstance(years, (int, float)) and years > 0 else ""
    experience = profile.get("experience") or []
    roles: List[str] = []
    if isinstance(experience, list):
        for item in experience:
            if isinstance(item, dict):
                role = str(item.get("role") or item.get("title") or "")
                if role:
                    roles.append(role)
    parts = [target_family, skills_text, years_text, major] + roles
    return " ".join(p for p in parts if p)


# ══════════════════════════════════════════════════════════════════
# 核心流水线
# ══════════════════════════════════════════════════════════════════


def encode_jobs_offline(
    jobs_path: Path,
    out_dir: Path,
    service: SemanticEmbeddingService,
    job_text_mode: str,
    force: bool = False,
    max_jobs: int = 0,
) -> Tuple[np.ndarray, List[str], float]:
    """离线阶段：编码岗位向量并缓存。max_jobs=0 表示全部。"""
    emb_path = out_dir / "jobs_embeddings.npy"
    ids_path = out_dir / "jobs_embedding_ids.json"

    if not force and emb_path.exists() and ids_path.exists():
        cached = np.load(emb_path)
        job_ids = json.loads(ids_path.read_text(encoding="utf-8"))
        test_vec = np.asarray(service.encode_text("测试"), dtype=np.float32)
        if cached.shape[1] == test_vec.shape[0]:
            if max_jobs > 0 and len(job_ids) > max_jobs:
                print(f"[离线] 缓存有 {len(job_ids)} 条，截取前 {max_jobs} 条")
                return cached[:max_jobs], job_ids[:max_jobs], 0.0
            print(f"[离线] 岗位向量缓存已存在且维度匹配 ({cached.shape[1]}d), 跳过编码: {emb_path}")
            return cached, job_ids, 0.0
        else:
            print(f"[离线] 缓存维度 ({cached.shape[1]}d) 与当前模型 ({test_vec.shape[0]}d) 不匹配, 重新编码")

    print(f"[离线] 读取岗位数据: {jobs_path}")
    jobs = read_jsonl_all(jobs_path)

    if max_jobs > 0 and len(jobs) > max_jobs:
        jobs = jobs[:max_jobs]

    print(f"[离线] 共 {len(jobs)} 条岗位")

    job_ids: List[str] = []
    job_texts: List[str] = []
    skipped = 0
    for job in jobs:
        jid = str(job.get("job_id") or job.get("id") or "")
        text = build_job_text(job, job_text_mode)
        if not jid or not text:
            skipped += 1
            continue
        job_ids.append(jid)
        job_texts.append(text)

    if skipped:
        print(f"[离线] 跳过 {skipped} 条无 ID 或无文本的岗位")

    print(f"[离线] 开始编码 {len(job_texts)} 条岗位文本 (模型: {service.model_name}, 模式: {job_text_mode})")
    t0 = time.perf_counter()
    job_vecs_list = service.encode_texts(job_texts)
    elapsed = time.perf_counter() - t0

    job_embeddings = np.asarray(job_vecs_list, dtype=np.float32)
    print(f"[离线] 编码完成: {job_embeddings.shape}, 耗时 {elapsed:.1f}s")

    service.save_embeddings(job_embeddings, emb_path)
    service.save_embedding_ids(job_ids, ids_path)

    return job_embeddings, job_ids, elapsed


def rerank_with_bm25_candidates(
    bm25_path: Path,
    job_embeddings: np.ndarray,
    job_ids: List[str],
    out_dir: Path,
    service: SemanticEmbeddingService,
    job_text_mode: str,
    limit: Optional[int] = None,
) -> Tuple[Path, float, int]:
    print(f"[在线] 读取 BM25 候选集: {bm25_path}")
    bm25_records = read_jsonl_all(bm25_path)
    print(f"[在线] 共 {len(bm25_records)} 条查询")

    id_to_idx: Dict[str, int] = {jid: idx for idx, jid in enumerate(job_ids)}
    output_path = out_dir / "semantic_rerank_top200.jsonl"
    query_count = 0
    candidate_count = 0
    total_encode_ms = 0.0
    tracemalloc.start()

    with output_path.open("w", encoding="utf-8", newline="\n") as fh:
        for record in bm25_records:
            if limit is not None and query_count >= limit:
                break

            query_id = str(
                record.get("query_id")
                or record.get("candidate_id")
                or record.get("resume_id")
                or ""
            ).strip()
            if not query_id:
                raise ValueError(f"BM25 记录缺少 query_id")

            query_text = str(record.get("query_text") or "").strip()
            bm25_candidates = record.get("candidates", [])

            valid_candidates = [
                c for c in bm25_candidates
                if str(c.get("job_id", "")) in id_to_idx
            ]

            if not valid_candidates:
                result = {
                    "query_id": query_id,
                    "model": service.model_name,
                    "job_text_mode": job_text_mode,
                    "encode_time_ms": 0,
                    "candidates": [],
                }
                fh.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
                query_count += 1
                continue

            t0 = time.perf_counter()
            query_vec = np.asarray(service.encode_text(query_text), dtype=np.float32)
            encode_ms = (time.perf_counter() - t0) * 1000
            total_encode_ms += encode_ms

            candidate_indices = np.asarray(
                [id_to_idx[str(c.get("job_id"))] for c in valid_candidates],
                dtype=np.int64,
            )
            cand_vecs = job_embeddings[candidate_indices]

            query_norm = np.linalg.norm(query_vec)
            if query_norm == 0:
                similarities = np.zeros(len(cand_vecs), dtype=np.float32)
            else:
                query_vec_normed = query_vec / query_norm
                cand_norms = np.linalg.norm(cand_vecs, axis=1, keepdims=True)
                cand_norms[cand_norms == 0] = 1.0
                cand_vecs_normed = cand_vecs / cand_norms
                similarities = cand_vecs_normed @ query_vec_normed

            sorted_order = np.argsort(-similarities)

            ranked: List[Dict[str, Any]] = []
            for rank, pos in enumerate(sorted_order, start=1):
                idx = int(pos)
                ranked.append({
                    "job_id": str(valid_candidates[idx].get("job_id")),
                    "bm25_score": valid_candidates[idx].get("bm25_score"),
                    "bm25_rank": valid_candidates[idx].get("bm25_rank"),
                    "semantic_score": round(float(similarities[idx]), 6),
                    "semantic_rank": rank,
                })

            result = {
                "query_id": query_id,
                "model": service.model_name,
                "job_text_mode": job_text_mode,
                "encode_time_ms": round(encode_ms, 2),
                "candidates": ranked,
            }
            fh.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n")
            query_count += 1
            candidate_count += len(ranked)

    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    avg_encode_ms = total_encode_ms / query_count if query_count else 0.0
    print(f"[在线] 完成 {query_count} 条查询, {candidate_count} 个候选")
    print(f"[在线] 平均编码耗时: {avg_encode_ms:.1f}ms/查询")
    print(f"[在线] 峰值内存: {peak_memory / 1024 / 1024:.1f}MB")

    return output_path, avg_encode_ms, peak_memory


# ══════════════════════════════════════════════════════════════════
# 命令行入口
# ══════════════════════════════════════════════════════════════════


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="工作流 2 — BGE-M3 语义重排对照组")
    parser.add_argument("--jobs", type=Path, default=DEFAULT_JOBS)
    parser.add_argument("--bm25", type=Path, default=DEFAULT_BM25)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--model", default=DEFAULT_MODEL, help="BGE 模型名称")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda", "mps"])
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument(
        "--job-text-mode",
        default="title+duty+requirements+skills",
        choices=sorted(JOB_TEXT_MODES),
    )
    parser.add_argument("--skip-encode", action="store_true")
    parser.add_argument("--force-encode", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-jobs", type=int, default=0, help="限制编码的岗位数量（0=全部）")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.skip_encode and not args.jobs.exists():
        raise FileNotFoundError(f"岗位文件不存在: {args.jobs}")
    if not args.bm25.exists():
        raise FileNotFoundError(f"BM25 候选集不存在: {args.bm25}")

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[初始化] 加载 BGE-M3 模型: {args.model}")
    t0_load = time.perf_counter()
    service = SemanticEmbeddingService(
        model_name=args.model,
        device=args.device,
        batch_size=args.batch_size,
    )
    load_time = time.perf_counter() - t0_load
    print(f"[初始化] 模型加载耗时: {load_time:.1f}s")
    print(f"[初始化] 模型状态: {service.model_status}")

    # ── 离线阶段 ──────────────────────────────────────────────────
    encode_time = 0.0
    if args.skip_encode:
        emb_path = out_dir / "jobs_embeddings.npy"
        ids_path = out_dir / "jobs_embedding_ids.json"
        if not emb_path.exists() or not ids_path.exists():
            raise FileNotFoundError(f"缓存不存在: {emb_path} / {ids_path}")
        print(f"[离线] 跳过编码，加载缓存")
        job_embeddings = np.load(emb_path)
        job_ids = json.loads(ids_path.read_text(encoding="utf-8"))
    else:
        job_embeddings, job_ids, encode_time = encode_jobs_offline(
            jobs_path=args.jobs,
            out_dir=out_dir,
            service=service,
            job_text_mode=args.job_text_mode,
            force=args.force_encode,
            max_jobs=args.max_jobs,
        )

    # ── 在线阶段 ──────────────────────────────────────────────────
    output_path, avg_encode_ms, peak_memory = rerank_with_bm25_candidates(
        bm25_path=args.bm25,
        job_embeddings=job_embeddings,
        job_ids=job_ids,
        out_dir=out_dir,
        service=service,
        job_text_mode=args.job_text_mode,
        limit=args.limit,
    )

    # ── 元数据 ────────────────────────────────────────────────────
    metadata = {
        "workflow": "workflow_2_bge_m3_semantic_rerank",
        "model": {
            "model_name": service.model_name,
            "model_family": service.model_family,
            "model_status": service.model_status,
            "device": service.device,
            "batch_size": service.batch_size,
        },
        "job_text_mode": args.job_text_mode,
        "load_time_sec": round(load_time, 1),
        "encode_time_sec": round(encode_time, 1),
        "avg_query_encode_ms": round(avg_encode_ms, 2),
        "peak_memory_mb": round(peak_memory / 1024 / 1024, 1),
        "num_jobs_encoded": len(job_ids),
        "embedding_dim": int(job_embeddings.shape[1]),
        "jobs_input": str(args.jobs),
        "bm25_input": str(args.bm25),
        "output": str(output_path),
    }
    write_json(out_dir / "run_metadata.json", metadata)

    print("\n" + "=" * 60)
    print("工作流 2 — BGE-M3 语义重排（对照组）完成")
    print("=" * 60)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
