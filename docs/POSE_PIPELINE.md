# The pose pipeline

How a camera frame becomes a correction, and what to do if you need live
detection inside a native React Native build.

## The path a frame takes

```
camera frame
   ↓  MediaPipe Pose (on device)
33 landmarks  {x, y, z, visibility}
   ↓  PoseFrame            ai/pose_detection/landmarks.py
normalised body model, scaled by torso length
   ↓  recognition          ai/pose_recognition/recognizer.py
which asana is this?  (widened tolerances — shape, not quality)
   ↓  assessment           ai/pose_assessment/engine.py
per-rule measurements against that asana's target ranges
   ↓  scoring              ai/scoring/scoring.py
weighted component scores → overall score + confidence
   ↓  feedback             ai/feedback/feedback.py
prioritised, throttled, evidence-backed corrections
   ↓  safety               ai/safety/safety.py
motion, sustained deviation, optional sensor fusion
```

Only the first step is platform-specific. Everything below `PoseFrame` is
pure Python with no camera, no framework and no network, which is why the
whole chain is testable from synthetic skeletons.

## Landmark format

The contract between every backend and the rest of the system:

```json
[{"x": 0.42, "y": 0.61, "z": -0.1, "visibility": 0.97}, ...]   // exactly 33
```

- `x`, `y` normalised to `[0, 1]`, origin at the **top-left** of the frame
  (so `y` grows *downward* — the geometry helpers compensate internally).
- `z` is torso-relative depth; used sparingly, since single-camera depth is
  unreliable.
- `visibility` in `[0, 1]`. Below `0.5` a landmark is treated as unseen and
  every rule depending on it is excluded from the score.

Order is the standard MediaPipe Pose order, listed in
`ai/pose_detection/landmarks.py` and mirrored in
`frontend/src/pose/poseDetector.js`. **Index position is the wire format** —
do not reorder either list.

## The three detection backends

| Where | Backend | Status |
|---|---|---|
| Python (server, desktop scripts) | `ai/pose_detection/detector.py` | Working |
| Expo Web | MediaPipe Tasks Vision (WASM) | Working |
| iOS / Android native | native frame processor | Integration seam |

### Python

`PoseDetector` adapts to whichever MediaPipe API is installed:

- **Tasks API** (`mediapipe.tasks.python.vision.PoseLandmarker`) — the current
  interface and the *only* one in MediaPipe 1.x. Needs a `.task` bundle:
  ```bash
  python scripts/fetch_models.py
  ```
- **Legacy Solutions API** (`mp.solutions.pose.Pose`) — removed in 1.0, but
  still present in 0.10.x installs. Bundles its own weights.

The adapter tries legacy first, then Tasks, and raises a
`DetectorUnavailable` explaining the fix if neither starts. Nothing upstream
knows which is in use.

One caveat: the Tasks video API requires strictly increasing integer
millisecond timestamps and raises on a repeat. The adapter nudges the stamp
forward rather than dropping the frame.

### Web

`frontend/src/pose/poseDetector.js` loads Tasks Vision from a CDN and runs it
against the `<video>` element from `getUserMedia` — no canvas round-trip.
This is the fastest way to exercise the whole product, and `npm run web` is
the recommended development target.

### Native — the integration seam

MediaPipe has no JavaScript runtime inside React Native's JS engine, so
real-time detection needs a native frame processor. This cannot run in Expo
Go; it requires a custom dev build.

1. Create a dev build:
   ```bash
   cd frontend && npx expo prebuild
   ```
2. Add `react-native-vision-camera` and a MediaPipe pose frame-processor
   plugin for your platform.
3. Have the plugin return the 33 landmarks in the format above, with `x`/`y`
   normalised to `[0, 1]`.
4. Register it before the app mounts:
   ```js
   import PoseDetector from './src/pose/poseDetector';
   PoseDetector.nativeFrameProcessor = (frame) => myPlugin.detectPose(frame);
   ```

That is the only change required. `PracticeScreen`, the overlay, assessment,
feedback and scoring all consume the same landmark shape already.

## Request pacing

Detection is local and cheap; assessment is a network round-trip. The
practice screen therefore:

- runs detection **every animation frame** (drives the skeleton overlay), and
- calls `POST /assessment` at most every **260 ms**, skipping the call
  entirely while one is still in flight.

Never queue assessment requests. A backlog makes corrections describe a
posture the practitioner has already moved on from, which is worse than no
correction at all.

## Live state between requests

Each frame arrives as a separate HTTP call, but feedback throttling,
sustained-misalignment timers and motion history must persist across them.
`backend/services/assessment_service.py` holds that per-(user, session) state
in a bounded LRU.

Call `POST /assessment/reset` when moving to the next asana, otherwise the
previous pose's cooldowns suppress the first corrections of the new one.

## Camera placement

Some poses cannot be judged head-on — knee flexion in Chair Pose is
foreshortened to nothing. Each asana declares:

```json
"preferred_view": "side",
"camera_hint": "Place your camera to your side, about 2-3 metres away, ..."
```

Show `camera_hint` before the pose starts. When required landmarks are not
visible the assessment says so explicitly, naming the joints, rather than
scoring what it cannot see.

## Debugging a rule

```bash
python scripts/live_session.py --asana trikonasana
```

Shows measured values against target ranges in real time. Edit the JSON in
`data/pose_rules/`, restart, and the change is visible on the next frame — no
retraining, no rebuild.

For a deterministic check without a camera, the fixtures in
`tests/fixtures.py` provide a hand-built reference skeleton per asana plus a
`perturb()` helper for injecting one specific fault:

```python
from ai.pose_assessment import PoseAssessmentEngine
from tests.fixtures import build_frame, warrior_ii_good, perturb

engine = PoseAssessmentEngine()
faulty = perturb(warrior_ii_good(), left_knee=(0.13, -0.02))
result = engine.assess(build_frame(faulty), "virabhadrasana_ii")

print(result.overall)
for d in result.deviations:
    print(d.rule_id, d.value, d.feedback)
```
