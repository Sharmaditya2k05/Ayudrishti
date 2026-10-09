"""Turning assessment results into corrective coaching.

The spec is emphatic that "Incorrect" is not feedback. Every message here
names a body part, a direction and an action, and is traceable to the exact
rule and measurement that produced it.

Two behaviours matter as much as the wording:

* **Prioritisation.** A frame can violate six rules at once. Reading all six
  aloud is useless mid-pose, so the generator surfaces only the most
  important few, ranked by how wrong they are and how much the rule matters.

* **Throttling.** Repeating the same correction every frame is noise. A
  message that has just been given is suppressed for a cooldown period, and
  a correction the practitioner has fixed is acknowledged rather than
  silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from ..pose_assessment.engine import AssessmentResult
from ..pose_assessment.rules import RuleResult

# Severity bands. A rule scoring above OK_THRESHOLD is treated as correct and
# eligible for positive acknowledgement.
OK_THRESHOLD = 0.85
MINOR_THRESHOLD = 0.65
MAJOR_THRESHOLD = 0.4

# How long (in seconds) before the same correction may be repeated.
DEFAULT_COOLDOWN = 6.0

# Most corrections to surface at once. More than this and the practitioner
# cannot act on any of them.
DEFAULT_MAX_MESSAGES = 2


@dataclass
class FeedbackMessage:
    """One actionable instruction, with the evidence behind it."""

    text: str
    kind: str  # "correction" | "praise" | "info" | "safety"
    severity: str  # "minor" | "moderate" | "major" | "none"
    component: str = ""
    body_part: str = ""
    rule_id: str = ""
    priority: float = 0.0
    # The measurement that triggered this, so the UI can explain *why*.
    measured_value: Optional[float] = None
    target_min: Optional[float] = None
    target_max: Optional[float] = None
    unit: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "text": self.text,
            "kind": self.kind,
            "severity": self.severity,
            "component": self.component,
            "body_part": self.body_part,
            "rule_id": self.rule_id,
            "priority": round(self.priority, 4),
            "measured_value": (
                None if self.measured_value is None else round(self.measured_value, 2)
            ),
            "target_min": self.target_min,
            "target_max": self.target_max,
            "unit": self.unit,
        }


@dataclass
class AlignmentIndicator:
    """A per-component status light for the live session screen."""

    component: str
    label: str
    status: str  # "good" | "adjust" | "off" | "unknown"
    score: float
    message: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "component": self.component,
            "label": self.label,
            "status": self.status,
            "score": round(self.score, 1),
            "message": self.message,
        }


@dataclass
class FeedbackBundle:
    """Everything the practice screen needs to render for one frame."""

    messages: List[FeedbackMessage] = field(default_factory=list)
    indicators: List[AlignmentIndicator] = field(default_factory=list)
    headline: str = ""
    highlight_landmarks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "headline": self.headline,
            "messages": [m.to_dict() for m in self.messages],
            "indicators": [i.to_dict() for i in self.indicators],
            "highlight_landmarks": list(self.highlight_landmarks),
        }


def severity_of(score: float) -> str:
    if score >= OK_THRESHOLD:
        return "none"
    if score >= MINOR_THRESHOLD:
        return "minor"
    if score >= MAJOR_THRESHOLD:
        return "moderate"
    return "major"


def _fallback_text(result: RuleResult) -> str:
    """A usable instruction when a rule ships without custom wording.

    Still names the body part and a direction -- never a bare "incorrect".
    """
    part = result.body_part or result.component.replace("_", " ")
    if result.status == "low":
        return f"Increase the angle at your {part} slightly."
    if result.status == "high":
        return f"Reduce the angle at your {part} slightly."
    return f"Check the alignment of your {part}."


class FeedbackGenerator:
    """Produces prioritised, throttled coaching from assessment results."""

    def __init__(
        self,
        *,
        max_messages: int = DEFAULT_MAX_MESSAGES,
        cooldown: float = DEFAULT_COOLDOWN,
        praise_enabled: bool = True,
    ) -> None:
        self.max_messages = max_messages
        self.cooldown = cooldown
        self.praise_enabled = praise_enabled
        self._last_spoken: Dict[str, float] = {}
        self._outstanding: Dict[str, str] = {}

    def reset(self) -> None:
        """Clear throttling state, e.g. when starting a new asana."""
        self._last_spoken.clear()
        self._outstanding.clear()

    # ---- main entry point ------------------------------------------------

    def generate(
        self,
        assessment: AssessmentResult,
        *,
        timestamp: float = 0.0,
        include_praise: bool = True,
    ) -> FeedbackBundle:
        if not assessment.detected:
            return FeedbackBundle(
                headline="Step into the camera view",
                messages=[
                    FeedbackMessage(
                        text=(
                            "I cannot see you. Step back so your whole body is "
                            "in the frame."
                        ),
                        kind="info",
                        severity="none",
                    )
                ],
            )

        messages: List[FeedbackMessage] = []

        # Camera-setup problems come first: no correction is meaningful if the
        # relevant joints are out of frame.
        for note in assessment.notes:
            messages.append(
                FeedbackMessage(text=note, kind="info", severity="none", priority=100.0)
            )

        corrections = self._corrections(assessment, timestamp)
        messages.extend(corrections[: self.max_messages])

        if include_praise and self.praise_enabled:
            # Praise is judged against what is *actually* still wrong, not
            # against what we happened to say this frame. Cooldown silences a
            # repeat correction; it must never be mistaken for a fix.
            still_failing = {
                res.rule_id
                for res in assessment.score.rule_results
                if res.available and res.score < OK_THRESHOLD
            }
            praise = self._praise(assessment, still_failing)
            if praise:
                messages.append(praise)

        indicators = self.indicators(assessment)
        highlight = [lm for c in corrections[: self.max_messages] for lm in self._landmarks_for(assessment, c.rule_id)]

        return FeedbackBundle(
            messages=messages,
            indicators=indicators,
            headline=self._headline(assessment),
            highlight_landmarks=sorted(set(highlight)),
        )

    # ---- pieces ----------------------------------------------------------

    def _corrections(
        self, assessment: AssessmentResult, timestamp: float
    ) -> List[FeedbackMessage]:
        """Rank failing rules and drop any still inside their cooldown."""
        out: List[FeedbackMessage] = []
        for res in assessment.deviations:
            if res.score >= OK_THRESHOLD:
                # Close enough to correct that nagging would be unhelpful.
                self._clear(res.rule_id)
                continue

            # Importance = how wrong it is, weighted by how much this rule
            # matters to the pose. A heavily-weighted rule slightly off can
            # outrank a trivial rule badly off, which is the correct
            # coaching instinct.
            priority = res.severity * res.weight

            if not self._due(res.rule_id, timestamp):
                continue

            text = res.feedback or _fallback_text(res)
            out.append(
                FeedbackMessage(
                    text=text,
                    kind="correction",
                    severity=severity_of(res.score),
                    component=res.component,
                    body_part=res.body_part,
                    rule_id=res.rule_id,
                    priority=priority,
                    measured_value=res.value,
                    target_min=res.target_min,
                    target_max=res.target_max,
                    unit=res.unit,
                )
            )

        out.sort(key=lambda m: m.priority, reverse=True)
        for msg in out[: self.max_messages]:
            self._mark_spoken(msg.rule_id, msg.text, timestamp)
        return out

    def _praise(
        self,
        assessment: AssessmentResult,
        still_failing: set[str],
    ) -> Optional[FeedbackMessage]:
        """Acknowledge a correction that has just been fixed, or a good hold.

        Confirming that a fix landed is what closes the correction loop for
        the practitioner -- otherwise they never learn which adjustment
        worked.
        """
        fixed = [rid for rid in self._outstanding if rid not in still_failing]
        if fixed:
            rule_id = fixed[0]
            part = self._body_part_for(assessment, rule_id)
            self._clear(rule_id)
            return FeedbackMessage(
                text=f"Good - your {part} is aligned now.",
                kind="praise",
                severity="none",
                rule_id=rule_id,
                priority=-1.0,
            )

        if not still_failing and assessment.overall >= 88:
            return FeedbackMessage(
                text="Excellent alignment. Hold and breathe steadily.",
                kind="praise",
                severity="none",
                priority=-1.0,
            )
        return None

    def indicators(self, assessment: AssessmentResult) -> List[AlignmentIndicator]:
        """Per-component status lights, e.g. "Torso ok / Front knee adjust"."""
        out: List[AlignmentIndicator] = []
        worst_by_component: Dict[str, RuleResult] = {}
        for res in assessment.deviations:
            cur = worst_by_component.get(res.component)
            if cur is None or res.severity > cur.severity:
                worst_by_component[res.component] = res

        for comp in assessment.score.components:
            if comp.available_count == 0:
                status = "unknown"
            elif comp.score >= 85:
                status = "good"
            elif comp.score >= 65:
                status = "adjust"
            else:
                status = "off"
            worst = worst_by_component.get(comp.component)
            out.append(
                AlignmentIndicator(
                    component=comp.component,
                    label=comp.label,
                    status=status,
                    score=comp.score,
                    message=(worst.feedback or "") if worst and status != "good" else "",
                )
            )
        return out

    def _headline(self, assessment: AssessmentResult) -> str:
        score = assessment.overall
        if not assessment.reliable:
            return f"{assessment.asana_name} - partial view"
        if score >= 90:
            return f"{assessment.asana_name} - excellent"
        if score >= 80:
            return f"{assessment.asana_name} - good"
        if score >= 70:
            return f"{assessment.asana_name} - keep adjusting"
        return f"{assessment.asana_name} - let's fix the alignment"

    # ---- throttling helpers ----------------------------------------------

    def _due(self, rule_id: str, timestamp: float) -> bool:
        last = self._last_spoken.get(rule_id)
        if last is None:
            return True
        return (timestamp - last) >= self.cooldown

    def _mark_spoken(self, rule_id: str, text: str, timestamp: float) -> None:
        self._last_spoken[rule_id] = timestamp
        self._outstanding[rule_id] = text

    def _clear(self, rule_id: str) -> None:
        self._outstanding.pop(rule_id, None)

    @staticmethod
    def _body_part_for(assessment: AssessmentResult, rule_id: str) -> str:
        for res in assessment.score.rule_results:
            if res.rule_id == rule_id:
                return res.body_part or res.component.replace("_", " ")
        return "alignment"

    @staticmethod
    def _landmarks_for(assessment: AssessmentResult, rule_id: str) -> List[str]:
        for res in assessment.score.rule_results:
            if res.rule_id == rule_id:
                return list(res.landmarks)
        return []


def summarise_corrections(messages: Sequence[FeedbackMessage]) -> List[str]:
    """Deduplicated correction texts, for the end-of-session summary."""
    seen: List[str] = []
    for msg in messages:
        if msg.kind == "correction" and msg.text not in seen:
            seen.append(msg.text)
    return seen
