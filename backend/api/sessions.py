"""Practice session endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from ..auth.deps import get_current_user
from ..database.session import get_db
from ..models.models import PracticeSession, User
from ..schemas.schemas import (
    SessionComplete,
    SessionCreate,
    SessionDetail,
    SessionOut,
)
from ..services import session_service
from ..services.assessment_service import live_state

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _to_out(session: PracticeSession) -> dict:
    return {
        "id": session.id,
        "started_at": session.started_at,
        "completed_at": session.completed_at,
        "duration_seconds": session.duration_seconds,
        "overall_score": session.overall_score,
        "asana_count": session.asana_count,
        "correction_count": session.correction_count,
        "deviation_count": session.deviation_count,
        "status": session.status,
        "planned_asanas": session.planned_asanas or [],
        "notes": session.notes or "",
    }


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    session = session_service.start_session(
        db, user, planned_asanas=payload.planned_asanas, notes=payload.notes
    )
    return _to_out(session)


@router.get("", response_model=List[SessionOut])
def list_sessions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[dict]:
    return [_to_out(s) for s in session_service.list_sessions(db, user, limit=limit, offset=offset)]


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    session = session_service.get_session(db, user, session_id)
    return {**_to_out(session), **session_service.summarise(db, session)}


@router.post("/{session_id}/complete", response_model=SessionDetail)
def complete_session(
    session_id: int,
    payload: SessionComplete,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Finish a session, record its assessments and return the summary."""
    session = session_service.get_session(db, user, session_id)
    session = session_service.complete_session(
        db,
        session,
        assessments=payload.assessments,
        duration_seconds=payload.duration_seconds,
        notes=payload.notes,
    )
    # The live coaching state belongs to this session only.
    live_state.clear(user.id, session_id)
    return {**_to_out(session), **session_service.summarise(db, session)}
