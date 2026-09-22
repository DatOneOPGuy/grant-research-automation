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
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { FlaskConical } from 'lucide-react'
import { fetchFoundationsV5, type FoundationRowV5 } from '../../lib/apiV5'
import { money, titleCase } from '../../lib/format'

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
