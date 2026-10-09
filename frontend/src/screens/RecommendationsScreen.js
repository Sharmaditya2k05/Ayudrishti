/**
 * Recommendations ("Plan" tab).
 *
 * Shows not just *what* to practise but *why*: every pose can be expanded to
 * reveal the signed scoring factors the engine used. That transparency is a
 * product requirement, not a debug view -- a practitioner who understands
 * why a pose was chosen is far more likely to trust and follow the plan.
 *
 * Built on the same dashboard shell as Home/Progress/Profile: a header, and
 * a wide-viewport two-column body (sequence on the left, plan controls in a
 * sidebar) that collapses to one column on a phone.
 */

import React, { useCallback, useState } from 'react';
import { Image, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import api from '../api/client';
import DashboardHeader from '../components/DashboardHeader';
import DashboardLayout from '../components/DashboardLayout';
import {
  Badge,
  Button,
  Card,
  Chip,
  EmptyState,
  ErrorNotice,
  Loading,
  Screen,
  SectionTitle,
} from '../components/common';
import { colors, fonts, radius, spacing, typography } from '../theme/theme';

const DURATIONS = [10, 15, 20, 30, 45];

export default function RecommendationsScreen({ navigation }) {
  const [plan, setPlan] = useState(null);
  const [duration, setDuration] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(
    async (minutes) => {
      setError(null);
      try {
        setPlan(await api.getRecommendations(minutes ?? duration));
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [duration],
  );

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const pickDuration = (minutes) => {
    setDuration(minutes);
    setLoading(true);
    load(minutes);
  };

  if (loading) return <Loading label="Building your plan..." />;

  if (!plan?.items?.length) {
    return (
      <Screen>
        <DashboardHeader navigation={navigation} />
        <ErrorNotice error={error} onRetry={() => load()} />
        <EmptyState
          title="No recommendations yet"
          message="Set your goals and experience level so AyuDrishti can plan for you."
          action={<Button title="Update profile" onPress={() => navigation.navigate('Profile')} />}
        />
      </Screen>
    );
  }

  // Collapse rounds: the same asana repeated three times is one card.
  const unique = [...new Map(plan.items.map((i) => [i.asana_id, i])).values()];

  return (
    <Screen
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => {
            setRefreshing(true);
            load();
          }}
          tintColor={colors.primary}
        />
      }
    >
      <DashboardHeader navigation={navigation} />
      <ErrorNotice error={error} onRetry={() => load()} />

      <View style={styles.header}>
        <Text style={typography.label}>Recommended for you</Text>
        <Text style={typography.display}>{plan.focus}</Text>
        <Text style={[typography.bodyMuted, { marginTop: spacing.xs }]}>
          {Math.round(plan.total_minutes)} minutes · {unique.length} asanas
          {plan.rounds > 1 ? ` · ${plan.rounds} rounds` : ''}
        </Text>
      </View>

      <DashboardLayout
        sidebar={
          <>
            <Card>
              <View style={styles.sidebarTitleRow}>
                <MaterialCommunityIcons name="tune-variant" size={16} color={colors.primary} />
                <Text style={styles.sidebarTitle}>Session length</Text>
              </View>
              <View style={styles.durationRow}>
                {DURATIONS.map((d) => (
                  <Chip
                    key={d}
                    label={`${d}m`}
                    selected={duration === d || (!duration && plan.requested_minutes === d)}
                    onPress={() => pickDuration(d)}
                  />
                ))}
              </View>
              <Button
                title="Start this session"
                icon="play"
                onPress={() => navigation.navigate('Practice', { plan })}
                style={{ marginTop: spacing.md }}
              />
            </Card>

            {plan.notes?.length ? (
              <Card>
                <View style={styles.sidebarTitleRow}>
                  <MaterialCommunityIcons name="lightbulb-outline" size={16} color={colors.primary} />
                  <Text style={styles.sidebarTitle}>Why this plan</Text>
                </View>
                {plan.notes.map((note, i) => (
                  <Text key={i} style={styles.note}>
                    · {note}
                  </Text>
                ))}
              </Card>
            ) : null}
          </>
        }
      >
        <SectionTitle>The sequence</SectionTitle>
        {unique.map((item, i) => {
          const open = expanded === item.asana_id;
          return (
            <Card key={item.asana_id} onPress={() => setExpanded(open ? null : item.asana_id)}>
              <View style={styles.itemHeader}>
                <View style={styles.stepNumber}>
                  <Text style={styles.stepNumberText}>{i + 1}</Text>
                </View>
                {/* A thumbnail so the practitioner recognises the pose before
                    reading its name, not just after starting the session. */}
                {item.image_url ? (
                  <Image
                    source={{ uri: item.image_url }}
                    style={styles.thumbnail}
                    resizeMode="cover"
                    accessibilityLabel={`Reference photo of ${item.asana_name}`}
                  />
                ) : null}
                <View style={{ flex: 1 }}>
                  <Text style={typography.heading}>{item.asana_name}</Text>
                  <Text style={typography.caption}>
                    {item.duration_seconds}s
                    {item.sides > 1 ? ' each side' : ''} · {item.difficulty} ·{' '}
                    {item.sequence_stage}
                  </Text>
                </View>
              </View>

              <Text style={[typography.bodyMuted, { marginTop: spacing.sm }]}>{item.reason}</Text>

              {item.targeted_weakness ? (
                <View style={{ marginTop: spacing.sm }}>
                  <Badge
                    text={`Targets ${item.targeted_weakness.replace(/_/g, ' ')}`}
                    tone={colors.warn}
                  />
                </View>
              ) : null}

              {open ? (
                <View style={styles.factors}>
                  <Text style={typography.label}>How this was scored</Text>
                  {item.factors.map((factor, fi) => (
                    <View key={fi} style={styles.factorRow}>
                      <Text
                        style={[
                          styles.factorPoints,
                          { color: factor.points >= 0 ? colors.good : colors.bad },
                        ]}
                      >
                        {factor.points >= 0 ? '+' : ''}
                        {factor.points}
                      </Text>
                      <Text style={styles.factorText}>{factor.explanation}</Text>
                    </View>
                  ))}
                  <View style={styles.totalRow}>
                    <Text style={styles.totalLabel}>Total</Text>
                    <Text style={styles.totalValue}>{item.score.toFixed(1)}</Text>
                  </View>
                </View>
              ) : (
                <Text style={styles.expandHint}>Tap to see why this was chosen</Text>
              )}
            </Card>
          );
        })}
      </DashboardLayout>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { marginTop: spacing.md, marginBottom: spacing.lg },
  sidebarTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: spacing.md },
  sidebarTitle: { fontFamily: fonts.bodySemibold, fontSize: 14.5, color: colors.text },
  durationRow: { flexDirection: 'row', flexWrap: 'wrap' },
  note: { color: colors.textMuted, fontSize: 13, marginTop: spacing.sm, lineHeight: 19 },
  itemHeader: { flexDirection: 'row', alignItems: 'center' },
  stepNumber: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: colors.primarySoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.md,
  },
  stepNumberText: { color: colors.primary, fontFamily: fonts.mono, fontSize: 14 },
  thumbnail: {
    width: 52,
    height: 52,
    borderRadius: 10,
    marginRight: spacing.md,
    backgroundColor: colors.surfaceRaised,
  },
  factors: {
    marginTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: spacing.md,
  },
  factorRow: { flexDirection: 'row', marginTop: spacing.sm },
  factorPoints: { width: 44, fontSize: 13, fontFamily: fonts.mono },
  factorText: { flex: 1, color: colors.textMuted, fontSize: 13 },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: spacing.md,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  totalLabel: { color: colors.text, fontWeight: '600', fontSize: 13 },
  totalValue: { color: colors.primary, fontFamily: fonts.mono, fontSize: 13 },
  expandHint: { color: colors.textFaint, fontSize: 12, marginTop: spacing.sm },
});
