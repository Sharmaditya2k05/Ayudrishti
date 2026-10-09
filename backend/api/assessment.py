"""Live pose assessment endpoints.

The client detects landmarks on-device with MediaPipe and posts only the 33
coordinates. No image ever reaches the server, which is what makes the
privacy claim in the README structural rather than aspirational.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..auth.deps import get_current_user
from ..database.session import get_db
from ..models.models import User
from ..schemas.schemas import AssessmentRequest, AssessmentResponse, RecognitionOut
from ..services import wearable_service
from ..services.assessment_service import assess_frame, live_state, recognize_frame

router = APIRouter(prefix="/assessment", tags=["assessment"])


@router.post("", response_model=AssessmentResponse)
def assess(
    payload: AssessmentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Score one frame and return corrective feedback.

    If ``asana_id`` is omitted the pose is recognised first, so the same
    endpoint serves both a guided session (pose known) and free practice
    (pose discovered).
    """
    # Wearable context is looked up opportunistically: if no device has sent
    # anything recently this is simply None and the fusion checks stay quiet.
    physio = wearable_service.latest_snapshot(
        db, user, session_id=payload.session_id
    )

    return assess_frame(
        user_id=user.id,
        landmarks=payload.landmarks,
        asana_id=payload.asana_id,
        session_id=payload.session_id,
        timestamp=payload.timestamp,
        lead_side=payload.lead_side,
        expected_asanas=payload.expected_asanas,
        include_rules=payload.include_rules,
        physiological=physio,
        resting_heart_rate=user.resting_heart_rate,
    )


@router.post("/pose", response_model=RecognitionOut)
def recognise(
    payload: AssessmentRequest, user: User = Depends(get_current_user)
) -> dict:
    """Identify the pose in a frame without scoring it."""
    return recognize_frame(
        landmarks=payload.landmarks,
        timestamp=payload.timestamp,
        expected_asanas=payload.expected_asanas,
    )


@router.post("/reset", status_code=204, response_class=Response, response_model=None)
def reset_live_state(
    session_id: int | None = None, user: User = Depends(get_current_user)
) -> None:
    """Clear feedback throttling and safety timers.

    Called when moving to the next asana or restarting a session, so
    cooldowns from the previous pose do not silence the first corrections
    of the new one.
    """
    live_state.clear(user.id, session_id)
