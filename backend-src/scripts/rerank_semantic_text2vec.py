"""
工作流 2 — text2vec 轻量语义重排脚本

流水线：
    1. 离线阶段：读取 jobs.jsonl → 构建岗位文本 → text2vec 编码 → 缓存向量 + ID 映射
    2. 在线阶段：读取 BM25 Top200 候选集 → 编码简历 → 仅对 Top200 候选计算余弦相似度 → 排序输出

用法：
    # 三阶段完整运行（离线编码 + 在线重排 + 评测）
    python backend-src/scripts/rerank_semantic_text2vec.py

    # 仅重排（假设向量缓存已存在）
    python backend-src/scripts/rerank_semantic_text2vec.py --skip-encode

    # 指定岗位文本拼接方式和模型
    python backend-src/scripts/rerank_semantic_text2vec.py \
        --job-text-mode title+duty+requirements+skills \
        --model shibing624/text2vec-base-chinese

输出：
    artifacts/semantic_text2vec/
        jobs_embeddings.npy          # 岗位向量缓存
        jobs_embedding_ids.json      # 岗位 ID 映射
        semantic_rerank_top200.jsonl # 重排结果（符合工作流 2 契约）
        run_metadata.json            # 实验配置与资源占用
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

# ── 路径解析 ──────────────────────────────────────────────────────

_SCRIPT_DIR = Path(__file__).resolve()
BACKEND_ROOT = _SCRIPT_DIR.parents[1]
# 智能检测仓库根目录：Docker 中 backend-src 即根，本地则为上级目录
_REPO_ROOT = BACKEND_ROOT.parent
if not (_REPO_ROOT / "artifacts").exists() and (BACKEND_ROOT / "artifacts").exists():
    _REPO_ROOT = BACKEND_ROOT
REPO_ROOT = _REPO_ROOT
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.text2vec_embedding_service import Text2VecEmbeddingService

# ── 默认路径 ──────────────────────────────────────────────────────

DEFAULT_JOBS = REPO_ROOT / "artifacts" / "dataset_iteration_05" / "jobs.jsonl"
DEFAULT_BM25 = REPO_ROOT / "artifacts" / "bm25" / "bm25_top200.jsonl"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "semantic_text2vec"
DEFAULT_MODEL = "shibing624/text2vec-base-chinese-sentence"


# ══════════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════════

def read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    """逐行读取 JSONL 文件。"""
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
    """一次性读取全部 JSONL 记录。"""
    return list(read_jsonl(path))


def write_jsonl(path: Path, records: Iterable[Dict[str, Any]]) -> None:
    """写入 JSONL 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")))
            fh.write("\n")


def write_json(path: Path, payload: Any) -> None:
    """写入 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_strings(values: Iterable[Any]) -> List[str]:
    """去重并保持顺序。"""
    seen: set[str] = set()
    ordered: List[str] = []
    for v in values:
        item = str(v).strip()
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered


# ══════════════════════════════════════════════════════════════════
# 岗位文本构建（3 种模式）
# ══════════════════════════════════════════════════════════════════

JOB_TEXT_MODES = {
    "title_only",
    "title+requirements",
    "title+duty+requirements+skills",
}


def build_job_text(job: Dict[str, Any], mode: str) -> str:
    """按指定模式拼接岗位文本。

    mode:
        - title_only: 仅岗位标题
        - title+requirements: 标题 + 岗位要求
        - title+duty+requirements+skills: 标题 + 职责 + 要求 + 技能（默认）
    """
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

    # 如果没有独立的 responsibilities/requirements，使用 description
    if not responsibilities and not requirements and description:
        responsibilities = description

    if mode == "title_only":
        return title
    elif mode == "title+requirements":
        parts = [title, requirements or description or detailed]
        return " ".join(p for p in parts if p)
    else:  # title+duty+requirements+skills
        parts = [
            title,
            responsibilities,
            requirements,
            detailed,
            skills_text,
        ]
        return " ".join(p for p in parts if p)


def build_query_text(profile: Dict[str, Any]) -> str:
    """从标准简历构建查询文本。

    与工作流 5 的 build_query_text 逻辑一致：
    目标岗位族 + 核心技能 + 工作年限 + 专业 + 关键项目词
    """
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

    # 从 experience 提取角色
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
    service: Text2VecEmbeddingService,
    job_text_mode: str,
    force: bool = False,
    max_jobs: int = 0,
) -> Tuple[np.ndarray, List[str], float]:
    """离线阶段：编码全部岗位向量并缓存。max_jobs=0 表示全部。"""
    emb_path = out_dir / "jobs_embeddings.npy"
    ids_path = out_dir / "jobs_embedding_ids.json"

    # 如果缓存已存在且未强制重生成，先校验维度再加载
    if not force and emb_path.exists() and ids_path.exists():
        cached = service.load_embeddings(emb_path)
        job_ids = service.load_embedding_ids(ids_path)
        test_vec = np.asarray(service.encode_text("测试"), dtype=np.float32)
        if cached.shape[1] == test_vec.shape[0]:
            # 即使有缓存，如果 max_jobs 限制且缓存更多，截取
            if max_jobs > 0 and len(job_ids) > max_jobs:
                print(f"[离线] 缓存有 {len(job_ids)} 条，截取前 {max_jobs} 条")
                return cached[:max_jobs], job_ids[:max_jobs], 0.0
            print(f"[离线] 岗位向量缓存已存在且维度匹配 ({cached.shape[1]}d), 跳过编码: {emb_path}")
            return cached, job_ids, 0.0
        else:
            print(f"[离线] 缓存维度 ({cached.shape[1]}d) 与当前模型 ({test_vec.shape[0]}d) 不匹配, 重新编码")

    print(f"[离线] 读取岗位数据: {jobs_path}")
    jobs = read_jsonl_all(jobs_path)

    # 限制岗位数量
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

    # 缓存
    service.save_embeddings(job_embeddings, emb_path)
    service.save_embedding_ids(job_ids, ids_path)

    return job_embeddings, job_ids, elapsed


def rerank_with_bm25_candidates(
    bm25_path: Path,
    job_embeddings: np.ndarray,
    job_ids: List[str],
    out_dir: Path,
    service: Text2VecEmbeddingService,
    job_text_mode: str,
    limit: Optional[int] = None,
) -> Tuple[str, float]:
    """在线阶段：读取 BM25 Top200，对每份简历做语义重排。"""
    print(f"[在线] 读取 BM25 候选集: {bm25_path}")
    bm25_records = read_jsonl_all(bm25_path)
    print(f"[在线] 共 {len(bm25_records)} 条查询")

    if limit:
        bm25_records = bm25_records[:limit]

    # 建立 job_id → 向量索引 的映射
    id_to_idx: Dict[str, int] = {jid: idx for idx, jid in enumerate(job_ids)}

    output_path = out_dir / "semantic_rerank_top200.jsonl"
    query_count = 0
    candidate_count = 0
    total_encode_ms = 0.0

    # 启动内存追踪
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
                raise ValueError(f"BM25 记录缺少 query_id: {record}")

            query_text = str(record.get("query_text") or "").strip()
            bm25_candidates = record.get("candidates", [])

            # 过滤出有对应向量的候选岗位
            valid_candidates: List[Dict[str, Any]] = []
            valid_texts: List[str] = []
            for cand in bm25_candidates:
                jid = str(cand.get("job_id") or "")
                if jid in id_to_idx:
                    valid_candidates.append(cand)
                    valid_texts.append("")  # 占位，不需要岗位文本

            if not valid_candidates:
                # 全部候选都不在向量库中
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

            # 只编码简历文本（不需要重新编码岗位，直接查缓存矩阵）
            t0 = time.perf_counter()
            query_vec = np.asarray(service.encode_text(query_text), dtype=np.float32)
            encode_ms = (time.perf_counter() - t0) * 1000
            total_encode_ms += encode_ms

            # 批量取出候选岗位向量并计算余弦相似度
            candidate_indices = np.asarray(
                [id_to_idx[str(c.get("job_id"))] for c in valid_candidates],
                dtype=np.int64,
            )
            cand_vecs = job_embeddings[candidate_indices]

            # 归一化后点积 = 余弦相似度
            query_norm = np.linalg.norm(query_vec)
            if query_norm == 0:
                similarities = np.zeros(len(cand_vecs), dtype=np.float32)
            else:
                query_vec_normed = query_vec / query_norm
                cand_norms = np.linalg.norm(cand_vecs, axis=1, keepdims=True)
                cand_norms[cand_norms == 0] = 1.0
                cand_vecs_normed = cand_vecs / cand_norms
                similarities = cand_vecs_normed @ query_vec_normed

            # 排序
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

    # 内存追踪
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
    parser = argparse.ArgumentParser(
        description="工作流 2 — text2vec 轻量语义重排",
    )
    parser.add_argument(
        "--jobs",
        type=Path,
        default=DEFAULT_JOBS,
        help="标准岗位 JSONL 路径（工作流 1 输出）",
    )
    parser.add_argument(
        "--bm25",
        type=Path,
        default=DEFAULT_BM25,
        help="BM25 Top200 候选集 JSONL 路径（工作流 5 输出）",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="输出目录",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="text2vec 模型名称（默认: shibing624/text2vec-base-chinese）",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "cuda", "mps"],
        help="推理设备",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="编码批大小",
    )
    parser.add_argument(
        "--job-text-mode",
        default="title+duty+requirements+skills",
        choices=sorted(JOB_TEXT_MODES),
        help="岗位文本拼接方式",
    )
    parser.add_argument(
        "--max-seq-length",
        type=int,
        default=256,
        help="模型最大输入长度",
    )
    parser.add_argument(
        "--skip-encode",
        action="store_true",
        help="跳过离线编码阶段（使用已有缓存）",
    )
    parser.add_argument(
        "--force-encode",
        action="store_true",
        help="强制重新编码岗位向量（覆盖缓存）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="限制处理的简历数量（用于快速测试）",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=0,
        help="限制编码的岗位数量（0=全部，测试建议 500）",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="不缓存岗位向量（每次重新编码）",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # 校验输入
    if not args.skip_encode and not args.jobs.exists():
        raise FileNotFoundError(f"岗位文件不存在: {args.jobs}")
    if not args.bm25.exists():
        raise FileNotFoundError(f"BM25 候选集不存在: {args.bm25}")

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── 初始化服务 ────────────────────────────────────────────────
    print(f"[初始化] 加载 text2vec 模型: {args.model}")
    t0_load = time.perf_counter()
    service = Text2VecEmbeddingService(
        model_name=args.model,
        device=args.device,
        batch_size=args.batch_size,
        max_seq_length=args.max_seq_length,
    )
    load_time = time.perf_counter() - t0_load
    model_info = service.get_model_info()
    print(f"[初始化] 模型加载耗时: {load_time:.1f}s")
    print(f"[初始化] 模型信息: {json.dumps(model_info, ensure_ascii=False)}")

    # ── 离线阶段：岗位向量编码 ────────────────────────────────────
    encode_time = 0.0
    if args.skip_encode:
        emb_path = out_dir / "jobs_embeddings.npy"
        ids_path = out_dir / "jobs_embedding_ids.json"
        if not emb_path.exists() or not ids_path.exists():
            raise FileNotFoundError(
                f"缓存不存在，不能 --skip-encode: {emb_path} / {ids_path}"
            )
        print(f"[离线] 跳过编码，加载缓存")
        job_embeddings = service.load_embeddings(emb_path)
        job_ids = service.load_embedding_ids(ids_path)
    else:
        job_embeddings, job_ids, encode_time = encode_jobs_offline(
            jobs_path=args.jobs,
            out_dir=out_dir,
            service=service,
            job_text_mode=args.job_text_mode,
            force=args.force_encode,
            max_jobs=args.max_jobs,
        )

    # ── 在线阶段：BM25 Top200 语义重排 ─────────────────────────────
    output_path, avg_encode_ms, peak_memory = rerank_with_bm25_candidates(
        bm25_path=args.bm25,
        job_embeddings=job_embeddings,
        job_ids=job_ids,
        out_dir=out_dir,
        service=service,
        job_text_mode=args.job_text_mode,
        limit=args.limit,
    )

    # ── 写入实验元数据 ─────────────────────────────────────────────
    metadata = {
        "workflow": "workflow_2_text2vec_semantic_rerank",
        "model": model_info,
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

    # ── 输出摘要 ──────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("工作流 2 — text2vec 语义重排 完成")
    print("=" * 60)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
