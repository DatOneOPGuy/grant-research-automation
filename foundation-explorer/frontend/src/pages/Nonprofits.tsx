// The grant-seeking side of the ledger.
//
// Every other page in this product looks at grantmakers. This looks at the
// 1.5M active 501(c)(3) public charities that approach them -- the population
// our own outreach works from, and the one a user comparing themselves to
// peers wants to browse.
//
// Categories and revenue bands deliberately use the IRS's own vocabulary
// rather than our cause-area regrouping, so a figure seen in the BMF or on
// ProPublica lands in the same bucket here.
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import {
  ChevronLeft, ChevronRight, ExternalLink, Globe, Loader2, Search, X,
} from 'lucide-react'
import {
  NTEE_MAJOR_LABELS, REVENUE_BAND_LABELS, fetchNonprofits,
} from '../lib/apiV5'
import { money, num, propublicaUrl, titleCase, websiteUrl } from '../lib/format'
import { Skeleton } from '../components/ui/primitives'

const PAGE_SIZE = 50

type Filters = {
  q: string
  category: string[]
  revenue_band: string[]
  state: string[]
  christian_funded: boolean
}

const EMPTY: Filters = {
  q: '', category: [], revenue_band: [], state: [], christian_funded: false,
}

function toParams(f: Filters): URLSearchParams {
  const p = new URLSearchParams()
  if (f.q.trim()) p.set('q', f.q.trim())
  for (const key of ['category', 'revenue_band', 'state'] as const) {
    if (f[key].length) p.set(key, f[key].join(','))
  }
  if (f.christian_funded) p.set('christian_funded', 'true')
  return p
}

function fromParams(sp: URLSearchParams): Filters {
  const list = (k: string) => (sp.get(k) || '').split(',').filter(Boolean)
  return {
    q: sp.get('q') || '',
    category: list('category'),
    revenue_band: list('revenue_band'),
    state: list('state'),
    christian_funded: sp.get('christian_funded') === 'true',
  }
}

export default function Nonprofits() {
  const [urlParams, setUrlParams] = useSearchParams()
  const [filters, setFilters] = useState<Filters>(() => fromParams(urlParams))
  const [page, setPage] = useState(0)
  const [draft, setDraft] = useState(filters.q)

  // Debounced so typing does not fire a query per keystroke against 1.5M rows.
  useEffect(() => {
    const t = setTimeout(
      () => setFilters((f) => ({ ...f, q: draft })), 300)
    return () => clearTimeout(t)
  }, [draft])

  const qs = useMemo(() => toParams(filters).toString(), [filters])
  useEffect(() => { setUrlParams(toParams(filters), { replace: true }) },
    [filters, setUrlParams])
  useEffect(() => { setPage(0) }, [qs])

  const { data, isFetching } = useQuery({
    queryKey: ['v5nonprofits', qs, page],
    queryFn: () => fetchNonprofits(qs, PAGE_SIZE, page * PAGE_SIZE),
    placeholderData: keepPreviousData,
  })

  const total = data?.total ?? 0
  const pages = Math.ceil(total / PAGE_SIZE)
  const active = filters.category.length + filters.revenue_band.length
    + filters.state.length + (filters.christian_funded ? 1 : 0)

  const toggle = (key: 'category' | 'revenue_band' | 'state', value: string) =>
    setFilters((f) => ({
      ...f,
      [key]: f[key].includes(value)
        ? f[key].filter((v) => v !== value)
        : [...f[key], value],
    }))

  return (
    <div>
      <div className="flex items-end justify-between mb-5 gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold text-primary">
            Nonprofits
          </h1>
          <div className="text-sm text-muted mt-1 flex items-center gap-2">
            {data
              ? <>{num(total)} organisations match</>
              : 'Loading…'}
            {isFetching && <Loader2 size={14} className="animate-spin" />}
          </div>
        </div>
        <div className="relative shrink-0">
          <Search size={15}
            className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
          <input value={draft} onChange={(e) => setDraft(e.target.value)}
            placeholder="Search by name…" aria-label="Search nonprofits"
            className="w-72 text-sm border border-line rounded-md bg-surface
              pl-8 pr-3 py-1.5 placeholder:text-muted/70 focus:outline-none
              focus:border-primary/40" />
        </div>
      </div>

      <div className="flex gap-5 items-start">
        <aside className="w-64 shrink-0 space-y-4">
          {active > 0 && (
            <button onClick={() => { setFilters(EMPTY); setDraft('') }}
              className="flex items-center gap-1 text-xs text-primary
                hover:underline">
              <X size={12} /> Clear {active} filter{active === 1 ? '' : 's'}
            </button>
          )}

          {/* Our own signal, not the IRS's, so it leads: an organisation
              already taking money from Christian funders is the population
              this product is actually about. */}
          <label className="flex items-start gap-2 rounded-md border
            border-accent/30 bg-accent/5 px-3 py-2 cursor-pointer">
            <input type="checkbox" checked={filters.christian_funded}
              onChange={() => setFilters(
                (f) => ({ ...f, christian_funded: !f.christian_funded }))}
              className="mt-0.5" />
            <span className="text-xs">
              <span className="font-medium text-ink">
                Already funded by Christian foundations
              </span>
              <span className="block text-muted mt-0.5">
                Has received a grant from a funder whose classified giving is
                majority Christian.
              </span>
            </span>
          </label>

          <FacetGroup title="Nonprofit Category"
            counts={data?.facets.category}
            selected={filters.category}
            label={(k) => NTEE_MAJOR_LABELS[k] ?? k}
            onToggle={(v) => toggle('category', v)} />

          <FacetGroup title="Recent Annual Revenue"
            counts={data?.facets.revenue_band}
            selected={filters.revenue_band}
            label={(k) => REVENUE_BAND_LABELS[Number(k)] ?? k}
            sortKeys={(a, b) => Number(a) - Number(b)}
            onToggle={(v) => toggle('revenue_band', v)} />

          <FacetGroup title="State" counts={data?.facets.state}
            selected={filters.state} label={(k) => k}
            onToggle={(v) => toggle('state', v)} initial={8} />
        </aside>

        <div className="flex-1 min-w-0">
          <div className="bg-surface border border-line rounded-lg
            overflow-x-auto">
            <table className="w-full text-sm table-fixed min-w-[820px]">
              <colgroup>
                <col className="w-[34%]" /><col className="w-[26%]" />
                <col className="w-[13%]" /><col className="w-[17%]" />
                <col className="w-[10%]" />
              </colgroup>
              <thead>
                <tr className="text-left text-xs text-muted border-b
                  border-line">
                  <th className="py-2 px-3 font-medium">Organisation</th>
                  <th className="px-2 font-medium">Category</th>
                  <th className="px-2 text-right font-medium">Revenue</th>
                  <th className="px-2 text-right font-medium">
                    Christian funding
                  </th>
                  <th className="px-2" />
                </tr>
              </thead>
              <tbody>
                {data?.rows.map((r) => (
                  <tr key={r.ein}
                    className="border-b border-line/60 hover:bg-canvas
                      align-top">
                    <td className="py-2.5 px-3">
                      <div className="font-medium line-clamp-2 leading-snug">
                        {titleCase(r.name)}
                      </div>
                      <div className="text-xs text-muted truncate mt-0.5">
                        {r.city && `${titleCase(r.city)}, `}{r.state}
                      </div>
                    </td>
                    <td className="px-2 text-xs text-muted">
                      <span className="line-clamp-2">
                        {r.ntee_major
                          ? NTEE_MAJOR_LABELS[r.ntee_major] ?? r.ntee_major
                          : <span className="text-muted/50">—</span>}
                      </span>
                    </td>
                    <td className="px-2 text-right tabular whitespace-nowrap">
                      {money(r.revenue)}
                    </td>
                    <td className="px-2 text-right tabular whitespace-nowrap">
                      {r.christian_dollars > 0 ? (
                        <>
                          {money(r.christian_dollars)}
                          <div className="text-[10px] text-muted font-normal">
                            {r.christian_funders} funder
                            {r.christian_funders === 1 ? '' : 's'}
                          </div>
                        </>
                      ) : <span className="text-muted/50">—</span>}
                    </td>
                    <td className="px-2">
                      <div className="flex items-center justify-end gap-0.5">
                        {websiteUrl(r.website) && (
                          <a href={websiteUrl(r.website) as string}
                            target="_blank" rel="noreferrer" title={r.website ?? ''}
                            aria-label="Open website"
                            className="p-1 text-muted hover:text-primary">
                            <Globe size={13} />
                          </a>
                        )}
                        <a href={propublicaUrl(r.ein)} target="_blank"
                          rel="noreferrer" title="Open on ProPublica"
                          aria-label="Open on ProPublica"
                          className="p-1 text-muted/60 hover:text-primary">
                          <ExternalLink size={13} />
                        </a>
                      </div>
                    </td>
                  </tr>
                ))}
                {!data && Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i}><td colSpan={5} className="py-2 px-3">
                    <Skeleton className="h-8" />
                  </td></tr>
                ))}
              </tbody>
            </table>
          </div>

          {pages > 1 && (
            <div className="flex items-center justify-between mt-3 text-sm">
              <span className="text-muted">
                Page {page + 1} of {num(pages)}
              </span>
              <div className="flex gap-1">
                <button onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0} aria-label="Previous page"
                  className="p-1.5 rounded border border-line hover:bg-canvas
                    disabled:opacity-40">
                  <ChevronLeft size={15} />
                </button>
                <button onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
                  disabled={page >= pages - 1} aria-label="Next page"
                  className="p-1.5 rounded border border-line hover:bg-canvas
                    disabled:opacity-40">
                  <ChevronRight size={15} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/** A checkbox list with counts. Counts come from the API computed with every
 *  OTHER filter applied, so a number beside an unchecked box is what you would
 *  get by ticking it. */
function FacetGroup({ title, counts, selected, label, onToggle, initial = 10,
  sortKeys }: {
  title: string
  counts: Record<string, number> | undefined
  selected: string[]
  label: (key: string) => string
  onToggle: (key: string) => void
  initial?: number
  sortKeys?: (a: string, b: string) => number
}) {
  const [expanded, setExpanded] = useState(false)
  const entries = Object.entries(counts ?? {})
  entries.sort(sortKeys
    ? (a, b) => sortKeys(a[0], b[0])
    : (a, b) => b[1] - a[1])
  // A selected value must stay visible even if it falls outside the top slice,
  // otherwise ticking a box can make it disappear.
  const shown = expanded ? entries : [
    ...entries.slice(0, initial),
    ...entries.slice(initial).filter(([k]) => selected.includes(k)),
  ]

  return (
    <div>
      <div className="text-xs font-medium text-ink mb-1.5">{title}</div>
      <div className="space-y-1">
        {shown.map(([key, count]) => (
          <label key={key}
            className="flex items-start gap-2 text-xs cursor-pointer
              text-muted hover:text-ink">
            <input type="checkbox" checked={selected.includes(key)}
              onChange={() => onToggle(key)} className="mt-0.5 shrink-0" />
            <span className="flex-1 leading-snug">
              {label(key)}{' '}
              <span className="text-muted/70 tabular">({num(count)})</span>
            </span>
          </label>
        ))}
        {!counts && <Skeleton className="h-24" />}
      </div>
      {entries.length > initial && (
        <button onClick={() => setExpanded((e) => !e)}
          className="text-xs text-primary hover:underline mt-1.5">
          {expanded ? '− Show fewer' : `+ Show ${entries.length - initial} more`}
        </button>
      )}
    </div>
  )
}
