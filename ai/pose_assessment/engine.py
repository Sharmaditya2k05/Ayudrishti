"""The pose assessment engine.

Given a detected frame and the asana the practitioner is meant to be in,
this produces a measured, explainable verdict: every rule's actual value,
how far it sits from the target range, a weighted score, and the specific
corrections that follow.

Two details matter for correctness:

* **Side resolution.** Unilateral poses (Warrior II, Trikonasana, Tree) can
  be performed leading with either leg. The engine evaluates both
  assignments and keeps the better one, so a right-lead Warrior II is not
  scored as a badly-executed left-lead one.

* **Temporal smoothing.** A single frame of MediaPipe output jitters. The
  engine can smooth scores over a short rolling window so that the live
  feedback is stable enough to act on rather than flickering every frame.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Sequence, Tuple

from ..pose_detection.landmarks import DEFAULT_VISIBILITY_THRESHOLD, PoseFrame
from ..scoring.scoring import PoseScore, aggregate_rules
from .asana import AsanaConfig, AsanaRegistry, get_registry
from .rules import RuleResult

SIDE_MAPS: Tuple[Dict[str, str], ...] = (
    {"lead": "left", "rear": "right"},
    {"lead": "right", "rear": "left"},
)


@dataclass
class AssessmentResult:
    """A complete, explainable verdict on one attempt at one asana."""

    asana_id: str
    asana_name: str
    score: PoseScore
    lead_side: Optional[str] = None
    detected: bool = True
    # Rules that failed, worst first -- the raw material for feedback.
    deviations: List[RuleResult] = field(default_factory=list)
    missing_landmarks: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def overall(self) -> float:
        return self.score.overall

    @property
    def reliable(self) -> bool:
        return self.detected and self.score.reliable

    def to_dict(self, include_rules: bool = True) -> Dict[str, object]:
        return {
            "asana_id": self.asana_id,
            "asana_name": self.asana_name,
            "detected": self.detected,
            "lead_side": self.lead_side,
            "reliable": self.reliable,
            "missing_landmarks": list(self.missing_landmarks),
            "notes": list(self.notes),
            "deviations": [d.to_dict() for d in self.deviations],
            **self.score.to_dict(include_rules=include_rules),
        }


class PoseAssessmentEngine:
    """Evaluates frames against asana rule sets.

    Stateless with respect to a single ``assess`` call; the optional rolling
    window it keeps is only used by :meth:`assess_smoothed` for live sessions.
    """

    def __init__(
        self,
        registry: Optional[AsanaRegistry] = None,
        *,
        visibility_threshold: float = DEFAULT_VISIBILITY_THRESHOLD,
        smoothing_window: int = 5,
    ) -> None:
        self.registry = registry or get_registry()
        self.visibility_threshold = visibility_threshold
        self.smoothing_window = max(1, smoothing_window)
        self._history: Dict[str, Deque[float]] = {}

    # ---- core assessment -------------------------------------------------

    def assess(
        self,
        frame: PoseFrame,
        asana_id: str,
        *,
        lead_side: Optional[str] = None,
    ) -> AssessmentResult:
        """Score ``frame`` against the rules for ``asana_id``."""
        config = self.registry.require(asana_id)
        return self.assess_with_config(frame, config, lead_side=lead_side)

    def assess_with_config(
        self,
        frame: PoseFrame,
        config: AsanaConfig,
        *,
        lead_side: Optional[str] = None,
    ) -> AssessmentResult:
        if not frame.detected or not frame.landmarks:
            empty = aggregate_rules(config.id, [], config.components)
            return AssessmentResult(
                asana_id=config.id,
                asana_name=config.english_name,
                score=empty,
                detected=False,
                notes=["No body detected in frame. Step back so your whole body is visible."],
            )

        results, chosen_side = self._evaluate_rules(frame, config, lead_side)
        score = aggregate_rules(config.id, results, config.components)

        deviations = sorted(
            (r for r in results if r.available and r.status in ("low", "high")),
            key=lambda r: (-(r.severity * r.weight), r.rule_id),
        )

        missing = frame.missing(config.required_landmarks(), self.visibility_threshold)
        notes: List[str] = []
        if missing:
            # Say so as soon as any required joint is out of view, not only
            # once so much is hidden that the score collapses. A partly
            # occluded assessment is still a partial one, and the user needs
            # to know which way to move the camera to fix it.
            parts = ", ".join(m.replace("_", " ") for m in missing[:3])
            more = f" and {len(missing) - 3} more" if len(missing) > 3 else ""
            notes.append(
                f"The camera cannot clearly see your {parts}{more}, so those "
                f"checks were skipped. {config.camera_hint}".strip()
            )
        if not score.reliable:
            notes.append(
                "Only part of your body is visible, so this score covers "
                "what the camera could see. Adjust the camera for a full-body view."
            )

        return AssessmentResult(
            asana_id=config.id,
            asana_name=config.english_name,
            score=score,
            lead_side=chosen_side,
            detected=True,
            deviations=deviations,
            missing_landmarks=missing,
            notes=notes,
        )

    def _evaluate_rules(
        self,
        frame: PoseFrame,
        config: AsanaConfig,
        lead_side: Optional[str],
    ) -> Tuple[List[RuleResult], Optional[str]]:
        """Run every rule, resolving the lead side for unilateral poses."""
        if not config.is_unilateral:
            return [
                rule.evaluate(frame, visibility_threshold=self.visibility_threshold)
                for rule in config.rules
            ], None

        candidates: List[Tuple[float, str, List[RuleResult]]] = []
        side_maps = SIDE_MAPS
        if lead_side in ("left", "right"):
            # Caller already knows which leg leads (e.g. the session script
            # said "Warrior II, right leg forward"), so don't second-guess it.
            side_maps = (
                {"lead": lead_side, "rear": "right" if lead_side == "left" else "left"},
            )

        for side_map in side_maps:
            results = [
                rule.evaluate(
                    frame,
                    side_map=side_map,
                    visibility_threshold=self.visibility_threshold,
                )
                for rule in config.rules
            ]
            available = [r for r in results if r.available]
            weight = sum(r.weight for r in available)
            total = sum(r.score * r.weight for r in available)
            # Rank by achieved score, tie-broken by how much we could measure,
            # so a fully-visible reading beats a partially-occluded one.
            quality = (total / weight if weight else 0.0, weight)
            candidates.append((quality[0] * 1000 + quality[1], side_map["lead"], results))

        best = max(candidates, key=lambda c: c[0])
        return best[2], best[1]

    # ---- live session helpers -------------------------------------------

    def assess_smoothed(
        self,
        frame: PoseFrame,
        asana_id: str,
        *,
        lead_side: Optional[str] = None,
    ) -> AssessmentResult:
        """Assess a frame, reporting a score smoothed over recent frames.

        The per-rule detail stays instantaneous (so corrections react
        immediately), but the headline number the user sees stops jittering.
        """
        result = self.assess(frame, asana_id, lead_side=lead_side)
        if not result.detected:
            return result

        window = self._history.setdefault(asana_id, deque(maxlen=self.smoothing_window))
        window.append(result.score.overall)
        result.score.overall = sum(window) / len(window)
        return result

    def reset_smoothing(self, asana_id: Optional[str] = None) -> None:
        """Clear rolling history, e.g. when moving to the next asana."""
        if asana_id is None:
            self._history.clear()
        else:
            self._history.pop(asana_id, None)

    # ---- batch helpers ---------------------------------------------------

    def assess_many(
        self, frames: Sequence[PoseFrame], asana_id: str
    ) -> List[AssessmentResult]:
        return [self.assess(f, asana_id) for f in frames]

    def best_of(
        self, frames: Sequence[PoseFrame], asana_id: str
    ) -> Optional[AssessmentResult]:
        """The best-scoring frame from a hold.

        A held pose is judged by how well it was achieved, not by the wobble
        on the way in, so summaries use the peak rather than the mean.
        """
        results = [r for r in self.assess_many(frames, asana_id) if r.detected]
        return max(results, key=lambda r: r.overall) if results else None
