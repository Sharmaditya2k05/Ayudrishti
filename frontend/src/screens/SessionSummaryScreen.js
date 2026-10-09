import React, { useMemo } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import ScoreChart from '../components/ScoreChart';
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ScoreBar,
  ScoreRing,
  Screen,
  SectionTitle,
  formatDuration,
} from '../components/common';
import { useLanguage } from '../i18n/LanguageContext';
import { colors, fonts, scoreColor, spacing, typography } from '../theme/theme';

export default function SessionSummaryScreen({ route, navigation }) {
  const { t } = useLanguage();
  const summary = route.params?.summary;

  const perPose = useMemo(() => {
    if (!summary?.assessments) return [];
    // Average repeats of the same asana so a pose done in three rounds shows
    // as one row rather than three.
    const grouped = new Map();
    summary.assessments.forEach((a) => {
      const entry = grouped.get(a.asana_id) ?? {
        asana_id: a.asana_id,
        asana_name: a.asana_name,
        scores: [],
        corrections: [],
        metrics: {},
      };
      entry.scores.push(a.score);
      entry.corrections.push(...(a.corrections ?? []));
      Object.entries(a.alignment_metrics ?? {}).forEach(([k, v]) => {
        entry.metrics[k] = entry.metrics[k] ? [...entry.metrics[k], v] : [v];
      });
      grouped.set(a.asana_id, entry);
    });

    return [...grouped.values()]
      .map((e) => ({
        ...e,
        score: e.scores.reduce((s, v) => s + v, 0) / e.scores.length,
        components: Object.fromEntries(
          Object.entries(e.metrics).map(([k, vals]) => [
            k,
            vals.reduce((s, v) => s + v, 0) / vals.length,
          ]),
        ),
      }))
      .sort((a, b) => b.score - a.score);
  }, [summary]);

  if (!summary) {
    return (
      <Screen>
        <EmptyState
          title={t('sessionSummary.noSummaryTitle')}
          message={t('sessionSummary.noSummaryMsg')}
          action={
            <Button title={t('sessionSummary.backToHome')} onPress={() => navigation.navigate('Home')} />
          }
        />
      </Screen>
    );
  }

  const chartData = perPose.map((p) => ({
    name: p.asana_name.split(' ')[0],
    score: Math.round(p.score),
  }));

  const allCorrections = [...new Set(perPose.flatMap((p) => p.corrections))];

  return (
    <Screen>
      <View style={styles.hero}>
        <ScoreRing score={summary.overall_score} size={132} sublabel={t('sessionSummary.sessionScore')} />
        <Text style={[typography.title, { marginTop: spacing.md }]}>
          {t('sessionSummary.sessionComplete')}
        </Text>
        <Text style={typography.bodyMuted}>
          {formatDuration(summary.duration_seconds)} · {summary.asana_count} {t('home.asanas')} ·{' '}
          {summary.correction_count} {t('sessionSummary.corrections')}
        </Text>
      </View>

      {perPose.length > 1 ? (
        <ScoreChart
          data={chartData}
          xKey="name"
          type="bar"
          title={t('sessionSummary.scoreByAsana')}
          subtitle={t('sessionSummary.scoreByAsanaSubtitle')}
        />
      ) : null}

      <SectionTitle>{t('sessionSummary.howEachPoseWent')}</SectionTitle>
      {perPose.map((pose) => (
        <Card key={pose.asana_id}>
          <View style={styles.poseHeader}>
            <View style={{ flex: 1 }}>
              <Text style={typography.heading}>{pose.asana_name}</Text>
              <Text style={typography.caption}>
                {pose.scores.length} {pose.scores.length === 1 ? t('sessionSummary.round') : t('sessionSummary.rounds')}
              </Text>
            </View>
            <Text style={[styles.poseScore, { color: scoreColor(pose.score) }]}>
              {Math.round(pose.score)}%
            </Text>
          </View>

          <View style={{ marginTop: spacing.md }}>
            {Object.entries(pose.components).map(([component, value]) => (
              <ScoreBar
                key={component}
                label={component.replace(/_/g, ' ')}
                score={value}
              />
            ))}
          </View>

          {pose.asana_id === summary.best_pose ? (
            <Badge text={t('sessionSummary.bestPose')} tone={colors.good} />
          ) : null}
          {pose.asana_id === summary.weakest_pose && perPose.length > 1 ? (
            <Badge text={t('sessionSummary.needsMostWork')} tone={colors.warn} />
          ) : null}
        </Card>
      ))}

      {allCorrections.length ? (
        <>
          <SectionTitle>{t('sessionSummary.correctionsReceived')}</SectionTitle>
          <Card>
            {allCorrections.slice(0, 6).map((text, i) => (
              <Text key={i} style={styles.correction}>
                · {text}
              </Text>
            ))}
          </Card>
        </>
      ) : null}

      {summary.improvement_areas?.length ? (
        <>
          <SectionTitle>{t('sessionSummary.workNextTime')}</SectionTitle>
          <Card>
            <Text style={typography.bodyMuted}>{t('sessionSummary.workNextTimeDesc')}</Text>
            <View style={styles.tagRow}>
              {summary.improvement_areas.map((area) => (
                <View key={area} style={styles.tag}>
                  <Text style={styles.tagText}>{area.replace(/_/g, ' ')}</Text>
                </View>
              ))}
            </View>
          </Card>
        </>
      ) : null}

      <Button title={t('sessionSummary.backToHome')} onPress={() => navigation.navigate('Home')} />
      <Button
        title={t('sessionSummary.seeMyProgress')}
        variant="ghost"
        onPress={() => navigation.navigate('Progress')}
        style={{ marginTop: spacing.sm }}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: { alignItems: 'center', marginVertical: spacing.lg },
  poseHeader: { flexDirection: 'row', alignItems: 'center' },
  poseScore: { fontSize: 30, fontFamily: fonts.mono },
  correction: { color: colors.textMuted, fontSize: 14, marginBottom: spacing.sm },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', marginTop: spacing.sm },
  tag: {
    backgroundColor: colors.warnSoft,
    borderColor: colors.warn,
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 5,
    marginRight: spacing.sm,
    marginBottom: spacing.sm,
  },
  tagText: { color: colors.warn, fontSize: 12, fontWeight: '600' },
});
