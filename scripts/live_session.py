#!/usr/bin/env python
"""Run the full AyuDrishti pipeline on a laptop webcam.

Camera -> MediaPipe Pose -> landmarks -> joint angles -> recognition ->
pose-specific assessment -> scoring -> corrective feedback, drawn live over
the video with a skeleton overlay.

Needs no backend, no database and no mobile app -- useful for developing
alignment rules, since a rule change is visible on the next frame.

Usage:
    python scripts/live_session.py                     # auto-recognise the pose
    python scripts/live_session.py --asana trikonasana # score one pose only
    python scripts/live_session.py --source clip.mp4   # run against a video
    python scripts/live_session.py --list

Keys:  q quit   n next asana   r reset feedback   space pause
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.feedback import FeedbackGenerator  # noqa: E402
from ai.pose_assessment import PoseAssessmentEngine, get_registry  # noqa: E402
from ai.pose_detection import DetectorUnavailable, PoseDetector  # noqa: E402
from ai.pose_detection.video import (  # noqa: E402
    CameraUnavailable,
    VideoSource,
    draw_session_overlay,
    draw_skeleton,
)
from ai.pose_recognition import TemporalRecognizer  # noqa: E402
from ai.safety import SafetyMonitor  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--asana", help="score against this asana instead of auto-recognising")
    parser.add_argument("--source", default="0", help="camera index or video file path")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--no-mirror", action="store_true")
    parser.add_argument("--list", action="store_true", help="list available asanas and exit")
    args = parser.parse_args()

    registry = get_registry()

    if args.list:
        print(f"{len(registry)} asanas available:\n")
        for config in sorted(registry.all(), key=lambda c: (c.difficulty_rank, c.id)):
            print(f"  {config.id:24s} {config.english_name:26s} "
                  f"{config.difficulty:12s} view: {config.preferred_view}")
        return 0

    if args.asana and args.asana not in registry:
        print(f"Unknown asana '{args.asana}'. Use --list to see the options.")
        return 1

    try:
        import cv2
    except ImportError:
        print("OpenCV is required. Install it with:  pip install opencv-python")
        return 1

    try:
        detector = PoseDetector(static_image_mode=False)
    except DetectorUnavailable as exc:
        print(f"Pose detector unavailable:\n{exc}")
        return 1

    print(f"Pose detector ready (backend: {detector.backend})")

    engine = PoseAssessmentEngine(registry)
    recognizer = TemporalRecognizer(window=8)
    feedback = FeedbackGenerator(max_messages=2, cooldown=4.0)
    safety = SafetyMonitor()

    asana_ids = registry.ids()
    fixed_index = asana_ids.index(args.asana) if args.asana else None

    source = args.source if not args.source.isdigit() else int(args.source)
    video = VideoSource(
        source=source, width=args.width, height=args.height, mirror=not args.no_mirror
    )

    try:
        video.open()
    except CameraUnavailable as exc:
        print(exc)
        return 1

    if args.asana:
        config = registry.require(args.asana)
        print(f"\nScoring against: {config.english_name}")
        print(f"  {config.camera_hint}")
        for cue in config.cues:
            print(f"  - {cue}")
    else:
        print("\nAuto-recognising poses. Move into an asana and hold it.")

    print("\nKeys: q quit | n next asana | r reset | space pause\n")

    paused = False
    frame_count = 0
    fps_clock = time.monotonic()
    fps = 0.0

    try:
        for image, timestamp in video.frames():
            if not paused:
                frame = detector.detect(image, timestamp=timestamp)
                frame_count += 1

                if frame_count % 15 == 0:
                    now = time.monotonic()
                    fps = 15.0 / max(now - fps_clock, 1e-6)
                    fps_clock = now

                if fixed_index is not None:
                    target = asana_ids[fixed_index]
                    confidence = 1.0
                else:
                    result = recognizer.update(frame)
                    target = result.asana_id
                    confidence = result.confidence

                if target is None:
                    draw_skeleton(image, frame)
                    draw_session_overlay(
                        image,
                        asana_name="Detecting pose...",
                        messages=["Move into a yoga pose and hold it steady."],
                    )
                else:
                    assessment = engine.assess_smoothed(frame, target)
                    bundle = feedback.generate(assessment, timestamp=timestamp)
                    alerts = safety.check(frame, assessment, timestamp=timestamp)

                    messages = [m.text for m in bundle.messages]
                    for alert in alerts:
                        messages.insert(0, f"! {alert.message}")

                    draw_skeleton(
                        image, frame, highlight=bundle.highlight_landmarks
                    )
                    draw_session_overlay(
                        image,
                        asana_name=assessment.asana_name,
                        score=assessment.overall,
                        indicators=bundle.indicators,
                        messages=messages[:3],
                        confidence=confidence,
                    )

                cv2.putText(
                    image,
                    f"{fps:4.1f} fps  [{detector.backend}]",
                    (image.shape[1] - 200, image.shape[0] - 16),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (150, 150, 150),
                    1,
                    cv2.LINE_AA,
                )

            cv2.imshow("AyuDrishti - live session", image)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord(" "):
                paused = not paused
            if key == ord("r"):
                feedback.reset()
                safety.reset()
                recognizer.reset()
                engine.reset_smoothing()
                print("Feedback and safety state reset.")
            if key == ord("n") and fixed_index is not None:
                fixed_index = (fixed_index + 1) % len(asana_ids)
                config = registry.require(asana_ids[fixed_index])
                feedback.reset()
                engine.reset_smoothing()
                print(f"\nNow scoring: {config.english_name} ({config.preferred_view} view)")
    except KeyboardInterrupt:
        pass
    finally:
        video.release()
        detector.close()
        cv2.destroyAllWindows()

    print("\nSession ended.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
