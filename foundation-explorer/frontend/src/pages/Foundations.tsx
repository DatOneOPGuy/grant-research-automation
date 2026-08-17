import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import {
  ArrowDown, ArrowUp, Bookmark, ChevronLeft, ChevronRight, ExternalLink,
  Globe, HelpCircle, Loader2, PanelLeftClose, PanelLeftOpen,
} from 'lucide-react'
import {
  defaultV5Filters, fetchFoundationsV5,
  v5FilterParams, v5FiltersFromParams, type V5Filters,
} from '../lib/apiV5'
import { money, num, propublicaUrl, titleCase, websiteUrl } from '../lib/format'
import { useSavedFoundations } from '../lib/savedContext'
import { Skeleton, StatusPill } from '../components/ui/primitives'
import FilterPanel from '../components/foundations/FilterPanel'
import ActiveFilters from '../components/foundations/ActiveFilters'
import DetailPanel from '../components/foundations/DetailPanel'
import { BucketBar } from '../components/foundations/BucketBar'

const PAGE_SIZE = 25

// Table columns; sortKey maps to the API's sort vocabulary.
const COLUMNS: { key: string; label: string; sortKey?: string
  help?: string; altSortKey?: string; altLabel?: string }[] = [
  { key: 'name', label: 'Foundation', sortKey: 'name' },
  { key: 'state', label: 'Location' },
  {
    key: 'pct', label: '% Christian', sortKey: 'pct_christian',
    help: 'Share of this foundation\u2019s CLASSIFIED giving that went to '
      + 'Christian organizations. Unclassified dollars are unknown, not '
      + 'non-Christian, so they are excluded from the denominator. The '
      + 'smaller figure below is coverage: the share of this foundation\u2019s '
      + 'giving we could classify at all. A high percentage on low coverage '
      + 'is a thinner claim. With high-confidence evidence only, the '
      + 'numerator tightens to IRS-derived evidence while the denominator '
      + 'stays the same, so the figure can only fall.',
  },
  {
    key: 'christian', label: 'Christian $', sortKey: 'christian',
    help: 'Absolute dollars to Christian organizations. A large foundation '
      + 'can be a small percentage and still be a major Christian funder.',
  },
  {
    key: 'paid', label: 'Paid 2023–24', sortKey: 'paid', altSortKey: 'median',
    altLabel: 'median grant',
  },
  { key: 'status', label: 'Application' },
  {
    key: 'intl', label: 'International', sortKey: 'foreign',
    help: 'Dollars this foundation sent outside the US, with the countries '
      + 'it funded. Destinations come from the country code on the filing '
      + '(IRS/FIPS codes, not ISO). Where a code could not be verified the '
      + 'money is counted as international but left unplaced rather than '
      + 'assigned to a guessed country.',
  },
  { key: 'actions', label: '' },
]

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
  // The filter rail costs 240px, which on a 14-inch laptop is the difference
  // between the table fitting and the last two columns needing a scroll.
  // Collapsing is safe because the active-filter chips above still show what
  // is applied. Remembered so it does not reset on every navigation.
  const [filtersOpen, setFiltersOpen] = useState(
    () => localStorage.getItem('fe.filtersOpen') !== 'false')
  useEffect(() => {
    localStorage.setItem('fe.filtersOpen', String(filtersOpen))
  }, [filtersOpen])

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

      <div className="flex gap-4">
        {filtersOpen ? (
          <div className="shrink-0">
            <button onClick={() => setFiltersOpen(false)}
              className="flex items-center gap-1.5 text-xs text-muted
                hover:text-ink mb-2">
              <PanelLeftClose size={14} /> Hide filters
            </button>
            <FilterPanel filters={filters} onChange={setFilters} />
          </div>
        ) : (
          <button onClick={() => setFiltersOpen(true)}
            title="Show filters"
            className="shrink-0 self-start flex items-center gap-1.5 text-xs
              text-muted hover:text-ink border border-line rounded-md px-2
              py-2">
            <PanelLeftOpen size={14} />
            <span className="[writing-mode:vertical-rl] py-1">Filters</span>
          </button>
        )}

        <div className="flex-1 min-w-0">
          <div className="bg-surface border border-line rounded-lg overflow-x-auto">
            <table className="w-full text-sm table-fixed min-w-[1000px]">
              {/* Proportional widths, in COLUMNS order: Foundation,
                  Location, % Christian, Christian $, Paid, Application,
                  International, Actions. Actions gets 9% because that is
                  ~90px at the 1000px minimum, which is what the three icon
                  buttons need; less and they overflow the pinned cell.
                  No comments or whitespace inside <colgroup> itself -- React
                  treats stray text nodes there as invalid HTML. */}
              <colgroup>
                <col className="w-[19%]" />
                <col className="w-[11%]" />
                <col className="w-[11%]" />
                <col className="w-[14%]" />
                <col className="w-[13%]" />
                <col className="w-[11%]" />
                <col className="w-[12%]" />
                <col className="w-[9%]" />
              </colgroup>
              <thead>
                <tr className="text-left text-xs text-muted border-b border-line bg-canvas">
                  {COLUMNS.map((c) => (
                    <th key={c.key}
                      className={`px-2 py-2.5 font-medium align-bottom ${
                        c.key === 'actions'
                          ? 'sticky right-0 bg-canvas border-l border-line/60'
                          : ''}`}>
                      {c.sortKey ? (
                        <button onClick={() => sortBy(c.sortKey!)}
                          title={c.help}
                          className="flex items-center gap-1 hover:text-ink">
                          {c.label}
                          {c.help && <HelpCircle size={11} className="opacity-60" />}
                          {filters.sort === c.sortKey && (
                            filters.order === 'desc'
                              ? <ArrowDown size={12} /> : <ArrowUp size={12} />)}
                        </button>
                      ) : c.label}
                      {c.altSortKey && (
                        <button onClick={() => sortBy(c.altSortKey!)}
                          className={`block text-[11px] font-normal mt-0.5
                            hover:text-ink ${filters.sort === c.altSortKey
                              ? 'text-ink' : 'text-muted/70'}`}>
                          {c.altLabel}
                          {filters.sort === c.altSortKey && (
                            <span className="ml-0.5">
                              {filters.order === 'desc' ? '↓' : '↑'}
                            </span>
                          )}
                        </button>
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className={isFetching ? 'opacity-60' : ''}>
                {!data && !isError && Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i}><td colSpan={COLUMNS.length} className="px-3 py-2">
                    <Skeleton className="h-6" /></td></tr>
                ))}
                {data?.rows.length === 0 && (
                  <tr><td colSpan={COLUMNS.length} className="px-3 py-12 text-center text-muted">
                    No foundations match these criteria — try broadening your
                    filters.
                  </td></tr>
                )}
                {data?.rows.map((r) => (
                  <tr key={r.ein} onClick={() => setSelected(r.ein)}
                    className="group border-b border-line/60 hover:bg-canvas
                      cursor-pointer">
                    <td className="px-2 py-2.5">
                      <span className="font-medium text-primary truncate block"
                        title={titleCase(r.name)}>
                        {titleCase(r.name)}
                      </span>
                    </td>
                    <td className="px-2 text-muted">
                      <span className="truncate block"
                        title={r.city ? `${titleCase(r.city)}, ${r.state}` : r.state || ''}>
                        {r.city ? `${titleCase(r.city)}, ` : ''}{r.state}
                      </span>
                    </td>
                    <td className="px-2 py-2 whitespace-nowrap">
                      <PctChristian pct={r.pct_christian}
                        coverage={r.coverage_pct} />
                    </td>
                    <td className="px-2 tabular whitespace-nowrap">
                      <div className="font-medium">
                        {money(r.christian_dollars)}
                      </div>
                      <div className="mt-1 w-full max-w-24">
                        <BucketBar b={{
                          christian: r.christian_dollars,
                          nonchristian: r.nonchristian_dollars,
                          unclassified: r.unclassified_dollars,
                          daf: r.daf_dollars,
                        }} />
                      </div>
                    </td>
                    <td className="px-2 tabular whitespace-nowrap">
                      <div className="font-medium">{money(r.paid_2324)}</div>
                      <div className="text-[11px] text-muted">
                        {money(r.median_grant)} median
                      </div>
                    </td>
                    <td className="px-2 whitespace-nowrap">
                      <StatusPill status={r.application_status} />
                    </td>
                    <td className="px-2 tabular">
                      {r.foreign_dollars > 0 ? (
                        <>
                          <div className="font-medium whitespace-nowrap">
                            {money(r.foreign_dollars)}
                          </div>
                          <div className="text-[11px] text-muted truncate"
                            title={r.foreign_top_countries
                              || 'Country not stated in the filing'}>
                            {r.foreign_country_count > 0
                              ? `${r.foreign_country_count} ${r.foreign_country_count === 1 ? 'country' : 'countries'}`
                              : 'country not stated'}
                          </div>
                        </>
                      ) : <span className="text-muted">—</span>}
                    </td>
                    <RowActions ein={r.ein} website={r.website} />
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

// Row actions live inside a clickable <tr>, so every control stops
// propagation -- otherwise saving a foundation would also open its panel.
function RowActions({ ein, website }: { ein: string; website: string | null }) {
  const { isSaved, toggle } = useSavedFoundations()
  const saved = isSaved(ein)
  const site = websiteUrl(website)
  const stop = (e: React.MouseEvent) => e.stopPropagation()
  return (
    <td className="px-2 whitespace-nowrap sticky right-0 bg-surface
      group-hover:bg-canvas border-l border-line/60">
      <div className="flex items-center gap-0">
        <button
          onClick={(e) => { stop(e); toggle(ein) }}
          title={saved ? 'Remove from saved' : 'Save this foundation'}
          aria-label={saved ? 'Remove from saved' : 'Save this foundation'}
          aria-pressed={saved}
          className={`p-1 rounded hover:bg-canvas ${
            saved ? 'text-primary' : 'text-muted hover:text-ink'}`}>
          <Bookmark size={15} fill={saved ? 'currentColor' : 'none'} />
        </button>
        {site ? (
          <a href={site} target="_blank" rel="noreferrer" onClick={stop}
            title={`Website: ${site}`} aria-label="Foundation website"
            className="p-1 rounded text-muted hover:text-ink hover:bg-canvas">
            <Globe size={15} />
          </a>
        ) : (
          <span className="p-1 text-line" title="No website in the filing"
            aria-hidden><Globe size={15} /></span>
        )}
        <a href={propublicaUrl(ein)} target="_blank" rel="noreferrer"
          onClick={stop} title="View on ProPublica Nonprofit Explorer"
          aria-label="View on ProPublica"
          className="p-1 rounded text-muted hover:text-ink hover:bg-canvas">
          <ExternalLink size={15} />
        </a>
      </div>
    </td>
  )
}

// The primary signal. Two honesty rules are enforced here:
//   - null means nothing could be classified, so it renders as an em dash and
//     "no classifiable giving" -- never "0% Christian", which would assert we
//     know the giving is non-Christian when we know nothing about it.
//   - the percentage is never shown without its coverage qualifier, because
//     "100% Christian at 33% classified" is a much weaker claim than at 100%.
function PctChristian({ pct, coverage }: {
  pct: number | null; coverage: number
}) {
  if (pct === null) {
    return (
      <div title="This foundation's filing did not attribute its giving to
        organizations we could classify, so no share can be computed.">
        <div className="text-lg text-line leading-none">—</div>
        <div className="text-[11px] text-muted mt-1">no classifiable giving</div>
      </div>
    )
  }
  const strong = pct >= 50
  const thin = coverage < 50
  return (
    <div>
      <div className={`text-base font-semibold leading-none tabular ${
        strong ? 'text-primary' : 'text-ink'}`}>
        {Math.round(pct)}%
      </div>
      <div className={`text-[11px] mt-1 ${thin ? 'text-scoremid' : 'text-muted'}`}
        title={thin
          ? 'Low coverage: we could classify under half of this foundation\u2019s giving, so this share rests on a thin base.'
          : 'Coverage: the share of this foundation\u2019s giving we could classify.'}>
        {Math.round(coverage)}% classified
      </div>
    </div>
  )
}
