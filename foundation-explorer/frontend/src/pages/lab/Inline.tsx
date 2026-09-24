/** Lab 8 — Inline expand.
 *
 *  Tests whether the detail PANEL is part of the overwhelm. Click a row and
 *  it opens in place: the three biggest grants with their purpose lines
 *  quoted, and nothing else. "Full details" is the link out to the real
 *  panel. If nobody clicks through, the panel is doing less work than its
 *  seven tabs suggest.
 */
import { Fragment, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronRight } from 'lucide-react'
import DetailPanel from '../../components/foundations/DetailPanel'
import { ANY_CHRISTIAN } from '../../lib/apiV5'
import { money, num, titleCase } from '../../lib/format'
import {
  AdvancedButton, AdvancedDrawer, CauseSelect, LabBanner, QuickSave,
  applyPhrase, focusPhrase, placeOf, useAdvanced, useLab,
} from './shared'

type GrantRow = {
  recipient_name: string; amount: number; tax_year: number
  purpose: string | null
}

function useTopGrants(ein: string | null) {
  return useQuery({
    queryKey: ['labGrants', ein],
    queryFn: async () => {
      const res = await fetch(`/api/v5/foundations/${ein}/grants?limit=3`)
      if (!res.ok) throw new Error(`grants: ${res.status}`)
      return res.json() as Promise<{ rows: GrantRow[] }>
    },
    enabled: Boolean(ein),
    staleTime: 5 * 60_000,
  })
}

export default function LabInline() {
  const [expanded, setExpanded] = useState<string | null>(null)
  const [panel, setPanel] = useState<string | null>(null)
  const [page, setPage] = useState(0)
  const [cause, setCause] = useState('')
  const adv = useAdvanced()
  const { data, isFetching } = useLab({
    tradition: ANY_CHRISTIAN, sort: 'christian',
    ntee: cause,
    ...adv.params,
  }, 25, page)
  const grants = useTopGrants(expanded)

  return (
    <div className="mx-auto max-w-4xl">
      <LabBanner testing="rows that open in place — is the detail panel part of the overwhelm?" />

      <div className="mb-4 flex items-end justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold text-primary
            mb-1">
            Funders
          </h1>
          <p className="text-sm text-muted">
            {data ? num(data.total) : '…'} — click a row to see the receipts
            right here.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <CauseSelect value={cause} onChange={setCause} />
          <AdvancedButton adv={adv} />
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-line bg-surface">
        <table className="w-full text-sm">
          <tbody className={isFetching ? 'opacity-60' : ''}>
            {(data?.rows ?? []).map((f) => {
              const open = expanded === f.ein
              const focus = focusPhrase(f)
              const apply = applyPhrase(f.application_status)
              return (
                <Fragment key={f.ein}>
                  <tr onClick={() => setExpanded(open ? null : f.ein)}
                    className={`cursor-pointer border-b align-middle
                      ${open ? 'border-transparent bg-honey-50/50'
                        : 'border-line/60 hover:bg-canvas'}`}>
                    <td className="w-10 py-3 pl-2"
                      onClick={(e) => e.stopPropagation()}>
                      <QuickSave ein={f.ein} />
                    </td>
                    <td className="py-3 pr-3">
                      <span className="font-medium text-primary">
                        {titleCase(f.name)}
                      </span>
                      <span className="ml-2 text-xs text-muted">
                        {placeOf(f)}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-right tabular font-medium
                      whitespace-nowrap">
                      {money(f.christian_dollars)}
                    </td>
                    <td className="hidden px-3 py-3 text-xs text-muted
                      sm:table-cell">
                      {focus.label}
                    </td>
                    <td className="w-8 pr-3 text-muted">
                      {open ? <ChevronDown size={15} />
                        : <ChevronRight size={15} />}
                    </td>
                  </tr>

                  {open && (
                    <tr className="border-b border-line/60 bg-honey-50/50">
                      <td />
                      <td colSpan={4} className="pb-4 pr-4">
                        {grants.isLoading && (
                          <div className="py-2 text-xs text-muted">
                            Reading the filing…
                          </div>
                        )}
                        {grants.data && (
                          <div className="space-y-2">
                            {grants.data.rows.map((g, i) => (
                              <div key={i} className="text-sm">
                                <span className="font-medium text-ink">
                                  {titleCase(g.recipient_name)}
                                </span>
                                <span className="tabular text-muted">
                                  {' '}— {money(g.amount)} ({g.tax_year})
                                </span>
                                {g.purpose && (
                                  <div className="mt-0.5 border-l-2
                                    border-honey-400 pl-2 text-xs italic
                                    text-muted line-clamp-2">
                                    “{g.purpose}”
                                  </div>
                                )}
                              </div>
                            ))}
                            <div className="flex items-center gap-4 pt-1
                              text-xs">
                              <span className={apply.open === true
                                ? 'font-medium text-scorehigh'
                                : 'text-muted'}>
                                {apply.label}
                              </span>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation(); setPanel(f.ein)
                                }}
                                className="text-primary underline
                                  underline-offset-2 hover:text-honey-700">
                                Full details →
                              </button>
                            </div>
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>

      {data && data.total > 25 && (
        <div className="mt-4 flex justify-center gap-3 text-sm">
          <button onClick={() => { setPage((p) => Math.max(0, p - 1)); setExpanded(null) }}
            disabled={page === 0}
            className="rounded-lg border border-line px-4 py-2
              hover:bg-canvas disabled:opacity-40">Previous</button>
          <button onClick={() => { setPage((p) => p + 1); setExpanded(null) }}
            disabled={(page + 1) * 25 >= data.total}
            className="rounded-lg border border-line px-4 py-2
              hover:bg-canvas disabled:opacity-40">Next</button>
        </div>
      )}

      <AdvancedDrawer adv={adv} />
      {panel && (
        <DetailPanel ein={panel} onClose={() => setPanel(null)} />
      )}
    </div>
  )
}
