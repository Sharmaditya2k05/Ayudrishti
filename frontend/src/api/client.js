/**
 * Typed-ish REST client for the AyuDrishti backend.
 *
 * One place owns the base URL, the bearer token, JSON encoding and error
 * shaping, so screens deal in domain calls (`api.getRecommendations()`)
 * rather than fetch plumbing.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { Platform } from 'react-native';

const TOKEN_KEY = 'ayudrishti.token';

function defaultBaseUrl() {
  const fromEnv = process.env.EXPO_PUBLIC_API_BASE_URL;
  if (fromEnv) return fromEnv;

  const fromConfig = Constants.expoConfig?.extra?.apiBaseUrl;
  if (fromConfig && Platform.OS !== 'android') return fromConfig;

  // The Android emulator maps the host machine to 10.0.2.2; "localhost"
  // there refers to the emulator itself and silently fails to connect.
  if (Platform.OS === 'android') return 'http://10.0.2.2:8000';
  return 'http://localhost:8000';
}

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }

  /** Whether the caller should send the user back to the login screen. */
  get isAuthError() {
    return this.status === 401 || this.status === 403;
  }

  /** Whether onboarding must be completed before this call can succeed. */
  get needsOnboarding() {
    return this.status === 428;
  }
}

class ApiClient {
  constructor() {
    this.baseUrl = defaultBaseUrl();
    this.token = null;
    this.onAuthError = null;
  }

  setBaseUrl(url) {
    this.baseUrl = url.replace(/\/$/, '');
  }

  async loadToken() {
    this.token = await AsyncStorage.getItem(TOKEN_KEY);
    return this.token;
  }

  async setToken(token) {
    this.token = token;
    if (token) await AsyncStorage.setItem(TOKEN_KEY, token);
    else await AsyncStorage.removeItem(TOKEN_KEY);
  }

  async request(path, { method = 'GET', body, form, signal } = {}) {
    const headers = { Accept: 'application/json' };
    if (this.token) headers.Authorization = `Bearer ${this.token}`;

    let payload;
    if (form) {
      headers['Content-Type'] = 'application/x-www-form-urlencoded';
      payload = new URLSearchParams(form).toString();
    } else if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
      payload = JSON.stringify(body);
    }

    let response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, {
        method,
        headers,
        body: payload,
        signal,
      });
    } catch (err) {
      if (err.name === 'AbortError') throw err;
      throw new ApiError(
        `Cannot reach the AyuDrishti server at ${this.baseUrl}. Check that the backend is running.`,
        0,
        null,
      );
    }

    if (response.status === 204) return null;

    let data = null;
    const text = await response.text();
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = { detail: text };
      }
    }

    if (!response.ok) {
      const detail = data?.detail;
      const message =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail.map((d) => d.msg || String(d)).join('; ')
            : `Request failed (${response.status})`;
      const error = new ApiError(message, response.status, detail);
      if (error.isAuthError && this.onAuthError) this.onAuthError(error);
      throw error;
    }

    return data;
  }

  // ---- auth ----------------------------------------------------------

  register(payload) {
    return this.request('/auth/register', { method: 'POST', body: payload });
  }

  /** The backend uses the OAuth2 password form; email goes in `username`. */
  login(email, password) {
    return this.request('/auth/login', {
      method: 'POST',
      form: { username: email, password },
    });
  }

  // ---- profile -------------------------------------------------------

  getMe() {
    return this.request('/users/me');
  }

  updateMe(payload) {
    return this.request('/users/me', { method: 'PUT', body: payload });
  }

  // ---- asanas --------------------------------------------------------

  listAsanas(params = {}) {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null),
    ).toString();
    return this.request(`/asanas${query ? `?${query}` : ''}`);
  }

  getAsana(asanaId) {
    return this.request(`/asanas/${asanaId}`);
  }

  // ---- recommendations -----------------------------------------------

  getRecommendations(durationMinutes) {
    const query = durationMinutes ? `?duration_minutes=${durationMinutes}` : '';
    return this.request(`/recommendations${query}`);
  }

  generateRecommendations(durationMinutes) {
    return this.request('/recommendations/generate', {
      method: 'POST',
      body: { duration_minutes: durationMinutes ?? null, persist: true },
    });
  }

  // ---- sessions ------------------------------------------------------

  startSession(plannedAsanas = [], notes = '') {
    return this.request('/sessions', {
      method: 'POST',
      body: { planned_asanas: plannedAsanas, notes },
    });
  }

  listSessions(limit = 50) {
    return this.request(`/sessions?limit=${limit}`);
  }

  getSession(sessionId) {
    return this.request(`/sessions/${sessionId}`);
  }

  completeSession(sessionId, { assessments, durationSeconds, notes = '' }) {
    return this.request(`/sessions/${sessionId}/complete`, {
      method: 'POST',
      body: {
        assessments,
        duration_seconds: durationSeconds,
        notes,
      },
    });
  }

  // ---- assessment ----------------------------------------------------

  /**
   * Score one frame.
   *
   * `landmarks` is the 33-point MediaPipe array produced on-device. Only
   * coordinates are sent -- the image itself never leaves the device.
   */
  assess({ landmarks, asanaId, sessionId, timestamp, leadSide, expectedAsanas, signal }) {
    return this.request('/assessment', {
      method: 'POST',
      signal,
      body: {
        landmarks,
        asana_id: asanaId ?? null,
        session_id: sessionId ?? null,
        timestamp: timestamp ?? 0,
        lead_side: leadSide ?? null,
        expected_asanas: expectedAsanas ?? [],
        include_rules: false,
      },
    });
  }

  recognise({ landmarks, timestamp, expectedAsanas }) {
    return this.request('/assessment/pose', {
      method: 'POST',
      body: {
        landmarks,
        timestamp: timestamp ?? 0,
        expected_asanas: expectedAsanas ?? [],
      },
    });
  }

  resetLiveState(sessionId) {
    const query = sessionId ? `?session_id=${sessionId}` : '';
    return this.request(`/assessment/reset${query}`, { method: 'POST' });
  }

  // ---- progress ------------------------------------------------------

  getProgress() {
    return this.request('/progress');
  }

  getAsanaProgress(asanaId) {
    return this.request(`/progress/${asanaId}`);
  }

  // ---- wearables (optional) ------------------------------------------

  getWearableStatus() {
    return this.request('/wearables/status');
  }

  connectWearable(deviceId, deviceName = '', firmware = '') {
    return this.request('/wearables/connect', {
      method: 'POST',
      body: { device_id: deviceId, device_name: deviceName, firmware },
    });
  }

  sendWearableData(samples, { sessionId, deviceId } = {}) {
    return this.request('/wearables/data', {
      method: 'POST',
      body: { samples, session_id: sessionId ?? null, device_id: deviceId ?? null },
    });
  }

  health() {
    return this.request('/health');
  }

  // ---- yoga assistant (RAG over Groq) ---------------------------------

  getAssistantStatus() {
    return this.request('/assistant/status');
  }

  askAssistant(question) {
    return this.request('/assistant/ask', { method: 'POST', body: { question } });
  }
}

export const api = new ApiClient();
export default api;
