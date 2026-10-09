/**
 * Top bar for every main-tab screen (Home, Plan, Progress, Profile).
 *
 * Logo + wordmark on the left, a notification bell and the user's avatar on
 * the right. Purely a header -- screens render it as the first child inside
 * their own <Screen> so it scrolls with the page, matching how AuthHero's
 * logo row behaves.
 */

import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAuth } from '../context/AuthContext';
import { colors, fonts, radius, spacing } from '../theme/theme';

export default function DashboardHeader({ navigation }) {
  const { user } = useAuth();
  const initial = (user?.name ?? '?').trim().charAt(0).toUpperCase();

  return (
    <View style={styles.row}>
      <View style={styles.logoRow}>
        <View style={styles.logoMark}>
          <MaterialCommunityIcons name="leaf" size={18} color={colors.primary} />
        </View>
        <View>
          <Text style={styles.wordmark}>AyuDrishti</Text>
          <Text style={styles.wordmarkSub}>AI YOGA COACH</Text>
        </View>
      </View>

      <View style={styles.actions}>
        <Pressable style={styles.iconButton} accessibilityRole="button" accessibilityLabel="Notifications">
          <MaterialCommunityIcons name="bell-outline" size={19} color={colors.textMuted} />
        </Pressable>
        <Pressable
          style={styles.avatarRow}
          onPress={() => navigation?.navigate?.('Profile')}
          accessibilityRole="button"
          accessibilityLabel="Open profile"
        >
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{initial}</Text>
          </View>
          <MaterialCommunityIcons name="chevron-down" size={16} color={colors.textFaint} />
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.lg,
  },
  logoRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  logoMark: {
    width: 34,
    height: 34,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primarySoft,
    borderWidth: 1,
    borderColor: colors.borderStrong,
  },
  wordmark: { fontFamily: fonts.display, fontSize: 19, color: colors.text },
  wordmarkSub: {
    fontFamily: fonts.mono,
    fontSize: 8.5,
    color: colors.primary,
    letterSpacing: 1.6,
    marginTop: -2,
  },
  actions: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  iconButton: {
    width: 38,
    height: 38,
    borderRadius: radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surfaceSoft,
    borderWidth: 1,
    borderColor: colors.border,
  },
  avatarRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingLeft: spacing.xs,
  },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
  },
  avatarText: { fontFamily: fonts.bodySemibold, fontSize: 15, color: colors.bgDeep },
});
