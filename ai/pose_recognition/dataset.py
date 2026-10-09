"""Building landmark datasets from labelled yoga images and videos.

AyuDrishti's rule-based recogniser needs no training data. This module
exists for the optional learned classifier, and for evaluating how well the
alignment rules generalise to real photographs rather than the synthetic
skeletons used in tests.

Expected input layout -- one directory per asana, named with the asana id::

    data/datasets/yoga_poses/
        virabhadrasana_ii/  img001.jpg  img002.jpg  clip.mp4 ...
        trikonasana/        ...
        tadasana/           ...

Directory names must match ids in ``data/pose_rules/``; anything else is
reported and skipped rather than silently mislabelled.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from ..pose_assessment.asana import AsanaRegistry, get_registry
from ..pose_detection.landmarks import LANDMARK_NAMES, PoseFrame
from .features import extract_features, feature_names

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


@dataclass
class ExtractionReport:
    processed: int = 0
    detected: int = 0
    skipped_files: int = 0
    unknown_labels: List[str] = field(default_factory=list)
    per_label: Dict[str, int] = field(default_factory=dict)
    failures: List[Tuple[str, str]] = field(default_factory=list)

    @property
    def detection_rate(self) -> float:
        return self.detected / self.processed if self.processed else 0.0

    def summary(self) -> str:
        lines = [
            f"Processed {self.processed} frames, detected a body in {self.detected} "
            f"({self.detection_rate:.1%})",
        ]
        if self.per_label:
            lines.append("\nSamples per asana:")
            for label in sorted(self.per_label, key=lambda k: -self.per_label[k]):
                lines.append(f"  {label:26s} {self.per_label[label]}")
        if self.unknown_labels:
            lines.append(
                f"\nSkipped {len(self.unknown_labels)} directories with no matching "
                f"asana definition: {', '.join(sorted(set(self.unknown_labels)))}"
            )
        if self.failures:
            lines.append(f"\n{len(self.failures)} files could not be read. First few:")
            for path, reason in self.failures[:5]:
                lines.append(f"  {path}: {reason}")
        return "\n".join(lines)


def iter_labelled_files(
    root: Path, registry: Optional[AsanaRegistry] = None
) -> Iterator[Tuple[Path, str]]:
    """Yield ``(file, asana_id)`` for every media file under a labelled tree."""
    registry = registry or get_registry()
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"dataset directory not found: {root}")

    for label_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        label = label_dir.name
        for path in sorted(label_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() in IMAGE_SUFFIXES | VIDEO_SUFFIXES:
                yield path, label


def extract_dataset(
    root: Path,
    output_csv: Path,
    *,
    registry: Optional[AsanaRegistry] = None,
    video_stride: int = 10,
    max_frames_per_video: int = 40,
    min_visibility: float = 0.5,
    progress: bool = True,
) -> ExtractionReport:
    """Run pose detection over a labelled tree and write a feature CSV.

    Videos are sampled rather than exhausted: consecutive frames of a held
    pose are near-duplicates, and feeding thousands of them to a classifier
    inflates the apparent dataset size without adding information.
    """
    from ..pose_detection.detector import PoseDetector

    registry = registry or get_registry()
    report = ExtractionReport()
    known = set(registry.ids())

    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    columns = ["label", "source", "frame"] + feature_names()

    with PoseDetector(static_image_mode=True) as image_detector, open(
        output_csv, "w", newline="", encoding="utf-8"
    ) as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)

        for path, label in iter_labelled_files(root, registry):
            if label not in known:
                report.unknown_labels.append(label)
                report.skipped_files += 1
                continue

            try:
                if path.suffix.lower() in IMAGE_SUFFIXES:
                    frames = _frames_from_image(path, image_detector)
                else:
                    frames = _frames_from_video(
                        path, video_stride, max_frames_per_video, min_visibility
                    )
            except Exception as exc:  # noqa: BLE001 - report and continue
                report.failures.append((str(path), str(exc)))
                report.skipped_files += 1
                continue

            for index, frame in frames:
                report.processed += 1
                if not frame.detected:
                    continue
                if frame.mean_visibility() < min_visibility:
                    continue
                report.detected += 1
                report.per_label[label] = report.per_label.get(label, 0) + 1
                writer.writerow([label, path.name, index] + extract_features(frame))

            if progress and report.processed and report.processed % 200 == 0:
                print(f"  {report.processed} frames processed...", flush=True)

    return report


def _frames_from_image(path: Path, detector) -> List[Tuple[int, PoseFrame]]:
    import cv2

    image = cv2.imread(str(path))
    if image is None:
        raise ValueError("could not decode image")
    return [(0, detector.detect(image, timestamp=0.0))]


def _frames_from_video(
    path: Path, stride: int, max_frames: int, min_visibility: float
) -> List[Tuple[int, PoseFrame]]:
    import cv2

    from ..pose_detection.detector import PoseDetector

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError("could not open video")

    out: List[Tuple[int, PoseFrame]] = []
    # A dedicated detector per clip: video mode carries tracking state, which
    # must not leak between unrelated recordings.
    with PoseDetector(static_image_mode=False) as detector:
        index = 0
        kept = 0
        try:
            while kept < max_frames:
                ok, image = capture.read()
                if not ok:
                    break
                if index % max(stride, 1) == 0:
                    ts = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                    out.append((index, detector.detect(image, timestamp=ts)))
                    kept += 1
                index += 1
        finally:
            capture.release()
    return out


def load_features(csv_path: Path) -> Tuple[List[List[float]], List[str], List[str]]:
    """Read a feature CSV back as ``(features, labels, sources)``."""
    csv_path = Path(csv_path)
    if not csv_path.is_file():
        raise FileNotFoundError(f"feature file not found: {csv_path}")

    expected = feature_names()
    features: List[List[float]] = []
    labels: List[str] = []
    sources: List[str] = []

    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if header is None:
            raise ValueError(f"{csv_path} is empty")

        columns = header[3:]
        if columns != expected:
            raise ValueError(
                f"{csv_path} was written with a different feature layout "
                f"({len(columns)} columns vs {len(expected)}). Re-extract it."
            )

        for row in reader:
            if len(row) != len(header):
                continue
            labels.append(row[0])
            sources.append(row[1])
            features.append([float(v) for v in row[3:]])

    return features, labels, sources


def frame_from_row(row: Sequence[float]) -> PoseFrame:
    """Rebuild a PoseFrame from a raw landmark row (33 x 4 values)."""
    values = list(row)
    if len(values) < len(LANDMARK_NAMES) * 4:
        raise ValueError("expected 33 landmarks of [x, y, z, visibility]")
    points = [values[i * 4 : i * 4 + 4] for i in range(len(LANDMARK_NAMES))]
    return PoseFrame.from_sequence(points)
