import React, { useCallback, useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import api from '../api/client';
import DashboardHeader from '../components/DashboardHeader';
import DashboardLayout from '../components/DashboardLayout';
import {
  Button,
  Card,
  Chip,
  ErrorNotice,
  Screen,
  SectionTitle,
} from '../components/common';
import { useAuth } from '../context/AuthContext';
import { useWearable } from '../wearable/useWearable';
import { parsePreferences } from '../nlp/parsePreferences';
import {
  EXPERIENCE_OPTIONS,
  FOCUS_OPTIONS,
  GOAL_OPTIONS,
  colors,
  fonts,
  radius,
  spacing,
  typography,
} from '../theme/theme';

const DURATIONS = [10, 15, 20, 30, 45];
const FREQUENCIES = [1, 2, 3, 4, 5, 6, 7];

const optionLabel = (options, id) => options.find((o) => o.id === id)?.label ?? id;

export default function ProfileScreen({ navigation }) {
  const { user, updateProfile, signOut } = useAuth();

  const [form, setForm] = useState(() => ({
    name: user?.name ?? '',
    age: user?.age ? String(user.age) : '',
    experience: user?.experience ?? 'beginner',
    goals: user?.goals ?? [],
    focus_areas: user?.focus_areas ?? [],
    avoid_asanas: user?.avoid_asanas ?? [],
    preferred_duration: user?.preferred_duration ?? 20,
    practice_frequency: user?.practice_frequency ?? 3,
    resting_heart_rate: user?.resting_heart_rate ? String(user.resting_heart_rate) : '',
  }));
  const [asanas, setAsanas] = useState([]);
  const [wearable, setWearable] = useState(null);
  const band = useWearable();
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  // ---- free-text preference detection ------------------------------------
  // Nothing here ever touches `form` (and so never the saved profile) until
  // the practitioner explicitly applies it below, and even then a further
  // explicit "Save changes" is still required -- two confirmations, not one.
  const [nlpText, setNlpText] = useState('');
  const [nlpResult, setNlpResult] = useState(null);
  const [nlpSelected, setNlpSelected] = useState({});
  const [nlpApplied, setNlpApplied] = useState(false);

  useEffect(() => {
    api.listAsanas().then(setAsanas).catch(() => setAsanas([]));
    api.getWearableStatus().then(setWearable).catch(() => setWearable(null));
  }, []);

  const set = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const toggle = (key, id) =>
    set(
      key,
      form[key].includes(id) ? form[key].filter((x) => x !== id) : [...form[key], id],
    );

  const detectPreferences = () => {
    const result = parsePreferences(nlpText);
    const hasAnything =
      result.experience ||
      result.goals.length ||
      result.focus_areas.length ||
      result.preferred_duration ||
      result.practice_frequency ||
      result.age;
    setNlpApplied(false);
    if (!hasAnything && !result.avoidMentions.length) {
      setNlpResult({ empty: true });
      return;
    }
    setNlpResult(result);
    const selected = {};
    if (result.experience) selected.experience = true;
    if (result.age) selected.age = true;
    if (result.preferred_duration) selected.preferred_duration = true;
    if (result.practice_frequency) selected.practice_frequency = true;
    result.goals.forEach((g) => {
      selected[`goal:${g.value}`] = true;
    });
    result.focus_areas.forEach((f) => {
      selected[`focus:${f.value}`] = true;
    });
    setNlpSelected(selected);
  };

  const toggleNlpSelection = (key) =>
    setNlpSelected((prev) => ({ ...prev, [key]: !prev[key] }));

  const applyDetected = () => {
    if (!nlpResult) return;
    setForm((prev) => {
      const next = { ...prev };
      if (nlpResult.experience && nlpSelected.experience) next.experience = nlpResult.experience.value;
      if (nlpResult.age && nlpSelected.age) next.age = String(nlpResult.age.value);
      if (nlpResult.preferred_duration && nlpSelected.preferred_duration) {
        next.preferred_duration = nlpResult.preferred_duration.value;
      }
      if (nlpResult.practice_frequency && nlpSelected.practice_frequency) {
        next.practice_frequency = nlpResult.practice_frequency.value;
      }
      const goalsToAdd = nlpResult.goals
        .filter((g) => nlpSelected[`goal:${g.value}`])
        .map((g) => g.value);
      if (goalsToAdd.length) next.goals = [...new Set([...prev.goals, ...goalsToAdd])];
      const focusToAdd = nlpResult.focus_areas
        .filter((f) => nlpSelected[`focus:${f.value}`])
        .map((f) => f.value);
      if (focusToAdd.length) next.focus_areas = [...new Set([...prev.focus_areas, ...focusToAdd])];
      return next;
    });
    setSaved(false);
    setNlpApplied(true);
    setNlpResult(null);
    setNlpText('');
  };

  const save = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await updateProfile({
        name: form.name.trim(),
        age: form.age ? Number(form.age) : null,
        experience: form.experience,
        goals: form.goals,
        focus_areas: form.focus_areas,
        avoid_asanas: form.avoid_asanas,
        preferred_duration: form.preferred_duration,
        practice_frequency: form.practice_frequency,
        resting_heart_rate: form.resting_heart_rate
          ? Number(form.resting_heart_rate)
          : null,
      });
      setSaved(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }, [form, updateProfile]);

  const initial = (user?.name ?? '?').trim().charAt(0).toUpperCase();

  return (
    <Screen>
      <DashboardHeader navigation={navigation} />
      <ErrorNotice error={error} />

      <DashboardLayout
        sidebar={
          <>
            <Card style={styles.identityCard}>
              <View style={styles.avatarLarge}>
                <Text style={styles.avatarLargeText}>{initial}</Text>
              </View>
              <Text style={styles.identityName}>{user?.name}</Text>
              <Text style={styles.identityEmail}>{user?.email}</Text>
            </Card>

            <Card>
              <View style={styles.sidebarTitleRow}>
                <MaterialCommunityIcons name="watch-variant" size={16} color={colors.primary} />
                <Text style={styles.sidebarTitle}>Wearable</Text>
              </View>
              <Text style={typography.bodyMuted}>
                {band.connected
                  ? 'Band connected over Bluetooth — streaming live.'
                  : wearable?.connected
                  ? `Last connected to ${wearable.device_name || wearable.device_id}.`
                  : 'No wearable connected. AyuDrishti works fully without one.'}
              </Text>

              {band.supported ? (
                <>
                  <Pressable
                    style={[styles.bandButton, band.connected && styles.bandButtonActive]}
                    onPress={band.connected ? band.disconnect : band.connect}
                  >
                    <MaterialCommunityIcons
                      name={band.connected ? 'bluetooth-connect' : 'bluetooth'}
                      size={15}
                      color={band.connected ? colors.bgDeep : colors.primary}
                    />
                    <Text style={[styles.bandButtonText, band.connected && styles.bandButtonTextActive]}>
                      {band.status === 'connecting'
                        ? 'Connecting…'
                        : band.connected
                        ? 'Disconnect band'
                        : 'Connect band (Bluetooth)'}
                    </Text>
                  </Pressable>

                  {band.connected && band.reading ? (
                    <View style={styles.vitalsRow}>
                      <Vital label="HR" value={band.reading.hr} unit="bpm" />
                      <Vital label="SpO₂" value={band.reading.spo2} unit="%" />
                      <Vital label="GSR" value={band.reading.gsr} unit="µS" digits={1} />
                      <Vital label="Motion" value={band.reading.motion} unit="g" digits={2} />
                    </View>
                  ) : null}

                  {band.error ? (
                    <Text style={[typography.caption, { marginTop: spacing.xs, color: colors.warn }]}>
                      {band.error.message}
                    </Text>
                  ) : null}
                </>
              ) : (
                <Text style={[typography.caption, { marginTop: spacing.sm }]}>
                  Live band pairing needs Chrome or Edge (desktop or Android). The band is optional.
                </Text>
              )}

              <Text style={[typography.label, { marginTop: spacing.md }]}>
                Resting heart rate
              </Text>
              <TextInput
                style={styles.input}
                value={form.resting_heart_rate}
                onChangeText={(v) => set('resting_heart_rate', v.replace(/[^0-9]/g, ''))}
                keyboardType="number-pad"
                placeholder="e.g. 62"
                placeholderTextColor={colors.textFaint}
              />
              {wearable?.disclaimer ? (
                <Text style={[typography.caption, { marginTop: spacing.sm }]}>
                  {wearable.disclaimer}
                </Text>
              ) : null}
            </Card>

            <Card>
              <View style={styles.sidebarTitleRow}>
                <MaterialCommunityIcons name="shield-lock-outline" size={16} color={colors.primary} />
                <Text style={styles.sidebarTitle}>Privacy</Text>
              </View>
              <Text style={typography.bodyMuted}>
                Your camera feed is analysed on your device. Only posture measurements --
                joint angles and alignment scores -- are sent to the server. No video,
                images or raw frames are transmitted or stored.
              </Text>
            </Card>

            <Button title={saved ? 'Saved' : 'Save changes'} onPress={save} loading={busy} />
            <Button
              title="Sign out"
              variant="ghost"
              icon="logout"
              onPress={signOut}
              style={{ marginTop: spacing.sm }}
            />
          </>
        }
      >
        <SectionTitle>Describe your practice</SectionTitle>
        <Card>
          <Text style={typography.caption}>
            Type it however you'd say it out loud -- goals, experience, how long or often
            you'd like to practise. Nothing is changed until you review and apply it below.
          </Text>
          <TextInput
            style={[styles.input, styles.nlpInput]}
            value={nlpText}
            onChangeText={setNlpText}
            multiline
            placeholder={
              'e.g. "I\'m a beginner and want to work on flexibility and stress relief, ' +
              'about 20 minutes, 4 times a week"'
            }
            placeholderTextColor={colors.textFaint}
          />
          <Button
            title="Detect my preferences"
            variant="ghost"
            icon="magnify"
            onPress={detectPreferences}
            disabled={!nlpText.trim()}
            style={{ marginTop: spacing.sm }}
          />

          {nlpApplied ? (
            <View style={styles.nlpAppliedRow}>
              <MaterialCommunityIcons name="check-circle-outline" size={14} color={colors.good} />
              <Text style={styles.nlpAppliedText}>
                Applied below -- review the highlighted sections, then Save changes.
              </Text>
            </View>
          ) : null}

          {nlpResult?.empty ? (
            <Text style={[typography.bodyMuted, { marginTop: spacing.md }]}>
              I couldn't pick out anything specific from that -- try mentioning a goal
              (e.g. "flexibility"), your experience level, or how long/often you'd like to
              practise.
            </Text>
          ) : null}

          {nlpResult && !nlpResult.empty ? (
            <View style={styles.nlpConfirm}>
              <Text style={[typography.label, { marginTop: spacing.md }]}>
                Here's what I found -- tap to exclude anything before applying
              </Text>

              {nlpResult.experience ? (
                <NlpDetection
                  label={`Experience: ${optionLabel(EXPERIENCE_OPTIONS, nlpResult.experience.value)}`}
                  matchedText={nlpResult.experience.matchedText}
                  selected={!!nlpSelected.experience}
                  onToggle={() => toggleNlpSelection('experience')}
                />
              ) : null}
              {nlpResult.goals.map((g) => (
                <NlpDetection
                  key={`goal:${g.value}`}
                  label={`Goal: ${optionLabel(GOAL_OPTIONS, g.value)}`}
                  matchedText={g.matchedText}
                  selected={!!nlpSelected[`goal:${g.value}`]}
                  onToggle={() => toggleNlpSelection(`goal:${g.value}`)}
                />
              ))}
              {nlpResult.focus_areas.map((f) => (
                <NlpDetection
                  key={`focus:${f.value}`}
                  label={`Focus area: ${optionLabel(FOCUS_OPTIONS, f.value)}`}
                  matchedText={f.matchedText}
                  selected={!!nlpSelected[`focus:${f.value}`]}
                  onToggle={() => toggleNlpSelection(`focus:${f.value}`)}
                />
              ))}
              {nlpResult.preferred_duration ? (
                <NlpDetection
                  label={`Session length: ${nlpResult.preferred_duration.value} min`}
                  matchedText={nlpResult.preferred_duration.matchedText}
                  selected={!!nlpSelected.preferred_duration}
                  onToggle={() => toggleNlpSelection('preferred_duration')}
                />
              ) : null}
              {nlpResult.practice_frequency ? (
                <NlpDetection
                  label={`Sessions per week: ${nlpResult.practice_frequency.value}`}
                  matchedText={nlpResult.practice_frequency.matchedText}
                  selected={!!nlpSelected.practice_frequency}
                  onToggle={() => toggleNlpSelection('practice_frequency')}
                />
              ) : null}
              {nlpResult.age ? (
                <NlpDetection
                  label={`Age: ${nlpResult.age.value}`}
                  matchedText={nlpResult.age.matchedText}
                  selected={!!nlpSelected.age}
                  onToggle={() => toggleNlpSelection('age')}
                />
              ) : null}

              {nlpResult.avoidMentions.length ? (
                <View style={styles.nlpWarnBox}>
                  <MaterialCommunityIcons name="alert-outline" size={16} color={colors.warn} />
                  <Text style={styles.nlpWarnText}>
                    You mentioned "{nlpResult.avoidMentions[0]}" -- I can't safely guess which
                    poses that means avoiding, so nothing was excluded automatically. Add
                    specific poses yourself in "Poses to skip" below.
                  </Text>
                </View>
              ) : null}

              <View style={styles.nlpActionRow}>
                <Button title="Apply to form" onPress={applyDetected} style={{ flex: 1 }} />
                <Button
                  title="Discard"
                  variant="ghost"
                  onPress={() => setNlpResult(null)}
                  style={{ flex: 1 }}
                />
              </View>
            </View>
          ) : null}
        </Card>

        <SectionTitle>Basics</SectionTitle>
        <Card>
          <Text style={typography.label}>Name</Text>
          <TextInput
            style={styles.input}
            value={form.name}
            onChangeText={(v) => set('name', v)}
            placeholderTextColor={colors.textFaint}
          />
          <Text style={[typography.label, { marginTop: spacing.md }]}>Age</Text>
          <TextInput
            style={styles.input}
            value={form.age}
            onChangeText={(v) => set('age', v.replace(/[^0-9]/g, ''))}
            keyboardType="number-pad"
            placeholder="Optional"
            placeholderTextColor={colors.textFaint}
          />
        </Card>

        <SectionTitle>Experience</SectionTitle>
        <Card>
          <View style={styles.chipWrap}>
            {EXPERIENCE_OPTIONS.map((o) => (
              <Chip
                key={o.id}
                label={o.label}
                selected={form.experience === o.id}
                onPress={() => set('experience', o.id)}
              />
            ))}
          </View>
          <Text style={typography.caption}>
            AyuDrishti never suggests poses more than one level above you, and only steps
            up once your recent scores support it.
          </Text>
        </Card>

        <SectionTitle>Goals</SectionTitle>
        <Card>
          <View style={styles.chipWrap}>
            {GOAL_OPTIONS.map((g) => (
              <Chip
                key={g.id}
                label={g.label}
                selected={form.goals.includes(g.id)}
                onPress={() => toggle('goals', g.id)}
              />
            ))}
          </View>
        </Card>

        <SectionTitle>Focus areas</SectionTitle>
        <Card>
          <View style={styles.chipWrap}>
            {FOCUS_OPTIONS.map((f) => (
              <Chip
                key={f.id}
                label={f.label}
                selected={form.focus_areas.includes(f.id)}
                onPress={() => toggle('focus_areas', f.id)}
              />
            ))}
          </View>
        </Card>

        <SectionTitle>Practice preferences</SectionTitle>
        <Card>
          <Text style={typography.label}>Session length</Text>
          <View style={[styles.chipWrap, { marginTop: spacing.sm }]}>
            {DURATIONS.map((d) => (
              <Chip
                key={d}
                label={`${d} min`}
                selected={form.preferred_duration === d}
                onPress={() => set('preferred_duration', d)}
              />
            ))}
          </View>
          <Text style={[typography.label, { marginTop: spacing.md }]}>Sessions per week</Text>
          <View style={[styles.chipWrap, { marginTop: spacing.sm }]}>
            {FREQUENCIES.map((f) => (
              <Chip
                key={f}
                label={String(f)}
                selected={form.practice_frequency === f}
                onPress={() => set('practice_frequency', f)}
              />
            ))}
          </View>
        </Card>

        {asanas.length ? (
          <>
            <SectionTitle>Poses to skip</SectionTitle>
            <Card>
              <Text style={[typography.caption, { marginBottom: spacing.sm }]}>
                Anything you select here is excluded from every plan -- useful if you have
                an injury or a pose you would rather avoid.
              </Text>
              <View style={styles.chipWrap}>
                {asanas.map((a) => (
                  <Chip
                    key={a.id}
                    label={a.english_name}
                    selected={form.avoid_asanas.includes(a.id)}
                    onPress={() => toggle('avoid_asanas', a.id)}
                    tone={form.avoid_asanas.includes(a.id) ? colors.bad : undefined}
                  />
                ))}
              </View>
            </Card>
          </>
        ) : null}
      </DashboardLayout>
    </Screen>
  );
}

/** One live vital reading from the band. Dashes out when the value is absent. */
function Vital({ label, value, unit, digits = 0 }) {
  const shown =
    value == null || value < 0 ? '—' : Number(value).toFixed(digits);
  return (
    <View style={styles.vital}>
      <Text style={styles.vitalValue}>{shown}</Text>
      <Text style={styles.vitalLabel}>
        {label}
        {unit ? ` ${unit}` : ''}
      </Text>
    </View>
  );
}

/** One toggle-able row in the "here's what I found" confirmation list. */
function NlpDetection({ label, matchedText, selected, onToggle }) {
  return (
    <Pressable onPress={onToggle} style={styles.nlpRow}>
      <MaterialCommunityIcons
        name={selected ? 'checkbox-marked' : 'checkbox-blank-outline'}
        size={18}
        color={selected ? colors.primary : colors.textFaint}
      />
      <View style={{ flex: 1 }}>
        <Text style={styles.nlpRowLabel}>{label}</Text>
        <Text style={styles.nlpRowMatch}>from “{matchedText}”</Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  input: {
    backgroundColor: colors.surfaceRaised,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.text,
    padding: 13,
    marginTop: spacing.xs,
    fontSize: 15,
  },
  chipWrap: { flexDirection: 'row', flexWrap: 'wrap' },

  bandButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    marginTop: spacing.md,
    paddingVertical: 10,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.primary,
    backgroundColor: colors.primaryFaint,
  },
  bandButtonActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  bandButtonText: { fontFamily: fonts.body, fontSize: 13.5, color: colors.primary },
  bandButtonTextActive: { color: colors.bgDeep, fontWeight: '600' },
  vitalsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: spacing.md,
    gap: spacing.xs,
  },
  vital: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceRaised,
  },
  vitalValue: { fontFamily: fonts.display, fontSize: 18, color: colors.text },
  vitalLabel: { fontFamily: fonts.mono, fontSize: 9.5, color: colors.textFaint, marginTop: 2 },

  nlpInput: { minHeight: 72, textAlignVertical: 'top', marginTop: spacing.sm },
  nlpAppliedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: spacing.sm,
  },
  nlpAppliedText: { fontFamily: fonts.body, fontSize: 12.5, color: colors.good },
  nlpConfirm: {
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  nlpRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    paddingVertical: 7,
  },
  nlpRowLabel: { fontFamily: fonts.bodyMedium, fontSize: 13.5, color: colors.text },
  nlpRowMatch: { fontFamily: fonts.body, fontSize: 11.5, color: colors.textFaint, marginTop: 1 },
  nlpWarnBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    marginTop: spacing.sm,
    padding: spacing.sm,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.warn,
    backgroundColor: colors.warnSoft,
  },
  nlpWarnText: { flex: 1, fontFamily: fonts.body, fontSize: 12.5, color: colors.text, lineHeight: 18 },
  nlpActionRow: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.md },
  sidebarTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: spacing.md },
  sidebarTitle: { fontFamily: fonts.bodySemibold, fontSize: 14.5, color: colors.text },
  identityCard: { alignItems: 'center' },
  avatarLarge: {
    width: 64,
    height: 64,
    borderRadius: 32,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
    marginBottom: spacing.sm,
  },
  avatarLargeText: { fontFamily: fonts.bodySemibold, fontSize: 26, color: colors.bgDeep },
  identityName: { fontFamily: fonts.display, fontSize: 22, color: colors.text },
  identityEmail: { fontFamily: fonts.body, fontSize: 13, color: colors.textMuted, marginTop: 2 },
});
