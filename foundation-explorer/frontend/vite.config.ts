import { existsSync, readFileSync, statSync } from 'node:fs'
import { join, normalize } from 'node:path'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

// Demo mode is toggled with DEMO=1 at build time (npm run build:demo).
// We inject it explicitly via `define` so the flag reliably compiles into
// the bundle regardless of Vite's .env loading behaviour.
const demo = process.env.DEMO === '1' || process.env.VITE_DEMO === '1'

// In production, nginx mounts the marketing site at /website. The dev server
// knows nothing about it, so the sidebar's Website link fell through Vite's
// SPA fallback to index.html, React Router found no matching route, and the
// user got the app's "This page couldn't load" boundary -- which reads like a
// bug in the product rather than a path that only exists on the server.
//
// This serves the same static export locally when it has been built, and
// otherwise says plainly what is missing and how to build it.
const WEBSITE_OUT = process.env.WEBSITE_OUT
  ?? '../../../NonProfits/FindChristianFundersWebsite/out'

function marketingSite(): Plugin {
  return {
    name: 'serve-marketing-site',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = (req.url ?? '').split('?')[0]
        if (!url.startsWith('/website')) return next()

        const root = join(server.config.root, WEBSITE_OUT)
        if (!existsSync(root)) {
          res.statusCode = 503
          res.setHeader('Content-Type', 'text/html')
          res.end(`<!doctype html><meta charset="utf-8">
<title>Marketing site not built</title>
<div style="font:16px/1.6 system-ui;max-width:40rem;margin:15vh auto;padding:0 1.5rem">
<h1 style="font-size:1.3rem">The marketing site isn't built locally</h1>
<p>In production nginx serves this from <code>/var/www/fcf/website</code>.
The dev server needs a local copy:</p>
<pre style="background:#f4f2ee;padding:1rem;overflow-x:auto">cd ${WEBSITE_OUT.replace(/\/out$/, '')}
npm run build:review</pre>
<p>Then reload. Set <code>WEBSITE_OUT</code> if your checkout is elsewhere.</p>
<p><a href="/">Back to the app</a></p></div>`)
          return
        }

        // Strip the /website prefix, then resolve exactly as nginx does:
        // a file, or a directory's index.html, or the export's 404 page.
        const rel = url.slice('/website'.length) || '/'
        // normalize() collapses any ../ before it can escape the export.
        const target = normalize(join(root, rel))
        if (!target.startsWith(normalize(root))) return next()

        let file = target
        if (existsSync(file) && statSync(file).isDirectory()) {
          file = join(file, 'index.html')
        }
        if (!existsSync(file)) {
          const notFound = join(root, '404.html')
          if (!existsSync(notFound)) return next()
          res.statusCode = 404
          file = notFound
        }

        const ext = file.slice(file.lastIndexOf('.'))
        const types: Record<string, string> = {
          '.html': 'text/html', '.css': 'text/css',
          '.js': 'text/javascript', '.json': 'application/json',
          '.svg': 'image/svg+xml', '.txt': 'text/plain',
          '.woff2': 'font/woff2', '.png': 'image/png', '.ico': 'image/x-icon',
        }
        res.setHeader('Content-Type', types[ext] ?? 'application/octet-stream')
        res.end(readFileSync(file))
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), marketingSite()],
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
