"""Identifying which asana the practitioner is currently performing.

Recognition and assessment answer different questions. Recognition asks
"which pose is this?"; assessment asks "how well is it done?". Conflating
them is a classic failure mode -- a beginner's shaky Warrior II would be
mis-recognised as some other pose simply because it scored badly.

The rule-based recogniser therefore reuses the same alignment rules but
evaluates them with widened tolerances, so it matches on *shape* rather than
on quality. It works with no training data at all, is fully explainable, and
serves as the always-available default.

An optional scikit-learn classifier can be trained from a landmark dataset
and layered on top; see :mod:`ai.pose_recognition.classifier`.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Sequence, Tuple

from ..pose_assessment.asana import AsanaConfig, AsanaRegistry, get_registry
from ..pose_detection.landmarks import DEFAULT_VISIBILITY_THRESHOLD, PoseFrame

# How much to widen rule tolerances when matching shape rather than quality.
RECOGNITION_TOLERANCE_SCALE = 2.5

# A match below this normalised score is reported as "unknown" rather than
# forcing every frame into one of the ten known asanas.
MIN_MATCH_SCORE = 0.55

# When the top two candidates are this close, the frame is genuinely
# ambiguous and we say so instead of picking arbitrarily.
AMBIGUITY_MARGIN = 0.06

# Minimum share of an asana's signature rules that must be measurable
# before it is considered a candidate at all.
MIN_COVERAGE = 0.6

# Shortest believable shoulder-centre to hip-centre distance, as a
# fraction of the frame. Below this the detection is not a usable body.
MIN_TORSO_LENGTH = 0.02


@dataclass
class PoseCandidate:
    asana_id: str
    asana_name: str
    match: float  # 0.0 - 1.0
    lead_side: Optional[str] = None
    measured_rules: int = 0
    total_rules: int = 0

    @property
    def coverage(self) -> float:
        return self.measured_rules / self.total_rules if self.total_rules else 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "asana_id": self.asana_id,
            "asana_name": self.asana_name,
            "match": round(self.match, 4),
            "lead_side": self.lead_side,
            "coverage": round(self.coverage, 3),
        }


@dataclass
class RecognitionResult:
    """Which asana was recognised, how confidently, and what else it could be."""

    asana_id: Optional[str]
    asana_name: Optional[str]
    confidence: float
    method: str
    lead_side: Optional[str] = None
    candidates: List[PoseCandidate] = field(default_factory=list)
    ambiguous: bool = False
    reason: str = ""

    @property
    def recognised(self) -> bool:
        return self.asana_id is not None

    def to_dict(self) -> Dict[str, object]:
        return {
            "asana_id": self.asana_id,
            "asana_name": self.asana_name,
            "confidence": round(self.confidence, 4),
            "method": self.method,
            "lead_side": self.lead_side,
            "ambiguous": self.ambiguous,
            "reason": self.reason,
            "candidates": [c.to_dict() for c in self.candidates[:5]],
        }


class RuleBasedRecognizer:
    """Matches a frame against every asana's signature rules.

    Transparent by construction: the returned candidate list shows exactly
    how well each known pose fitted, so a disagreement with the user can
    always be traced to specific rules.
    """

    def __init__(
        self,
        registry: Optional[AsanaRegistry] = None,
        *,
        tolerance_scale: float = RECOGNITION_TOLERANCE_SCALE,
        visibility_threshold: float = DEFAULT_VISIBILITY_THRESHOLD,
        min_match: float = MIN_MATCH_SCORE,
    ) -> None:
        self.registry = registry or get_registry()
        self.tolerance_scale = tolerance_scale
        self.visibility_threshold = visibility_threshold
        self.min_match = min_match

    def score_asana(
        self, frame: PoseFrame, config: AsanaConfig
    ) -> Optional[PoseCandidate]:
        """How well ``frame`` fits ``config``, or None if unmeasurable."""
        side_maps: Tuple[Optional[Dict[str, str]], ...]
        if config.is_unilateral:
            side_maps = ({"lead": "left", "rear": "right"}, {"lead": "right", "rear": "left"})
        else:
            side_maps = (None,)

        best: Optional[PoseCandidate] = None
        rules = config.signature_rules()
        if not rules:
            return None

        for side_map in side_maps:
            total_weight = 0.0
            weighted = 0.0
            measured = 0
            for rule in rules:
                res = rule.evaluate(
                    frame,
                    side_map=side_map,
                    visibility_threshold=self.visibility_threshold,
                    tolerance_scale=1.0 if rule.discriminative else self.tolerance_scale,
                )
                if not res.available:
                    continue
                measured += 1
                total_weight += rule.weight
                weighted += res.score * rule.weight

            if total_weight <= 0:
                continue

            coverage = measured / len(rules)
            # A pose matched on only a couple of its signature rules is not
            # evidence of that pose -- it is evidence that most of the checks
            # were unmeasurable. Refuse the candidate outright rather than
            # letting a lucky partial match win.
            if coverage < MIN_COVERAGE:
                continue

            match = weighted / total_weight
            # Beyond the hard gate, still prefer better-covered candidates so
            # a pose matched on six rules outranks one matched on four.
            adjusted = match * (0.55 + 0.45 * coverage)

            candidate = PoseCandidate(
                asana_id=config.id,
                asana_name=config.english_name,
                match=adjusted,
                lead_side=side_map["lead"] if side_map else None,
                measured_rules=measured,
                total_rules=len(rules),
            )
            if best is None or candidate.match > best.match:
                best = candidate

        return best

    def recognize(
        self,
        frame: PoseFrame,
        *,
        expected: Optional[Sequence[str]] = None,
        expected_bonus: float = 0.05,
    ) -> RecognitionResult:
        """Identify the pose in ``frame``.

        ``expected`` lists asanas the current session has queued up. Poses on
        that list get a small bonus, which resolves near-ties in favour of
        what the session actually asked for without letting the prior
        override a clearly different pose.
        """
        if not frame.detected or not frame.landmarks:
            return RecognitionResult(
                asana_id=None,
                asana_name=None,
                confidence=0.0,
                method="rule_based",
                reason="No body detected in the frame.",
            )

        # Every torso-relative measurement divides by torso length, and every
        # scale-free comparison assumes a coherent body. A skeleton whose
        # shoulders and hips collapse onto the same point is detector noise,
        # not a posture -- scoring it would produce a confident answer from
        # whichever angle rules happened to survive.
        if frame.torso_length < MIN_TORSO_LENGTH:
            return RecognitionResult(
                asana_id=None,
                asana_name=None,
                confidence=0.0,
                method="rule_based",
                reason=(
                    "Your body outline is unclear. Step back so your head, "
                    "torso and legs are all in frame."
                ),
            )

        expected_set = set(expected or ())
        candidates: List[PoseCandidate] = []
        for config in self.registry.all():
            cand = self.score_asana(frame, config)
            if cand is None:
                continue
            if cand.asana_id in expected_set:
                cand.match = min(1.0, cand.match + expected_bonus)
            candidates.append(cand)

        if not candidates:
            return RecognitionResult(
                asana_id=None,
                asana_name=None,
                confidence=0.0,
                method="rule_based",
                reason="Too few landmarks visible to identify a pose.",
            )

        candidates.sort(key=lambda c: c.match, reverse=True)
        top = candidates[0]
        runner_up = candidates[1] if len(candidates) > 1 else None
        margin = top.match - runner_up.match if runner_up else top.match
        ambiguous = margin < AMBIGUITY_MARGIN

        if top.match < self.min_match:
            return RecognitionResult(
                asana_id=None,
                asana_name=None,
                confidence=top.match,
                method="rule_based",
                candidates=candidates,
                reason=(
                    "Your posture does not clearly match any asana in the "
                    "library yet. Move into the pose and hold it."
                ),
            )

        # Confidence blends how well the winner fitted with how decisively it
        # beat the alternatives: a strong fit that barely wins is not a
        # confident identification.
        confidence = top.match * (0.7 + 0.3 * min(margin / AMBIGUITY_MARGIN, 1.0))

        return RecognitionResult(
            asana_id=top.asana_id,
            asana_name=top.asana_name,
            confidence=min(confidence, 1.0),
            method="rule_based",
            lead_side=top.lead_side,
            candidates=candidates,
            ambiguous=ambiguous,
            reason=(
                f"Closest match to {top.asana_name}"
                + (f", but {runner_up.asana_name} is nearly as close." if ambiguous and runner_up else ".")
            ),
        )


class TemporalRecognizer:
    """Stabilises frame-by-frame recognition over a short time window.

    Single-frame recognition flickers as the practitioner transitions between
    poses. Requiring a candidate to win a majority of recent frames before
    switching stops the on-screen pose label from strobing, which matters
    because the label drives which rule set the assessment uses.
    """

    def __init__(
        self,
        recognizer: Optional[RuleBasedRecognizer] = None,
        *,
        window: int = 8,
        switch_ratio: float = 0.6,
    ) -> None:
        self.recognizer = recognizer or RuleBasedRecognizer()
        self.window = max(1, window)
        self.switch_ratio = switch_ratio
        self._history: Deque[Optional[str]] = deque(maxlen=self.window)
        self._current: Optional[str] = None
        self._last: Optional[RecognitionResult] = None

    def reset(self) -> None:
        self._history.clear()
        self._current = None
        self._last = None

    def update(
        self, frame: PoseFrame, *, expected: Optional[Sequence[str]] = None
    ) -> RecognitionResult:
        result = self.recognizer.recognize(frame, expected=expected)
        self._history.append(result.asana_id)

        counts: Dict[Optional[str], int] = {}
        for aid in self._history:
            counts[aid] = counts.get(aid, 0) + 1

        winner, votes = max(counts.items(), key=lambda kv: kv[1])
        share = votes / len(self._history)

        if winner is not None and share >= self.switch_ratio:
            self._current = winner
        elif winner is None and share >= self.switch_ratio:
            self._current = None

        # Report the stable pose, but carry the current frame's candidate
        # detail so the UI can still show live match quality.
        if self._current == result.asana_id:
            self._last = result
            return result

        if self._current is None:
            stabilised = RecognitionResult(
                asana_id=None,
                asana_name=None,
                confidence=result.confidence,
                method="rule_based+temporal",
                candidates=result.candidates,
                reason="Hold the pose steadily so it can be identified.",
            )
            self._last = stabilised
            return stabilised

        config = self.recognizer.registry.get(self._current)
        stabilised = RecognitionResult(
            asana_id=self._current,
            asana_name=config.english_name if config else self._current,
            confidence=result.confidence * 0.9,
            method="rule_based+temporal",
            lead_side=result.lead_side,
            candidates=result.candidates,
            ambiguous=True,
            reason="Holding the previously identified pose while your posture settles.",
        )
        self._last = stabilised
        return stabilised
