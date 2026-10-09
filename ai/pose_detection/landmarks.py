"""Body landmark model shared by every AyuDrishti component.

MediaPipe Pose emits 33 landmarks. We wrap them in a small, explicit data
model so that the rest of the system (assessment rules, recognition
features, the REST API, the mobile client) can refer to landmarks by
readable name -- "left_knee" -- instead of a magic index.

Coordinates are normalised to the frame: x and y in [0, 1] with the origin
at the top-left of the image, z roughly in torso-relative units (negative =
closer to the camera). ``visibility`` is the detector's own confidence that
the landmark is present and not occluded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Canonical MediaPipe Pose landmark order (33 points). Do not reorder --
# index position is the wire format used by the detector and the API.
LANDMARK_NAMES: Tuple[str, ...] = (
    "nose",
    "left_eye_inner",
    "left_eye",
    "left_eye_outer",
    "right_eye_inner",
    "right_eye",
    "right_eye_outer",
    "left_ear",
    "right_ear",
    "mouth_left",
    "mouth_right",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_pinky",
    "right_pinky",
    "left_index",
    "right_index",
    "left_thumb",
    "right_thumb",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
    "left_heel",
    "right_heel",
    "left_foot_index",
    "right_foot_index",
)

LANDMARK_INDEX: Dict[str, int] = {name: i for i, name in enumerate(LANDMARK_NAMES)}

# Landmarks that actually matter for yoga alignment. The face mesh points
# (eyes, mouth, ears) are noisy and carry no alignment information, so
# assessment and recognition ignore them.
BODY_LANDMARKS: Tuple[str, ...] = (
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
    "left_heel",
    "right_heel",
    "left_foot_index",
    "right_foot_index",
)

# Skeleton edges used for the overlay drawn on the camera preview.
POSE_CONNECTIONS: Tuple[Tuple[str, str], ...] = (
    ("left_shoulder", "right_shoulder"),
    ("left_shoulder", "left_elbow"),
    ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"),
    ("right_elbow", "right_wrist"),
    ("left_shoulder", "left_hip"),
    ("right_shoulder", "right_hip"),
    ("left_hip", "right_hip"),
    ("left_hip", "left_knee"),
    ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"),
    ("right_knee", "right_ankle"),
    ("left_ankle", "left_heel"),
    ("left_heel", "left_foot_index"),
    ("right_ankle", "right_heel"),
    ("right_heel", "right_foot_index"),
)

# Below this visibility score we treat a landmark as "not reliably seen" and
# refuse to score any rule that depends on it, rather than inventing an
# assessment from a guessed joint position.
DEFAULT_VISIBILITY_THRESHOLD = 0.5


@dataclass(frozen=True)
class Landmark:
    """A single detected body point."""

    name: str
    x: float
    y: float
    z: float = 0.0
    visibility: float = 0.0

    @property
    def xy(self) -> Tuple[float, float]:
        return (self.x, self.y)

    @property
    def xyz(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def is_visible(self, threshold: float = DEFAULT_VISIBILITY_THRESHOLD) -> bool:
        return self.visibility >= threshold

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "x": round(self.x, 5),
            "y": round(self.y, 5),
            "z": round(self.z, 5),
            "visibility": round(self.visibility, 4),
        }


@dataclass
class PoseFrame:
    """All landmarks detected in one video frame, plus frame metadata."""

    landmarks: Dict[str, Landmark] = field(default_factory=dict)
    timestamp: float = 0.0
    frame_index: int = 0
    image_width: int = 0
    image_height: int = 0
    detected: bool = True

    # ---- construction -------------------------------------------------

    @classmethod
    def from_sequence(
        cls,
        points: Sequence[Sequence[float]],
        *,
        timestamp: float = 0.0,
        frame_index: int = 0,
        image_width: int = 0,
        image_height: int = 0,
    ) -> "PoseFrame":
        """Build a frame from raw ``[x, y, z, visibility]`` rows.

        This is the format the mobile client posts to ``/assessment/pose``
        and the format the MediaPipe adapters normalise to, so it is the
        single entry point for landmark data into the system.
        """
        landmarks: Dict[str, Landmark] = {}
        for i, row in enumerate(points):
            if i >= len(LANDMARK_NAMES):
                break
            x = float(row[0]) if len(row) > 0 else 0.0
            y = float(row[1]) if len(row) > 1 else 0.0
            z = float(row[2]) if len(row) > 2 else 0.0
            vis = float(row[3]) if len(row) > 3 else 1.0
            landmarks[LANDMARK_NAMES[i]] = Landmark(LANDMARK_NAMES[i], x, y, z, vis)
        return cls(
            landmarks=landmarks,
            timestamp=timestamp,
            frame_index=frame_index,
            image_width=image_width,
            image_height=image_height,
            detected=bool(landmarks),
        )

    @classmethod
    def from_mapping(
        cls, mapping: Dict[str, Sequence[float]], **kwargs: object
    ) -> "PoseFrame":
        """Build a frame from a ``{landmark_name: [x, y, z, visibility]}`` dict.

        Convenient for tests and for fixture data that only specifies the
        handful of landmarks a particular rule cares about.
        """
        landmarks: Dict[str, Landmark] = {}
        for name, row in mapping.items():
            if name not in LANDMARK_INDEX:
                continue
            x = float(row[0]) if len(row) > 0 else 0.0
            y = float(row[1]) if len(row) > 1 else 0.0
            z = float(row[2]) if len(row) > 2 else 0.0
            vis = float(row[3]) if len(row) > 3 else 1.0
            landmarks[name] = Landmark(name, x, y, z, vis)
        frame = cls(landmarks=landmarks, detected=bool(landmarks))
        for key, value in kwargs.items():
            if hasattr(frame, key):
                setattr(frame, key, value)
        return frame

    @classmethod
    def empty(cls, *, timestamp: float = 0.0, frame_index: int = 0) -> "PoseFrame":
        return cls(
            landmarks={}, timestamp=timestamp, frame_index=frame_index, detected=False
        )

    # ---- access -------------------------------------------------------

    def get(self, name: str) -> Optional[Landmark]:
        return self.landmarks.get(name)

    def __contains__(self, name: object) -> bool:
        return name in self.landmarks

    def require(
        self, names: Iterable[str], threshold: float = DEFAULT_VISIBILITY_THRESHOLD
    ) -> bool:
        """True when every named landmark exists and is confidently visible."""
        for name in names:
            lm = self.landmarks.get(name)
            if lm is None or not lm.is_visible(threshold):
                return False
        return True

    def missing(
        self, names: Iterable[str], threshold: float = DEFAULT_VISIBILITY_THRESHOLD
    ) -> List[str]:
        """Which of ``names`` are absent or too low-confidence to trust."""
        out: List[str] = []
        for name in names:
            lm = self.landmarks.get(name)
            if lm is None or not lm.is_visible(threshold):
                out.append(name)
        return out

    def mean_visibility(self, names: Iterable[str] = BODY_LANDMARKS) -> float:
        vals = [self.landmarks[n].visibility for n in names if n in self.landmarks]
        return sum(vals) / len(vals) if vals else 0.0

    # ---- derived geometry --------------------------------------------

    def midpoint(self, a: str, b: str) -> Optional[Tuple[float, float]]:
        la, lb = self.landmarks.get(a), self.landmarks.get(b)
        if la is None or lb is None:
            return None
        return ((la.x + lb.x) / 2.0, (la.y + lb.y) / 2.0)

    @property
    def hip_center(self) -> Optional[Tuple[float, float]]:
        return self.midpoint("left_hip", "right_hip")

    @property
    def shoulder_center(self) -> Optional[Tuple[float, float]]:
        return self.midpoint("left_shoulder", "right_shoulder")

    @property
    def torso_length(self) -> float:
        """Shoulder-centre to hip-centre distance.

        Used as the scale unit for every distance-based rule so that a
        person standing close to the camera is not judged differently from
        one standing far away.
        """
        sc, hc = self.shoulder_center, self.hip_center
        if sc is None or hc is None:
            return 0.0
        return ((sc[0] - hc[0]) ** 2 + (sc[1] - hc[1]) ** 2) ** 0.5

    def to_dict(self) -> Dict[str, object]:
        return {
            "detected": self.detected,
            "timestamp": self.timestamp,
            "frame_index": self.frame_index,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "landmarks": [lm.to_dict() for lm in self.landmarks.values()],
        }
