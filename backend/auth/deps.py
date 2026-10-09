"""Authentication dependencies for protected endpoints."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ..database.session import get_db
from ..models.models import User
from .security import TokenError, decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise CREDENTIALS_ERROR
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (TokenError, ValueError, KeyError):
        raise CREDENTIALS_ERROR

    user = db.get(User, user_id)
    if user is None:
        raise CREDENTIALS_ERROR
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This account is disabled."
        )
    return user


def get_current_onboarded_user(user: User = Depends(get_current_user)) -> User:
    """For endpoints that need a complete profile to produce useful output.

    Recommendations without goals or an experience level would be arbitrary,
    so those routes ask for onboarding to be finished first rather than
    guessing.
    """
    if not user.onboarded:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="Complete onboarding before using this feature.",
        )
    return user
