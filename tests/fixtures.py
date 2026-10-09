"""Hand-built reference skeletons used across the test suite.

Each fixture is a set of normalised image coordinates (x right, y down, both
in [0, 1]) laid out to represent a competently performed asana. They let us
test the assessment engine deterministically, without a camera and without
shipping video files in the repository.

The "good" skeletons are drawn to satisfy their asana's rules; the helpers
below then perturb specific joints so tests can assert that a known fault
produces the expected correction.
"""

from __future__ import annotations

from typing import Dict, Tuple

from ai.pose_detection.landmarks import LANDMARK_NAMES, PoseFrame

Coords = Dict[str, Tuple[float, float]]


def build_frame(coords: Coords, visibility: float = 0.95) -> PoseFrame:
    """Turn a partial ``{landmark: (x, y)}`` map into a full PoseFrame.

    Landmarks not supplied are marked invisible rather than placed at the
    origin, so rules that depend on them report "unavailable" instead of
    silently scoring against a bogus point at (0, 0).
    """
    mapping = {}
    for name in LANDMARK_NAMES:
        if name in coords:
            x, y = coords[name]
            mapping[name] = [x, y, 0.0, visibility]
        else:
            mapping[name] = [0.0, 0.0, 0.0, 0.0]
    return PoseFrame.from_mapping(mapping, image_width=720, image_height=1280)


def _head(x: float, y: float) -> Coords:
    """Approximate face landmarks around a nose position."""
    return {
        "nose": (x, y),
        "left_eye": (x - 0.02, y - 0.01),
        "right_eye": (x + 0.02, y - 0.01),
        "left_ear": (x - 0.04, y),
        "right_ear": (x + 0.04, y),
    }


# ---------------------------------------------------------------------------
# Reference skeletons
# ---------------------------------------------------------------------------

def warrior_ii_good() -> Coords:
    """Warrior II, front view, leading with the left leg.

    Front thigh parallel to the floor with the shin vertical (so the knee
    stacks over the ankle), back leg straight, arms level at shoulder height.
    """
    coords: Coords = {
        "left_shoulder": (0.40, 0.38),
        "right_shoulder": (0.60, 0.38),
        "left_elbow": (0.22, 0.38),
        "right_elbow": (0.78, 0.38),
        "left_wrist": (0.04, 0.38),
        "right_wrist": (0.96, 0.38),
        "left_hip": (0.42, 0.62),
        "right_hip": (0.58, 0.62),
        "left_knee": (0.16, 0.63),
        "right_knee": (0.72, 0.77),
        "left_ankle": (0.14, 0.92),
        "right_ankle": (0.86, 0.92),
        "left_heel": (0.15, 0.94),
        "right_heel": (0.87, 0.94),
        "left_foot_index": (0.09, 0.95),
        "right_foot_index": (0.92, 0.95),
    }
    coords.update(_head(0.50, 0.30))
    return coords


def tadasana_good() -> Coords:
    """Mountain pose, front view: feet together, arms at the sides."""
    coords: Coords = {
        "left_shoulder": (0.44, 0.30),
        "right_shoulder": (0.56, 0.30),
        "left_elbow": (0.43, 0.44),
        "right_elbow": (0.57, 0.44),
        "left_wrist": (0.42, 0.57),
        "right_wrist": (0.58, 0.57),
        "left_hip": (0.46, 0.55),
        "right_hip": (0.54, 0.55),
        "left_knee": (0.465, 0.74),
        "right_knee": (0.535, 0.74),
        "left_ankle": (0.47, 0.93),
        "right_ankle": (0.53, 0.93),
        "left_heel": (0.47, 0.95),
        "right_heel": (0.53, 0.95),
        "left_foot_index": (0.46, 0.97),
        "right_foot_index": (0.54, 0.97),
    }
    coords.update(_head(0.50, 0.22))
    return coords


def trikonasana_good() -> Coords:
    """Triangle pose, front view, leading with the left leg.

    Both legs straight, torso tilted sideways over the front leg, arms
    stacked in one vertical line.
    """
    coords: Coords = {
        # Torso tilted about 50 degrees from vertical toward the left leg.
        "left_shoulder": (0.30, 0.52),
        "right_shoulder": (0.44, 0.42),
        "left_elbow": (0.24, 0.68),
        "right_elbow": (0.47, 0.27),
        "left_wrist": (0.19, 0.83),
        "right_wrist": (0.50, 0.12),
        "left_hip": (0.44, 0.66),
        "right_hip": (0.58, 0.62),
        "left_knee": (0.29, 0.79),
        "right_knee": (0.72, 0.77),
        "left_ankle": (0.14, 0.92),
        "right_ankle": (0.86, 0.92),
        "left_heel": (0.13, 0.94),
        "right_heel": (0.87, 0.94),
        "left_foot_index": (0.09, 0.95),
        "right_foot_index": (0.92, 0.95),
    }
    coords.update(_head(0.34, 0.44))
    return coords


def utkatasana_good() -> Coords:
    """Chair pose, side view facing screen-left.

    Judged from the side because knee flexion -- the whole point of the pose
    -- is foreshortened to nothing in a head-on view.
    """
    coords: Coords = {
        "left_shoulder": (0.42, 0.36),
        "right_shoulder": (0.42, 0.38),
        "left_elbow": (0.40, 0.26),
        "right_elbow": (0.40, 0.28),
        "left_wrist": (0.38, 0.16),
        "right_wrist": (0.38, 0.18),
        "left_hip": (0.62, 0.62),
        "right_hip": (0.62, 0.64),
        "left_knee": (0.44, 0.72),
        "right_knee": (0.44, 0.74),
        "left_ankle": (0.48, 0.93),
        "right_ankle": (0.48, 0.95),
        "left_heel": (0.50, 0.95),
        "right_heel": (0.50, 0.97),
        "left_foot_index": (0.42, 0.95),
        "right_foot_index": (0.42, 0.97),
    }
    coords.update(_head(0.36, 0.30))
    return coords


def vrikshasana_good() -> Coords:
    """Tree pose, front view: standing on the right leg, left foot lifted."""
    coords: Coords = {
        "left_shoulder": (0.44, 0.30),
        "right_shoulder": (0.56, 0.30),
        "left_elbow": (0.42, 0.42),
        "right_elbow": (0.58, 0.42),
        "left_wrist": (0.47, 0.24),
        "right_wrist": (0.53, 0.24),
        "left_hip": (0.46, 0.55),
        "right_hip": (0.54, 0.55),
        # Lifted (left) leg: knee opens out to the side, foot at the inner thigh.
        "left_knee": (0.30, 0.63),
        "left_ankle": (0.50, 0.70),
        "left_heel": (0.52, 0.71),
        "left_foot_index": (0.47, 0.72),
        # Standing (right) leg: straight.
        "right_knee": (0.545, 0.74),
        "right_ankle": (0.55, 0.93),
        "right_heel": (0.55, 0.95),
        "right_foot_index": (0.54, 0.97),
    }
    coords.update(_head(0.50, 0.22))
    return coords


def balasana_good() -> Coords:
    """Child's pose, side view facing screen-left: hips back, torso folded."""
    coords: Coords = {
        "left_shoulder": (0.42, 0.72),
        "right_shoulder": (0.42, 0.74),
        "left_elbow": (0.30, 0.76),
        "right_elbow": (0.30, 0.78),
        "left_wrist": (0.18, 0.80),
        "right_wrist": (0.18, 0.82),
        "left_hip": (0.66, 0.68),
        "right_hip": (0.66, 0.70),
        "left_knee": (0.50, 0.82),
        "right_knee": (0.50, 0.84),
        "left_ankle": (0.72, 0.86),
        "right_ankle": (0.72, 0.88),
        "left_heel": (0.75, 0.86),
        "right_heel": (0.75, 0.88),
        "left_foot_index": (0.78, 0.88),
        "right_foot_index": (0.78, 0.90),
    }
    coords.update(_head(0.30, 0.80))
    return coords


def bhujangasana_good() -> Coords:
    """Cobra, side view facing screen-left: chest lifted, hips grounded."""
    coords: Coords = {
        "left_shoulder": (0.34, 0.58),
        "right_shoulder": (0.34, 0.60),
        "left_elbow": (0.32, 0.72),
        "right_elbow": (0.32, 0.74),
        "left_wrist": (0.36, 0.86),
        "right_wrist": (0.36, 0.88),
        "left_hip": (0.58, 0.86),
        "right_hip": (0.58, 0.88),
        "left_knee": (0.76, 0.89),
        "right_knee": (0.76, 0.91),
        "left_ankle": (0.92, 0.90),
        "right_ankle": (0.92, 0.92),
        "left_heel": (0.94, 0.89),
        "right_heel": (0.94, 0.91),
        "left_foot_index": (0.96, 0.92),
        "right_foot_index": (0.96, 0.94),
    }
    coords.update(_head(0.28, 0.48))
    return coords


def downward_dog_good() -> Coords:
    """Downward dog, side view facing screen-left: hips high, back long."""
    coords: Coords = {
        "left_shoulder": (0.32, 0.56),
        "right_shoulder": (0.32, 0.58),
        "left_elbow": (0.26, 0.70),
        "right_elbow": (0.26, 0.72),
        "left_wrist": (0.20, 0.86),
        "right_wrist": (0.20, 0.88),
        "left_hip": (0.60, 0.30),
        "right_hip": (0.60, 0.32),
        "left_knee": (0.70, 0.58),
        "right_knee": (0.70, 0.60),
        "left_ankle": (0.78, 0.86),
        "right_ankle": (0.78, 0.88),
        "left_heel": (0.80, 0.88),
        "right_heel": (0.80, 0.90),
        "left_foot_index": (0.74, 0.90),
        "right_foot_index": (0.74, 0.92),
    }
    coords.update(_head(0.28, 0.66))
    return coords


def setu_bandhasana_good() -> Coords:
    """Bridge, side view facing screen-left: hips lifted into a straight ramp."""
    coords: Coords = {
        "left_shoulder": (0.26, 0.80),
        "right_shoulder": (0.26, 0.82),
        "left_elbow": (0.34, 0.86),
        "right_elbow": (0.34, 0.88),
        "left_wrist": (0.44, 0.88),
        "right_wrist": (0.44, 0.90),
        "left_hip": (0.54, 0.62),
        "right_hip": (0.54, 0.64),
        "left_knee": (0.74, 0.60),
        "right_knee": (0.74, 0.62),
        "left_ankle": (0.76, 0.88),
        "right_ankle": (0.76, 0.90),
        "left_heel": (0.78, 0.90),
        "right_heel": (0.78, 0.92),
        "left_foot_index": (0.70, 0.91),
        "right_foot_index": (0.70, 0.93),
    }
    coords.update(_head(0.20, 0.83))
    return coords


def paschimottanasana_good() -> Coords:
    """Seated forward bend, side view facing screen-right: legs straight."""
    coords: Coords = {
        "left_shoulder": (0.52, 0.62),
        "right_shoulder": (0.52, 0.64),
        "left_elbow": (0.66, 0.66),
        "right_elbow": (0.66, 0.68),
        "left_wrist": (0.80, 0.72),
        "right_wrist": (0.80, 0.74),
        "left_hip": (0.30, 0.78),
        "right_hip": (0.30, 0.80),
        "left_knee": (0.58, 0.80),
        "right_knee": (0.58, 0.82),
        "left_ankle": (0.86, 0.80),
        "right_ankle": (0.86, 0.82),
        "left_heel": (0.88, 0.83),
        "right_heel": (0.88, 0.85),
        "left_foot_index": (0.88, 0.74),
        "right_foot_index": (0.88, 0.76),
    }
    coords.update(_head(0.58, 0.66))
    return coords


REFERENCE_POSES = {
    "tadasana": tadasana_good,
    "virabhadrasana_ii": warrior_ii_good,
    "trikonasana": trikonasana_good,
    "vrikshasana": vrikshasana_good,
    "utkatasana": utkatasana_good,
    "balasana": balasana_good,
    "bhujangasana": bhujangasana_good,
    "adho_mukha_svanasana": downward_dog_good,
    "setu_bandhasana": setu_bandhasana_good,
    "paschimottanasana": paschimottanasana_good,
}


def perturb(coords: Coords, **moves: Tuple[float, float]) -> Coords:
    """Return a copy of ``coords`` with named landmarks shifted by (dx, dy).

    Used to introduce one specific, named fault into an otherwise correct
    skeleton so a test can assert the engine catches exactly that fault.
    """
    out = dict(coords)
    for name, (dx, dy) in moves.items():
        if name in out:
            x, y = out[name]
            out[name] = (x + dx, y + dy)
    return out
