import React from 'react';
import { NavigationContainer, DefaultTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { Loading } from '../components/common';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../i18n/LanguageContext';
import AssistantScreen from '../screens/AssistantScreen';
import HomeScreen from '../screens/HomeScreen';
import LandingScreen from '../screens/LandingScreen';
import LoginScreen from '../screens/LoginScreen';
import OnboardingScreen from '../screens/OnboardingScreen';
import PracticeScreen from '../screens/PracticeScreen';
import ProfileScreen from '../screens/ProfileScreen';
import ProgressScreen from '../screens/ProgressScreen';
import RecommendationsScreen from '../screens/RecommendationsScreen';
import SessionSummaryScreen from '../screens/SessionSummaryScreen';
import { colors, fonts } from '../theme/theme';

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

const navTheme = {
  ...DefaultTheme,
  dark: true,
  colors: {
    ...DefaultTheme.colors,
    primary: colors.primary,
    // Transparent so the app-wide ambient Background shows through every
    // navigator surface instead of each screen painting its own flat colour.
    background: 'transparent',
    card: 'transparent',
    text: colors.text,
    border: colors.border,
    notification: colors.primary,
  },
};

const TAB_ICONS = {
  Home: 'home-variant-outline',
  Recommendations: 'clipboard-list-outline',
  Progress: 'chart-line',
  Assistant: 'robot-outline',
  Profile: 'account-circle-outline',
};

function TabIcon({ name, color }) {
  // react-navigation's bottom tab bar renders a focused AND unfocused icon
  // stacked in the same spot for its crossfade transition -- swapping glyph
  // *names* between the two (e.g. outline vs filled) leaves both visible at
  // once. Active/inactive is communicated by colour alone instead.
  return <MaterialCommunityIcons name={TAB_ICONS[name] ?? 'circle-outline'} size={22} color={color} />;
}

function MainTabs() {
  const { t } = useLanguage();
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerStyle: { backgroundColor: 'transparent' },
        headerTitleStyle: { color: colors.text, fontFamily: fonts.display, fontSize: 20 },
        headerShadowVisible: false,
        headerTransparent: true,
        tabBarStyle: {
          // Translucent bar so the ambient glow bleeds through it.
          backgroundColor: colors.bgDeep,
          borderTopColor: colors.border,
          height: 64,
          paddingBottom: 8,
          paddingTop: 8,
        },
        tabBarLabelStyle: { fontFamily: fonts.mono, fontSize: 10, letterSpacing: 0.6 },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textFaint,
        tabBarIcon: ({ color }) => <TabIcon name={route.name} color={color} />,
      })}
    >
      <Tab.Screen
        name="Home"
        component={HomeScreen}
        options={{ headerShown: false, title: t('tabs.home') }}
      />
      <Tab.Screen
        name="Recommendations"
        component={RecommendationsScreen}
        options={{ headerShown: false, title: t('tabs.plan') }}
      />
      <Tab.Screen
        name="Progress"
        component={ProgressScreen}
        options={{ headerShown: false, title: t('tabs.progress') }}
      />
      <Tab.Screen
        name="Assistant"
        component={AssistantScreen}
        options={{ headerShown: false, title: t('tabs.assistant') }}
      />
      <Tab.Screen
        name="Profile"
        component={ProfileScreen}
        options={{ headerShown: false, title: t('tabs.profile') }}
      />
    </Tab.Navigator>
  );
}

export default function AppNavigator() {
  const { isAuthenticated, needsOnboarding, loading } = useAuth();
  const { t } = useLanguage();

  if (loading) return <Loading label="Starting AyuDrishti..." />;

  return (
    <NavigationContainer theme={navTheme}>
      <Stack.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: 'transparent' },
          headerTransparent: true,
          headerTitleStyle: { color: colors.text },
          headerTintColor: colors.primary,
          headerShadowVisible: false,
          contentStyle: { backgroundColor: 'transparent' },
        }}
      >
        {!isAuthenticated ? (
          <>
            <Stack.Screen
              name="Landing"
              component={LandingScreen}
              options={{ headerShown: false }}
            />
            <Stack.Screen
              name="Login"
              component={LoginScreen}
              options={{ headerShown: false }}
            />
            <Stack.Screen
              name="Onboarding"
              component={OnboardingScreen}
              options={{ title: t('onboarding.getStarted') }}
            />
          </>
        ) : needsOnboarding ? (
          // A profile without goals cannot produce a meaningful plan, so
          // onboarding is the only reachable screen until it is completed.
          <Stack.Screen
            name="Onboarding"
            component={OnboardingScreen}
            options={{ title: t('onboarding.createAccountTitle'), headerBackVisible: false }}
          />
        ) : (
          <>
            <Stack.Screen name="Main" component={MainTabs} options={{ headerShown: false }} />
            <Stack.Screen
              name="Practice"
              component={PracticeScreen}
              options={{ title: t('practice.title'), headerBackTitle: t('practice.endBackTitle') }}
            />
            <Stack.Screen
              name="SessionSummary"
              component={SessionSummaryScreen}
              options={{ title: t('sessionSummary.title'), headerBackVisible: false }}
            />
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
