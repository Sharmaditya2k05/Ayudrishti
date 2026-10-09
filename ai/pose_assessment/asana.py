"""Asana configuration: the per-pose rule sets that drive assessment.

Each asana lives in its own JSON file under ``data/pose_rules/``. Adding a
new pose to AyuDrishti means dropping a new file in that directory -- no
Python change, no redeploy of the assessment engine. That is the modularity
requirement from the spec made concrete.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .rules import Rule, RuleConfigError

# data/pose_rules relative to the repository root (this file is
# ai/pose_assessment/asana.py, so three parents up is the root).
DEFAULT_RULES_DIR = Path(__file__).resolve().parents[2] / "data" / "pose_rules"

DIFFICULTY_ORDER = ("beginner", "intermediate", "advanced")


@dataclass
class AsanaConfig:
    """Everything the system knows about one yoga pose."""

    id: str
    name: str  # Sanskrit / canonical name
    english_name: str
    difficulty: str
    description: str
    target_goals: List[str]
    focus_areas: List[str]
    rules: List[Rule]
    components: Dict[str, str] = field(default_factory=dict)
    # "bilateral" poses look the same on both sides (Tadasana, Balasana).
    # "unilateral" poses have a lead and a rear side (Warrior II, Trikonasana)
    # and their rules use lead_/rear_ placeholders.
    symmetry: str = "bilateral"
    # Some asanas can only be judged from one angle: knee flexion in Chair
    # Pose is invisible head-on, so the app tells the user where to stand
    # the camera rather than silently scoring an unmeasurable pose.
    preferred_view: str = "front"
    camera_hint: str = ""
    # A reference photo shown before the user attempts the pose, so they know
    # what it looks like rather than being asked to hold an unfamiliar shape
    # sight-unseen. image_credit carries the attribution the photo's licence
    # requires; both are blank for an asana that has no photo yet.
    image_url: str = ""
    image_credit: str = ""
    hold_seconds: int = 30
    cues: List[str] = field(default_factory=list)
    benefits: List[str] = field(default_factory=list)
    contraindications: List[str] = field(default_factory=list)
    # Poses that build toward this one, used by the adaptive recommender when
    # a practitioner is struggling and needs an easier entry point.
    preparatory: List[str] = field(default_factory=list)
    # Which weaknesses this pose helps correct, e.g. "knee_alignment".
    corrects: List[str] = field(default_factory=list)
    # Where this pose belongs in a session arc, and how demanding it is.
    sequence_stage: str = "standing"
    intensity: int = 2
    min_visible_landmarks: int = 0

    # ---- derived -------------------------------------------------------

    @property
    def is_unilateral(self) -> bool:
        return self.symmetry == "unilateral"

    @property
    def difficulty_rank(self) -> int:
        try:
            return DIFFICULTY_ORDER.index(self.difficulty)
        except ValueError:
            return 0

    def required_landmarks(self) -> List[str]:
        """Every landmark any rule depends on, with placeholders expanded."""
        names: set[str] = set()
        for rule in self.rules:
            if self.is_unilateral:
                for side_map in ({"lead": "left", "rear": "right"},
                                 {"lead": "right", "rear": "left"}):
                    names.update(rule.resolve_landmarks(side_map))
            else:
                names.update(rule.resolve_landmarks())
        return sorted(names)

    def signature_rules(self) -> List[Rule]:
        """Rules used to decide *which* asana is being performed."""
        return [r for r in self.rules if r.signature]

    def component_label(self, component: str) -> str:
        return self.components.get(component, component.replace("_", " ").title())

    def rules_for_component(self, component: str) -> List[Rule]:
        return [r for r in self.rules if r.component == component]

    # ---- serialisation --------------------------------------------------

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "AsanaConfig":
        asana_id = str(data.get("id", "")).strip()
        if not asana_id:
            raise RuleConfigError("asana config needs an 'id'")

        raw_rules = data.get("rules") or []
        if not isinstance(raw_rules, list) or not raw_rules:
            raise RuleConfigError(f"asana '{asana_id}' defines no rules")

        rules: List[Rule] = []
        seen: set[str] = set()
        for raw in raw_rules:
            rule = Rule.from_dict(raw)
            if rule.id in seen:
                raise RuleConfigError(
                    f"asana '{asana_id}' has duplicate rule id '{rule.id}'"
                )
            seen.add(rule.id)
            rules.append(rule)

        symmetry = str(data.get("symmetry", "bilateral"))
        if symmetry not in ("bilateral", "unilateral"):
            raise RuleConfigError(
                f"asana '{asana_id}': symmetry must be 'bilateral' or 'unilateral'"
            )

        difficulty = str(data.get("difficulty", "beginner"))
        if difficulty not in DIFFICULTY_ORDER:
            raise RuleConfigError(
                f"asana '{asana_id}': difficulty must be one of {DIFFICULTY_ORDER}"
            )

        def str_list(key: str) -> List[str]:
            value = data.get(key) or []
            return [str(x) for x in value] if isinstance(value, list) else []

        components = data.get("components") or {}
        if not isinstance(components, dict):
            components = {}

        return cls(
            id=asana_id,
            name=str(data.get("name", asana_id)),
            english_name=str(data.get("english_name", asana_id)),
            difficulty=difficulty,
            description=str(data.get("description", "")),
            target_goals=str_list("target_goals"),
            focus_areas=str_list("focus_areas"),
            rules=rules,
            components={str(k): str(v) for k, v in components.items()},
            symmetry=symmetry,
            preferred_view=str(data.get("preferred_view", "front")),
            camera_hint=str(data.get("camera_hint", "")),
            image_url=str(data.get("image_url", "")),
            image_credit=str(data.get("image_credit", "")),
            hold_seconds=int(data.get("hold_seconds", 30)),
            cues=str_list("cues"),
            benefits=str_list("benefits"),
            contraindications=str_list("contraindications"),
            preparatory=str_list("preparatory"),
            corrects=str_list("corrects"),
            sequence_stage=str(data.get("sequence_stage", "standing")),
            intensity=int(data.get("intensity", 2)),
            min_visible_landmarks=int(data.get("min_visible_landmarks", 0)),
        )

    @classmethod
    def from_file(cls, path: Path) -> "AsanaConfig":
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        try:
            return cls.from_dict(data)
        except RuleConfigError as exc:
            raise RuleConfigError(f"{path.name}: {exc}") from exc

    def to_dict(self, include_rules: bool = True) -> Dict[str, object]:
        out: Dict[str, object] = {
            "id": self.id,
            "name": self.name,
            "english_name": self.english_name,
            "difficulty": self.difficulty,
            "description": self.description,
            "target_goals": list(self.target_goals),
            "focus_areas": list(self.focus_areas),
            "components": dict(self.components),
            "symmetry": self.symmetry,
            "preferred_view": self.preferred_view,
            "camera_hint": self.camera_hint,
            "image_url": self.image_url,
            "image_credit": self.image_credit,
            "hold_seconds": self.hold_seconds,
            "cues": list(self.cues),
            "benefits": list(self.benefits),
            "contraindications": list(self.contraindications),
            "preparatory": list(self.preparatory),
            "corrects": list(self.corrects),
            "sequence_stage": self.sequence_stage,
            "intensity": self.intensity,
        }
        if include_rules:
            out["rules"] = [r.to_dict() for r in self.rules]
        return out


class AsanaRegistry:
    """Loads and serves the asana library.

    Kept as an explicit object rather than module globals so tests can build
    a registry over a fixture directory without touching the real library.
    """

    def __init__(self, configs: Optional[Iterable[AsanaConfig]] = None) -> None:
        self._configs: Dict[str, AsanaConfig] = {}
        for cfg in configs or []:
            self.add(cfg)

    # ---- population -----------------------------------------------------

    def add(self, config: AsanaConfig) -> None:
        self._configs[config.id] = config

    @classmethod
    def from_directory(cls, directory: Optional[Path] = None) -> "AsanaRegistry":
        directory = Path(directory) if directory else DEFAULT_RULES_DIR
        registry = cls()
        if not directory.is_dir():
            raise FileNotFoundError(f"pose rules directory not found: {directory}")
        for path in sorted(directory.glob("*.json")):
            registry.add(AsanaConfig.from_file(path))
        if not registry._configs:
            raise RuleConfigError(f"no asana definitions found in {directory}")
        return registry

    # ---- access ---------------------------------------------------------

    def get(self, asana_id: str) -> Optional[AsanaConfig]:
        return self._configs.get(asana_id)

    def require(self, asana_id: str) -> AsanaConfig:
        cfg = self._configs.get(asana_id)
        if cfg is None:
            raise KeyError(
                f"unknown asana '{asana_id}'. Known: {sorted(self._configs)}"
            )
        return cfg

    def all(self) -> List[AsanaConfig]:
        return list(self._configs.values())

    def ids(self) -> List[str]:
        return sorted(self._configs)

    def by_difficulty(self, difficulty: str) -> List[AsanaConfig]:
        return [c for c in self._configs.values() if c.difficulty == difficulty]

    def by_goal(self, goal: str) -> List[AsanaConfig]:
        return [c for c in self._configs.values() if goal in c.target_goals]

    def up_to_difficulty(self, difficulty: str) -> List[AsanaConfig]:
        try:
            limit = DIFFICULTY_ORDER.index(difficulty)
        except ValueError:
            limit = 0
        return [c for c in self._configs.values() if c.difficulty_rank <= limit]

    def __len__(self) -> int:
        return len(self._configs)

    def __contains__(self, asana_id: object) -> bool:
        return asana_id in self._configs

    def __iter__(self):
        return iter(self._configs.values())


_registry: Optional[AsanaRegistry] = None


def get_registry(directory: Optional[Path] = None, *, reload: bool = False) -> AsanaRegistry:
    """Process-wide asana registry.

    The rule files are read once and cached; ``reload=True`` picks up edits
    without restarting, which is handy while authoring a new asana.
    """
    global _registry
    if _registry is None or reload:
        _registry = AsanaRegistry.from_directory(directory)
    return _registry
