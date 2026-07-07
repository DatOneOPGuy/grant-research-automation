import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import {
  ArrowDown, ArrowUp, Bookmark, Download, ExternalLink, X,
} from 'lucide-react'
import {
  activeFilterChips, apiGet, DEMO, defaultFilters, filterParams,
  type FoundationFilterState, type FoundationRow, type Paged,
} from '../lib/api'
import {
  loadPersistedFilters, persistFilters, useSavedFoundations,
} from '../lib/savedStore'
import { money, num, titleCase } from '../lib/format'
import { Skeleton, StatusPill, VerdictBadge } from '../components/ui/primitives'
import FilterPanel from '../components/foundations/FilterPanel'
import DetailPanel from '../components/foundations/DetailPanel'

const SORTS: [string, string][] = [
  ['christian_dollars_3yr', 'Christian $ (3yr)'],
  ['christian_recipient_count', 'Christian orgs funded'],
  ['total_giving_3yr', 'Total giving (3yr)'],
  ['assets', 'Total assets'],
  ['typical_grant_size', 'Typical grant size'],
  ['foundation_name', 'Name'],
  ['state', 'State'],
]

const PRESETS: { key: string; label: string }[] = [
  { key: 'best-prospects', label: 'Best Prospects' },
  { key: 'top-christian-dollars', label: 'Top Christian $ Givers' },
  { key: 'accepting', label: 'Accepting Applications' },
]

const COLUMNS: { key: string; label: string; sortable?: boolean }[] = [
  { key: 'save', label: '' },
  { key: 'foundation_name', label: 'Foundation', sortable: true },
  { key: 'state', label: 'Location', sortable: true },
  { key: 'verdict', label: 'Christian giving', sortable: false },
  { key: 'christian_dollars_3yr', label: 'Christian $ (3yr)', sortable: true },
  { key: 'typical_grant_size', label: 'Typical grant', sortable: true },
  { key: 'application_status', label: 'Application', sortable: true },
  { key: 'actions', label: '' },
]

export default function Foundations({ presetLock }: { presetLock?: string }) {
  const [urlParams, setUrlParams] = useSearchParams()
  const { isSaved, toggle } = useSavedFoundations()
  const [filters, setFilters] = useState<FoundationFilterState>(() => ({
    ...defaultFilters,
    ...(presetLock ? {} : loadPersistedFilters<FoundationFilterState>() || {}),
    preset: presetLock || urlParams.get('preset') || '',
    page: 1,
  }))
  const [search, setSearch] = useState(filters.q)
  const [selected, setSelected] = useState<string | null>(
    urlParams.get('ein'))

  // persist filter state across navigation (session-scoped)
  useEffect(() => { if (!presetLock) persistFilters(filters) }, [filters,
    presetLock])

  const { data: stats } = useQuery({
    queryKey: ['stats'], queryFn: () => apiGet<any>('/api/foundations/stats'),
    staleTime: Infinity,
  })
  const chips = activeFilterChips(filters)
  const set = (patch: Partial<FoundationFilterState>) =>
    setFilters((f) => ({ ...f, ...patch, page: 1 }))
  const clearAll = () => setFilters((f) => ({
    ...defaultFilters, preset: f.preset, page: 1,
  }))

  // deep-link: ?ein= opens the detail panel
  useEffect(() => {
    const e = urlParams.get('ein')
    if (e) setSelected(e)
  }, [urlParams])

  useEffect(() => {
    const t = setTimeout(
      () => setFilters((f) => ({ ...f, q: search, page: 1 })), 300)
    return () => clearTimeout(t)
  }, [search])

  const params = useMemo(() => filterParams(filters).toString(), [filters])
  const { data, isFetching } = useQuery({
    queryKey: ['foundations', params],
    queryFn: () => apiGet<Paged<FoundationRow>>(`/api/foundations?${params}`),
    placeholderData: keepPreviousData,
  })

  const sortBy = (col: string) => setFilters((f) => ({
    ...f, sort: col,
    direction: f.sort === col && f.direction === 'desc' ? 'asc' : 'desc',
    page: 1,
  }))

  const applyPreset = (key: string) => setFilters((f) => ({
    ...f, preset: f.preset === key ? '' : key, sort: '', page: 1,
  }))

  const pages = data ? Math.max(1, Math.ceil(data.total / filters.page_size)) : 1

  return (
    <div>
      <div className="flex items-end justify-between mb-5">
        <div>
          <h1 className="font-display text-3xl font-semibold text-primary">
            {presetLock === 'best-prospects' ? 'Best Prospects' : 'Foundations'}
          </h1>
          <div className="text-sm text-muted mt-1">
            {data
              ? <>Showing {num(data.total)}
                {stats && <> of {num(stats.total)}</>} foundations</>
              : 'Loading…'}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <select className="border border-line rounded-md px-2 py-2 text-sm bg-surface"
            value={filters.sort || 'christian_dollars_3yr'}
            onChange={(e) => setFilters((f) => ({
              ...f, sort: e.target.value, page: 1 }))}>
            {SORTS.map(([v, label]) => (
              <option key={v} value={v}>Sort: {label}</option>))}
          </select>
          {!DEMO && (
            <a href={`/api/export/foundations.csv?${params}`}
              className="flex items-center gap-2 bg-primary text-white text-sm rounded-md px-4 py-2 hover:bg-primary/90">
              <Download size={15} /> Export
            </a>
          )}
        </div>
      </div>

      {/* Preset views */}
      {!presetLock && (
        <div className="flex flex-wrap gap-2 mb-4">
          <span className="text-xs text-muted self-center mr-1">
            Preset views:
          </span>
          {PRESETS.map((p) => (
            <button key={p.key} onClick={() => applyPreset(p.key)}
              className={`text-sm rounded-full px-3 py-1 border transition-colors ${
                filters.preset === p.key
                  ? 'bg-primary text-white border-primary'
                  : 'bg-surface text-muted border-line hover:border-primary'}`}>
              {p.label}
            </button>
          ))}
        </div>
      )}

      <div className="flex gap-8">
        <FilterPanel filters={filters} onChange={(f) => {
          setFilters(f)
          if (f.preset) urlParams.set('preset', f.preset)
          else urlParams.delete('preset')
        }} />

        <div className="flex-1 min-w-0">
          <input
            placeholder="Search foundation name, EIN, or city…"
            className="w-full border border-line rounded-md px-4 py-2.5 text-sm mb-3 bg-surface"
            value={search} onChange={(e) => setSearch(e.target.value)} />

          {chips.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 mb-4">
              <span className="text-xs text-muted mr-1">
                {chips.length} filter{chips.length > 1 ? 's' : ''} active:
              </span>
              {chips.map((c) => (
                <button key={c.key} onClick={() => set(c.clear)}
                  className="flex items-center gap-1 text-xs bg-canvas border border-line rounded-full px-2 py-0.5 hover:border-primary">
                  {c.label} <X size={11} />
                </button>
              ))}
              <button onClick={clearAll}
                className="text-xs text-primary underline ml-1">
                Clear all
              </button>
            </div>
          )}

          <div className="bg-surface border border-line rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted border-b border-line bg-canvas/50">
                  {COLUMNS.map((c) => (
                    <th key={c.key} className="px-3 py-3 font-medium">
                      {c.sortable ? (
                        <button onClick={() => sortBy(c.key)}
                          className="flex items-center gap-1 hover:text-ink">
                          {c.label}
                          {filters.sort === c.key && (filters.direction === 'desc'
                            ? <ArrowDown size={12} /> : <ArrowUp size={12} />)}
                        </button>
                      ) : c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className={isFetching ? 'opacity-60' : ''}>
                {!data && Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i}><td colSpan={8} className="px-3 py-2">
                    <Skeleton className="h-6" /></td></tr>
                ))}
                {data?.rows.length === 0 && (
                  <tr><td colSpan={8} className="px-3 py-12 text-center text-muted">
                    No foundations match these criteria — try broadening your
                    filters.
                  </td></tr>
                )}
                {data?.rows.map((r) => (
                  <tr key={r.ein} onClick={() => setSelected(r.ein)}
                    className="border-b border-line/60 hover:bg-canvas/70 cursor-pointer">
                    <td className="pl-3">
                      <button onClick={(e) => { e.stopPropagation(); toggle(r.ein) }}
                        title={isSaved(r.ein) ? 'Saved' : 'Save'}
                        className="p-1 text-muted hover:text-accent">
                        <Bookmark size={15}
                          className={isSaved(r.ein)
                            ? 'fill-accent text-accent' : ''} />
                      </button>
                    </td>
                    <td className="px-3 py-2.5 font-medium text-primary max-w-72 truncate">
                      {titleCase(r.foundation_name)}
                    </td>
                    <td className="px-3 text-muted whitespace-nowrap">
                      {titleCase(r.city)}, {r.state}
                    </td>
                    <td className="px-3 py-2">
                      <VerdictBadge verdict={r.verdict} />
                      {r.christian_preview && (
                        <div className="text-xs text-muted mt-1 max-w-72 truncate"
                          title={titleCase(r.christian_preview)}>
                          {titleCase(r.christian_preview)}
                        </div>
                      )}
                    </td>
                    <td className="px-3 tabular font-medium">
                      {money(r.christian_dollars_3yr)}
                    </td>
                    <td className="px-3 tabular text-muted">
                      {money(r.typical_grant_size)}
                    </td>
                    <td className="px-3"><StatusPill status={r.application_status} /></td>
                    <td className="px-3">
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
                <select className="border border-line rounded px-2 py-1"
                  value={filters.page_size}
                  onChange={(e) => setFilters((f) => ({
                    ...f, page_size: Number(e.target.value), page: 1 }))}>
                  {[25, 50, 100, 250].map((n) => (
                    <option key={n} value={n}>{n} / page</option>))}
                </select>
                <button disabled={filters.page <= 1}
                  onClick={() => setFilters((f) => ({ ...f, page: f.page - 1 }))}
                  className="border border-line rounded px-3 py-1 disabled:opacity-40">
                  Prev
                </button>
                <button disabled={filters.page >= pages}
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
        <DetailPanel ein={selected} onClose={() => {
          setSelected(null)
          urlParams.delete('ein'); setUrlParams(urlParams, { replace: true })
        }} />
      )}
    </div>
  )
}
