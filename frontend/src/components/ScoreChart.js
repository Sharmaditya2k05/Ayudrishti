/**
 * Progress charts.
 *
 * Recharts is the project's charting library and is used directly on web
 * (Expo Web / react-native-web), where it renders as real DOM SVG.
 *
 * Recharts depends on the DOM, so it cannot mount inside React Native's
 * native renderer. Rather than leave phones without charts, the native path
 * draws the same series with `react-native-svg`, which is already part of
 * the Expo dependency set. Both paths take identical props and render the
 * same visual language, so screens never branch on platform.
 */

import React, { useMemo } from 'react';
import { Platform, StyleSheet, Text, View } from 'react-native';

import { colors, radius, scoreColor, spacing, typography } from '../theme/theme';

const CHART_HEIGHT = 200;

function useSeries(data, dataKey) {
  return useMemo(() => {
    const points = (data ?? [])
      .map((d, i) => ({ ...d, _index: i, _value: Number(d[dataKey]) }))
      .filter((d) => Number.isFinite(d._value));
    return points;
  }, [data, dataKey]);
}

// ---------------------------------------------------------------------------
// Web: Recharts
// ---------------------------------------------------------------------------

function WebLineChart({ data, dataKey, xKey, color, domain }) {
  const {
    ResponsiveContainer,
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
  } = require('recharts');

  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -18 }}>
        <CartesianGrid stroke={colors.border} strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey={xKey}
          stroke={colors.textFaint}
          tick={{ fill: colors.textFaint, fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: colors.border }}
        />
        <YAxis
          domain={domain}
          stroke={colors.textFaint}
          tick={{ fill: colors.textFaint, fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          width={44}
        />
        <Tooltip
          contentStyle={{
            background: colors.surfaceRaised,
            border: `1px solid ${colors.border}`,
            borderRadius: 10,
            color: colors.text,
          }}
          labelStyle={{ color: colors.textMuted }}
          formatter={(value) => [`${Math.round(value)}%`, 'Score']}
        />
        <Line
          type="monotone"
          dataKey={dataKey}
          stroke={color}
          strokeWidth={2.5}
          dot={{ r: 3, fill: color, strokeWidth: 0 }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

function WebBarChart({ data, dataKey, xKey, color, domain }) {
  const {
    ResponsiveContainer,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Cell,
  } = require('recharts');

  return (
    <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
      <BarChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -18 }}>
        <CartesianGrid stroke={colors.border} strokeDasharray="3 3" vertical={false} />
        <XAxis
          dataKey={xKey}
          stroke={colors.textFaint}
          tick={{ fill: colors.textFaint, fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: colors.border }}
          interval={0}
          angle={-20}
          textAnchor="end"
          height={54}
        />
        <YAxis
          domain={domain}
          stroke={colors.textFaint}
          tick={{ fill: colors.textFaint, fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          width={44}
        />
        <Tooltip
          cursor={{ fill: colors.primarySoft }}
          contentStyle={{
            background: colors.surfaceRaised,
            border: `1px solid ${colors.border}`,
            borderRadius: 10,
            color: colors.text,
          }}
          formatter={(value) => [`${Math.round(value)}%`, 'Score']}
        />
        <Bar dataKey={dataKey} radius={[6, 6, 0, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={color ?? scoreColor(entry[dataKey])} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// Native: react-native-svg
// ---------------------------------------------------------------------------

function NativeLineChart({ data, dataKey, xKey, color, domain }) {
  const { default: Svg, Circle, Line, Path, Text: SvgText } = require('react-native-svg');
  const points = useSeries(data, dataKey);

  const [minY, maxY] = domain ?? [0, 100];
  const width = 320;
  const height = CHART_HEIGHT;
  const padX = 34;
  const padY = 16;

  if (!points.length) return null;

  const stepX =
    points.length > 1 ? (width - padX - 12) / (points.length - 1) : 0;
  const scaleY = (v) =>
    height - padY - ((v - minY) / Math.max(maxY - minY, 1)) * (height - padY * 2);

  const coords = points.map((p, i) => ({
    x: padX + i * stepX,
    y: scaleY(p._value),
    value: p._value,
  }));

  const path = coords
    .map((c, i) => `${i === 0 ? 'M' : 'L'}${c.x.toFixed(1)},${c.y.toFixed(1)}`)
    .join(' ');

  return (
    <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`}>
      {[0, 25, 50, 75, 100].map((tick) => {
        const y = scaleY(tick);
        return (
          <React.Fragment key={tick}>
            <Line
              x1={padX}
              y1={y}
              x2={width - 8}
              y2={y}
              stroke={colors.border}
              strokeWidth={1}
              strokeDasharray="3,3"
            />
            <SvgText x={4} y={y + 4} fill={colors.textFaint} fontSize={10}>
              {tick}
            </SvgText>
          </React.Fragment>
        );
      })}
      <Path d={path} stroke={color} strokeWidth={2.5} fill="none" />
      {coords.map((c, i) => (
        <Circle key={i} cx={c.x} cy={c.y} r={3.2} fill={color} />
      ))}
    </Svg>
  );
}

function NativeBarChart({ data, dataKey, color, domain }) {
  const { default: Svg, Rect, Line, Text: SvgText } = require('react-native-svg');
  const points = useSeries(data, dataKey);

  const [minY, maxY] = domain ?? [0, 100];
  const width = 320;
  const height = CHART_HEIGHT;
  const padX = 34;
  const padY = 16;

  if (!points.length) return null;

  const slot = (width - padX - 12) / points.length;
  const barWidth = Math.min(slot * 0.62, 30);
  const scaleY = (v) =>
    height - padY - ((v - minY) / Math.max(maxY - minY, 1)) * (height - padY * 2);

  return (
    <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`}>
      {[0, 50, 100].map((tick) => {
        const y = scaleY(tick);
        return (
          <React.Fragment key={tick}>
            <Line
              x1={padX}
              y1={y}
              x2={width - 8}
              y2={y}
              stroke={colors.border}
              strokeWidth={1}
              strokeDasharray="3,3"
            />
            <SvgText x={4} y={y + 4} fill={colors.textFaint} fontSize={10}>
              {tick}
            </SvgText>
          </React.Fragment>
        );
      })}
      {points.map((p, i) => {
        const y = scaleY(p._value);
        return (
          <Rect
            key={i}
            x={padX + i * slot + (slot - barWidth) / 2}
            y={y}
            width={barWidth}
            height={Math.max(height - padY - y, 1)}
            rx={4}
            fill={color ?? scoreColor(p._value)}
          />
        );
      })}
    </Svg>
  );
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

export default function ScoreChart({
  data,
  dataKey = 'score',
  xKey = 'date',
  type = 'line',
  title,
  subtitle,
  color = colors.primary,
  domain = [0, 100],
  emptyMessage = 'Not enough data yet. Complete a session to see your trend.',
}) {
  const hasData = Array.isArray(data) && data.length > 0;

  let chart = null;
  if (hasData) {
    if (Platform.OS === 'web') {
      chart =
        type === 'bar' ? (
          <WebBarChart data={data} dataKey={dataKey} xKey={xKey} color={color} domain={domain} />
        ) : (
          <WebLineChart data={data} dataKey={dataKey} xKey={xKey} color={color} domain={domain} />
        );
    } else {
      chart =
        type === 'bar' ? (
          <NativeBarChart data={data} dataKey={dataKey} color={color} domain={domain} />
        ) : (
          <NativeLineChart data={data} dataKey={dataKey} xKey={xKey} color={color} domain={domain} />
        );
    }
  }

  return (
    <View style={styles.wrapper}>
      {title ? <Text style={typography.heading}>{title}</Text> : null}
      {subtitle ? <Text style={[typography.caption, { marginTop: 2 }]}>{subtitle}</Text> : null}
      <View style={styles.chartArea}>
        {hasData ? chart : <Text style={styles.empty}>{emptyMessage}</Text>}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  chartArea: { marginTop: spacing.md, minHeight: 120, justifyContent: 'center' },
  empty: { color: colors.textMuted, fontSize: 14, textAlign: 'center', padding: spacing.lg },
});
