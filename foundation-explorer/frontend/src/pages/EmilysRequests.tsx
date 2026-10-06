import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Download, MessageSquareQuote } from 'lucide-react'
import DetailPanel from '../components/foundations/DetailPanel'
import { StatusPill } from '../components/ui/primitives'
import { money, num, titleCase } from '../lib/format'

/** Emily's Custom Requests — the running log of asks from the field, each
 *  answered as a LIVE query, not a pasted spreadsheet. When the data
 *  refreshes, every answer here refreshes with it; the date on each entry
 *  is when it was asked, not when the numbers were true.
 *
 *  To add a request: give it an endpoint under /api/v5/custom/ and a card
 *  here. The asks themselves have repeatedly become product features
 *  (international benchmark, conjoint NTEE x state), so this page is also
 *  where features audition.
 */

type CampFunder = {
  ein: string; name: string; city: string | null; state: string | null
  application_status: string | null; website: string | null
  dollars: number; camp_count: number; examples: string | null
}
type CampResponse = {
  asked: string; camp_orgs: number; camp_dollars: number
  total_funders: number; funders: CampFunder[]
}

async function fetchCampFunders(): Promise<CampResponse> {
  const res = await fetch('/api/v5/custom/camp-funders')
  if (!res.ok) throw new Error(`camp-funders: ${res.status}`)
  return res.json()
}

export default function EmilysRequests() {
  const [selected, setSelected] = useState<string | null>(null)
  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="font-display text-3xl font-semibold text-primary">
        Emily&apos;s Custom Requests
      </h1>
      <p className="mt-1 mb-6 max-w-2xl text-sm text-muted">
        Questions from the field, answered with live data — these numbers
        recompute from the current database every time the page loads.
        Several earlier asks became product features (the International
        filter, cause area × state); this page is where the next ones
        audition.
      </p>

      <CampFundersRequest onOpen={setSelected} />

      {selected && (
        <DetailPanel ein={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}

function CampFundersRequest({ onOpen }: { onOpen: (ein: string) => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ['campFunders'],
    queryFn: fetchCampFunders,
    staleTime: 10 * 60_000,
  })
  const [shown, setShown] = useState(50)

  const exportCsv = () => {
    if (!data) return
    const esc = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`
    const lines = [
      ['Foundation', 'City', 'State', 'Applications', 'Website',
        '$ to camp orgs', '# camp orgs', 'Example camps', 'EIN']
        .map(esc).join(','),
      ...data.funders.map((f) => [
        titleCase(f.name), f.city ? titleCase(f.city) : '', f.state ?? '',
        f.application_status ?? '', f.website ?? '', f.dollars,
        f.camp_count, f.examples ?? '', f.ein,
      ].map(esc).join(',')),
    ]
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'camp_funders.csv'
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <div className="rounded-xl border border-line bg-surface">
      <div className="border-b border-line bg-honey-50/60 px-5 py-4">
        <div className="flex items-start gap-2.5">
          <MessageSquareQuote size={18}
            className="mt-0.5 shrink-0 text-honey-700" />
          <div>
            <div className="text-sm font-medium text-ink">
              &ldquo;A new client is Camp Longridge — is there a way to pull
              a list of funders who have given to an organization with
              <em> camp</em> in their name?&rdquo;
            </div>
            <div className="mt-0.5 text-xs text-muted">
              Asked October 6, 2026 · answered live below
            </div>
          </div>
        </div>
      </div>

      <div className="px-5 py-4">
        {isLoading && (
          <div className="text-sm text-muted">Reading the filings…</div>
        )}
        {data && (
          <>
            <div className="flex flex-wrap items-end justify-between gap-3">
              <p className="max-w-xl text-sm text-ink">
                <span className="font-semibold">
                  {num(data.total_funders)} foundations
                </span>{' '}
                have funded at least one of the{' '}
                <span className="font-semibold">{num(data.camp_orgs)}</span>{' '}
                camp-named organizations in the data (
                {money(data.camp_dollars)} received).{' '}
                <span className="text-muted">
                  Matched on the word &ldquo;camp/camps&rdquo; — Campus
                  Crusade, campaigns and the Campbell foundations are
                  excluded, not counted.
                </span>
              </p>
              <div className="flex shrink-0 items-center gap-2">
                {/* The real "filter through them": the full cohort on the
                    Foundations page, where every filter and the notes
                    column apply. Plain <a>: filters load from the URL on
                    mount. */}
                <a href="/foundations?grantee_word=camp"
                  className="rounded-md bg-primary px-3 py-1.5 text-sm
                    font-medium text-white hover:bg-primary/90">
                  Browse &amp; filter all {num(data.total_funders)} →
                </a>
                <button onClick={exportCsv}
                  className="flex items-center gap-1.5 rounded-md border
                    border-line px-3 py-1.5 text-sm text-muted
                    hover:bg-canvas hover:text-ink">
                  <Download size={14} />
                  CSV (all {num(data.funders.length)})
                </button>
              </div>
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b-2 border-honey-300 bg-honey-50/60
                    text-left text-xs text-muted">
                    <th className="py-2 pl-2 pr-3 font-medium">Foundation</th>
                    <th className="px-3 font-medium">Gave to</th>
                    <th className="px-3 text-right font-medium">
                      $ to camps
                    </th>
                    <th className="px-3 text-right font-medium"># camps</th>
                    <th className="px-3 font-medium">Applications</th>
                  </tr>
                </thead>
                <tbody>
                  {data.funders.slice(0, shown).map((f) => (
                    <tr key={f.ein} onClick={() => onOpen(f.ein)}
                      className="cursor-pointer border-b border-line/50
                        align-top hover:bg-canvas">
                      <td className="py-2 pl-2 pr-3">
                        <div className="font-medium text-primary">
                          {titleCase(f.name)}
                        </div>
                        <div className="text-xs text-muted">
                          {f.city ? `${titleCase(f.city)}, ` : ''}{f.state}
                        </div>
                      </td>
                      <td className="max-w-[20rem] px-3 py-2 text-xs
                        leading-snug text-muted">
                        {f.examples ? titleCase(f.examples) : '—'}
                        {f.camp_count > 3 && (
                          <span> + {num(f.camp_count - 3)} more</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-right tabular
                        font-medium whitespace-nowrap">
                        {money(f.dollars)}
                      </td>
                      <td className="px-3 py-2 text-right tabular
                        text-muted">
                        {f.camp_count}
                      </td>
                      <td className="px-3 py-2">
                        <StatusPill status={f.application_status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {shown < data.funders.length && (
              <div className="mt-3 text-center">
                <button onClick={() => setShown((n) => n + 100)}
                  className="rounded-lg border border-line px-4 py-2 text-sm
                    text-muted hover:bg-canvas hover:text-ink">
                  Show more ({num(data.funders.length - shown)} remaining
                  of the top {num(data.funders.length)})
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
