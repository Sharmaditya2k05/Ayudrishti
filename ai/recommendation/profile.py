"""User profile and practice history, as the recommender sees them.

These are plain dataclasses rather than database models on purpose: the AI
layer must stay usable from a script, a test or a notebook without a
PostgreSQL connection. The backend maps its ORM rows onto these.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence

EXPERIENCE_LEVELS = ("beginner", "intermediate", "advanced")

GOALS = (
    "flexibility",
    "strength",
    "relaxation",
    "stress_reduction",
    "mobility",
    "general_fitness",
    "beginner_learning",
    "balance",
)


@dataclass
class UserProfile:
    """Everything about the practitioner that shapes a recommendation."""

    user_id: int = 0
    name: str = ""
    age: Optional[int] = None
    experience: str = "beginner"
    goals: List[str] = field(default_factory=list)
    preferred_duration: int = 20  # minutes
    practice_frequency: int = 3  # sessions per week
    focus_areas: List[str] = field(default_factory=list)
    # Poses to leave out entirely, e.g. because of a known injury.
    avoid: List[str] = field(default_factory=list)

    @property
    def experience_rank(self) -> int:
        try:
            return EXPERIENCE_LEVELS.index(self.experience)
        except ValueError:
            return 0

    @property
    def is_senior(self) -> bool:
        """Whether to bias toward gentler sequencing.

        Not a medical judgement -- purely a conservative default for session
        intensity, which the practitioner can override in their profile.
        """
        return self.age is not None and self.age >= 60


@dataclass
class PoseRecord:
    """One assessed attempt at one asana, as stored in session history."""

    asana_id: str
    score: float
    performed_at: datetime
    component_scores: Dict[str, float] = field(default_factory=dict)
    deviation_count: int = 0
    corrections: List[str] = field(default_factory=list)
    session_id: Optional[int] = None

    @property
    def day(self) -> date:
        return self.performed_at.date()


@dataclass
class PracticeHistory:
    """A practitioner's assessed history, ordered oldest to newest."""

    records: List[PoseRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.records.sort(key=lambda r: r.performed_at)

    # ---- slicing ---------------------------------------------------------

    def for_asana(self, asana_id: str) -> List[PoseRecord]:
        return [r for r in self.records if r.asana_id == asana_id]

    def since(self, when: datetime) -> "PracticeHistory":
        return PracticeHistory([r for r in self.records if r.performed_at >= when])

    def recent(self, days: int = 30) -> "PracticeHistory":
        if not self.records:
            return PracticeHistory([])
        cutoff = self.records[-1].performed_at - timedelta(days=days)
        return self.since(cutoff)

    # ---- summaries -------------------------------------------------------

    def practised_asanas(self) -> List[str]:
        seen: List[str] = []
        for r in self.records:
            if r.asana_id not in seen:
                seen.append(r.asana_id)
        return seen

    def average_score(self, asana_id: Optional[str] = None) -> Optional[float]:
        rows = self.for_asana(asana_id) if asana_id else self.records
        if not rows:
            return None
        return sum(r.score for r in rows) / len(rows)

    def latest_score(self, asana_id: str) -> Optional[float]:
        rows = self.for_asana(asana_id)
        return rows[-1].score if rows else None

    def attempts(self, asana_id: str) -> int:
        return len(self.for_asana(asana_id))

    def last_practised(self, asana_id: str) -> Optional[datetime]:
        rows = self.for_asana(asana_id)
        return rows[-1].performed_at if rows else None

    def days_since(self, asana_id: str, *, now: Optional[datetime] = None) -> Optional[int]:
        last = self.last_practised(asana_id)
        if last is None:
            return None
        now = now or (self.records[-1].performed_at if self.records else datetime.now())
        return max((now - last).days, 0)

    def session_days(self) -> List[date]:
        return sorted({r.day for r in self.records})

    def trend(self, asana_id: str, window: int = 3) -> Optional[float]:
        """Score change for an asana: recent average minus earlier average.

        Positive means improving. Returns None until there is enough history
        for the comparison to mean anything.
        """
        rows = self.for_asana(asana_id)
        if len(rows) < 2:
            return None
        window = max(1, min(window, len(rows) // 2))
        earlier = rows[:window]
        later = rows[-window:]
        return (sum(r.score for r in later) / len(later)) - (
            sum(r.score for r in earlier) / len(earlier)
        )

    def component_average(self, component: str) -> Optional[float]:
        """Average score for one alignment component across all asanas.

        This is what surfaces cross-cutting weaknesses -- a practitioner
        whose knee alignment is poor in Warrior II is usually also losing
        marks for it in Chair Pose.
        """
        vals = [
            r.component_scores[component]
            for r in self.records
            if component in r.component_scores
        ]
        return sum(vals) / len(vals) if vals else None

    def all_components(self) -> List[str]:
        names: List[str] = []
        for r in self.records:
            for c in r.component_scores:
                if c not in names:
                    names.append(c)
        return names

    def __len__(self) -> int:
        return len(self.records)

    def __bool__(self) -> bool:
        return bool(self.records)
