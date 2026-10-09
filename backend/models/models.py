"""SQLAlchemy models for AyuDrishti.

Design notes:

* Asana definitions and their pose rules are mirrored into the database from
  ``data/pose_rules/*.json`` by the seeder. The JSON files remain the source
  of truth for the assessment engine -- the tables exist so the API can
  serve, filter and join on asana metadata without reading files per request.
* Assessment results store *derived metrics only*. No frames, no images and
  (by default) no raw landmarks are persisted, which is what makes the
  privacy requirement structural rather than a policy note.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    age: Mapped[Optional[int]] = mapped_column(Integer)
    experience: Mapped[str] = mapped_column(String(20), default="beginner", nullable=False)
    # Lists of short slugs; JSON keeps onboarding fields flexible without a
    # migration every time a new goal or focus area is offered.
    goals: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    focus_areas: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    avoid_asanas: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    preferred_duration: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    practice_frequency: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    resting_heart_rate: Mapped[Optional[float]] = mapped_column(Float)

    onboarded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="practitioner", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    sessions: Mapped[List["PracticeSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    recommendations: Mapped[List["Recommendation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    physiological_data: Mapped[List["PhysiologicalData"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Asana(Base):
    __tablename__ = "asanas"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    english_name: Mapped[str] = mapped_column(String(120), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")

    target_goals: Mapped[List[str]] = mapped_column(JSON, default=list)
    focus_areas: Mapped[List[str]] = mapped_column(JSON, default=list)
    corrects: Mapped[List[str]] = mapped_column(JSON, default=list)
    preparatory: Mapped[List[str]] = mapped_column(JSON, default=list)
    cues: Mapped[List[str]] = mapped_column(JSON, default=list)
    benefits: Mapped[List[str]] = mapped_column(JSON, default=list)
    contraindications: Mapped[List[str]] = mapped_column(JSON, default=list)

    symmetry: Mapped[str] = mapped_column(String(20), default="bilateral")
    preferred_view: Mapped[str] = mapped_column(String(20), default="front")
    camera_hint: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(Text, default="")
    image_credit: Mapped[str] = mapped_column(Text, default="")
    sequence_stage: Mapped[str] = mapped_column(String(20), default="standing")
    intensity: Mapped[int] = mapped_column(Integer, default=2)
    hold_seconds: Mapped[int] = mapped_column(Integer, default=30)

    pose_rules: Mapped[List["PoseRule"]] = relationship(
        back_populates="asana", cascade="all, delete-orphan"
    )
    assessments: Mapped[List["PoseAssessment"]] = relationship(back_populates="asana")


class PoseRule(Base):
    """One alignment rule, mirrored from the asana JSON for API visibility."""

    __tablename__ = "pose_rules"
    __table_args__ = (UniqueConstraint("asana_id", "rule_key", name="uq_pose_rule_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    asana_id: Mapped[int] = mapped_column(
        ForeignKey("asanas.id", ondelete="CASCADE"), index=True, nullable=False
    )
    rule_key: Mapped[str] = mapped_column(String(80), nullable=False)
    component: Mapped[str] = mapped_column(String(60), nullable=False)
    body_part: Mapped[str] = mapped_column(String(60), default="")
    measurement: Mapped[str] = mapped_column(String(40), nullable=False)

    # Landmark slots. Kept as explicit columns (rather than a JSON blob) so
    # the schema documents what a rule actually references, matching the
    # PoseRule shape described in the spec.
    landmark_1: Mapped[Optional[str]] = mapped_column(String(40))
    landmark_2: Mapped[Optional[str]] = mapped_column(String(40))
    landmark_3: Mapped[Optional[str]] = mapped_column(String(40))
    landmark_4: Mapped[Optional[str]] = mapped_column(String(40))

    minimum_angle: Mapped[float] = mapped_column(Float, nullable=False)
    maximum_angle: Mapped[float] = mapped_column(Float, nullable=False)
    tolerance: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    unit: Mapped[str] = mapped_column(String(20), default="degrees")

    feedback_message: Mapped[str] = mapped_column(Text, default="")
    feedback_message_high: Mapped[str] = mapped_column(Text, default="")

    asana: Mapped[Asana] = relationship(back_populates="pose_rules")


class PracticeSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)

    overall_score: Mapped[Optional[float]] = mapped_column(Float)
    asana_count: Mapped[int] = mapped_column(Integer, default=0)
    correction_count: Mapped[int] = mapped_column(Integer, default=0)
    deviation_count: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)
    planned_asanas: Mapped[List[str]] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(Text, default="")

    user: Mapped[User] = relationship(back_populates="sessions")
    assessments: Mapped[List["PoseAssessment"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    physiological_data: Mapped[List["PhysiologicalData"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class PoseAssessment(Base):
    """One scored attempt at one asana within a session."""

    __tablename__ = "pose_assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    asana_id: Mapped[int] = mapped_column(
        ForeignKey("asanas.id", ondelete="RESTRICT"), index=True, nullable=False
    )

    score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    lead_side: Mapped[Optional[str]] = mapped_column(String(10))
    hold_seconds: Mapped[int] = mapped_column(Integer, default=0)

    # {"knee": 78.2, "torso": 91.0, ...} -- the per-component breakdown shown
    # in the summary and used by the weakness analyser.
    alignment_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    corrections: Mapped[List[str]] = mapped_column(JSON, default=list)
    deviation_count: Mapped[int] = mapped_column(Integer, default=0)
    # Per-rule measured values, for the "why did I score that?" view.
    rule_details: Mapped[List[dict]] = mapped_column(JSON, default=list)

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    session: Mapped[PracticeSession] = relationship(back_populates="assessments")
    asana: Mapped[Asana] = relationship(back_populates="assessments")


Index("ix_assessment_asana_time", PoseAssessment.asana_id, PoseAssessment.recorded_at)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    asana_id: Mapped[int] = mapped_column(
        ForeignKey("asanas.id", ondelete="CASCADE"), index=True, nullable=False
    )

    reason: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[str] = mapped_column(String(20), default="beginner")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    position: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=30)
    sides: Mapped[int] = mapped_column(Integer, default=1)
    round_number: Mapped[int] = mapped_column(Integer, default=1)
    targeted_weakness: Mapped[Optional[str]] = mapped_column(String(60))
    # The full signed factor list, so the app can always show its working.
    factors: Mapped[List[dict]] = mapped_column(JSON, default=list)

    batch_id: Mapped[str] = mapped_column(String(40), index=True, default="")
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    user: Mapped[User] = relationship(back_populates="recommendations")
    asana: Mapped[Asana] = relationship()


class PhysiologicalData(Base):
    """Optional wearable readings. Never required for the core loop."""

    __tablename__ = "physiological_data"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    heart_rate: Mapped[Optional[float]] = mapped_column(Float)
    spo2: Mapped[Optional[float]] = mapped_column(Float)
    gsr: Mapped[Optional[float]] = mapped_column(Float)
    motion: Mapped[Optional[float]] = mapped_column(Float)
    device_id: Mapped[Optional[str]] = mapped_column(String(80))

    user: Mapped[User] = relationship(back_populates="physiological_data")
    session: Mapped[Optional[PracticeSession]] = relationship(
        back_populates="physiological_data"
    )


class WearableDevice(Base):
    __tablename__ = "wearable_devices"
    __table_args__ = (UniqueConstraint("user_id", "device_id", name="uq_user_device"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    device_id: Mapped[str] = mapped_column(String(80), nullable=False)
    device_name: Mapped[str] = mapped_column(String(120), default="")
    firmware: Mapped[str] = mapped_column(String(40), default="")
    connected: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship()
