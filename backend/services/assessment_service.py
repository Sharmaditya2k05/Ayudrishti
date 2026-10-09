"""The live assessment pipeline behind ``POST /assessment``.

One frame of landmarks in, a complete coaching response out: which pose,
how well, what to fix, and whether anything looks unsafe. This is the
Detect -> Assess -> Correct segment of the closed loop.

Per-user feedback and safety state (throttling cooldowns, sustained-
misalignment timers, motion history) has to persist between requests, since
each frame arrives as a separate HTTP call. That state is held here in a
bounded in-process cache.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from ai.feedback import FeedbackGenerator
from ai.pose_detection.landmarks import PoseFrame
from ai.safety import PhysiologicalSnapshot, SafetyMonitor

from .engines import get_assessment_engine, get_recognizer

# Cap the number of concurrent live sessions we keep state for, so a long-
# running server cannot grow unboundedly from abandoned sessions.
MAX_TRACKED_SESSIONS = 512


@dataclass
class LiveState:
    """Per-session coaching state that must survive between frames."""

    feedback: FeedbackGenerator
    safety: SafetyMonitor
    last_asana: Optional[str] = None


class LiveStateStore:
    """Bounded LRU of live session state, keyed by user and session."""

    def __init__(self, max_entries: int = MAX_TRACKED_SESSIONS) -> None:
        self._entries: "OrderedDict[str, LiveState]" = OrderedDict()
        self._max = max_entries

    @staticmethod
    def key(user_id: int, session_id: Optional[int]) -> str:
        return f"{user_id}:{session_id or 0}"

    def get(
        self, user_id: int, session_id: Optional[int], *, resting_hr: Optional[float] = None
    ) -> LiveState:
        key = self.key(user_id, session_id)
        state = self._entries.get(key)
        if state is None:
            state = LiveState(
                feedback=FeedbackGenerator(),
                safety=SafetyMonitor(resting_heart_rate=resting_hr),
            )
            self._entries[key] = state
            while len(self._entries) > self._max:
                self._entries.popitem(last=False)
        else:
            self._entries.move_to_end(key)
        return state

    def clear(self, user_id: int, session_id: Optional[int] = None) -> None:
        if session_id is None:
            for key in [k for k in self._entries if k.startswith(f"{user_id}:")]:
                self._entries.pop(key, None)
        else:
            self._entries.pop(self.key(user_id, session_id), None)


live_state = LiveStateStore()


def build_frame(landmarks: Sequence[object], timestamp: float) -> PoseFrame:
    """Convert posted landmark objects into a PoseFrame."""
    rows = [
        [lm.x, lm.y, getattr(lm, "z", 0.0), getattr(lm, "visibility", 1.0)]
        for lm in landmarks
    ]
    return PoseFrame.from_sequence(rows, timestamp=timestamp)


def assess_frame(
    *,
    user_id: int,
    landmarks: Sequence[object],
    asana_id: Optional[str] = None,
    session_id: Optional[int] = None,
    timestamp: float = 0.0,
    lead_side: Optional[str] = None,
    expected_asanas: Optional[Sequence[str]] = None,
    include_rules: bool = True,
    physiological: Optional[PhysiologicalSnapshot] = None,
    resting_heart_rate: Optional[float] = None,
) -> Dict[str, object]:
    """Run one frame through recognition, assessment, feedback and safety."""
    frame = build_frame(landmarks, timestamp)
    state = live_state.get(user_id, session_id, resting_hr=resting_heart_rate)

    engine = get_assessment_engine()
    recognizer = get_recognizer()

    recognition = None
    target = asana_id

    if target is None:
        # No pose specified: identify it first, then score against it.
        result = recognizer.recognize(frame, expected=expected_asanas or ())
        recognition = result
        target = result.asana_id
        if lead_side is None:
            lead_side = result.lead_side

        if target is None:
            return {
                "detected": frame.detected,
                "recognition": _recognition_dict(result),
                "feedback": {
                    "headline": "Move into a pose",
                    "messages": [
                        {
                            "text": result.reason
                            or "Hold a pose steadily so it can be identified.",
                            "kind": "info",
                            "severity": "none",
                        }
                    ],
                    "indicators": [],
                    "highlight_landmarks": [],
                },
                "safety_alerts": [],
                "notes": [],
                "missing_landmarks": [],
            }

    # Switching pose invalidates the previous pose's throttling and timers.
    if state.last_asana != target:
        state.feedback.reset()
        state.safety.reset()
        engine.reset_smoothing(target)
        state.last_asana = target

    assessment = engine.assess(frame, target, lead_side=lead_side)
    bundle = state.feedback.generate(assessment, timestamp=timestamp)
    alerts = state.safety.check(
        frame, assessment, physiological, timestamp=timestamp
    )

    payload: Dict[str, object] = {
        "detected": assessment.detected,
        "asana_id": assessment.asana_id,
        "asana_name": assessment.asana_name,
        "overall": round(assessment.overall, 1),
        "grade": assessment.score.grade,
        "confidence": round(assessment.score.confidence, 3),
        "reliable": assessment.reliable,
        "lead_side": assessment.lead_side,
        "deviation_count": assessment.score.deviation_count,
        "components": [c.to_dict() for c in assessment.score.components],
        "rules": (
            [r.to_dict() for r in assessment.score.rule_results] if include_rules else []
        ),
        "feedback": bundle.to_dict(),
        "safety_alerts": [a.to_dict() for a in alerts],
        "missing_landmarks": assessment.missing_landmarks,
        "notes": assessment.notes,
    }
    if recognition is not None:
        payload["recognition"] = _recognition_dict(recognition)
    return payload


def recognize_frame(
    *,
    landmarks: Sequence[object],
    timestamp: float = 0.0,
    expected_asanas: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    """Identify the pose without scoring it."""
    frame = build_frame(landmarks, timestamp)
    result = get_recognizer().recognize(frame, expected=expected_asanas or ())
    return _recognition_dict(result)


def _recognition_dict(result) -> Dict[str, object]:
    return {
        "asana_id": result.asana_id,
        "asana_name": result.asana_name,
        "confidence": round(result.confidence, 4),
        "method": result.method,
        "lead_side": result.lead_side,
        "ambiguous": result.ambiguous,
        "reason": result.reason,
        "candidates": [c.to_dict() for c in result.candidates[:5]],
    }
