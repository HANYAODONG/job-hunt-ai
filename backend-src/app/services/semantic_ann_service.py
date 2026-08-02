import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..core.config import settings
from .nlp_service import NLPService

logger = logging.getLogger(__name__)


class SemanticANNService:
    """Wrapper around a prebuilt HNSW/FAISS index (optional fallback to disabled state)."""

    def __init__(self):
        self.enabled = False
        self.index = None
        self.embeddings: Optional[np.ndarray] = None
        self.normalized_embeddings: Optional[np.ndarray] = None
        self.job_ids: List[str] = []
        self.dimension: Optional[int] = None
        self.nlp_service = NLPService()

        self._load_index()

    def _load_index(self):
        index_path = self._resolve_path(settings.SEMANTIC_INDEX_PATH)
        ids_path = self._resolve_path(settings.SEMANTIC_INDEX_IDS)

        if not index_path or not ids_path:
            logger.info("Semantic ANN index paths not configured; semantic source disabled.")
            return

        try:
            ids = json.loads(Path(ids_path).read_text())
            embeddings = np.load(index_path)
            if embeddings.shape[0] != len(ids):
                raise ValueError("Embedding count does not match job id count.")
            self.dimension = embeddings.shape[1]
            self.embeddings = embeddings
            self.normalized_embeddings = self._normalize(embeddings)
            self.job_ids = ids

            try:
                import hnswlib

                index = hnswlib.Index(space="cosine", dim=self.dimension)
                index.init_index(max_elements=len(ids), ef_construction=200, M=16)
                index.add_items(embeddings, list(range(len(ids))))
                self.index = index
                logger.info("Semantic ANN index loaded with %s items via hnswlib.", len(ids))
            except ModuleNotFoundError:
                logger.warning("hnswlib not installed; falling back to brute-force semantic search.")

            self.enabled = True
        except Exception as exc:
            logger.error("Failed to load semantic ANN index: %s", exc)

    def is_available(self) -> bool:
        return self.enabled and (self.index is not None or self.normalized_embeddings is not None)

    def query(self, query_text: str, top_k: int = 100) -> List[Tuple[str, float]]:
        if not self.is_available():
            return []
        try:
            embedding_list = self.nlp_service.get_sentence_embeddings([query_text])
            if not embedding_list:
                return []
            embedding = np.asarray(embedding_list[0], dtype=np.float32)
            if self.index is not None:
                labels, distances = self.index.knn_query(embedding, k=min(top_k, len(self.job_ids)))
                hits = []
                for idx, dist in zip(labels[0], distances[0]):
                    job_id = self.job_ids[idx]
                    score = 1 - dist  # cosine distance -> similarity
                    hits.append((job_id, float(score)))
                return hits

            if self.normalized_embeddings is None:
                return []

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

    def rank_candidate_ids(self, query_text: str, candidate_ids: List[str]) -> List[Dict[str, Any]]:
        if not self.is_available() or self.normalized_embeddings is None:
            return []

        query_embedding_list = self.nlp_service.get_sentence_embeddings([query_text])
        if not query_embedding_list:
            return []

        query_embedding = np.asarray(query_embedding_list[0], dtype=np.float32)
        query_norm = np.linalg.norm(query_embedding)
        if query_norm == 0:
            return []

        normalized_query = query_embedding / query_norm
        id_to_index = {job_id: index for index, job_id in enumerate(self.job_ids)}
        seen: set[str] = set()
        candidate_rows: List[Tuple[str, int]] = []
        for job_id in candidate_ids:
            if job_id in seen:
                continue
            seen.add(job_id)
            index = id_to_index.get(job_id)
            if index is not None:
                candidate_rows.append((job_id, index))

        if not candidate_rows:
            return []

        candidate_vectors = self.normalized_embeddings[[index for _, index in candidate_rows]]
        scores = candidate_vectors @ normalized_query
        order = np.argsort(-scores)

        ranked: List[Dict[str, Any]] = []
        for rank, position in enumerate(order, start=1):
            job_id, _ = candidate_rows[int(position)]
            ranked.append(
                {
                    "job_id": job_id,
                    "semantic_score": float(scores[int(position)]),
                    "semantic_rank": rank,
                }
            )
        return ranked

    def rank_candidate_texts(self, query_text: str, candidate_texts: Dict[str, str]) -> List[Dict[str, Any]]:
        if not candidate_texts:
            return []

        texts = [query_text] + list(candidate_texts.values())
        embeddings = self.nlp_service.get_sentence_embeddings(texts)
        if len(embeddings) != len(texts):
            return []

        query_embedding = np.asarray(embeddings[0], dtype=np.float32)
        candidate_matrix = np.asarray(embeddings[1:], dtype=np.float32)

        query_norm = np.linalg.norm(query_embedding)
        if query_norm == 0:
            return []

        candidate_norms = np.linalg.norm(candidate_matrix, axis=1, keepdims=True)
        candidate_norms[candidate_norms == 0] = 1.0

        normalized_query = query_embedding / query_norm
        normalized_candidates = candidate_matrix / candidate_norms
        scores = normalized_candidates @ normalized_query
        order = np.argsort(-scores)

        ranked: List[Dict[str, Any]] = []
        candidate_ids = list(candidate_texts.keys())
        for rank, position in enumerate(order, start=1):
            ranked.append(
                {
                    "job_id": candidate_ids[int(position)],
                    "semantic_score": float(scores[int(position)]),
                    "semantic_rank": rank,
                }
            )
        return ranked

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
        # Resolve relative paths against repository root (two levels up from backend/app)
        repo_root = Path(__file__).resolve().parents[3]
        return repo_root / path
