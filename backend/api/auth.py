"""Registration and login."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.deps import get_current_user
from ..auth.security import create_access_token, hash_password, verify_password
from ..core.config import settings
from ..database.session import get_db
from ..models.models import User
from ..schemas.schemas import AuthResponse, Token, UserOut, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "expires_in_minutes": settings.access_token_expire_minutes,
    }


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> dict:
    existing = db.execute(
        select(User).where(User.email == payload.email.lower())
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        name=payload.name,
        age=payload.age,
        experience=payload.experience,
        goals=payload.goals,
        focus_areas=payload.focus_areas,
        avoid_asanas=[],
        preferred_duration=payload.preferred_duration,
        practice_frequency=payload.practice_frequency,
        # Registration doubles as onboarding when goals were supplied, so a
        # user who filled in the full form is not asked the same questions again.
        onboarded=bool(payload.goals),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {**_issue(user), "user": UserOut.model_validate(user)}


@router.post("/login", response_model=AuthResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> dict:
    """Log in with email and password.

    Uses the OAuth2 password form so FastAPI's interactive docs can
    authenticate; the ``username`` field carries the email address.
    """
    user = db.execute(
        select(User).where(User.email == form.username.lower())
    ).scalar_one_or_none()

    # Identical error whether the account is unknown or the password is
    # wrong, so the endpoint cannot be used to enumerate registered emails.
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This account is disabled."
        )

    return {**_issue(user), "user": UserOut.model_validate(user)}


@router.post("/refresh", response_model=Token)
def refresh(user: User = Depends(get_current_user)) -> dict:
    return _issue(user)
