// How much this foundation's Christian figure can actually be stood behind.
// The distinction that matters: evidence that can be independently checked
// (IRS codes, denominational rulings, the recipient's own mission statement)
// versus evidence inferred from a name alone.
import {
  METHODS, methodIsIndependent, methodLabel, type FoundationDetailV5,
} from '../../../lib/apiV5'
import { money } from '../../../lib/format'
import { BarRow, Empty, SectionTitle, Stat } from './parts'

export default function EvidenceTab({ data }: { data: FoundationDetailV5 }) {
  const f = data.foundation
  const rows = data.methods.filter((m) => m.dollars > 0)
  const max = Math.max(...rows.map((m) => m.dollars), 1)
  const christianRows = rows.filter((m) => m.christian_dollars > 0)
  const verified = christianRows
    .filter((m) => methodIsIndependent(m.method))
    .reduce((sum, m) => sum + m.christian_dollars, 0)
  const nameOnly = christianRows
    .filter((m) => !methodIsIndependent(m.method))
    .reduce((sum, m) => sum + m.christian_dollars, 0)
  const totalChristian = verified + nameOnly
  const pctVerified = totalChristian > 0
    ? Math.round((verified / totalChristian) * 100) : null

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-2">
        <Stat label="Coverage" value={`${Math.round(f.coverage_pct)}%`}
          hint={`${f.coverage_band} — share of giving we could classify`} />
        <Stat label="Independently verified"
          value={money(verified)}
          hint={pctVerified === null ? 'no Christian giving found'
            : `${pctVerified}% of Christian dollars`} />
        <Stat label="Name evidence only" value={money(nameOnly)}
          hint={pctVerified === null ? '—' : `${100 - pctVerified}% of Christian dollars`} />
      </div>

      {totalChristian > 0 && (
        <div className={`rounded-md px-3 py-2 text-xs leading-snug ${
          pctVerified !== null && pctVerified >= 50
            ? 'bg-scorehigh/10 text-ink' : 'bg-accent/15 text-ink'}`}>
          {pctVerified !== null && pctVerified >= 50 ? (
            <>Most of this foundation’s Christian giving rests on evidence that
              can be checked against an independent source. This is a claim you
              can take into a conversation.</>
          ) : (
            <>Most of this foundation’s Christian giving rests on recipient
              names alone. The IRS filing often supplies only a name and a city,
              so there is nothing to cross-check against. Treat this as a lead
              worth verifying, not an established fact.</>
          )}
        </div>
      )}

      <div>
        <SectionTitle note="Every dollar this foundation gave, grouped by the
          strongest evidence we hold about the recipient. The darker segment is
          the part classified as Christian.">
          Evidence behind the classification
        </SectionTitle>
        {rows.length ? (
          <div className="space-y-1.5 max-w-xl">
            {rows.map((m) => (
              <BarRow key={m.method} label={methodLabel(m.method)}
                dollars={m.dollars} christian={m.christian_dollars} max={max}
                sub={`${m.recipients.toLocaleString()} orgs`}
                title={METHODS.find((x) => x.key === m.method)?.hint} />
            ))}
          </div>
        ) : <Empty>No classified recipients.</Empty>}
      </div>

      <div>
        <SectionTitle>What each basis means</SectionTitle>
        <dl className="space-y-1.5 max-w-xl">
          {METHODS.filter((m) => rows.some((r) => r.method === m.key))
            .map((m) => (
              <div key={m.key} className="text-xs">
                <dt className="font-medium text-ink inline">{m.label}</dt>
                <dd className="text-muted inline"> — {m.hint}</dd>
              </div>
            ))}
        </dl>
      </div>

      {f.auth_christian_dollars > 0 && (
        <div>
          <SectionTitle note="A stricter reading: Christian dollars carrying
            IRS-derived or denominational evidence, over the same total giving.
            It can only be lower than the headline figure — never higher.">
            High-confidence view
          </SectionTitle>
          <div className="text-sm">
            <span className="tabular font-semibold text-ink">
              {money(f.auth_christian_dollars)}
            </span>
            <span className="text-muted">
              {' '}of {money(f.christian_dollars)} Christian giving
              {f.pct_christian_auth !== null
                && ` (${f.pct_christian_auth}% of classified giving)`}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
