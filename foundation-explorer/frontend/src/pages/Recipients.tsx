import { Fragment, useEffect, useMemo, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import {
  ANY_CHRISTIAN, CHRISTIAN_TRADITIONS, OTHER_TRADITIONS,
  fetchRecipientV5, fetchRecipientsStatsV5, fetchRecipientsV5,
  traditionLabel, type RecipientRowV5,
} from '../lib/apiV5'
import { money, moneyFull, num, titleCase } from '../lib/format'
import { Card, CardTitle, Skeleton } from '../components/ui/primitives'
import CountyFilter from '../components/recipients/CountyFilter'
import { IdentityChip, TraditionChip } from '../components/foundations/V5Chips'

const PAGE_SIZE = 50

const IDENTITY_STATUSES = [
  'matched_bmf', 'unresolved', 'individual', 'foreign', 'collision',
  'government', 'unattributable',
]

export default function Recipients() {
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  const [tradition, setTradition] = useState('')
  const [identity, setIdentity] = useState('')
  const [minReceived, setMinReceived] = useState('')
  const [counties, setCounties] = useState<string[]>([])
  const [page, setPage] = useState(1)
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    const t = setTimeout(() => { setDebounced(q); setPage(1) }, 300)
    return () => clearTimeout(t)
  }, [q])

  const qs = useMemo(() => {
    const p = new URLSearchParams()
    if (debounced) p.set('q', debounced)
    if (tradition) p.set('tradition', tradition)
    if (identity) p.set('identity_status', identity)
    if (minReceived) p.set('min_received', minReceived)
    if (counties.length) p.set('county', counties.join(','))
    p.set('page', String(page))
    p.set('page_size', String(PAGE_SIZE))
    return p.toString()
  }, [debounced, tradition, identity, minReceived, counties, page])

  const { data, isFetching } = useQuery({
    queryKey: ['v5recipients', qs],
    queryFn: () => fetchRecipientsV5(qs),
    placeholderData: keepPreviousData,
  })
  const { data: stats } = useQuery({
    queryKey: ['v5recipientsStats'],
    queryFn: fetchRecipientsStatsV5,
  })
  const { data: funders } = useQuery({
    queryKey: ['v5recipientFunders', expanded],
    queryFn: () => fetchRecipientV5(expanded as string),
    enabled: !!expanded,
  })

  const pages = data ? Math.ceil(data.total / PAGE_SIZE) : 0

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold text-primary mb-1">
        Recipients
      </h1>
      <p className="text-sm text-muted mb-4">
        Who the money went to, tax years 2023–2024. Every classification shows
        its method and the evidence behind it.
      </p>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          {stats.by_tradition.slice(0, 4).map((t) => (
            <Card key={t.tradition}>
              <div className="text-xs text-muted">
                {traditionLabel(t.tradition)}
              </div>
              <div className="text-lg font-semibold text-primary tabular">
                {money(t.dollars)}
              </div>
              <div className="text-xs text-muted">
                {num(t.recipients)} recipients
              </div>
            </Card>
          ))}
        </div>
      )}

      <Card className="mb-4">
        <div className="flex flex-wrap gap-3 items-end">
          <label className="flex flex-col text-xs text-muted">
            Search name
            <input value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="e.g. seminary"
              className="mt-1 border border-line rounded px-2 py-1.5 text-sm
                w-64" />
          </label>
          <label className="flex flex-col text-xs text-muted">
            Tradition
            <select value={tradition}
              onChange={(e) => { setTradition(e.target.value); setPage(1) }}
              className="mt-1 border border-line rounded px-2 py-1.5 text-sm">
              <option value="">Any</option>
              <option value={ANY_CHRISTIAN}>Any Christian</option>
              {[...CHRISTIAN_TRADITIONS, ...OTHER_TRADITIONS]
                .map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label className="flex flex-col text-xs text-muted">
            Identity status
            <select value={identity}
              onChange={(e) => { setIdentity(e.target.value); setPage(1) }}
              className="mt-1 border border-line rounded px-2 py-1.5 text-sm">
              <option value="">Any</option>
              {IDENTITY_STATUSES.map((s) =>
                <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
            </select>
          </label>
          <label className="flex flex-col text-xs text-muted">
            Min received
            <input value={minReceived} inputMode="numeric"
              onChange={(e) => { setMinReceived(e.target.value); setPage(1) }}
              placeholder="e.g. 100000"
              className="mt-1 border border-line rounded px-2 py-1.5 text-sm
                w-32" />
          </label>
          <CountyFilter value={counties}
            onChange={(next) => { setCounties(next); setPage(1) }} />
          <button onClick={() => {
            setQ(''); setTradition(''); setIdentity(''); setMinReceived('')
            setCounties([]); setPage(1)
          }} className="text-sm text-primary hover:underline pb-1.5">
            Reset
          </button>
        </div>
      </Card>

      <div className="text-sm text-muted mb-2">
        {data ? `${num(data.total)} recipients` : <Skeleton className="h-4 w-40" />}
        {isFetching && <span className="ml-2 opacity-60">updating…</span>}
      </div>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted border-b border-line">
                <th className="py-2">Recipient</th>
                <th>Location</th>
                <th>Classification</th>
                <th>Method</th>
                <th className="text-right">Received</th>
                <th className="text-right">Funders</th>
              </tr>
            </thead>
            <tbody>
              {!data && <tr><td colSpan={6} className="py-6">
                <Skeleton className="h-40" /></td></tr>}
              {data?.rows.map((r: RecipientRowV5) => (
                <Fragment key={r.entity_id}>
                  <tr onClick={() => setExpanded(
                        expanded === r.entity_id ? null : r.entity_id)}
                    className="border-b border-line/60 cursor-pointer
                      hover:bg-canvas align-top">
                    <td className="py-2 pr-3 font-medium">
                      {titleCase(r.name)}
                      {r.identity_status !== 'matched_bmf' && (
                        <span className="ml-1.5">
                          <IdentityChip status={r.identity_status} /></span>
                      )}
                    </td>
                    <td className="pr-3 text-xs whitespace-nowrap">
                      {r.county ? (
                        <>
                          <div className="text-ink">
                            {titleCase(r.city || '')}, {r.state}
                          </div>
                          <div className="text-muted"
                            title={r.place_count && r.place_count > 1
                              ? `${r.place_count} different places appear on `
                                + 'this organisation\u2019s grants; this is '
                                + 'the one with the most dollars.'
                              : undefined}>
                            {r.county.replace(/ County$/, '')}
                            {r.place_count != null && r.place_count > 1 && ' *'}
                          </div>
                        </>
                      ) : (
                        <span className="text-muted"
                          title="No usable city appeared on any of this
                            organisation's grants.">—</span>
                      )}
                    </td>
                    <td className="pr-3">
                      {r.tradition
                        ? <TraditionChip tradition={r.tradition} />
                        : <span className="text-muted text-xs">
                            Unclassified</span>}
                    </td>
                    <td className="pr-3 text-muted text-xs">
                      {r.method || '—'}
                      {r.confidence != null &&
                        ` · ${Math.round(r.confidence * 100)}%`}
                    </td>
                    <td className="text-right tabular pr-3 whitespace-nowrap">
                      {moneyFull(r.total_received)}
                    </td>
                    <td className="text-right tabular pr-3">
                      {num(r.funder_count)}
                    </td>
                  </tr>
                  {expanded === r.entity_id && (
                    <tr className="border-b border-line/60 bg-canvas/50">
                      <td colSpan={6} className="py-3 px-3">
                        {r.reason && (
                          <div className="text-xs text-muted mb-2">
                            <span className="font-medium text-ink">
                              Evidence:</span> {r.reason}
                          </div>
                        )}
                        <CardTitle>Funders</CardTitle>
                        {!funders && <Skeleton className="h-16 mt-2" />}
                        {funders && (
                          <table className="w-full text-xs mt-2">
                            <tbody>
                              {(funders.funders ?? []).slice(0, 15).map((f) => (
                                <tr key={f.ein}>
                                  <td className="py-1 pr-3">
                                    {titleCase(f.name)}
                                  </td>
                                  <td className="text-right tabular pr-3">
                                    {moneyFull(f.dollars)}
                                  </td>
                                  <td className="text-muted pr-3">
                                    {f.grants} grants · last {f.last_year}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {data?.rows.length === 0 && (
                <tr><td colSpan={6} className="py-6 text-center text-muted">
                  No recipients match these filters.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
        {pages > 1 && (
          <div className="flex items-center gap-3 mt-3 text-sm">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}
              className="px-2 py-1 border border-line rounded
                disabled:opacity-40">Previous</button>
            <span className="text-muted">
              Page {num(page)} of {num(pages)}
            </span>
            <button disabled={page >= pages}
              onClick={() => setPage((p) => p + 1)}
              className="px-2 py-1 border border-line rounded
                disabled:opacity-40">Next</button>
          </div>
        )}
      </Card>
    </div>
  )
}
