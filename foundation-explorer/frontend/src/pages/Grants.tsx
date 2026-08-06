import { useEffect, useMemo, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import {
  ANY_CHRISTIAN, CHRISTIAN_TRADITIONS, OTHER_TRADITIONS,
  fetchGrantsV5, traditionLabel, type GrantsExplorerRow,
} from '../lib/apiV5'
import { money, moneyFull, num, titleCase, US_STATES } from '../lib/format'
import { Card, Skeleton } from '../components/ui/primitives'
import { IdentityChip, TraditionChip } from '../components/foundations/V5Chips'

type Filters = {
  q: string
  recipient_state: string
  foundation_state: string
  amount_min: string
  tax_year: string
  tradition: string
  page: number
}

const initial: Filters = {
  q: '', recipient_state: '', foundation_state: '', amount_min: '',
  tax_year: '', tradition: '', page: 1,
}

const PAGE_SIZE = 50

function params(f: Filters): string {
  const p = new URLSearchParams()
  if (f.q) p.set('q', f.q)
  if (f.recipient_state) p.set('recipient_state', f.recipient_state)
  if (f.foundation_state) p.set('foundation_state', f.foundation_state)
  if (f.amount_min) p.set('amount_min', f.amount_min)
  if (f.tax_year) p.set('tax_year', f.tax_year)
  if (f.tradition) p.set('tradition', f.tradition)
  p.set('page', String(f.page))
  p.set('page_size', String(PAGE_SIZE))
  return p.toString()
}

export default function Grants() {
  const [filters, setFilters] = useState<Filters>(initial)
  const [search, setSearch] = useState('')

  useEffect(() => {
    const t = setTimeout(
      () => setFilters((f) => ({ ...f, q: search, page: 1 })), 300)
    return () => clearTimeout(t)
  }, [search])

  const qs = useMemo(() => params(filters), [filters])
  const { data, isFetching } = useQuery({
    queryKey: ['v5grants', qs],
    queryFn: () => fetchGrantsV5(qs),
    placeholderData: keepPreviousData,
  })

  const set = (patch: Partial<Filters>) =>
    setFilters((f) => ({ ...f, ...patch, page: 1 }))

  const pages = data ? Math.ceil(data.total / PAGE_SIZE) : 0

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold text-primary mb-1">
        Grants
      </h1>
      <p className="text-sm text-muted mb-4">
        Every paid grant, tax years 2023–2024. Recipients the filing never
        named are shown with the reason rather than a raw placeholder.
      </p>

      <Card className="mb-4">
        <div className="flex flex-wrap gap-3 items-end">
          <label className="flex flex-col text-xs text-muted">
            Search recipient or foundation
            <input value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="e.g. seminary"
              className="mt-1 border border-line rounded px-2 py-1.5 text-sm
                text-ink w-64" />
          </label>
          <label className="flex flex-col text-xs text-muted">
            Recipient state
            <select value={filters.recipient_state}
              onChange={(e) => set({ recipient_state: e.target.value })}
              className="mt-1 border border-line rounded px-2 py-1.5 text-sm">
              <option value="">Any</option>
              {US_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="flex flex-col text-xs text-muted">
            Foundation state
            <select value={filters.foundation_state}
              onChange={(e) => set({ foundation_state: e.target.value })}
              className="mt-1 border border-line rounded px-2 py-1.5 text-sm">
              <option value="">Any</option>
              {US_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="flex flex-col text-xs text-muted">
            Tradition
            <select value={filters.tradition}
              onChange={(e) => set({ tradition: e.target.value })}
              className="mt-1 border border-line rounded px-2 py-1.5 text-sm">
              <option value="">Any</option>
              <option value={ANY_CHRISTIAN}>Any Christian</option>
              {[...CHRISTIAN_TRADITIONS, ...OTHER_TRADITIONS]
                .filter(([v]) => v !== 'unclassified')
                .map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label className="flex flex-col text-xs text-muted">
            Tax year
            <select value={filters.tax_year}
              onChange={(e) => set({ tax_year: e.target.value })}
              className="mt-1 border border-line rounded px-2 py-1.5 text-sm">
              <option value="">Both</option>
              <option value="2023">2023</option>
              <option value="2024">2024</option>
            </select>
          </label>
          <label className="flex flex-col text-xs text-muted">
            Min amount
            <input value={filters.amount_min} inputMode="numeric"
              onChange={(e) => set({ amount_min: e.target.value })}
              placeholder="e.g. 50000"
              className="mt-1 border border-line rounded px-2 py-1.5 text-sm
                w-32" />
          </label>
          <button onClick={() => { setSearch(''); setFilters(initial) }}
            className="text-sm text-primary hover:underline pb-1.5">
            Reset
          </button>
        </div>
      </Card>

      <div className="text-sm text-muted mb-2">
        {data
          ? <>{num(data.total)} grants · {money(data.total_dollars)} matching</>
          : <Skeleton className="h-4 w-48" />}
        {isFetching && <span className="ml-2 opacity-60">updating…</span>}
      </div>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted border-b border-line">
                <th className="py-2">Recipient</th>
                <th>Location</th>
                <th>Funder</th>
                <th className="text-right">Amount</th>
                <th>Year</th>
                <th>Purpose</th>
              </tr>
            </thead>
            <tbody>
              {!data && <tr><td colSpan={6} className="py-6">
                <Skeleton className="h-40" /></td></tr>}
              {data?.rows.map((g: GrantsExplorerRow, i: number) => (
                <tr key={i} className="border-b border-line/60 align-top">
                  <td className="py-2 pr-3 font-medium">
                    {titleCase(g.grantee_name)}
                    {g.tradition && <span className="ml-1.5">
                      <TraditionChip tradition={g.tradition} /></span>}
                    {g.identity_status && g.identity_status !== 'matched_bmf' && (
                      <span className="ml-1">
                        <IdentityChip status={g.identity_status} /></span>
                    )}
                  </td>
                  <td className="pr-3 text-muted whitespace-nowrap">
                    {g.city && `${titleCase(g.city)}, `}{g.state}
                  </td>
                  <td className="pr-3 text-muted max-w-48 truncate"
                    title={g.foundation_name}>
                    {titleCase(g.foundation_name)}
                  </td>
                  <td className="text-right tabular pr-3 whitespace-nowrap">
                    {moneyFull(g.amount)}
                  </td>
                  <td className="tabular pr-3">{g.tax_year}</td>
                  <td className="text-muted max-w-56 truncate"
                    title={g.purpose || undefined}>{g.purpose}</td>
                </tr>
              ))}
              {data?.rows.length === 0 && (
                <tr><td colSpan={6} className="py-6 text-center text-muted">
                  No grants match these filters.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
        {pages > 1 && (
          <div className="flex items-center gap-3 mt-3 text-sm">
            <button disabled={filters.page <= 1}
              onClick={() => setFilters((f) => ({ ...f, page: f.page - 1 }))}
              className="px-2 py-1 border border-line rounded
                disabled:opacity-40">Previous</button>
            <span className="text-muted">
              Page {num(filters.page)} of {num(pages)}
            </span>
            <button disabled={filters.page >= pages}
              onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}
              className="px-2 py-1 border border-line rounded
                disabled:opacity-40">Next</button>
          </div>
        )}
      </Card>
      <p className="text-xs text-muted mt-3">
        Sorted by amount. {traditionLabel(null)} recipients are those we have
        not yet classified — see Data Quality for what that covers.
      </p>
    </div>
  )
}
