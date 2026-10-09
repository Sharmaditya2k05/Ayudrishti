/**
 * Shared shell for every auth-adjacent screen (Login, Onboarding).
 *
 * On a wide viewport (web / tablet) this is a two-panel hero: a marketing
 * panel over a background photo on the left, and a card on the right, with
 * an optional bottom strip below both. On a phone the panel collapses to
 * logo + headline + the card alone -- the feature list, privacy callout and
 * bottom strip are dropped rather than stacked, so a 375px screen isn't an
 * extremely long scroll before the fields the user actually came here for.
 *
 * Screens supply their own card interior as `children` (a login form, or an
 * onboarding step with its own stepper) -- this component only owns the
 * photo/gradient/headline/feature-list/bottom-strip scaffolding that is
 * identical across all of them.
 */

import React from 'react';
import {
  Image,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';

import { colors, fonts, radius, spacing } from '../theme/theme';

// Bundled locally rather than hotlinked: no network dependency for the hero
// panel, and it loads instantly instead of waiting on an external fetch.
const BACKGROUND_IMAGE = require('../../assets/login-background.jpg');

// Below this width the page loses the marketing panel and the bottom strip
// and becomes logo + headline + card only.
export const WIDE_BREAKPOINT = 900;

function Logo({ size = 40, iconSize = 20 }) {
  return (
    <View style={[styles.logoMark, { width: size, height: size, borderRadius: size * 0.3 }]}>
      <MaterialCommunityIcons name="leaf" size={iconSize} color={colors.primary} />
    </View>
  );
}

function FeatureRow({ icon, title, description }) {
  return (
    <View style={styles.featureRow}>
      <View style={styles.featureIcon}>
        <MaterialCommunityIcons name={icon} size={20} color={colors.primary} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.featureTitle}>{title}</Text>
        <Text style={styles.featureDescription}>{description}</Text>
      </View>
    </View>
  );
}

function BottomItem({ icon, title, description, wide }) {
  if (wide) {
    return (
      <View style={styles.bottomWideItem}>
        <View style={styles.bottomWideIcon}>
          <MaterialCommunityIcons name={icon} size={20} color={colors.primary} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.bottomWideTitle}>{title}</Text>
          <Text style={styles.bottomWideDescription}>{description}</Text>
        </View>
      </View>
    );
  }
  return (
    <View style={styles.bottomFeature}>
      <View style={styles.bottomFeatureIcon}>
        <MaterialCommunityIcons name={icon} size={18} color={colors.primary} />
      </View>
      <View>
        <Text style={styles.bottomFeatureTitle}>{title}</Text>
        <Text style={styles.bottomFeatureDescription}>{description}</Text>
      </View>
    </View>
  );
}

/**
 * @param {string} [backLabel] - top-left back affordance in the left panel; omitted if not given
 * @param {() => void} [onBack]
 * @param {[string, string]} headlineLines - [plainLine, accentLine]
 * @param {string} subtitle
 * @param {Array<{icon:string,title:string,description:string}>} features
 * @param {{title:string,text:string}} [privacyCallout] - shown in the left panel under the features, wide only
 * @param {Array<{icon:string,title:string,description:string,wide?:boolean}>} [bottomStrip]
 * @param {React.ReactNode} children - the card's interior content
 */
export default function AuthHero({
  backLabel,
  onBack,
  headlineLines,
  subtitle,
  features,
  privacyCallout,
  bottomStrip,
  children,
}) {
  const { width } = useWindowDimensions();
  const isWide = width >= WIDE_BREAKPOINT;

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView
        style={{ flex: 1, backgroundColor: colors.bg }}
        contentContainerStyle={isWide ? styles.wideScrollContent : styles.narrowScrollContent}
      >
        {isWide ? (
          <>
            <View style={styles.wideHero}>
              {/* Left: marketing panel over the background photo. */}
              <View style={styles.leftPanel}>
                <Image source={BACKGROUND_IMAGE} style={styles.leftPanelImage} resizeMode="cover" />

                {/* A left-to-right gradient, not a flat overlay: dark enough
                    behind the text to stay legible, but fading to nearly
                    clear over the right side of the photo so the subject
                    isn't just crushed into a grey silhouette by a flat tint. */}
                <LinearGradient
                  colors={[
                    'rgba(5,10,8,0.88)',
                    'rgba(5,10,8,0.62)',
                    'rgba(5,10,8,0.22)',
                    'rgba(5,10,8,0.05)',
                  ]}
                  locations={[0, 0.38, 0.7, 1]}
                  start={{ x: 0, y: 0.5 }}
                  end={{ x: 1, y: 0.5 }}
                  style={StyleSheet.absoluteFill}
                />
                {/* A light vertical vignette so bottom-edge content still has
                    a readable backdrop. */}
                <LinearGradient
                  colors={['transparent', 'rgba(5,10,8,0.45)']}
                  locations={[0.6, 1]}
                  style={StyleSheet.absoluteFill}
                />

                <View style={styles.leftContent}>
                  {backLabel ? (
                    <Pressable onPress={onBack} style={styles.backRow} accessibilityRole="link">
                      <MaterialCommunityIcons name="arrow-left" size={18} color={colors.primary} />
                      <Text style={styles.backLabel}>{backLabel}</Text>
                    </Pressable>
                  ) : null}

                  <View style={styles.logoRow}>
                    <Logo />
                    <View>
                      <Text style={styles.wordmark}>AyuDrishti</Text>
                      <Text style={styles.wordmarkSub}>AI YOGA COACH</Text>
                    </View>
                  </View>

                  <Text style={styles.headline}>
                    {headlineLines[0]}
                    {'\n'}
                    <Text style={styles.headlineAccent}>{headlineLines[1]}</Text>
                  </Text>
                  <Text style={styles.heroSubtitle}>{subtitle}</Text>

                  <View style={styles.featureList}>
                    {features.map((f) => (
                      <FeatureRow key={f.title} {...f} />
                    ))}
                  </View>

                  {privacyCallout ? (
                    <View style={styles.privacyCallout}>
                      <MaterialCommunityIcons name="shield-lock-outline" size={18} color={colors.primary} />
                      <View style={{ flex: 1 }}>
                        <Text style={styles.privacyCalloutTitle}>{privacyCallout.title}</Text>
                        <Text style={styles.privacyCalloutText}>{privacyCallout.text}</Text>
                      </View>
                    </View>
                  ) : null}
                </View>
              </View>

              {/* Right: the card. */}
              <View style={styles.rightPanel}>
                <View style={styles.card}>{children}</View>
              </View>
            </View>

            {bottomStrip?.length ? (
              <View style={styles.bottomStripRow}>
                {bottomStrip.map((item) => (
                  <BottomItem key={item.title} {...item} />
                ))}
              </View>
            ) : null}
          </>
        ) : (
          <View style={styles.narrowContent}>
            <View style={styles.narrowHeader}>
              {backLabel ? (
                <Pressable onPress={onBack} style={styles.backRowNarrow} accessibilityRole="link">
                  <MaterialCommunityIcons name="arrow-left" size={18} color={colors.primary} />
                  <Text style={styles.backLabel}>{backLabel}</Text>
                </Pressable>
              ) : null}
              <View style={styles.logoRow}>
                <Logo size={34} iconSize={17} />
                <View>
                  <Text style={[styles.wordmark, { fontSize: 22 }]}>AyuDrishti</Text>
                  <Text style={styles.wordmarkSub}>AI YOGA COACH</Text>
                </View>
              </View>
              <Text style={[styles.headline, styles.headlineNarrow]}>
                {headlineLines[0]}
                {'\n'}
                <Text style={styles.headlineAccent}>{headlineLines[1]}</Text>
              </Text>
            </View>
            <View style={[styles.card, styles.cardNarrow]}>{children}</View>
          </View>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  // ---- layout shells ----------------------------------------------------
  wideScrollContent: { flexGrow: 1, paddingBottom: spacing.xl },
  narrowScrollContent: { flexGrow: 1, padding: spacing.md, paddingTop: spacing.xxl },
  wideHero: { flexDirection: 'row', minHeight: 720 },
  narrowContent: { flex: 1 },

  // ---- left marketing panel (wide only) ---------------------------------
  leftPanel: { flex: 1.15, overflow: 'hidden', position: 'relative' },
  // The bundled asset carries its natural pixel dimensions (1535x1024) as
  // metadata, and RN's style-array merge lets those win over a plain
  // StyleSheet.absoluteFill (which never sets width/height, only the inset
  // properties) -- so the image rendered pinned at its native size instead
  // of stretched to the panel. Explicit 100%/100% here overrides that.
  leftPanelImage: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    width: '100%',
    height: '100%',
  },
  leftContent: { flex: 1, padding: spacing.xl, justifyContent: 'center' },

  backRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: spacing.lg },
  backRowNarrow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: spacing.md },
  backLabel: { color: colors.text, fontFamily: fonts.bodyMedium, fontSize: 14 },

  logoRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.lg },
  logoMark: {
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primarySoft,
    borderWidth: 1,
    borderColor: colors.borderStrong,
  },
  wordmark: { fontFamily: fonts.display, fontSize: 26, color: colors.text },
  wordmarkSub: {
    fontFamily: fonts.mono,
    fontSize: 10,
    color: colors.primary,
    letterSpacing: 2,
    marginTop: -2,
  },

  headline: {
    fontFamily: fonts.display,
    fontSize: 44,
    lineHeight: 48,
    color: colors.text,
    marginBottom: spacing.md,
  },
  headlineNarrow: { fontSize: 32, lineHeight: 36, marginTop: spacing.lg },
  headlineAccent: { color: colors.primary },
  heroSubtitle: {
    fontFamily: fonts.body,
    fontSize: 15,
    lineHeight: 23,
    color: colors.textMuted,
    maxWidth: 440,
    marginBottom: spacing.lg,
  },

  featureList: { gap: spacing.md, marginBottom: spacing.lg },
  featureRow: { flexDirection: 'row', gap: spacing.sm, maxWidth: 440 },
  featureIcon: {
    width: 36,
    height: 36,
    borderRadius: radius.sm,
    backgroundColor: 'rgba(10,20,15,0.55)',
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  featureTitle: { fontFamily: fonts.bodySemibold, fontSize: 14, color: colors.text },
  featureDescription: {
    fontFamily: fonts.body,
    fontSize: 12.5,
    lineHeight: 18,
    color: colors.textMuted,
    marginTop: 2,
  },

  privacyCallout: {
    flexDirection: 'row',
    gap: spacing.sm,
    alignItems: 'flex-start',
    maxWidth: 420,
    padding: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: 'rgba(10,20,15,0.55)',
  },
  privacyCalloutTitle: { fontFamily: fonts.bodySemibold, fontSize: 13, color: colors.primary },
  privacyCalloutText: {
    fontFamily: fonts.body,
    fontSize: 12,
    lineHeight: 17,
    color: colors.textMuted,
    marginTop: 2,
  },

  // ---- card shell ---------------------------------------------------------
  rightPanel: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
    backgroundColor: colors.bgDeep,
  },
  narrowHeader: { alignItems: 'center', marginBottom: spacing.xl },
  card: {
    width: '100%',
    maxWidth: 460,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    borderTopColor: colors.borderStrong,
    padding: spacing.xl,
  },
  cardNarrow: { padding: spacing.lg },

  // ---- bottom strip (wide only) -------------------------------------------
  bottomStripRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    flexWrap: 'wrap',
    gap: spacing.xl,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.xl,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.bgDeep,
  },
  bottomFeature: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  bottomFeatureIcon: {
    width: 34,
    height: 34,
    borderRadius: 17,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  bottomFeatureTitle: { fontFamily: fonts.bodyMedium, fontSize: 13, color: colors.text },
  bottomFeatureDescription: { fontFamily: fonts.body, fontSize: 11, color: colors.textFaint },

  bottomWideItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    maxWidth: 340,
  },
  bottomWideIcon: {
    width: 34,
    height: 34,
    borderRadius: 17,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  bottomWideTitle: { fontFamily: fonts.bodySemibold, fontSize: 13, color: colors.text },
  bottomWideDescription: {
    fontFamily: fonts.body,
    fontSize: 11.5,
    lineHeight: 16,
    color: colors.textFaint,
    marginTop: 2,
  },
});
