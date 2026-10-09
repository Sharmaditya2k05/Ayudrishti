/**
 * Responsive two-column body for the main-tab dashboard screens.
 *
 * On a wide viewport (web / tablet) the main content and the sidebar sit
 * side by side. On a phone there is no room for two columns, so the sidebar
 * simply drops below the main content instead of disappearing -- every
 * screen stays reachable by scrolling, nothing is hidden.
 */

import React from 'react';
import { StyleSheet, View, useWindowDimensions } from 'react-native';

import { spacing } from '../theme/theme';

export const DASHBOARD_WIDE_BREAKPOINT = 880;

export default function DashboardLayout({ sidebar, children }) {
  const { width } = useWindowDimensions();
  const isWide = width >= DASHBOARD_WIDE_BREAKPOINT;

  return (
    <View style={isWide ? styles.rowWide : styles.columnNarrow}>
      <View style={isWide ? styles.main : undefined}>{children}</View>
      {sidebar ? <View style={isWide ? styles.sidebar : undefined}>{sidebar}</View> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  rowWide: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.lg },
  columnNarrow: { flexDirection: 'column' },
  main: { flex: 1, minWidth: 0 },
  sidebar: { width: 340 },
});
