/**
 * Web pose-detection backend: MediaPipe Tasks Vision (WASM).
 *
 * Split into its own `.web.js` file with a static top-level import so Metro's
 * platform resolver excludes this module entirely from native bundles --
 * `@mediapipe/tasks-vision` never enters their module graph. This replaces
 * an earlier `await import('@mediapipe/tasks-vision')` inside poseDetector.js:
 * that dynamic import relied on Metro's async-chunk loading, which the Expo
 * web *dev server* does not reliably support (it worked fine in a static
 * `expo export` build, but broke in `expo start --web` with a "Requiring
 * unknown module" error after the module's async chunk ID drifted). A
 * `.web.js`/`.js` platform split resolves per-platform at bundle time, so
 * there is no runtime chunk loading involved at all.
 */

import * as vision from '@mediapipe/tasks-vision';

const MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task';

// Must match the @mediapipe/tasks-vision version pinned in package.json: the
// JS wrapper and the WASM binary are versioned together, and a mismatch fails
// at load time rather than degrading gracefully.
const WASM_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm';

export class WebPoseAdapter {
  constructor() {
    this.landmarker = null;
    this.lastTimestamp = -1;
  }

  async load() {
    if (this.landmarker) return;

    const fileset = await vision.FilesetResolver.forVisionTasks(WASM_URL);

    this.landmarker = await vision.PoseLandmarker.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: MODEL_URL, delegate: 'GPU' },
      runningMode: 'VIDEO',
      numPoses: 1,
      minPoseDetectionConfidence: 0.5,
      minPosePresenceConfidence: 0.5,
      minTrackingConfidence: 0.5,
    });
  }

  /**
   * @param {HTMLVideoElement} video
   * @param {number} timestampMs
   */
  detect(video, timestampMs) {
    if (!this.landmarker || !video || video.readyState < 2) return null;

    // Tasks Vision requires strictly increasing timestamps and throws on a
    // repeat, which happens whenever the render loop outruns the camera.
    let ts = Math.round(timestampMs);
    if (ts <= this.lastTimestamp) ts = this.lastTimestamp + 1;
    this.lastTimestamp = ts;

    const result = this.landmarker.detectForVideo(video, ts);
    const first = result?.landmarks?.[0];
    if (!first || !first.length) return null;
    return first;
  }

  close() {
    this.landmarker?.close?.();
    this.landmarker = null;
  }
}

export default WebPoseAdapter;
