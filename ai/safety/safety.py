"""Conservative safety monitoring during a live session.

This layer watches for situations where the sensible coaching response is
"pause and reset" rather than "adjust your knee": sustained poor alignment,
sudden or excessive movement, a loss of balance, or -- when a wearable is
connected -- an unusual physiological response.

Scope discipline matters here. Nothing in this module diagnoses anything.
Every physiological signal is treated as *context*, and every message
produced from one is explicitly labelled a wellness indicator. The strongest
action the system ever takes is suggesting a rest.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Sequence

from ..pose_assessment.engine import AssessmentResult
from ..pose_detection.landmarks import BODY_LANDMARKS, PoseFrame

# Standard wording appended wherever physiological data influences a message,
# so the disclaimer cannot be lost by a UI that renders only `message`.
WELLNESS_DISCLAIMER = (
    "This is a system-generated wellness indicator based on sensor readings, "
    "not a medical measurement or diagnosis."
)

# Alignment below this, held for SUSTAINED_SECONDS, prompts a reset.
POOR_ALIGNMENT_SCORE = 55.0
SUSTAINED_SECONDS = 12.0

# Movement thresholds, in torso lengths per second.
EXCESSIVE_MOTION = 1.6
SUDDEN_MOTION = 3.2

SEVERITY_ORDER = {"info": 0, "caution": 1, "rest": 2}


@dataclass
class SafetyAlert:
    """A safety observation and the action it suggests."""

    code: str
    severity: str  # "info" | "caution" | "rest"
    message: str
    source: str = "posture"  # "posture" | "motion" | "physiological" | "fusion"
    detail: str = ""

    @property
    def rank(self) -> int:
        return SEVERITY_ORDER.get(self.severity, 0)

    def to_dict(self) -> Dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "source": self.source,
            "detail": self.detail,
        }


@dataclass
class PhysiologicalSnapshot:
    """One reading from an optional wearable.

    Every field is optional: the system must behave identically when no
    device is connected, which is the spec's hard requirement.
    """

    heart_rate: Optional[float] = None  # bpm
    spo2: Optional[float] = None  # %
    gsr: Optional[float] = None  # microsiemens
    motion_magnitude: Optional[float] = None  # g
    timestamp: float = 0.0

    @property
    def has_data(self) -> bool:
        return any(
            v is not None
            for v in (self.heart_rate, self.spo2, self.gsr, self.motion_magnitude)
        )


@dataclass
class MotionReading:
    speed: float = 0.0  # torso lengths per second
    peak_joint: str = ""
    stable: bool = True


class MotionTracker:
    """Measures how fast the body is moving between frames.

    Normalising by torso length keeps the reading comparable across
    practitioners and camera distances, and dividing by real elapsed time
    keeps it comparable across frame rates.
    """

    def __init__(self, *, window: int = 5) -> None:
        self._previous: Optional[PoseFrame] = None
        self._history: Deque[float] = deque(maxlen=max(1, window))

    def reset(self) -> None:
        self._previous = None
        self._history.clear()

    def update(self, frame: PoseFrame) -> MotionReading:
        previous, self._previous = self._previous, frame
        if previous is None or not frame.detected or not previous.detected:
            return MotionReading()

        dt = frame.timestamp - previous.timestamp
        if dt <= 1e-3:
            # Without a reliable clock delta any speed figure is meaningless,
            # so report no motion rather than a fabricated number.
            return MotionReading()

        scale = frame.torso_length
        if scale < 1e-6:
            return MotionReading()

        peak = 0.0
        peak_joint = ""
        for name in BODY_LANDMARKS:
            a, b = previous.get(name), frame.get(name)
            if a is None or b is None or not a.is_visible() or not b.is_visible():
                continue
            moved = ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5 / scale
            speed = moved / dt
            if speed > peak:
                peak, peak_joint = speed, name

        self._history.append(peak)
        smoothed = sum(self._history) / len(self._history)
        return MotionReading(
            speed=smoothed, peak_joint=peak_joint, stable=smoothed < EXCESSIVE_MOTION
        )


class SafetyMonitor:
    """Combines posture, motion and optional physiology into safety alerts."""

    def __init__(
        self,
        *,
        poor_alignment_score: float = POOR_ALIGNMENT_SCORE,
        sustained_seconds: float = SUSTAINED_SECONDS,
        resting_heart_rate: Optional[float] = None,
    ) -> None:
        self.poor_alignment_score = poor_alignment_score
        self.sustained_seconds = sustained_seconds
        self.resting_heart_rate = resting_heart_rate
        self.motion = MotionTracker()
        self._poor_since: Optional[float] = None
        self._baseline_gsr: Optional[float] = None
        self._gsr_samples: List[float] = []

    def reset(self) -> None:
        self.motion.reset()
        self._poor_since = None
        self._baseline_gsr = None
        self._gsr_samples.clear()

    # ---- main entry point ------------------------------------------------

    def check(
        self,
        frame: PoseFrame,
        assessment: Optional[AssessmentResult] = None,
        physiological: Optional[PhysiologicalSnapshot] = None,
        *,
        timestamp: Optional[float] = None,
    ) -> List[SafetyAlert]:
        """Evaluate one moment and return any alerts, most severe first."""
        now = timestamp if timestamp is not None else frame.timestamp
        alerts: List[SafetyAlert] = []

        motion = self.motion.update(frame)
        alerts.extend(self._motion_alerts(motion))
        alerts.extend(self._posture_alerts(assessment, now))

        physio_alerts = self._physiological_alerts(physiological)
        alerts.extend(physio_alerts)
        alerts.extend(self._fusion_alerts(assessment, motion, physio_alerts))

        alerts.sort(key=lambda a: a.rank, reverse=True)
        return alerts

    # ---- individual checks -----------------------------------------------

    def _motion_alerts(self, motion: MotionReading) -> List[SafetyAlert]:
        if motion.speed >= SUDDEN_MOTION:
            return [
                SafetyAlert(
                    code="sudden_movement",
                    severity="rest",
                    message="That was a sudden movement. Pause and reset your posture before continuing.",
                    source="motion",
                    detail=f"Peak movement {motion.speed:.1f} torso-lengths/s at {motion.peak_joint or 'body'}.",
                )
            ]
        if motion.speed >= EXCESSIVE_MOTION:
            return [
                SafetyAlert(
                    code="excessive_movement",
                    severity="caution",
                    message="You are wobbling a lot. Steady yourself, and use a wall for support if you need it.",
                    source="motion",
                    detail=f"Movement {motion.speed:.1f} torso-lengths/s.",
                )
            ]
        return []

    def _posture_alerts(
        self, assessment: Optional[AssessmentResult], now: float
    ) -> List[SafetyAlert]:
        if assessment is None or not assessment.detected:
            self._poor_since = None
            return []

        # Only track sustained-deviation time when the reading is trustworthy;
        # a low score caused by half the body being out of frame is a camera
        # problem, not a safety one.
        if not assessment.reliable:
            self._poor_since = None
            return []

        if assessment.overall >= self.poor_alignment_score:
            self._poor_since = None
            return []

        if self._poor_since is None:
            self._poor_since = now
            return []

        held = now - self._poor_since
        if held < self.sustained_seconds:
            return []

        self._poor_since = now  # re-arm so we prompt periodically, not every frame
        worst = assessment.score.weakest_component()
        detail = (
            f"Alignment held at {assessment.overall:.0f}% for {held:.0f}s"
            + (f", weakest area: {worst.label}." if worst else ".")
        )
        return [
            SafetyAlert(
                code="sustained_misalignment",
                severity="rest",
                message=(
                    "You have held this pose out of alignment for a while. "
                    "Come out of the pose, rest, and try again."
                ),
                source="posture",
                detail=detail,
            )
        ]

    def _physiological_alerts(
        self, physio: Optional[PhysiologicalSnapshot]
    ) -> List[SafetyAlert]:
        """Wellness context from a wearable, if one is connected.

        Thresholds here are intentionally loose and the language is
        non-clinical: the goal is to prompt a rest, never to characterise a
        medical state.
        """
        if physio is None or not physio.has_data:
            return []

        alerts: List[SafetyAlert] = []

        if physio.heart_rate is not None:
            hr = physio.heart_rate
            # Compare against the practitioner's own resting rate when known,
            # since absolute bpm means little without that baseline.
            if self.resting_heart_rate and hr > self.resting_heart_rate * 2.0:
                alerts.append(
                    SafetyAlert(
                        code="elevated_heart_rate",
                        severity="caution",
                        message=(
                            "Your heart rate is much higher than your usual resting "
                            "level. Slow your breathing and rest if you need to. "
                            + WELLNESS_DISCLAIMER
                        ),
                        source="physiological",
                        detail=f"{hr:.0f} bpm vs resting {self.resting_heart_rate:.0f} bpm.",
                    )
                )
            elif hr >= 150:
                alerts.append(
                    SafetyAlert(
                        code="high_heart_rate",
                        severity="caution",
                        message=(
                            "Your heart rate is high for a yoga session. Ease off and "
                            "breathe slowly. " + WELLNESS_DISCLAIMER
                        ),
                        source="physiological",
                        detail=f"{hr:.0f} bpm.",
                    )
                )

        if physio.spo2 is not None and physio.spo2 < 92:
            alerts.append(
                SafetyAlert(
                    code="low_spo2_reading",
                    severity="rest",
                    message=(
                        "Your blood-oxygen reading is lower than expected. Come out of "
                        "the pose, sit down and breathe normally. If the reading stays "
                        "low or you feel unwell, seek advice from a healthcare "
                        "professional. " + WELLNESS_DISCLAIMER
                    ),
                    source="physiological",
                    detail=f"SpO2 {physio.spo2:.0f}%. Consumer sensors are easily disturbed by movement.",
                )
            )

        if physio.gsr is not None:
            self._gsr_samples.append(physio.gsr)
            if self._baseline_gsr is None and len(self._gsr_samples) >= 10:
                # First readings of the session establish the personal baseline;
                # absolute GSR varies far too much between people to threshold.
                self._baseline_gsr = sum(self._gsr_samples[:10]) / 10
            if self._baseline_gsr and physio.gsr > self._baseline_gsr * 1.6:
                alerts.append(
                    SafetyAlert(
                        code="raised_stress_response",
                        severity="info",
                        message=(
                            "Your skin-response reading has risen, which often "
                            "accompanies effort or tension. Soften your breath. "
                            + WELLNESS_DISCLAIMER
                        ),
                        source="physiological",
                        detail=f"GSR {physio.gsr:.1f} vs baseline {self._baseline_gsr:.1f}.",
                    )
                )

        return alerts

    def _fusion_alerts(
        self,
        assessment: Optional[AssessmentResult],
        motion: MotionReading,
        physio_alerts: Sequence[SafetyAlert],
    ) -> List[SafetyAlert]:
        """Combine posture strain with physiological strain.

        Neither signal alone is strong evidence: poor alignment might just be
        a beginner learning, and a raised heart rate is normal in a vigorous
        pose. Together they are a reasonable prompt to back off, which is the
        sensor-fusion behaviour the spec describes.
        """
        if assessment is None or not assessment.detected or not assessment.reliable:
            return []
        if not physio_alerts:
            return []

        strained_posture = assessment.overall < 65 or not motion.stable
        physio_strain = any(a.severity in ("caution", "rest") for a in physio_alerts)

        if strained_posture and physio_strain:
            return [
                SafetyAlert(
                    code="high_effort_detected",
                    severity="rest",
                    message=(
                        "High effort detected: your alignment is slipping and your "
                        "body readings are elevated. Return to a neutral position "
                        "and rest before continuing. " + WELLNESS_DISCLAIMER
                    ),
                    source="fusion",
                    detail=(
                        f"Alignment {assessment.overall:.0f}%, "
                        f"movement {motion.speed:.1f} torso-lengths/s, "
                        f"plus {len(physio_alerts)} sensor indicator(s)."
                    ),
                )
            ]
        return []
