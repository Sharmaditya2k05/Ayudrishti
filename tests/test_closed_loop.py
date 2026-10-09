"""End-to-end test of the AyuDrishti closed loop through the REST API.

Exercises the full cycle the spec defines as the definition of success:

    Onboard -> Recommend -> Start session -> Perform asana -> Live assessment
    -> Correction -> Complete session -> Progress -> Adapted recommendation

Runs against a throwaway SQLite database so it needs no PostgreSQL server.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Point the app at a temporary database before importing anything that reads
# settings, since the engine is created at import time.
_TMP_DB = Path(tempfile.gettempdir()) / "ayudrishti_test.db"
if _TMP_DB.exists():
    _TMP_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from tests.fixtures import (  # noqa: E402
    build_frame,
    perturb,
    utkatasana_good,
    warrior_ii_good,
)


def landmark_payload(coords) -> list:
    """Convert a fixture skeleton into the 33-landmark wire format."""
    frame = build_frame(coords)
    from ai.pose_detection.landmarks import LANDMARK_NAMES

    out = []
    for name in LANDMARK_NAMES:
        lm = frame.landmarks[name]
        out.append(
            {"x": lm.x, "y": lm.y, "z": lm.z, "visibility": lm.visibility}
        )
    return out


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "asha@example.com",
            "password": "practice-daily-2026",
            "name": "Asha",
            "age": 31,
            "experience": "intermediate",
            "goals": ["strength", "flexibility"],
            "focus_areas": ["legs", "core"],
            "preferred_duration": 20,
            "practice_frequency": 4,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user"]["onboarded"] is True
    return {"Authorization": f"Bearer {body['access_token']}"}


# ---------------------------------------------------------------------------
# 1. SUGGEST
# ---------------------------------------------------------------------------


def test_recommendation_is_personalised_and_explained(client, auth):
    response = client.get("/recommendations", headers=auth)
    assert response.status_code == 200, response.text
    plan = response.json()

    assert plan["items"], "expected a non-empty session plan"
    assert plan["total_minutes"] > 0

    # Every recommendation must carry a human-readable justification and the
    # signed factors behind it -- the engine is required not to be a black box.
    for item in plan["items"]:
        assert item["reason"], f"{item['asana_id']} has no reason"
        assert item["factors"], f"{item['asana_id']} has no scoring factors"

    # A session must warm up before it works, and rest at the end.
    stages = [i["sequence_stage"] for i in plan["items"]]
    assert stages[0] == "warmup"
    assert stages[-1] == "cooldown"

    # An intermediate practitioner must not be handed advanced poses.
    assert all(i["difficulty"] in ("beginner", "intermediate") for i in plan["items"])


# ---------------------------------------------------------------------------
# 2. DETECT + ASSESS + CORRECT
# ---------------------------------------------------------------------------


def test_assessment_scores_a_good_pose_highly(client, auth):
    response = client.post(
        "/assessment",
        headers=auth,
        json={
            "landmarks": landmark_payload(warrior_ii_good()),
            "asana_id": "virabhadrasana_ii",
            "timestamp": 0.0,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["detected"] is True
    assert body["overall"] >= 95
    assert body["reliable"] is True
    assert body["lead_side"] == "left"
    assert body["feedback"]["indicators"], "expected per-component indicators"


def test_assessment_explains_a_specific_fault(client, auth):
    """A knee drifting off the ankle must produce that exact correction."""
    faulty = perturb(warrior_ii_good(), left_knee=(0.13, -0.02))
    response = client.post(
        "/assessment",
        headers=auth,
        json={
            "landmarks": landmark_payload(faulty),
            "asana_id": "virabhadrasana_ii",
            "timestamp": 10.0,
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["overall"] < 95
    corrections = [
        m for m in body["feedback"]["messages"] if m["kind"] == "correction"
    ]
    assert corrections, "a faulty pose must produce corrective feedback"

    knee = next((m for m in corrections if "knee" in m["text"].lower()), None)
    assert knee is not None, f"expected knee feedback, got {[m['text'] for m in corrections]}"

    # Feedback must be actionable, not a bare verdict.
    assert "incorrect" not in knee["text"].lower()
    assert knee["measured_value"] is not None, "feedback must cite its measurement"
    assert knee["rule_id"], "feedback must be traceable to a rule"

    # The offending joints are flagged so the UI can highlight them.
    assert "left_knee" in body["feedback"]["highlight_landmarks"]


def test_assessment_recognises_the_pose_when_not_told(client, auth):
    response = client.post(
        "/assessment",
        headers=auth,
        json={"landmarks": landmark_payload(utkatasana_good()), "timestamp": 20.0},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recognition"]["asana_id"] == "utkatasana"
    assert body["asana_id"] == "utkatasana"


def test_partial_body_lowers_confidence_rather_than_inventing_a_score(client, auth):
    """Landmarks the camera cannot see must not be silently scored."""
    payload = landmark_payload(warrior_ii_good())
    from ai.pose_detection.landmarks import LANDMARK_INDEX

    for name in ("left_knee", "left_ankle", "right_knee", "right_ankle"):
        payload[LANDMARK_INDEX[name]]["visibility"] = 0.1

    response = client.post(
        "/assessment",
        headers=auth,
        json={
            "landmarks": payload,
            "asana_id": "virabhadrasana_ii",
            "timestamp": 30.0,
        },
    )
    body = response.json()
    assert body["confidence"] < 1.0
    assert body["missing_landmarks"], "unseen landmarks must be reported"
    assert any("camera" in n.lower() for n in body["notes"])


# ---------------------------------------------------------------------------
# 3. TRACK
# ---------------------------------------------------------------------------


def test_session_records_and_summarises(client, auth):
    created = client.post(
        "/sessions",
        headers=auth,
        json={"planned_asanas": ["virabhadrasana_ii", "utkatasana"]},
    )
    assert created.status_code == 201, created.text
    session_id = created.json()["id"]

    completed = client.post(
        f"/sessions/{session_id}/complete",
        headers=auth,
        json={
            "duration_seconds": 1080,
            "assessments": [
                {
                    "asana_id": "virabhadrasana_ii",
                    "score": 64.0,
                    "hold_seconds": 30,
                    "alignment_metrics": {
                        "knee": 48.0, "torso": 88.0, "arms": 84.0,
                        "legs": 80.0, "hips": 86.0, "shoulders": 90.0,
                    },
                    "corrections": ["Your front knee has drifted away from your ankle."],
                    "deviation_count": 3,
                },
                {
                    "asana_id": "utkatasana",
                    "score": 86.0,
                    "hold_seconds": 25,
                    "alignment_metrics": {"legs": 84.0, "torso": 88.0, "arms": 86.0},
                    "corrections": [],
                    "deviation_count": 0,
                },
            ],
        },
    )
    assert completed.status_code == 200, completed.text
    summary = completed.json()

    assert summary["status"] == "completed"
    assert summary["asana_count"] == 2
    assert summary["overall_score"] == pytest.approx(75.0, abs=0.1)
    assert summary["best_pose"] == "utkatasana"
    assert summary["weakest_pose"] == "virabhadrasana_ii"
    assert "knee" in summary["improvement_areas"]
    assert summary["correction_count"] == 1


def test_progress_reflects_recorded_sessions(client, auth):
    response = client.get("/progress", headers=auth)
    assert response.status_code == 200
    progress = response.json()

    assert progress["total_sessions"] >= 1
    assert progress["total_assessments"] >= 2
    assert progress["score_history"], "expected a session score series for charting"

    warrior = next(
        p for p in progress["per_asana"] if p["asana_id"] == "virabhadrasana_ii"
    )
    assert warrior["latest_score"] == pytest.approx(64.0, abs=0.1)
    assert "knee" in warrior["weak_components"]


# ---------------------------------------------------------------------------
# 4. ADAPT -- the loop closing
# ---------------------------------------------------------------------------


def test_recommendations_adapt_to_a_detected_weakness(client, auth):
    """Repeated poor knee alignment must change what is recommended next."""
    # Two more sessions with the same weak knee, so it is a pattern rather
    # than one bad day.
    for score in (66.0, 68.0):
        session_id = client.post(
            "/sessions", headers=auth, json={"planned_asanas": ["virabhadrasana_ii"]}
        ).json()["id"]
        client.post(
            f"/sessions/{session_id}/complete",
            headers=auth,
            json={
                "duration_seconds": 900,
                "assessments": [
                    {
                        "asana_id": "virabhadrasana_ii",
                        "score": score,
                        "hold_seconds": 30,
                        "alignment_metrics": {
                            "knee": 50.0, "torso": 89.0, "arms": 85.0,
                            "legs": 82.0, "hips": 87.0, "shoulders": 90.0,
                        },
                        "corrections": ["Your front knee has drifted away from your ankle."],
                        "deviation_count": 3,
                    }
                ],
            },
        )

    progress = client.get("/progress", headers=auth).json()
    weaknesses = [w["component"] for w in progress["weaknesses"]]
    assert "knee" in weaknesses, f"knee should be flagged as a weakness, got {weaknesses}"

    plan = client.get("/recommendations", headers=auth).json()

    # The plan must now be explicitly organised around fixing that weakness.
    assert "knee" in plan["focus"].lower(), f"focus was {plan['focus']!r}"
    assert any("knee" in note.lower() for note in plan["notes"])

    targeted = [i for i in plan["items"] if i["targeted_weakness"] == "knee"]
    assert targeted, "expected at least one pose chosen to target the knee weakness"

    # And the struggling pose must be revisited rather than dropped.
    warrior = next(
        (i for i in plan["items"] if i["asana_id"] == "virabhadrasana_ii"), None
    )
    assert warrior is not None, "a struggling pose should be repeated, not abandoned"
    assert any(f["name"] == "needs_work" for f in warrior["factors"])


def test_generated_plan_is_persisted_with_its_reasoning(client, auth):
    generated = client.post(
        "/recommendations/generate", headers=auth, json={"persist": True}
    )
    assert generated.status_code == 200

    latest = client.get("/recommendations/latest", headers=auth)
    assert latest.status_code == 200
    rows = latest.json()
    assert rows, "persisted plan should be retrievable"
    assert all(r["reason"] for r in rows)
    assert any(r["factors"] for r in rows)


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


def test_protected_endpoints_reject_anonymous_access(client):
    for method, path in [
        ("get", "/users/me"),
        ("get", "/recommendations"),
        ("get", "/progress"),
        ("get", "/sessions"),
    ]:
        response = getattr(client, method)(path)
        assert response.status_code == 401, f"{path} should require auth"


def test_users_cannot_read_another_users_session(client, auth):
    other = client.post(
        "/auth/register",
        json={
            "email": "ravi@example.com",
            "password": "another-password-99",
            "name": "Ravi",
            "experience": "beginner",
            "goals": ["relaxation"],
        },
    ).json()
    other_auth = {"Authorization": f"Bearer {other['access_token']}"}

    mine = client.get("/sessions", headers=auth).json()
    assert mine, "expected the first user to have sessions"

    response = client.get(f"/sessions/{mine[0]['id']}", headers=other_auth)
    assert response.status_code == 404
