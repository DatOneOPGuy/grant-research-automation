import { Link, useRouteError } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import { STATIC_MODE } from '../../lib/apiV5'

// Without this, a single unexpected null anywhere in a page replaces the whole
// application with React Router's raw stack trace -- which is how a missing
// recipient record took down the entire review build. A page that cannot load
// should cost the reviewer that page, not the product.
export default function RouteError() {
  const error = useRouteError()
  const message = error instanceof Error ? error.message : String(error ?? '')
  return (
    <div className="min-h-screen flex items-start justify-center px-6 py-24">
      <div className="max-w-xl">
        <div className="flex items-center gap-2 text-scoremid mb-3">
          <AlertTriangle size={20} />
          <h1 className="font-display text-2xl font-semibold">
            This page couldn’t load
          </h1>
        </div>
        <p className="text-sm text-muted mb-4">
          {STATIC_MODE
            ? 'This is a sampled review build, so some records are not '
              + 'included. The rest of the app is unaffected.'
            : 'Something went wrong rendering this page. The rest of the '
              + 'app is unaffected.'}
        </p>
        <div className="flex gap-3 text-sm">
          <Link to="/" className="px-3 py-1.5 rounded bg-primary text-white">
            Back to dashboard
          </Link>
          <button onClick={() => window.history.back()}
            className="px-3 py-1.5 rounded border border-line hover:bg-canvas">
            Go back
          </button>
        </div>
        {message && (
          <details className="mt-6 text-xs text-muted">
            <summary className="cursor-pointer">Technical detail</summary>
            <pre className="mt-2 whitespace-pre-wrap break-words">{message}</pre>
          </details>
        )}
      </div>
    </div>
  )
}
