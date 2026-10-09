"""Processing for optional wearable telemetry.

Consumer optical and skin-response sensors are noisy, easily disturbed by
movement, and vary enormously between people. Everything here exists to turn
that raw stream into something conservative enough to act on:

* discard samples the band itself flagged as bad contact,
* smooth over a short window rather than reacting to single readings,
* express results relative to the wearer's own baseline, because absolute
  GSR and heart rate figures mean little across individuals.

Nothing here diagnoses anything. The output feeds the safety layer's
"consider resting" prompts and nothing stronger.
"""

from __future__ import annotations

import json
import statistics
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Iterable, List, Optional

# Physiologically plausible bounds. Readings outside these are sensor
# artefacts (finger moved, electrode lifted) rather than real measurements.
HR_RANGE = (30.0, 220.0)
SPO2_RANGE = (70.0, 100.0)
GSR_RANGE = (0.0, 100.0)
MOTION_RANGE = (0.0, 16.0)

# Samples used to establish the wearer's session baseline.
BASELINE_SAMPLES = 10


@dataclass
class SensorSample:
    """One parsed, validated telemetry reading."""

    heart_rate: Optional[float] = None
    spo2: Optional[float] = None
    gsr: Optional[float] = None
    motion: Optional[float] = None
    device_time_ms: int = 0
    contact: bool = True

    @property
    def has_data(self) -> bool:
        return any(
            v is not None for v in (self.heart_rate, self.spo2, self.gsr, self.motion)
        )

    def to_api_payload(self) -> Dict[str, object]:
        """Shape expected by ``POST /wearables/data``."""
        return {
            "heart_rate": self.heart_rate,
            "spo2": self.spo2,
            "gsr": self.gsr,
            "motion": self.motion,
        }


def _clean(value: object, low: float, high: float) -> Optional[float]:
    """Accept a reading only if it is a number inside a plausible range.

    The firmware reports -1 for "unavailable", which this rejects along with
    anything out of range.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < low or number > high:
        return None
    return number


def parse_telemetry(payload: str | bytes | Dict[str, object]) -> Optional[SensorSample]:
    """Parse one BLE notification from the ESP32 band.

    Returns ``None`` for malformed payloads rather than raising: a corrupt
    BLE packet mid-session must not interrupt the practice.
    """
    if isinstance(payload, (bytes, bytearray)):
        try:
            payload = payload.decode("utf-8")
        except UnicodeDecodeError:
            return None

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None

    if not isinstance(payload, dict):
        return None

    contact = bool(payload.get("ok", True))
    sample = SensorSample(
        heart_rate=_clean(payload.get("hr"), *HR_RANGE),
        spo2=_clean(payload.get("spo2"), *SPO2_RANGE),
        gsr=_clean(payload.get("gsr"), *GSR_RANGE),
        motion=_clean(payload.get("motion"), *MOTION_RANGE),
        device_time_ms=int(payload.get("t", 0) or 0),
        contact=contact,
    )

    if not contact:
        # The band says the finger is off the sensor. Pulse-derived values are
        # meaningless then, but GSR and motion electrodes are unaffected.
        sample.heart_rate = None
        sample.spo2 = None

    return sample if sample.has_data else None


class SignalProcessor:
    """Smooths a telemetry stream and expresses it against a personal baseline."""

    def __init__(self, *, window: int = 8, baseline_samples: int = BASELINE_SAMPLES) -> None:
        self.window = max(1, window)
        self.baseline_samples = max(1, baseline_samples)
        self._hr: Deque[float] = deque(maxlen=self.window)
        self._spo2: Deque[float] = deque(maxlen=self.window)
        self._gsr: Deque[float] = deque(maxlen=self.window)
        self._motion: Deque[float] = deque(maxlen=self.window)
        self._baseline_hr: List[float] = []
        self._baseline_gsr: List[float] = []

    def reset(self) -> None:
        for buf in (self._hr, self._spo2, self._gsr, self._motion):
            buf.clear()
        self._baseline_hr.clear()
        self._baseline_gsr.clear()

    def add(self, sample: SensorSample) -> SensorSample:
        """Ingest a sample and return the smoothed current state."""
        if sample.heart_rate is not None:
            self._hr.append(sample.heart_rate)
            if len(self._baseline_hr) < self.baseline_samples:
                self._baseline_hr.append(sample.heart_rate)
        if sample.spo2 is not None:
            self._spo2.append(sample.spo2)
        if sample.gsr is not None:
            self._gsr.append(sample.gsr)
            if len(self._baseline_gsr) < self.baseline_samples:
                self._baseline_gsr.append(sample.gsr)
        if sample.motion is not None:
            self._motion.append(sample.motion)

        return SensorSample(
            heart_rate=self._median(self._hr),
            spo2=self._median(self._spo2),
            gsr=self._median(self._gsr),
            motion=self._median(self._motion),
            device_time_ms=sample.device_time_ms,
            contact=sample.contact,
        )

    @staticmethod
    def _median(buffer: Deque[float]) -> Optional[float]:
        """Median, not mean: one spike from a shifted electrode should not
        drag the reported value with it."""
        return statistics.median(buffer) if buffer else None

    # ---- baselines -------------------------------------------------------

    @property
    def baseline_heart_rate(self) -> Optional[float]:
        if len(self._baseline_hr) < self.baseline_samples:
            return None
        return statistics.median(self._baseline_hr)

    @property
    def baseline_gsr(self) -> Optional[float]:
        if len(self._baseline_gsr) < self.baseline_samples:
            return None
        return statistics.median(self._baseline_gsr)

    def heart_rate_elevation(self) -> Optional[float]:
        """Current heart rate as a multiple of this session's baseline."""
        current = self._median(self._hr)
        base = self.baseline_heart_rate
        if current is None or not base:
            return None
        return current / base

    def gsr_elevation(self) -> Optional[float]:
        current = self._median(self._gsr)
        base = self.baseline_gsr
        if current is None or not base:
            return None
        return current / base

    def stillness(self) -> Optional[float]:
        """How still the wearer is, 0 (thrashing) to 1 (motionless).

        Derived from deviation away from 1 g, which is what an accelerometer
        reads at rest under gravity alone.
        """
        if not self._motion:
            return None
        deviation = statistics.mean(abs(m - 1.0) for m in self._motion)
        return max(0.0, 1.0 - min(deviation / 0.6, 1.0))

    def summary(self) -> Dict[str, object]:
        return {
            "heart_rate": self._median(self._hr),
            "spo2": self._median(self._spo2),
            "gsr": self._median(self._gsr),
            "motion": self._median(self._motion),
            "baseline_heart_rate": self.baseline_heart_rate,
            "baseline_gsr": self.baseline_gsr,
            "heart_rate_elevation": self.heart_rate_elevation(),
            "gsr_elevation": self.gsr_elevation(),
            "stillness": self.stillness(),
            "samples": len(self._hr),
        }


def to_snapshot(sample: SensorSample):
    """Convert to the AI layer's :class:`PhysiologicalSnapshot`.

    Imported lazily so this module stays usable from a standalone BLE bridge
    script that has no reason to pull in the assessment engine.
    """
    from ai.safety import PhysiologicalSnapshot

    return PhysiologicalSnapshot(
        heart_rate=sample.heart_rate,
        spo2=sample.spo2,
        gsr=sample.gsr,
        motion_magnitude=sample.motion,
        timestamp=sample.device_time_ms / 1000.0,
    )


def batch_to_api(samples: Iterable[SensorSample]) -> List[Dict[str, object]]:
    """Prepare a batch for ``POST /wearables/data``."""
    return [s.to_api_payload() for s in samples if s.has_data]
