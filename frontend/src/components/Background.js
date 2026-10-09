/**
 * Ambient app background.
 *
 * A near-black forest base with two soft radial glows and a faint grid,
 * shared by every screen so the whole app sits in one continuous atmosphere
 * -- the same treatment the landing page uses behind its video. Purely
 * decorative and non-interactive; screen content renders on top.
 *
 * The glows are plain views with a large border-radius and low opacity rather
 * than real gradients, so this needs no gradient library and behaves
 * identically on web and native.
 */

import React from 'react';
import { StyleSheet, View } from 'react-native';

import { colors } from '../theme/theme';

export default function Background({ children }) {
  return (
    <View style={styles.root}>
      {/* Glow, top-right -- mint green. */}
      <View pointerEvents="none" style={[styles.glow, styles.glowPrimary]} />
      {/* Glow, bottom-left -- teal, dimmer. */}
      <View pointerEvents="none" style={[styles.glow, styles.glowSecondary]} />
      {/* A top vignette so the status bar / header area reads darker. */}
      <View pointerEvents="none" style={styles.topVignette} />
      <View style={styles.content}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg, overflow: 'hidden' },
  content: { flex: 1 },
  glow: {
    position: 'absolute',
    width: 520,
    height: 520,
    borderRadius: 260,
    opacity: 0.5,
  },
  glowPrimary: {
    top: -220,
    right: -160,
    backgroundColor: colors.glowPrimary,
  },
  glowSecondary: {
    bottom: -240,
    left: -180,
    backgroundColor: colors.glowSecondary,
    opacity: 0.4,
  },
  topVignette: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: 160,
    backgroundColor: colors.bgDeep,
    opacity: 0.5,
  },
});
