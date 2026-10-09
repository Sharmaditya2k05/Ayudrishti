/**
 * Web Bluetooth bridge for the AyuDrishti wearable band.
 *
 * This is the piece that closes the hardware→app path the firmware was always
 * written for: it connects to the ESP32 band over BLE, subscribes to its
 * telemetry characteristic, decodes each JSON packet, and forwards the
 * readings to the backend's /wearables/data endpoint. Live values are also
 * surfaced to the UI as they arrive.
 *
 * Web Bluetooth is available in Chrome/Edge on desktop and Android over HTTPS
 * (or localhost). It is NOT available in iOS Safari or Firefox -- `supported`
 * is false there and the app carries on exactly as before, since the band is
 * optional. On native (React Native) `navigator.bluetooth` is undefined, so
 * this reports unsupported too; a native build would swap in a plugin such as
 * react-native-ble-plx behind the same hook.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import api from '../api/client';

// Must match the firmware's BLE contract (wearable/esp32/ayudrishti_wearable.ino).
export const WEARABLE_SERVICE_UUID = '6e400001-b5a3-f393-e0a9-e50e24dcca9e';
export const WEARABLE_TELEMETRY_UUID = '6e400003-b5a3-f393-e0a9-e50e24dcca9e';
export const WEARABLE_COMMAND_UUID = '6e400002-b5a3-f393-e0a9-e50e24dcca9e';

export const wearableSupported =
  typeof navigator !== 'undefined' && !!navigator.bluetooth;

// Flush buffered samples to the backend at least this often, so a session
// carries physiological context even if the user never opens the vitals card.
const FLUSH_INTERVAL_MS = 5000;

// The firmware emits -1 for a value it can't read (finger off the sensor, no
// MPU, etc.). Map those to null, and clamp into the backend's accepted range
// so a noisy reading can't 422 the whole batch.
function clampOrNull(value, min, max) {
  if (value == null || value < 0) return null;
  if (value < min || value > max) return null;
  return value;
}

// Firmware packet: {"hr","spo2","gsr","motion","t","ok"} -> backend WearableSample.
function packetToSample(pkt) {
  return {
    heart_rate: clampOrNull(pkt.hr, 20, 250),
    spo2: clampOrNull(pkt.spo2, 50, 100),
    gsr: clampOrNull(pkt.gsr, 0, 100),
    motion: clampOrNull(pkt.motion, 0, 64),
    recorded_at: new Date().toISOString(),
  };
}

export function useWearable({ sessionId = null } = {}) {
  const [status, setStatus] = useState('idle'); // idle | connecting | connected | error
  const [reading, setReading] = useState(null); // latest decoded packet
  const [error, setError] = useState(null);

  const deviceRef = useRef(null);
  const charRef = useRef(null);
  const bufferRef = useRef([]);
  const sessionRef = useRef(sessionId);
  const deviceIdRef = useRef(null);

  useEffect(() => {
    sessionRef.current = sessionId;
  }, [sessionId]);

  const flush = useCallback(async () => {
    const batch = bufferRef.current;
    if (!batch.length) return;
    bufferRef.current = [];
    try {
      await api.sendWearableData(batch, {
        sessionId: sessionRef.current,
        deviceId: deviceIdRef.current,
      });
    } catch (err) {
      // Don't crash the stream on a transient network error; drop the batch
      // and keep going -- physiological context is best-effort, not critical.
      // eslint-disable-next-line no-console
      console.warn('[wearable] failed to forward samples:', err?.message);
    }
  }, []);

  const handleValue = useCallback((event) => {
    let pkt;
    try {
      const text = new TextDecoder().decode(event.target.value);
      pkt = JSON.parse(text);
    } catch {
      return; // ignore a malformed packet rather than tearing down the stream
    }
    setReading(pkt);
    // ok === false means the sensor had no skin contact -- show it live, but
    // don't persist noise as a physiological event.
    if (pkt.ok !== false) {
      bufferRef.current.push(packetToSample(pkt));
    }
  }, []);

  const disconnect = useCallback(async () => {
    try {
      await flush();
      if (charRef.current) {
        charRef.current.removeEventListener('characteristicvaluechanged', handleValue);
      }
      if (deviceRef.current?.gatt?.connected) {
        deviceRef.current.gatt.disconnect();
      }
    } catch {
      /* already gone */
    }
    charRef.current = null;
    deviceRef.current = null;
    setStatus('idle');
    setReading(null);
  }, [flush, handleValue]);

  const connect = useCallback(async () => {
    if (!wearableSupported) {
      setError(new Error('Bluetooth is not available in this browser. Use Chrome or Edge on desktop or Android.'));
      return;
    }
    setError(null);
    setStatus('connecting');
    try {
      const device = await navigator.bluetooth.requestDevice({
        filters: [{ services: [WEARABLE_SERVICE_UUID] }],
        optionalServices: [WEARABLE_SERVICE_UUID],
      });
      deviceRef.current = device;
      deviceIdRef.current = device.id || 'YOGA_BAND_01';

      device.addEventListener('gattserverdisconnected', () => {
        setStatus('idle');
        setReading(null);
      });

      const server = await device.gatt.connect();
      const service = await server.getPrimaryService(WEARABLE_SERVICE_UUID);
      const telemetry = await service.getCharacteristic(WEARABLE_TELEMETRY_UUID);
      await telemetry.startNotifications();
      telemetry.addEventListener('characteristicvaluechanged', handleValue);
      charRef.current = telemetry;

      // Register the device with the backend so /wearables/status reflects it.
      try {
        await api.connectWearable(deviceIdRef.current, device.name || 'AyuDrishti Band', 'esp32-ble');
      } catch {
        /* status registration is non-critical */
      }

      setStatus('connected');
    } catch (err) {
      // User cancelling the chooser throws NotFoundError -- treat as a benign
      // no-op rather than an error state.
      if (err?.name === 'NotFoundError') {
        setStatus('idle');
        return;
      }
      setError(err);
      setStatus('error');
    }
  }, [handleValue]);

  // Periodic flush while connected.
  useEffect(() => {
    if (status !== 'connected') return undefined;
    const id = setInterval(flush, FLUSH_INTERVAL_MS);
    return () => clearInterval(id);
  }, [status, flush]);

  // Tear down on unmount.
  useEffect(() => () => { disconnect(); }, [disconnect]);

  return {
    supported: wearableSupported,
    status,
    reading,
    error,
    connect,
    disconnect,
    connected: status === 'connected',
  };
}
