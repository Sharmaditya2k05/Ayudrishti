"""Session lifecycle: start, record assessments, complete, summarise."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ai.scoring import score_session

from ..models.models import Asana, PoseAssessment, PracticeSession, User
from .engines import asana_id_map


def start_session(
    db: Session, user: User, *, planned_asanas: Sequence[str] = (), notes: str = ""
) -> PracticeSession:
    """Open a new practice session.

    Any session the user left hanging is closed first, so a forgotten
    session cannot sit "in progress" forever and pollute their history.
    """
    stale = db.execute(
        select(PracticeSession).where(
            PracticeSession.user_id == user.id,
            PracticeSession.status == "in_progress",
        )
    ).scalars().all()
    for row in stale:
        row.status = "abandoned"
        row.completed_at = datetime.now(timezone.utc)

    session = PracticeSession(
        user_id=user.id,
        planned_asanas=list(planned_asanas),
        notes=notes,
        status="in_progress",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, user: User, session_id: int) -> PracticeSession:
    session = db.execute(
        select(PracticeSession)
        .where(PracticeSession.id == session_id)
        .options(
            joinedload(PracticeSession.assessments).joinedload(PoseAssessment.asana)
        )
    ).unique().scalar_one_or_none()

    if session is None or session.user_id != user.id:
        # Same response whether it is missing or someone else's, so the API
        # cannot be used to probe for other users' session ids.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
        )
    return session


def list_sessions(
    db: Session, user: User, *, limit: int = 50, offset: int = 0
) -> List[PracticeSession]:
    return list(
        db.execute(
            select(PracticeSession)
            .where(PracticeSession.user_id == user.id)
            .order_by(PracticeSession.started_at.desc())
            .limit(limit)
            .offset(offset)
        ).scalars()
    )


def record_assessments(
    db: Session,
    session: PracticeSession,
    assessments: Sequence[object],
) -> List[PoseAssessment]:
    """Persist completed asana attempts against a session."""
    slugs = asana_id_map(db)
    rows: List[PoseAssessment] = []

    for item in assessments:
        asana_pk = slugs.get(item.asana_id)
        if asana_pk is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown asana '{item.asana_id}'.",
            )
        rows.append(
            PoseAssessment(
                session_id=session.id,
                asana_id=asana_pk,
                score=item.score,
                confidence=item.confidence,
                lead_side=item.lead_side,
                hold_seconds=item.hold_seconds,
                alignment_metrics=dict(item.alignment_metrics or {}),
                corrections=list(item.corrections or []),
                deviation_count=item.deviation_count,
                rule_details=list(item.rule_details or []),
            )
        )

    db.add_all(rows)
    db.flush()
    return rows


def complete_session(
    db: Session,
    session: PracticeSession,
    *,
    assessments: Sequence[object] = (),
    duration_seconds: int = 0,
    notes: str = "",
) -> PracticeSession:
    """Close a session and compute its rolled-up score."""
    if session.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This session has already been completed.",
        )

    if assessments:
        record_assessments(db, session, assessments)

    db.flush()
    rows = list(
        db.execute(
            select(PoseAssessment)
            .where(PoseAssessment.session_id == session.id)
            .options(joinedload(PoseAssessment.asana))
        ).scalars()
    )

    grouped: Dict[str, List[float]] = {}
    corrections = 0
    deviations = 0
    for row in rows:
        grouped.setdefault(row.asana.slug, []).append(row.score)
        corrections += len(row.corrections or [])
        deviations += row.deviation_count

    summary = score_session(grouped, corrections=corrections, deviations=deviations)

    session.completed_at = datetime.now(timezone.utc)
    session.status = "completed"
    session.duration_seconds = duration_seconds or _elapsed_seconds(session)
    session.overall_score = summary.overall if rows else None
    session.asana_count = summary.asana_count
    session.correction_count = corrections
    session.deviation_count = deviations
    if notes:
        session.notes = notes

    db.commit()
    db.refresh(session)
    return session


def _elapsed_seconds(session: PracticeSession) -> int:
    started = session.started_at
    if started is None:
        return 0
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return max(int((datetime.now(timezone.utc) - started).total_seconds()), 0)


def summarise(db: Session, session: PracticeSession) -> Dict[str, object]:
    """Build the end-of-session summary payload."""
    rows = list(
        db.execute(
            select(PoseAssessment)
            .where(PoseAssessment.session_id == session.id)
            .options(joinedload(PoseAssessment.asana))
            .order_by(PoseAssessment.recorded_at)
        ).scalars()
    )

    grouped: Dict[str, List[float]] = {}
    for row in rows:
        grouped.setdefault(row.asana.slug, []).append(row.score)

    best = weakest = None
    if grouped:
        averages = {k: sum(v) / len(v) for k, v in grouped.items()}
        best = max(averages, key=lambda k: averages[k])
        weakest = min(averages, key=lambda k: averages[k])

    # Which alignment components let the session down, worst first.
    component_totals: Dict[str, List[float]] = {}
    for row in rows:
        for comp, value in (row.alignment_metrics or {}).items():
            component_totals.setdefault(comp, []).append(value)
    improvement_areas = sorted(
        (c for c, vals in component_totals.items() if sum(vals) / len(vals) < 75),
        key=lambda c: sum(component_totals[c]) / len(component_totals[c]),
    )

    return {
        "assessments": [
            {
                "id": row.id,
                "asana_id": row.asana.slug,
                "asana_name": row.asana.english_name,
                "score": row.score,
                "confidence": row.confidence,
                "lead_side": row.lead_side,
                "hold_seconds": row.hold_seconds,
                "alignment_metrics": row.alignment_metrics or {},
                "corrections": row.corrections or [],
                "deviation_count": row.deviation_count,
                "recorded_at": row.recorded_at,
            }
            for row in rows
        ],
        "best_pose": best,
        "weakest_pose": weakest,
        "improvement_areas": improvement_areas,
    }
