/**
 * Text-to-speech, via the browser's native SpeechSynthesis API.
 *
 * Web only -- there is no cross-platform TTS without a native module, and
 * the whole camera + detection pipeline is already web-only (see
 * ../pose/poseDetector.js and its header comment for why). `speechSupported`
 * is exported so callers can hide voice-only affordances gracefully instead
 * of throwing on unsupported platforms/browsers.
 */

import { Platform } from 'react-native';

export const speechSupported =
  Platform.OS === 'web' && typeof window !== 'undefined' && 'speechSynthesis' in window;

/** @param {string} text @param {{lang?: string, rate?: number}} [options] */
export function speak(text, { lang = 'en-US', rate = 1 } = {}) {
  if (!speechSupported || !text) return;
  // Cancel first: a new correction should replace whatever was mid-sentence,
  // never queue behind it -- by the time it would play, it would describe a
  // posture the practitioner has already moved past.
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = lang;
  utterance.rate = rate;
  window.speechSynthesis.speak(utterance);
}

export function stopSpeaking() {
  if (!speechSupported) return;
  window.speechSynthesis.cancel();
}
