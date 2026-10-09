"""The personalised recommendation engine.

Deliberately a transparent, rule-based scorer rather than a learned model.
Every asana's score is the sum of named, signed contributions -- goal match,
difficulty fit, weakness targeting, recency -- and each contribution carries
the sentence that explains it. The user can therefore always be told *why*
a pose was chosen, which the spec requires of the MVP.

The same structure is what makes the loop adaptive: performance analysis
feeds in as additional scoring factors, so last session's weaknesses change
this session's plan without any separate code path.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from ..pose_assessment.asana import AsanaConfig, AsanaRegistry, get_registry
from .adaptation import PerformanceAnalysis, PerformanceAnalyzer
from .profile import PracticeHistory, UserProfile

# Order in which a well-formed session moves through the body.
STAGE_ORDER = ("warmup", "standing", "balance", "floor", "cooldown")

# Seconds of setup/transition assumed around each asana's hold, used to turn
# a requested session length into a realistic number of poses.
TRANSITION_SECONDS = 40


@dataclass
class ScoreFactor:
    """One named, explainable contribution to an asana's score."""

    name: str
    points: float
    explanation: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "points": round(self.points, 2),
            "explanation": self.explanation,
        }


@dataclass
class Recommendation:
    """One recommended asana, with its full reasoning."""

    asana_id: str
    asana_name: str
    difficulty: str
    score: float
    factors: List[ScoreFactor] = field(default_factory=list)
    duration_seconds: int = 30
    targeted_weakness: Optional[str] = None
    sequence_stage: str = "standing"
    # Unilateral poses are practised on both sides; anything else would leave
    # the practitioner asymmetrically worked.
    sides: int = 1
    # Which repeat of the core sequence this entry belongs to.
    round_number: int = 1
    # A reference photo of the pose, shown before the practitioner attempts
    # it, plus the attribution its licence requires.
    image_url: str = ""
    image_credit: str = ""

    @property
    def total_seconds(self) -> int:
        """Hold time across every side, excluding transitions."""
        return self.duration_seconds * self.sides

    @property
    def reason(self) -> str:
        """A short, user-facing justification built from the top factors."""
        positive = sorted(
            (f for f in self.factors if f.points > 0),
            key=lambda f: f.points,
            reverse=True,
        )
        if not positive:
            return "A balanced addition to your session."
        return " ".join(f.explanation for f in positive[:2])

    def to_dict(self) -> Dict[str, object]:
        return {
            "asana_id": self.asana_id,
            "asana_name": self.asana_name,
            "difficulty": self.difficulty,
            "score": round(self.score, 2),
            "reason": self.reason,
            "factors": [f.to_dict() for f in self.factors],
            "duration_seconds": self.duration_seconds,
            "sides": self.sides,
            "total_seconds": self.total_seconds,
            "targeted_weakness": self.targeted_weakness,
            "sequence_stage": self.sequence_stage,
            "round_number": self.round_number,
            "image_url": self.image_url,
            "image_credit": self.image_credit,
        }


@dataclass
class SessionPlan:
    """An ordered, time-budgeted practice session."""

    items: List[Recommendation] = field(default_factory=list)
    total_seconds: int = 0
    requested_minutes: int = 20
    rounds: int = 1
    focus: str = ""
    notes: List[str] = field(default_factory=list)
    generated_at: Optional[datetime] = None

    @property
    def asana_ids(self) -> List[str]:
        return [i.asana_id for i in self.items]

    @property
    def total_minutes(self) -> float:
        return self.total_seconds / 60.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "items": [i.to_dict() for i in self.items],
            "total_seconds": self.total_seconds,
            "total_minutes": round(self.total_minutes, 1),
            "requested_minutes": self.requested_minutes,
            "rounds": self.rounds,
            "focus": self.focus,
            "notes": list(self.notes),
            "generated_at": (
                self.generated_at.isoformat() if self.generated_at else None
            ),
        }


class RecommendationEngine:
    """Scores and sequences asanas for a given practitioner."""

    def __init__(
        self,
        registry: Optional[AsanaRegistry] = None,
        analyzer: Optional[PerformanceAnalyzer] = None,
    ) -> None:
        self.registry = registry or get_registry()
        self.analyzer = analyzer or PerformanceAnalyzer()

    # ---- scoring ---------------------------------------------------------

    def score_asana(
        self,
        config: AsanaConfig,
        profile: UserProfile,
        analysis: Optional[PerformanceAnalysis] = None,
        history: Optional[PracticeHistory] = None,
    ) -> Tuple[float, List[ScoreFactor], Optional[str]]:
        """Score one asana for one practitioner, with its reasoning."""
        factors: List[ScoreFactor] = []
        targeted_weakness: Optional[str] = None

        # --- goal alignment ------------------------------------------------
        matched = [g for g in profile.goals if g in config.target_goals]
        if matched:
            pts = 3.0 * len(matched)
            label = matched[0].replace("_", " ")
            factors.append(
                ScoreFactor("goal_match", pts, f"Supports your {label} goal.")
            )
        elif profile.goals:
            factors.append(
                ScoreFactor("goal_match", -1.0, "Not directly aligned with your goals.")
            )

        # --- focus areas ---------------------------------------------------
        focus_hits = [f for f in profile.focus_areas if f in config.focus_areas]
        if focus_hits:
            factors.append(
                ScoreFactor(
                    "focus_area",
                    2.0 * len(focus_hits),
                    f"Works the {focus_hits[0].replace('_', ' ')} you asked to focus on.",
                )
            )

        # --- difficulty fit -------------------------------------------------
        gap = config.difficulty_rank - profile.experience_rank
        if gap <= -1:
            factors.append(
                ScoreFactor("difficulty", 1.0, "A comfortable, familiar-level pose.")
            )
        elif gap == 0:
            factors.append(
                ScoreFactor("difficulty", 3.0, f"Matched to your {profile.experience} level.")
            )
        elif gap == 1:
            # One step up is a stretch goal, but only once the basics hold.
            ready = analysis.ready_to_progress if analysis else False
            factors.append(
                ScoreFactor(
                    "difficulty",
                    1.5 if ready else -3.0,
                    (
                        "A step up, and your recent scores show you are ready."
                        if ready
                        else "Harder than your current level."
                    ),
                )
            )
        else:
            factors.append(
                ScoreFactor("difficulty", -8.0, "Too advanced for your current level.")
            )

        # --- intensity vs age ------------------------------------------------
        if profile.is_senior and config.intensity >= 4:
            factors.append(
                ScoreFactor(
                    "intensity", -2.5, "A demanding pose, kept lighter in your plan."
                )
            )

        # --- adaptive factors -------------------------------------------------
        if analysis:
            weakness_pts, weakness_factor, targeted_weakness = self._weakness_factor(
                config, analysis
            )
            if weakness_factor:
                factors.append(weakness_factor)

            perf = analysis.asana_performance.get(config.id)
            if perf:
                factors.extend(self._history_factors(config, perf, analysis))

        # --- variety / recency -------------------------------------------------
        if history:
            days = history.days_since(config.id)
            attempts = history.attempts(config.id)
            if days is not None and days <= 1 and attempts > 0:
                perf = analysis.asana_performance.get(config.id) if analysis else None
                if perf and perf.struggling:
                    # Repetition is the point when a pose needs work.
                    factors.append(
                        ScoreFactor(
                            "repetition",
                            1.5,
                            "Repeated deliberately so you can build on yesterday's practice.",
                        )
                    )
                else:
                    factors.append(
                        ScoreFactor(
                            "recency", -2.0, "Practised very recently, so rotating for variety."
                        )
                    )
            elif attempts == 0:
                factors.append(
                    ScoreFactor("novelty", 1.5, "A new pose to broaden your practice.")
                )

        # --- explicit avoidance -------------------------------------------------
        if config.id in profile.avoid:
            factors.append(
                ScoreFactor("avoided", -100.0, "You chose to exclude this pose.")
            )

        total = sum(f.points for f in factors)
        return total, factors, targeted_weakness

    def _weakness_factor(
        self, config: AsanaConfig, analysis: PerformanceAnalysis
    ) -> Tuple[float, Optional[ScoreFactor], Optional[str]]:
        """Reward poses that address a recurring weakness."""
        for weakness in analysis.weaknesses:
            # A pose helps either by explicitly declaring it corrects this
            # area, or by exercising that component itself.
            corrects = weakness.component in config.corrects
            exercises = weakness.component in config.components
            if not (corrects or exercises):
                continue
            pts = 5.0 * weakness.severity + (2.0 if corrects else 0.0)
            label = weakness.component.replace("_", " ")
            return (
                pts,
                ScoreFactor(
                    "targets_weakness",
                    pts,
                    f"Chosen to work on your {label}, your weakest area.",
                ),
                weakness.component,
            )
        return 0.0, None, None

    def _history_factors(
        self,
        config: AsanaConfig,
        perf,
        analysis: PerformanceAnalysis,
    ) -> List[ScoreFactor]:
        out: List[ScoreFactor] = []
        if perf.struggling:
            out.append(
                ScoreFactor(
                    "needs_work",
                    3.5,
                    f"You are averaging {perf.average_score:.0f}% here, so it is worth revisiting.",
                )
            )
        elif perf.mastered:
            out.append(
                ScoreFactor(
                    "mastered",
                    -2.0,
                    f"You have this one solid at {perf.average_score:.0f}%.",
                )
            )
        if perf.plateaued:
            out.append(
                ScoreFactor(
                    "plateau", 1.5, "Your score here has stalled, so more practice should help."
                )
            )
        if perf.days_since is not None and perf.days_since >= 14:
            out.append(
                ScoreFactor(
                    "refresher",
                    1.5,
                    f"You have not practised this in {perf.days_since} days.",
                )
            )
        return out

    # ---- session assembly ------------------------------------------------

    def recommend(
        self,
        profile: UserProfile,
        history: Optional[PracticeHistory] = None,
        *,
        limit: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> List[Recommendation]:
        """Rank every asana for this practitioner, best first."""
        history = history or PracticeHistory()
        analysis = self.analyzer.analyze(history, profile, now=now) if history else None

        out: List[Recommendation] = []
        for config in self.registry.all():
            if not self.is_appropriate(config, profile, analysis):
                continue
            score, factors, weakness = self.score_asana(
                config, profile, analysis, history
            )
            out.append(
                Recommendation(
                    asana_id=config.id,
                    asana_name=config.english_name,
                    difficulty=config.difficulty,
                    score=score,
                    factors=factors,
                    duration_seconds=config.hold_seconds,
                    targeted_weakness=weakness,
                    sequence_stage=config.sequence_stage,
                    sides=2 if config.is_unilateral else 1,
                    image_url=config.image_url,
                    image_credit=config.image_credit,
                )
            )

        out.sort(key=lambda r: (-r.score, r.asana_id))
        return out[:limit] if limit else out

    def is_appropriate(
        self,
        config: AsanaConfig,
        profile: UserProfile,
        analysis: Optional[PerformanceAnalysis] = None,
    ) -> bool:
        """Hard eligibility gate, applied before any scoring.

        Scoring alone is not enough to keep an over-hard pose out of a
        beginner's plan: if the library ran short of good options, a
        negatively-scored advanced pose would still be selected. A pose more
        than one level above the practitioner is never offered, and one level
        above only once their recent scores show they are ready.
        """
        if config.id in profile.avoid:
            return False
        headroom = 1 if (analysis and analysis.ready_to_progress) else 0
        return config.difficulty_rank <= profile.experience_rank + headroom

    def build_session(
        self,
        profile: UserProfile,
        history: Optional[PracticeHistory] = None,
        *,
        duration_minutes: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> SessionPlan:
        """Assemble a time-budgeted, well-sequenced session.

        Ranking alone is not a session: a list of the five highest-scoring
        poses could open with a deep backbend and never warm up. Selection
        therefore fills the time budget from the ranking, then reorders into
        the standard warmup -> standing -> floor -> cooldown arc.
        """
        history = history or PracticeHistory()
        minutes = duration_minutes or profile.preferred_duration
        budget = max(minutes, 5) * 60
        analysis = self.analyzer.analyze(history, profile, now=now)

        eligible = self.recommend(profile, history, now=now)
        if not eligible:
            return SessionPlan(
                requested_minutes=minutes,
                focus="No suitable poses",
                notes=["No asanas in the library match your profile settings."],
                generated_at=now or datetime.now(),
            )

        # Roughly one asana per two and a half minutes keeps holds long enough
        # to assess properly without turning a session into a slideshow.
        target_count = max(3, min(round(minutes / 2.5), len(eligible)))

        chosen: List[Recommendation] = []
        stage_counts: Dict[str, int] = {}

        warmup = self._first_of_stage(eligible, "warmup")
        cooldown = self._first_of_stage(eligible, "cooldown")

        if warmup is not None:
            chosen.append(warmup)
            stage_counts["warmup"] = 1

        for rec in eligible:
            if len(chosen) >= target_count - (1 if cooldown is not None else 0):
                break
            if rec is warmup or rec is cooldown:
                continue
            # Cap any one stage so a session cannot become five standing poses.
            if stage_counts.get(rec.sequence_stage, 0) >= 3:
                continue
            chosen.append(rec)
            stage_counts[rec.sequence_stage] = stage_counts.get(rec.sequence_stage, 0) + 1

        if cooldown is not None:
            chosen.append(cooldown)

        chosen = self._sequence(chosen)
        chosen, rounds = self._add_rounds(chosen, budget)
        used = self._fit_to_budget(chosen, budget)

        notes = self._notes(profile, analysis)
        if rounds > 1:
            notes.append(
                f"The main sequence is repeated for {rounds} rounds to fill your "
                f"{minutes}-minute session."
            )

        return SessionPlan(
            items=chosen,
            total_seconds=used,
            requested_minutes=minutes,
            rounds=rounds,
            focus=self._focus_label(profile, analysis),
            notes=notes,
            generated_at=now or datetime.now(),
        )

    @staticmethod
    def _add_rounds(
        items: List[Recommendation], budget: int
    ) -> Tuple[List[Recommendation], int]:
        """Repeat the core sequence when a short library cannot fill the time.

        A beginner has only a handful of appropriate poses, so a 20-minute
        session cannot be built from distinct asanas alone. Practising the
        core sequence for several rounds is how this is actually taught, and
        it beats either padding holds to unsafe lengths or silently handing
        back a shorter session than the user asked for.
        """
        core = [i for i in items if i.sequence_stage not in ("warmup", "cooldown")]
        if len(core) < 2:
            return items, 1

        warmup = [i for i in items if i.sequence_stage == "warmup"]
        cooldown = [i for i in items if i.sequence_stage == "cooldown"]

        def cost(seq: Sequence[Recommendation]) -> int:
            return sum(i.total_seconds + TRANSITION_SECONDS for i in seq)

        fixed_cost = cost(warmup) + cost(cooldown)
        core_cost = cost(core)
        if core_cost <= 0:
            return items, 1

        # Only add a round if the current plan is meaningfully short and the
        # extra round genuinely fits.
        # Prefer fewer rounds with longer holds over many rushed ones: only
        # add a round if it fits within the budget outright, since overshoot
        # would force _fit_to_budget to compress holds below their reference.
        rounds = 1
        while (
            rounds < 4
            and fixed_cost + core_cost * (rounds + 1) <= budget
            and fixed_cost + core_cost * rounds < budget * 0.8
        ):
            rounds += 1

        if rounds == 1:
            return items, 1

        # Copy each repeat: _fit_to_budget mutates duration in place, so
        # sharing one object across rounds would scale it once per round.
        expanded = list(warmup)
        for round_index in range(rounds):
            for item in core:
                expanded.append(replace(item, round_number=round_index + 1))
        expanded.extend(cooldown)
        return expanded, rounds

    @staticmethod
    def _fit_to_budget(items: List[Recommendation], budget: int) -> int:
        """Stretch or trim holds so the session actually lasts as long as asked.

        Selection fixes *which* poses to do; this fixes *how long*. Holds are
        scaled toward the budget within safe bounds -- never shorter than half
        the reference hold, never more than double it, since an extremely long
        hold is a different exercise rather than a longer version of the same
        one.
        """
        if not items:
            return 0

        transitions = TRANSITION_SECONDS * len(items)
        base_hold = sum(i.total_seconds for i in items)
        available = max(budget - transitions, 30)

        if base_hold > 0:
            scale = max(0.5, min(available / base_hold, 2.0))
            for item in items:
                item.duration_seconds = max(10, int(round(item.duration_seconds * scale / 5) * 5))

        return sum(i.total_seconds for i in items) + transitions

    @staticmethod
    def _first_of_stage(
        recs: Sequence[Recommendation], stage: str
    ) -> Optional[Recommendation]:
        for rec in recs:
            if rec.sequence_stage == stage:
                return rec
        return None

    @staticmethod
    def _sequence(recs: List[Recommendation]) -> List[Recommendation]:
        """Order poses into the standard session arc.

        Within a stage the ranking order is preserved, so the most relevant
        pose in each phase comes first while the overall arc stays safe.
        """
        def key(rec: Recommendation) -> Tuple[int, float]:
            try:
                stage = STAGE_ORDER.index(rec.sequence_stage)
            except ValueError:
                stage = len(STAGE_ORDER)
            return (stage, -rec.score)

        return sorted(recs, key=key)

    @staticmethod
    def _focus_label(profile: UserProfile, analysis: PerformanceAnalysis) -> str:
        weakness = analysis.primary_weakness()
        if weakness:
            return f"Improving {weakness.component.replace('_', ' ')}"
        if profile.goals:
            return profile.goals[0].replace("_", " ").title()
        return "Balanced practice"

    @staticmethod
    def _notes(profile: UserProfile, analysis: PerformanceAnalysis) -> List[str]:
        notes: List[str] = []
        weakness = analysis.primary_weakness()
        if weakness:
            notes.append(weakness.describe())
        if analysis.consistency and analysis.consistency.sessions > 0:
            notes.append(analysis.consistency.describe())
        if analysis.ready_to_progress:
            notes.append(
                "Your recent scores are strong, so this session introduces a harder pose."
            )
        struggling = analysis.struggling_asanas()
        if struggling:
            notes.append(
                f"Revisiting {len(struggling)} pose(s) you have found difficult."
            )
        return notes
