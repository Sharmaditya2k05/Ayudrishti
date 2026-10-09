"""Shared AI engine instances and DB-to-AI translation.

The AI layer knows nothing about SQLAlchemy, so this module owns the
conversion between ORM rows and the plain dataclasses the engines expect.
Keeping that mapping in one place means the API routers stay thin and the AI
layer stays independently testable.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ai.pose_assessment import AsanaRegistry, PoseAssessmentEngine
from ai.pose_recognition import RuleBasedRecognizer
from ai.recommendation import (
    PerformanceAnalyzer,
    PoseRecord,
    PracticeHistory,
    RecommendationEngine,
    UserProfile,
)

from ..core.config import settings
from ..models.models import Asana, PoseAssessment, PracticeSession, User


@lru_cache
def get_registry() -> AsanaRegistry:
    return AsanaRegistry.from_directory(Path(settings.pose_rules_dir))


@lru_cache
def get_assessment_engine() -> PoseAssessmentEngine:
    return PoseAssessmentEngine(
        get_registry(), visibility_threshold=settings.visibility_threshold
    )


@lru_cache
def get_recognizer() -> RuleBasedRecognizer:
    return RuleBasedRecognizer(
        get_registry(), visibility_threshold=settings.visibility_threshold
    )


@lru_cache
def get_recommendation_engine() -> RecommendationEngine:
    return RecommendationEngine(get_registry(), PerformanceAnalyzer())


@lru_cache
def get_analyzer() -> PerformanceAnalyzer:
    return PerformanceAnalyzer()


def to_profile(user: User) -> UserProfile:
    """Map a User row onto the profile the recommender consumes."""
    return UserProfile(
        user_id=user.id,
        name=user.name,
        age=user.age,
        experience=user.experience,
        goals=list(user.goals or []),
        preferred_duration=user.preferred_duration,
        practice_frequency=user.practice_frequency,
        focus_areas=list(user.focus_areas or []),
        avoid=list(user.avoid_asanas or []),
    )


def load_history(db: Session, user_id: int, *, limit: int = 500) -> PracticeHistory:
    """Build practice history from this user's recorded assessments."""
    stmt = (
        select(PoseAssessment)
        .join(PracticeSession, PoseAssessment.session_id == PracticeSession.id)
        .where(PracticeSession.user_id == user_id)
        .options(joinedload(PoseAssessment.asana))
        .order_by(PoseAssessment.recorded_at.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().all()

    records = [
        PoseRecord(
            asana_id=row.asana.slug,
            score=row.score,
            performed_at=row.recorded_at,
            component_scores=dict(row.alignment_metrics or {}),
            deviation_count=row.deviation_count,
            corrections=list(row.corrections or []),
            session_id=row.session_id,
        )
        for row in rows
    ]
    # PracticeHistory sorts oldest-first in __post_init__.
    return PracticeHistory(records)


def asana_id_map(db: Session) -> Dict[str, int]:
    """slug -> primary key, for writing assessment rows."""
    rows = db.execute(select(Asana.slug, Asana.id)).all()
    return {slug: pk for slug, pk in rows}


def asana_by_slug(db: Session, slug: str) -> Optional[Asana]:
    return db.execute(select(Asana).where(Asana.slug == slug)).scalar_one_or_none()
