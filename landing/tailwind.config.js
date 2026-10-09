/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        // Loaded via <link> tags in index.html; the same three faces the app
        // uses, so the two surfaces share one typographic voice.
        serif: ['"Instrument Serif"', 'Georgia', 'serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['"Space Grotesk"', 'ui-monospace', 'monospace'],
      },
      colors: {
        // The app's violet accent, so accents match across both surfaces.
        accent: '#C6A8FF',
      },
    },
  },
  plugins: [],
};
