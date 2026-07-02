import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#1a3a2e',
        accent: '#c9a961',
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
