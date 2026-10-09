"""Seed the demo account against a running backend over HTTP.

Unlike scripts/seed_demo_account.py (which writes to the database directly and
can backdate history), this talks to the public REST API, so it works against
a deployed backend without its database URL. Sessions are stamped server-side
at "now", so the over-time trend is compressed -- but profile, per-pose
scores, weaknesses and adaptive recommendations all populate.

    python scripts/seed_demo_via_api.py --backend https://your-backend.example
"""

from __future__ import annotations

import argparse
import random

import httpx

DEMO_EMAIL = "demo@ayudrishti.app"
DEMO_PASSWORD = "Explore@2026"
DEMO_NAME = "Aditi Sharma"

PROFILE = dict(
    age=29,
    experience="beginner",
    goals=["flexibility", "stress_reduction"],
    focus_areas=["spine", "hips"],
    preferred_duration=20,
    practice_frequency=4,
)

# Components per pose (from the asana registry) so alignment metrics look real.
POSE_COMPONENTS = {
    "tadasana": ["legs", "torso", "shoulders", "arms"],
    "utkatasana": ["legs", "torso", "arms"],
    "bhujangasana": ["spine", "chest", "arms", "legs", "shoulders"],
    "setu_bandhasana": ["hips", "legs", "spine"],
    "balasana": ["legs", "torso", "arms"],
}
SESSION_POSES = ["tadasana", "utkatasana", "bhujangasana", "setu_bandhasana", "balasana"]
WEAK_POSE = "utkatasana"

SESSIONS = 14
HOLD_SECONDS = 30
rng = random.Random(20260821)


def _clamp(v, lo=5.0, hi=99.0):
    return max(lo, min(hi, v))


def build_assessments(progress: float):
    """One session's worth of pose assessments. `progress` in 0..1 trends up."""
    base = 63 + progress * 23
    out = []
    for slug in SESSION_POSES:
        penalty = 12 if slug == WEAK_POSE else 0
        score = _clamp(base - penalty + rng.uniform(-4, 4))
        metrics = {}
        for c in POSE_COMPONENTS[slug]:
            low = 6 if (slug == WEAK_POSE and c in ("legs", "torso")) else 0
            metrics[c] = round(_clamp(score + rng.uniform(-6, 6) - low), 1)
        corrections = [
            f"Refine your {c.replace('_', ' ')} alignment." for c, v in metrics.items() if v < 72
        ][:2]
        out.append(
            {
                "asana_id": slug,
                "score": round(score, 1),
                "confidence": round(rng.uniform(0.86, 0.98), 2),
                "hold_seconds": HOLD_SECONDS,
                "alignment_metrics": metrics,
                "corrections": corrections,
                "deviation_count": len(corrections),
                "rule_details": [],
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", required=True, help="Backend base URL")
    args = parser.parse_args()
    base = args.backend.rstrip("/")

    with httpx.Client(base_url=base, timeout=30.0) as client:
        # Register (or log in if the demo user already exists).
        reg = client.post(
            "/auth/register",
            json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD, "name": DEMO_NAME, **PROFILE},
        )
        if reg.status_code == 201:
            token = reg.json()["access_token"]
            print("Registered demo user.")
        elif reg.status_code == 409:
            login = client.post(
                "/auth/login", data={"username": DEMO_EMAIL, "password": DEMO_PASSWORD}
            )
            login.raise_for_status()
            token = login.json()["access_token"]
            print("Demo user already existed; logged in (adding more sessions).")
        else:
            raise SystemExit(f"Register failed: {reg.status_code} {reg.text}")

        auth = {"Authorization": f"Bearer {token}"}

        for i in range(SESSIONS):
            created = client.post(
                "/sessions", headers=auth, json={"planned_asanas": SESSION_POSES, "notes": ""}
            )
            created.raise_for_status()
            sid = created.json()["id"]

            assessments = build_assessments(i / max(1, SESSIONS - 1))
            done = client.post(
                f"/sessions/{sid}/complete",
                headers=auth,
                json={
                    "assessments": assessments,
                    "duration_seconds": PROFILE["preferred_duration"] * 60,
                    "notes": "",
                },
            )
            done.raise_for_status()
            print(f"  session {i + 1}/{SESSIONS}: overall {done.json().get('overall_score')}")

        print("\nDone. Log in as:")
        print(f"  Email     {DEMO_EMAIL}")
        print(f"  Password  {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
