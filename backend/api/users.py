"""Profile management and onboarding."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth.deps import get_current_user
from ..database.session import get_db
from ..models.models import User
from ..schemas.schemas import UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def read_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.put("/me", response_model=UserOut)
def update_me(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Update the profile. Only supplied fields change."""
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(user, field, value)

    # Goals and experience are what the recommender needs; once they exist
    # the user counts as onboarded.
    if user.goals and user.experience:
        user.onboarded = True

    db.commit()
    db.refresh(user)
    return user
