/**
 * The live practice screen -- Detect, Assess and Correct in one loop.
 *
 * The flow is deliberately turn-based, not continuously auto-advancing:
 * the practitioner says "ready" (or taps the button), holds the pose for a
 * fixed check window, then the app speaks its feedback and shows the score.
 * From there it's "retry" (redo the same pose, looping as many times as
 * wanted) or "next" (record the result and move on) -- by voice or button.
 *
 * Pose detection runs per animation frame (cheap, local, WASM/GPU) only
 * during the check window; assessment is a network round-trip, so it is
 * throttled and never allowed to queue -- if a request is still in flight
 * the frame is skipped rather than stacking latency behind the
 * practitioner's movements.
 *
 * The score shown at the end of a check is the *best* frame achieved during
 * it, because a hold is judged by what the practitioner reached, not by the
 * wobble on the way in.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import api from '../api/client';
import CameraFeed from '../components/CameraFeed';
import PoseOverlay from '../components/PoseOverlay';
import {
  AlignmentIndicator,
  Badge,
  Button,
  Card,
  ErrorNotice,
  ScoreRing,
} from '../components/common';
import { useLanguage } from '../i18n/LanguageContext';
import PoseDetector, { toNamedMap, toWireFormat } from '../pose/poseDetector';
import { colors, fonts, radius, scoreColor, spacing, typography } from '../theme/theme';
import { speak, speechSupported } from '../voice/speech';
import { useVoiceCommands, voiceCommandsSupported } from '../voice/useVoiceCommands';

/** Milliseconds between assessment requests. ~4/s keeps feedback responsive. */
const ASSESS_INTERVAL_MS = 260;

/** Below this width there's no room for camera and panel side by side. */
const WIDE_BREAKPOINT = 900;

const VOICE_COMMANDS = {
  ready: ['ready', "i'm ready", 'i am ready', 'तैयार', 'रेडी'],
  retry: ['retry', 'try again', 'again', 'दोबारा', 'फिर से', 'रीट्राई'],
  next: ['next', 'next pose', 'move on', 'अगला', 'नेक्स्ट'],
};

function formatClock(seconds) {
  const s = Math.max(0, Math.round(seconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`;
}

/** The correction/praise text plus score, phrased for speech rather than reading. */
function speakableFeedback(best) {
  if (!best?.detected) {
    return "I couldn't get a clear view of your pose. Adjust your camera and try again.";
  }
  const messages = best.feedback?.messages ?? [];
  const text =
    messages.find((m) => m.kind === 'correction')?.text ??
    messages[0]?.text ??
    'Nicely held.';
  const scoreText = best.overall != null ? `Score ${Math.round(best.overall)} percent. ` : '';
  return scoreText + text;
}

export default function PracticeScreen({ route, navigation }) {
  const plan = route.params?.plan;
  const { width } = useWindowDimensions();
  const isWide = width >= WIDE_BREAKPOINT;
  const { language } = useLanguage();

  const items = useMemo(() => plan?.items ?? [], [plan]);
  const expectedAsanas = useMemo(
    () => [...new Set(items.map((i) => i.asana_id))],
    [items],
  );

  const [session, setSession] = useState(null);
  const [index, setIndex] = useState(0);
  // loading | ready | holding | reviewing | finishing
  //   ready:     waiting for "I'm in position" / "ready"
  //   holding:   actively checking the pose for current.duration_seconds
  //   reviewing: check finished -- feedback spoken, score shown, waiting for
  //              "retry" (redo this pose) or "next" (record and move on)
  const [phase, setPhase] = useState('loading');
  const [assessment, setAssessment] = useState(null);
  const [reviewResult, setReviewResult] = useState(null);
  const [landmarks, setLandmarks] = useState(null);
  const [error, setError] = useState(null);
  // Two different failure sources -- getUserMedia denial vs. the MediaPipe
  // model failing to load -- used to share one state var, which meant a
  // camera error silently hid a detector error underneath it (or vice
  // versa) with no way to tell which one had actually happened.
  const [cameraError, setCameraError] = useState(null);
  const [detectorError, setDetectorError] = useState(null);
  const [detectorReady, setDetectorReady] = useState(false);
  const [holdElapsed, setHoldElapsed] = useState(0);
  const [previewSize, setPreviewSize] = useState({ width: 0, height: 0 });
  // Cues/benefits aren't part of the recommendation payload (that only
  // carries what scoring needs) -- fetched per pose from the asana detail
  // endpoint, which is the one place that data actually lives.
  const [poseDetail, setPoseDetail] = useState(null);

  const cameraRef = useRef(null);
  const detectorRef = useRef(null);
  const rafRef = useRef(null);
  const lastAssessRef = useRef(0);
  const inFlightRef = useRef(false);
  const startedAtRef = useRef(Date.now());
  const holdStartRef = useRef(null);
  const phaseRef = useRef(phase);
  phaseRef.current = phase;

  // Per-pose accumulator: the best frame plus everything needed to record it.
  const bestRef = useRef(null);
  const resultsRef = useRef([]);
  const attemptCountRef = useRef(0);

  const current = items[index] ?? null;
  const recognitionLang = language === 'hi' ? 'hi-IN' : 'en-US';

  // ---- session bootstrap ------------------------------------------------

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const created = await api.startSession(expectedAsanas);
        if (!cancelled) {
          setSession(created);
          setPhase('ready');
        }
      } catch (err) {
        if (!cancelled) setError(err);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [expectedAsanas]);

  // ---- detector ---------------------------------------------------------

  useEffect(() => {
    const detector = new PoseDetector();
    detectorRef.current = detector;
    detector
      .load()
      .then(() => setDetectorReady(true))
      .catch((err) => {
        // Logged in full because the on-screen message is deliberately
        // short; the stack is what actually diagnoses a load failure.
        console.error('PoseDetector failed to load:', err);
        setDetectorError(err);
      });
    return () => {
      detector.close();
      detectorRef.current = null;
    };
  }, []);

  // ---- per-pose detail (cues / benefits) ---------------------------------

  useEffect(() => {
    if (!current?.asana_id) {
      setPoseDetail(null);
      return undefined;
    }
    let cancelled = false;
    setPoseDetail(null);
    api
      .getAsana(current.asana_id)
      .then((detail) => {
        if (!cancelled) setPoseDetail(detail);
      })
      .catch(() => {
        /* non-fatal: the session works fine without cues/benefits */
      });
    return () => {
      cancelled = true;
    };
  }, [current?.asana_id]);

  // ---- detection + assessment loop --------------------------------------

  const tick = useCallback(() => {
    rafRef.current = requestAnimationFrame(tick);

    const detector = detectorRef.current;
    const source = cameraRef.current?.getSource?.();
    if (!detector?.ready || !source || !current) return;

    const now = performance.now();
    const raw = detector.detect(source, now);
    if (!raw) return;

    setLandmarks(toNamedMap(raw));

    if (now - lastAssessRef.current < ASSESS_INTERVAL_MS) return;
    // Never queue requests: a backlog would make corrections describe a
    // posture the practitioner has already moved on from.
    if (inFlightRef.current) return;

    lastAssessRef.current = now;
    inFlightRef.current = true;

    api
      .assess({
        landmarks: toWireFormat(raw),
        asanaId: current.asana_id,
        sessionId: session?.id,
        timestamp: (Date.now() - startedAtRef.current) / 1000,
        expectedAsanas,
      })
      .then((result) => {
        setAssessment(result);
        if (result?.detected && result.reliable) {
          const best = bestRef.current;
          if (!best || result.overall > best.overall) bestRef.current = result;
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') setError(err);
      })
      .finally(() => {
        inFlightRef.current = false;
      });
  }, [current, session, expectedAsanas]);

  useEffect(() => {
    if (phase !== 'holding') return undefined;
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [phase, tick]);

  // ---- flow ---------------------------------------------------------------

  /** Speak the result and reveal the score/feedback panel. */
  const finishChecking = useCallback(() => {
    const best = bestRef.current;
    setReviewResult(best);
    speak(speakableFeedback(best), { lang: 'en-US' });
    setPhase('reviewing');
  }, []);

  // ---- hold timer -------------------------------------------------------

  useEffect(() => {
    if (phase !== 'holding' || !current) return undefined;
    holdStartRef.current = Date.now();
    setHoldElapsed(0);

    const id = setInterval(() => {
      const elapsed = (Date.now() - holdStartRef.current) / 1000;
      setHoldElapsed(elapsed);
      if (elapsed >= current.duration_seconds) finishChecking();
    }, 250);

    return () => clearInterval(id);
  }, [phase, index, current, finishChecking]);

  /** Used both for the first attempt at a pose and for every "retry". */
  const startChecking = useCallback(async () => {
    bestRef.current = null;
    setAssessment(null);
    setReviewResult(null);
    attemptCountRef.current += 1;
    // Clear the previous attempt's feedback cooldowns and safety timers so
    // the first correction of this attempt is not suppressed.
    try {
      await api.resetLiveState(session?.id);
    } catch {
      /* non-fatal: stale throttling is a minor annoyance, not a failure */
    }
    setPhase('holding');
  }, [session]);

  const finish = useCallback(async () => {
    setPhase('finishing');
    if (rafRef.current) cancelAnimationFrame(rafRef.current);

    try {
      const summary = await api.completeSession(session.id, {
        assessments: resultsRef.current,
        durationSeconds: Math.round((Date.now() - startedAtRef.current) / 1000),
      });
      navigation.replace('SessionSummary', { summary });
    } catch (err) {
      setError(err);
      setPhase('ready');
    }
  }, [session, navigation]);

  /** Record the best attempt (if any) and move to the next pose, or finish. */
  const nextPose = useCallback(() => {
    const item = items[index];
    const best = bestRef.current;

    if (item && best?.detected) {
      const metrics = {};
      (best.components ?? []).forEach((c) => {
        if (c.available_count > 0) metrics[c.component] = c.score;
      });
      const corrections = (best.feedback?.messages ?? [])
        .filter((m) => m.kind === 'correction')
        .map((m) => m.text);

      resultsRef.current.push({
        asana_id: item.asana_id,
        score: best.overall,
        confidence: best.confidence ?? 1,
        lead_side: best.lead_side ?? null,
        hold_seconds: Math.round(item.duration_seconds),
        alignment_metrics: metrics,
        corrections,
        deviation_count: best.deviation_count ?? 0,
      });
    }

    if (index + 1 < items.length) {
      setIndex((i) => i + 1);
      setPhase('ready');
      setAssessment(null);
      setReviewResult(null);
      bestRef.current = null;
      attemptCountRef.current = 0;
    } else {
      finish();
    }
  }, [index, items, finish]);

  const quit = () => {
    if (resultsRef.current.length) finish();
    else navigation.goBack();
  };

  // ---- voice commands -----------------------------------------------------

  const handleVoiceCommand = useCallback(
    (command) => {
      if (command === 'ready' && phaseRef.current === 'ready') startChecking();
      else if (command === 'retry' && phaseRef.current === 'reviewing') startChecking();
      else if (command === 'next' && phaseRef.current === 'reviewing') nextPose();
    },
    [startChecking, nextPose],
  );

  const { supported: voiceSupported, listening: voiceListening, micError: voiceMicError } =
    useVoiceCommands({
      enabled: phase === 'ready' || phase === 'reviewing',
      lang: recognitionLang,
      commands: VOICE_COMMANDS,
      onCommand: handleVoiceCommand,
    });

  // ---- render -----------------------------------------------------------

  if (!plan || items.length === 0) {
    return (
      <View style={styles.centered}>
        <Text style={typography.heading}>No session to practise</Text>
        <Button title="Go back" variant="ghost" onPress={() => navigation.goBack()} />
      </View>
    );
  }

  const feedback = assessment?.feedback;
  const messages = feedback?.messages ?? [];
  const primary = messages.find((m) => m.kind === 'correction') ?? messages[0];
  const alerts = assessment?.safety_alerts ?? [];
  const safety = alerts[0];
  const score = assessment?.overall;
  const holdRatio = current ? Math.min(holdElapsed / current.duration_seconds, 1) : 0;
  const reviewFeedback = reviewResult?.feedback;
  const reviewMessages = reviewFeedback?.messages ?? [];
  const reviewPrimary = reviewMessages.find((m) => m.kind === 'correction') ?? reviewMessages[0];
  const correctionCount = reviewMessages.filter((m) => m.kind === 'correction').length;
  const sessionElapsed = (Date.now() - startedAtRef.current) / 1000;

  const cameraBox = (
    <View
      style={[styles.cameraWrap, isWide && styles.cameraWrapWide]}
      onLayout={(e) => setPreviewSize(e.nativeEvent.layout)}
    >
      <CameraFeed ref={cameraRef} onError={setCameraError} />
      {phase === 'holding' ? (
        <PoseOverlay
          landmarks={landmarks}
          highlight={feedback?.highlight_landmarks ?? []}
          width={previewSize.width}
          height={previewSize.height}
          mirrored
        />
      ) : null}

      <View style={styles.hud} pointerEvents="none">
        <View style={styles.hudTop}>
          <View style={styles.hudPose}>
            <Text style={styles.hudPoseName}>{current?.asana_name}</Text>
            <Text style={styles.hudProgress}>
              Pose {index + 1} of {items.length}
              {current?.sides > 1 ? ' · both sides' : ''}
            </Text>
          </View>
          {phase === 'holding' && score != null ? (
            <View style={[styles.hudScore, { borderColor: scoreColor(score) }]}>
              <Text style={[styles.hudScoreValue, { color: scoreColor(score) }]}>
                {Math.round(score)}
              </Text>
            </View>
          ) : null}
        </View>

        {phase === 'holding' ? (
          <View style={styles.holdBar}>
            <View style={[styles.holdFill, { width: `${holdRatio * 100}%` }]} />
          </View>
        ) : null}
      </View>

      {safety ? (
        <View style={[styles.safety, safety.severity === 'rest' && styles.safetyRest]}>
          <Text style={styles.safetyText}>{safety.message}</Text>
        </View>
      ) : null}

      {primary && phase === 'holding' ? (
        <View
          style={[
            styles.coach,
            primary.kind === 'praise' && styles.coachPraise,
            primary.kind === 'info' && styles.coachInfo,
          ]}
        >
          <Text style={styles.coachText}>{primary.text}</Text>
        </View>
      ) : null}
    </View>
  );

  const breakdown = phase === 'reviewing' ? (
    <AlignmentBreakdown
      score={reviewResult?.overall}
      grade={reviewResult?.grade}
      indicators={reviewFeedback?.indicators}
      primary={reviewPrimary}
      detected={reviewResult?.detected}
      wide={isWide}
    />
  ) : null;

  return (
    <View style={styles.screen}>
      <View style={[styles.body, isWide && styles.bodyWide]}>
        {/* Row-reverse (not reordered JSX) so the camera stays the second
            child -- on a wide screen the reference photo / info panel reads
            on the left and the live camera on the right. The alignment
            breakdown sits directly under the camera on a wide screen, since
            there is room; on a phone it falls back into the scrolling panel
            below instead. */}
        {isWide ? (
          <View style={styles.cameraColumn}>
            {cameraBox}
            {breakdown}
          </View>
        ) : (
          cameraBox
        )}

        <ScrollView
          style={[styles.panel, isWide && styles.panelWide]}
          contentContainerStyle={styles.panelContent}
        >
          <ErrorNotice error={error} />
          {cameraError ? (
            <Card style={styles.warnCard}>
              <View style={styles.warnHeader}>
                <MaterialCommunityIcons name="camera-off-outline" size={18} color={colors.warn} />
                <Text style={typography.heading}>Camera unavailable</Text>
              </View>
              <Text style={[typography.bodyMuted, { marginTop: spacing.xs }]}>
                {cameraError.message}
              </Text>
            </Card>
          ) : null}
          {detectorError ? (
            <Card style={styles.warnCard}>
              <View style={styles.warnHeader}>
                <MaterialCommunityIcons name="alert-circle-outline" size={18} color={colors.warn} />
                <Text style={typography.heading}>Live detection unavailable</Text>
              </View>
              <Text style={[typography.bodyMuted, { marginTop: spacing.xs }]}>
                {detectorError.message}
              </Text>
              {detectorError.remedy ? (
                <Text style={[typography.caption, { marginTop: spacing.sm }]}>
                  {detectorError.remedy}
                </Text>
              ) : null}
            </Card>
          ) : null}

          {phase === 'ready' ? (
            <>
              <Card style={styles.readyCard}>
                <View style={styles.readyHeader}>
                  <View style={{ flex: 1 }}>
                    <View style={styles.eyebrowRow}>
                      <MaterialCommunityIcons name="human-handsup" size={14} color={colors.primary} />
                      <Text style={typography.label}>Current pose</Text>
                      {detectorReady ? (
                        <View style={styles.readyDot}>
                          <View style={styles.readyDotInner} />
                          <Text style={styles.readyDotText}>Live</Text>
                        </View>
                      ) : null}
                    </View>
                    <Text style={[typography.title, { marginTop: 2 }]}>{current?.asana_name}</Text>
                    <Badge text={current?.difficulty ?? 'pose'} />
                  </View>
                  {current?.image_url ? (
                    <Image
                      source={{ uri: current.image_url }}
                      style={styles.readyThumb}
                      resizeMode="cover"
                      accessibilityLabel={`Reference photo of ${current.asana_name}`}
                    />
                  ) : null}
                </View>

                <Text style={[typography.bodyMuted, { marginTop: spacing.sm }]}>
                  {current?.reason}
                </Text>
                {current?.image_credit ? (
                  <Text style={styles.imageCredit}>{current.image_credit}</Text>
                ) : null}

                <View style={styles.holdRow}>
                  <MaterialCommunityIcons name="clock-outline" size={16} color={colors.textMuted} />
                  <Text style={styles.holdRowText}>
                    Hold for {current?.duration_seconds}s
                    {current?.sides > 1 ? ' on each side' : ''}
                  </Text>
                </View>
              </Card>

              {poseDetail?.benefits?.length ? (
                <Card>
                  <View style={styles.eyebrowRow}>
                    <MaterialCommunityIcons name="star-four-points-outline" size={14} color={colors.primary} />
                    <Text style={typography.label}>Pose benefits</Text>
                  </View>
                  <View style={{ marginTop: spacing.sm }}>
                    {poseDetail.benefits.map((b, i) => (
                      <View key={i} style={styles.benefitRow}>
                        <MaterialCommunityIcons
                          name="checkbox-marked-circle-outline"
                          size={16}
                          color={colors.primary}
                        />
                        <Text style={styles.benefitText}>{b}</Text>
                      </View>
                    ))}
                  </View>
                </Card>
              ) : null}

              {poseDetail?.cues?.length ? (
                <Card>
                  <View style={styles.eyebrowRow}>
                    <MaterialCommunityIcons name="format-list-numbered" size={14} color={colors.primary} />
                    <Text style={typography.label}>Instructions</Text>
                  </View>
                  <View style={{ marginTop: spacing.sm }}>
                    {poseDetail.cues.map((c, i) => (
                      <View key={i} style={styles.cueRow}>
                        <View style={styles.cueDot} />
                        <Text style={styles.cueText}>{c}</Text>
                      </View>
                    ))}
                  </View>
                </Card>
              ) : null}

              <Button title="I'm in position" onPress={startChecking} style={{ marginTop: spacing.md }} />
              <Button
                title="Skip this pose"
                variant="ghost"
                onPress={nextPose}
                style={{ marginTop: spacing.sm }}
              />
              <VoiceStatus
                supported={voiceSupported}
                listening={voiceListening}
                micError={voiceMicError}
                hint="Say “ready” to begin hands-free"
              />
            </>
          ) : null}

          {phase === 'holding' ? (
            <Card style={styles.checkingCard}>
              <ActivityIndicator color={colors.primary} />
              <Text style={[typography.heading, { marginTop: spacing.sm }]}>Checking your pose...</Text>
              <Text style={[typography.caption, { marginTop: spacing.xs }]}>
                {Math.max(0, Math.round((current?.duration_seconds ?? 0) - holdElapsed))}s remaining
              </Text>
            </Card>
          ) : null}

          {phase === 'reviewing' ? (
            <>
              {!isWide ? breakdown : null}
              {speechSupported ? (
                <View style={styles.spokenRow}>
                  <MaterialCommunityIcons name="volume-high" size={14} color={colors.textFaint} />
                  <Text style={styles.spokenText}>Feedback was read aloud</Text>
                </View>
              ) : null}
              <Button title="Next pose" onPress={nextPose} style={{ marginTop: spacing.md }} />
              <Button
                title="Retry this pose"
                variant="ghost"
                onPress={startChecking}
                style={{ marginTop: spacing.sm }}
              />
              <VoiceStatus
                supported={voiceSupported}
                listening={voiceListening}
                micError={voiceMicError}
                hint="Say “retry” or “next”"
              />
            </>
          ) : null}

          {phase === 'finishing' ? (
            <Card style={{ alignItems: 'center' }}>
              <ActivityIndicator color={colors.primary} />
              <Text style={[typography.bodyMuted, { marginTop: spacing.sm }]}>
                Saving your session...
              </Text>
            </Card>
          ) : null}
        </ScrollView>
      </View>

      {phase !== 'finishing' ? (
        <View style={styles.statusBar}>
          <View style={styles.statusStats}>
            <StatusStat icon="timer-outline" value={formatClock(sessionElapsed)} label="Time elapsed" />
            <StatusStat
              icon="repeat-variant"
              value={`${current?.round_number ?? 1}/${plan.rounds}`}
              label="Round"
            />
            <StatusStat icon="alert-circle-outline" value={String(correctionCount)} label="Corrections" />
          </View>
          <Pressable onPress={quit} style={styles.endButton}>
            <MaterialCommunityIcons name="flag-checkered" size={16} color={colors.bad} />
            <Text style={styles.endButtonText}>End session</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

function StatusStat({ icon, value, label }) {
  return (
    <View style={styles.statusStat}>
      <MaterialCommunityIcons name={icon} size={18} color={colors.primary} />
      <View>
        <Text style={styles.statusValue}>{value}</Text>
        <Text style={styles.statusLabel}>{label}</Text>
      </View>
    </View>
  );
}

/** Small "listening for a voice command" status line; silent if unsupported. */
function VoiceStatus({ supported, listening, micError, hint }) {
  if (!supported) return null;
  return (
    <View style={styles.voiceRow}>
      <MaterialCommunityIcons
        name={micError ? 'microphone-off' : 'microphone'}
        size={14}
        color={micError ? colors.textFaint : colors.primary}
      />
      <Text style={styles.voiceText}>
        {micError
          ? 'Microphone unavailable -- use the buttons instead'
          : listening
            ? hint
            : 'Starting voice commands...'}
      </Text>
    </View>
  );
}

/** The three-way alignment readout: score ring, per-component status, coaching. */
function AlignmentBreakdown({ score, grade, indicators, primary, detected, wide }) {
  return (
    <View style={[styles.breakdown, wide && styles.breakdownRow]}>
      <Card style={styles.breakdownCol}>
        <Text style={typography.label}>Alignment score</Text>
        <View style={styles.breakdownScoreRow}>
          <ScoreRing score={score} size={84} sublabel={grade ?? ''} />
        </View>
        {detected === false ? (
          <Text style={[typography.caption, { color: colors.warn, marginTop: spacing.xs }]}>
            You weren't clearly detected -- try again with your full body in frame
          </Text>
        ) : null}
      </Card>

      <Card style={styles.breakdownCol}>
        <Text style={typography.label}>Key alignments</Text>
        <View style={{ marginTop: spacing.sm }}>
          {indicators?.length ? (
            indicators.map((ind) => <AlignmentIndicator key={ind.component} indicator={ind} />)
          ) : (
            <Text style={styles.breakdownEmpty}>No alignment data for this attempt.</Text>
          )}
        </View>
      </Card>

      <Card style={styles.breakdownCol}>
        <Text style={typography.label}>Feedback</Text>
        <Text style={[typography.body, { marginTop: spacing.sm }]}>
          {primary?.text ?? 'Nicely held -- no corrections needed.'}
        </Text>
      </Card>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  body: { flex: 1 },
  bodyWide: { flexDirection: 'row-reverse' },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.bg,
    padding: spacing.lg,
  },
  cameraColumn: { flex: 1, flexDirection: 'column' },
  cameraWrap: {
    height: '46%',
    minHeight: 260,
    margin: spacing.md,
    borderRadius: radius.md,
    overflow: 'hidden',
    backgroundColor: '#000',
  },
  cameraWrapWide: { flex: 1, height: undefined, marginBottom: 0 },
  hud: { ...StyleSheet.absoluteFillObject, padding: spacing.md, justifyContent: 'space-between' },
  hudTop: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between' },
  hudPose: {
    backgroundColor: 'rgba(18,16,14,0.72)',
    borderRadius: radius.sm,
    paddingHorizontal: 12,
    paddingVertical: 8,
    maxWidth: '70%',
  },
  hudPoseName: { color: colors.text, fontSize: 17, fontWeight: '700' },
  hudProgress: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  hudScore: {
    width: 52,
    height: 52,
    borderRadius: 26,
    borderWidth: 3,
    backgroundColor: 'rgba(18,16,14,0.72)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  hudScoreValue: { fontSize: 20, fontFamily: fonts.mono },
  holdBar: {
    height: 5,
    borderRadius: 3,
    backgroundColor: 'rgba(255,255,255,0.2)',
    overflow: 'hidden',
  },
  holdFill: { height: '100%', backgroundColor: colors.primary },
  coach: {
    position: 'absolute',
    left: spacing.md,
    right: spacing.md,
    bottom: spacing.lg,
    backgroundColor: 'rgba(222,107,94,0.94)',
    borderRadius: radius.sm,
    padding: spacing.md,
  },
  coachPraise: { backgroundColor: 'rgba(111,191,115,0.94)' },
  coachInfo: { backgroundColor: 'rgba(121,167,211,0.94)' },
  coachText: { color: '#12100E', fontSize: 15, fontWeight: '600' },
  safety: {
    position: 'absolute',
    top: 70,
    left: spacing.md,
    right: spacing.md,
    backgroundColor: 'rgba(229,180,92,0.95)',
    borderRadius: radius.sm,
    padding: spacing.sm,
  },
  safetyRest: { backgroundColor: 'rgba(222,107,94,0.96)' },
  safetyText: { color: '#12100E', fontSize: 13, fontWeight: '600' },
  panel: { flex: 1 },
  panelWide: { flex: 0, width: 440, maxWidth: '42%' },
  panelContent: { padding: spacing.md, paddingBottom: spacing.md },

  eyebrowRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  readyCard: { overflow: 'hidden' },
  readyHeader: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.md },
  readyThumb: {
    width: 64,
    height: 64,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceRaised,
  },
  readyDot: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginLeft: spacing.sm,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: radius.pill,
    backgroundColor: colors.goodSoft,
  },
  readyDotInner: { width: 5, height: 5, borderRadius: 3, backgroundColor: colors.good },
  readyDotText: { fontFamily: fonts.mono, fontSize: 9, color: colors.good, letterSpacing: 0.5 },
  imageCredit: {
    color: colors.textFaint,
    fontSize: 10,
    marginTop: spacing.xs,
    fontFamily: fonts.body,
  },
  holdRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  holdRowText: { fontFamily: fonts.body, fontSize: 13, color: colors.textMuted },

  benefitRow: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm, marginBottom: spacing.sm },
  benefitText: { flex: 1, fontFamily: fonts.body, fontSize: 13.5, color: colors.text, lineHeight: 19 },
  cueRow: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm, marginBottom: spacing.sm },
  cueDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.primary,
    marginTop: 7,
  },
  cueText: { flex: 1, fontFamily: fonts.body, fontSize: 13.5, color: colors.textMuted, lineHeight: 19 },

  warnHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  warnCard: { borderColor: colors.warn, backgroundColor: colors.warnSoft },

  checkingCard: { alignItems: 'center', paddingVertical: spacing.lg },

  spokenRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: spacing.sm },
  spokenText: { fontFamily: fonts.body, fontSize: 11.5, color: colors.textFaint },

  voiceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginTop: spacing.md,
  },
  voiceText: { fontFamily: fonts.body, fontSize: 11.5, color: colors.textFaint },

  breakdown: { gap: spacing.md },
  breakdownRow: {
    flexDirection: 'row',
    marginHorizontal: spacing.md,
    marginTop: spacing.md,
  },
  breakdownCol: { flex: 1 },
  breakdownScoreRow: { alignItems: 'center', marginTop: spacing.sm },
  breakdownEmpty: { color: colors.textFaint, fontSize: 13, fontFamily: fonts.body },

  statusBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.bgDeep,
  },
  statusStats: { flexDirection: 'row', gap: spacing.lg, flexWrap: 'wrap' },
  statusStat: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  statusValue: { fontFamily: fonts.mono, fontSize: 15, color: colors.text },
  statusLabel: { fontFamily: fonts.body, fontSize: 10.5, color: colors.textFaint },
  endButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.badSoft,
  },
  endButtonText: { color: colors.bad, fontSize: 13, fontFamily: fonts.bodyMedium },
});
