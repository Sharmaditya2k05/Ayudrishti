/**
 * Onboarding.
 *
 * Everything asked here feeds the recommendation engine directly -- goals,
 * experience, duration and focus areas are all scoring factors. Nothing is
 * collected that the system does not actually use.
 *
 * Built on the shared AuthHero shell (see AuthHero.js): the left marketing
 * panel and bottom strip stay constant across all three steps, and only the
 * card's interior (the stepper + the step's own fields) changes. The
 * validation/submit logic here is unchanged from before -- only the
 * presentation and the field icons are new.
 */

import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import AuthHero from '../components/AuthHero';
import { Button, Chip, ErrorNotice } from '../components/common';
import { useAuth } from '../context/AuthContext';
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

const FEATURES = [
  {
    icon: 'shield-account-outline',
    title: 'Personalized Experience',
    description: 'Get recommendations tailored to your goals and experience level.',
  },
  {
    icon: 'chart-line',
    title: 'Track Your Progress',
    description: 'Monitor your improvement and maintain consistency.',
  },
  {
    icon: 'heart-pulse',
    title: 'Health & Safety First',
    description: 'Optional wearable support for a safer and smarter practice.',
  },
  {
    icon: 'camera-outline',
    title: 'Practice Anywhere',
    description: 'All you need is your device camera to get started.',
  },
];

const BOTTOM_STRIP = [
  {
    icon: 'shield-lock-outline',
    title: 'Your privacy matters',
    description: 'We never share your data. Your information is secure and used only to enhance your experience.',
    wide: true,
  },
  { icon: 'lock-outline', title: 'Secure', description: 'Enterprise-grade protection' },
  { icon: 'shield-check-outline', title: 'Private', description: 'Your data stays yours' },
  { icon: 'account-group-outline', title: 'Trusted', description: 'Built for yoga communities' },
];

function Stepper({ labels, activeIndex }) {
  return (
    <View style={styles.stepperRow}>
      {labels.map((label, i) => (
        <React.Fragment key={label}>
          <View style={styles.stepperItem}>
            <View
              style={[
                styles.stepCircle,
                i === activeIndex && styles.stepCircleActive,
                i < activeIndex && styles.stepCircleDone,
              ]}
            >
              {i < activeIndex ? (
                <MaterialCommunityIcons name="check" size={14} color={colors.bgDeep} />
              ) : (
                <Text style={[styles.stepNumber, i === activeIndex && styles.stepNumberActive]}>
                  {i + 1}
                </Text>
              )}
            </View>
            <Text style={[styles.stepLabel, i === activeIndex && styles.stepLabelActive]}>
              {label}
            </Text>
          </View>
          {i < labels.length - 1 ? (
            <View style={[styles.stepConnector, i < activeIndex && styles.stepConnectorDone]} />
          ) : null}
        </React.Fragment>
      ))}
    </View>
  );
}

function IconField({ icon, label, value, onChange, secure, onToggleSecure, showSecure, ...rest }) {
  return (
    <View style={{ marginBottom: spacing.md }}>
      <Text style={typography.label}>{label}</Text>
      <View style={styles.inputRow}>
        <MaterialCommunityIcons name={icon} size={18} color={colors.textFaint} />
        <TextInput
          style={styles.input}
          value={value}
          onChangeText={onChange}
          placeholderTextColor={colors.textFaint}
          secureTextEntry={secure && !showSecure}
          {...rest}
        />
        {secure ? (
          <Pressable onPress={onToggleSecure} hitSlop={8}>
            <MaterialCommunityIcons
              name={showSecure ? 'eye-off-outline' : 'eye-outline'}
              size={18}
              color={colors.textFaint}
            />
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

export default function OnboardingScreen({ navigation }) {
  const { register, user, updateProfile } = useAuth();
  const editing = Boolean(user);

  const [step, setStep] = useState(editing ? 1 : 0);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const [form, setForm] = useState({
    name: user?.name ?? '',
    email: '',
    password: '',
    age: user?.age ? String(user.age) : '',
    experience: user?.experience ?? 'beginner',
    goals: user?.goals ?? [],
    focus_areas: user?.focus_areas ?? [],
    preferred_duration: user?.preferred_duration ?? 20,
    practice_frequency: user?.practice_frequency ?? 3,
  });

  const set = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  const toggle = (key, id) =>
    setForm((prev) => ({
      ...prev,
      [key]: prev[key].includes(id)
        ? prev[key].filter((x) => x !== id)
        : [...prev[key], id],
    }));

  const validateAccount = () => {
    if (!form.name.trim()) return 'Please enter your name.';
    if (!form.email.includes('@')) return 'Please enter a valid email address.';
    if (form.password.length < 8) return 'Password must be at least 8 characters.';
    if (form.age && (Number(form.age) < 5 || Number(form.age) > 120))
      return 'Please enter a valid age.';
    return null;
  };

  const next = () => {
    setError(null);
    if (step === 0) {
      const problem = validateAccount();
      if (problem) {
        setError(new Error(problem));
        return;
      }
    }
    if (step === 1 && form.goals.length === 0) {
      setError(new Error('Choose at least one goal so we can plan your sessions.'));
      return;
    }
    setStep((s) => s + 1);
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const payload = {
        name: form.name.trim(),
        age: form.age ? Number(form.age) : null,
        experience: form.experience,
        goals: form.goals,
        focus_areas: form.focus_areas,
        preferred_duration: form.preferred_duration,
        practice_frequency: form.practice_frequency,
      };
      if (editing) {
        await updateProfile(payload);
      } else {
        await register({
          ...payload,
          email: form.email.trim().toLowerCase(),
          password: form.password,
        });
      }
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const stepLabels = editing ? ['Goals', 'Practice'] : ['Account', 'Goals', 'Practice'];
  const stepIndex = editing ? step - 1 : step;
  const isLast = step === (editing ? 2 : 2);
  const canGoBack = !editing && step === 0 ? true : step > (editing ? 1 : 0);
  const backLabel = !editing && step === 0 ? 'Get started' : canGoBack ? 'Back' : undefined;
  const onBack = !editing && step === 0 ? () => navigation.goBack() : () => setStep((s) => s - 1);

  return (
    <AuthHero
      backLabel={backLabel}
      onBack={onBack}
      headlineLines={["Let's start your", 'Yoga journey']}
      subtitle="Create your account to save your practice history, get personalized recommendations, and track your progress over time."
      features={FEATURES}
      bottomStrip={BOTTOM_STRIP}
    >
      <Stepper labels={stepLabels} activeIndex={stepIndex} />

      {step === 0 && !editing ? (
        <>
          <Text style={styles.cardTitle}>Create your account</Text>
          <Text style={styles.cardSubtitle}>Fill in your details to get started</Text>

          <View style={{ marginTop: spacing.lg }}>
            <IconField
              icon="account-outline"
              label="Full name"
              value={form.name}
              onChange={(v) => set('name', v)}
              placeholder="Your name"
            />
            <IconField
              icon="email-outline"
              label="Email address"
              value={form.email}
              onChange={(v) => set('email', v)}
              placeholder="you@example.com"
              keyboardType="email-address"
              autoCapitalize="none"
              autoComplete="email"
            />
            <IconField
              icon="lock-outline"
              label="Password"
              value={form.password}
              onChange={(v) => set('password', v)}
              placeholder="At least 8 characters"
              secure
              showSecure={showPassword}
              onToggleSecure={() => setShowPassword((v) => !v)}
            />
            <IconField
              icon="calendar-outline"
              label="Age (optional)"
              value={form.age}
              onChange={(v) => set('age', v.replace(/[^0-9]/g, ''))}
              placeholder="e.g. 32"
              keyboardType="number-pad"
            />
          </View>
        </>
      ) : null}

      {step === 1 ? (
        <>
          <Text style={styles.cardTitle}>What are you working towards?</Text>
          <Text style={styles.cardSubtitle}>
            Your goals decide which asanas we recommend. Choose as many as you like.
          </Text>
          <View style={[styles.chipWrap, { marginTop: spacing.lg }]}>
            {GOAL_OPTIONS.map((g) => (
              <Chip
                key={g.id}
                label={g.label}
                selected={form.goals.includes(g.id)}
                onPress={() => toggle('goals', g.id)}
              />
            ))}
          </View>

          <Text style={[typography.label, { marginTop: spacing.lg }]}>Your experience</Text>
          <Text style={[typography.caption, { marginBottom: spacing.sm }]}>
            We never suggest poses more than one level above you.
          </Text>
          {EXPERIENCE_OPTIONS.map((option) => (
            <Pressable
              key={option.id}
              onPress={() => set('experience', option.id)}
              style={[styles.option, form.experience === option.id && styles.optionSelected]}
            >
              <View style={{ flex: 1 }}>
                <Text style={styles.optionLabel}>{option.label}</Text>
                <Text style={styles.optionHint}>{option.hint}</Text>
              </View>
              <View style={[styles.radio, form.experience === option.id && styles.radioSelected]}>
                {form.experience === option.id ? (
                  <MaterialCommunityIcons name="check" size={12} color={colors.bgDeep} />
                ) : null}
              </View>
            </Pressable>
          ))}
        </>
      ) : null}

      {step === 2 ? (
        <>
          <Text style={styles.cardTitle}>How do you want to practise?</Text>
          <Text style={styles.cardSubtitle}>You can always change this later in your profile.</Text>

          <Text style={[typography.label, { marginTop: spacing.lg }]}>
            Session length (minutes)
          </Text>
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

          <Text style={[typography.label, { marginTop: spacing.md }]}>Areas to focus on</Text>
          <Text style={[typography.caption, { marginBottom: spacing.sm }]}>
            Optional. Poses that work these areas score higher in your plan.
          </Text>
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
        </>
      ) : null}

      <ErrorNotice error={error} />

      <Button
        title={isLast ? (editing ? 'Save' : 'Start practising') : 'Continue'}
        icon={isLast ? undefined : 'arrow-right'}
        onPress={isLast ? submit : next}
        loading={busy}
        style={{ marginTop: spacing.lg }}
      />

      {!editing && step === 0 ? (
        <>
          <View style={styles.divider}>
            <View style={styles.dividerLine} />
            <Text style={styles.dividerText}>or</Text>
            <View style={styles.dividerLine} />
          </View>
          <Button
            title="I already have an account"
            variant="ghost"
            onPress={() => navigation.goBack()}
          />
        </>
      ) : null}
    </AuthHero>
  );
}

const styles = StyleSheet.create({
  stepperRow: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.xl },
  stepperItem: { alignItems: 'center' },
  stepCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: colors.border,
    backgroundColor: colors.surfaceRaised,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepCircleActive: { borderColor: colors.primary, backgroundColor: colors.primaryFaint },
  stepCircleDone: { borderColor: colors.primary, backgroundColor: colors.primary },
  stepNumber: { fontFamily: fonts.bodySemibold, fontSize: 13, color: colors.textFaint },
  stepNumberActive: { color: colors.primary },
  stepLabel: {
    fontFamily: fonts.body,
    fontSize: 11,
    color: colors.textFaint,
    marginTop: 4,
  },
  stepLabelActive: { color: colors.primary, fontFamily: fonts.bodyMedium },
  stepConnector: {
    flex: 1,
    height: 1,
    borderStyle: 'dashed',
    borderWidth: 1,
    borderColor: colors.border,
    marginHorizontal: spacing.sm,
    marginBottom: 18,
  },
  stepConnectorDone: { borderColor: colors.primary },

  cardTitle: { fontFamily: fonts.display, fontSize: 26, color: colors.text },
  cardSubtitle: {
    fontFamily: fonts.body,
    fontSize: 13,
    color: colors.textMuted,
    marginTop: 4,
  },

  inputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.bgDeep,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: 14,
    marginTop: spacing.xs,
  },
  input: {
    flex: 1,
    color: colors.text,
    paddingVertical: 13,
    fontSize: 15,
    fontFamily: fonts.body,
  },

  chipWrap: { flexDirection: 'row', flexWrap: 'wrap' },

  option: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.sm,
  },
  optionSelected: { borderColor: colors.primary, backgroundColor: colors.primarySoft },
  optionLabel: { color: colors.text, fontSize: 15, fontFamily: fonts.bodySemibold },
  optionHint: { color: colors.textMuted, fontSize: 12, marginTop: 2, fontFamily: fonts.body },
  radio: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioSelected: { borderColor: colors.primary, backgroundColor: colors.primary },

  divider: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginVertical: spacing.md,
  },
  dividerLine: { flex: 1, height: 1, backgroundColor: colors.border },
  dividerText: { color: colors.textFaint, fontSize: 12, fontFamily: fonts.body },
});
