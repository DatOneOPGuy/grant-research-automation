import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import {
  ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Download, Loader2,
} from 'lucide-react'
import {
  defaultV5Filters, fetchFoundationsV5, type FoundationRowV5,
  v5FilterParams, v5FiltersFromParams, type V5Filters,
} from '../lib/apiV5'
import { money, num, titleCase } from '../lib/format'
import { Skeleton, StatusPill } from '../components/ui/primitives'
import FilterPanel from '../components/foundations/FilterPanel'
import ActiveFilters from '../components/foundations/ActiveFilters'
import DetailPanel from '../components/foundations/DetailPanel'
import { BucketBar } from '../components/foundations/BucketBar'
import { CoverageChip } from '../components/foundations/V5Chips'

const PAGE_SIZE = 25
const EXPORT_LIMIT = 500

// Table columns; sortKey maps to the API's sort vocabulary.
const COLUMNS: { key: string; label: string; sortKey?: string }[] = [
  { key: 'name', label: 'Foundation', sortKey: 'name' },
  { key: 'state', label: 'Location' },
  { key: 'paid', label: 'Paid 2023–24', sortKey: 'paid' },
  { key: 'mix', label: 'Faith mix ($)', sortKey: 'christian' },
  { key: 'coverage', label: 'Coverage', sortKey: 'coverage' },
  { key: 'status', label: 'Application' },
  { key: 'median', label: 'Median grant', sortKey: 'median' },
]

const CSV_FIELDS: (keyof FoundationRowV5)[] = [
  'ein', 'name', 'city', 'state', 'paid_2324', 'grant_count_2324',
  'recipient_count', 'median_grant', 'christian_dollars',
  'nonchristian_dollars', 'unclassified_dollars', 'daf_dollars',
  'coverage_pct', 'coverage_band', 'application_status', 'website',
  'assets', 'revenue', 'is_testamentary', 'is_micro',
]

function exportCsv(rows: FoundationRowV5[]) {
  const esc = (v: unknown) => {
    const s = v == null ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const lines = [CSV_FIELDS.join(',')]
  rows.forEach((r) => lines.push(CSV_FIELDS.map((k) => esc(r[k])).join(',')))
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'foundations-v5.csv'
  a.click()
  URL.revokeObjectURL(a.href)
}

const PAGE_LABEL = (page: number, count: number, total: number) => {
  if (!total) return '0 results'
  const from = page * PAGE_SIZE + 1
  return `${from.toLocaleString()}–${(from + count - 1).toLocaleString()} of ${total.toLocaleString()}`
}

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

export default function Foundations() {
  const [urlParams, setUrlParams] = useSearchParams()
  const [filters, setFilters] = useState<V5Filters>(
    () => v5FiltersFromParams(urlParams))
  const [selected, setSelected] = useState<string | null>(
    urlParams.get('ein'))

  const [page, setPage] = useState(0)

  // Debounce filter changes (~300ms), then sync the shareable URL and query.
  const debounced = useDebounced(filters, 300)
  const queryString = useMemo(
    () => v5FilterParams(debounced).toString(), [debounced])
  useEffect(() => {
    const p = v5FilterParams(debounced)
    if (selected) p.set('ein', selected)
    setUrlParams(p, { replace: true })
  }, [debounced, selected, setUrlParams])
  // New result set → back to the first page.
  useEffect(() => { setPage(0) }, [queryString])

  const { data, isFetching, isError } = useQuery({
    queryKey: ['v5foundations', queryString, page],
    queryFn: () => fetchFoundationsV5(queryString, PAGE_SIZE, page * PAGE_SIZE),
    placeholderData: keepPreviousData,
  })

  const sortBy = (sortKey: string) => setFilters((f) => ({
    ...f, sort: sortKey,
    order: f.sort === sortKey && f.order === 'desc' ? 'asc' : 'desc',
  }))

  const [exporting, setExporting] = useState(false)
  const handleExport = async () => {
    setExporting(true)
    try {
      const res = await fetchFoundationsV5(queryString, EXPORT_LIMIT)
      exportCsv(res.rows)
    } finally { setExporting(false) }
  }

  const total = data?.total ?? 0
  const pageCount = Math.ceil(total / PAGE_SIZE)

  return (
    <div>
      <div className="flex items-end justify-between mb-5">
        <div>
          <h1 className="font-display text-3xl font-semibold text-primary">
            Foundations
          </h1>
          <div className="text-sm text-muted mt-1 flex items-center gap-2">
            {data
              ? <>{num(total)} foundations match · showing {PAGE_LABEL(
                  page, data.rows.length, total)}</>
              : 'Loading…'}
            {isFetching && (
              <Loader2 size={14} className="animate-spin text-muted" />
            )}
          </div>
        </div>
        <button onClick={handleExport} disabled={!data || exporting}
          className="flex items-center gap-2 bg-primary text-white text-sm rounded-md px-4 py-2 hover:bg-primary/90 disabled:opacity-40">
          {exporting
            ? <Loader2 size={15} className="animate-spin" />
            : <Download size={15} />}
          Export CSV{total > EXPORT_LIMIT ? ` (top ${EXPORT_LIMIT})` : ''}
        </button>
      </div>

      {isError && (
        <div className="mb-4 rounded-md border border-scoremid/40 bg-amber-50 px-4 py-2.5 text-sm text-scoremid">
          Could not reach the v5 API at localhost:8000 — start the backend and
          this page will recover automatically.
        </div>
      )}

      <ActiveFilters filters={filters} onChange={setFilters}
        onClearAll={() => setFilters((f) => ({
          ...defaultV5Filters, sort: f.sort, order: f.order }))} />

      <div className="flex gap-6">
        <FilterPanel filters={filters} onChange={setFilters} />

        <div className="flex-1 min-w-0">
          <div className="bg-surface border border-line rounded-lg overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted border-b border-line bg-canvas/50">
                  {COLUMNS.map((c) => (
                    <th key={c.key} className="px-3 py-3 font-medium">
                      {c.sortKey ? (
                        <button onClick={() => sortBy(c.sortKey!)}
                          className="flex items-center gap-1 hover:text-ink">
                          {c.label}
                          {filters.sort === c.sortKey && (
                            filters.order === 'desc'
                              ? <ArrowDown size={12} /> : <ArrowUp size={12} />)}
                        </button>
                      ) : c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className={isFetching ? 'opacity-60' : ''}>
                {!data && !isError && Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i}><td colSpan={7} className="px-3 py-2">
                    <Skeleton className="h-6" /></td></tr>
                ))}
                {data?.rows.length === 0 && (
                  <tr><td colSpan={7} className="px-3 py-12 text-center text-muted">
                    No foundations match these criteria — try broadening your
                    filters.
                  </td></tr>
                )}
                {data?.rows.map((r) => (
                  <tr key={r.ein} onClick={() => setSelected(r.ein)}
                    className="border-b border-line/60 hover:bg-canvas/70 cursor-pointer">
                    <td className="px-3 py-2.5 max-w-56">
                      <span className="font-medium text-primary truncate block">
                        {titleCase(r.name)}
                      </span>
                    </td>
                    <td className="px-3 text-muted whitespace-nowrap">
                      {r.city ? `${titleCase(r.city)}, ` : ''}{r.state}
                    </td>
                    <td className="px-3 tabular font-medium whitespace-nowrap">
                      {money(r.paid_2324)}
                    </td>
                    <td className="px-3 min-w-32">
                      <BucketBar b={{
                        christian: r.christian_dollars,
                        nonchristian: r.nonchristian_dollars,
                        unclassified: r.unclassified_dollars,
                        daf: r.daf_dollars,
                      }} />
                    </td>
                    <td className="px-3 whitespace-nowrap">
                      <CoverageChip band={r.coverage_band}
                        pct={r.coverage_pct} />
                    </td>
                    <td className="px-3 whitespace-nowrap">
                      <StatusPill status={r.application_status} />
                    </td>
                    <td className="px-3 tabular text-muted whitespace-nowrap">
                      {money(r.median_grant)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {pageCount > 1 && (
            <div className="flex items-center justify-between mt-3 text-sm">
              <span className="text-muted">
                Page {page + 1} of {num(pageCount)}
              </span>
              <div className="flex items-center gap-2">
                <button onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0 || isFetching}
                  className="flex items-center gap-1 border border-line rounded-md px-3 py-1.5 hover:bg-canvas disabled:opacity-40">
                  <ChevronLeft size={15} /> Prev
                </button>
                <button onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                  disabled={page >= pageCount - 1 || isFetching}
                  className="flex items-center gap-1 border border-line rounded-md px-3 py-1.5 hover:bg-canvas disabled:opacity-40">
                  Next <ChevronRight size={15} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {selected && (
        <DetailPanel ein={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
