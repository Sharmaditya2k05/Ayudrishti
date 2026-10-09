/**
 * Native-platform fallback for `WebPoseAdapter`.
 *
 * Metro resolves `webPoseAdapter.web.js` for the web bundle and this plain
 * file for iOS/Android, so `@mediapipe/tasks-vision` (browser-only) never
 * enters the native module graph. `PoseDetector` never actually constructs
 * this class on native (see poseDetector.js), so these methods existing only
 * to fail loudly is intentional -- it should never run.
 */

export class WebPoseAdapter {
  async load() {
    throw new Error('WebPoseAdapter is web-only and must not be used on native.');
  }

  detect() {
    return null;
  }

  close() {}
}

export default WebPoseAdapter;
