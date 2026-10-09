import React, { useCallback, useState } from 'react';
import { Image, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';

import api from '../api/client';
import DashboardHeader from '../components/DashboardHeader';
import DashboardLayout from '../components/DashboardLayout';
import {
  Button,
  Card,
  EmptyState,
  ErrorNotice,
  Loading,
  ScoreRing,
  Screen,
  formatDuration,
} from '../components/common';
import { useAuth } from '../context/AuthContext';
import { colors, fonts, radius, spacing, typography } from '../theme/theme';

const HERO_IMAGE = require('../../assets/home-hero.jpg');
const HERO_CREDIT = 'Photo: Dennis Yang / CC BY 2.0';

const DAY_LABELS = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

const STAGE_LABELS = {
  warmup: 'Warm-up',
  standing: 'Standing',
  balance: 'Balance',
  floor: 'Floor',
  cooldown: 'Cooldown',
};

function stageLabel(stage) {
  if (!stage) return '';
  return STAGE_LABELS[stage] ?? stage[0].toUpperCase() + stage.slice(1);
}

function toLocalISODate(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/** Monday-to-Sunday local dates for the week containing `today`. */
function currentWeekDates() {
  const today = new Date();
  const day = today.getDay();
  const mondayOffset = day === 0 ? -6 : 1 - day;
  const monday = new Date(today.getFullYear(), today.getMonth(), today.getDate() + mondayOffset);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return toLocalISODate(d);
  });
}

export default function HomeScreen({ navigation }) {
  const { user } = useAuth();
  const [plan, setPlan] = useState(null);
  const [progress, setProgress] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      // All three are needed to render the dashboard; fetch together so the
      // screen does not pop in three separate times.
      const [nextPlan, stats, recentSessions] = await Promise.all([
        api.getRecommendations(),
        api.getProgress(),
        api.listSessions(100),
      ]);
      setPlan(nextPlan);
      setProgress(stats);
      setSessions(recentSessions.filter((s) => s.status === 'completed'));
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

  const onRefresh = () => {
    setRefreshing(true);
    load();
  };

  if (loading) return <Loading label="Preparing your session..." />;

  const uniqueAsanas = plan
    ? [...new Map(plan.items.map((i) => [i.asana_id, i])).values()]
    : [];

  const totalSeconds = sessions.reduce((sum, s) => sum + (s.duration_seconds ?? 0), 0);
  const practicedDates = new Set(progress?.score_history?.map((h) => h.date) ?? []);
  const weekDates = currentWeekDates();
  const recentActivity = sessions.slice(0, 4);

  const sessionDescription =
    plan && plan.rounds > 1
      ? `The main sequence is repeated ${plan.rounds} times to fill your ${Math.round(
          plan.total_minutes,
        )}-minute session.`
      : plan?.notes?.[0];

  return (
    <Screen
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />
      }
    >
      <DashboardHeader navigation={navigation} />
      <ErrorNotice error={error} onRetry={load} />

      <DashboardLayout
        sidebar={
          <>
            <Card>
              <View style={styles.sidebarHeaderRow}>
                <View style={styles.sidebarTitleRow}>
                  <MaterialCommunityIcons name="trending-up" size={16} color={colors.primary} />
                  <Text style={styles.sidebarTitle}>Your Progress</Text>
                </View>
                <Text style={styles.link} onPress={() => navigation.navigate('Progress')}>
                  View all
                </Text>
              </View>
              <View style={styles.progressRow}>
                <ScoreRing score={progress?.overall_average} size={104} label="AVG SCORE" />
                <View style={styles.progressStats}>
                  <ProgressStat
                    icon="calendar-check-outline"
                    label="Sessions"
                    value={progress?.total_sessions ?? 0}
                  />
                  <ProgressStat
                    icon="clock-outline"
                    label="Total Time"
                    value={formatDuration(totalSeconds)}
                  />
                  <ProgressStat
                    icon="yoga"
                    label="Asanas Practiced"
                    value={progress?.total_assessments ?? 0}
                  />
                </View>
              </View>
            </Card>

            <Card>
              <View style={styles.sidebarHeaderRow}>
                <View style={styles.sidebarTitleRow}>
                  <MaterialCommunityIcons name="fire" size={16} color={colors.primary} />
                  <Text style={styles.sidebarTitle}>Weekly Streak</Text>
                </View>
                <Text style={styles.streakValue}>
                  {progress?.consistency?.current_streak ?? 0} days
                </Text>
              </View>
              <View style={styles.weekRow}>
                {DAY_LABELS.map((label, i) => {
                  const active = practicedDates.has(weekDates[i]);
                  return (
                    <View key={i} style={styles.weekDay}>
                      <View style={[styles.weekDot, active && styles.weekDotActive]}>
                        {active ? (
                          <MaterialCommunityIcons name="check" size={12} color={colors.bgDeep} />
                        ) : null}
                      </View>
                      <Text style={styles.weekLabel}>{label}</Text>
                    </View>
                  );
                })}
              </View>
              <View style={styles.streakPrompt}>
                <MaterialCommunityIcons name="arrow-up-right" size={14} color={colors.primary} />
                <Text style={styles.streakPromptText}>
                  {progress?.consistency?.current_streak
                    ? 'Keep it going -- practise today to extend your streak.'
                    : 'Start your streak and keep it going!'}
                </Text>
              </View>
            </Card>

            <Card>
              <View style={styles.sidebarTitleRow}>
                <MaterialCommunityIcons name="history" size={16} color={colors.primary} />
                <Text style={styles.sidebarTitle}>Recent Activity</Text>
              </View>
              {recentActivity.length ? (
                <View style={{ marginTop: spacing.md }}>
                  {recentActivity.map((s) => (
                    <View key={s.id} style={styles.activityRow}>
                      <View style={styles.activityIcon}>
                        <MaterialCommunityIcons name="yoga" size={16} color={colors.primary} />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.activityTitle}>
                          {s.asana_count} {s.asana_count === 1 ? 'asana' : 'asanas'} ·{' '}
                          {formatDuration(s.duration_seconds)}
                        </Text>
                        <Text style={styles.activityMeta}>
                          {new Date(s.started_at).toLocaleDateString(undefined, {
                            day: 'numeric',
                            month: 'short',
                          })}
                          {s.overall_score != null ? ` · ${Math.round(s.overall_score)}%` : ''}
                        </Text>
                      </View>
                    </View>
                  ))}
                </View>
              ) : (
                <View style={styles.emptyActivity}>
                  <View style={styles.emptyActivityIcon}>
                    <MaterialCommunityIcons name="yoga" size={34} color={colors.primary} />
                  </View>
                  <Text style={styles.emptyActivityTitle}>No recent activity</Text>
                  <Text style={styles.emptyActivityText}>
                    Your practice history will appear here.
                  </Text>
                </View>
              )}
            </Card>
          </>
        }
      >
        <View style={styles.hero}>
          <Image source={HERO_IMAGE} style={styles.heroImage} resizeMode="cover" />
          <LinearGradient
            colors={[
              'rgba(7,13,10,0.92)',
              'rgba(7,13,10,0.68)',
              'rgba(7,13,10,0.24)',
              'rgba(7,13,10,0.02)',
            ]}
            locations={[0, 0.32, 0.62, 1]}
            start={{ x: 0, y: 0.5 }}
            end={{ x: 1, y: 0.5 }}
            style={styles.heroImage}
          />
          <View style={styles.heroContent}>
            <Text style={typography.label}>Namaste,</Text>
            <Text style={styles.heroName}>{user?.name ?? 'Practitioner'}</Text>
            <Text style={styles.heroSubtitle}>
              Let's begin your journey to a stronger, healthier you.
            </Text>
          </View>
          <Text style={styles.heroCredit}>{HERO_CREDIT}</Text>
        </View>

        {progress && progress.total_sessions === 0 ? (
          <Card style={styles.nudgeCard}>
            <View style={styles.nudgeIcon}>
              <MaterialCommunityIcons name="leaf" size={18} color={colors.primary} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.nudgeTitle}>No sessions recorded yet.</Text>
              <Text style={styles.nudgeText}>Start your first session today!</Text>
            </View>
          </Card>
        ) : null}

        {plan && plan.items.length > 0 ? (
          <Card>
            <View style={styles.planHeader}>
              <View style={{ flex: 1 }}>
                <Text style={typography.label}>Today's session</Text>
                <Text style={[typography.title, { marginTop: 2 }]}>{plan.focus}</Text>
                <Text style={[typography.caption, { marginTop: spacing.xs }]}>
                  {Math.round(plan.total_minutes)} min · {uniqueAsanas.length} asanas
                  {plan.rounds > 1 ? ` · ${plan.rounds} rounds` : ''}
                </Text>
              </View>
              <ScoreRing score={progress?.overall_average} size={72} label="AVG" />
            </View>

            {sessionDescription ? (
              <Text style={styles.sessionDescription}>{sessionDescription}</Text>
            ) : null}

            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              style={styles.poseRow}
              contentContainerStyle={styles.poseRowContent}
            >
              {uniqueAsanas.slice(0, 5).map((item, i) => (
                <React.Fragment key={item.asana_id}>
                  <View style={styles.poseCard}>
                    {item.image_url ? (
                      <Image
                        source={{ uri: item.image_url }}
                        style={styles.poseThumb}
                        resizeMode="cover"
                        accessibilityLabel={`Reference photo of ${item.asana_name}`}
                      />
                    ) : (
                      <View style={[styles.poseThumb, styles.poseThumbPlaceholder]}>
                        <MaterialCommunityIcons name="yoga" size={22} color={colors.textFaint} />
                      </View>
                    )}
                    <Text style={styles.poseName} numberOfLines={1}>
                      {item.asana_name}
                    </Text>
                    <Text style={styles.poseStage}>{stageLabel(item.sequence_stage)}</Text>
                  </View>
                  {i < Math.min(uniqueAsanas.length, 5) - 1 ? (
                    <MaterialCommunityIcons
                      name="chevron-right"
                      size={16}
                      color={colors.textFaint}
                      style={styles.poseChevron}
                    />
                  ) : null}
                </React.Fragment>
              ))}
            </ScrollView>

            <Button
              title="Start session"
              icon="play"
              onPress={() => navigation.navigate('Practice', { plan })}
              style={{ marginTop: spacing.md }}
            />
          </Card>
        ) : (
          <EmptyState
            title="No session available"
            message="Complete your profile so AyuDrishti can plan a session for you."
            action={<Button title="Update profile" onPress={() => navigation.navigate('Profile')} />}
          />
        )}
      </DashboardLayout>
    </Screen>
  );
}

function ProgressStat({ icon, label, value }) {
  return (
    <View style={styles.progressStatRow}>
      <MaterialCommunityIcons name={icon} size={16} color={colors.primary} />
      <View>
        <Text style={styles.progressStatLabel}>{label}</Text>
        <Text style={styles.progressStatValue}>{value}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  hero: {
    height: 260,
    borderRadius: radius.lg,
    overflow: 'hidden',
    marginTop: spacing.md,
    marginBottom: spacing.md,
    backgroundColor: colors.surfaceRaised,
  },
  heroImage: { ...StyleSheet.absoluteFillObject, width: '100%', height: '100%' },
  heroContent: { flex: 1, padding: spacing.lg, justifyContent: 'center', maxWidth: 340 },
  heroName: { fontFamily: fonts.display, fontSize: 34, color: colors.primary, marginTop: -2 },
  heroSubtitle: {
    fontFamily: fonts.body,
    fontSize: 14,
    lineHeight: 20,
    color: colors.textMuted,
    marginTop: spacing.sm,
  },
  heroCredit: {
    position: 'absolute',
    right: spacing.sm,
    bottom: spacing.xs,
    color: 'rgba(255,255,255,0.55)',
    fontSize: 9,
    fontFamily: fonts.body,
  },

  nudgeCard: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  nudgeIcon: {
    width: 34,
    height: 34,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primarySoft,
  },
  nudgeTitle: { fontFamily: fonts.bodySemibold, fontSize: 14, color: colors.text },
  nudgeText: { fontFamily: fonts.body, fontSize: 13, color: colors.textMuted, marginTop: 1 },

  planHeader: { flexDirection: 'row', alignItems: 'center' },
  sessionDescription: {
    fontFamily: fonts.body,
    fontSize: 13,
    lineHeight: 19,
    color: colors.textMuted,
    marginTop: spacing.sm,
  },
  poseRow: { marginTop: spacing.md },
  poseRowContent: { flexDirection: 'row', alignItems: 'flex-start' },
  poseCard: { width: 96 },
  poseThumb: {
    width: 96,
    height: 96,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceRaised,
    marginBottom: 6,
  },
  poseThumbPlaceholder: { alignItems: 'center', justifyContent: 'center' },
  poseName: { fontFamily: fonts.bodySemibold, fontSize: 12, color: colors.text },
  poseStage: { fontFamily: fonts.body, fontSize: 10.5, color: colors.textFaint, marginTop: 1 },
  poseChevron: { marginHorizontal: 2, marginTop: 40 },

  sidebarHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  sidebarTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  sidebarTitle: { fontFamily: fonts.bodySemibold, fontSize: 14.5, color: colors.text },
  link: { color: colors.primary, fontSize: 12.5, fontFamily: fonts.bodyMedium },

  progressRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  progressStats: { flex: 1, gap: spacing.sm },
  progressStatRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  progressStatLabel: { fontFamily: fonts.body, fontSize: 11, color: colors.textFaint },
  progressStatValue: { fontFamily: fonts.bodySemibold, fontSize: 14.5, color: colors.text },

  streakValue: { fontFamily: fonts.mono, fontSize: 13, color: colors.primary },
  weekRow: { flexDirection: 'row', justifyContent: 'space-between' },
  weekDay: { alignItems: 'center', gap: 6 },
  weekDot: {
    width: 30,
    height: 30,
    borderRadius: 15,
    borderWidth: 1.5,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  weekDotActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  weekLabel: { fontFamily: fonts.body, fontSize: 10.5, color: colors.textFaint },
  streakPrompt: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  streakPromptText: { flex: 1, fontFamily: fonts.body, fontSize: 12, color: colors.textMuted },

  activityRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.sm },
  activityIcon: {
    width: 32,
    height: 32,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primaryFaint,
  },
  activityTitle: { fontFamily: fonts.bodyMedium, fontSize: 13, color: colors.text },
  activityMeta: { fontFamily: fonts.body, fontSize: 11.5, color: colors.textFaint, marginTop: 1 },

  emptyActivity: { alignItems: 'center', paddingVertical: spacing.lg },
  emptyActivityIcon: {
    width: 72,
    height: 72,
    borderRadius: 36,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primaryFaint,
    marginBottom: spacing.sm,
  },
  emptyActivityTitle: { fontFamily: fonts.bodySemibold, fontSize: 14, color: colors.text },
  emptyActivityText: {
    fontFamily: fonts.body,
    fontSize: 12,
    color: colors.textFaint,
    marginTop: 2,
    textAlign: 'center',
  },
});
