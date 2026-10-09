"""MediaPipe Pose adapter.

MediaPipe ships two very different Python APIs and which one is available
depends on the installed version:

* **Tasks API** (``mediapipe.tasks.python.vision.PoseLandmarker``) -- the
  current interface, used from 0.10 onward and the *only* one in 1.x. It
  needs a ``.task`` model bundle on disk.
* **Legacy Solutions API** (``mp.solutions.pose.Pose``) -- removed in 1.0,
  but still what most tutorials and older environments use. Bundles its own
  model.

Rather than pinning one and breaking on the other, this module detects what
is installed and adapts. Both paths emit the same :class:`PoseFrame`, so no
other part of AyuDrishti knows or cares which is in use.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Sequence

from .landmarks import LANDMARK_NAMES, PoseFrame

# Where fetch_models.py places the Tasks bundle.
DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[2] / "data" / "models"
DEFAULT_MODEL_NAME = "pose_landmarker_lite.task"


class DetectorUnavailable(RuntimeError):
    """Raised when no usable MediaPipe backend could be initialised.

    The message explains how to fix it, because this is the single most
    likely setup failure for a new developer on the project.
    """


class PoseDetector:
    """Detects body landmarks in images or video frames.

    Usage::

        detector = PoseDetector()
        frame = detector.detect(bgr_image, timestamp=1.5)
        if frame.detected:
            ...
    """

    def __init__(
        self,
        *,
        model_path: Optional[str] = None,
        static_image_mode: bool = False,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        model_complexity: int = 1,
    ) -> None:
        self.static_image_mode = static_image_mode
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.model_complexity = model_complexity
        self.model_path = model_path or os.environ.get("AYUDRISHTI_POSE_MODEL")

        self.backend: str = "none"
        self._impl = None
        self._frame_index = 0
        self._last_timestamp_ms = -1

        self._initialise()

    # ---- setup -----------------------------------------------------------

    def _initialise(self) -> None:
        try:
            import mediapipe as mp  # noqa: F401
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise DetectorUnavailable(
                "mediapipe is not installed. Install it with:\n"
                "    pip install mediapipe\n"
                "Landmarks can also be sent from the mobile client instead, in "
                "which case the backend never needs a detector."
            ) from exc

        if self._try_legacy():
            return
        if self._try_tasks():
            return

        raise DetectorUnavailable(
            "MediaPipe is installed but no pose backend could be started.\n"
            "For MediaPipe 1.x the Tasks model bundle is required. Fetch it with:\n"
            "    python scripts/fetch_models.py\n"
            f"or set AYUDRISHTI_POSE_MODEL to a {DEFAULT_MODEL_NAME} file."
        )

    def _try_legacy(self) -> bool:
        """Legacy Solutions API: self-contained, no model file needed."""
        try:
            import mediapipe as mp

            solutions = getattr(mp, "solutions", None)
            if solutions is None or not hasattr(solutions, "pose"):
                return False
            self._impl = solutions.pose.Pose(
                static_image_mode=self.static_image_mode,
                model_complexity=self.model_complexity,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
            )
            self.backend = "solutions"
            return True
        except Exception:
            return False

    def _try_tasks(self) -> bool:
        """Tasks API: current interface, requires a .task bundle on disk."""
        try:
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
        except Exception:
            return False

        path = self._resolve_model_path()
        if path is None:
            return False

        try:
            options = vision.PoseLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(path)),
                running_mode=(
                    vision.RunningMode.IMAGE
                    if self.static_image_mode
                    else vision.RunningMode.VIDEO
                ),
                num_poses=1,
                min_pose_detection_confidence=self.min_detection_confidence,
                min_pose_presence_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
            )
            self._impl = vision.PoseLandmarker.create_from_options(options)
            self.backend = "tasks"
            self.model_path = str(path)
            return True
        except Exception:
            return False

    def _resolve_model_path(self) -> Optional[Path]:
        candidates: List[Path] = []
        if self.model_path:
            candidates.append(Path(self.model_path))
        candidates.append(DEFAULT_MODEL_DIR / DEFAULT_MODEL_NAME)
        candidates.extend(sorted(DEFAULT_MODEL_DIR.glob("pose_landmarker*.task")))
        for path in candidates:
            if path.is_file():
                return path
        return None

    # ---- detection -------------------------------------------------------

    def detect(
        self,
        image,
        *,
        timestamp: Optional[float] = None,
        is_bgr: bool = True,
    ) -> PoseFrame:
        """Detect landmarks in one image.

        ``image`` is a numpy array as produced by OpenCV (BGR by default).
        ``timestamp`` is in seconds; it is required for the Tasks API in
        video mode and is carried through onto the returned frame.
        """
        if self._impl is None:
            raise DetectorUnavailable("Detector was not initialised.")

        import numpy as np

        if image is None or getattr(image, "size", 0) == 0:
            return PoseFrame.empty(timestamp=timestamp or 0.0, frame_index=self._frame_index)

        height, width = image.shape[:2]
        rgb = image[:, :, ::-1] if is_bgr else image
        rgb = np.ascontiguousarray(rgb)

        ts = timestamp if timestamp is not None else self._frame_index / 30.0
        self._frame_index += 1

        if self.backend == "solutions":
            rows = self._detect_solutions(rgb)
        else:
            rows = self._detect_tasks(rgb, ts)

        if not rows:
            return PoseFrame.empty(timestamp=ts, frame_index=self._frame_index - 1)

        return PoseFrame.from_sequence(
            rows,
            timestamp=ts,
            frame_index=self._frame_index - 1,
            image_width=width,
            image_height=height,
        )

    def _detect_solutions(self, rgb) -> Optional[List[List[float]]]:
        result = self._impl.process(rgb)
        landmarks = getattr(result, "pose_landmarks", None)
        if not landmarks:
            return None
        return [
            [lm.x, lm.y, lm.z, getattr(lm, "visibility", 1.0)]
            for lm in landmarks.landmark
        ]

    def _detect_tasks(self, rgb, timestamp: float) -> Optional[List[List[float]]]:
        import mediapipe as mp

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        if self.static_image_mode:
            result = self._impl.detect(mp_image)
        else:
            # The Tasks video API demands strictly increasing integer
            # milliseconds; a repeated or out-of-order stamp raises. Nudge
            # forward rather than dropping the frame.
            ts_ms = int(timestamp * 1000)
            if ts_ms <= self._last_timestamp_ms:
                ts_ms = self._last_timestamp_ms + 1
            self._last_timestamp_ms = ts_ms
            result = self._impl.detect_for_video(mp_image, ts_ms)

        landmark_sets = getattr(result, "pose_landmarks", None)
        if not landmark_sets:
            return None
        landmarks = landmark_sets[0]

        # The Tasks API reports `visibility` and `presence` as optional
        # attributes that are sometimes None; treat a missing value as fully
        # visible rather than silently zeroing out every rule.
        rows: List[List[float]] = []
        for lm in landmarks:
            vis = getattr(lm, "visibility", None)
            if vis is None:
                vis = getattr(lm, "presence", None)
            rows.append([lm.x, lm.y, getattr(lm, "z", 0.0), 1.0 if vis is None else vis])
        return rows

    # ---- lifecycle -------------------------------------------------------

    def reset(self) -> None:
        """Clear per-stream state before processing a different video."""
        self._frame_index = 0
        self._last_timestamp_ms = -1

    def close(self) -> None:
        if self._impl is not None and hasattr(self._impl, "close"):
            try:
                self._impl.close()
            except Exception:
                pass
        self._impl = None
        self.backend = "none"

    def __enter__(self) -> "PoseDetector":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


_detector: Optional[PoseDetector] = None


def get_detector(**kwargs) -> PoseDetector:
    """Shared detector instance.

    MediaPipe graphs are expensive to build, so the API server reuses one.
    Note that a video-mode detector holds tracking state across calls and is
    not safe to share between concurrent streams -- construct a dedicated
    :class:`PoseDetector` per stream for that.
    """
    global _detector
    if _detector is None or _detector.backend == "none":
        _detector = PoseDetector(**kwargs)
    return _detector
