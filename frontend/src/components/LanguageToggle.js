/** Small EN / हि pill switch. Used pre-login (AuthHero) and in Profile. */

import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useLanguage } from '../i18n/LanguageContext';
import { LANGUAGES } from '../i18n/translations';
import { colors, fonts, radius } from '../theme/theme';

export default function LanguageToggle({ style }) {
  const { language, setLanguage } = useLanguage();

  return (
    <View style={[styles.row, style]}>
      {LANGUAGES.map((lang) => {
        const active = language === lang.code;
        return (
          <Pressable
            key={lang.code}
            onPress={() => setLanguage(lang.code)}
            accessibilityRole="button"
            accessibilityLabel={lang.name}
            style={[styles.pill, active && styles.pillActive]}
          >
            <Text style={[styles.pillText, active && styles.pillTextActive]}>{lang.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    backgroundColor: colors.surfaceSoft,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 3,
  },
  pill: {
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: radius.pill,
  },
  pillActive: { backgroundColor: colors.primary },
  pillText: { fontFamily: fonts.bodyMedium, fontSize: 12, color: colors.textMuted },
  pillTextActive: { color: colors.bgDeep },
});
