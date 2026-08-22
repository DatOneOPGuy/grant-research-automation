// The unified search bar.
//
// One box over four indexes. A fundraiser rarely knows which field holds the
// thing they half-remember -- a funder's name, a grantee's name, a phrase from
// a mission statement -- so making them pick a field first is making them
// guess. Foundation-name matches always sort above indirect ones, because
// someone typing "Lilly" wants Lilly Endowment, not the funders of a grantee
// whose mission happens to contain the word.
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, Search, X } from 'lucide-react'
import {
  searchFoundations, type SearchResult, type SearchResponse,
} from '../../lib/apiSearch'
import { money, titleCase } from '../../lib/format'
import MatchPopover, { Highlighted, MatchBadges } from './MatchPopover'

const DEBOUNCE_MS = 140
const MIN_CHARS = 2

export default function GlobalSearch({ onOpen }: {
  /** Called with an EIN when a result is chosen. */
  onOpen: (ein: string) => void
}) {
  const [q, setQ] = useState('')
  const [data, setData] = useState<SearchResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  // Whether the user has explicitly moved the selection with the arrows.
  // Enter means "show me the table" until they have.
  const [arrowed, setArrowed] = useState(false)
  const [popover, setPopover] = useState<
    { result: SearchResult; top: number; left: number } | null>(null)

  const navigate = useNavigate()
  const boxRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  // Guards against out-of-order responses: a fast query answered after a slow
  // earlier one would otherwise overwrite fresher results with staler ones.
  const seqRef = useRef(0)

  const run = useCallback(async (term: string) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const seq = ++seqRef.current
    setLoading(true)
    try {
      const res = await searchFoundations(term, 20, controller.signal)
      if (seq !== seqRef.current) return
      setData(res)
      setError(null)
      setActive(0)
      setArrowed(false)
    } catch (err) {
      if (controller.signal.aborted || seq !== seqRef.current) return
      setError(err instanceof Error ? err.message : 'Search failed')
      setData(null)
    } finally {
      if (seq === seqRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const term = q.trim()
    if (term.length < MIN_CHARS) {
      abortRef.current?.abort()
      setData(null)
      setLoading(false)
      return
    }
    const timer = setTimeout(() => void run(term), DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [q, run])

  // Close on an outside click, and open the box from anywhere with / or cmd-K.
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) {
        setOpen(false)
        setPopover(null)
      }
    }
    const onKey = (e: KeyboardEvent) => {
      const typingElsewhere = ['INPUT', 'TEXTAREA'].includes(
        (e.target as HTMLElement)?.tagName)
      if (((e.key === '/' && !typingElsewhere)
        || (e.key.toLowerCase() === 'k' && (e.metaKey || e.ctrlKey)))) {
        e.preventDefault()
        inputRef.current?.focus()
        setOpen(true)
      }
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [])

  const results = data?.results ?? []

  const choose = (ein: string) => {
    onOpen(ein)
    setOpen(false)
    setPopover(null)
  }

  const seeAll = () => {
    const term = q.trim()
    if (!term) return
    setOpen(false)
    setPopover(null)
    navigate(`/search?q=${encodeURIComponent(term)}`)
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { setOpen(false); setPopover(null); return }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setArrowed(true)
      setActive((i) => Math.min(i + 1, Math.max(0, results.length - 1)))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setArrowed(true)
      setActive((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      // Enter runs the search and shows the table, which is what the old
      // search box did and what someone who has typed a query rather than
      // picked from a list expects. Arrowing to a row is an explicit choice
      // of that row, so Enter opens it instead.
      if (arrowed && results[active]) choose(results[active].ein)
      else seeAll()
    }
  }

  const showPanel = open && q.trim().length >= MIN_CHARS

  return (
    <div ref={boxRef} className="relative w-full max-w-2xl">
      <div className="relative">
        <Search size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-muted
            pointer-events-none" />
        <input
          ref={inputRef}
          value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder="Search foundations, grantees, missions, grant purposes…"
          aria-label="Search"
          className="w-full rounded-lg border border-line bg-surface pl-9 pr-16
            py-2 text-sm placeholder:text-muted/70
            focus:outline-none focus:ring-2 focus:ring-primary/20
            focus:border-primary/40" />
        <div className="absolute right-2.5 top-1/2 -translate-y-1/2
          flex items-center gap-1.5">
          {loading && <Loader2 size={14} className="animate-spin text-muted" />}
          {q ? (
            <button onClick={() => { setQ(''); setData(null); inputRef.current?.focus() }}
              aria-label="Clear search"
              className="p-0.5 rounded text-muted hover:text-ink">
              <X size={14} />
            </button>
          ) : (
            <kbd className="hidden sm:inline text-[10px] text-muted border
              border-line rounded px-1 py-0.5">/</kbd>
          )}
        </div>
      </div>

      {showPanel && (
        <div className="absolute z-50 mt-1.5 w-full rounded-lg border
          border-line bg-surface shadow-xl overflow-hidden">
          {error && (
            <div className="px-4 py-3 text-sm text-scoremid">{error}</div>
          )}

          {!error && data && results.length === 0 && !loading && (
            <div className="px-4 py-6 text-center text-sm text-muted">
              Nothing matched <span className="text-ink">{data.query}</span>.
              <div className="text-xs mt-1">
                Names, grantees, mission text and grant purposes were all
                searched.
              </div>
            </div>
          )}

          {results.length > 0 && (
            <>
              <ul className="max-h-[26rem] overflow-y-auto">
                {results.map((r, i) => (
                  <li key={r.ein}>
                    <button
                      onClick={() => choose(r.ein)}
                      onMouseEnter={(e) => {
                        setActive(i)
                        const rect = e.currentTarget.getBoundingClientRect()
                        // Prefer the right side; flip inside the viewport when
                        // there is not room for the panel.
                        const left = rect.right + 8 + 320 < window.innerWidth
                          ? rect.right + 8
                          : Math.max(8, rect.left - 328)
                        setPopover({ result: r, top: rect.top, left })
                      }}
                      className={`w-full text-left px-3 py-2.5 border-b
                        border-line/50 last:border-0 ${
                          i === active ? 'bg-canvas' : 'hover:bg-canvas'}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="font-medium text-ink truncate
                            [&_b]:bg-accent/30 [&_b]:rounded-sm">
                            {r.matches[0]?.field === 'name'
                              ? <Highlighted html={r.matches[0].snippet} />
                              : titleCase(r.name)}
                          </div>
                          <div className="text-xs text-muted mt-0.5 truncate">
                            {r.city && `${titleCase(r.city)}, `}{r.state}
                            {' · '}{money(r.paid_2324)} paid
                            {r.christian_dollars > 0 && (
                              <> · {money(r.christian_dollars)} Christian</>
                            )}
                          </div>
                          {/* The first non-name match, shown inline so the
                              reason is visible without hovering at all. */}
                          {r.matches.find((m) => m.field !== 'name') && (
                            <div className="text-xs text-muted mt-1 truncate
                              [&_b]:bg-accent/30 [&_b]:text-ink
                              [&_b]:rounded-sm [&_b]:px-0.5">
                              <Highlighted
                                html={r.matches.find(
                                  (m) => m.field !== 'name')!.snippet} />
                            </div>
                          )}
                        </div>
                        <MatchBadges matches={r.matches} />
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
              <button onClick={seeAll}
                className="w-full px-3 py-2 border-t border-line bg-canvas
                  text-[11px] text-muted hover:text-primary flex justify-between
                  items-center">
                <span>
                  {data?.count} result{data?.count === 1 ? '' : 's'} ·{' '}
                  <span className="text-primary font-medium">
                    press Enter to see them in a table
                  </span>
                </span>
                <span className="tabular">{data?.took_ms} ms</span>
              </button>
            </>
          )}
        </div>
      )}

      {popover && showPanel && (
        <MatchPopover matches={popover.result.matches}
          anchor={{ top: popover.top, left: popover.left }}
          onClose={() => setPopover(null)} />
      )}
    </div>
  )
}
