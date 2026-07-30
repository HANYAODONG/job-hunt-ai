"""
Text2Vec 轻量语义嵌入服务 — 工作流 2

基于 shibing624/text2vec-base-chinese 的中文人岗语义匹配。
比 BGE-M3 更轻量（~400MB vs ~2.2GB），CPU 友好，适合本地开发 baseline。

使用方式：
    service = Text2VecEmbeddingService()
    embeddings = service.encode_texts(["Python 后端工程师", "机器学习研究员"])
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None


# ── 默认模型配置（不依赖 config.py，避免修改现有文件） ─────────────

DEFAULT_TEXT2VEC_MODEL = "shibing624/text2vec-base-chinese-sentence"
DEFAULT_DEVICE = "cpu"
DEFAULT_BATCH_SIZE = 32
DEFAULT_NORMALIZE = True
DEFAULT_MAX_SEQ_LENGTH = 256


class Text2VecEmbeddingService:
    """text2vec-base-chinese 嵌入封装，接口与 SemanticEmbeddingService 兼容。"""

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        batch_size: Optional[int] = None,
        normalize_embeddings: Optional[bool] = None,
        max_seq_length: Optional[int] = None,
    ):
        self.model_name = model_name or DEFAULT_TEXT2VEC_MODEL
        self.device = device or DEFAULT_DEVICE
        self.model_family = "text2vec"
        self.batch_size = batch_size or DEFAULT_BATCH_SIZE
        self.normalize_embeddings = (
            normalize_embeddings if normalize_embeddings is not None else DEFAULT_NORMALIZE
        )
        self.max_seq_length = max_seq_length or DEFAULT_MAX_SEQ_LENGTH

        self.model: Optional[SentenceTransformer] = None
        self.model_loaded = False
        self.model_status = "fallback"
        self._load_model()

    # ── 模型加载 ──────────────────────────────────────────────────

    def _load_model(self) -> None:
        if SentenceTransformer is None:
            logger.warning(
                "sentence-transformers 未安装；使用确定性 fallback embedding。"
            )
            return

        try:
            self.model = SentenceTransformer(
                self.model_name,
                device=self.device,
                trust_remote_code=True,
            )
            if hasattr(self.model, "max_seq_length"):
                self.model.max_seq_length = self.max_seq_length
            self.model_loaded = True
            self.model_status = "loaded"
            logger.info(
                "已加载 text2vec 语义嵌入模型: %s (device=%s, max_len=%s)",
                self.model_name,
                self.device,
                self.max_seq_length,
            )
        except Exception as exc:
            logger.warning(
                "加载 text2vec 模型 '%s' 失败: %s；使用 fallback embedding。",
                self.model_name,
                exc,
            )
            self.model = None
            self.model_loaded = False
            self.model_status = "fallback"

    @property
    def model_size_mb(self) -> float:
        """估算模型文件大小（MB），用于资源占用报告。"""
        if self.model is None:
            return 0.0
        try:
            import os

            module_file = getattr(self.model, "_modules", {})
            total = 0
            for param in self.model.parameters():
                total += param.numel() * param.element_size()
            return round(total / (1024 * 1024), 1)
        except Exception:
            return 0.0

    # ── 文本预处理 ────────────────────────────────────────────────

    @staticmethod
    def _normalize_text(text: str) -> str:
        """压缩多余空白，保持中英文混合文本整洁。"""
        return " ".join(str(text).strip().split())

    # ── 编码 ──────────────────────────────────────────────────────

    def encode_texts(self, texts: Sequence[str]) -> List[List[float]]:
        """批量编码文本为向量。"""
        if not texts:
            return []

        cleaned = [self._normalize_text(t) for t in texts]

        if self.model is not None:
            try:
                embeddings = self.model.encode(
                    cleaned,
                    convert_to_numpy=True,
                    normalize_embeddings=self.normalize_embeddings,
                    batch_size=self.batch_size,
                    show_progress_bar=False,
                )
                return np.asarray(embeddings, dtype=np.float32).tolist()
            except Exception as exc:
                logger.warning(
                    "text2vec 编码失败 '%s': %s；降级到 fallback。",
                    self.model_name,
                    exc,
                )

        return [self._fallback_embedding(t) for t in cleaned]

    def encode_text(self, text: str) -> List[float]:
        """编码单个文本。"""
        results = self.encode_texts([text])
        return results[0] if results else []

    # ── 余弦相似度 ────────────────────────────────────────────────

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        dot = float(np.dot(vec1, vec2))
        n1 = float(np.linalg.norm(vec1))
        n2 = float(np.linalg.norm(vec2))
        if n1 == 0.0 or n2 == 0.0:
            return 0.0
        return dot / (n1 * n2)

    def compute_similarity(self, text1: str, text2: str) -> float:
        """计算两段文本的余弦相似度。"""
        if not text1 or not text2:
            return 0.0
        embs = self.encode_texts([text1, text2])
        if len(embs) < 2:
            return 0.0
        return float(
            self._cosine_similarity(
                np.asarray(embs[0], dtype=np.float32),
                np.asarray(embs[1], dtype=np.float32),
            )
        )

    # ── 候选重排 ──────────────────────────────────────────────────

    def rerank_candidates(
        self,
        query_text: str,
        candidate_texts: Sequence[str],
        candidate_ids: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        """对候选文本计算余弦相似度并排序。"""
        if not query_text:
            return []

        cid_list = list(candidate_ids or [f"c{idx}" for idx in range(len(candidate_texts))])
        query_vec = np.asarray(self.encode_text(query_text), dtype=np.float32)
        cand_vecs = np.asarray(self.encode_texts(list(candidate_texts)), dtype=np.float32)

        if cand_vecs.ndim == 1:
            cand_vecs = cand_vecs.reshape(1, -1)
        if query_vec.ndim == 1:
            query_vec = query_vec.reshape(1, -1)

        q = query_vec[0]
        items: List[Dict[str, Any]] = []
        for idx, cid in enumerate(cid_list):
            score = (
                float(self._cosine_similarity(q, cand_vecs[idx]))
                if idx < len(cand_vecs)
                else 0.0
            )
            items.append({
                "job_id": cid,
                "semantic_score": round(score, 6),
                "semantic_rank": 0,
            })

        items.sort(key=lambda x: x["semantic_score"], reverse=True)
        for rank, item in enumerate(items, start=1):
            item["semantic_rank"] = rank

        return items

    # ── Fallback embedding（确定性，不依赖模型） ────────────────────

    @staticmethod
    def _fallback_embedding(text: str, dim: int = 64) -> List[float]:
        """基于 MD5 哈希的确定性向量，保证无模型时仍可运行。"""
        tokens = [
            t for t in re.split(r"[^\u4e00-\u9fffA-Za-z0-9]+", text.lower()) if t
        ]
        vector = np.zeros(dim, dtype=np.float32)
        if not tokens:
            return vector.tolist()
        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            idx = int(digest[:8], 16) % dim
            vector[idx] += 1.0
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        return vector.tolist()

    # ── 持久化 ────────────────────────────────────────────────────

    def save_embeddings(self, embeddings: np.ndarray, output_path: Path) -> None:
        """保存向量到 .npy 文件。"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(output_path, embeddings)
        logger.info("已保存 %s 条向量 → %s", len(embeddings), output_path)

    def save_embedding_ids(self, ids: Sequence[str], output_path: Path) -> None:
        """保存 ID 列表到 JSON 文件。"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(list(ids), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("已保存 %s 个 ID → %s", len(ids), output_path)

    def load_embeddings(self, path: Path) -> np.ndarray:
        """从 .npy 文件加载向量。"""
        if not path.exists():
            raise FileNotFoundError(f"向量文件不存在: {path}")
        return np.load(path)

    def load_embedding_ids(self, path: Path) -> List[str]:
        """从 JSON 文件加载 ID 列表。"""
        if not path.exists():
            raise FileNotFoundError(f"ID 文件不存在: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    # ── 元信息 ────────────────────────────────────────────────────

    def get_model_info(self) -> Dict[str, Any]:
        """返回模型元信息，用于评测报告。"""
        return {
            "model_name": self.model_name,
            "model_family": self.model_family,
            "model_status": self.model_status,
            "device": self.device,
            "batch_size": self.batch_size,
            "normalize": self.normalize_embeddings,
            "max_seq_length": self.max_seq_length,
            "estimated_size_mb": self.model_size_mb,
        }
