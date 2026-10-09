/**
 * Login. Built on the shared AuthHero shell -- see AuthHero.js for the
 * responsive two-panel/simplified-mobile behaviour. This file only owns the
 * card's interior (the actual sign-in form) and the auth logic.
 */

import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import AuthHero from '../components/AuthHero';
import { ErrorNotice } from '../components/common';
import { useAuth } from '../context/AuthContext';
import { colors, fonts, radius, spacing, typography } from '../theme/theme';

const FEATURES = [
  {
    icon: 'target',
    title: 'Real-time Posture Assessment',
    description: 'AI vision detects and evaluates your poses with precision.',
  },
  {
    icon: 'heart-pulse',
    title: 'Health & Safety Monitoring',
    description: 'Optional wearable integration for heart rate, SpO₂, stress & more.',
  },
  {
    icon: 'trending-up',
    title: 'Track & Improve',
    description: 'Visualize your progress and stay motivated every step of the way.',
  },
  {
    icon: 'account-heart-outline',
    title: 'Personalized for You',
    description: 'Smart recommendations based on your goals, experience and performance.',
  },
];

const PRIVACY_CALLOUT = {
  title: 'Privacy First',
  text: "Your data is secure and never shared. We process only what's needed.",
};

const TRUST_BADGES = [
  { icon: 'shield-check-outline', title: 'Secure', description: 'Enterprise grade protection' },
  { icon: 'lock-outline', title: 'Private', description: 'Your data stays yours' },
  { icon: 'flash-outline', title: 'Smart', description: 'AI insights for better practice' },
  { icon: 'account-group-outline', title: 'Trusted', description: 'Built for yoga communities' },
];

const BOTTOM_STRIP = [
  {
    icon: 'check-circle-outline',
    title: 'Works with your device camera',
    description: 'No special hardware required',
  },
  {
    icon: 'cellphone-wireless',
    title: 'Optional Wearable Support',
    description: 'Heart rate, SpO₂, GSR, Motion',
  },
  {
    icon: 'leaf',
    title: 'Yoga for Everyone',
    description: 'Beginners to advanced practitioners',
  },
];

function TrustBadge({ icon, title, description }) {
  return (
    <View style={styles.trustBadge}>
      <MaterialCommunityIcons name={icon} size={20} color={colors.primary} />
      <Text style={styles.trustTitle}>{title}</Text>
      <Text style={styles.trustDescription}>{description}</Text>
    </View>
  );
}

export default function LoginScreen({ navigation }) {
  const { signIn } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [focused, setFocused] = useState(null);
  const [showPassword, setShowPassword] = useState(false);
  const [forgotMessage, setForgotMessage] = useState(false);

  const submit = async () => {
    if (!email.trim() || !password) {
      setError(new Error('Enter your email and password.'));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await signIn(email.trim(), password);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthHero
      backLabel="Back"
      onBack={() => navigation.goBack()}
      headlineLines={['Your Personal', 'AI Yoga Coach']}
      subtitle="Practise safely, get real-time posture correction, track your progress, and achieve your goals with personalized guidance."
      features={FEATURES}
      privacyCallout={PRIVACY_CALLOUT}
      bottomStrip={BOTTOM_STRIP}
    >
      <View style={styles.cardIconRow}>
        <MaterialCommunityIcons name="leaf" size={16} color={colors.primaryBright} style={styles.cardLeaf} />
        <View style={styles.cardIconBadge}>
          <MaterialCommunityIcons name="meditation" size={30} color={colors.primary} />
        </View>
        <MaterialCommunityIcons
          name="leaf"
          size={16}
          color={colors.primaryBright}
          style={[styles.cardLeaf, styles.cardLeafRight]}
        />
      </View>

      <Text style={styles.cardTitle}>Welcome back!</Text>
      <Text style={styles.cardSubtitle}>Sign in to continue your yoga journey</Text>

      <Text style={[typography.label, { marginTop: spacing.lg }]}>Email</Text>
      <View style={[styles.inputRow, focused === 'email' && styles.inputRowFocused]}>
        <MaterialCommunityIcons name="email-outline" size={18} color={colors.textFaint} />
        <TextInput
          style={styles.input}
          value={email}
          onChangeText={setEmail}
          onFocus={() => setFocused('email')}
          onBlur={() => setFocused(null)}
          placeholder="you@example.com"
          placeholderTextColor={colors.textFaint}
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
          inputMode="email"
        />
      </View>

      <Text style={[typography.label, { marginTop: spacing.md }]}>Password</Text>
      <View style={[styles.inputRow, focused === 'password' && styles.inputRowFocused]}>
        <MaterialCommunityIcons name="lock-outline" size={18} color={colors.textFaint} />
        <TextInput
          style={styles.input}
          value={password}
          onChangeText={setPassword}
          onFocus={() => setFocused('password')}
          onBlur={() => setFocused(null)}
          placeholder="Enter your password"
          placeholderTextColor={colors.textFaint}
          secureTextEntry={!showPassword}
          autoComplete="current-password"
          onSubmitEditing={submit}
        />
        <Pressable
          onPress={() => setShowPassword((v) => !v)}
          hitSlop={8}
          accessibilityLabel={showPassword ? 'Hide password' : 'Show password'}
        >
          <MaterialCommunityIcons
            name={showPassword ? 'eye-off-outline' : 'eye-outline'}
            size={18}
            color={colors.textFaint}
          />
        </Pressable>
      </View>

      <Pressable
        onPress={() => setForgotMessage(true)}
        style={styles.forgotRow}
        accessibilityRole="link"
      >
        <Text style={styles.forgotText}>Forgot password?</Text>
      </Pressable>
      {forgotMessage ? (
        <Text style={styles.forgotNotice}>
          Password reset isn't available yet -- contact support to regain access.
        </Text>
      ) : null}

      <ErrorNotice error={error} />

      <Pressable
        onPress={submit}
        disabled={busy}
        style={({ pressed }) => [
          styles.signInButton,
          pressed && styles.signInButtonPressed,
          busy && styles.signInButtonDisabled,
        ]}
      >
        <Text style={styles.signInButtonText}>{busy ? 'Signing in...' : 'Sign in'}</Text>
        {!busy ? (
          <MaterialCommunityIcons name="arrow-right" size={18} color={colors.bgDeep} />
        ) : null}
      </Pressable>

      <View style={styles.createRow}>
        <Text style={styles.createText}>Don't have an account? </Text>
        <Pressable onPress={() => navigation.navigate('Onboarding')}>
          <Text style={styles.createLink}>Create an account</Text>
        </Pressable>
      </View>

      <View style={styles.trustRow}>
        {TRUST_BADGES.map((badge) => (
          <TrustBadge key={badge.title} {...badge} />
        ))}
      </View>
    </AuthHero>
  );
}

const styles = StyleSheet.create({
  cardIconRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.md,
  },
  cardIconBadge: {
    width: 64,
    height: 64,
    borderRadius: 32,
    borderWidth: 1.5,
    borderColor: colors.primary,
    backgroundColor: colors.primaryFaint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardLeaf: { marginHorizontal: spacing.md, opacity: 0.7 },
  cardLeafRight: { transform: [{ scaleX: -1 }] },
  cardTitle: {
    fontFamily: fonts.bodySemibold,
    fontSize: 22,
    color: colors.text,
    textAlign: 'center',
  },
  cardSubtitle: {
    fontFamily: fonts.body,
    fontSize: 13,
    color: colors.textMuted,
    textAlign: 'center',
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
  inputRowFocused: { borderColor: colors.primary },
  input: {
    flex: 1,
    color: colors.text,
    paddingVertical: 13,
    fontSize: 15,
    fontFamily: fonts.body,
  },

  forgotRow: { alignSelf: 'flex-end', marginTop: spacing.sm },
  forgotText: { color: colors.primary, fontSize: 13, fontFamily: fonts.bodyMedium },
  forgotNotice: {
    color: colors.textFaint,
    fontSize: 12,
    marginTop: spacing.xs,
    textAlign: 'right',
    fontFamily: fonts.body,
  },

  signInButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    backgroundColor: colors.primary,
    borderRadius: radius.md,
    paddingVertical: 15,
    marginTop: spacing.lg,
  },
  signInButtonPressed: { backgroundColor: colors.primaryDeep },
  signInButtonDisabled: { opacity: 0.6 },
  signInButtonText: { fontFamily: fonts.bodySemibold, fontSize: 15, color: colors.bgDeep },

  createRow: { flexDirection: 'row', justifyContent: 'center', marginTop: spacing.md },
  createText: { color: colors.textMuted, fontSize: 13, fontFamily: fonts.body },
  createLink: { color: colors.primary, fontSize: 13, fontFamily: fonts.bodySemibold },

  trustRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: spacing.xl,
    paddingTop: spacing.lg,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  trustBadge: { alignItems: 'center', flex: 1, gap: 4 },
  trustTitle: { fontFamily: fonts.bodySemibold, fontSize: 12, color: colors.text, marginTop: 2 },
  trustDescription: {
    fontFamily: fonts.body,
    fontSize: 10,
    color: colors.textFaint,
    textAlign: 'center',
  },
});
