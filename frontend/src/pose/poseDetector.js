/**
 * On-device pose detection.
 *
 * Landmarks are extracted on the device and only the 33 coordinates are sent
 * to the server. The camera image never leaves the phone, which is what makes
 * AyuDrishti's privacy claim structural rather than a policy promise.
 *
 * Two backends, selected at runtime:
 *
 *  - **web** (Expo Web, and the fastest way to run the whole pipeline):
 *    MediaPipe Tasks Vision compiled to WASM, running against a `<video>`
 *    element from `getUserMedia`. Fully functional.
 *
 *  - **native** (iOS/Android): MediaPipe has no JS runtime inside React
 *    Native's engine, so real-time detection needs a native frame processor
 *    (react-native-vision-camera plus a pose plugin) in a custom dev build.
 *    `NativePoseAdapter` below is the single seam that has to be filled in;
 *    everything downstream already works against the same landmark format.
 *
 * See docs/POSE_PIPELINE.md for the native wiring steps.
 */

import { Platform } from 'react-native';

import { WebPoseAdapter } from './webPoseAdapter';

/** MediaPipe Pose landmark order. Index position is the wire format. */
export const LANDMARK_NAMES = [
  'nose',
  'left_eye_inner', 'left_eye', 'left_eye_outer',
  'right_eye_inner', 'right_eye', 'right_eye_outer',
  'left_ear', 'right_ear',
  'mouth_left', 'mouth_right',
  'left_shoulder', 'right_shoulder',
  'left_elbow', 'right_elbow',
  'left_wrist', 'right_wrist',
  'left_pinky', 'right_pinky',
  'left_index', 'right_index',
  'left_thumb', 'right_thumb',
  'left_hip', 'right_hip',
  'left_knee', 'right_knee',
  'left_ankle', 'right_ankle',
  'left_heel', 'right_heel',
  'left_foot_index', 'right_foot_index',
];

/** Skeleton edges for the overlay. */
export const POSE_CONNECTIONS = [
  ['left_shoulder', 'right_shoulder'],
  ['left_shoulder', 'left_elbow'], ['left_elbow', 'left_wrist'],
  ['right_shoulder', 'right_elbow'], ['right_elbow', 'right_wrist'],
  ['left_shoulder', 'left_hip'], ['right_shoulder', 'right_hip'],
  ['left_hip', 'right_hip'],
  ['left_hip', 'left_knee'], ['left_knee', 'left_ankle'],
  ['right_hip', 'right_knee'], ['right_knee', 'right_ankle'],
  ['left_ankle', 'left_heel'], ['left_heel', 'left_foot_index'],
  ['right_ankle', 'right_heel'], ['right_heel', 'right_foot_index'],
];

export class PoseDetectorUnavailable extends Error {
  constructor(message, { platform, remedy } = {}) {
    super(message);
    this.name = 'PoseDetectorUnavailable';
    this.platform = platform;
    this.remedy = remedy;
  }
}

/**
 * Convert a backend-agnostic landmark list into the API wire format.
 * Always returns exactly 33 entries so the server's validation passes even
 * when a backend reports fewer points.
 */
export function toWireFormat(landmarks) {
  const out = [];
  for (let i = 0; i < LANDMARK_NAMES.length; i += 1) {
    const lm = landmarks?.[i];
    if (!lm) {
      out.push({ x: 0, y: 0, z: 0, visibility: 0 });
      continue;
    }
    // Tasks Vision reports visibility/presence as optional and sometimes
    // null; treating a missing value as fully visible avoids zeroing out
    // every rule on backends that do not populate it.
    const vis = lm.visibility ?? lm.presence ?? 1;
    out.push({
      x: lm.x ?? 0,
      y: lm.y ?? 0,
      z: lm.z ?? 0,
      visibility: vis === null || vis === undefined ? 1 : vis,
    });
  }
  return out;
}

/** Landmarks keyed by name, for drawing and quick lookups. */
export function toNamedMap(landmarks) {
  const map = {};
  LANDMARK_NAMES.forEach((name, i) => {
    const lm = landmarks?.[i];
    if (lm) map[name] = { ...lm, visibility: lm.visibility ?? lm.presence ?? 1 };
  });
  return map;
}

// The web backend (MediaPipe Tasks Vision / WASM) lives in webPoseAdapter --
// split into `.web.js` + `.js` platform variants (see that file's header
// comment) so `@mediapipe/tasks-vision` is resolved at bundle time rather
// than through a runtime dynamic import.

// ---------------------------------------------------------------------------
// Native backend: integration seam
// ---------------------------------------------------------------------------

class NativePoseAdapter {
  /**
   * Real-time pose detection on iOS/Android requires a native frame
   * processor, which cannot run in Expo Go. To enable it:
   *
   *   1. `npx expo prebuild` to create a custom dev build.
   *   2. Add `react-native-vision-camera` and a MediaPipe pose frame-processor
   *      plugin.
   *   3. Have the plugin return the 33 landmarks as `{x, y, z, visibility}`
   *      with x/y normalised to [0, 1].
   *   4. Assign that function to `PoseDetector.nativeFrameProcessor`.
   *
   * Everything downstream -- assessment, feedback, scoring, the overlay --
   * already consumes this exact shape, so no other file changes.
   */
  constructor(frameProcessor) {
    this.frameProcessor = frameProcessor;
  }

  async load() {
    if (!this.frameProcessor) {
      throw new PoseDetectorUnavailable(
        'Live pose detection is not available in Expo Go on this device.',
        {
          platform: Platform.OS,
          remedy:
            'Run the app in a browser with `npm run web` for the full camera pipeline, ' +
            'or create a dev build with a MediaPipe frame processor. See docs/POSE_PIPELINE.md.',
        },
      );
    }
  }

  detect(frame) {
    return this.frameProcessor ? this.frameProcessor(frame) : null;
  }

  close() {}
}

// ---------------------------------------------------------------------------
// Facade
// ---------------------------------------------------------------------------

export class PoseDetector {
  /** Set this from a native frame-processor plugin to enable native capture. */
  static nativeFrameProcessor = null;

  constructor() {
    this.adapter =
      Platform.OS === 'web'
        ? new WebPoseAdapter()
        : new NativePoseAdapter(PoseDetector.nativeFrameProcessor);
    this.ready = false;
  }

  static get isSupported() {
    return Platform.OS === 'web' || Boolean(PoseDetector.nativeFrameProcessor);
  }

  async load() {
    await this.adapter.load();
    this.ready = true;
  }

  /**
   * Detect landmarks in one frame.
   * @returns {Array|null} raw landmark array, or null when no body is found.
   */
  detect(source, timestampMs) {
    if (!this.ready) return null;
    try {
      return this.adapter.detect(source, timestampMs);
    } catch (err) {
      // A single dropped frame must never take down the session; the next
      // frame is a few milliseconds away.
      console.warn('Pose detection frame failed:', err?.message ?? err);
      return null;
    }
  }

  close() {
    this.adapter.close();
    this.ready = false;
  }
}

export default PoseDetector;
