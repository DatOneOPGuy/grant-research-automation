// Full search results, as a table.
//
// The dropdown answers "is the thing I am thinking of in here?"; this answers
// "what did that turn up?". Same ranked list, but wide enough to compare
// foundations against each other rather than pick one, and with a Matched
// column that makes the ranking legible: every row can be interrogated for
// why it is here and how strong the evidence is.
import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ExternalLink, Globe, Loader2, Search } from 'lucide-react'
import {
  MATCH_STYLE, searchFoundations, type SearchMatch, type SearchResult,
} from '../lib/apiSearch'
import { money, num, propublicaUrl, titleCase, websiteUrl } from '../lib/format'
import SaveMenu from '../components/foundations/SaveMenu'
import DetailPanel from '../components/foundations/DetailPanel'
import MatchPopover, { Highlighted } from '../components/search/MatchPopover'
import { Skeleton } from '../components/ui/primitives'

const LIMIT = 100

export default function SearchResults() {
  const [params] = useSearchParams()
  const q = params.get('q') ?? ''
  const [selected, setSelected] = useState<string | null>(null)

  const { data, isFetching, isError, error } = useQuery({
    queryKey: ['v5search', q],
    queryFn: () => searchFoundations(q, LIMIT),
    enabled: q.trim().length > 0,
    placeholderData: keepPreviousData,
  })

  const rows = data?.results ?? []

  return (
    <div>
      <div className="flex items-end justify-between mb-5 gap-4">
        <div className="min-w-0">
          <h1 className="font-display text-3xl font-semibold text-primary">
            Search results
          </h1>
          <div className="text-sm text-muted mt-1 flex items-center gap-2">
            {q
              ? data
                ? <>
                    {num(data.count)} result{data.count === 1 ? '' : 's'} for{' '}
                    <span className="text-ink font-medium">“{q}”</span>
                    {data.count === LIMIT && <> (top {LIMIT})</>}
                    {' · '}<span className="tabular">{data.took_ms} ms</span>
                  </>
                : 'Searching…'
              : 'Type a query to search.'}
            {isFetching && <Loader2 size={14} className="animate-spin" />}
          </div>
        </div>

        {/* No second search box here. The bar directly above this page is
            the search box, and putting another one alongside it just asks
            which of the two is the real one. */}
      </div>

      {isError && (
        <div className="mb-4 rounded-md border border-scoremid/40 bg-amber-50
          px-4 py-2.5 text-sm text-scoremid">
          {error instanceof Error ? error.message : 'Search failed.'}
        </div>
      )}

      {q && data && rows.length === 0 && !isFetching && (
        <div className="border border-line rounded-lg bg-surface p-12
          text-center">
          <Search size={26} className="mx-auto text-line mb-3" />
          <div className="text-sm text-muted">
            Nothing matched <span className="text-ink">“{q}”</span>.
            <div className="text-xs mt-1">
              Foundation names, grantee names, grantee mission statements and
              grant purposes were all searched.
            </div>
          </div>
        </div>
      )}

      {rows.length > 0 && (
        <div className="bg-surface border border-line rounded-lg
          overflow-x-auto">
          <table className="w-full text-sm table-fixed min-w-[820px]">
            {/* Sized to fit the content area rather than an ideal width.
                With the sidebar open, a 1000px-wide browser leaves about
                810px here, so anything wider scrolls the right-hand columns
                out of sight -- which is how the links column disappeared.
                Location moved into the Foundation cell and Paid moved to the
                detail panel to buy the room. */}
            <colgroup>
              <col className="w-[23%]" /><col className="w-[12%]" />
              <col className="w-[18%]" /><col className="w-[21%]" />
              <col className="w-[8%]" /><col className="w-[12%]" />
              <col className="w-[6%]" />
            </colgroup>
            <thead>
              <tr className="text-left text-xs text-muted border-b border-line">
                <th className="py-2 px-3 font-medium">Foundation</th>
                <th className="px-2 font-medium">Matched</th>
                <th className="px-2 font-medium">Grantee</th>
                <th className="px-2 font-medium">Mission</th>
                <th className="px-2 text-right font-medium">% Chr.</th>
                <th className="px-2 text-right font-medium">Christian $</th>
                <th className="px-2" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <Row key={r.ein} r={r} onOpen={setSelected} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {isFetching && rows.length === 0 && q && (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-10" />
          ))}
        </div>
      )}

      {selected && (
        <DetailPanel ein={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}

function Row({ r, onOpen }: {
  r: SearchResult
  onOpen: (ein: string) => void
}) {
  return (
    <tr className="border-b border-line/60 hover:bg-canvas align-top">
      <td className="py-2.5 px-3 cursor-pointer"
        onClick={() => onOpen(r.ein)}>
        <div className="font-medium line-clamp-2 leading-snug">
          {titleCase(r.name)}
        </div>
        {(r.city || r.state) && (
          <div className="text-xs text-muted truncate mt-0.5">
            {r.city && `${titleCase(r.city)}, `}{r.state}
          </div>
        )}
      </td>
      <td className="px-2">
        <MatchCell matches={r.matches} />
      </td>
      {/* The two indirect routes, shown as text rather than left in a hover.
          A grantee name or a line of mission text is the thing a researcher
          is actually reading, so it belongs on the row. */}
      <td className="px-2 text-xs">
        <TextMatch match={r.matches.find((m) => m.field === 'recipient')} />
      </td>
      <td className="px-2 text-xs">
        <TextMatch match={r.matches.find((m) => m.field === 'mission')}
          showDetail />
      </td>
      <td className="px-2 text-right tabular">
        {/* NULL means nothing could be classified. Rendering it as 0% would
            assert the giving is non-Christian, which is a different claim. */}
        {r.pct_christian === null
          ? <span className="text-muted" title="Nothing could be classified">—</span>
          : `${Math.round(r.pct_christian)}%`}
      </td>
      <td className="px-2 text-right tabular whitespace-nowrap">
        {money(r.christian_dollars)}
        {/* Paid is the denominator behind the percentage beside it, and it
            is in the detail panel; the column cost more width than it
            earned here. */}
        <div className="text-[10px] text-muted font-normal">
          of {money(r.paid_2324)}
        </div>
      </td>
      <td className="px-2">
        <div className="flex items-center justify-end gap-0.5">
          <SaveMenu ein={r.ein} align="right" />
          {websiteUrl(r.website) ? (
            <a href={websiteUrl(r.website) as string}
              target="_blank" rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              title={r.website ?? undefined} aria-label="Open website"
              className="p-1 text-muted hover:text-primary shrink-0">
              <Globe size={13} />
            </a>
          ) : (
            <a href={propublicaUrl(r.ein)} target="_blank" rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              title="No website on file — open on ProPublica"
              aria-label="Open on ProPublica"
              className="p-1 text-muted/60 hover:text-primary shrink-0">
              <ExternalLink size={13} />
            </a>
          )}
        </div>
      </td>
    </tr>
  )
}

/** A matched text field, or an em dash when this route did not contribute.
 *
 *  An em dash rather than an empty cell: blank reads as missing data, and
 *  "this foundation was not reached through a grantee" is a fact about the
 *  match, not an absence in the record.
 */
function TextMatch({ match, showDetail = false }: {
  match: SearchMatch | undefined
  showDetail?: boolean
}) {
  if (!match) return <span className="text-muted/50">—</span>
  return (
    <div title={match.detail ?? undefined}>
      <div className="line-clamp-2 leading-snug text-ink
        [&_b]:bg-accent/30 [&_b]:rounded-sm [&_b]:px-0.5">
        <Highlighted html={match.snippet} />
      </div>
      {showDetail && match.detail && (
        <div className="text-muted truncate mt-0.5">{match.detail}</div>
      )}
    </div>
  )
}

/** The badges, each independently hoverable for its own evidence. */
function MatchCell({ matches }: { matches: SearchMatch[] }) {
  const [hover, setHover] = useState<
    { matches: SearchMatch[]; top: number; left: number } | null>(null)
  const timer = useRef<number | null>(null)

  const show = (e: React.MouseEvent, subset: SearchMatch[]) => {
    if (timer.current) window.clearTimeout(timer.current)
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
    const left = Math.min(rect.left, window.innerWidth - 336)
    // Flip above when the row is near the bottom, so the panel is never
    // clipped by the viewport on the last rows of a long table.
    const below = rect.bottom + 8
    const top = below + 220 > window.innerHeight
      ? Math.max(8, rect.top - 228)
      : below
    setHover({ matches: subset, top, left: Math.max(8, left) })
  }

  // A short close delay keeps the panel open while the pointer crosses the
  // gap between the badge and the panel itself.
  const hide = () => {
    timer.current = window.setTimeout(() => setHover(null), 120)
  }

  useEffect(() => () => {
    if (timer.current) window.clearTimeout(timer.current)
  }, [])

  // One row, never wrapping. Wrapping turned a three-match row into a tower
  // of badges four deep and tripled the row height, which made the table
  // unreadable well before it made it informative. Hovering any badge shows
  // every match, so there is no separate "all" affordance to fit in either.
  return (
    <>
      <div
        onMouseEnter={(e) => show(e, matches)}
        onMouseLeave={hide}
        tabIndex={0}
        onFocus={(e) => show(e as unknown as React.MouseEvent, matches)}
        onBlur={hide}
        aria-label={`Matched on ${matches.map((m) => m.label).join(', ')}`}
        className="flex flex-wrap items-center gap-1 cursor-help">
        {matches.map((m) => (
          <span key={m.field}
            title={m.label}
            className={`px-1 py-0.5 rounded border text-[9px] font-semibold
              uppercase tracking-wide leading-none shrink-0
              ${MATCH_STYLE[m.field].cls}`}>
            {MATCH_STYLE[m.field].short}
          </span>
        ))}
      </div>
      {hover && (
        <MatchPopover matches={hover.matches}
          anchor={{ top: hover.top, left: hover.left }}
          onClose={() => setHover(null)} />
      )}
    </>
  )
}
