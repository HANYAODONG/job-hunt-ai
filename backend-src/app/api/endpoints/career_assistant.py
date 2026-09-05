from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from ...services.career_assistant_service import ask_career_assistant

router = APIRouter()


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1600)


class CareerAssistantRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=8)
    page_context: dict[str, Any] = Field(default_factory=dict)


@router.post("/chat")
async def chat(request: CareerAssistantRequest):
    try:
        return await run_in_threadpool(
            ask_career_assistant,
            request.message,
            [item.model_dump() for item in request.history],
            request.page_context,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
