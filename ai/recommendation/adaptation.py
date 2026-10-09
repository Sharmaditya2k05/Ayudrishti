"""Performance analysis: turning history into what to change next.

This is the "Adapt" step of the closed loop. It answers three questions the
recommender needs:

* Which alignment weaknesses keep recurring across sessions?
* Which asanas is the practitioner struggling with, and are they improving?
* Are they practising consistently enough to progress?

Everything here is descriptive statistics over recorded assessments. There
is no hidden model: each conclusion can be traced to the scores that
produced it, which is what lets the app tell the user *why* it changed their
plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .profile import PracticeHistory, UserProfile

# A component averaging below this across sessions counts as a weakness worth
# targeting.
WEAKNESS_THRESHOLD = 72.0

# An asana averaging below this is one the practitioner is struggling with.
STRUGGLE_THRESHOLD = 70.0

# Above this, a pose is considered mastered enough to progress beyond.
MASTERY_THRESHOLD = 88.0

# Minimum attempts before we draw any conclusion about a pose or component.
MIN_OBSERVATIONS = 2


@dataclass
class Weakness:
    """A recurring alignment problem, with the evidence for it."""

    component: str
    average_score: float
    observations: int
    affected_asanas: List[str] = field(default_factory=list)
    trend: Optional[float] = None

    @property
    def severity(self) -> float:
        """0-1, how much attention this deserves."""
        return max(0.0, min(1.0, (WEAKNESS_THRESHOLD - self.average_score) / 40.0))

    @property
    def improving(self) -> bool:
        return self.trend is not None and self.trend > 2.0

    def describe(self) -> str:
        label = self.component.replace("_", " ")
        if self.improving:
            return (
                f"Your {label} averages {self.average_score:.0f}% but is improving "
                f"(up {self.trend:.0f} points)."
            )
        return f"Your {label} averages {self.average_score:.0f}%, your weakest area."

    def to_dict(self) -> Dict[str, object]:
        return {
            "component": self.component,
            "average_score": round(self.average_score, 1),
            "observations": self.observations,
            "affected_asanas": list(self.affected_asanas),
            "trend": None if self.trend is None else round(self.trend, 1),
            "severity": round(self.severity, 3),
            "improving": self.improving,
            "description": self.describe(),
        }


@dataclass
class AsanaPerformance:
    """How the practitioner is doing on one asana."""

    asana_id: str
    average_score: float
    latest_score: float
    best_score: float
    attempts: int
    trend: Optional[float] = None
    days_since: Optional[int] = None
    weak_components: List[str] = field(default_factory=list)

    @property
    def struggling(self) -> bool:
        return self.average_score < STRUGGLE_THRESHOLD and self.attempts >= MIN_OBSERVATIONS

    @property
    def mastered(self) -> bool:
        return self.average_score >= MASTERY_THRESHOLD and self.attempts >= MIN_OBSERVATIONS

    @property
    def improving(self) -> bool:
        return self.trend is not None and self.trend > 2.0

    @property
    def plateaued(self) -> bool:
        return (
            self.trend is not None
            and abs(self.trend) <= 2.0
            and self.attempts >= 3
            and not self.mastered
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "asana_id": self.asana_id,
            "average_score": round(self.average_score, 1),
            "latest_score": round(self.latest_score, 1),
            "best_score": round(self.best_score, 1),
            "attempts": self.attempts,
            "trend": None if self.trend is None else round(self.trend, 1),
            "days_since": self.days_since,
            "weak_components": list(self.weak_components),
            "struggling": self.struggling,
            "mastered": self.mastered,
            "improving": self.improving,
            "plateaued": self.plateaued,
        }


@dataclass
class ConsistencyReport:
    sessions: int
    active_days: int
    span_days: int
    sessions_per_week: float
    target_per_week: int
    current_streak: int = 0
    longest_gap_days: int = 0

    @property
    def on_track(self) -> bool:
        return self.sessions_per_week >= self.target_per_week * 0.8

    def describe(self) -> str:
        if self.sessions == 0:
            return "No sessions recorded yet."
        if self.on_track:
            return (
                f"You are practising {self.sessions_per_week:.1f} times a week, "
                f"meeting your goal of {self.target_per_week}."
            )
        return (
            f"You are practising {self.sessions_per_week:.1f} times a week, "
            f"below your goal of {self.target_per_week}."
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "sessions": self.sessions,
            "active_days": self.active_days,
            "span_days": self.span_days,
            "sessions_per_week": round(self.sessions_per_week, 2),
            "target_per_week": self.target_per_week,
            "current_streak": self.current_streak,
            "longest_gap_days": self.longest_gap_days,
            "on_track": self.on_track,
            "description": self.describe(),
        }


@dataclass
class PerformanceAnalysis:
    """The complete picture the recommender adapts to."""

    weaknesses: List[Weakness] = field(default_factory=list)
    asana_performance: Dict[str, AsanaPerformance] = field(default_factory=dict)
    consistency: Optional[ConsistencyReport] = None
    overall_average: Optional[float] = None
    overall_trend: Optional[float] = None

    def struggling_asanas(self) -> List[str]:
        return [a for a, p in self.asana_performance.items() if p.struggling]

    def mastered_asanas(self) -> List[str]:
        return [a for a, p in self.asana_performance.items() if p.mastered]

    def primary_weakness(self) -> Optional[Weakness]:
        return self.weaknesses[0] if self.weaknesses else None

    @property
    def ready_to_progress(self) -> bool:
        """Whether to allow harder poses into the next session."""
        if self.overall_average is None:
            return False
        return (
            self.overall_average >= 80.0
            and len(self.mastered_asanas()) >= 2
            and not self.struggling_asanas()
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "overall_average": (
                None if self.overall_average is None else round(self.overall_average, 1)
            ),
            "overall_trend": (
                None if self.overall_trend is None else round(self.overall_trend, 1)
            ),
            "ready_to_progress": self.ready_to_progress,
            "weaknesses": [w.to_dict() for w in self.weaknesses],
            "asana_performance": {
                k: v.to_dict() for k, v in self.asana_performance.items()
            },
            "consistency": self.consistency.to_dict() if self.consistency else None,
        }


class PerformanceAnalyzer:
    """Derives weaknesses, per-asana performance and consistency from history."""

    def __init__(
        self,
        *,
        weakness_threshold: float = WEAKNESS_THRESHOLD,
        min_observations: int = MIN_OBSERVATIONS,
    ) -> None:
        self.weakness_threshold = weakness_threshold
        self.min_observations = min_observations

    def analyze(
        self,
        history: PracticeHistory,
        profile: Optional[UserProfile] = None,
        *,
        now: Optional[datetime] = None,
    ) -> PerformanceAnalysis:
        if not history:
            return PerformanceAnalysis(
                consistency=ConsistencyReport(
                    sessions=0,
                    active_days=0,
                    span_days=0,
                    sessions_per_week=0.0,
                    target_per_week=profile.practice_frequency if profile else 3,
                )
            )

        now = now or history.records[-1].performed_at

        return PerformanceAnalysis(
            weaknesses=self._weaknesses(history),
            asana_performance=self._per_asana(history, now=now),
            consistency=self._consistency(history, profile, now=now),
            overall_average=history.average_score(),
            overall_trend=self._overall_trend(history),
        )

    # ---- pieces ----------------------------------------------------------

    def _weaknesses(self, history: PracticeHistory) -> List[Weakness]:
        """Components scoring poorly across enough observations to trust."""
        out: List[Weakness] = []
        for component in history.all_components():
            rows = [
                r for r in history.records if component in r.component_scores
            ]
            if len(rows) < self.min_observations:
                continue
            scores = [r.component_scores[component] for r in rows]
            average = sum(scores) / len(scores)
            if average >= self.weakness_threshold:
                continue

            affected = sorted(
                {
                    r.asana_id
                    for r in rows
                    if r.component_scores[component] < self.weakness_threshold
                }
            )
            out.append(
                Weakness(
                    component=component,
                    average_score=average,
                    observations=len(rows),
                    affected_asanas=affected,
                    trend=self._component_trend(scores),
                )
            )

        out.sort(key=lambda w: w.average_score)
        return out

    @staticmethod
    def _component_trend(scores: List[float]) -> Optional[float]:
        if len(scores) < 4:
            return None
        half = len(scores) // 2
        earlier = scores[:half]
        later = scores[-half:]
        return sum(later) / len(later) - sum(earlier) / len(earlier)

    def _per_asana(
        self, history: PracticeHistory, *, now: datetime
    ) -> Dict[str, AsanaPerformance]:
        out: Dict[str, AsanaPerformance] = {}
        for asana_id in history.practised_asanas():
            rows = history.for_asana(asana_id)
            scores = [r.score for r in rows]

            # Which components drag this specific pose down.
            comp_totals: Dict[str, List[float]] = {}
            for r in rows:
                for comp, val in r.component_scores.items():
                    comp_totals.setdefault(comp, []).append(val)
            weak = sorted(
                (
                    comp
                    for comp, vals in comp_totals.items()
                    if sum(vals) / len(vals) < self.weakness_threshold
                ),
                key=lambda c: sum(comp_totals[c]) / len(comp_totals[c]),
            )

            out[asana_id] = AsanaPerformance(
                asana_id=asana_id,
                average_score=sum(scores) / len(scores),
                latest_score=scores[-1],
                best_score=max(scores),
                attempts=len(scores),
                trend=history.trend(asana_id),
                days_since=history.days_since(asana_id, now=now),
                weak_components=weak,
            )
        return out

    def _consistency(
        self,
        history: PracticeHistory,
        profile: Optional[UserProfile],
        *,
        now: datetime,
    ) -> ConsistencyReport:
        days = history.session_days()
        span = max((days[-1] - days[0]).days + 1, 1) if days else 1
        # Distinct calendar days, so several poses in one sitting count once.
        sessions = len(days)
        per_week = sessions / (span / 7.0) if span else 0.0

        gaps = [(days[i] - days[i - 1]).days for i in range(1, len(days))]
        longest_gap = max(gaps) if gaps else 0

        streak = 0
        cursor = now.date()
        day_set = set(days)
        # Count back from today, allowing one rest day between sessions.
        while cursor in day_set or (cursor - timedelta(days=1)) in day_set:
            if cursor in day_set:
                streak += 1
            cursor -= timedelta(days=1)
            if streak > 365:
                break

        return ConsistencyReport(
            sessions=sessions,
            active_days=sessions,
            span_days=span,
            sessions_per_week=per_week,
            target_per_week=profile.practice_frequency if profile else 3,
            current_streak=streak,
            longest_gap_days=longest_gap,
        )

    @staticmethod
    def _overall_trend(history: PracticeHistory) -> Optional[float]:
        scores = [r.score for r in history.records]
        if len(scores) < 4:
            return None
        half = len(scores) // 2
        return sum(scores[-half:]) / half - sum(scores[:half]) / half
