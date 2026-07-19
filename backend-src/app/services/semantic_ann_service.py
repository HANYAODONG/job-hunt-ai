import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..core.config import settings
from .nlp_service import NLPService

logger = logging.getLogger(__name__)


class SemanticANNService:
    """Load precomputed semantic embeddings and rerank candidate jobs."""

    def __init__(self):
        self.enabled = False
        self.index = None
        self.embeddings: Optional[np.ndarray] = None
        self.normalized_embeddings: Optional[np.ndarray] = None
        self.job_ids: List[str] = []
        self.dimension: Optional[int] = None
        self.job_id_to_index: Dict[str, int] = {}
        self.nlp_service = NLPService()

        self._load_index()

    def _load_index(self):
        index_path = self._resolve_path(settings.SEMANTIC_INDEX_PATH)
        ids_path = self._resolve_path(settings.SEMANTIC_INDEX_IDS)

        if not index_path or not ids_path:
            logger.info("Semantic ANN index paths not configured; semantic source disabled.")
            return

        try:
            ids = json.loads(Path(ids_path).read_text(encoding="utf-8"))
            embeddings = np.load(index_path)
            if embeddings.shape[0] != len(ids):
                raise ValueError("Embedding count does not match job id count.")

            self.dimension = embeddings.shape[1]
            self.embeddings = embeddings.astype(np.float32)
            self.normalized_embeddings = self._normalize(self.embeddings)
            self.job_ids = list(ids)
            self.job_id_to_index = {job_id: idx for idx, job_id in enumerate(self.job_ids)}

            self.enabled = True
            logger.info("Semantic ANN index loaded with %s items.", len(self.job_ids))
        except Exception as exc:
            logger.error("Failed to load semantic ANN index: %s", exc)

    def is_available(self) -> bool:
        return self.enabled and self.normalized_embeddings is not None

    def query(self, query_text: str, top_k: int = 100) -> List[Tuple[str, float]]:
        if not self.is_available():
            return []

        try:
            embedding_list = self.nlp_service.get_sentence_embeddings([query_text])
            if not embedding_list:
                return []

            embedding = np.asarray(embedding_list[0], dtype=np.float32)
            norm = np.linalg.norm(embedding)
            if norm == 0:
                return []

            normalized_query = embedding / norm
            sims = self.normalized_embeddings @ normalized_query
            top_indices = np.argsort(-sims)[: min(top_k, len(self.job_ids))]
            return [(self.job_ids[idx], float(sims[idx])) for idx in top_indices]
        except Exception as exc:
            logger.error("Semantic ANN query failed: %s", exc)
            return []

    def rerank_candidates(
        self,
        query_text: str,
        candidate_job_ids: Sequence[str],
    ) -> List[Dict[str, Any]]:
        if not self.is_available() or not candidate_job_ids:
            return []

        try:
            embedding_list = self.nlp_service.get_sentence_embeddings([query_text])
            if not embedding_list:
                return []

            embedding = np.asarray(embedding_list[0], dtype=np.float32)
            norm = np.linalg.norm(embedding)
            if norm == 0:
                return []

            normalized_query = embedding / norm

            valid_ids = []
            valid_indices = []

            for job_id in candidate_job_ids:
                idx = self.job_id_to_index.get(job_id)
                if idx is not None:
                    valid_ids.append(job_id)
                    valid_indices.append(idx)

            if not valid_indices:
                return []

            candidate_vectors = self.normalized_embeddings[np.asarray(valid_indices, dtype=int)]
            sims = candidate_vectors @ normalized_query

            ranked = sorted(
                zip(valid_ids, sims.tolist()),
                key=lambda item: item[1],
                reverse=True,
            )

            return [
                {
                    "job_id": job_id,
                    "semantic_score": round(float(score), 6),
                    "semantic_rank": idx + 1,
                }
                for idx, (job_id, score) in enumerate(ranked)
            ]
        except Exception as exc:
            logger.error("Semantic rerank failed: %s", exc)
            return []

    def _normalize(self, matrix: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms

    def _resolve_path(self, path_str: Optional[str]) -> Optional[Path]:
        if not path_str:
            return None
        path = Path(path_str)
        if path.is_absolute():
            return path
        repo_root = Path(__file__).resolve().parents[3]
        return repo_root / path