"""Yoga assistant: retrieval-augmented Q&A over the asana library and a
curated yoga-knowledge base, answered by a Groq-hosted language model."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from ..auth.deps import get_current_user
from ..core.config import settings
from ..models.models import User
from ..schemas.schemas import AssistantAnswer, AssistantAsk, AssistantStatusOut
from ..services import assistant_service

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.get("/status", response_model=AssistantStatusOut)
def assistant_status() -> dict:
    return {"configured": bool(settings.groq_api_key)}


@router.post("/ask", response_model=AssistantAnswer)
async def ask_assistant(
    payload: AssistantAsk, user: User = Depends(get_current_user)
) -> dict:
    try:
        return await assistant_service.ask(payload.question)
    except assistant_service.AssistantUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The yoga assistant's language model is temporarily unavailable.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach the yoga assistant's language model.",
        ) from exc
