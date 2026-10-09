/**
 * Shared building blocks, in the app's dark-green editorial system.
 *
 * Headings are serif, eyebrows and figures are mono, surfaces are near-black
 * forest green with sage hairline borders. Every screen composes these, so
 * restyling here re-skins the whole app.
 */

import React from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import {
  colors,
  fonts,
  radius,
  scoreColor,
  spacing,
  statusColor,
  typography,
} from '../theme/theme';

export function Screen({ children, scroll = true, style, refreshControl }) {
  const Container = scroll ? ScrollView : View;
  const extra = scroll
    ? { contentContainerStyle: [styles.screenContent, style], refreshControl }
    : { style: [styles.screen, styles.screenContent, style] };
  return (
    <Container
      style={scroll ? styles.screen : undefined}
      showsVerticalScrollIndicator={false}
      {...extra}
    >
      {children}
    </Container>
  );
}

export function Card({ children, style, onPress }) {
  // Pressable calls a function `style` prop with { pressed } -- plain View
  // does not call it at all, it just silently drops it. So the two wrappers
  // need genuinely different style props, not a shared callback.
  if (onPress) {
    return (
      <Pressable
        style={({ pressed }) => [styles.card, pressed && styles.cardPressed, style]}
        onPress={onPress}
      >
        {children}
      </Pressable>
    );
  }
  return <View style={[styles.card, style]}>{children}</View>;
}

/** The small mono uppercase kicker above a heading. */
export function Eyebrow({ children, color, style }) {
  return (
    <Text style={[typography.eyebrow, color && { color }, style]}>{children}</Text>
  );
}

export function SectionTitle({ children, action }) {
  return (
    <View style={styles.sectionTitleRow}>
      <Text style={typography.label}>{children}</Text>
      {action}
    </View>
  );
}

export function Button({ title, onPress, variant = 'primary', disabled, loading, style, icon }) {
  const isPrimary = variant === 'primary';
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: disabled || loading }}
      onPress={disabled || loading ? undefined : onPress}
      style={({ pressed }) => [
        styles.button,
        isPrimary ? styles.buttonPrimary : styles.buttonGhost,
        icon && styles.buttonWithIcon,
        (disabled || loading) && styles.buttonDisabled,
        pressed && styles.buttonPressed,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={isPrimary ? colors.bgDeep : colors.text} />
      ) : (
        <>
          <Text style={[styles.buttonText, !isPrimary && styles.buttonTextGhost]}>{title}</Text>
          {icon ? (
            <MaterialCommunityIcons
              name={icon}
              size={18}
              color={isPrimary ? colors.bgDeep : colors.text}
            />
          ) : null}
        </>
      )}
    </Pressable>
  );
}

export function Chip({ label, selected, onPress, tone }) {
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityState={{ checked: Boolean(selected) }}
      onPress={onPress}
      style={[
        styles.chip,
        selected && styles.chipSelected,
        tone && selected && { borderColor: tone, backgroundColor: `${tone}22` },
      ]}
    >
      <Text style={[styles.chipText, selected && styles.chipTextSelected, tone && selected && { color: tone }]}>
        {label}
      </Text>
    </Pressable>
  );
}

/** Circular score gauge; the headline figure on most screens. */
export function ScoreRing({ score, size = 108, label, sublabel }) {
  const value = Math.max(0, Math.min(100, score ?? 0));
  const tint = scoreColor(score);
  return (
    <View style={{ alignItems: 'center' }}>
      <View
        style={[
          styles.ring,
          {
            width: size,
            height: size,
            borderRadius: size / 2,
            borderColor: tint,
            borderWidth: 3 + (value / 100) * 4,
          },
        ]}
      >
        <Text style={[styles.ringValue, { color: tint, fontSize: size * 0.3 }]}>
          {score == null ? '--' : Math.round(value)}
        </Text>
        {label ? <Text style={styles.ringLabel}>{label}</Text> : null}
      </View>
      {sublabel ? <Text style={styles.ringSub}>{sublabel}</Text> : null}
    </View>
  );
}

/** Horizontal bar for one alignment component. */
export function ScoreBar({ label, score, status }) {
  const tint = status ? statusColor(status) : scoreColor(score);
  const width = `${Math.max(0, Math.min(100, score ?? 0))}%`;
  return (
    <View style={styles.barRow}>
      <View style={styles.barHeader}>
        <Text style={styles.barLabel} numberOfLines={1}>
          {label}
        </Text>
        <Text style={[styles.barValue, { color: tint }]}>
          {score == null ? '--' : `${Math.round(score)}%`}
        </Text>
      </View>
      <View style={styles.barTrack}>
        <View style={[styles.barFill, { width, backgroundColor: tint }]} />
      </View>
    </View>
  );
}

/** Status light for a component during a live session. */
export function AlignmentIndicator({ indicator }) {
  const tint = statusColor(indicator.status);
  const glyph =
    indicator.status === 'good' ? '✓' : indicator.status === 'unknown' ? '?' : '!';
  return (
    <View style={styles.indicatorRow}>
      <View style={[styles.indicatorDot, { backgroundColor: `${tint}22`, borderColor: tint }]}>
        <Text style={[styles.indicatorGlyph, { color: tint }]}>{glyph}</Text>
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.indicatorLabel}>{indicator.label}</Text>
        {indicator.message ? (
          <Text style={styles.indicatorMessage} numberOfLines={2}>
            {indicator.message}
          </Text>
        ) : null}
      </View>
      <Text style={[styles.indicatorScore, { color: tint }]}>
        {Math.round(indicator.score)}%
      </Text>
    </View>
  );
}

export function Badge({ text, tone = colors.primary }) {
  return (
    <View style={[styles.badge, { borderColor: `${tone}66`, backgroundColor: `${tone}1F` }]}>
      <Text style={[styles.badgeText, { color: tone }]}>{text}</Text>
    </View>
  );
}

export function EmptyState({ title, message, action }) {
  return (
    <Card style={styles.empty}>
      <Text style={typography.heading}>{title}</Text>
      <Text style={[typography.bodyMuted, { marginTop: spacing.sm, textAlign: 'center' }]}>
        {message}
      </Text>
      {action ? <View style={{ marginTop: spacing.md }}>{action}</View> : null}
    </Card>
  );
}

export function ErrorNotice({ error, onRetry }) {
  if (!error) return null;
  return (
    <Card style={styles.errorCard}>
      <Text style={styles.errorText}>{error.message ?? String(error)}</Text>
      {onRetry ? (
        <Button title="Try again" variant="ghost" onPress={onRetry} style={{ marginTop: spacing.sm }} />
      ) : null}
    </Card>
  );
}

export function Loading({ label = 'Loading...' }) {
  return (
    <View style={styles.loading}>
      <ActivityIndicator color={colors.primary} size="large" />
      <Text style={[typography.label, { marginTop: spacing.md }]}>{label}</Text>
    </View>
  );
}

export function formatDuration(seconds) {
  if (!seconds) return '0 min';
  const mins = Math.round(seconds / 60);
  if (mins < 60) return `${mins} min`;
  const hours = Math.floor(mins / 60);
  return `${hours}h ${mins % 60}m`;
}

export function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  return date.toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: 'transparent' },
  screenContent: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
    flexGrow: 1,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    // A faintly brighter top edge reads as a sheen of light on the card.
    borderTopColor: colors.borderStrong,
    marginBottom: spacing.md,
  },
  cardPressed: { backgroundColor: colors.surfaceRaised },
  sectionTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
    marginTop: spacing.md,
  },
  button: {
    paddingVertical: 15,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 50,
  },
  buttonWithIcon: { flexDirection: 'row', gap: spacing.sm },
  buttonPrimary: { backgroundColor: colors.primary },
  buttonGhost: { backgroundColor: colors.surfaceSoft, borderWidth: 1, borderColor: colors.borderStrong },
  buttonDisabled: { opacity: 0.4 },
  buttonPressed: { opacity: 0.85 },
  buttonText: { color: colors.bgDeep, fontFamily: fonts.bodySemibold, fontSize: 15, letterSpacing: 0.2 },
  buttonTextGhost: { color: colors.text },
  chip: {
    paddingVertical: 9,
    paddingHorizontal: spacing.md,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    marginRight: spacing.sm,
    marginBottom: spacing.sm,
    backgroundColor: colors.surfaceSoft,
  },
  chipSelected: { borderColor: colors.primary, backgroundColor: colors.primarySoft },
  chipText: { color: colors.textMuted, fontSize: 14, fontFamily: fonts.body },
  chipTextSelected: { color: colors.primary, fontFamily: fonts.bodyMedium },
  ring: { alignItems: 'center', justifyContent: 'center' },
  ringValue: { fontFamily: fonts.mono, letterSpacing: -1 },
  ringLabel: { color: colors.textMuted, fontSize: 10, marginTop: 2, fontFamily: fonts.mono, letterSpacing: 1, textTransform: 'uppercase' },
  ringSub: { color: colors.textMuted, fontSize: 13, marginTop: spacing.sm, fontFamily: fonts.body },
  barRow: { marginBottom: spacing.sm },
  barHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 },
  barLabel: { color: colors.textMuted, fontSize: 13, flex: 1, fontFamily: fonts.body, textTransform: 'capitalize' },
  barValue: { fontSize: 13, fontFamily: fonts.monoMedium },
  barTrack: {
    height: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceRaised,
    overflow: 'hidden',
  },
  barFill: { height: '100%', borderRadius: radius.pill },
  indicatorRow: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.md },
  indicatorDot: {
    width: 30,
    height: 30,
    borderRadius: 15,
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.sm,
  },
  indicatorGlyph: { fontFamily: fonts.bodySemibold, fontSize: 14 },
  indicatorLabel: { color: colors.text, fontSize: 14, fontFamily: fonts.bodyMedium },
  indicatorMessage: { color: colors.textMuted, fontSize: 12, marginTop: 2, fontFamily: fonts.body },
  indicatorScore: { fontSize: 14, fontFamily: fonts.monoMedium, marginLeft: spacing.sm },
  badge: {
    paddingHorizontal: 11,
    paddingVertical: 4,
    borderRadius: radius.pill,
    borderWidth: 1,
    alignSelf: 'flex-start',
  },
  badgeText: { fontSize: 10, fontFamily: fonts.mono, letterSpacing: 1, textTransform: 'uppercase' },
  empty: { alignItems: 'center', paddingVertical: spacing.xl },
  errorCard: { borderColor: `${colors.bad}66`, backgroundColor: colors.badSoft, borderTopColor: `${colors.bad}66` },
  errorText: { color: colors.text, fontSize: 14, fontFamily: fonts.body },
  loading: { padding: spacing.xl, alignItems: 'center', justifyContent: 'center', flex: 1, backgroundColor: colors.bg },
});

export { styles as commonStyles };
