"""Schema creation and asana seeding.

The JSON files in ``data/pose_rules/`` are the source of truth. This mirrors
them into the ``asanas`` and ``pose_rules`` tables so the API can query and
join on pose metadata, and re-running it is safe: existing rows are updated
in place rather than duplicated.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.pose_assessment.asana import AsanaConfig

from ..database.session import Base, SessionLocal, engine
from ..models.models import Asana, PoseRule
from ..services.engines import get_registry

logger = logging.getLogger(__name__)


def create_tables() -> None:
    """Create any missing tables.

    Fine for development and for a first deploy. Schema *changes* to an
    existing database should go through Alembic, which is why alembic is in
    requirements.txt.
    """
    Base.metadata.create_all(bind=engine)


def _landmark_slots(landmarks: List[str]) -> Dict[str, Optional[str]]:
    slots: Dict[str, Optional[str]] = {
        "landmark_1": None,
        "landmark_2": None,
        "landmark_3": None,
        "landmark_4": None,
    }
    for i, name in enumerate(landmarks[:4]):
        slots[f"landmark_{i + 1}"] = name
    return slots


def seed_asana(db: Session, config: AsanaConfig) -> Asana:
    """Insert or update one asana and its rules."""
    asana = db.execute(
        select(Asana).where(Asana.slug == config.id)
    ).scalar_one_or_none()
    if asana is None:
        asana = Asana(slug=config.id)
        db.add(asana)

    asana.name = config.name
    asana.english_name = config.english_name
    asana.difficulty = config.difficulty
    asana.description = config.description
    asana.target_goals = list(config.target_goals)
    asana.focus_areas = list(config.focus_areas)
    asana.corrects = list(config.corrects)
    asana.preparatory = list(config.preparatory)
    asana.cues = list(config.cues)
    asana.benefits = list(config.benefits)
    asana.contraindications = list(config.contraindications)
    asana.symmetry = config.symmetry
    asana.preferred_view = config.preferred_view
    asana.camera_hint = config.camera_hint
    asana.image_url = config.image_url
    asana.image_credit = config.image_credit
    asana.sequence_stage = config.sequence_stage
    asana.intensity = config.intensity
    asana.hold_seconds = config.hold_seconds

    db.flush()

    existing = {
        row.rule_key: row
        for row in db.execute(
            select(PoseRule).where(PoseRule.asana_id == asana.id)
        ).scalars()
    }

    seen: set[str] = set()
    for rule in config.rules:
        seen.add(rule.id)
        row = existing.get(rule.id)
        if row is None:
            row = PoseRule(asana_id=asana.id, rule_key=rule.id)
            db.add(row)

        row.component = rule.component
        row.body_part = rule.body_part
        row.measurement = rule.measurement
        for slot, value in _landmark_slots(rule.landmarks).items():
            setattr(row, slot, value)
        row.minimum_angle = rule.target_min
        row.maximum_angle = rule.target_max
        row.tolerance = rule.tolerance
        row.weight = rule.weight
        row.unit = rule.unit
        row.feedback_message = rule.feedback_low
        row.feedback_message_high = rule.feedback_high

    # Drop rules removed from the JSON so the tables cannot drift out of sync.
    for key, row in existing.items():
        if key not in seen:
            db.delete(row)

    return asana


def seed_asanas(db: Optional[Session] = None) -> int:
    """Mirror every asana definition into the database."""
    owns_session = db is None
    db = db or SessionLocal()
    try:
        registry = get_registry()
        for config in registry.all():
            seed_asana(db, config)
        db.commit()
        logger.info("Seeded %d asanas from pose rule definitions.", len(registry))
        return len(registry)
    finally:
        if owns_session:
            db.close()


def init_db() -> int:
    create_tables()
    return seed_asanas()


if __name__ == "__main__":  # pragma: no cover - manual entry point
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    count = init_db()
    print(f"Database ready. {count} asanas seeded.")
