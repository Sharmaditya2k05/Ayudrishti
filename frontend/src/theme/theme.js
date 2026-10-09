/**
 * AyuDrishti design system.
 *
 * A calm, low-light palette: a near-black forest backdrop, sage hairline
 * borders, and a mint-green accent, with a serif display face for headings
 * and a mono face for the small uppercase labels. It is tuned to be read
 * from a mat in a dim room, and to feel like one continuous product from the
 * marketing page through to the live session.
 *
 * The same tokens back the landing page (see ../../landing), so the two
 * surfaces stay in visual lockstep.
 */

export const colors = {
  // Backdrop: near-black with a green cast, layered lighter for surfaces.
  bg: '#0A1310',
  bgDeep: '#070D0A',
  surface: '#101E18',
  surfaceRaised: '#16281F',
  surfaceSoft: 'rgba(120, 210, 160, 0.05)',

  // Hairline borders are sage at very low alpha -- they read as edges of
  // light rather than as drawn lines.
  border: 'rgba(150, 220, 180, 0.13)',
  borderStrong: 'rgba(150, 220, 180, 0.24)',

  // Mint-green accent family.
  primary: '#4ADE80',
  primaryBright: '#6EE7A0',
  primaryDeep: '#16A34A',
  primarySoft: 'rgba(74, 222, 128, 0.14)',
  primaryFaint: 'rgba(74, 222, 128, 0.08)',

  text: '#F3FBF6',
  textMuted: '#A9C4B4',
  textFaint: '#6E8A7B',

  // Semantic scoring colours. "good" sits apart from the brand green so a
  // strong score doesn't read as merely "the accent colour" -- it needed to
  // stay its own signal even after the app moved onto a green identity.
  good: '#7FE0B8',
  goodSoft: 'rgba(127, 224, 184, 0.14)',
  warn: '#F0C987',
  warnSoft: 'rgba(240, 201, 135, 0.14)',
  bad: '#F1889F',
  badSoft: 'rgba(241, 136, 159, 0.14)',
  info: '#8FC9E8',

  // Skeleton overlay on the camera preview.
  skeleton: '#7FE0B8',
  skeletonFlagged: '#F1889F',

  // Ambient background glows.
  glowPrimary: 'rgba(74, 222, 128, 0.26)',
  glowSecondary: 'rgba(45, 140, 150, 0.16)',
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

export const radius = {
  sm: 10,
  md: 16,
  lg: 22,
  pill: 999,
};

/*
 * Font family names.
 *
 * These match the fonts registered in ./fonts.js. If font loading fails or is
 * still in flight, the values fall back to platform serif/sans/mono, so text
 * always renders -- it simply starts in a system face and swaps in.
 */
export const fonts = {
  display: 'InstrumentSerif', // headings
  displayItalic: 'InstrumentSerif_Italic',
  body: 'Inter', // body copy
  bodyMedium: 'Inter_Medium',
  bodySemibold: 'Inter_SemiBold',
  mono: 'SpaceGrotesk', // eyebrows, labels, numbers
  monoMedium: 'SpaceGrotesk_Medium',
};

/*
 * Type scale.
 *
 * Headings use the serif display face at a light weight with tight tracking --
 * the editorial voice. Eyebrows and stat numbers use the mono face with wide
 * uppercase tracking. Body stays in Inter.
 */
export const typography = {
  display: { fontFamily: fonts.display, fontSize: 40, color: colors.text, letterSpacing: -0.5 },
  title: { fontFamily: fonts.display, fontSize: 28, color: colors.text, letterSpacing: -0.3 },
  heading: { fontFamily: fonts.display, fontSize: 21, color: colors.text, letterSpacing: -0.2 },
  serifLead: { fontFamily: fonts.display, fontSize: 18, color: colors.textMuted },

  body: { fontFamily: fonts.body, fontSize: 15, color: colors.text, lineHeight: 22 },
  bodyMuted: { fontFamily: fonts.body, fontSize: 15, color: colors.textMuted, lineHeight: 22 },
  caption: { fontFamily: fonts.body, fontSize: 13, color: colors.textMuted, lineHeight: 18 },

  // Mono eyebrow: the small uppercase kicker above a heading.
  eyebrow: {
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.primary,
    letterSpacing: 2,
    textTransform: 'uppercase',
  },
  label: {
    fontFamily: fonts.mono,
    fontSize: 11,
    color: colors.textFaint,
    letterSpacing: 1.6,
    textTransform: 'uppercase',
  },
  // Big mono figure, e.g. a stat value or the score in a ring.
  stat: { fontFamily: fonts.mono, fontSize: 30, color: colors.text, letterSpacing: -0.5 },
};

/** Colour for a 0-100 score, shared by rings, bars and charts. */
export function scoreColor(score) {
  if (score === null || score === undefined) return colors.textFaint;
  if (score >= 85) return colors.good;
  if (score >= 70) return colors.warn;
  return colors.bad;
}

/** Colour for an alignment indicator status from the assessment API. */
export function statusColor(status) {
  switch (status) {
    case 'good':
      return colors.good;
    case 'adjust':
      return colors.warn;
    case 'off':
      return colors.bad;
    default:
      return colors.textFaint;
  }
}

export const DIFFICULTY_LABELS = {
  beginner: 'Beginner',
  intermediate: 'Intermediate',
  advanced: 'Advanced',
};

export const GOAL_OPTIONS = [
  { id: 'flexibility', label: 'Flexibility' },
  { id: 'strength', label: 'Strength' },
  { id: 'relaxation', label: 'Relaxation' },
  { id: 'stress_reduction', label: 'Stress reduction' },
  { id: 'mobility', label: 'Mobility' },
  { id: 'general_fitness', label: 'General fitness' },
  { id: 'beginner_learning', label: 'Learning the basics' },
  { id: 'balance', label: 'Balance' },
];

export const FOCUS_OPTIONS = [
  { id: 'legs', label: 'Legs' },
  { id: 'core', label: 'Core' },
  { id: 'hips', label: 'Hips' },
  { id: 'spine', label: 'Spine' },
  { id: 'shoulders', label: 'Shoulders' },
  { id: 'hamstrings', label: 'Hamstrings' },
  { id: 'posture', label: 'Posture' },
  { id: 'relaxation', label: 'Relaxation' },
];

export const EXPERIENCE_OPTIONS = [
  { id: 'beginner', label: 'Beginner', hint: 'New to yoga or returning after a break' },
  { id: 'intermediate', label: 'Intermediate', hint: 'Comfortable with common asanas' },
  { id: 'advanced', label: 'Advanced', hint: 'Years of regular practice' },
];
