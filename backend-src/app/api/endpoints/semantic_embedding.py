import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...services.semantic_embedding_service import SemanticEmbeddingService

router = APIRouter()


class SemanticRerankRequest(BaseModel):
    query_id: str
    query_text: str
    candidate_job_ids: List[str] = Field(default_factory=list)
    candidate_texts: List[str] = Field(default_factory=list)


class SemanticRerankResponse(BaseModel):
    query_id: str
    candidates: List[Dict[str, Any]]


@router.post("/semantic-rerank", response_model=SemanticRerankResponse)
def semantic_rerank(request: SemanticRerankRequest) -> SemanticRerankResponse:
    if not request.candidate_job_ids and not request.candidate_texts:
        raise HTTPException(status_code=400, detail="candidate_job_ids or candidate_texts is required")

    service = SemanticEmbeddingService()
    candidates = service.rerank_candidates(
        query_text=request.query_text,
        candidate_texts=request.candidate_texts or [request.query_text] * len(request.candidate_job_ids),
        candidate_ids=request.candidate_job_ids,
    )
    return SemanticRerankResponse(query_id=request.query_id, candidates=candidates)


@router.post("/semantic-rerank-from-file")
def semantic_rerank_from_file() -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[3]
    artifact_dir = repo_root / "artifacts" / "semantic_index"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    output_path = artifact_dir / "semantic_rerank_output.json"
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="semantic rerank output not found; run the generation script first")
    return json.loads(output_path.read_text(encoding="utf-8"))
