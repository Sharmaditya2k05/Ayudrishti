"""Feature extraction for pose recognition.

Raw landmark pixels are a poor input to a classifier: they change when the
practitioner moves closer to the camera, shifts left, or is simply taller.
This module converts a frame into features that survive all three.

Two feature families are produced:

* **Joint angles** -- scale, translation and (mostly) rotation invariant by
  construction. A 90-degree knee is 90 degrees from any distance.
* **Normalised coordinates** -- every landmark re-expressed relative to the
  hip centre and divided by torso length, which captures the *shape* of the
  pose (arms overhead vs arms out) that angles alone miss.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from ..pose_assessment import geometry as geo
from ..pose_detection.landmarks import PoseFrame

# Joints measured as (name, (landmark_a, vertex, landmark_c)).
ANGLE_FEATURES: Tuple[Tuple[str, Tuple[str, str, str]], ...] = (
    ("left_elbow", ("left_shoulder", "left_elbow", "left_wrist")),
    ("right_elbow", ("right_shoulder", "right_elbow", "right_wrist")),
    ("left_shoulder", ("left_elbow", "left_shoulder", "left_hip")),
    ("right_shoulder", ("right_elbow", "right_shoulder", "right_hip")),
    ("left_hip", ("left_shoulder", "left_hip", "left_knee")),
    ("right_hip", ("right_shoulder", "right_hip", "right_knee")),
    ("left_knee", ("left_hip", "left_knee", "left_ankle")),
    ("right_knee", ("right_hip", "right_knee", "right_ankle")),
    ("left_torso_leg", ("left_shoulder", "left_hip", "left_ankle")),
    ("right_torso_leg", ("right_shoulder", "right_hip", "right_ankle")),
)

# Segment orientations relative to vertical -- these distinguish poses that
# share joint angles but differ in how the body is oriented in space, such as
# Tadasana (torso up) versus Bhujangasana (torso pitched forward).
ORIENTATION_FEATURES: Tuple[Tuple[str, Tuple[str, str]], ...] = (
    ("torso_left", ("left_shoulder", "left_hip")),
    ("torso_right", ("right_shoulder", "right_hip")),
    ("left_thigh", ("left_hip", "left_knee")),
    ("right_thigh", ("right_hip", "right_knee")),
    ("left_shin", ("left_knee", "left_ankle")),
    ("right_shin", ("right_knee", "right_ankle")),
    ("left_upper_arm", ("left_shoulder", "left_elbow")),
    ("right_upper_arm", ("right_shoulder", "right_elbow")),
    ("shoulder_line", ("left_shoulder", "right_shoulder")),
    ("hip_line", ("left_hip", "right_hip")),
)

# Landmarks whose normalised position is kept as a shape descriptor.
SHAPE_LANDMARKS: Tuple[str, ...] = (
    "nose",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)

# Sentinel for a feature that could not be measured. Kept out of the [0, 1]
# range that valid normalised features occupy so a model can learn to treat
# it as "missing" rather than as a plausible value.
MISSING = -1.0


def feature_names() -> List[str]:
    """Column names for the vector produced by :func:`extract_features`."""
    names = [f"angle_{n}" for n, _ in ANGLE_FEATURES]
    names += [f"vert_{n}" for n, _ in ORIENTATION_FEATURES]
    for lm in SHAPE_LANDMARKS:
        names += [f"{lm}_x", f"{lm}_y"]
    names += ["aspect_ratio", "shoulder_hip_ratio", "vertical_extent"]
    return names


def extract_features(frame: PoseFrame, visibility_threshold: float = 0.5) -> List[float]:
    """Turn a frame into a fixed-length numeric vector.

    The layout is stable across calls and matches :func:`feature_names`, so
    a model trained on one build keeps working on the next as long as this
    function is unchanged.
    """
    feats: List[float] = []

    def point(name: str) -> Optional[Tuple[float, float]]:
        lm = frame.get(name)
        if lm is None or not lm.is_visible(visibility_threshold):
            return None
        return lm.xy

    # --- joint angles, scaled from degrees into [0, 1] ---------------------
    for _, (a, b, c) in ANGLE_FEATURES:
        pa, pb, pc = point(a), point(b), point(c)
        if pa is None or pb is None or pc is None:
            feats.append(MISSING)
            continue
        ang = geo.joint_angle(pa, pb, pc)
        feats.append(MISSING if ang is None else ang / 180.0)

    # --- segment orientations relative to vertical -------------------------
    for _, (a, b) in ORIENTATION_FEATURES:
        pa, pb = point(a), point(b)
        if pa is None or pb is None:
            feats.append(MISSING)
            continue
        ang = geo.segment_angle_to_vertical(pa, pb)
        feats.append(MISSING if ang is None else ang / 180.0)

    # --- normalised shape coordinates --------------------------------------
    hip_center = frame.hip_center
    scale = frame.torso_length
    for lm in SHAPE_LANDMARKS:
        p = point(lm)
        if p is None or hip_center is None or scale < 1e-6:
            feats.extend([MISSING, MISSING])
            continue
        # Origin at the hips, one unit = one torso length, y positive upward.
        feats.append((p[0] - hip_center[0]) / scale)
        feats.append((hip_center[1] - p[1]) / scale)

    # --- whole-body proportions --------------------------------------------
    feats.extend(_body_proportions(frame, visibility_threshold))
    return feats


def _body_proportions(frame: PoseFrame, visibility_threshold: float) -> List[float]:
    """Coarse descriptors of the silhouette as a whole.

    Aspect ratio alone separates upright standing poses from the low, wide
    silhouettes of Downward Dog and Child's Pose before any joint is examined.
    """
    pts = [
        lm.xy
        for lm in frame.landmarks.values()
        if lm.is_visible(visibility_threshold) and lm.name in SHAPE_LANDMARKS
    ]
    if len(pts) < 4:
        return [MISSING, MISSING, MISSING]

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    aspect = width / height if height > 1e-6 else MISSING

    scale = frame.torso_length
    sc, hc = frame.shoulder_center, frame.hip_center
    if sc is None or hc is None or scale < 1e-6:
        shoulder_hip = MISSING
        vertical_extent = MISSING
    else:
        # How far the shoulders sit above the hips, signed: negative in
        # inverted or prone poses, strongly positive when standing tall.
        shoulder_hip = (hc[1] - sc[1]) / scale
        vertical_extent = height / scale

    return [aspect, shoulder_hip, vertical_extent]


def extract_batch(
    frames: Sequence[PoseFrame], visibility_threshold: float = 0.5
) -> List[List[float]]:
    return [extract_features(f, visibility_threshold) for f in frames]


def features_to_dict(features: Sequence[float]) -> Dict[str, float]:
    """Pair a raw vector with its column names, for inspection and debugging."""
    return dict(zip(feature_names(), features))
