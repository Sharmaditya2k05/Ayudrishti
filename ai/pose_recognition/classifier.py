"""Optional learned pose classifier.

The rule-based recogniser in :mod:`ai.pose_recognition.recognizer` is the
default: it needs no training data, works from day one, and can explain
every decision. This module adds a scikit-learn classifier for the cases
where a labelled dataset is available and can push accuracy further --
particularly for poses seen from unusual angles, where hand-written rules
are weakest.

The two are combined rather than swapped. :class:`HybridRecognizer` trusts
the model when it is confident *and* the rules do not strongly disagree,
and falls back to rules otherwise. That keeps the explainability guarantee:
whenever the system gives a reason, that reason is real.

PyTorch is intentionally not used here. A 49-feature, ten-class problem is
solved perfectly well by a gradient-boosted forest, and the spec is explicit
that deep learning should not be added to the MVP without cause.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from ..pose_detection.landmarks import PoseFrame
from .features import extract_features, feature_names
from .recognizer import (
    MIN_MATCH_SCORE,
    PoseCandidate,
    RecognitionResult,
    RuleBasedRecognizer,
)

DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "models" / "pose_classifier.joblib"
)

# Below this probability the model is not trusted over the rule engine.
MIN_MODEL_CONFIDENCE = 0.6


class ClassifierUnavailable(RuntimeError):
    """Raised when a trained model was requested but could not be loaded."""


@dataclass
class TrainingReport:
    accuracy: float
    n_train: int
    n_test: int
    classes: List[str]
    per_class_f1: Dict[str, float]
    confusion: List[List[int]]

    def summary(self) -> str:
        lines = [
            f"Accuracy: {self.accuracy:.3f} on {self.n_test} held-out samples",
            f"Trained on {self.n_train} samples across {len(self.classes)} asanas",
            "",
            "Per-class F1:",
        ]
        for name in sorted(self.per_class_f1, key=lambda k: self.per_class_f1[k]):
            lines.append(f"  {name:26s} {self.per_class_f1[name]:.3f}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, object]:
        return {
            "accuracy": round(self.accuracy, 4),
            "n_train": self.n_train,
            "n_test": self.n_test,
            "classes": list(self.classes),
            "per_class_f1": {k: round(v, 4) for k, v in self.per_class_f1.items()},
            "confusion": self.confusion,
        }


class MLPoseClassifier:
    """Scikit-learn classifier over the landmark feature vector."""

    def __init__(self, model=None, classes: Optional[Sequence[str]] = None) -> None:
        self.model = model
        self.classes = list(classes or [])
        self.feature_names = feature_names()

    # ---- training --------------------------------------------------------

    @classmethod
    def train(
        cls,
        features: Sequence[Sequence[float]],
        labels: Sequence[str],
        *,
        test_size: float = 0.2,
        random_state: int = 42,
    ) -> Tuple["MLPoseClassifier", TrainingReport]:
        """Fit a classifier and report held-out performance."""
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.metrics import confusion_matrix, f1_score
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline

        if len(features) != len(labels):
            raise ValueError("features and labels must be the same length")
        if len(set(labels)) < 2:
            raise ValueError("need at least two distinct asanas to train")

        # Stratify so every asana appears in both splits; an unstratified
        # split on a small dataset can leave a class entirely untested.
        x_train, x_test, y_train, y_test = train_test_split(
            list(features),
            list(labels),
            test_size=test_size,
            random_state=random_state,
            stratify=list(labels),
        )

        # HistGradientBoosting handles the MISSING sentinel natively and does
        # not need feature scaling, which keeps the pipeline honest about
        # what it is doing to the inputs.
        pipeline = Pipeline(
            [("model", HistGradientBoostingClassifier(random_state=random_state))]
        )
        pipeline.fit(x_train, y_train)

        predictions = pipeline.predict(x_test)
        classes = sorted(set(labels))
        f1_scores = f1_score(y_test, predictions, average=None, labels=classes, zero_division=0)

        report = TrainingReport(
            accuracy=float((predictions == y_test).mean())
            if hasattr(predictions, "mean")
            else sum(p == t for p, t in zip(predictions, y_test)) / len(y_test),
            n_train=len(x_train),
            n_test=len(x_test),
            classes=classes,
            per_class_f1={c: float(s) for c, s in zip(classes, f1_scores)},
            confusion=confusion_matrix(y_test, predictions, labels=classes).tolist(),
        )

        return cls(pipeline, classes), report

    # ---- inference -------------------------------------------------------

    def predict(self, frame: PoseFrame) -> Tuple[Optional[str], float]:
        """Predicted asana and its probability."""
        if self.model is None:
            raise ClassifierUnavailable("No model loaded.")

        features = [extract_features(frame)]
        try:
            probabilities = self.model.predict_proba(features)[0]
        except AttributeError:
            label = self.model.predict(features)[0]
            return str(label), 1.0

        best = max(range(len(probabilities)), key=lambda i: probabilities[i])
        classes = list(getattr(self.model, "classes_", self.classes))
        return str(classes[best]), float(probabilities[best])

    def predict_all(self, frame: PoseFrame) -> Dict[str, float]:
        """Probability for every known asana."""
        if self.model is None:
            raise ClassifierUnavailable("No model loaded.")
        probabilities = self.model.predict_proba([extract_features(frame)])[0]
        classes = list(getattr(self.model, "classes_", self.classes))
        return {str(c): float(p) for c, p in zip(classes, probabilities)}

    # ---- persistence -----------------------------------------------------

    def save(self, path: Optional[Path] = None) -> Path:
        import joblib

        path = Path(path or DEFAULT_MODEL_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model": self.model,
                "classes": self.classes,
                # Stored so a model trained against an older feature layout
                # is rejected instead of silently producing nonsense.
                "feature_names": self.feature_names,
            },
            path,
        )
        return path

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "MLPoseClassifier":
        import joblib

        path = Path(path or DEFAULT_MODEL_PATH)
        if not path.is_file():
            raise ClassifierUnavailable(
                f"No trained model at {path}. Train one with:\n"
                f"    python scripts/train_classifier.py --data data/datasets/landmarks.csv"
            )

        payload = joblib.load(path)
        stored_features = payload.get("feature_names", [])
        current = feature_names()
        if stored_features and stored_features != current:
            raise ClassifierUnavailable(
                f"Model at {path} was trained on a different feature layout "
                f"({len(stored_features)} features vs {len(current)}). Retrain it."
            )

        return cls(payload["model"], payload.get("classes", []))


class HybridRecognizer:
    """Rule-based recognition with an optional learned model layered on top.

    Deliberately conservative about deferring to the model: it only wins when
    it is confident and the rules put the same pose somewhere near the top.
    A model that contradicts the rules outright is treated as suspect, since
    the rules encode explicit biomechanics while the model encodes whatever
    happened to correlate in its training set.
    """

    def __init__(
        self,
        rule_recognizer: Optional[RuleBasedRecognizer] = None,
        classifier: Optional[MLPoseClassifier] = None,
        *,
        min_model_confidence: float = MIN_MODEL_CONFIDENCE,
    ) -> None:
        self.rules = rule_recognizer or RuleBasedRecognizer()
        self.classifier = classifier
        self.min_model_confidence = min_model_confidence

    @classmethod
    def with_model(
        cls, path: Optional[Path] = None, **kwargs
    ) -> "HybridRecognizer":
        """Load a trained model if one exists, else fall back to rules alone."""
        try:
            classifier = MLPoseClassifier.load(path)
        except ClassifierUnavailable:
            classifier = None
        return cls(classifier=classifier, **kwargs)

    @property
    def has_model(self) -> bool:
        return self.classifier is not None

    def recognize(
        self, frame: PoseFrame, *, expected: Optional[Sequence[str]] = None
    ) -> RecognitionResult:
        rule_result = self.rules.recognize(frame, expected=expected)

        if self.classifier is None:
            return rule_result

        try:
            label, probability = self.classifier.predict(frame)
        except Exception:
            # A model failure must never take out recognition entirely.
            return rule_result

        if label is None or probability < self.min_model_confidence:
            return rule_result

        if label == rule_result.asana_id:
            # Agreement: keep the rule result (it carries the candidate
            # breakdown) but raise confidence to reflect the corroboration.
            rule_result.confidence = min(1.0, max(rule_result.confidence, probability))
            rule_result.method = "hybrid(agreed)"
            return rule_result

        # Disagreement: only override when the rules also rated this pose
        # plausibly, so the model can refine a close call but not invent one.
        rule_match = next(
            (c.match for c in rule_result.candidates if c.asana_id == label), 0.0
        )
        if rule_match >= MIN_MATCH_SCORE * 0.85 and probability >= 0.75:
            config = self.rules.registry.get(label)
            return RecognitionResult(
                asana_id=label,
                asana_name=config.english_name if config else label,
                confidence=probability,
                method="hybrid(model)",
                lead_side=rule_result.lead_side,
                candidates=rule_result.candidates,
                ambiguous=True,
                reason=(
                    f"Classified as {config.english_name if config else label} by the "
                    f"trained model; the rule engine ranked it a close alternative."
                ),
            )

        rule_result.method = "hybrid(rules)"
        rule_result.reason += " The trained model disagreed, so the explicit alignment rules were used."
        return rule_result
