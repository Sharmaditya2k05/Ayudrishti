#!/usr/bin/env python
"""Train the optional scikit-learn pose classifier.

AyuDrishti recognises poses without this. The rule-based recogniser works
from day one and can explain every decision; a trained model is an optional
accuracy layer for awkward camera angles, combined with the rules by
:class:`HybridRecognizer` rather than replacing them.

Two stages:

    # 1. Extract landmarks from a labelled image/video tree
    python scripts/train_classifier.py extract \
        --data data/datasets/yoga_poses \
        --out  data/datasets/landmarks.csv

    # 2. Fit and evaluate a classifier
    python scripts/train_classifier.py train \
        --features data/datasets/landmarks.csv

See data/datasets/README.md for the expected directory layout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.pose_recognition.classifier import MLPoseClassifier  # noqa: E402
from ai.pose_recognition.dataset import extract_dataset, load_features  # noqa: E402

DEFAULT_FEATURES = ROOT / "data" / "datasets" / "landmarks.csv"
DEFAULT_MODEL = ROOT / "data" / "models" / "pose_classifier.joblib"


def cmd_extract(args: argparse.Namespace) -> int:
    print(f"Extracting landmarks from {args.data}")
    print("This runs MediaPipe over every image and sampled video frame; "
          "expect it to take a while on a large dataset.\n")

    report = extract_dataset(
        Path(args.data),
        Path(args.out),
        video_stride=args.stride,
        max_frames_per_video=args.max_frames,
        min_visibility=args.min_visibility,
    )

    print("\n" + report.summary())
    print(f"\nFeatures written to {args.out}")

    if report.detected == 0:
        print("\nNo poses were detected. Check that the images show a full body "
              "and that directory names match ids in data/pose_rules/.")
        return 1
    if report.detection_rate < 0.5:
        print("\nWarning: a body was detected in fewer than half the frames. "
              "Cropped or partial-body images are the usual cause.")
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    features_path = Path(args.features)
    print(f"Loading features from {features_path}")
    features, labels, _ = load_features(features_path)

    if not features:
        print("No samples found. Run the 'extract' step first.")
        return 1

    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1

    print(f"{len(features)} samples across {len(counts)} asanas")
    thin = {k: v for k, v in counts.items() if v < 20}
    if thin:
        # Small classes produce a model that looks accurate overall while
        # being useless for exactly the poses it was meant to help with.
        print(f"\nWarning: these asanas have very few samples: {thin}")
        print("Expect poor accuracy on them. 50+ samples per asana is a "
              "reasonable minimum.")

    print("\nTraining...")
    classifier, report = MLPoseClassifier.train(
        features, labels, test_size=args.test_size, random_state=args.seed
    )

    print("\n" + report.summary())

    print("\nConfusion matrix (rows = actual, columns = predicted):")
    width = max(len(c) for c in report.classes)
    print(" " * (width + 2) + " ".join(f"{c[:6]:>6s}" for c in report.classes))
    for name, row in zip(report.classes, report.confusion):
        print(f"  {name:<{width}s} " + " ".join(f"{v:6d}" for v in row))

    if args.no_save:
        print("\n--no-save given; model not written.")
        return 0

    path = classifier.save(Path(args.model))
    print(f"\nModel saved to {path}")

    metrics_path = Path(args.model).with_suffix(".metrics.json")
    metrics_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    print(f"Metrics saved to {metrics_path}")

    if report.accuracy < 0.8:
        print("\nAccuracy is below 0.80. The rule-based recogniser will usually "
              "outperform this; consider gathering more varied data before "
              "enabling the model.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser("extract", help="run pose detection over a labelled dataset")
    extract.add_argument("--data", required=True, help="root directory, one folder per asana")
    extract.add_argument("--out", default=str(DEFAULT_FEATURES))
    extract.add_argument("--stride", type=int, default=10, help="sample every Nth video frame")
    extract.add_argument("--max-frames", type=int, default=40, help="frames kept per video")
    extract.add_argument("--min-visibility", type=float, default=0.5)
    extract.set_defaults(func=cmd_extract)

    train = sub.add_parser("train", help="fit a classifier on extracted features")
    train.add_argument("--features", default=str(DEFAULT_FEATURES))
    train.add_argument("--model", default=str(DEFAULT_MODEL))
    train.add_argument("--test-size", type=float, default=0.2)
    train.add_argument("--seed", type=int, default=42)
    train.add_argument("--no-save", action="store_true")
    train.set_defaults(func=cmd_train)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
