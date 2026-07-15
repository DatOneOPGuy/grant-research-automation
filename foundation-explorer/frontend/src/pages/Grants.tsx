import { useEffect, useMemo, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { apiGet } from '../lib/api'
import { money, moneyFull, num, US_STATES } from '../lib/format'
import { Card } from '../components/ui/primitives'

type GrantFilters = {
  q: string
  years: number[]
  recipient_state: string
  foundation_state: string
  amount_min?: number
  foreign_only: boolean
  page: number
}

const initial: GrantFilters = {
  q: '', years: [], recipient_state: '', foundation_state: '',
  foreign_only: false, page: 1,
}

function params(f: GrantFilters): string {
  const p = new URLSearchParams()
  if (f.q) p.set('q', f.q)
  f.years.forEach((y) => p.append('years', String(y)))
  if (f.recipient_state) p.set('recipient_state', f.recipient_state)
  if (f.foundation_state) p.set('foundation_state', f.foundation_state)
  if (f.amount_min !== undefined) p.set('amount_min', String(f.amount_min))
  if (f.foreign_only) p.set('foreign_only', 'true')
  p.set('page', String(f.page))
  p.set('page_size', '50')
  return p.toString()
}

export default function Grants() {
  const [filters, setFilters] = useState<GrantFilters>(initial)
  const [search, setSearch] = useState('')

  useEffect(() => {
    const t = setTimeout(
      () => setFilters((f) => ({ ...f, q: search, page: 1 })), 300,
    )
    return () => clearTimeout(t)
  }, [search])

  const qs = useMemo(() => params(filters), [filters])
  const { data, isFetching } = useQuery({
    queryKey: ['grants', qs],
    queryFn: () => apiGet<any>(`/api/grants?${qs}`),
    placeholderData: keepPreviousData,
  })

  const set = (patch: Partial<GrantFilters>) =>
    setFilters((f) => ({ ...f, ...patch, page: 1 }))

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold text-primary mb-1">
        Grants
      </h1>
      <div className="text-sm text-muted mb-6">
        {data ? <>
          {num(data.total)} grants · {money(data.total_dollars)} matching
        </> : 'Loading…'}
      </div>

      <Card className="mb-4">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <input
            placeholder="Search recipient or purpose…"
            className="border border-line rounded px-3 py-1.5 w-64"
            value={search} onChange={(e) => setSearch(e.target.value)}
          />
          {[2023, 2024].map((y) => (
            <label key={y} className="flex items-center gap-1">
              <input type="checkbox" className="accent-primary"
                checked={filters.years.includes(y)}
                onChange={() => set({
                  years: filters.years.includes(y)
                    ? filters.years.filter((x) => x !== y)
                    : [...filters.years, y],
                })} />
              TY{y}
            </label>
          ))}
          <select className="border border-line rounded px-2 py-1.5"
            value={filters.recipient_state}
            onChange={(e) => set({ recipient_state: e.target.value })}>
            <option value="">Recipient state</option>
            {US_STATES.map((s) => <option key={s}>{s}</option>)}
          </select>
          <select className="border border-line rounded px-2 py-1.5"
            value={filters.foundation_state}
            onChange={(e) => set({ foundation_state: e.target.value })}>
            <option value="">Funder state</option>
            {US_STATES.map((s) => <option key={s}>{s}</option>)}
          </select>
          <input type="number" placeholder="Min $"
            className="border border-line rounded px-2 py-1.5 w-24"
            value={filters.amount_min ?? ''}
            onChange={(e) => set({
              amount_min: e.target.value === '' ? undefined
                : Number(e.target.value),
            })} />
          <label className="flex items-center gap-1">
            <input type="checkbox" className="accent-primary"
              checked={filters.foreign_only}
              onChange={(e) => set({ foreign_only: e.target.checked })} />
            Foreign only
          </label>
        </div>
      </Card>

      <Card>
        <table className={`w-full text-sm ${isFetching ? 'opacity-60' : ''}`}>
          <thead>
            <tr className="text-left text-xs text-muted border-b border-line">
              <th className="py-2 pr-3">Funder</th>
              <th className="pr-3">Recipient</th>
              <th className="pr-3">Location</th>
              <th className="text-right pr-3">Amount</th>
              <th className="pr-3">Purpose</th>
              <th>Year</th>
            </tr>
          </thead>
          <tbody>
            {data?.rows.map((g: any, i: number) => (
              <tr key={i} className="border-b border-line/60">
                <td className="py-2 pr-3 max-w-52 truncate text-muted">
                  {g.foundation_name || g.ein}
                </td>
                <td className="pr-3 max-w-56 truncate font-medium">
                  {g.grantee_name}
                </td>
                <td className="pr-3 text-muted">
                  {g.is_foreign ? g.country : `${g.city}, ${g.state}`}
                </td>
                <td className="text-right tabular pr-3">
                  {moneyFull(g.amount)}
                </td>
                <td className="pr-3 text-muted max-w-56 truncate"
                  title={g.purpose}>{g.purpose}</td>
                <td className="tabular">{g.tax_year}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex justify-end gap-2 pt-3 text-sm">
          <button disabled={filters.page <= 1}
            onClick={() => setFilters((f) => ({ ...f, page: f.page - 1 }))}
            className="border border-line rounded px-3 py-1 disabled:opacity-40">
            Prev
          </button>
          <span className="py-1 text-muted tabular">Page {filters.page}</span>
          <button
            onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}
            className="border border-line rounded px-3 py-1">
            Next
          </button>
        </div>
      </Card>
    </div>
  )
}
