"""Progress and analytics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth.deps import get_current_user
from ..database.session import get_db
from ..models.models import User
from ..schemas.schemas import PoseProgressOut, ProgressOut
from ..services import progress_service

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("", response_model=ProgressOut)
def get_progress(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    return progress_service.overall_progress(db, user)


@router.get("/{asana_id}", response_model=PoseProgressOut)
def get_asana_progress(
    asana_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return progress_service.asana_progress(db, user, asana_id)
