#!/usr/bin/env python
"""Walk the complete AyuDrishti closed loop in the terminal.

Suggest -> Detect -> Assess -> Correct -> Track -> Adapt -> Suggest again,
using synthetic skeletons instead of a camera so the whole cycle can be
demonstrated on any machine with no webcam, no database and no mobile app.

The skeletons are clearly labelled sample data. Every score, correction and
recommendation shown is computed by the real engines from those landmarks --
nothing is hard-coded.

Usage:
    python scripts/demo_loop.py
    python scripts/demo_loop.py --sessions 6
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.feedback import FeedbackGenerator  # noqa: E402
from ai.pose_assessment import PoseAssessmentEngine  # noqa: E402
from ai.pose_recognition import RuleBasedRecognizer  # noqa: E402
from ai.recommendation import (  # noqa: E402
    PerformanceAnalyzer,
    PoseRecord,
    PracticeHistory,
    RecommendationEngine,
    UserProfile,
)
from tests.fixtures import build_frame, perturb, warrior_ii_good  # noqa: E402

BAR = "=" * 74


def fmt_range(low: float, high: float) -> str:
    """Format a target range without flattening sub-unit bounds to zero.

    Angle targets run to three digits, but torso-relative ones live between
    0 and 1, where "%.0f" would render 0.0-0.3 as a meaningless "0-0".
    """
    precision = 0 if max(abs(low), abs(high)) >= 10 else 2
    return f"{low:.{precision}f}-{high:.{precision}f}"


def header(step: str, title: str) -> None:
    print(f"\n{BAR}\n  {step}  {title}\n{BAR}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sessions", type=int, default=4, help="simulated past sessions")
    args = parser.parse_args()

    print(BAR)
    print("  AyuDrishti - closed-loop demonstration")
    print("  Landmarks below are SAMPLE DATA (synthetic skeletons).")
    print("  All scores, corrections and recommendations are computed live.")
    print(BAR)

    profile = UserProfile(
        name="Asha",
        age=31,
        experience="intermediate",
        goals=["strength", "flexibility"],
        focus_areas=["legs", "core"],
        preferred_duration=20,
        practice_frequency=4,
    )

    rec_engine = RecommendationEngine()
    assess_engine = PoseAssessmentEngine()
    recognizer = RuleBasedRecognizer()
    analyzer = PerformanceAnalyzer()

    # ---- 1. SUGGEST -------------------------------------------------------
    header("1. SUGGEST", "Goal-based recommendation, no history yet")
    plan = rec_engine.build_session(profile)
    print(f"Focus: {plan.focus}   |   {plan.total_minutes:.0f} min   |   {plan.rounds} round(s)")
    seen = set()
    for item in plan.items:
        if item.asana_id in seen:
            continue
        seen.add(item.asana_id)
        print(f"  - {item.asana_name:24s} {item.duration_seconds:3d}s"
              f"{' x2 sides' if item.sides > 1 else '         '}  score {item.score:5.1f}")
        print(f"      why: {item.reason}")

    # ---- 2. DETECT --------------------------------------------------------
    header("2. DETECT", "Body landmarks -> which asana is this?")
    faulty = perturb(warrior_ii_good(), left_knee=(0.13, -0.02), right_wrist=(0, 0.16))
    frame = build_frame(faulty)
    recognition = recognizer.recognize(frame, expected=plan.asana_ids)
    print(f"Recognised: {recognition.asana_name}  (confidence {recognition.confidence:.0%},"
          f" leading with the {recognition.lead_side} leg)")
    print("Next-closest candidates:")
    for cand in recognition.candidates[1:4]:
        print(f"  - {cand.asana_name:24s} match {cand.match:.2f}")

    # ---- 3. ASSESS --------------------------------------------------------
    header("3. ASSESS", "Pose-specific alignment rules and joint angles")
    assessment = assess_engine.assess(frame, recognition.asana_id)
    print(f"{assessment.asana_name}: {assessment.overall:.0f}%  ({assessment.score.grade})\n")
    for comp in assessment.score.components:
        bar = "#" * int(comp.score / 5)
        print(f"  {comp.label:24s} {comp.score:5.1f}%  {bar}")

    print("\nMeasured values behind the score:")
    for rule in assessment.score.rule_results[:6]:
        if rule.value is None:
            continue
        flag = "  " if rule.status == "ok" else "->"
        print(f"  {flag} {rule.rule_id:26s} {rule.value:7.1f} {rule.unit:8s}"
              f" target {fmt_range(rule.target_min, rule.target_max)}")

    # ---- 4. CORRECT -------------------------------------------------------
    header("4. CORRECT", "Real-time, explainable feedback")
    feedback = FeedbackGenerator(max_messages=2)
    bundle = feedback.generate(assessment, timestamp=0.0)
    print(f"{bundle.headline}\n")
    for message in bundle.messages:
        print(f"  [{message.kind}] {message.text}")
        if message.measured_value is not None:
            print(f"       because {message.rule_id} measured {message.measured_value:.1f}"
                  f" {message.unit} (target {fmt_range(message.target_min, message.target_max)})")
    print(f"\n  Highlighted joints: {', '.join(bundle.highlight_landmarks)}")

    print("\n  -- practitioner adjusts, next frame --")
    corrected = assess_engine.assess(build_frame(warrior_ii_good()), recognition.asana_id)
    for message in feedback.generate(corrected, timestamp=2.0).messages:
        print(f"  [{message.kind}] {message.text}")
    print(f"  Score moved {assessment.overall:.0f}% -> {corrected.overall:.0f}%")

    # ---- 5. TRACK ---------------------------------------------------------
    header("5. TRACK", f"{args.sessions} sessions recorded (sample history)")
    base = datetime(2026, 8, 1, 7, 0)
    records = []
    for i in range(args.sessions):
        when = base + timedelta(days=i * 2)
        for asana_id, score, comps in [
            ("virabhadrasana_ii", 64 + i * 2,
             {"knee": 48 + i * 3, "torso": 87, "arms": 85, "legs": 84, "hips": 86, "shoulders": 90}),
            ("trikonasana", 82 + i,
             {"legs": 86, "torso": 84, "arms": 83, "hips": 81}),
            ("utkatasana", 79 + i,
             {"legs": 76 + i, "torso": 85, "arms": 88}),
        ]:
            records.append(PoseRecord(asana_id=asana_id, score=score, performed_at=when,
                                      component_scores=comps))
    history = PracticeHistory(records)
    now = base + timedelta(days=args.sessions * 2)

    for asana_id in history.practised_asanas():
        scores = [f"{r.score:.0f}" for r in history.for_asana(asana_id)]
        trend = history.trend(asana_id)
        # The suffix is built separately: folding the conditional into the
        # print argument made a pose with no computable trend print a blank
        # line instead of its scores.
        suffix = f"   ({trend:+.1f} pts)" if trend is not None else ""
        print(f"  {asana_id:22s} {' -> '.join(scores)}{suffix}")

    # ---- 6. ADAPT ---------------------------------------------------------
    header("6. ADAPT", "Performance analysis drives the next plan")
    analysis = analyzer.analyze(history, profile, now=now)
    print(f"Overall {analysis.overall_average:.1f}%  trend {analysis.overall_trend:+.1f}"
          f"  ready to progress: {analysis.ready_to_progress}")
    print(f"{analysis.consistency.describe()}\n")
    for weakness in analysis.weaknesses:
        print(f"  weakness: {weakness.describe()}")
        print(f"            seen in {', '.join(weakness.affected_asanas)}")
    struggling = analysis.struggling_asanas()
    if struggling:
        print(f"  struggling with: {', '.join(struggling)}")

    # ---- 7. SUGGEST AGAIN -------------------------------------------------
    header("7. SUGGEST AGAIN", "The loop closes -- the plan has changed")
    adapted = rec_engine.build_session(profile, history, now=now)
    print(f"Focus: {adapted.focus}")
    for note in adapted.notes:
        print(f"  note: {note}")
    print()

    before = {i.asana_id: i.score for i in plan.items}
    seen = set()
    for item in adapted.items:
        if item.asana_id in seen:
            continue
        seen.add(item.asana_id)
        delta = item.score - before.get(item.asana_id, item.score)
        marker = f"  ({delta:+.1f} vs first plan)" if abs(delta) > 0.05 else ""
        target = f"  [targets {item.targeted_weakness}]" if item.targeted_weakness else ""
        print(f"  - {item.asana_name:24s} score {item.score:5.1f}{marker}{target}")
        print(f"      why: {item.reason}")

    print(f"\n{BAR}")
    print("  Loop complete: the weakness measured in step 3 changed the plan in step 7.")
    print(BAR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
