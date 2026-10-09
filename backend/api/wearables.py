"""Optional wearable endpoints.

None of these are required for the core loop. The app is fully functional
with no device connected.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..auth.deps import get_current_user
from ..database.session import get_db
from ..models.models import User
from ..schemas.schemas import WearableConnect, WearableDataIn, WearableStatusOut
from ..services import wearable_service

router = APIRouter(prefix="/wearables", tags=["wearables"])


@router.post("/connect", response_model=WearableStatusOut)
def connect(
    payload: WearableConnect,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    wearable_service.connect_device(
        db,
        user,
        device_id=payload.device_id,
        device_name=payload.device_name,
        firmware=payload.firmware,
    )
    return wearable_service.device_status(db, user)


@router.post("/disconnect/{device_id}", status_code=204, response_class=Response, response_model=None)
def disconnect(
    device_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    if not wearable_service.disconnect_device(db, user, device_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found."
        )


@router.post("/data", status_code=status.HTTP_202_ACCEPTED)
def ingest(
    payload: WearableDataIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    written = wearable_service.ingest_samples(
        db,
        user,
        samples=payload.samples,
        session_id=payload.session_id,
        device_id=payload.device_id,
    )
    return {"accepted": written}


@router.get("/status", response_model=WearableStatusOut)
def status_endpoint(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    return wearable_service.device_status(db, user)
