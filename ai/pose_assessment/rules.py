"""Pose-specific alignment rules and their evaluation.

A rule is one checkable statement about a posture -- "the front knee should
be flexed to roughly 90 degrees", "the wrists should be level with each
other". Each asana owns a list of them, loaded from JSON in
``data/pose_rules/``, so a new asana can be added without touching this
module.

Deliberately there is no universal joint-angle threshold here. Every rule
carries its own target range, its own tolerance and its own feedback text,
because 90 degrees of knee flexion is correct in Warrior II and wrong in
Tadasana.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from ..pose_detection.landmarks import DEFAULT_VISIBILITY_THRESHOLD, PoseFrame
from . import geometry as geo

Point = Tuple[float, float]

# Placeholders used in unilateral asanas (Warrior II, Trikonasana, Tree...)
# so one rule set can describe both the left-lead and right-lead variant.
SIDE_PREFIXES = ("lead", "rear")


class RuleConfigError(ValueError):
    """Raised when an asana JSON file describes a rule we cannot evaluate."""


# --------------------------------------------------------------------------
# Measurement functions
# --------------------------------------------------------------------------
# Each takes the resolved landmark points plus the body scale and returns a
# single number, or None when the measurement is undefined for this frame.
# The unit each returns is documented because it determines how the rule's
# ``target`` and ``tolerance`` in JSON should be read.

def _m_angle(p: Sequence[Point], scale: float) -> Optional[float]:
    """Interior joint angle at the middle landmark. Unit: degrees."""
    return geo.joint_angle(p[0], p[1], p[2])


def _m_segment_vertical(p: Sequence[Point], scale: float) -> Optional[float]:
    """Segment tilt away from vertical. Unit: degrees (0 = upright)."""
    return geo.segment_angle_to_vertical(p[0], p[1])


def _m_segment_horizontal(p: Sequence[Point], scale: float) -> Optional[float]:
    """Segment tilt away from horizontal. Unit: degrees (0 = level)."""
    return geo.segment_angle_to_horizontal(p[0], p[1])


def _m_straightness(p: Sequence[Point], scale: float) -> Optional[float]:
    """Bend in a three-point chain. Unit: degrees (0 = straight line)."""
    return geo.collinearity(p[0], p[1], p[2])


def _m_horizontal_gap(p: Sequence[Point], scale: float) -> Optional[float]:
    """Unsigned horizontal separation. Unit: torso lengths."""
    return geo.horizontal_offset(p[0], p[1], scale)


def _m_vertical_gap(p: Sequence[Point], scale: float) -> Optional[float]:
    """Unsigned vertical separation. Unit: torso lengths."""
    return geo.vertical_offset(p[0], p[1], scale)


def _m_signed_vertical_gap(p: Sequence[Point], scale: float) -> Optional[float]:
    """How far the first point is above the second. Unit: torso lengths."""
    return geo.signed_vertical_offset(p[0], p[1], scale)


def _m_signed_horizontal_gap(p: Sequence[Point], scale: float) -> Optional[float]:
    """How far the first point is right of the second. Unit: torso lengths."""
    return geo.signed_horizontal_offset(p[0], p[1], scale)


def _m_distance_ratio(p: Sequence[Point], scale: float) -> Optional[float]:
    """dist(p0,p1) / dist(p2,p3). Unit: dimensionless ratio."""
    return geo.distance_ratio(p[0], p[1], p[2], p[3])


def _m_point_line_distance(p: Sequence[Point], scale: float) -> Optional[float]:
    """Distance from p0 to the line p1-p2. Unit: torso lengths."""
    return geo.point_line_distance(p[0], p[1], p[2], scale)


def _m_distance(p: Sequence[Point], scale: float) -> Optional[float]:
    """Straight-line distance between two points. Unit: torso lengths."""
    if scale < 1e-9:
        return None
    return geo.distance(p[0], p[1]) / scale


@dataclass(frozen=True)
class MeasurementSpec:
    fn: Callable[[Sequence[Point], float], Optional[float]]
    arity: int
    unit: str


MEASUREMENTS: Dict[str, MeasurementSpec] = {
    "angle": MeasurementSpec(_m_angle, 3, "degrees"),
    "segment_vertical": MeasurementSpec(_m_segment_vertical, 2, "degrees"),
    "segment_horizontal": MeasurementSpec(_m_segment_horizontal, 2, "degrees"),
    "straightness": MeasurementSpec(_m_straightness, 3, "degrees"),
    "horizontal_gap": MeasurementSpec(_m_horizontal_gap, 2, "torso"),
    "vertical_gap": MeasurementSpec(_m_vertical_gap, 2, "torso"),
    "signed_vertical_gap": MeasurementSpec(_m_signed_vertical_gap, 2, "torso"),
    "signed_horizontal_gap": MeasurementSpec(_m_signed_horizontal_gap, 2, "torso"),
    "distance_ratio": MeasurementSpec(_m_distance_ratio, 4, "ratio"),
    "point_line_distance": MeasurementSpec(_m_point_line_distance, 3, "torso"),
    "distance": MeasurementSpec(_m_distance, 2, "torso"),
}


# --------------------------------------------------------------------------
# Rule definition and result
# --------------------------------------------------------------------------


@dataclass
class RuleResult:
    """Outcome of evaluating one rule against one frame."""

    rule_id: str
    component: str
    body_part: str
    measurement: str
    unit: str
    value: Optional[float]
    target_min: float
    target_max: float
    score: float  # 0.0 - 1.0
    weight: float
    status: str  # "ok" | "low" | "high" | "unavailable"
    feedback: Optional[str]
    landmarks: List[str] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return self.status != "unavailable"

    @property
    def severity(self) -> float:
        """How wrong this is, 0 (perfect) to 1 (maximally off)."""
        return 0.0 if not self.available else 1.0 - self.score

    def to_dict(self) -> Dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "component": self.component,
            "body_part": self.body_part,
            "measurement": self.measurement,
            "unit": self.unit,
            "value": None if self.value is None else round(self.value, 2),
            "target_min": self.target_min,
            "target_max": self.target_max,
            "score": round(self.score, 4),
            "weight": self.weight,
            "status": self.status,
            "feedback": self.feedback,
            "landmarks": self.landmarks,
        }


@dataclass
class Rule:
    """One alignment requirement for one asana.

    ``target_min``/``target_max`` bound the acceptable range for the
    measurement. ``tolerance`` sets how far outside that range the value can
    drift before the rule scores zero, which is what makes scoring a smooth
    gradient rather than a pass/fail flag -- a knee 5 degrees off should not
    look the same as a knee 40 degrees off.
    """

    id: str
    component: str
    measurement: str
    landmarks: List[str]
    target_min: float
    target_max: float
    tolerance: float
    weight: float = 1.0
    body_part: str = ""
    feedback_low: str = ""
    feedback_high: str = ""
    # Recognition rules identify *which* asana this is; assessment rules
    # judge how well it is done. Most rules do both, but a few exist purely
    # to discriminate between similar-looking poses.
    signature: bool = True
    optional: bool = False
    # A rule that separates this asana from a look-alike (hips above
    # shoulders in Downward Dog vs below them when seated). Recognition
    # keeps these at full tightness -- widening them would erase exactly
    # the distinction they exist to make.
    discriminative: bool = False

    def __post_init__(self) -> None:
        if self.measurement not in MEASUREMENTS:
            raise RuleConfigError(
                f"rule '{self.id}': unknown measurement '{self.measurement}'. "
                f"Known: {sorted(MEASUREMENTS)}"
            )
        spec = MEASUREMENTS[self.measurement]
        if len(self.landmarks) != spec.arity:
            raise RuleConfigError(
                f"rule '{self.id}': measurement '{self.measurement}' needs "
                f"{spec.arity} landmarks, got {len(self.landmarks)}"
            )
        if self.target_min > self.target_max:
            raise RuleConfigError(
                f"rule '{self.id}': target_min {self.target_min} exceeds "
                f"target_max {self.target_max}"
            )
        if self.tolerance <= 0:
            raise RuleConfigError(f"rule '{self.id}': tolerance must be positive")
        if not self.body_part:
            self.body_part = self.component

    @property
    def unit(self) -> str:
        return MEASUREMENTS[self.measurement].unit

    # ---- evaluation ---------------------------------------------------

    def resolve_landmarks(self, side_map: Optional[Dict[str, str]] = None) -> List[str]:
        """Substitute ``lead_``/``rear_`` placeholders for real side names."""
        if not side_map:
            return list(self.landmarks)
        out: List[str] = []
        for name in self.landmarks:
            for prefix in SIDE_PREFIXES:
                if name.startswith(prefix + "_"):
                    name = side_map[prefix] + "_" + name[len(prefix) + 1 :]
                    break
            out.append(name)
        return out

    def evaluate(
        self,
        frame: PoseFrame,
        *,
        side_map: Optional[Dict[str, str]] = None,
        visibility_threshold: float = DEFAULT_VISIBILITY_THRESHOLD,
        tolerance_scale: float = 1.0,
    ) -> RuleResult:
        names = self.resolve_landmarks(side_map)

        def unavailable() -> RuleResult:
            return RuleResult(
                rule_id=self.id,
                component=self.component,
                body_part=self.body_part,
                measurement=self.measurement,
                unit=self.unit,
                value=None,
                target_min=self.target_min,
                target_max=self.target_max,
                score=0.0,
                weight=self.weight,
                status="unavailable",
                feedback=None,
                landmarks=names,
            )

        # Refuse to guess: a rule whose landmarks the camera cannot see is
        # reported as unavailable and left out of the score entirely.
        if frame.missing(names, visibility_threshold):
            return unavailable()

        scale = frame.torso_length
        points = [frame.landmarks[n].xy for n in names]
        value = MEASUREMENTS[self.measurement].fn(points, scale)
        if value is None:
            return unavailable()

        score, status = self.score_value(value, tolerance_scale=tolerance_scale)
        feedback = None
        if status == "low":
            feedback = self.feedback_low or None
        elif status == "high":
            feedback = self.feedback_high or None

        return RuleResult(
            rule_id=self.id,
            component=self.component,
            body_part=self.body_part,
            measurement=self.measurement,
            unit=self.unit,
            value=value,
            target_min=self.target_min,
            target_max=self.target_max,
            score=score,
            weight=self.weight,
            status=status,
            feedback=feedback,
            landmarks=names,
        )

    def score_value(
        self, value: float, *, tolerance_scale: float = 1.0
    ) -> Tuple[float, str]:
        """Map a measured value to a 0-1 score and a direction label.

        Inside the target range scores 1.0. Outside, the score falls
        linearly with distance from the nearest edge, reaching 0.0 once the
        value is a full ``tolerance`` beyond it.

        ``tolerance_scale`` widens that band without changing the target.
        Recognition uses a scale above 1 because identifying *which* pose
        someone is attempting is a far more forgiving question than judging
        how well they are doing it -- a wobbly beginner's Warrior II is
        still unmistakably a Warrior II.
        """
        tolerance = self.tolerance * max(tolerance_scale, 1e-6)
        if value < self.target_min:
            excess = self.target_min - value
            status = "low"
        elif value > self.target_max:
            excess = value - self.target_max
            status = "high"
        else:
            return 1.0, "ok"
        score = geo.clamp(1.0 - (excess / tolerance), 0.0, 1.0)
        return score, status

    # ---- serialisation -------------------------------------------------

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "Rule":
        target = data.get("target")
        if isinstance(target, (list, tuple)) and len(target) == 2:
            tmin, tmax = float(target[0]), float(target[1])
        else:
            tmin = float(data.get("target_min", 0.0))
            tmax = float(data.get("target_max", 0.0))

        feedback = data.get("feedback") or {}
        if isinstance(feedback, str):
            feedback = {"low": feedback, "high": feedback}

        rule_id = str(data.get("id", ""))
        if not rule_id:
            raise RuleConfigError("every rule needs an 'id'")

        return cls(
            id=rule_id,
            component=str(data.get("component", "general")),
            measurement=str(data.get("measurement", data.get("type", "angle"))),
            landmarks=[str(x) for x in (data.get("landmarks") or [])],
            target_min=tmin,
            target_max=tmax,
            tolerance=float(data.get("tolerance", 20.0)),
            weight=float(data.get("weight", 1.0)),
            body_part=str(data.get("body_part", "")),
            feedback_low=str(feedback.get("low", "")),
            feedback_high=str(feedback.get("high", "")),
            signature=bool(data.get("signature", True)),
            optional=bool(data.get("optional", False)),
            discriminative=bool(data.get("discriminative", False)),
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "component": self.component,
            "body_part": self.body_part,
            "measurement": self.measurement,
            "landmarks": list(self.landmarks),
            "target": [self.target_min, self.target_max],
            "tolerance": self.tolerance,
            "weight": self.weight,
            "unit": self.unit,
            "feedback": {"low": self.feedback_low, "high": self.feedback_high},
            "signature": self.signature,
            "optional": self.optional,
            "discriminative": self.discriminative,
        }
