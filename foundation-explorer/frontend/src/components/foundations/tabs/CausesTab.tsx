import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, ExternalLink } from 'lucide-react'
import { NTEE_MAJORS } from '../../../lib/apiV5'
import { money, num, titleCase } from '../../../lib/format'
import { TraditionChip } from '../V5Chips'
import { SectionTitle } from './parts'

/** The Causes tab: every cause area this foundation funded, expandable to
 *  the recipients inside each.
 *
 *  Three deliberate touches beyond the ask:
 *   - each cause carries its per-STATE split, because "Education — NC, VA"
 *     is the conjoint fact Emily prospects on, shown here in reverse;
 *   - every cause and every state chip deep-links back into the Foundations
 *     page pre-filtered ("find more funders doing this, there") — the detail
 *     page becomes a springboard, not a dead end;
 *   - coverage is stated up front. Codes exist only for grantees matched to
 *     an IRS record, and pretending otherwise would let a thin profile read
 *     as a complete one.
 */

type CauseRecipient = {
  ntee: string; entity_id: string; name: string; tradition: string | null
  city: string | null; org_state: string | null
  dollars: number; grants: number
}
type CauseMajor = {
  major: string; dollars: number; grants: number; recipient_count: number
  states: { state: string; dollars: number }[]
  recipients: CauseRecipient[]
}
type CausesResponse = {
  paid_2324: number; coded_dollars: number; coded_recipients: number
  majors: CauseMajor[]
}

const LABELS = new Map(NTEE_MAJORS)

async function fetchCauses(ein: string): Promise<CausesResponse> {
  const res = await fetch(`/api/v5/foundations/${ein}/causes`)
  if (!res.ok) throw new Error(`causes: ${res.status}`)
  return res.json()
}

export default function CausesTab({ ein }: { ein: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['v5causes', ein],
    queryFn: () => fetchCauses(ein),
    staleTime: 5 * 60_000,
  })
  const [open, setOpen] = useState<string | null>(null)

  if (isLoading) {
    return <div className="text-sm text-muted">Reading the filings…</div>
  }
  if (!data) return null

  if (data.majors.length === 0) {
    return (
      <div className="max-w-2xl text-sm text-muted">
        None of this foundation&apos;s grantees could be matched to an IRS
        record carrying a cause code, so there is no cause-area breakdown to
        show — that is a limit of the public data, not a statement about the
        foundation.
      </div>
    )
  }

  const max = Math.max(...data.majors.map((m) => m.dollars))
  const pct = data.paid_2324 > 0
    ? Math.round((100 * data.coded_dollars) / data.paid_2324) : 0

  return (
    <div>
      <SectionTitle note={`Cause areas come from IRS NTEE codes, which exist
        only for grantees matched to an IRS record: ${money(
        data.coded_dollars)} of this foundation's ${money(data.paid_2324)}
        paid (${pct}%), across ${num(data.coded_recipients)} coded
        recipients. The rest of its giving is not "other" — it is simply
        uncoded.`}>
        Cause areas
      </SectionTitle>

      <div className="mt-3 space-y-1.5">
        {data.majors.map((m) => {
          const isOpen = open === m.major
          const label = LABELS.get(m.major) ?? m.major
          return (
            <div key={m.major}
              className={`rounded-lg border ${isOpen
                ? 'border-honey-300 bg-honey-50/40' : 'border-line/70'}`}>
              <button
                onClick={() => setOpen(isOpen ? null : m.major)}
                className="flex w-full items-center gap-3 px-3 py-2 text-left">
                {isOpen ? <ChevronDown size={14} className="shrink-0 text-muted" />
                  : <ChevronRight size={14} className="shrink-0 text-muted" />}
                <span className="w-44 shrink-0 truncate text-sm text-ink"
                  title={`${label} (NTEE ${m.major})`}>
                  {label}
                </span>
                <span className="hidden flex-1 sm:block">
                  <span className="block h-2 rounded-sm bg-primary/70"
                    style={{ width: `${Math.max(2,
                      (100 * m.dollars) / max)}%` }} />
                </span>
                <span className="w-20 shrink-0 text-right tabular text-sm
                  font-medium">
                  {money(m.dollars)}
                </span>
                <span className="w-16 shrink-0 text-right text-xs text-muted">
                  {num(m.recipient_count)} org{m.recipient_count === 1 ? '' : 's'}
                </span>
              </button>

              {isOpen && (
                <div className="border-t border-line/60 px-4 pb-3 pt-2">
                  {m.states.length > 0 && (
                    <div className="mb-2 flex flex-wrap items-center gap-1.5">
                      <span className="text-[11px] text-muted">Where:</span>
                      {m.states.map((s) => (
                        <a key={s.state}
                          href={`/foundations?ntee=${m.major}&gives_to_state=${s.state}`}
                          title={`${money(s.dollars)} of ${label.toLowerCase()} giving in ${s.state} — click to find every funder doing this there`}
                          className="rounded-full border border-honey-300
                            bg-honey-50 px-2 py-0.5 text-[11px] text-honey-800
                            hover:bg-honey-100">
                          {s.state} · {money(s.dollars)}
                        </a>
                      ))}
                    </div>
                  )}

                  <table className="w-full text-sm">
                    <tbody>
                      {m.recipients.map((r) => (
                        <tr key={r.entity_id}
                          className="border-b border-line/40 last:border-0">
                          <td className="py-1.5 pr-3">
                            <span className="text-ink">{titleCase(r.name)}</span>
                            <span className="ml-2 text-xs text-muted">
                              {r.city ? `${titleCase(r.city)}, ` : ''}
                              {r.org_state ?? ''}
                            </span>
                          </td>
                          <td className="w-14 pr-2 text-right">
                            <span className="rounded bg-canvas px-1 py-0.5
                              font-mono text-[10px] text-muted"
                              title={`Exact NTEE code ${r.ntee}`}>
                              {r.ntee}
                            </span>
                          </td>
                          <td className="w-16 pr-2 text-right">
                            {r.tradition && (
                              <TraditionChip tradition={r.tradition} />
                            )}
                          </td>
                          <td className="w-20 py-1.5 text-right tabular
                            whitespace-nowrap">
                            {money(r.dollars)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {m.recipient_count > m.recipients.length && (
                    <div className="mt-1.5 text-[11px] text-muted">
                      Largest {m.recipients.length} of{' '}
                      {num(m.recipient_count)} shown.
                    </div>
                  )}

                  <a href={`/foundations?ntee=${m.major}`}
                    className="mt-2 inline-flex items-center gap-1 text-xs
                      text-primary underline underline-offset-2
                      hover:text-honey-700">
                    Find every foundation funding {label.toLowerCase()}
                    <ExternalLink size={11} />
                  </a>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
