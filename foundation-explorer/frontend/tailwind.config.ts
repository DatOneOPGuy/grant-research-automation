import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#1a3a2e',
        accent: '#c9a961',
        // Honey. 400 is the brand value; the rest is a ramp around it, because
        // #E0AC69 itself is a background colour -- it fails contrast as text on
        // anything light (2.1:1 on canvas), so text and icons use 700/800 and
        // the flat value is kept for fills, rules and borders.
        honey: {
          50: '#fdf8f2',
          100: '#faedde',
          200: '#f2d8ba',
          300: '#e9c294',
          400: '#e0ac69',
          500: '#d2934a',
          600: '#b87a36',
          700: '#94602b',
          800: '#6f4820',
        },
        canvas: '#faf8f5',
        surface: '#ffffff',
        ink: '#1a1a1a',
        muted: '#4a4a4a',
        line: '#e5e0d5',
        scorehigh: '#2d5a3d',
        scoremid: '#b8860b',
        scorelow: '#9ca3af',
      },
      fontFamily: {
        display: ['Fraunces', 'Georgia', 'serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
} satisfies Config
