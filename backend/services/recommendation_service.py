"""Recommendation generation and persistence."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ai.recommendation import SessionPlan

from ..models.models import Recommendation, User
from .engines import asana_id_map, get_recommendation_engine, load_history, to_profile


def build_plan(
    db: Session,
    user: User,
    *,
    duration_minutes: Optional[int] = None,
    now: Optional[datetime] = None,
) -> SessionPlan:
    """Generate a personalised, adapted session plan."""
    profile = to_profile(user)
    history = load_history(db, user.id)
    return get_recommendation_engine().build_session(
        profile, history, duration_minutes=duration_minutes, now=now
    )


def persist_plan(db: Session, user: User, plan: SessionPlan) -> str:
    """Store a plan as Recommendation rows and return its batch id.

    Recording what was recommended (and why) is what makes the adaptation
    auditable later: we can always show which weakness drove a suggestion.
    """
    slugs = asana_id_map(db)
    batch_id = uuid.uuid4().hex[:32]
    generated = plan.generated_at or datetime.now(timezone.utc)

    rows: List[Recommendation] = []
    for position, item in enumerate(plan.items):
        asana_pk = slugs.get(item.asana_id)
        if asana_pk is None:
            continue
        rows.append(
            Recommendation(
                user_id=user.id,
                asana_id=asana_pk,
                reason=item.reason,
                difficulty=item.difficulty,
                score=item.score,
                position=position,
                duration_seconds=item.duration_seconds,
                sides=item.sides,
                round_number=item.round_number,
                targeted_weakness=item.targeted_weakness,
                factors=[f.to_dict() for f in item.factors],
                batch_id=batch_id,
                generated_at=generated,
            )
        )

    db.add_all(rows)
    db.commit()
    return batch_id


def latest_plan(db: Session, user: User) -> List[Recommendation]:
    """The most recently generated recommendation batch, in order."""
    newest = db.execute(
        select(Recommendation.batch_id)
        .where(Recommendation.user_id == user.id)
        .order_by(Recommendation.generated_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if not newest:
        return []

    return list(
        db.execute(
            select(Recommendation)
            .where(
                Recommendation.user_id == user.id,
                Recommendation.batch_id == newest,
            )
            .options(joinedload(Recommendation.asana))
            .order_by(Recommendation.position)
        ).scalars()
    )


def plan_to_payload(plan: SessionPlan) -> Dict[str, object]:
    return plan.to_dict()
