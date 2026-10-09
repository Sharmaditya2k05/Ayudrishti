/**
 * Font loading.
 *
 * Registers the Instrument Serif / Inter / Space Grotesk faces under the names
 * the theme's `fonts` map expects. Loading is asynchronous, so `useAppFonts`
 * reports readiness -- but the app renders immediately either way: until the
 * custom faces arrive, React Native falls back to the platform serif/sans/mono,
 * so there is never a blank screen, only a brief swap.
 */

import { useFonts } from 'expo-font';
import {
  InstrumentSerif_400Regular,
  InstrumentSerif_400Regular_Italic,
} from '@expo-google-fonts/instrument-serif';
import {
  Inter_400Regular,
  Inter_500Medium,
  Inter_600SemiBold,
} from '@expo-google-fonts/inter';
import {
  SpaceGrotesk_400Regular,
  SpaceGrotesk_500Medium,
} from '@expo-google-fonts/space-grotesk';

export const FONT_MAP = {
  InstrumentSerif: InstrumentSerif_400Regular,
  InstrumentSerif_Italic: InstrumentSerif_400Regular_Italic,
  Inter: Inter_400Regular,
  Inter_Medium: Inter_500Medium,
  Inter_SemiBold: Inter_600SemiBold,
  SpaceGrotesk: SpaceGrotesk_400Regular,
  SpaceGrotesk_Medium: SpaceGrotesk_500Medium,
};

/** @returns {boolean} whether the custom faces have finished loading. */
export function useAppFonts() {
  const [loaded, error] = useFonts(FONT_MAP);
  // Treat a load error the same as "loaded": we render with fallback fonts
  // rather than blocking the whole app on a font that failed to fetch.
  return loaded || Boolean(error);
}
