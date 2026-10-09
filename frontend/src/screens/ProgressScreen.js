import React, { useCallback, useState } from 'react';
import { RefreshControl, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import api from '../api/client';
import DashboardHeader from '../components/DashboardHeader';
import DashboardLayout from '../components/DashboardLayout';
import ScoreChart from '../components/ScoreChart';
import {
  Badge,
  Card,
  EmptyState,
  ErrorNotice,
  Loading,
  ScoreBar,
  ScoreRing,
  Screen,
  SectionTitle,
} from '../components/common';
import { colors, fonts, scoreColor, spacing, typography } from '../theme/theme';

export default function ProgressScreen({ navigation }) {
  const [progress, setProgress] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setProgress(await api.getProgress());
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  if (loading) return <Loading label="Loading your progress..." />;

  if (!progress?.total_assessments) {
    return (
      <Screen>
        <DashboardHeader navigation={navigation} />
        <EmptyState
          title="No practice recorded yet"
          message="Complete your first session and your alignment scores will start appearing here."
        />
      </Screen>
    );
  }

  const trend = progress.overall_trend;

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
      <ErrorNotice error={error} onRetry={load} />

      <DashboardLayout
        sidebar={
          <>
            <Card>
              <View style={styles.hero}>
                <ScoreRing score={progress.overall_average} size={124} sublabel="Average score" />
                {trend != null ? (
                  <View style={{ marginTop: spacing.md }}>
                    <Badge
                      text={`${trend >= 0 ? '▲' : '▼'} ${Math.abs(trend).toFixed(1)} points`}
                      tone={trend >= 0 ? colors.good : colors.bad}
                    />
                  </View>
                ) : null}
              </View>
              <View style={styles.statsRow}>
                <Stat label="Sessions" value={progress.total_sessions} />
                <Stat label="Poses" value={progress.total_assessments} />
                <Stat
                  label="Per week"
                  value={(progress.consistency?.sessions_per_week ?? 0).toFixed(1)}
                />
              </View>
              {progress.consistency?.description ? (
                <Text style={[typography.caption, { marginTop: spacing.md, textAlign: 'center' }]}>
                  {progress.consistency.description}
                </Text>
              ) : null}
            </Card>

            {progress.weaknesses?.length ? (
              <Card>
                <View style={styles.sidebarTitleRow}>
                  <MaterialCommunityIcons name="alert-circle-outline" size={16} color={colors.warn} />
                  <Text style={styles.sidebarTitle}>Alignment weaknesses</Text>
                </View>
                {progress.weaknesses.map((w) => (
                  <View key={w.component} style={styles.weaknessItem}>
                    <View style={styles.weaknessHeader}>
                      <Text style={styles.weaknessName}>{w.component.replace(/_/g, ' ')}</Text>
                      <Badge
                        text={w.improving ? 'Improving' : 'Needs work'}
                        tone={w.improving ? colors.good : colors.warn}
                      />
                    </View>
                    <Text style={[typography.caption, { marginTop: spacing.xs }]}>
                      {w.description}
                    </Text>
                    <Text style={styles.weaknessMeta}>
                      Measured {w.observations} times · seen in {w.affected_asanas.join(', ')}
                    </Text>
                  </View>
                ))}
              </Card>
            ) : null}
          </>
        }
      >
        <ScoreChart
          data={progress.score_history}
          title="Overall score over time"
          subtitle="Every completed session"
        />

        <SectionTitle>Pose by pose</SectionTitle>
        {progress.per_asana.map((pose) => {
          const open = expanded === pose.asana_id;
          return (
            <Card key={pose.asana_id} onPress={() => setExpanded(open ? null : pose.asana_id)}>
              <View style={styles.poseHeader}>
                <View style={{ flex: 1 }}>
                  <Text style={typography.heading}>{pose.asana_name}</Text>
                  <Text style={typography.caption}>
                    {pose.attempts} {pose.attempts === 1 ? 'attempt' : 'attempts'}
                    {pose.trend != null
                      ? ` · ${pose.trend >= 0 ? '+' : ''}${pose.trend.toFixed(1)} pts`
                      : ''}
                    {pose.days_since != null ? ` · ${pose.days_since}d ago` : ''}
                  </Text>
                </View>
                <Text style={[styles.poseScore, { color: scoreColor(pose.average_score) }]}>
                  {Math.round(pose.average_score)}%
                </Text>
              </View>

              {pose.weak_components?.length ? (
                <Text style={[typography.caption, { marginTop: spacing.sm, color: colors.warn }]}>
                  Weakest: {pose.weak_components.join(', ')}
                </Text>
              ) : null}

              {open ? (
                <View style={{ marginTop: spacing.md }}>
                  <ScoreChart
                    data={pose.history}
                    title="Score history"
                    color={scoreColor(pose.average_score)}
                  />
                  {Object.entries(pose.component_history ?? {}).map(([component, series]) => {
                    const latest = series[series.length - 1]?.score;
                    return (
                      <ScoreBar
                        key={component}
                        label={component.replace(/_/g, ' ')}
                        score={latest}
                      />
                    );
                  })}
                  <View style={styles.metaRow}>
                    <Text style={typography.caption}>Best {Math.round(pose.best_score)}%</Text>
                    <Text style={typography.caption}>
                      Latest {Math.round(pose.latest_score)}%
                    </Text>
                  </View>
                </View>
              ) : (
                <Text style={styles.expandHint}>Tap for detail</Text>
              )}
            </Card>
          );
        })}
      </DashboardLayout>
    </Screen>
  );
}

function Stat({ label, value }) {
  return (
    <View style={{ alignItems: 'center' }}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  hero: { alignItems: 'center', marginBottom: spacing.md },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  statValue: { color: colors.primary, fontSize: 26, fontFamily: fonts.mono },
  statLabel: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  sidebarTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: spacing.md },
  sidebarTitle: { fontFamily: fonts.bodySemibold, fontSize: 14.5, color: colors.text },
  weaknessItem: {
    marginBottom: spacing.md,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  weaknessHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  weaknessName: {
    fontFamily: fonts.bodySemibold,
    fontSize: 13.5,
    color: colors.text,
    textTransform: 'capitalize',
    flex: 1,
    marginRight: spacing.sm,
  },
  weaknessMeta: { fontFamily: fonts.body, fontSize: 11, color: colors.textFaint, marginTop: 4 },
  poseHeader: { flexDirection: 'row', alignItems: 'center' },
  poseScore: { fontSize: 26, fontFamily: fonts.mono },
  metaRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: spacing.sm },
  expandHint: { color: colors.textFaint, fontSize: 12, marginTop: spacing.sm },
});
