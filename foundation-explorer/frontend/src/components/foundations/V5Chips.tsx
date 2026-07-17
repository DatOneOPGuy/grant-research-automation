import { Badge } from '../ui/primitives'
import { traditionLabel } from '../../lib/apiV5'

// Honesty markers: coverage band, identity status, tradition (with method +
// confidence in tooltip), DAF pass-through. These stay visible everywhere.

export function CoverageChip({ band, pct }: {
  band: string | null | undefined; pct?: number | null
}) {
  const label = pct != null ? `${band} · ${Math.round(pct)}%` : band || '—'
  const title = 'Coverage = % of this foundation’s paid dollars with a classified recipient'
  if (band === 'High') {
    return <Badge className="bg-green-50 text-scorehigh whitespace-nowrap"
      ><span title={title}>{label}</span></Badge>
  }
  if (band === 'Moderate') {
    return <Badge className="bg-amber-50 text-scoremid whitespace-nowrap"
      ><span title={title}>{label}</span></Badge>
  }
  return <Badge className="bg-gray-100 text-scorelow whitespace-nowrap"
    ><span title={title}>{label}</span></Badge>
}

const CHRISTIAN_SET = new Set(['evangelical_protestant', 'catholic',
  'orthodox_christian', 'christian_unspecified', 'any_christian'])

export function TraditionChip({ tradition, method, confidence, reason }: {
  tradition: string | null
  method?: string | null
  confidence?: number | null
  reason?: string | null
}) {
  const label = traditionLabel(tradition)
  const parts: string[] = []
  if (method) parts.push(`method: ${method}`)
  if (confidence != null) parts.push(`confidence: ${confidence}`)
  if (reason) parts.push(`why: ${reason}`)
  const title = parts.join(' · ') || undefined
  let cls = 'bg-gray-100 text-scorelow'
  if (tradition && CHRISTIAN_SET.has(tradition)) cls = 'bg-green-50 text-scorehigh'
  else if (tradition === 'secular') cls = 'bg-slate-100 text-slate-600'
  else if (tradition && tradition !== 'unclassified') cls = 'bg-blue-50 text-blue-700'
  return (
    <Badge className={`${cls} whitespace-nowrap`}>
      <span title={title}>{label}</span>
    </Badge>
  )
}

// Identity resolution status — shown honestly, unresolved is not hidden.
export function IdentityChip({ status }: { status: string | null }) {
  if (status === 'matched') {
    return <Badge className="bg-green-50 text-scorehigh">matched</Badge>
  }
  return <Badge className="bg-amber-50 text-scoremid">
    {status || 'unresolved'}
  </Badge>
}

export function DafChip() {
  return <Badge className="bg-purple-100 text-purple-700 whitespace-nowrap">
    DAF pass-through
  </Badge>
}
