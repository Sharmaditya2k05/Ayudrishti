"""Pydantic request/response models for the REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from ai.recommendation.profile import EXPERIENCE_LEVELS, GOALS

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)

    age: Optional[int] = Field(default=None, ge=5, le=120)
    experience: str = "beginner"
    goals: List[str] = Field(default_factory=list)
    focus_areas: List[str] = Field(default_factory=list)
    preferred_duration: int = Field(default=20, ge=5, le=120)
    practice_frequency: int = Field(default=3, ge=1, le=14)

    @field_validator("experience")
    @classmethod
    def _valid_experience(cls, v: str) -> str:
        if v not in EXPERIENCE_LEVELS:
            raise ValueError(f"experience must be one of {list(EXPERIENCE_LEVELS)}")
        return v

    @field_validator("goals")
    @classmethod
    def _valid_goals(cls, v: List[str]) -> List[str]:
        unknown = [g for g in v if g not in GOALS]
        if unknown:
            raise ValueError(f"unknown goals {unknown}; valid goals are {list(GOALS)}")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class AuthResponse(Token):
    user: "UserOut"


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str
    age: Optional[int]
    experience: str
    goals: List[str]
    focus_areas: List[str]
    avoid_asanas: List[str]
    preferred_duration: int
    practice_frequency: int
    resting_heart_rate: Optional[float]
    onboarded: bool
    role: str
    created_at: datetime


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    age: Optional[int] = Field(default=None, ge=5, le=120)
    experience: Optional[str] = None
    goals: Optional[List[str]] = None
    focus_areas: Optional[List[str]] = None
    avoid_asanas: Optional[List[str]] = None
    preferred_duration: Optional[int] = Field(default=None, ge=5, le=120)
    practice_frequency: Optional[int] = Field(default=None, ge=1, le=14)
    resting_heart_rate: Optional[float] = Field(default=None, ge=30, le=120)

    @field_validator("experience")
    @classmethod
    def _valid_experience(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in EXPERIENCE_LEVELS:
            raise ValueError(f"experience must be one of {list(EXPERIENCE_LEVELS)}")
        return v

    @field_validator("goals")
    @classmethod
    def _valid_goals(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        unknown = [g for g in v if g not in GOALS]
        if unknown:
            raise ValueError(f"unknown goals {unknown}; valid goals are {list(GOALS)}")
        return v


# ---------------------------------------------------------------------------
# Asanas
# ---------------------------------------------------------------------------


class PoseRuleOut(BaseModel):
    rule_id: str
    component: str
    body_part: str
    measurement: str
    landmarks: List[str]
    target_min: float
    target_max: float
    tolerance: float
    weight: float
    unit: str
    feedback_low: str = ""
    feedback_high: str = ""


class AsanaOut(BaseModel):
    id: str
    name: str
    english_name: str
    difficulty: str
    description: str
    target_goals: List[str]
    focus_areas: List[str]
    components: Dict[str, str]
    symmetry: str
    preferred_view: str
    camera_hint: str
    image_url: str
    image_credit: str
    sequence_stage: str
    intensity: int
    hold_seconds: int
    cues: List[str]
    benefits: List[str]
    contraindications: List[str]
    preparatory: List[str]
    corrects: List[str]


class AsanaDetail(AsanaOut):
    rules: List[Dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------


class LandmarkIn(BaseModel):
    """One detected body point, as sent by the client."""

    x: float
    y: float
    z: float = 0.0
    visibility: float = 1.0


class AssessmentRequest(BaseModel):
    """Landmarks for one frame, plus what to assess them against.

    The client runs MediaPipe locally and posts only landmark coordinates --
    never the image. That keeps camera data on the device, which is the
    privacy posture the spec asks for.
    """

    landmarks: List[LandmarkIn] = Field(min_length=1)
    asana_id: Optional[str] = Field(
        default=None,
        description="Asana to score against. Omit to auto-recognise the pose.",
    )
    session_id: Optional[int] = None
    timestamp: float = 0.0
    lead_side: Optional[str] = None
    expected_asanas: List[str] = Field(default_factory=list)
    include_rules: bool = True

    @field_validator("landmarks")
    @classmethod
    def _landmark_count(cls, v: List[LandmarkIn]) -> List[LandmarkIn]:
        if len(v) not in (33,):
            raise ValueError(
                f"expected 33 MediaPipe Pose landmarks, got {len(v)}"
            )
        return v

    @field_validator("lead_side")
    @classmethod
    def _valid_side(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("left", "right"):
            raise ValueError("lead_side must be 'left' or 'right'")
        return v


class RecognitionOut(BaseModel):
    asana_id: Optional[str]
    asana_name: Optional[str]
    confidence: float
    method: str
    lead_side: Optional[str] = None
    ambiguous: bool = False
    reason: str = ""
    candidates: List[Dict[str, Any]] = Field(default_factory=list)


class AssessmentResponse(BaseModel):
    detected: bool
    asana_id: Optional[str] = None
    asana_name: Optional[str] = None
    overall: float = 0.0
    grade: str = ""
    confidence: float = 0.0
    reliable: bool = False
    lead_side: Optional[str] = None
    deviation_count: int = 0
    components: List[Dict[str, Any]] = Field(default_factory=list)
    rules: List[Dict[str, Any]] = Field(default_factory=list)
    feedback: Dict[str, Any] = Field(default_factory=dict)
    recognition: Optional[RecognitionOut] = None
    safety_alerts: List[Dict[str, Any]] = Field(default_factory=list)
    missing_landmarks: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


class SessionCreate(BaseModel):
    planned_asanas: List[str] = Field(default_factory=list)
    notes: str = ""


class PoseAssessmentIn(BaseModel):
    """A completed asana attempt, recorded at the end of its hold."""

    asana_id: str
    score: float = Field(ge=0, le=100)
    confidence: float = Field(default=1.0, ge=0, le=1)
    lead_side: Optional[str] = None
    hold_seconds: int = Field(default=0, ge=0)
    alignment_metrics: Dict[str, float] = Field(default_factory=dict)
    corrections: List[str] = Field(default_factory=list)
    deviation_count: int = Field(default=0, ge=0)
    rule_details: List[Dict[str, Any]] = Field(default_factory=list)


class SessionComplete(BaseModel):
    assessments: List[PoseAssessmentIn] = Field(default_factory=list)
    duration_seconds: int = Field(default=0, ge=0)
    notes: str = ""


class PoseAssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asana_id: str
    asana_name: str
    score: float
    confidence: float
    lead_side: Optional[str]
    hold_seconds: int
    alignment_metrics: Dict[str, float]
    corrections: List[str]
    deviation_count: int
    recorded_at: datetime


class SessionOut(BaseModel):
    id: int
    started_at: datetime
    completed_at: Optional[datetime]
    duration_seconds: int
    overall_score: Optional[float]
    asana_count: int
    correction_count: int
    deviation_count: int
    status: str
    planned_asanas: List[str]
    notes: str


class SessionDetail(SessionOut):
    assessments: List[PoseAssessmentOut] = Field(default_factory=list)
    best_pose: Optional[str] = None
    weakest_pose: Optional[str] = None
    improvement_areas: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


class RecommendationOut(BaseModel):
    asana_id: str
    asana_name: str
    difficulty: str
    score: float
    reason: str
    factors: List[Dict[str, Any]]
    duration_seconds: int
    sides: int
    total_seconds: int
    round_number: int
    targeted_weakness: Optional[str]
    sequence_stage: str
    image_url: str
    image_credit: str


class SessionPlanOut(BaseModel):
    items: List[RecommendationOut]
    total_seconds: int
    total_minutes: float
    requested_minutes: int
    rounds: int
    focus: str
    notes: List[str]
    generated_at: Optional[str]


class GenerateRecommendationRequest(BaseModel):
    duration_minutes: Optional[int] = Field(default=None, ge=5, le=120)
    persist: bool = True


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------


class ScorePoint(BaseModel):
    date: str
    score: float
    session_id: Optional[int] = None


class PoseProgressOut(BaseModel):
    asana_id: str
    asana_name: str
    attempts: int
    average_score: float
    latest_score: float
    best_score: float
    trend: Optional[float]
    days_since: Optional[int]
    weak_components: List[str]
    history: List[ScorePoint]
    component_history: Dict[str, List[ScorePoint]] = Field(default_factory=dict)


class ProgressOut(BaseModel):
    overall_average: Optional[float]
    overall_trend: Optional[float]
    total_sessions: int
    total_assessments: int
    ready_to_progress: bool
    score_history: List[ScorePoint]
    per_asana: List[PoseProgressOut]
    weaknesses: List[Dict[str, Any]]
    consistency: Optional[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Wearables
# ---------------------------------------------------------------------------


class WearableConnect(BaseModel):
    device_id: str = Field(min_length=1, max_length=80)
    device_name: str = ""
    firmware: str = ""


class WearableSample(BaseModel):
    heart_rate: Optional[float] = Field(default=None, ge=20, le=250)
    spo2: Optional[float] = Field(default=None, ge=50, le=100)
    gsr: Optional[float] = Field(default=None, ge=0, le=100)
    motion: Optional[float] = Field(default=None, ge=0, le=64)
    recorded_at: Optional[datetime] = None


class WearableDataIn(BaseModel):
    session_id: Optional[int] = None
    device_id: Optional[str] = None
    samples: List[WearableSample] = Field(min_length=1, max_length=2000)


class WearableStatusOut(BaseModel):
    connected: bool
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    last_seen: Optional[datetime] = None
    samples_today: int = 0
    disclaimer: str


class AssistantAsk(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class AssistantSource(BaseModel):
    id: str
    title: str
    kind: str


class AssistantAnswer(BaseModel):
    answer: str
    sources: List[AssistantSource]


class AssistantStatusOut(BaseModel):
    configured: bool


AuthResponse.model_rebuild()
