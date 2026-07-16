import { Link } from 'react-router-dom'
import { Wrench } from 'lucide-react'

// Placeholder for pages still wired to the retired v1 API. Kept in the nav so
// nothing crashes while they are migrated to v5.
export default function NotRewired({ name }: { name: string }) {
  return (
    <div className="max-w-xl mx-auto mt-24 text-center">
      <Wrench size={32} className="mx-auto text-muted mb-4" />
      <h1 className="font-display text-2xl font-semibold text-primary mb-2">
        {name}
      </h1>
      <p className="text-sm text-muted">
        This page has not yet been rewired to the v5 API. In the meantime, the
        {' '}<Link to="/foundations" className="text-primary underline">
          Foundations explorer
        </Link>{' '}
        covers filtering, evidence, and export against the new data.
      </p>
    </div>
  )
}
