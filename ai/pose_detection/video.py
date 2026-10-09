"""OpenCV camera handling and skeleton overlays.

Used by the development/desktop runner (``scripts/live_session.py``) and by
any offline evaluation over recorded video. The mobile client does its own
capture and drawing; this exists so the whole pipeline can be exercised on a
laptop webcam without building the React Native app first.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from .landmarks import POSE_CONNECTIONS, PoseFrame

# BGR colours, since OpenCV works in BGR.
COLOR_GOOD = (110, 200, 90)
COLOR_WARN = (60, 190, 250)
COLOR_BAD = (70, 70, 235)
COLOR_NEUTRAL = (220, 220, 220)
COLOR_TEXT = (245, 245, 245)
COLOR_PANEL = (35, 30, 28)

STATUS_COLORS = {
    "good": COLOR_GOOD,
    "adjust": COLOR_WARN,
    "off": COLOR_BAD,
    "unknown": COLOR_NEUTRAL,
}


class CameraUnavailable(RuntimeError):
    """Raised when the requested camera or video file cannot be opened."""


@dataclass
class VideoSource:
    """A camera or video file, yielding frames with real timestamps.

    Timestamps come from the capture clock for files and from wall time for
    live cameras, because motion analysis and the Tasks API both need a
    truthful elapsed time rather than an assumed frame rate.
    """

    source: object = 0
    width: Optional[int] = None
    height: Optional[int] = None
    mirror: bool = True

    def __post_init__(self) -> None:
        self._cap = None
        self._is_file = isinstance(self.source, str)

    def open(self) -> "VideoSource":
        import cv2

        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            raise CameraUnavailable(
                f"Could not open video source {self.source!r}. "
                "Check the camera index, permissions, or file path."
            )
        if self.width:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap = cap
        return self

    def frames(self) -> Iterator[Tuple[object, float]]:
        """Yield ``(image, timestamp_seconds)`` until the source ends."""
        import time

        import cv2

        if self._cap is None:
            self.open()

        start = time.monotonic()
        while True:
            ok, image = self._cap.read()
            if not ok:
                break
            if self.mirror and not self._is_file:
                # Mirror the webcam so the practitioner's left appears on the
                # left, as in a mirror. Landmark names are unaffected: the
                # detector runs on the flipped image, so "left_knee" is the
                # knee the user sees on their left.
                image = cv2.flip(image, 1)
            if self._is_file:
                ts = self._cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            else:
                ts = time.monotonic() - start
            yield image, ts

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> "VideoSource":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.release()


def draw_skeleton(
    image,
    frame: PoseFrame,
    *,
    highlight: Optional[Sequence[str]] = None,
    color: Tuple[int, int, int] = COLOR_GOOD,
    highlight_color: Tuple[int, int, int] = COLOR_BAD,
    thickness: int = 2,
    radius: int = 4,
):
    """Draw the pose skeleton, emphasising landmarks under correction."""
    import cv2

    if not frame.detected:
        return image

    height, width = image.shape[:2]
    highlight_set = set(highlight or ())

    def pixel(name: str) -> Optional[Tuple[int, int]]:
        lm = frame.get(name)
        if lm is None or not lm.is_visible():
            return None
        return (int(lm.x * width), int(lm.y * height))

    for a, b in POSE_CONNECTIONS:
        pa, pb = pixel(a), pixel(b)
        if pa is None or pb is None:
            continue
        flagged = a in highlight_set and b in highlight_set
        cv2.line(
            image,
            pa,
            pb,
            highlight_color if flagged else color,
            thickness + (1 if flagged else 0),
            cv2.LINE_AA,
        )

    for name in frame.landmarks:
        point = pixel(name)
        if point is None:
            continue
        flagged = name in highlight_set
        cv2.circle(
            image,
            point,
            radius + (2 if flagged else 0),
            highlight_color if flagged else color,
            -1,
            cv2.LINE_AA,
        )
    return image


def draw_session_overlay(
    image,
    *,
    asana_name: str = "",
    score: Optional[float] = None,
    indicators: Sequence[object] = (),
    messages: Sequence[str] = (),
    confidence: Optional[float] = None,
):
    """Render the live coaching panel: pose, score, indicators, corrections."""
    import cv2

    height, width = image.shape[:2]
    panel_height = 30 + 26 * (len(indicators) + len(messages)) + 40
    panel_height = min(panel_height, height - 20)

    overlay = image.copy()
    cv2.rectangle(overlay, (10, 10), (min(470, width - 10), panel_height), COLOR_PANEL, -1)
    cv2.addWeighted(overlay, 0.72, image, 0.28, 0, image)

    y = 42
    title = asana_name or "Detecting pose..."
    cv2.putText(image, title, (24, y), cv2.FONT_HERSHEY_SIMPLEX, 0.78, COLOR_TEXT, 2, cv2.LINE_AA)

    if score is not None:
        colour = COLOR_GOOD if score >= 80 else COLOR_WARN if score >= 65 else COLOR_BAD
        label = f"{score:.0f}%"
        cv2.putText(
            image, label, (24, y + 34), cv2.FONT_HERSHEY_SIMPLEX, 0.95, colour, 2, cv2.LINE_AA
        )
        if confidence is not None and confidence < 0.99:
            cv2.putText(
                image,
                f"match {confidence * 100:.0f}%",
                (120, y + 34),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                COLOR_NEUTRAL,
                1,
                cv2.LINE_AA,
            )
        y += 34

    y += 28
    for ind in indicators:
        status = getattr(ind, "status", "unknown")
        label = getattr(ind, "label", "")
        value = getattr(ind, "score", 0.0)
        mark = {"good": "OK", "adjust": "~", "off": "!", "unknown": "?"}.get(status, "?")
        cv2.putText(
            image,
            f"[{mark}] {label}: {value:.0f}%",
            (24, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            STATUS_COLORS.get(status, COLOR_NEUTRAL),
            1,
            cv2.LINE_AA,
        )
        y += 24

    if messages:
        y += 6
    for text in messages:
        for line in _wrap(text, 52):
            cv2.putText(
                image, line, (24, y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, COLOR_TEXT, 1, cv2.LINE_AA
            )
            y += 22
    return image


def _wrap(text: str, width: int) -> List[str]:
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines
