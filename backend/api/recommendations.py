"""Recommendation endpoints -- the Suggest and Adapt ends of the loop."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth.deps import get_current_onboarded_user
from ..database.session import get_db
from ..models.models import User
from ..schemas.schemas import (
    GenerateRecommendationRequest,
    RecommendationOut,
    SessionPlanOut,
)
from ..services import recommendation_service

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("", response_model=SessionPlanOut)
def get_recommendations(
    duration_minutes: int | None = Query(default=None, ge=5, le=120),
    user: User = Depends(get_current_onboarded_user),
    db: Session = Depends(get_db),
) -> dict:
    """Today's recommended session, freshly adapted to recent performance."""
    plan = recommendation_service.build_plan(db, user, duration_minutes=duration_minutes)
    return plan.to_dict()


@router.post("/generate", response_model=SessionPlanOut)
def generate_recommendations(
    payload: GenerateRecommendationRequest,
    user: User = Depends(get_current_onboarded_user),
    db: Session = Depends(get_db),
) -> dict:
    """Generate a plan and (by default) record it for later audit."""
    plan = recommendation_service.build_plan(
        db, user, duration_minutes=payload.duration_minutes
    )
    if payload.persist:
        recommendation_service.persist_plan(db, user, plan)
    return plan.to_dict()


@router.get("/latest", response_model=List[RecommendationOut])
def latest(
    user: User = Depends(get_current_onboarded_user),
    db: Session = Depends(get_db),
) -> List[dict]:
    """The most recently stored plan, with the reasoning that produced it."""
    return [
        {
            "asana_id": row.asana.slug,
            "asana_name": row.asana.english_name,
            "difficulty": row.difficulty,
            "score": row.score,
            "reason": row.reason,
            "factors": row.factors or [],
            "duration_seconds": row.duration_seconds,
            "sides": row.sides,
            "total_seconds": row.duration_seconds * row.sides,
            "round_number": row.round_number,
            "targeted_weakness": row.targeted_weakness,
            "sequence_stage": row.asana.sequence_stage,
            "image_url": row.asana.image_url,
            "image_credit": row.asana.image_credit,
        }
        for row in recommendation_service.latest_plan(db, user)
    ]
