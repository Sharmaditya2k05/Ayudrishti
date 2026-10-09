"""Turning rule results into scores.

Scores here are always derived from measured rule outcomes. Nothing in this
module invents a number: if the camera could not see the landmarks a rule
needs, that rule contributes nothing and the reported confidence drops
instead of the score being padded.

Aggregation is a weighted mean over *available* rules. Weighting matters
because not every alignment point is equally important -- a collapsed front
knee in Warrior II is a safety issue, a slightly low rear arm is cosmetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

from ..pose_assessment.rules import RuleResult

# A pose scored below this is treated as "needs work" when the recommender
# looks for weaknesses to target in future sessions.
WEAKNESS_THRESHOLD = 70.0

# Below this share of rule weight being measurable, we consider the
# assessment untrustworthy and say so rather than reporting a confident score.
MIN_CONFIDENCE = 0.5


@dataclass
class ComponentScore:
    """Score for one anatomical grouping, e.g. "legs" or "torso"."""

    component: str
    label: str
    score: float  # 0 - 100
    weight: float
    rule_count: int
    available_count: int
    issues: List[str] = field(default_factory=list)

    @property
    def confidence(self) -> float:
        return self.available_count / self.rule_count if self.rule_count else 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "component": self.component,
            "label": self.label,
            "score": round(self.score, 1),
            "weight": self.weight,
            "rule_count": self.rule_count,
            "available_count": self.available_count,
            "confidence": round(self.confidence, 3),
            "issues": list(self.issues),
        }


@dataclass
class PoseScore:
    """Overall score for one asana attempt, with its component breakdown."""

    asana_id: str
    overall: float  # 0 - 100
    components: List[ComponentScore] = field(default_factory=list)
    rule_results: List[RuleResult] = field(default_factory=list)
    confidence: float = 1.0
    deviation_count: int = 0

    @property
    def reliable(self) -> bool:
        return self.confidence >= MIN_CONFIDENCE

    @property
    def grade(self) -> str:
        return grade_label(self.overall)

    def component_map(self) -> Dict[str, float]:
        return {c.component: round(c.score, 1) for c in self.components}

    def weakest_component(self) -> Optional[ComponentScore]:
        available = [c for c in self.components if c.available_count > 0]
        return min(available, key=lambda c: c.score) if available else None

    def to_dict(self, include_rules: bool = True) -> Dict[str, object]:
        out: Dict[str, object] = {
            "asana_id": self.asana_id,
            "overall": round(self.overall, 1),
            "grade": self.grade,
            "confidence": round(self.confidence, 3),
            "reliable": self.reliable,
            "deviation_count": self.deviation_count,
            "components": [c.to_dict() for c in self.components],
        }
        if include_rules:
            out["rules"] = [r.to_dict() for r in self.rule_results]
        return out


@dataclass
class SessionScore:
    """Aggregate performance across all asanas in one practice session."""

    overall: float
    pose_scores: Dict[str, float] = field(default_factory=dict)
    best_pose: Optional[str] = None
    weakest_pose: Optional[str] = None
    total_corrections: int = 0
    total_deviations: int = 0
    asana_count: int = 0

    def to_dict(self) -> Dict[str, object]:
        return {
            "overall": round(self.overall, 1),
            "grade": grade_label(self.overall),
            "pose_scores": {k: round(v, 1) for k, v in self.pose_scores.items()},
            "best_pose": self.best_pose,
            "weakest_pose": self.weakest_pose,
            "total_corrections": self.total_corrections,
            "total_deviations": self.total_deviations,
            "asana_count": self.asana_count,
        }


def grade_label(score: float) -> str:
    """Plain-language band for a 0-100 score, for the UI to display."""
    if score >= 90:
        return "excellent"
    if score >= 80:
        return "good"
    if score >= 70:
        return "fair"
    if score >= 55:
        return "needs work"
    return "keep practising"


def aggregate_rules(
    asana_id: str,
    results: Sequence[RuleResult],
    component_labels: Optional[Dict[str, str]] = None,
) -> PoseScore:
    """Combine rule results into component scores and one overall score."""
    component_labels = component_labels or {}

    by_component: Dict[str, List[RuleResult]] = {}
    for res in results:
        by_component.setdefault(res.component, []).append(res)

    components: List[ComponentScore] = []
    for name, group in by_component.items():
        available = [r for r in group if r.available]
        total_weight = sum(r.weight for r in available)
        if total_weight > 0:
            score = sum(r.score * r.weight for r in available) / total_weight * 100.0
        else:
            # Nothing measurable in this component -- report 0 but with zero
            # confidence, so callers can tell "unseen" from "done badly".
            score = 0.0
        issues = [r.rule_id for r in available if r.status in ("low", "high")]
        components.append(
            ComponentScore(
                component=name,
                label=component_labels.get(name, name.replace("_", " ").title()),
                score=score,
                weight=total_weight,
                rule_count=len(group),
                available_count=len(available),
                issues=issues,
            )
        )

    components.sort(key=lambda c: c.component)

    available_all = [r for r in results if r.available]
    total_weight = sum(r.weight for r in available_all)
    overall = (
        sum(r.score * r.weight for r in available_all) / total_weight * 100.0
        if total_weight > 0
        else 0.0
    )

    # Confidence is the share of rule weight we could actually measure.
    declared_weight = sum(r.weight for r in results)
    confidence = total_weight / declared_weight if declared_weight > 0 else 0.0

    deviations = sum(1 for r in available_all if r.status in ("low", "high"))

    return PoseScore(
        asana_id=asana_id,
        overall=overall,
        components=components,
        rule_results=list(results),
        confidence=confidence,
        deviation_count=deviations,
    )


def score_session(
    pose_scores: Dict[str, Iterable[float]],
    *,
    corrections: int = 0,
    deviations: int = 0,
) -> SessionScore:
    """Roll per-asana scores up into a session score.

    Each asana is first averaged across however many assessments it received
    during the session, then the asanas are averaged equally. Averaging in
    two stages stops a pose that happened to be sampled more often from
    dominating the session score.
    """
    per_asana: Dict[str, float] = {}
    for asana_id, scores in pose_scores.items():
        vals = [float(s) for s in scores]
        if vals:
            per_asana[asana_id] = sum(vals) / len(vals)

    if not per_asana:
        return SessionScore(overall=0.0, asana_count=0)

    overall = sum(per_asana.values()) / len(per_asana)
    best = max(per_asana, key=lambda k: per_asana[k])
    worst = min(per_asana, key=lambda k: per_asana[k])

    return SessionScore(
        overall=overall,
        pose_scores=per_asana,
        best_pose=best,
        weakest_pose=worst,
        total_corrections=corrections,
        total_deviations=deviations,
        asana_count=len(per_asana),
    )
