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


def get_service() -> ChineseBM25Service:
    client = get_elasticsearch()
    if client is None:
        raise HTTPException(status_code=503, detail="Elasticsearch is unavailable")
    return ChineseBM25Service(client)


@router.post("/search")
def search_jobs(request: BM25SearchRequest):
    try:
        return get_service().search(
            query_text=request.query,
            size=request.size,
            source_type=request.source_type,
            location=request.location,
            exclude_duplicates=request.exclude_duplicates,
        )
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
