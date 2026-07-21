from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...services.semantic_ann_service import SemanticANNService

logger = logging.getLogger(__name__)
router = APIRouter()

semantic_service = SemanticANNService()


class SemanticCandidateInput(BaseModel):
    job_id: str = Field(..., description="Candidate job id")
    title: Optional[str] = Field(default=None, description="Job title")
    description: Optional[str] = Field(default=None, description="Job description")
    required_skills: List[str] = Field(default_factory=list, description="Required skills")


class SemanticRankCandidate(BaseModel):
    job_id: str
    semantic_score: float
    semantic_rank: int


class SemanticRerankRequest(BaseModel):
    query_id: str
    query_text: str
    candidates: List[SemanticCandidateInput]


class SemanticRerankResponse(BaseModel):
    query_id: str
    candidates: List[SemanticRankCandidate]
    model_name: str
    source: str


def build_job_text(candidate: SemanticCandidateInput) -> str:
    return " ".join(
        [
            candidate.title or "",
            candidate.description or "",
            " ".join(candidate.required_skills or []),
        ]
    ).strip()


@router.post("/rerank", response_model=SemanticRerankResponse)
async def rerank_candidates(request: SemanticRerankRequest) -> SemanticRerankResponse:
    if not request.candidates:
        raise HTTPException(status_code=400, detail="candidates cannot be empty")

    candidate_texts = {}
    candidate_ids = []
    has_meaningful_text = False
    for item in request.candidates:
        candidate_ids.append(item.job_id)
        candidate_text = build_job_text(item)
        if candidate_text:
            has_meaningful_text = True
        candidate_texts[item.job_id] = candidate_text or item.job_id

    if has_meaningful_text:
        ranked = semantic_service.rank_candidate_texts(request.query_text, candidate_texts)
        source = "on_the_fly_embeddings"
    else:
        ranked = semantic_service.rank_candidate_ids(request.query_text, candidate_ids)
        source = "precomputed_index"

    if not ranked:
        raise HTTPException(
            status_code=503,
            detail="Semantic ranking is unavailable. Ensure sentence-transformers or fallback embeddings are available and, for id-only requests, semantic index files are configured.",
        )

    return SemanticRerankResponse(
        query_id=request.query_id,
        candidates=[SemanticRankCandidate(**item) for item in ranked],
        model_name=semantic_service.nlp_service.sentence_transformer_model,
        source=source,
    )