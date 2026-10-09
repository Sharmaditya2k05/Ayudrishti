/**
 * Marketing landing screen -- the app's own front door.
 *
 * Absorbs the purpose of the standalone `landing/` Vite site (a
 * pre-auth pitch that hands off into the real app) directly into the app
 * itself, so there is one deployable surface instead of two. Below the hero
 * sits a "How it works" section that summarises the platform and links out to
 * the full illustrated guide (served as a static page at /how-it-works.html).
 * It is not a pixel port of the old site -- it carries the same message built
 * with the app's own design system.
 */

import React from 'react';
import {
  Dimensions,
  Image,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';

import { colors, fonts, radius, spacing } from '../theme/theme';

const HERO_IMAGE = require('../../assets/home-hero.jpg');
const HERO_CREDIT = 'Photo: Dennis Yang / CC BY 2.0';
const HERO_HEIGHT = Dimensions.get('window').height;

const STATS = [
  { icon: 'triangle-outline', value: '10 Asanas', label: 'Pose Library' },
  { icon: 'grid', value: '82 Checks', label: 'Alignment Rules' },
  { icon: 'pulse', value: '4 Signals', label: 'Safety Monitoring' },
];

const LOOP = ['Suggest', 'Detect', 'Assess', 'Correct', 'Track', 'Adapt'];

const FEATURES = [
  {
    icon: 'camera-outline',
    title: 'It watches you',
    text: 'Your phone finds 33 points on your body — only those dots leave your device, never the video.',
  },
  {
    icon: 'account-voice',
    title: 'It corrects you',
    text: 'Hear the exact fix out loud, and run a whole session hands-free: say “ready”, “retry”, “next”.',
  },
  {
    icon: 'sync',
    title: 'It adapts',
    text: 'A pose you keep struggling with comes back on purpose — today’s plan is shaped by yesterday’s scores.',
  },
];

function openGuide() {
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    window.open('/how-it-works.html', '_blank', 'noopener');
  } else {
    Linking.openURL('/how-it-works.html').catch(() => {});
  }
}

export default function LandingScreen({ navigation }) {
  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
      {/* ---- Hero ---- */}
      <View style={styles.hero}>
        <Image source={HERO_IMAGE} style={styles.bg} resizeMode="cover" />
        <LinearGradient
          colors={['rgba(7,13,10,0.55)', 'rgba(7,13,10,0.72)', 'rgba(7,13,10,0.92)']}
          locations={[0, 0.5, 1]}
          style={styles.bg}
        />

        <View style={styles.nav}>
          <View style={styles.logoRow}>
            <View style={styles.logoMark}>
              <MaterialCommunityIcons name="leaf" size={18} color={colors.primary} />
            </View>
            <Text style={styles.wordmark}>AyuDrishti</Text>
          </View>
          <Pressable
            style={styles.signInButton}
            onPress={() => navigation.navigate('Login')}
            accessibilityRole="button"
          >
            <MaterialCommunityIcons name="account-circle-outline" size={18} color={colors.text} />
            <Text style={styles.signInText}>Sign in</Text>
          </Pressable>
        </View>

        <View style={styles.content}>
          <View style={styles.badge}>
            <MaterialCommunityIcons name="shield-check-outline" size={14} color={colors.primary} />
            <Text style={styles.badgeText}>your path to better alignment</Text>
          </View>

          <Text style={styles.headline}>
            Every Pose,{'\n'}
            <Text style={styles.headlineAccent}>Perfectly Aligned</Text>
          </Text>

          <Text style={styles.subtitle}>
            REAL-TIME POSTURE ASSESSMENT · CORRECTIONS YOU CAN ACT ON
          </Text>

          <View style={styles.heroButtons}>
            <Pressable
              style={styles.cta}
              onPress={() => navigation.navigate('Onboarding')}
              accessibilityRole="button"
            >
              <Text style={styles.ctaText}>Start Your Session</Text>
              <MaterialCommunityIcons name="arrow-right" size={18} color={colors.bgDeep} />
            </Pressable>
            <Pressable style={styles.ctaGhost} onPress={openGuide} accessibilityRole="button">
              <Text style={styles.ctaGhostText}>How it works</Text>
              <MaterialCommunityIcons name="arrow-down" size={16} color={colors.text} />
            </Pressable>
          </View>

          <View style={styles.statsRow}>
            {STATS.map((s) => (
              <View key={s.label} style={styles.stat}>
                <MaterialCommunityIcons name={s.icon} size={20} color={colors.primary} />
                <Text style={styles.statValue}>{s.value}</Text>
                <Text style={styles.statLabel}>{s.label}</Text>
              </View>
            ))}
          </View>
        </View>

        <Text style={styles.credit}>{HERO_CREDIT}</Text>
      </View>

      {/* ---- How it works ---- */}
      <View style={styles.section}>
        <Text style={styles.eyebrow}>HOW IT WORKS</Text>
        <Text style={styles.sectionTitle}>One loop that learns you</Text>
        <Text style={styles.sectionLead}>
          AyuDrishti isn’t a video to copy. It watches your pose, tells you exactly what to fix,
          and reshapes tomorrow’s practice from what it measured today.
        </Text>

        <View style={styles.loopRow}>
          {LOOP.map((step, i) => (
            <React.Fragment key={step}>
              <View style={[styles.loopChip, step === 'Adapt' && styles.loopChipAccent]}>
                <Text style={[styles.loopText, step === 'Adapt' && styles.loopTextAccent]}>{step}</Text>
              </View>
              {i < LOOP.length - 1 ? (
                <MaterialCommunityIcons name="chevron-right" size={16} color={colors.textMuted} />
              ) : null}
            </React.Fragment>
          ))}
        </View>

        <View style={styles.cards}>
          {FEATURES.map((f) => (
            <View key={f.title} style={styles.card}>
              <View style={styles.cardIcon}>
                <MaterialCommunityIcons name={f.icon} size={20} color={colors.primary} />
              </View>
              <Text style={styles.cardTitle}>{f.title}</Text>
              <Text style={styles.cardText}>{f.text}</Text>
            </View>
          ))}
        </View>

        <Pressable style={styles.guideBtn} onPress={openGuide} accessibilityRole="button">
          <MaterialCommunityIcons name="book-open-page-variant-outline" size={18} color={colors.primary} />
          <Text style={styles.guideBtnText}>Read the full illustrated guide</Text>
          <MaterialCommunityIcons name="arrow-right" size={16} color={colors.primary} />
        </Pressable>
        <Text style={styles.guideHint}>
          Every part and every term explained in plain language, with flowcharts.
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: colors.bg },
  scrollContent: { flexGrow: 1 },

  /* ---- Hero ---- */
  hero: { minHeight: HERO_HEIGHT, justifyContent: 'flex-start' },
  bg: { ...StyleSheet.absoluteFillObject, width: '100%', height: '100%' },
  nav: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xl,
  },
  logoRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  logoMark: {
    width: 36,
    height: 36,
    borderRadius: 11,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(74,222,128,0.16)',
    borderWidth: 1,
    borderColor: 'rgba(150,220,180,0.3)',
  },
  wordmark: { fontFamily: fonts.display, fontSize: 20, color: colors.text },
  signInButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.16)',
  },
  signInText: { color: colors.text, fontFamily: fonts.bodyMedium, fontSize: 13 },
  content: { flex: 1, justifyContent: 'flex-end', padding: spacing.lg, maxWidth: 640 },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.md,
    paddingVertical: 8,
    borderRadius: radius.pill,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.16)',
    marginBottom: spacing.md,
  },
  badgeText: { color: 'rgba(255,255,255,0.85)', fontFamily: fonts.body, fontSize: 13 },
  headline: {
    fontFamily: fonts.display,
    fontSize: 56,
    lineHeight: 58,
    color: colors.text,
    letterSpacing: -0.5,
  },
  headlineAccent: { color: colors.primary },
  subtitle: {
    fontFamily: fonts.mono,
    fontSize: 11,
    letterSpacing: 1.6,
    color: 'rgba(255,255,255,0.7)',
    marginTop: spacing.md,
  },
  heroButtons: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.lg, flexWrap: 'wrap' },
  cta: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    backgroundColor: colors.primary,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
  },
  ctaText: { fontFamily: fonts.bodySemibold, fontSize: 13, letterSpacing: 0.4, color: colors.bgDeep },
  ctaGhost: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.22)',
  },
  ctaGhostText: { fontFamily: fonts.bodyMedium, fontSize: 13, color: colors.text },
  statsRow: { flexDirection: 'row', gap: spacing.xl, marginTop: spacing.xxl, flexWrap: 'wrap' },
  stat: { gap: 4 },
  statValue: { fontFamily: fonts.mono, fontSize: 20, color: colors.text },
  statLabel: {
    fontFamily: fonts.mono,
    fontSize: 10,
    letterSpacing: 1,
    textTransform: 'uppercase',
    color: 'rgba(255,255,255,0.55)',
  },
  credit: {
    position: 'absolute',
    right: spacing.sm,
    bottom: spacing.xs,
    color: 'rgba(255,255,255,0.4)',
    fontSize: 9,
    fontFamily: fonts.body,
  },

  /* ---- How it works section ---- */
  section: {
    backgroundColor: colors.bgDeep,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xxl,
    alignItems: 'center',
  },
  eyebrow: {
    fontFamily: fonts.mono,
    fontSize: 11,
    letterSpacing: 2,
    color: colors.primary,
    marginBottom: spacing.sm,
  },
  sectionTitle: {
    fontFamily: fonts.display,
    fontSize: 34,
    color: colors.text,
    textAlign: 'center',
    letterSpacing: -0.4,
  },
  sectionLead: {
    fontFamily: fonts.body,
    fontSize: 15,
    lineHeight: 23,
    color: colors.textMuted,
    textAlign: 'center',
    maxWidth: 560,
    marginTop: spacing.sm,
  },
  loopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: spacing.xl,
    maxWidth: 620,
  },
  loopChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  loopChipAccent: { borderColor: colors.primary, backgroundColor: colors.primaryFaint },
  loopText: { fontFamily: fonts.bodyMedium, fontSize: 13, color: colors.text },
  loopTextAccent: { color: colors.primary },
  cards: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: spacing.md,
    marginTop: spacing.xl,
    maxWidth: 900,
  },
  card: {
    flexGrow: 1,
    flexBasis: 240,
    maxWidth: 300,
    padding: spacing.lg,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  cardIcon: {
    width: 40,
    height: 40,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primaryFaint,
    marginBottom: spacing.md,
  },
  cardTitle: { fontFamily: fonts.display, fontSize: 20, color: colors.text, marginBottom: 6 },
  cardText: { fontFamily: fonts.body, fontSize: 13.5, lineHeight: 20, color: colors.textMuted },
  guideBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: spacing.xxl,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.primary,
    backgroundColor: colors.primaryFaint,
  },
  guideBtnText: { fontFamily: fonts.bodySemibold, fontSize: 14, color: colors.primary },
  guideHint: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.textMuted,
    marginTop: spacing.sm,
    textAlign: 'center',
  },
});
