"""Optional wearable ingestion.

Everything here is additive. The camera-only loop must work identically
whether a device is connected or not, so no other service depends on this
one, and no endpoint fails because a wearable is absent.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai.safety import WELLNESS_DISCLAIMER, PhysiologicalSnapshot

from ..models.models import PhysiologicalData, PracticeSession, User, WearableDevice


def connect_device(
    db: Session, user: User, *, device_id: str, device_name: str = "", firmware: str = ""
) -> WearableDevice:
    device = db.execute(
        select(WearableDevice).where(
            WearableDevice.user_id == user.id, WearableDevice.device_id == device_id
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if device is None:
        device = WearableDevice(
            user_id=user.id,
            device_id=device_id,
            device_name=device_name,
            firmware=firmware,
        )
        db.add(device)

    device.device_name = device_name or device.device_name
    device.firmware = firmware or device.firmware
    device.connected = True
    device.last_seen = now

    db.commit()
    db.refresh(device)
    return device


def disconnect_device(db: Session, user: User, device_id: str) -> bool:
    device = db.execute(
        select(WearableDevice).where(
            WearableDevice.user_id == user.id, WearableDevice.device_id == device_id
        )
    ).scalar_one_or_none()
    if device is None:
        return False
    device.connected = False
    db.commit()
    return True


def ingest_samples(
    db: Session,
    user: User,
    *,
    samples: Sequence[object],
    session_id: Optional[int] = None,
    device_id: Optional[str] = None,
) -> int:
    """Store a batch of readings. Returns how many rows were written."""
    if session_id is not None:
        owns = db.execute(
            select(PracticeSession.id).where(
                PracticeSession.id == session_id, PracticeSession.user_id == user.id
            )
        ).scalar_one_or_none()
        if owns is None:
            session_id = None  # never attach readings to someone else's session

    now = datetime.now(timezone.utc)
    rows = [
        PhysiologicalData(
            user_id=user.id,
            session_id=session_id,
            recorded_at=sample.recorded_at or now,
            heart_rate=sample.heart_rate,
            spo2=sample.spo2,
            gsr=sample.gsr,
            motion=sample.motion,
            device_id=device_id,
        )
        for sample in samples
    ]
    db.add_all(rows)

    if device_id:
        device = db.execute(
            select(WearableDevice).where(
                WearableDevice.user_id == user.id, WearableDevice.device_id == device_id
            )
        ).scalar_one_or_none()
        if device is not None:
            device.last_seen = now
            device.connected = True

    db.commit()
    return len(rows)


def device_status(db: Session, user: User) -> Dict[str, object]:
    device = db.execute(
        select(WearableDevice)
        .where(WearableDevice.user_id == user.id)
        .order_by(WearableDevice.last_seen.desc().nullslast())
        .limit(1)
    ).scalar_one_or_none()

    since = datetime.now(timezone.utc) - timedelta(days=1)
    samples_today = db.execute(
        select(func.count(PhysiologicalData.id)).where(
            PhysiologicalData.user_id == user.id,
            PhysiologicalData.recorded_at >= since,
        )
    ).scalar_one()

    return {
        "connected": bool(device and device.connected),
        "device_id": device.device_id if device else None,
        "device_name": device.device_name if device else None,
        "last_seen": device.last_seen if device else None,
        "samples_today": samples_today,
        "disclaimer": WELLNESS_DISCLAIMER,
    }


def latest_snapshot(
    db: Session, user: User, *, session_id: Optional[int] = None, window_seconds: int = 30
) -> Optional[PhysiologicalSnapshot]:
    """Most recent readings, for fusing with the live pose assessment.

    Averaged over a short window because single samples from consumer
    optical sensors are noisy, especially while the wearer is moving.
    """
    since = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    stmt = select(PhysiologicalData).where(
        PhysiologicalData.user_id == user.id, PhysiologicalData.recorded_at >= since
    )
    if session_id is not None:
        stmt = stmt.where(PhysiologicalData.session_id == session_id)

    rows = list(db.execute(stmt.order_by(PhysiologicalData.recorded_at.desc()).limit(60)).scalars())
    if not rows:
        return None

    def mean(attr: str) -> Optional[float]:
        vals = [getattr(r, attr) for r in rows if getattr(r, attr) is not None]
        return sum(vals) / len(vals) if vals else None

    return PhysiologicalSnapshot(
        heart_rate=mean("heart_rate"),
        spo2=mean("spo2"),
        gsr=mean("gsr"),
        motion=mean("motion"),
        timestamp=rows[0].recorded_at.timestamp(),
    )
