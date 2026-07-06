import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Demo mode is toggled with DEMO=1 at build time (npm run build:demo).
// We inject it explicitly via `define` so the flag reliably compiles into
// the bundle regardless of Vite's .env loading behaviour.
const demo = process.env.DEMO === '1' || process.env.VITE_DEMO === '1'

export default defineConfig({
  plugins: [react()],
  define: {
    'import.meta.env.VITE_DEMO': JSON.stringify(demo ? '1' : '0'),
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
