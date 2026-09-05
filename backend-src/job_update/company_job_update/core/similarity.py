from __future__ import annotations

import math
import re
from difflib import SequenceMatcher
from typing import Protocol, Sequence


class SimilarityBackend(Protocol):
    def score(self, query: str, candidates: Sequence[str]) -> list[float]:
        ...


class Text2VecSimilarity:
    """Adapter for shibing624/text2vec SentenceModel.

    Example:
        backend = Text2VecSimilarity("shibing624/text2vec-base-chinese")
    """

    def __init__(self, model_name_or_path: str = "shibing624/text2vec-base-chinese") -> None:
        try:
            from text2vec import SentenceModel
        except ImportError as exc:
            raise ImportError(
                "text2vec is required for job routing. Install it with `pip install text2vec`."
            ) from exc
        self.model = SentenceModel(model_name_or_path)

    def score(self, query: str, candidates: Sequence[str]) -> list[float]:
        if not candidates:
            return []
        texts = [query, *candidates]
        embeddings = self.model.encode(texts)
        query_vec = embeddings[0]
        return [self._cosine(query_vec, candidate_vec) for candidate_vec in embeddings[1:]]

    @staticmethod
    def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
        dot = sum(float(a) * float(b) for a, b in zip(left, right))
        left_norm = math.sqrt(sum(float(value) * float(value) for value in left))
        right_norm = math.sqrt(sum(float(value) * float(value) for value in right))
        if not left_norm or not right_norm:
            return 0.0
        return dot / (left_norm * right_norm)


class LexicalSimilarity:
    """Deterministic offline fallback for title routing."""

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value or "").lower())

    @staticmethod
    def _bigrams(value: str) -> set[str]:
        if len(value) < 2:
            return {value} if value else set()
        return {value[index:index + 2] for index in range(len(value) - 1)}

    def score(self, query: str, candidates: Sequence[str]) -> list[float]:
        normalized_query = self._normalize(query)
        query_bigrams = self._bigrams(normalized_query)
        scores: list[float] = []
        for candidate in candidates:
            normalized_candidate = self._normalize(candidate)
            if not normalized_query or not normalized_candidate:
                scores.append(0.0)
                continue
            if normalized_query == normalized_candidate:
                scores.append(1.0)
                continue

            candidate_bigrams = self._bigrams(normalized_candidate)
            union = query_bigrams | candidate_bigrams
            jaccard = len(query_bigrams & candidate_bigrams) / len(union) if union else 0.0
            sequence = SequenceMatcher(None, normalized_query, normalized_candidate).ratio()
            contained = min(len(normalized_query), len(normalized_candidate)) / max(
                len(normalized_query), len(normalized_candidate)
            ) if normalized_query in normalized_candidate or normalized_candidate in normalized_query else 0.0
            scores.append(min(1.0, max(jaccard, sequence * 0.86, contained * 0.95)))
        return scores
