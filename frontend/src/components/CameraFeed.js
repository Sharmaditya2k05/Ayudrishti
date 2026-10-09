/**
 * Camera preview, with the frame source exposed for pose detection.
 *
 * On web the stream comes from `getUserMedia` into a plain `<video>`, which
 * is exactly what MediaPipe Tasks Vision consumes -- no copy, no canvas
 * round-trip. On native, `expo-camera` renders the preview and the frame
 * source is supplied by a native frame processor (see poseDetector.js).
 *
 * The preview is mirrored so the practitioner sees themselves as in a
 * mirror; overlays compensate for that flip rather than the detector, since
 * flipping the input would swap left and right in every landmark name.
 */

import React, { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { Platform, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '../theme/theme';

const CameraFeed = forwardRef(function CameraFeed(
  { onReady, onError, facing = 'front', style, mirrored = true },
  ref,
) {
  const [status, setStatus] = useState('starting');
  const [message, setMessage] = useState('');
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const nativeRef = useRef(null);

  useImperativeHandle(ref, () => ({
    /** The object the pose detector reads frames from. */
    getSource: () => (Platform.OS === 'web' ? videoRef.current : nativeRef.current),
    getDimensions: () => {
      if (Platform.OS === 'web' && videoRef.current) {
        return {
          width: videoRef.current.videoWidth,
          height: videoRef.current.videoHeight,
        };
      }
      return { width: 0, height: 0 };
    },
  }));

  useEffect(() => {
    if (Platform.OS !== 'web') return undefined;

    let cancelled = false;

    (async () => {
      try {
        if (!navigator?.mediaDevices?.getUserMedia) {
          throw new Error(
            'This browser does not expose a camera API. Use a recent Chrome, Edge or Safari over HTTPS or localhost.',
          );
        }
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: facing === 'front' ? 'user' : 'environment',
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        const video = videoRef.current;
        if (video) {
          video.srcObject = stream;
          video.muted = true;
          video.playsInline = true;
          await video.play();
          setStatus('ready');
          onReady?.();
        }
      } catch (err) {
        if (cancelled) return;
        setStatus('error');
        const text =
          err?.name === 'NotAllowedError'
            ? 'Camera access was denied. Allow camera permission and reload to practise.'
            : err?.message || 'Could not start the camera.';
        setMessage(text);
        onError?.(new Error(text));
      }
    })();

    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    };
    // facing is intentionally the only dependency: re-running on callback
    // identity changes would tear down and restart the camera every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facing]);

  if (Platform.OS === 'web') {
    return (
      <View style={[styles.container, style]}>
        {React.createElement('video', {
          ref: videoRef,
          autoPlay: true,
          muted: true,
          playsInline: true,
          style: {
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            transform: mirrored ? 'scaleX(-1)' : 'none',
            backgroundColor: colors.bg,
          },
        })}
        {status !== 'ready' ? (
          <View style={styles.overlayMessage}>
            <Text style={typography.body}>
              {status === 'error' ? message : 'Starting camera...'}
            </Text>
          </View>
        ) : null}
      </View>
    );
  }

  return <NativeCamera ref={nativeRef} facing={facing} style={style} onError={onError} />;
});

const NativeCamera = forwardRef(function NativeCamera({ facing, style, onError }, ref) {
  const [permission, setPermission] = useState(null);
  const [CameraView, setCameraView] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mod = await import('expo-camera');
        const { requestCameraPermissionsAsync } = mod.Camera ?? mod;
        const result = await (mod.Camera?.requestCameraPermissionsAsync?.() ??
          requestCameraPermissionsAsync?.());
        if (cancelled) return;
        setPermission(result?.status === 'granted');
        setCameraView(() => mod.CameraView ?? mod.Camera);
      } catch (err) {
        if (!cancelled) onError?.(err);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [onError]);

  if (permission === false) {
    return (
      <View style={[styles.container, styles.permission, style]}>
        <Text style={typography.heading}>Camera permission needed</Text>
        <Text style={[typography.bodyMuted, styles.permissionText]}>
          AyuDrishti needs the camera to see your posture. Video stays on your device --
          only posture measurements are sent to the server.
        </Text>
      </View>
    );
  }

  if (!CameraView) {
    return (
      <View style={[styles.container, styles.permission, style]}>
        <Text style={typography.bodyMuted}>Starting camera...</Text>
      </View>
    );
  }

  return (
    <View style={[styles.container, style]}>
      <CameraView ref={ref} style={StyleSheet.absoluteFill} facing={facing} />
    </View>
  );
});

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000',
    borderRadius: radius.md,
    overflow: 'hidden',
  },
  overlayMessage: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(18,16,14,0.86)',
    padding: spacing.lg,
  },
  permission: { alignItems: 'center', justifyContent: 'center', padding: spacing.lg },
  permissionText: { textAlign: 'center', marginTop: spacing.sm },
});

export default CameraFeed;
