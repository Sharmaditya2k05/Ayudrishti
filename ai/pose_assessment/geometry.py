"""Geometric primitives for joint-angle and alignment analysis.

Every measurement the assessment engine makes bottoms out in one of these
functions. They operate on plain ``(x, y)`` tuples so they stay testable
without constructing a full :class:`PoseFrame`.

A note on coordinates: image ``y`` grows downward. Functions that talk
about "up", "height" or "above" compensate for this internally so callers
can reason in ordinary human terms.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence, Tuple

Point = Tuple[float, float]


def distance(a: Point, b: Point) -> float:
    """Euclidean distance between two points."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def midpoint(a: Point, b: Point) -> Point:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def joint_angle(a: Point, b: Point, c: Point) -> Optional[float]:
    """Interior angle at vertex ``b`` formed by ``a-b-c``, in degrees.

    This is the workhorse for joint measurement: ``joint_angle(hip, knee,
    ankle)`` gives knee flexion, where 180 degrees is a fully straight leg
    and 90 degrees is a right angle.

    Returns ``None`` when a limb segment has zero length, which happens if
    the detector collapses two landmarks onto the same pixel.
    """
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 < 1e-9 or n2 < 1e-9:
        return None
    cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    # Guard against floating point pushing cos marginally outside [-1, 1].
    cos = max(-1.0, min(1.0, cos))
    return math.degrees(math.acos(cos))


def segment_angle_to_vertical(a: Point, b: Point) -> Optional[float]:
    """Tilt of segment ``a->b`` away from vertical, in degrees (0-180).

    0 means the segment points straight up or straight down; 90 means it is
    horizontal. Used for rules like "keep your torso upright" or "the raised
    arm should be vertical", where only the magnitude of the lean matters.
    """
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    if math.hypot(dx, dy) < 1e-9:
        return None
    # Angle from the vertical axis, sign-independent.
    return math.degrees(math.atan2(abs(dx), abs(dy)))


def segment_angle_to_horizontal(a: Point, b: Point) -> Optional[float]:
    """Tilt of segment ``a->b`` away from horizontal, in degrees (0-90).

    0 means perfectly level -- the measurement behind "raise both arms to
    shoulder height" and "keep your hips level".
    """
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    if math.hypot(dx, dy) < 1e-9:
        return None
    return math.degrees(math.atan2(abs(dy), abs(dx)))


def signed_lean(a: Point, b: Point) -> Optional[float]:
    """Lean of segment ``a->b`` from vertical, signed, in degrees (-180-180).

    Positive means the far end leans toward increasing ``x`` (screen right).
    Distinguishes "leaning left" from "leaning right" so feedback can name a
    direction instead of just reporting a magnitude.
    """
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    if math.hypot(dx, dy) < 1e-9:
        return None
    # -dy so that "up the screen" is the positive vertical direction.
    return math.degrees(math.atan2(dx, -dy))


def horizontal_offset(a: Point, b: Point, scale: float = 1.0) -> Optional[float]:
    """Horizontal gap between two points, in units of ``scale``.

    With ``scale`` set to the torso length, the result is body-relative and
    therefore independent of how far the practitioner stands from the camera.
    """
    if scale < 1e-9:
        return None
    return abs(a[0] - b[0]) / scale


def vertical_offset(a: Point, b: Point, scale: float = 1.0) -> Optional[float]:
    """Vertical gap between two points, in units of ``scale``."""
    if scale < 1e-9:
        return None
    return abs(a[1] - b[1]) / scale


def signed_vertical_offset(a: Point, b: Point, scale: float = 1.0) -> Optional[float]:
    """How far ``a`` sits above ``b``, in units of ``scale``.

    Positive means ``a`` is higher on screen than ``b``. Flipping the raw
    image delta here keeps the "positive is up" convention for callers.
    """
    if scale < 1e-9:
        return None
    return (b[1] - a[1]) / scale


def signed_horizontal_offset(a: Point, b: Point, scale: float = 1.0) -> Optional[float]:
    """How far ``a`` sits to the right of ``b``, in units of ``scale``."""
    if scale < 1e-9:
        return None
    return (a[0] - b[0]) / scale


def distance_ratio(a: Point, b: Point, c: Point, d: Point) -> Optional[float]:
    """Ratio ``dist(a, b) / dist(c, d)``.

    Expresses one body measurement in terms of another -- for example stance
    width over leg length, which is how Warrior II and Trikonasana check that
    the feet are far enough apart for the practitioner's own proportions.
    """
    denom = distance(c, d)
    if denom < 1e-9:
        return None
    return distance(a, b) / denom


def point_line_distance(p: Point, a: Point, b: Point, scale: float = 1.0) -> Optional[float]:
    """Perpendicular distance from ``p`` to the line through ``a`` and ``b``.

    Measures "is this joint stacked over that one" claims, such as the knee
    tracking over the ankle in Warrior II, or the hip staying on the line
    from shoulder to ankle in a plank.
    """
    if scale < 1e-9:
        return None
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    denom = math.hypot(dx, dy)
    if denom < 1e-9:
        return None
    cross = abs(dx * (a[1] - p[1]) - (a[0] - p[0]) * dy)
    return (cross / denom) / scale


def collinearity(a: Point, b: Point, c: Point) -> Optional[float]:
    """How straight the chain ``a-b-c`` is, as degrees away from a line.

    0 means perfectly straight. Distinct from :func:`joint_angle` only in
    framing -- a "straightness deviation" reads more naturally in rules like
    "keep a straight line from shoulder to hip to ankle".
    """
    ang = joint_angle(a, b, c)
    if ang is None:
        return None
    return abs(180.0 - ang)


def centroid(points: Sequence[Point]) -> Optional[Point]:
    if not points:
        return None
    return (
        sum(p[0] for p in points) / len(points),
        sum(p[1] for p in points) / len(points),
    )


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
