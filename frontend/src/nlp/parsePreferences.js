/**
 * Free-text practice-preference extraction.
 *
 * Deliberately a keyword/pattern matcher, not a call to a language model:
 * there is no LLM wired into this app (the "AI" everywhere else here is the
 * transparent, rule-based assessment/recommendation engines), and a fake
 * "AI understood you" claim would be worse than an honest, inspectable rule
 * set. Every match records the exact phrase that triggered it, so the
 * confirmation UI can show its work rather than asking for blind trust --
 * and nothing here ever touches the profile directly; the caller is
 * responsible for confirming before applying anything.
 */

const GOAL_KEYWORDS = {
  flexibility: ['flexib', 'stretch', 'limber'],
  strength: ['strength', 'strong', 'muscle', 'toning', 'tone up'],
  relaxation: ['relax', 'calm', 'unwind', 'peaceful'],
  stress_reduction: ['stress', 'anxiety', 'anxious'],
  mobility: ['mobility', 'mobile', 'range of motion'],
  general_fitness: ['general fitness', 'overall health', 'stay fit', 'get fit', 'fitness'],
  beginner_learning: ['learn the basics', 'learning the basics', 'new to yoga', 'just starting', 'basics'],
  balance: ['balance', 'stability', 'steadiness', 'steadier'],
};

const EXPERIENCE_KEYWORDS = {
  advanced: ['advanced', 'experienced', 'years of practice', 'years of yoga', 'expert'],
  intermediate: ['intermediate', 'some experience', 'comfortable with yoga', 'comfortable with poses'],
  beginner: ['beginner', 'new to yoga', 'never done yoga', 'just started', 'just starting', 'novice', "haven't done yoga"],
};

const FOCUS_KEYWORDS = {
  legs: ['legs', 'thighs', 'calves', 'quads'],
  core: ['core', 'abs', 'stomach', 'belly'],
  hips: ['hips', 'hip '],
  spine: ['spine', 'lower back', 'upper back', 'my back'],
  shoulders: ['shoulder'],
  hamstrings: ['hamstring'],
  posture: ['posture', 'slouch'],
  relaxation: ['relax', 'calm', 'unwind'],
};

/** Longest match first within each category, so "stress reduction" doesn't
 * get shadowed by a shorter unrelated keyword before it's tried. */
function sortedEntries(map) {
  return Object.entries(map)
    .flatMap(([id, phrases]) => phrases.map((phrase) => [id, phrase]))
    .sort((a, b) => b[1].length - a[1].length);
}

function findAll(text, map) {
  const found = new Map(); // id -> matched phrase (first hit wins)
  for (const [id, phrase] of sortedEntries(map)) {
    if (found.has(id)) continue;
    if (text.includes(phrase)) found.set(id, phrase);
  }
  return found;
}

function findFirst(text, map) {
  // Priority order matters here (e.g. "advanced" beats "beginner" if both
  // somehow appear), so entries are tried in the map's own declared order.
  for (const [id, phrases] of Object.entries(map)) {
    for (const phrase of phrases) {
      if (text.includes(phrase)) return { id, phrase };
    }
  }
  return null;
}

const DURATION_OPTIONS = [10, 15, 20, 30, 45];
const FREQUENCY_MIN = 1;
const FREQUENCY_MAX = 7;

function nearest(value, options) {
  return options.reduce((best, opt) => (Math.abs(opt - value) < Math.abs(best - value) ? opt : best));
}

/**
 * @param {string} text
 * @returns {{
 *   experience?: {value: string, matchedText: string},
 *   goals: Array<{value: string, matchedText: string}>,
 *   focus_areas: Array<{value: string, matchedText: string}>,
 *   preferred_duration?: {value: number, matchedText: string},
 *   practice_frequency?: {value: number, matchedText: string},
 *   age?: {value: number, matchedText: string},
 *   avoidMentions: Array<string>,
 * }}
 */
export function parsePreferences(rawText) {
  const text = ` ${(rawText ?? '').toLowerCase().replace(/\s+/g, ' ')} `;

  const goalHits = findAll(text, GOAL_KEYWORDS);
  const goals = [...goalHits.entries()].map(([value, matchedText]) => ({ value, matchedText }));

  const focusHits = findAll(text, FOCUS_KEYWORDS);
  const focus_areas = [...focusHits.entries()].map(([value, matchedText]) => ({ value, matchedText }));

  const experienceHit = findFirst(text, EXPERIENCE_KEYWORDS);
  const experience = experienceHit
    ? { value: experienceHit.id, matchedText: experienceHit.phrase }
    : undefined;

  const durationMatch = text.match(/(\d{1,3})\s*(?:minutes?|mins?|min)\b/);
  const preferred_duration = durationMatch
    ? {
        value: nearest(Number(durationMatch[1]), DURATION_OPTIONS),
        matchedText: durationMatch[0].trim(),
      }
    : undefined;

  const frequencyMatch = text.match(
    /(\d{1,2})\s*(?:times?|days?|sessions?)\s*(?:a|per|\/)\s*week/,
  );
  const practice_frequency = frequencyMatch
    ? {
        value: Math.min(FREQUENCY_MAX, Math.max(FREQUENCY_MIN, Number(frequencyMatch[1]))),
        matchedText: frequencyMatch[0].trim(),
      }
    : undefined;

  const ageMatch =
    text.match(/\bi(?:'m| am)\s*(\d{1,3})\b/) ??
    text.match(/\bage(?:d)?\s*(\d{1,3})\b/) ??
    text.match(/(\d{1,3})\s*years?\s*old/);
  const ageValue = ageMatch ? Number(ageMatch[1]) : null;
  const age =
    ageValue != null && ageValue >= 5 && ageValue <= 120
      ? { value: ageValue, matchedText: ageMatch[0].trim() }
      : undefined;

  // Deliberately does not try to guess *which* poses an injury makes unsafe
  // -- that is a judgement call this app has no basis to make from a phrase
  // like "bad knees". It only surfaces that something was mentioned, so the
  // confirmation UI can point the practitioner at the real "poses to skip"
  // picker instead of silently excluding poses on an unverified guess.
  const avoidMentions = [];
  const seenAvoidSpans = new Set();
  const injuryWord = '(?:injur\\w*|pain\\w*|hurts?|sore|problem\\w*|issue\\w*|surger\\w*)';
  const bodyPartWord = '(?:knee|back|shoulder|wrist|hip|ankle|neck|elbow)\\w*';
  // Ordinary phrasing goes either way ("knee pain" as often as "pain in my
  // knee"), so both orders are matched rather than just one.
  const injuryPatterns = [
    new RegExp(`\\b${injuryWord}\\b[^.!?]{0,60}\\b${bodyPartWord}`, 'g'),
    new RegExp(`\\b${bodyPartWord}\\b[^.!?]{0,60}\\b${injuryWord}`, 'g'),
  ];
  for (const pattern of injuryPatterns) {
    let m;
    while ((m = pattern.exec(text)) !== null) {
      const phrase = m[0].trim();
      if (!seenAvoidSpans.has(phrase)) {
        seenAvoidSpans.add(phrase);
        avoidMentions.push(phrase);
      }
    }
  }

  return { experience, goals, focus_areas, preferred_duration, practice_frequency, age, avoidMentions };
}
