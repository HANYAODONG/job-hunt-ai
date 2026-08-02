import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..core.config import settings

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - optional dependency
    SentenceTransformer = None

logger = logging.getLogger(__name__)


class SemanticEmbeddingService:
    """BGE-M3-based embedding wrapper with a deterministic fallback implementation."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        batch_size: Optional[int] = None,
        normalize_embeddings: Optional[bool] = None,
        trust_remote_code: Optional[bool] = None,
    ):
        self.model_name = model_name or settings.SEMANTIC_EMBEDDING_MODEL
        self.device = device or settings.SEMANTIC_EMBEDDING_DEVICE
        self.model_family = "bge-m3"
        self.batch_size = batch_size or settings.SEMANTIC_EMBEDDING_BATCH_SIZE
        self.normalize_embeddings = (
            normalize_embeddings
            if normalize_embeddings is not None
            else settings.SEMANTIC_EMBEDDING_NORMALIZE
        )
        self.trust_remote_code = (
            trust_remote_code
            if trust_remote_code is not None
            else settings.SEMANTIC_EMBEDDING_TRUST_REMOTE_CODE
        )

        self.model = None
        self.model_loaded = False
        self.model_status = "fallback"
        self._load_model()

    def _load_model(self) -> None:
        if SentenceTransformer is None:
            logger.warning("sentence-transformers is not installed; using deterministic fallback embeddings.")
            return

        try:
            self.model = SentenceTransformer(
                self.model_name,
                device=self.device,
                trust_remote_code=self.trust_remote_code,
            )
            self.model_loaded = True
            self.model_status = "loaded"
            logger.info("Loaded BGE-M3 semantic embedding model: %s", self.model_name)
        except Exception as exc:  # pragma: no cover - optional dependency
            logger.warning(
                "Failed to load semantic embedding model '%s': %s; using fallback embeddings.",
                self.model_name,
                exc,
            )
            self.model = None
            self.model_loaded = False
            self.model_status = "fallback"

    def _normalize_text(self, text: str) -> str:
        return " ".join(str(text).strip().split())

    def encode_texts(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []

        cleaned_texts = [self._normalize_text(text) for text in texts]
        if self.model is not None:
            try:
                embeddings = self.model.encode(
                    cleaned_texts,
                    convert_to_numpy=True,
                    normalize_embeddings=self.normalize_embeddings,
                    batch_size=self.batch_size,
                )
                return np.asarray(embeddings, dtype=np.float32).tolist()
            except Exception as exc:  # pragma: no cover - optional dependency
                logger.warning("Embedding encode failed with model '%s': %s; falling back.", self.model_name, exc)

        return [self._fallback_embedding(text) for text in cleaned_texts]

    def encode_text(self, text: str) -> List[float]:
        return self.encode_texts([text])[0] if text else []

    def compute_similarity(self, text1: str, text2: str) -> float:
        if not text1 or not text2:
            return 0.0

        embeddings = self.encode_texts([text1, text2])
        if not embeddings or len(embeddings) < 2:
            return 0.0

        return float(
            self._cosine_similarity(
                np.asarray(embeddings[0], dtype=np.float32),
                np.asarray(embeddings[1], dtype=np.float32),
            )
        )

    def rerank_candidates(
        self,
        query_text: str,
        candidate_texts: Sequence[str],
        candidate_ids: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        if not query_text:
            return []

        candidate_ids = list(candidate_ids or [f"candidate_{idx}" for idx in range(len(candidate_texts))])
        query_embedding = np.asarray(self.encode_text(query_text), dtype=np.float32)
        embeddings = np.asarray(self.encode_texts(list(candidate_texts)), dtype=np.float32)

        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)

        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)

        query_vector = query_embedding[0]
        similarities = []

        for idx, candidate_id in enumerate(candidate_ids):
            if idx >= len(embeddings):
                score = 0.0
            else:
                score = float(self._cosine_similarity(query_vector, embeddings[idx]))

            similarities.append({
                "job_id": candidate_id,
                "semantic_score": round(score, 6),
                "semantic_rank": 0,
            })

        similarities.sort(key=lambda item: item["semantic_score"], reverse=True)
        for index, item in enumerate(similarities, start=1):
            item["semantic_rank"] = index

        return similarities

    def compare_models(self, sample_pairs: Sequence[Tuple[str, str]]) -> Dict[str, Any]:
        results = []
        for left, right in sample_pairs:
            results.append({
                "left": left,
                "right": right,
                "similarity": self.compute_similarity(left, right),
                "model": self.model_name,
                "mode": self.model_status,
            })
        return {
            "model": self.model_name,
            "model_family": self.model_family,
            "mode": self.model_status,
            "results": results,
        }

    def _fallback_embedding(self, text: str) -> List[float]:
        tokens = [token for token in re.split(r"[^\u4e00-\u9fffA-Za-z0-9]+", text.lower()) if token]
        vector = np.zeros(64, dtype=np.float32)
        if not tokens:
            return vector.tolist()

        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            idx = int(digest[:8], 16) % len(vector)
            vector[idx] += 1.0

        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        return vector.tolist()

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        dot_product = float(np.dot(vec1, vec2))
        norm1 = float(np.linalg.norm(vec1))
        norm2 = float(np.linalg.norm(vec2))
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        return dot_product / (norm1 * norm2)

    def save_embeddings(self, embeddings: np.ndarray, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(output_path, embeddings)

    def save_embedding_ids(self, embedding_ids: Sequence[str], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(list(embedding_ids), ensure_ascii=False, indent=2), encoding="utf-8")