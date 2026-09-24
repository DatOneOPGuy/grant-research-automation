/** Design Lab — shared pieces.
 *
 *  Five experiments living behind the DESIGN LAB group in the sidebar, built
 *  from Emily's feedback (2026-09-22): "sleek, easy to quickly grasp", "less
 *  buttons", "evidence tiers ... could confuse people". Each page is a
 *  different answer to the same question: what does this product look like
 *  for someone who knows nothing about grant research?
 *
 *  House rules for every lab page, so the experiments stay comparable:
 *    - No jargon. "Coverage", "evidence tier", "classified" never appear;
 *      pct_christian + coverage collapse into one plain phrase (below).
 *    - One primary action per screen, filters count on one hand.
 *    - Real data, real filters — everything hits the live local API, so
 *      Drake can test behaviour, not just look at mockups.
 *    - Clicking a foundation opens the REAL detail panel. The experiments
 *      reimagine finding, not the foundation page itself.
 */
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Bookmark, Flag, FlaskConical, SlidersHorizontal, X }
  from 'lucide-react'
import { useSavedFoundations } from '../../lib/savedContext'
import FilterPanel from '../../components/foundations/FilterPanel'
import { activeFilterCount } from '../../components/foundations/filterChips'
import {
  NTEE_MAJORS, defaultV5Filters, fetchFoundationsV5, v5FilterParams,
  type FoundationRowV5, type V5Filters,
} from '../../lib/apiV5'
import { money, num, titleCase } from '../../lib/format'

// --- data -------------------------------------------------------------------

/** Fetch foundations with a plain params object — the lab pages compose
 *  their few filters directly instead of carrying the full V5Filters
 *  machinery, which is itself part of what is being reconsidered. */
export function useLab(params: Record<string, string>, limit = 24, page = 0) {
  const qs = new URLSearchParams(
    Object.fromEntries(Object.entries(params).filter(([, v]) => v)),
  ).toString()
  return {
    qs,
    ...useQuery({
      queryKey: ['lab', qs, limit, page],
      queryFn: () => fetchFoundationsV5(qs, limit, page * limit),
      placeholderData: keepPreviousData,
    }),
  }
}

// --- plain language -----------------------------------------------------------

/** The lab's replacement for %-christian + coverage + evidence tier: one
 *  phrase a first-time user parses without a manual. The thresholds keep the
 *  product honest — "mostly Christian giving" is only said when both the
 *  share and the amount classified support it. */
export function focusPhrase(f: FoundationRowV5): {
  label: string; strong: boolean
} {
  if (f.pct_christian === null) {
    return { label: 'Giving focus unknown', strong: false }
  }
  const pct = Math.round(f.pct_christian)
  const thin = f.coverage_pct < 50
  if (pct >= 80) {
    return {
      label: thin ? 'Mostly Christian giving (partial data)'
        : 'Mostly Christian giving',
      strong: !thin,
    }
  }
  if (pct >= 40) {
    return { label: 'Significant Christian giving', strong: false }
  }
  if (pct > 0) return { label: 'Some Christian giving', strong: false }
  return { label: 'No Christian giving found', strong: false }
}

export function applyPhrase(status: string | null): {
  label: string; open: boolean | null
} {
  switch (status) {
    case 'Accepting Applications':
      return { label: 'Open to applications', open: true }
    case 'Contact First':
      return { label: 'Contact them first', open: true }
    case 'Invite Only':
      return { label: 'Invite only', open: false }
    default:
      return { label: 'Application info unknown', open: null }
  }
}

export function typicalGrant(f: FoundationRowV5): string {
  return f.median_grant ? `${money(f.median_grant)} typical grant` : ''
}

export function placeOf(f: FoundationRowV5): string {
  return f.city ? `${titleCase(f.city)}, ${f.state}` : f.state ?? ''
}

// --- chrome -------------------------------------------------------------------

/** Every lab page opens with this so nobody mistakes an experiment for the
 *  product. Names the design question the page is testing. */
export function LabBanner({ testing }: { testing: string }) {
  return (
    <div className="mb-5 flex items-start gap-2.5 rounded-md border
      border-honey-300/60 bg-honey-50 px-4 py-2.5 text-sm text-ink">
      <FlaskConical size={16} className="mt-0.5 shrink-0 text-honey-700" />
      <div>
        <span className="font-semibold">Design experiment.</span>{' '}
        Real data, real filters — a possible future look, not the product.
        <span className="text-muted"> Testing: {testing}</span>
      </div>
      <SavePill />
    </div>
  )
}

/** The card the Simple / Cards / Start pages share. Deliberately shows five
 *  facts and nothing else — the experiment is what happens when we stop
 *  showing everything we know. */
export function FoundationCard({ f, onOpen }: {
  f: FoundationRowV5
  onOpen: (ein: string) => void
}) {
  const focus = focusPhrase(f)
  const apply = applyPhrase(f.application_status)
  return (
    <button
      onClick={() => onOpen(f.ein)}
      className="w-full rounded-xl border border-line bg-surface p-4 text-left
        shadow-sm transition-shadow hover:shadow-md hover:border-honey-300">
      <div className="flex items-start justify-between gap-2">
        <div className="font-display text-[15px] font-semibold leading-snug
          text-primary line-clamp-2">
          {titleCase(f.name)}
        </div>
        {apply.open === true && (
          <span className="shrink-0 rounded-full bg-scorehigh/10 px-2 py-0.5
            text-[11px] font-medium text-scorehigh">
            Open
          </span>
        )}
      </div>
      <div className="mt-0.5 text-xs text-muted">{placeOf(f)}</div>
      <div className="mt-3 text-sm">
        <span className="font-semibold tabular text-ink">
          {money(f.christian_dollars)}
        </span>{' '}
        <span className="text-muted">to Christian work</span>
      </div>
      <div className={`mt-1 text-xs ${focus.strong
        ? 'font-medium text-scorehigh' : 'text-muted'}`}>
        {focus.label}
      </div>
      <div className="mt-1 text-xs text-muted">
        {typicalGrant(f)}
        {apply.open === false && ' · invite only'}
        {apply.open === null && ' · application info unknown'}
      </div>
    </button>
  )
}

// --- round 2: "what to show instead" (external review, 2026-09-22) ----------

/** Batched receipt lines for a page of rows — one request per page, not one
 *  per row. */
export function useReceipts(eins: string[]) {
  const key = [...eins].sort().join(',')
  return useQuery({
    queryKey: ['labReceipts', key],
    queryFn: async () => {
      const res = await fetch(`/api/v5/receipts?eins=${key}`)
      if (!res.ok) throw new Error(`receipts: ${res.status}`)
      return res.json() as Promise<
        Record<string, { names: { name: string; known: boolean }[] }>>
    },
    enabled: eins.length > 0,
    staleTime: 5 * 60_000,
  })
}

/** "Funded Wycliffe, Samaritan's Purse + 14 more" — the evidence chain as a
 *  sentence. Benchmark ministries render bold because recognition is the
 *  whole mechanism; the trailing count comes from recipient_count the row
 *  already carries. */
export function ReceiptLine({ f, receipts }: {
  f: FoundationRowV5
  receipts?: Record<string, { names: { name: string; known: boolean }[] }>
}) {
  const r = receipts?.[f.ein]
  if (!r) return <span className="text-xs text-muted/50">…</span>
  if (r.names.length === 0) {
    return <span className="text-xs text-muted">
      No named recipients on file
    </span>
  }
  const more = f.recipient_count - r.names.length
  return (
    <span className="text-xs text-ink leading-snug">
      Funded{' '}
      {r.names.map((n, i) => (
        <span key={n.name}>
          {i > 0 && ', '}
          <span className={n.known ? 'font-semibold' : ''}>
            {n.known ? n.name : titleCase(n.name)}
          </span>
        </span>
      ))}
      {more > 0 && (
        <span className="text-muted"> + {num(more)} more</span>
      )}
    </span>
  )
}

// Session metric the reviewer asked to design around: saves per session,
// not pages viewed. In-memory on purpose — it resets when the tab does,
// which is exactly what "per session" means.
let sessionSaves = 0
const bumpSaves = () => {
  sessionSaves += 1
  window.dispatchEvent(new Event('lab-save'))
}

/** One-click save — the reviewer's "make Save the primary action". First
 *  click creates/uses a shared "Prospects" folder; no menu, no decision.
 *  The full SaveMenu still exists inside the detail panel for filing into
 *  specific folders. */
export function QuickSave({ ein }: { ein: string }) {
  const { folders, foldersFor, addTo, removeFrom, createFolder, busy } =
    useSavedFoundations()
  const inFolderIds = foldersFor(ein)
  const saved = inFolderIds.length > 0

  const toggle = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (saved) {
      await removeFrom(ein, inFolderIds[0])
      return
    }
    let target = folders.find(
      (f) => f.name.toLowerCase() === 'prospects')
    if (!target) target = (await createFolder('Prospects')) ?? undefined
    if (target) {
      await addTo(ein, String(target.id))
      bumpSaves()
    }
  }

  return (
    <button onClick={toggle} disabled={busy}
      title={saved ? 'Saved — click to remove' : 'Save to Prospects'}
      aria-label={saved ? 'Remove from saved' : 'Save to Prospects'}
      className={`rounded-md p-1.5 transition-colors ${saved
        ? 'text-honey-700'
        : 'text-muted/40 hover:text-honey-700 hover:bg-honey-50'}`}>
      <Bookmark size={16} fill={saved ? 'currentColor' : 'none'} />
    </button>
  )
}

/** "This looks wrong" — one quiet flag per row. Lab version stores flags in
 *  localStorage; the production version writes to the team database and
 *  becomes free adjudication from people who know the funders. The
 *  experiment here is only: do they click it? */
const FLAG_KEY = 'lab.flags'
const readFlags = (): Record<string, boolean> => {
  try { return JSON.parse(localStorage.getItem(FLAG_KEY) ?? '{}') }
  catch { return {} }
}

export function FlagButton({ ein }: { ein: string }) {
  const [on, setOn] = useState(() => Boolean(readFlags()[ein]))
  const toggle = (e: React.MouseEvent) => {
    e.stopPropagation()
    const flags = readFlags()
    if (on) delete flags[ein]
    else flags[ein] = true
    localStorage.setItem(FLAG_KEY, JSON.stringify(flags))
    setOn(!on)
  }
  return (
    <button onClick={toggle}
      title={on ? 'Flagged as looks-wrong (stored locally in this lab)'
        : 'This looks wrong'}
      aria-label="Flag as incorrect"
      className={`rounded-md p-1.5 ${on
        ? 'text-scoremid'
        : 'text-muted/30 hover:text-scoremid hover:bg-amber-50'}`}>
      <Flag size={14} fill={on ? 'currentColor' : 'none'} />
    </button>
  )
}

/** The always-visible worklist: total saved + saves this session, pinned
 *  bottom-right on every lab page (rendered by LabBanner). */
export function SavePill() {
  const { saved } = useSavedFoundations()
  const [session, setSession] = useState(sessionSaves)
  useEffect(() => {
    const on = () => setSession(sessionSaves)
    window.addEventListener('lab-save', on)
    return () => window.removeEventListener('lab-save', on)
  }, [])
  return (
    <Link to="/saved"
      className="fixed bottom-5 right-5 z-30 flex items-center gap-2
        rounded-full border border-honey-300 bg-surface px-4 py-2 text-sm
        shadow-lg hover:border-honey-500">
      <Bookmark size={15} className="text-honey-700" />
      <span className="font-medium text-ink">{num(saved.length)} saved</span>
      {session > 0 && (
        <span className="rounded-full bg-honey-100 px-2 py-0.5 text-[11px]
          font-medium text-honey-800">
          +{session} this session
        </span>
      )}
    </Link>
  )
}

// --- the real advanced filters, in every design ------------------------------
// Per Drake (2026-09-22): each lab design must still offer the full filter
// vocabulary so Emily can do real work inside any of them. Rather than
// rebuild filters per page, every page gets the REAL FilterPanel — presets,
// geography, reachability, denomination, International, Advanced group,
// all of it — in a slide-over drawer. Its settings merge into the page's
// own quick controls, and win on overlap: opening the power drawer and
// setting something there is the stronger statement of intent.

/** One advanced-filter state per page. `params` is ready to spread into
 *  useLab AFTER the page's own params: last wins, so advanced overrides. */
export function useAdvanced() {
  const [filters, setFilters] = useState<V5Filters>(defaultV5Filters)
  const [open, setOpen] = useState(false)
  const params = useMemo(
    () => Object.fromEntries(v5FilterParams(filters).entries()),
    [filters])
  return {
    filters, setFilters, open, setOpen, params,
    count: activeFilterCount(filters),
    clear: () => setFilters(defaultV5Filters),
  }
}
export type Advanced = ReturnType<typeof useAdvanced>

export function AdvancedButton({ adv }: { adv: Advanced }) {
  return (
    <button onClick={() => adv.setOpen(true)}
      className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5
        text-sm transition-colors ${adv.count > 0
          ? 'border-primary bg-primary/5 text-primary'
          : 'border-line bg-surface text-muted hover:text-ink'}`}>
      <SlidersHorizontal size={14} />
      Advanced
      {adv.count > 0 && (
        <span className="rounded-full bg-primary px-1.5 py-0.5 text-[10px]
          font-medium text-white tabular">
          {adv.count}
        </span>
      )}
    </button>
  )
}

/** The full production FilterPanel in a right-hand slide-over. */
export function AdvancedDrawer({ adv }: { adv: Advanced }) {
  if (!adv.open) return null
  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/20"
        onClick={() => adv.setOpen(false)} />
      <div className="relative flex h-full w-[340px] flex-col bg-surface
        shadow-2xl">
        <div className="flex items-center justify-between border-b
          border-line px-4 py-3">
          <span className="font-display text-base font-semibold text-primary">
            Advanced filters
          </span>
          <div className="flex items-center gap-3">
            {adv.count > 0 && (
              <button onClick={adv.clear}
                className="text-xs text-muted underline underline-offset-2
                  hover:text-ink">
                Clear all ({adv.count})
              </button>
            )}
            <button onClick={() => adv.setOpen(false)} aria-label="Close"
              className="rounded p-1 text-muted hover:bg-canvas
                hover:text-ink">
              <X size={16} />
            </button>
          </div>
        </div>
        <p className="border-b border-line bg-honey-50/60 px-4 py-2
          text-[11px] leading-snug text-muted">
          The product's full filter set. Where a setting here overlaps a
          quick control on the page, this drawer wins.
        </p>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          <FilterPanel filters={adv.filters} onChange={adv.setFilters} />
        </div>
      </div>
    </div>
  )
}

/** Compact cause-area picker for the lab pages' quick bars — one major at
 *  a time, plain labels. The full 26-checkbox + exact-code version lives in
 *  the Advanced drawer; this is the one-click path Emily asked for
 *  ("food security, North Carolina"). Composes conjointly with any state
 *  control on the page: the API requires the cause area IN the states. */
export function CauseSelect({ value, onChange }: {
  value: string
  onChange: (v: string) => void
}) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}
      aria-label="Cause area"
      className="rounded-lg border border-line bg-surface px-2.5 py-1.5
        text-sm focus:outline-none focus:border-honey-500">
      <option value="">Any cause area</option>
      {NTEE_MAJORS.map(([m, label]) => (
        <option key={m} value={m}>{label}</option>
      ))}
    </select>
  )
}
