// US recipient geography. International destinations live in their own tab, so
// this one answers a single question: which states does this funder already
// give in?
import type { FoundationDetailV5 } from '../../../lib/apiV5'
import { money } from '../../../lib/format'
import { Empty, SectionTitle } from './parts'

export default function GeographyTab({ data }: { data: FoundationDetailV5 }) {
  const states = data.states.filter((s) => s.dollars > 0)
  if (!states.length) {
    return <Empty>
      No US recipient states recorded — the filing either named no domestic
      recipients or gave no addresses for them.
      {data.countries.length > 0
        && ' This foundation’s giving appears in the International tab.'}
    </Empty>
  }
  const max = Math.max(...states.map((s) => s.dollars), 1)
  const total = states.reduce((sum, s) => sum + s.dollars, 0)
  return (
    <div>
      <SectionTitle note={`${money(total)} across ${states.length} `
        + `${states.length === 1 ? 'state' : 'states'}, from the recipient `
        + 'addresses in the filing. A funder that already gives in your state '
        + 'is a materially warmer prospect.'}>
        US recipients by state
      </SectionTitle>
      <div className="space-y-1.5 max-w-xl">
        {states.map((s) => (
          <div key={s.state} className="flex items-center gap-3 text-sm">
            <span className="w-8 text-muted tabular shrink-0">
              {s.state || '—'}
            </span>
            <div className="flex-1 h-3 bg-line/40 rounded overflow-hidden">
              <div className="h-full bg-scorehigh/70 rounded"
                style={{ width: `${(s.dollars / max) * 100}%` }} />
            </div>
            <span className="w-20 text-right tabular font-medium shrink-0">
              {money(s.dollars)}
            </span>
            <span className="w-12 text-right text-[11px] text-muted shrink-0 tabular">
              {Math.round((s.dollars / total) * 100)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
