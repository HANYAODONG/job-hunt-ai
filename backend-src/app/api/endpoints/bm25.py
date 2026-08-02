from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...core.database import get_elasticsearch
from ...services.chinese_bm25_service import ChineseBM25Service


router = APIRouter()


class BM25SearchRequest(BaseModel):
    query: str = Field(min_length=1, description="岗位关键词或简历文本")
    size: int = Field(default=20, ge=1, le=200)
    source_type: Optional[str] = Field(default=None, description="enterprise 或 government")
    location: Optional[str] = None
    exclude_duplicates: bool = True


class BM25CandidateRequest(BM25SearchRequest):
    query_id: Optional[str] = Field(
        default=None,
        description="简历或查询ID；缺省时使用查询文本",
    )


def get_service() -> ChineseBM25Service:
    client = get_elasticsearch()
    if client is None:
        raise HTTPException(status_code=503, detail="Elasticsearch is unavailable")
    return ChineseBM25Service(client)


def execute_search(request: BM25SearchRequest):
    return get_service().search(
        query_text=request.query,
        size=request.size,
        source_type=request.source_type,
        location=request.location,
        exclude_duplicates=request.exclude_duplicates,
    )


@router.post("/search")
def search_jobs(request: BM25SearchRequest):
    try:
        return execute_search(request)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/candidates")
def retrieve_candidates(request: BM25CandidateRequest):
    """Return the stable, compact contract consumed by downstream workflows."""

    try:
        result = execute_search(request)
        candidates = [
            {
                "job_id": hit["job_id"],
                "bm25_score": hit["score"],
                "bm25_rank": hit["rank"],
            }
            for hit in result["hits"]
        ]
        return {
            "index_name": result["index_name"],
            "query_id": request.query_id or request.query,
            "query_text": request.query,
            "took_ms": result["took_ms"],
            "total": result["total"],
            "retrieved_count": len(candidates),
            "candidates": candidates,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/stats")
def index_stats():
    try:
        return get_service().stats()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
