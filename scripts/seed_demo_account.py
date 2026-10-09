"""Seed a demo account with a realistic practice history.

Creates one practitioner with a few weeks of completed sessions so every
screen has something real to show: goal-based recommendations that adapt,
progress trends, per-pose breakdowns, recurring weaknesses, and streaks.

Run against whatever DATABASE_URL points at:

    # local (SQLite fallback or your local Postgres)
    python scripts/seed_demo_account.py

    # the deployed database (grab the URL from Railway -> Postgres -> Variables)
    DATABASE_URL="postgresql+psycopg2://..." python scripts/seed_demo_account.py

Re-running deletes and recreates the same demo user, so the credentials below
stay stable. This writes only to the demo account; nothing else is touched.
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from backend.auth.security import hash_password
from backend.database.seed import init_db
from backend.database.session import SessionLocal
from backend.models.models import Asana, PhysiologicalData, PoseAssessment, PracticeSession, User
from backend.services.engines import get_registry

# --- who the demo account is ------------------------------------------------

DEMO_EMAIL = "demo@ayudrishti.app"
DEMO_PASSWORD = "Explore@2026"
DEMO_NAME = "Aditi Sharma"

PROFILE = dict(
    age=29,
    experience="beginner",
    goals=["flexibility", "stress_reduction"],
    focus_areas=["spine", "hips"],
    avoid_asanas=[],
    preferred_duration=20,
    practice_frequency=4,
    resting_heart_rate=64.0,
)

# The beginner session, in sequence order. "utkatasana" is deliberately kept
# the weak pose so the recommender has a real struggling area to target and
# the progress screen shows a laggard alongside the improvers.
SESSION_POSES = ["tadasana", "utkatasana", "bhujangasana", "setu_bandhasana", "balasana"]
WEAK_POSE = "utkatasana"

SESSIONS = 14            # ~4 weeks at 3-4/week
DAYS_SPAN = 28
HOLD_SECONDS = 30

rng = random.Random(20260821)  # deterministic, reproducible history


def _clamp(v: float, lo: float = 5.0, hi: float = 99.0) -> float:
    return max(lo, min(hi, v))


def build_history(db, user: User, components_by_slug: dict, asana_by_slug: dict) -> None:
    now = datetime.now(timezone.utc)
    # One session every ~2 days, oldest first, scores trending upward.
    for i in range(SESSIONS):
        day_offset = DAYS_SPAN - int(i * (DAYS_SPAN / SESSIONS))
        started = now - timedelta(days=day_offset, hours=rng.randint(0, 6), minutes=rng.randint(0, 59))
        # Overall skill rises from ~63 to ~86 across the month.
        base = 63 + (i / max(1, SESSIONS - 1)) * 23

        session = PracticeSession(
            user_id=user.id,
            started_at=started,
            completed_at=started + timedelta(minutes=PROFILE["preferred_duration"]),
            duration_seconds=PROFILE["preferred_duration"] * 60,
            status="completed",
            planned_asanas=list(SESSION_POSES),
        )
        db.add(session)
        db.flush()  # assign session.id

        scores: list[float] = []
        total_corrections = 0
        total_deviations = 0

        for slug in SESSION_POSES:
            asana = asana_by_slug[slug]
            comps = components_by_slug.get(slug, ["torso"])

            penalty = 12 if slug == WEAK_POSE else 0
            pose_score = _clamp(base - penalty + rng.uniform(-4, 4))

            # Per-component metrics scatter around the pose score; the weak
            # pose's primary components (legs) sit a little lower still.
            metrics = {}
            for c in comps:
                low = 6 if (slug == WEAK_POSE and c in ("legs", "knee", "torso")) else 0
                metrics[c] = round(_clamp(pose_score + rng.uniform(-6, 6) - low), 1)

            corrections = []
            for c, v in metrics.items():
                if v < 72:
                    corrections.append(f"Refine your {c.replace('_', ' ')} alignment.")
            corrections = corrections[:2]
            deviations = len(corrections)

            db.add(
                PoseAssessment(
                    session_id=session.id,
                    asana_id=asana.id,
                    score=round(pose_score, 1),
                    confidence=round(rng.uniform(0.86, 0.98), 2),
                    lead_side=None,
                    hold_seconds=HOLD_SECONDS,
                    alignment_metrics=metrics,
                    corrections=corrections,
                    deviation_count=deviations,
                    rule_details=[],
                    recorded_at=started + timedelta(minutes=len(scores) * 3),
                )
            )
            scores.append(pose_score)
            total_corrections += len(corrections)
            total_deviations += deviations

        session.overall_score = round(sum(scores) / len(scores), 1)
        session.asana_count = len(SESSION_POSES)
        session.correction_count = total_corrections
        session.deviation_count = total_deviations

        # Attach a little wearable data to the two most recent sessions so the
        # physiological screens are not empty.
        if i >= SESSIONS - 2:
            for k in range(6):
                db.add(
                    PhysiologicalData(
                        user_id=user.id,
                        session_id=session.id,
                        recorded_at=started + timedelta(minutes=k * 3),
                        heart_rate=round(72 + rng.uniform(-4, 18), 1),
                        spo2=round(rng.uniform(96, 99), 1),
                        gsr=round(rng.uniform(3, 12), 2),
                        motion=round(rng.uniform(0.9, 1.4), 2),
                        device_id="YOGA_BAND_01",
                    )
                )


def main() -> None:
    init_db()  # ensure tables exist and the asana library is seeded

    registry = get_registry()
    components_by_slug = {c.id: list(c.components.keys()) for c in registry.all()}

    db = SessionLocal()
    try:
        asanas = db.execute(select(Asana)).scalars().all()
        asana_by_slug = {a.slug: a for a in asanas}
        missing = [s for s in SESSION_POSES if s not in asana_by_slug]
        if missing:
            raise SystemExit(f"Asana library missing {missing}; did seeding run?")

        # Fresh start: remove any prior demo user (cascades to its sessions).
        existing = db.execute(select(User).where(User.email == DEMO_EMAIL)).scalar_one_or_none()
        if existing is not None:
            db.delete(existing)
            db.flush()

        user = User(
            email=DEMO_EMAIL,
            hashed_password=hash_password(DEMO_PASSWORD),
            name=DEMO_NAME,
            onboarded=True,
            **PROFILE,
        )
        db.add(user)
        db.flush()

        build_history(db, user, components_by_slug, asana_by_slug)
        db.commit()

        session_count = db.execute(
            select(PracticeSession).where(PracticeSession.user_id == user.id)
        ).scalars().all()
        assessment_count = db.execute(
            select(PoseAssessment)
            .join(PracticeSession)
            .where(PracticeSession.user_id == user.id)
        ).scalars().all()

        print("\n  Demo account ready\n" + "  " + "-" * 34)
        print(f"  Email     {DEMO_EMAIL}")
        print(f"  Password  {DEMO_PASSWORD}")
        print(f"  Name      {DEMO_NAME}  ({PROFILE['experience']})")
        print(f"  Goals     {', '.join(PROFILE['goals'])}")
        print(f"  Sessions  {len(session_count)} completed over ~{DAYS_SPAN} days")
        print(f"  Poses     {len(assessment_count)} scored attempts")
        print(f"  Weak area {WEAK_POSE} (drives adaptive recommendations)")
        print("  " + "-" * 34)
        print("  Log in on the app and open Plan / Progress to explore.\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()
