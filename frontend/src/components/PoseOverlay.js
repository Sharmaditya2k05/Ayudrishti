/**
 * Skeleton overlay drawn on top of the camera preview.
 *
 * Joints named in the current correction are drawn in the alert colour and
 * enlarged, so the practitioner can see *where* to move without reading the
 * text -- which matters when the phone is across the room.
 */

import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import Svg, { Circle, Line } from 'react-native-svg';

import { POSE_CONNECTIONS } from '../pose/poseDetector';
import { colors } from '../theme/theme';

const VISIBILITY_THRESHOLD = 0.5;

export default function PoseOverlay({
  landmarks,
  highlight = [],
  width,
  height,
  mirrored = false,
}) {
  const flagged = useMemo(() => new Set(highlight), [highlight]);

  const points = useMemo(() => {
    if (!landmarks) return null;
    const out = {};
    Object.entries(landmarks).forEach(([name, lm]) => {
      if (!lm || (lm.visibility ?? 1) < VISIBILITY_THRESHOLD) return;
      out[name] = {
        // The preview is mirrored for a natural "looking in a mirror" feel,
        // so overlay coordinates must be flipped to match what is on screen.
        x: (mirrored ? 1 - lm.x : lm.x) * width,
        y: lm.y * height,
      };
    });
    return out;
  }, [landmarks, width, height, mirrored]);

  if (!points || !width || !height) return null;

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      <Svg width={width} height={height}>
        {POSE_CONNECTIONS.map(([a, b]) => {
          const pa = points[a];
          const pb = points[b];
          if (!pa || !pb) return null;
          const isFlagged = flagged.has(a) && flagged.has(b);
          return (
            <Line
              key={`${a}-${b}`}
              x1={pa.x}
              y1={pa.y}
              x2={pb.x}
              y2={pb.y}
              stroke={isFlagged ? colors.skeletonFlagged : colors.skeleton}
              strokeWidth={isFlagged ? 5 : 3}
              strokeLinecap="round"
              opacity={0.9}
            />
          );
        })}
        {Object.entries(points).map(([name, p]) => {
          const isFlagged = flagged.has(name);
          return (
            <Circle
              key={name}
              cx={p.x}
              cy={p.y}
              r={isFlagged ? 8 : 4.5}
              fill={isFlagged ? colors.skeletonFlagged : colors.skeleton}
              opacity={isFlagged ? 1 : 0.85}
            />
          );
        })}
      </Svg>
    </View>
  );
}
