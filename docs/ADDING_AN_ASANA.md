# Adding an asana

Drop a JSON file in `data/pose_rules/`. Both the recogniser and the
assessment engine pick it up on restart — no Python change, no retraining,
no redeploy of the engine. That modularity is the point: the rule files are
the source of truth, and the engine is a generic evaluator over them.

## Minimal example

```json
{
  "id": "ustrasana",
  "name": "Ustrasana",
  "english_name": "Camel Pose",
  "difficulty": "intermediate",
  "symmetry": "bilateral",
  "preferred_view": "side",
  "camera_hint": "Place your camera to your side, about 2-3 metres away.",
  "hold_seconds": 25,
  "sequence_stage": "floor",
  "intensity": 3,
  "description": "A kneeling backbend...",
  "target_goals": ["flexibility", "mobility"],
  "focus_areas": ["spine", "chest"],
  "corrects": ["spine_extension"],
  "preparatory": ["bhujangasana"],
  "cues": ["Kneel with your hips over your knees", "..."],
  "benefits": ["Opens the chest and front of the hips"],
  "contraindications": ["Neck injury", "Recent back injury"],
  "components": { "spine": "Back extension", "hips": "Hips", "arms": "Arms" },
  "rules": [
    {
      "id": "hips_stacked_over_knees",
      "component": "hips",
      "body_part": "hips",
      "measurement": "horizontal_gap",
      "landmarks": ["left_hip", "left_knee"],
      "target": [0.0, 0.35],
      "tolerance": 0.4,
      "weight": 2.0,
      "feedback": {
        "high": "Bring your hips forward over your knees rather than sitting back."
      }
    }
  ]
}
```

Validate it immediately:

```bash
python -c "from ai.pose_assessment import get_registry; r=get_registry(reload=True); c=r.require('ustrasana'); print(c.english_name, len(c.rules), 'rules')"
```

Malformed definitions raise at load with the file and rule named, and the API
fails to start rather than surfacing the problem mid-session.

## Measurement types

| `measurement` | Landmarks | Unit | Measures |
|---|---|---|---|
| `angle` | 3 | degrees | Interior joint angle at the middle point |
| `segment_vertical` | 2 | degrees | Tilt from vertical (0 = upright) |
| `segment_horizontal` | 2 | degrees | Tilt from horizontal (0 = level) |
| `straightness` | 3 | degrees | Bend in a chain (0 = straight line) |
| `horizontal_gap` | 2 | torso | Unsigned horizontal separation |
| `vertical_gap` | 2 | torso | Unsigned vertical separation |
| `signed_vertical_gap` | 2 | torso | How far the **first** point is *above* the second |
| `signed_horizontal_gap` | 2 | torso | How far the first is *right* of the second |
| `distance` | 2 | torso | Straight-line distance |
| `distance_ratio` | 4 | ratio | `dist(a,b) / dist(c,d)` |
| `point_line_distance` | 3 | torso | Distance from `p0` to the line `p1–p2` |

"torso" means **torso lengths** — shoulder-centre to hip-centre. Everything
distance-based is expressed this way so a tall person, a short person, and
someone standing closer to the camera are all judged identically.

## Writing a good rule

**Pick the measurement that matches the cue.** "Knee over ankle" is a
`horizontal_gap`, not an angle. "Keep your torso upright" is
`segment_vertical`. If a rule needs an awkward measurement, the cue is
probably two rules.

**Target is the acceptable band, tolerance is how far past it scores zero.**
Score falls linearly from 1.0 at the edge of the target to 0.0 one full
tolerance beyond. Too tight and beginners see 0% for a reasonable attempt;
too loose and the rule never fires. A tolerance of roughly 1.5–2× the target
band's width is a sane starting point.

**Weight by consequence, not by visibility.** A collapsed front knee is a
knee-injury risk and deserves 2.5. A slightly low rear arm is cosmetic at
1.0. Weight drives which correction the user actually hears, since only the
top one or two are surfaced at a time.

**Write feedback as an instruction.** Name the body part and the direction.
`low` fires when the value is *below* the target, `high` when *above*. Leave
one empty if only one direction is a fault. A test enforces that no feedback
string contains "incorrect", "wrong" or "bad pose".

**Mark the discriminators.** If a rule is what separates this pose from a
look-alike, set `"discriminative": true`. Recognition widens tolerances to
match shape rather than quality, but leaves discriminative rules sharp —
"hips above shoulders" is exactly what tells Downward Dog from a seated
forward bend, and widening it erases the distinction.

## Unilateral poses

If the pose has a lead and a rear side, set `"symmetry": "unilateral"` and
write rules with `lead_` / `rear_` prefixes:

```json
"landmarks": ["lead_hip", "lead_knee", "lead_ankle"]
```

The engine evaluates both left-lead and right-lead assignments and keeps the
better-scoring one, so the practitioner can lead with either leg. Use literal
`left_` / `right_` for things that are genuinely side-specific regardless of
lead, such as "shoulders level".

## Choosing the view

If a key measurement is foreshortened head-on — knee flexion in a squat, any
forward fold — set `"preferred_view": "side"` and write a `camera_hint`. The
app shows it before the pose begins. Assessing a side-view pose from the
front produces low scores that reflect the camera, not the practitioner.

## Where it slots into a session

`sequence_stage` is one of `warmup`, `standing`, `balance`, `floor`,
`cooldown`, and orders the session arc. `intensity` (1–5) keeps demanding
poses from stacking up and softens plans for older practitioners.

## Test it

```bash
python scripts/live_session.py --asana ustrasana
```

Then add a reference skeleton to `tests/fixtures.py` so the pose is covered
by the automated suite — `test_reference_skeleton_scores_well` and the
recognition confusion check both parametrise over `REFERENCE_POSES`, so a new
entry is picked up with no further wiring.
