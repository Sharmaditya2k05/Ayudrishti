/**
 * AyuDrishti - AI-powered personalised yoga assessment and adaptive guidance.
 *
 * Run the backend first (see the repository README), then:
 *   npm run web      full pipeline: camera + MediaPipe + Recharts
 *   npm run android  / npm run ios
 */

import React from 'react';
import { View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import Background from './src/components/Background';
import { AuthProvider } from './src/context/AuthContext';
import { LanguageProvider } from './src/i18n/LanguageContext';
import AppNavigator from './src/navigation/AppNavigator';
import { useAppFonts } from './src/theme/fonts';
import { colors } from './src/theme/theme';

export default function App() {
  // Fonts load asynchronously; the app renders regardless (system-font
  // fallback) so there is no blank splash while they fetch.
  useAppFonts();

  return (
    <SafeAreaProvider>
      <View style={{ flex: 1, backgroundColor: colors.bg }}>
        {/* One ambient backdrop behind the whole app, so every screen shares
            the same atmosphere as the landing page. */}
        <Background>
          <LanguageProvider>
            <AuthProvider>
              <StatusBar style="light" />
              <AppNavigator />
            </AuthProvider>
          </LanguageProvider>
        </Background>
      </View>
    </SafeAreaProvider>
  );
}
