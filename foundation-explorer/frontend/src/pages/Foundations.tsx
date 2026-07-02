import { useEffect, useMemo, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, Download, ExternalLink } from 'lucide-react'
import {
  apiGet, defaultFilters, filterParams,
  type FoundationFilterState, type FoundationRow, type Paged,
} from '../lib/api'
import { money, num, scoreColor } from '../lib/format'
import { Badge, Skeleton, StatusPill } from '../components/ui/primitives'
import FilterPanel from '../components/foundations/FilterPanel'
import DetailPanel from '../components/foundations/DetailPanel'

const COLUMNS: { key: string; label: string; sortable?: boolean }[] = [
  { key: 'foundation_name', label: 'Foundation', sortable: true },
  { key: 'state', label: 'State', sortable: true },
  { key: 'distributions', label: 'Distributions', sortable: true },
  { key: 'faith_alignment_score', label: 'Faith Score', sortable: true },
  { key: 'application_status', label: 'Application', sortable: true },
  { key: 'actions', label: '' },
]

export default function Foundations() {
  const [filters, setFilters] = useState<FoundationFilterState>(defaultFilters)
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<string | null>(null)

  // debounce search 300ms
  useEffect(() => {
    const t = setTimeout(
      () => setFilters((f) => ({ ...f, q: search, page: 1 })), 300,
    )
    return () => clearTimeout(t)
  }, [search])

  const params = useMemo(() => filterParams(filters).toString(), [filters])
  const { data, isFetching } = useQuery({
    queryKey: ['foundations', params],
    queryFn: () => apiGet<Paged<FoundationRow>>(`/api/foundations?${params}`),
    placeholderData: keepPreviousData,
  })

  const sortBy = (col: string) => setFilters((f) => ({
    ...f,
    sort: col,
    direction: f.sort === col && f.direction === 'desc' ? 'asc' : 'desc',
    page: 1,
  }))

  const pages = data ? Math.max(1, Math.ceil(data.total / filters.page_size)) : 1

  return (
    <div>
      <div className="flex items-end justify-between mb-6">
        <div>
          <h1 className="font-display text-3xl font-semibold text-primary">
            Foundations
          </h1>
          <div className="text-sm text-muted mt-1">
            {data ? <>Showing {num(data.total)} of 139,965 foundations</>
              : 'Loading…'}
          </div>
        </div>
        <a
          href={`/api/export/foundations.csv?${params}`}
          className="flex items-center gap-2 bg-primary text-white text-sm rounded-md px-4 py-2 hover:bg-primary/90"
        >
          <Download size={15} /> Export current view
        </a>
      </div>

      <div className="flex gap-8">
        <FilterPanel filters={filters} onChange={setFilters} />

        <div className="flex-1 min-w-0">
          <input
            placeholder="Search foundation name or EIN…"
            className="w-full border border-line rounded-md px-4 py-2.5 text-sm mb-4 bg-surface"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />

          <div className="bg-surface border border-line rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted border-b border-line bg-canvas/50">
                  {COLUMNS.map((c) => (
                    <th key={c.key} className="px-4 py-3 font-medium">
                      {c.sortable ? (
                        <button onClick={() => sortBy(c.key)}
                          className="flex items-center gap-1 hover:text-ink">
                          {c.label}
                          {filters.sort === c.key && (
                            filters.direction === 'desc'
                              ? <ArrowDown size={12} />
                              : <ArrowUp size={12} />
                          )}
                        </button>
                      ) : c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className={isFetching ? 'opacity-60' : ''}>
                {!data && Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={6} className="px-4 py-2">
                      <Skeleton className="h-6" />
                    </td>
                  </tr>
                ))}
                {data?.rows.map((r) => (
                  <tr key={r.ein}
                    onClick={() => setSelected(r.ein)}
                    className="border-b border-line/60 hover:bg-canvas/70 cursor-pointer">
                    <td className="px-4 py-2.5 font-medium text-primary max-w-96 truncate">
                      {r.foundation_name}
                    </td>
                    <td className="px-4">{r.state}</td>
                    <td className="px-4 tabular">{money(r.distributions)}</td>
                    <td className="px-4">
                      <Badge className={scoreColor(r.faith_alignment_score)}>
                        {r.faith_alignment_score ?? '—'}
                      </Badge>
                    </td>
                    <td className="px-4">
                      <StatusPill status={r.application_status} />
                    </td>
                    <td className="px-4">
                      <a href={r.propublica_url} target="_blank" rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="text-muted hover:text-primary inline-block p-1">
                        <ExternalLink size={14} />
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="flex items-center justify-between px-4 py-3 border-t border-line text-sm">
              <div className="text-muted tabular">
                {data && <>Page {filters.page} of {num(pages)}</>}
              </div>
              <div className="flex items-center gap-2">
                <select
                  className="border border-line rounded px-2 py-1"
                  value={filters.page_size}
                  onChange={(e) => setFilters((f) => ({
                    ...f, page_size: Number(e.target.value), page: 1,
                  }))}
                >
                  {[25, 50, 100, 250].map((n) => (
                    <option key={n} value={n}>{n} / page</option>
                  ))}
                </select>
                <button
                  disabled={filters.page <= 1}
                  onClick={() => setFilters((f) => ({ ...f, page: f.page - 1 }))}
                  className="border border-line rounded px-3 py-1 disabled:opacity-40">
                  Prev
                </button>
                <button
                  disabled={filters.page >= pages}
                  onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}
                  className="border border-line rounded px-3 py-1 disabled:opacity-40">
                  Next
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {selected && (
        <DetailPanel ein={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
