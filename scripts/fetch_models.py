#!/usr/bin/env python
"""Download the MediaPipe Pose model bundle.

MediaPipe 1.x removed the legacy `mp.solutions.pose` API, which bundled its
own weights. The current Tasks API needs a `.task` file on disk, so this
fetches it into ``data/models/``.

Only needed for server-side or desktop detection (``scripts/live_session.py``).
The mobile client downloads its own model at runtime, and a backend that only
receives landmarks from the app never needs this at all.

Usage:
    python scripts/fetch_models.py              # lite model, ~5 MB
    python scripts/fetch_models.py --variant full
    python scripts/fetch_models.py --list
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "data" / "models"

BASE = "https://storage.googleapis.com/mediapipe-models/pose_landmarker"

VARIANTS = {
    "lite": {
        "url": f"{BASE}/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
        "filename": "pose_landmarker_lite.task",
        "approx_mb": 5.5,
        "note": "Fastest. Recommended for real-time use and for development.",
    },
    "full": {
        "url": f"{BASE}/pose_landmarker_full/float16/1/pose_landmarker_full.task",
        "filename": "pose_landmarker_full.task",
        "approx_mb": 9.0,
        "note": "Better accuracy, noticeably slower on CPU.",
    },
    "heavy": {
        "url": f"{BASE}/pose_landmarker_heavy/float16/1/pose_landmarker_heavy.task",
        "filename": "pose_landmarker_heavy.task",
        "approx_mb": 29.2,
        "note": "Most accurate. Offline analysis rather than live sessions.",
    },
}


def human(size: int) -> str:
    return f"{size / (1024 * 1024):.1f} MB"


def download(variant: str, *, force: bool = False) -> Path:
    spec = VARIANTS[variant]
    target = MODEL_DIR / spec["filename"]

    if target.is_file() and not force:
        print(f"Already present: {target} ({human(target.stat().st_size)})")
        return target

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {variant} model (~{spec['approx_mb']} MB)")
    print(f"  from {spec['url']}")
    print(f"  to   {target}")

    # Write to a temporary path and rename on success, so an interrupted
    # download cannot leave a truncated file that later fails to load.
    temp = target.with_suffix(target.suffix + ".part")
    try:
        with urllib.request.urlopen(spec["url"], timeout=120) as response:
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            digest = hashlib.sha256()
            with open(temp, "wb") as fh:
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    fh.write(chunk)
                    digest.update(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        print(f"\r  {pct:5.1f}%  {human(downloaded)}", end="", flush=True)
        print()
    except urllib.error.URLError as exc:
        temp.unlink(missing_ok=True)
        raise SystemExit(
            f"Download failed: {exc}\n"
            f"Check your network connection, or download the file manually from:\n"
            f"  {spec['url']}\n"
            f"and save it to {target}"
        ) from exc

    temp.replace(target)
    print(f"Saved {target} ({human(target.stat().st_size)})")
    print(f"  sha256: {digest.hexdigest()[:32]}...")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variant", choices=sorted(VARIANTS), default="lite")
    parser.add_argument("--force", action="store_true", help="re-download even if present")
    parser.add_argument("--list", action="store_true", help="show available models and exit")
    args = parser.parse_args()

    if args.list:
        print("Available MediaPipe Pose models:\n")
        for name, spec in VARIANTS.items():
            path = MODEL_DIR / spec["filename"]
            status = "installed" if path.is_file() else "not installed"
            print(f"  {name:6s} ~{spec['approx_mb']:>5.1f} MB  [{status}]")
            print(f"         {spec['note']}")
        return 0

    download(args.variant, force=args.force)

    print("\nVerifying the detector can start...")
    sys.path.insert(0, str(ROOT))
    try:
        from ai.pose_detection import PoseDetector

        with PoseDetector(static_image_mode=True) as detector:
            print(f"  Detector ready (backend: {detector.backend})")
    except Exception as exc:
        print(f"  Detector could not start: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
