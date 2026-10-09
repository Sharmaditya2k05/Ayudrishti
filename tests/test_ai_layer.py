"""Unit tests for the AI layer, independent of the API and database."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import pytest

from ai.feedback import FeedbackGenerator
from ai.pose_assessment import PoseAssessmentEngine, get_registry
from ai.pose_assessment import geometry as geo
from ai.pose_assessment.rules import Rule, RuleConfigError
from ai.pose_detection.landmarks import PoseFrame
from ai.pose_recognition import RuleBasedRecognizer, TemporalRecognizer, feature_names
from ai.pose_recognition.features import extract_features
from ai.recommendation import (
    PerformanceAnalyzer,
    PoseRecord,
    PracticeHistory,
    RecommendationEngine,
    UserProfile,
)
from ai.safety import WELLNESS_DISCLAIMER, PhysiologicalSnapshot, SafetyMonitor
from ai.scoring import aggregate_rules, grade_label, score_session
from tests.fixtures import REFERENCE_POSES, build_frame, perturb, warrior_ii_good


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


class TestGeometry:
    def test_right_angle(self):
        assert geo.joint_angle((0, 1), (0, 0), (1, 0)) == pytest.approx(90.0)

    def test_straight_limb(self):
        assert geo.joint_angle((0, 0), (1, 0), (2, 0)) == pytest.approx(180.0)

    def test_degenerate_segment_returns_none(self):
        """Two landmarks on the same pixel must not produce a fake angle."""
        assert geo.joint_angle((1, 1), (1, 1), (2, 2)) is None

    def test_vertical_and_horizontal_segments(self):
        assert geo.segment_angle_to_vertical((0, 0), (0, 1)) == pytest.approx(0.0)
        assert geo.segment_angle_to_vertical((0, 0), (1, 0)) == pytest.approx(90.0)
        assert geo.segment_angle_to_horizontal((0, 0), (1, 0)) == pytest.approx(0.0)

    def test_signed_vertical_offset_is_positive_when_first_point_is_higher(self):
        # Image y grows downward, so the smaller y is the higher point.
        assert geo.signed_vertical_offset((0, 0.2), (0, 0.6), 0.4) == pytest.approx(1.0)

    def test_scale_of_zero_is_rejected(self):
        assert geo.horizontal_offset((0, 0), (1, 0), 0.0) is None

    def test_point_line_distance(self):
        assert geo.point_line_distance((0, 1), (0, 0), (1, 0), 1.0) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


class TestRules:
    def _rule(self, **kw) -> Rule:
        base = dict(
            id="knee",
            component="legs",
            measurement="angle",
            landmarks=["left_hip", "left_knee", "left_ankle"],
            target_min=85.0,
            target_max=115.0,
            tolerance=30.0,
        )
        base.update(kw)
        return Rule(**base)

    def test_value_inside_target_scores_full_marks(self):
        assert self._rule().score_value(100.0) == (1.0, "ok")

    def test_score_decays_linearly_outside_the_target(self):
        rule = self._rule()
        score, status = rule.score_value(70.0)  # 15 degrees below the 85 floor
        assert status == "low"
        assert score == pytest.approx(0.5)

    def test_score_floors_at_zero(self):
        score, status = self._rule().score_value(10.0)
        assert (score, status) == (0.0, "low")

    def test_tolerance_scale_widens_the_band_for_recognition(self):
        rule = self._rule()
        tight, _ = rule.score_value(70.0)
        loose, _ = rule.score_value(70.0, tolerance_scale=2.0)
        assert loose > tight

    def test_wrong_landmark_count_is_rejected(self):
        with pytest.raises(RuleConfigError, match="needs 3 landmarks"):
            self._rule(landmarks=["left_hip", "left_knee"])

    def test_unknown_measurement_is_rejected(self):
        with pytest.raises(RuleConfigError, match="unknown measurement"):
            self._rule(measurement="vibes")

    def test_inverted_target_range_is_rejected(self):
        with pytest.raises(RuleConfigError, match="exceeds"):
            self._rule(target_min=120.0, target_max=80.0)

    def test_invisible_landmark_makes_the_rule_unavailable(self):
        """A rule must refuse to score rather than guess at a hidden joint."""
        frame = build_frame(warrior_ii_good())
        frame.landmarks["left_knee"] = frame.landmarks["left_knee"].__class__(
            "left_knee", 0.2, 0.6, 0.0, 0.05
        )
        result = self._rule().evaluate(frame)
        assert result.status == "unavailable"
        assert result.value is None

    def test_side_placeholders_resolve(self):
        rule = self._rule(landmarks=["lead_hip", "lead_knee", "lead_ankle"])
        assert rule.resolve_landmarks({"lead": "right", "rear": "left"}) == [
            "right_hip",
            "right_knee",
            "right_ankle",
        ]


# ---------------------------------------------------------------------------
# Asana library
# ---------------------------------------------------------------------------


class TestAsanaLibrary:
    def test_library_loads(self):
        registry = get_registry()
        assert len(registry) >= 10

    def test_every_rule_has_actionable_feedback(self):
        """No rule may fail without telling the user what to do about it."""
        for config in get_registry().all():
            for rule in config.rules:
                assert rule.feedback_low or rule.feedback_high, (
                    f"{config.id}.{rule.id} has no feedback text"
                )

    def test_feedback_never_just_says_incorrect(self):
        banned = ("incorrect", "wrong", "bad pose")
        for config in get_registry().all():
            for rule in config.rules:
                for text in (rule.feedback_low, rule.feedback_high):
                    if not text:
                        continue
                    assert not any(b in text.lower() for b in banned), (
                        f"{config.id}.{rule.id}: unhelpful feedback {text!r}"
                    )

    def test_thresholds_are_pose_specific(self):
        """The same joint must not share one universal threshold everywhere."""
        registry = get_registry()
        knee_targets = set()
        for config in registry.all():
            for rule in config.rules:
                if rule.measurement == "angle" and "knee" in rule.landmarks[1]:
                    knee_targets.add((rule.target_min, rule.target_max))
        assert len(knee_targets) > 1, "knee angle targets should differ between asanas"

    def test_unilateral_poses_use_side_placeholders(self):
        for config in get_registry().all():
            if not config.is_unilateral:
                continue
            assert any(
                lm.startswith(("lead_", "rear_"))
                for rule in config.rules
                for lm in rule.landmarks
            ), f"{config.id} is unilateral but defines no lead/rear rules"


# ---------------------------------------------------------------------------
# Assessment engine
# ---------------------------------------------------------------------------


class TestAssessmentEngine:
    engine = PoseAssessmentEngine()

    @pytest.mark.parametrize("asana_id", sorted(REFERENCE_POSES))
    def test_reference_skeleton_scores_well(self, asana_id):
        result = self.engine.assess(build_frame(REFERENCE_POSES[asana_id]()), asana_id)
        assert result.overall >= 90, f"{asana_id} scored {result.overall:.1f}"
        assert result.reliable

    def test_undetected_body_is_reported_not_scored_as_zero(self):
        result = self.engine.assess(PoseFrame.empty(), "tadasana")
        assert result.detected is False
        assert result.notes

    def test_lead_side_is_detected_for_unilateral_poses(self):
        left = self.engine.assess(build_frame(warrior_ii_good()), "virabhadrasana_ii")
        assert left.lead_side == "left"

        # Mirror the skeleton: the same pose led with the other leg must score
        # equally well rather than being penalised as a bad left-lead pose.
        mirrored = {
            name.replace("left", "TMP").replace("right", "left").replace("TMP", "right"): (
                1.0 - x,
                y,
            )
            for name, (x, y) in warrior_ii_good().items()
        }
        right = self.engine.assess(build_frame(mirrored), "virabhadrasana_ii")
        assert right.lead_side == "right"
        assert right.overall == pytest.approx(left.overall, abs=2.0)

    def test_a_specific_fault_isolates_to_its_own_rule(self):
        faulty = perturb(warrior_ii_good(), left_knee=(0.13, -0.02))
        result = self.engine.assess(build_frame(faulty), "virabhadrasana_ii")
        assert [d.rule_id for d in result.deviations] == ["front_knee_over_ankle"]

    def test_deviations_are_ranked_by_importance(self):
        faulty = perturb(
            warrior_ii_good(), left_knee=(0.13, -0.02), right_wrist=(0, 0.2)
        )
        result = self.engine.assess(build_frame(faulty), "virabhadrasana_ii")
        priorities = [d.severity * d.weight for d in result.deviations]
        assert priorities == sorted(priorities, reverse=True)

    def test_smoothing_dampens_a_single_bad_frame(self):
        engine = PoseAssessmentEngine(smoothing_window=5)
        for _ in range(4):
            engine.assess_smoothed(build_frame(warrior_ii_good()), "virabhadrasana_ii")
        faulty = perturb(warrior_ii_good(), left_knee=(0.20, -0.05))
        raw = engine.assess(build_frame(faulty), "virabhadrasana_ii").overall
        smoothed = engine.assess_smoothed(build_frame(faulty), "virabhadrasana_ii").overall
        assert smoothed > raw


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class TestScoring:
    def test_unavailable_rules_are_excluded_and_lower_confidence(self):
        engine = PoseAssessmentEngine()
        result = engine.assess(build_frame(warrior_ii_good()), "virabhadrasana_ii")
        results = result.score.rule_results
        for res in results[:3]:
            res.status = "unavailable"
        rescored = aggregate_rules("virabhadrasana_ii", results)
        assert rescored.confidence < 1.0

    def test_weights_matter(self):
        engine = PoseAssessmentEngine()
        result = engine.assess(build_frame(warrior_ii_good()), "virabhadrasana_ii")
        heavy = max(result.score.rule_results, key=lambda r: r.weight)
        light = min(result.score.rule_results, key=lambda r: r.weight)
        assert heavy.weight > light.weight

    def test_session_score_averages_per_asana_then_across_asanas(self):
        # Warrior sampled three times must not outweigh a single Tadasana.
        summary = score_session(
            {"virabhadrasana_ii": [60, 60, 60], "tadasana": [100]}
        )
        assert summary.overall == pytest.approx(80.0)
        assert summary.best_pose == "tadasana"
        assert summary.weakest_pose == "virabhadrasana_ii"

    def test_grade_labels(self):
        assert grade_label(95) == "excellent"
        assert grade_label(72) == "fair"
        assert grade_label(30) == "keep practising"


# ---------------------------------------------------------------------------
# Recognition
# ---------------------------------------------------------------------------


class TestRecognition:
    recognizer = RuleBasedRecognizer()

    @pytest.mark.parametrize("asana_id", sorted(REFERENCE_POSES))
    def test_each_reference_pose_is_recognised(self, asana_id):
        result = self.recognizer.recognize(build_frame(REFERENCE_POSES[asana_id]()))
        assert result.asana_id == asana_id

    def test_a_poorly_performed_pose_is_still_recognised(self):
        """Recognition must judge shape, not quality."""
        sloppy = perturb(
            warrior_ii_good(),
            left_knee=(0.06, -0.03),
            right_wrist=(0, 0.14),
            left_wrist=(0, 0.10),
        )
        result = self.recognizer.recognize(build_frame(sloppy))
        assert result.asana_id == "virabhadrasana_ii"

    def test_an_unknown_shape_is_not_forced_into_a_known_pose(self):
        nonsense = {
            "left_shoulder": (0.10, 0.10), "right_shoulder": (0.90, 0.90),
            "left_hip": (0.10, 0.90), "right_hip": (0.90, 0.10),
            "left_knee": (0.50, 0.10), "right_knee": (0.50, 0.90),
            "left_ankle": (0.10, 0.50), "right_ankle": (0.90, 0.50),
            "left_elbow": (0.30, 0.30), "right_elbow": (0.70, 0.70),
            "left_wrist": (0.20, 0.80), "right_wrist": (0.80, 0.20),
            "nose": (0.50, 0.50),
        }
        result = self.recognizer.recognize(build_frame(nonsense))
        assert result.asana_id is None or result.confidence < 0.75

    def test_empty_frame_is_handled(self):
        result = self.recognizer.recognize(PoseFrame.empty())
        assert result.asana_id is None
        assert "No body" in result.reason

    def test_temporal_recognizer_ignores_a_single_stray_frame(self):
        temporal = TemporalRecognizer(window=6, switch_ratio=0.6)
        for _ in range(5):
            temporal.update(build_frame(warrior_ii_good()))
        stray = temporal.update(build_frame(REFERENCE_POSES["balasana"]()))
        assert stray.asana_id == "virabhadrasana_ii", "one odd frame must not switch pose"


class TestFeatures:
    def test_vector_length_matches_names(self):
        features = extract_features(build_frame(warrior_ii_good()))
        assert len(features) == len(feature_names())

    def test_features_are_translation_and_scale_invariant(self):
        """The same pose nearer the camera or off-centre must look the same."""
        base = warrior_ii_good()
        shifted = {k: (x * 0.5 + 0.25, y * 0.5 + 0.25) for k, (x, y) in base.items()}
        a = extract_features(build_frame(base))
        b = extract_features(build_frame(shifted))
        for i, (x, y) in enumerate(zip(a, b)):
            assert x == pytest.approx(y, abs=0.02), f"feature {feature_names()[i]} moved"


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------


class TestFeedback:
    def test_correction_names_a_body_part_and_an_action(self):
        engine, generator = PoseAssessmentEngine(), FeedbackGenerator()
        faulty = perturb(warrior_ii_good(), left_knee=(0.13, -0.02))
        bundle = generator.generate(
            engine.assess(build_frame(faulty), "virabhadrasana_ii"), timestamp=0.0
        )
        corrections = [m for m in bundle.messages if m.kind == "correction"]
        assert corrections
        assert corrections[0].measured_value is not None
        assert corrections[0].rule_id

    def test_messages_are_capped(self):
        engine = PoseAssessmentEngine()
        generator = FeedbackGenerator(max_messages=2)
        very_bad = perturb(
            warrior_ii_good(),
            left_knee=(0.25, -0.2), left_wrist=(0, 0.4),
            right_wrist=(0, 0.45), right_knee=(-0.25, -0.1),
        )
        bundle = generator.generate(
            engine.assess(build_frame(very_bad), "virabhadrasana_ii"), timestamp=0.0
        )
        assert len([m for m in bundle.messages if m.kind == "correction"]) <= 2

    def test_throttling_suppresses_immediate_repeats(self):
        engine, generator = PoseAssessmentEngine(), FeedbackGenerator(cooldown=6.0)
        faulty = build_frame(perturb(warrior_ii_good(), left_knee=(0.13, -0.02)))
        first = generator.generate(engine.assess(faulty, "virabhadrasana_ii"), timestamp=0.0)
        second = generator.generate(engine.assess(faulty, "virabhadrasana_ii"), timestamp=1.0)
        assert [m for m in first.messages if m.kind == "correction"]
        assert not [m for m in second.messages if m.kind == "correction"]

    def test_throttling_does_not_fake_praise(self):
        """A silenced repeat must never be mistaken for a fixed fault."""
        engine, generator = PoseAssessmentEngine(), FeedbackGenerator(cooldown=6.0)
        faulty = build_frame(perturb(warrior_ii_good(), left_knee=(0.13, -0.02)))
        generator.generate(engine.assess(faulty, "virabhadrasana_ii"), timestamp=0.0)
        second = generator.generate(engine.assess(faulty, "virabhadrasana_ii"), timestamp=1.0)
        assert not [m for m in second.messages if m.kind == "praise"]

    def test_praise_follows_a_real_correction(self):
        engine, generator = PoseAssessmentEngine(), FeedbackGenerator(cooldown=6.0)
        faulty = build_frame(perturb(warrior_ii_good(), left_knee=(0.13, -0.02)))
        generator.generate(engine.assess(faulty, "virabhadrasana_ii"), timestamp=0.0)
        fixed = build_frame(warrior_ii_good())
        after = generator.generate(engine.assess(fixed, "virabhadrasana_ii"), timestamp=2.0)
        assert [m for m in after.messages if m.kind == "praise"]


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------


class TestSafety:
    def test_good_steady_pose_raises_nothing(self):
        monitor, engine = SafetyMonitor(), PoseAssessmentEngine()
        frame = build_frame(warrior_ii_good())
        frame.timestamp = 0.0
        assert monitor.check(frame, engine.assess(frame, "virabhadrasana_ii")) == []

    def test_sudden_movement_prompts_a_reset(self):
        monitor, engine = SafetyMonitor(), PoseAssessmentEngine()
        first = build_frame(warrior_ii_good())
        first.timestamp = 0.0
        monitor.check(first, engine.assess(first, "virabhadrasana_ii"))

        jumped = build_frame(perturb(warrior_ii_good(), left_knee=(0.35, -0.30)))
        jumped.timestamp = 0.12
        alerts = monitor.check(jumped, engine.assess(jumped, "virabhadrasana_ii"))
        assert any(a.code == "sudden_movement" for a in alerts)

    def test_sustained_misalignment_is_only_flagged_after_time(self):
        monitor, engine = SafetyMonitor(), PoseAssessmentEngine()
        bad = perturb(
            warrior_ii_good(), left_knee=(0.34, -0.30),
            left_wrist=(0, 0.4), right_wrist=(0, 0.45), right_knee=(-0.3, -0.1),
        )
        codes = []
        for t in (0.0, 5.0, 13.5):
            frame = build_frame(bad)
            frame.timestamp = t
            codes.append(
                [a.code for a in monitor.check(frame, engine.assess(frame, "virabhadrasana_ii"), timestamp=t)]
            )
        assert "sustained_misalignment" not in codes[0]
        assert "sustained_misalignment" in codes[2]

    def test_works_without_any_wearable(self):
        monitor, engine = SafetyMonitor(), PoseAssessmentEngine()
        frame = build_frame(warrior_ii_good())
        frame.timestamp = 0.0
        assert monitor.check(frame, engine.assess(frame, "virabhadrasana_ii"), None) == []

    def test_physiological_messages_carry_the_wellness_disclaimer(self):
        monitor = SafetyMonitor(resting_heart_rate=60)
        frame = build_frame(warrior_ii_good())
        frame.timestamp = 0.0
        alerts = monitor.check(frame, None, PhysiologicalSnapshot(heart_rate=155))
        assert alerts
        for alert in alerts:
            assert "not a medical measurement" in alert.message

    def test_no_alert_claims_a_diagnosis(self):
        monitor = SafetyMonitor(resting_heart_rate=60)
        frame = build_frame(warrior_ii_good())
        frame.timestamp = 0.0
        alerts = monitor.check(
            frame, None, PhysiologicalSnapshot(heart_rate=170, spo2=88, gsr=40)
        )
        banned = ("diagnos", "disease", "injury detected", "medical grade")
        for alert in alerts:
            # The standard disclaimer says the reading is *not* a diagnosis,
            # so strip it before scanning for claim words.
            body = alert.message.replace(WELLNESS_DISCLAIMER, '').lower()
            assert not any(b in body for b in banned), alert.message


# ---------------------------------------------------------------------------
# Recommendation and adaptation
# ---------------------------------------------------------------------------


def _history_with_weak_knee(sessions: int = 4) -> PracticeHistory:
    base = datetime(2026, 8, 1, 7, 0)
    records = []
    for i in range(sessions):
        when = base + timedelta(days=i * 2)
        records.append(
            PoseRecord(
                asana_id="virabhadrasana_ii",
                score=64 + i,
                performed_at=when,
                component_scores={"knee": 50 + i, "torso": 88, "arms": 86,
                                  "legs": 84, "hips": 87, "shoulders": 90},
            )
        )
        records.append(
            PoseRecord(
                asana_id="trikonasana",
                score=86 + i,
                performed_at=when,
                component_scores={"legs": 88, "torso": 87, "arms": 85, "hips": 84},
            )
        )
    return PracticeHistory(records)


class TestRecommendation:
    engine = RecommendationEngine()

    def test_beginner_is_never_offered_advanced_poses(self):
        profile = UserProfile(experience="beginner", goals=["flexibility"])
        for rec in self.engine.recommend(profile):
            assert rec.difficulty == "beginner"

    def test_goals_drive_selection(self):
        relaxed = self.engine.recommend(
            UserProfile(experience="intermediate", goals=["relaxation"]), limit=3
        )
        assert any("relaxation" in f.name or "relax" in f.explanation.lower()
                   for r in relaxed for f in r.factors)

    def test_avoided_poses_are_excluded(self):
        profile = UserProfile(experience="intermediate", goals=["strength"],
                              avoid=["virabhadrasana_ii"])
        assert all(r.asana_id != "virabhadrasana_ii" for r in self.engine.recommend(profile))

    def test_every_recommendation_explains_itself(self):
        profile = UserProfile(experience="intermediate", goals=["strength"])
        for rec in self.engine.recommend(profile):
            assert rec.reason
            assert rec.factors

    def test_session_is_correctly_sequenced(self):
        plan = self.engine.build_session(
            UserProfile(experience="intermediate", goals=["strength"], preferred_duration=25)
        )
        assert plan.items[0].sequence_stage == "warmup"
        assert plan.items[-1].sequence_stage == "cooldown"

    def test_session_respects_the_time_budget(self):
        for minutes in (10, 20, 30, 45):
            plan = self.engine.build_session(
                UserProfile(experience="intermediate", goals=["strength"]),
                duration_minutes=minutes,
            )
            assert plan.total_minutes <= minutes * 1.05, f"{minutes}min plan overran"
            assert plan.total_minutes >= minutes * 0.6, f"{minutes}min plan underfilled"

    def test_unilateral_poses_are_practised_on_both_sides(self):
        plan = self.engine.build_session(
            UserProfile(experience="intermediate", goals=["strength"])
        )
        for item in plan.items:
            config = get_registry().require(item.asana_id)
            assert item.sides == (2 if config.is_unilateral else 1)

    def test_repeated_rounds_do_not_share_mutable_state(self):
        """Each round is its own entry; scaling one must not scale the rest."""
        plan = self.engine.build_session(
            UserProfile(experience="beginner", goals=["flexibility"]), duration_minutes=25
        )
        if plan.rounds > 1:
            core = [i for i in plan.items if i.sequence_stage not in ("warmup", "cooldown")]
            assert len({id(i) for i in core}) == len(core)


class TestAdaptation:
    def test_recurring_weakness_is_detected(self):
        analysis = PerformanceAnalyzer().analyze(_history_with_weak_knee())
        assert analysis.weaknesses
        assert analysis.weaknesses[0].component == "knee"

    def test_struggling_pose_is_identified(self):
        analysis = PerformanceAnalyzer().analyze(_history_with_weak_knee())
        assert "virabhadrasana_ii" in analysis.struggling_asanas()

    def test_improvement_trend_is_positive(self):
        analysis = PerformanceAnalyzer().analyze(_history_with_weak_knee())
        assert analysis.overall_trend is not None and analysis.overall_trend > 0

    def test_recommendation_changes_because_of_history(self):
        """The same profile with a weakness must get a different plan."""
        profile = UserProfile(experience="intermediate", goals=["strength"])
        engine = RecommendationEngine()

        before = {r.asana_id: r.score for r in engine.recommend(profile)}
        after = {
            r.asana_id: r.score
            for r in engine.recommend(
                profile, _history_with_weak_knee(), now=datetime(2026, 8, 12)
            )
        }
        assert after["virabhadrasana_ii"] > before["virabhadrasana_ii"], (
            "a struggling pose should be prioritised, not dropped"
        )

    def test_plan_focus_names_the_weakness(self):
        plan = RecommendationEngine().build_session(
            UserProfile(experience="intermediate", goals=["strength"]),
            _history_with_weak_knee(),
            now=datetime(2026, 8, 12),
        )
        assert "knee" in plan.focus.lower()
        assert any("knee" in note.lower() for note in plan.notes)

    def test_no_history_is_handled(self):
        analysis = PerformanceAnalyzer().analyze(PracticeHistory())
        assert analysis.weaknesses == []
        assert analysis.ready_to_progress is False
