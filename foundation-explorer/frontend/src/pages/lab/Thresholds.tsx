/** Lab 9 — Test the thresholds, not just the phrases.
 *
 *  The reviewer's calibration exercise: show Emily ~18 real foundations
 *  WITHOUT the focus phrase or any percentage — just name, dollars, and who
 *  they funded — and have her bucket each by gut feel. Then reveal where
 *  her gut disagrees with focusPhrase(). Every disagreement is a threshold
 *  in the wrong place, found with data instead of debate.
 *
 *  Cards are drawn from three bands (high share / middle / low-or-thin) so
 *  the boundaries actually get exercised, then shuffled so band order
 *  can't leak.
 */
import { useMemo, useState } from 'react'
import { useQueries } from '@tanstack/react-query'
import { fetchFoundationsV5, type FoundationRowV5 } from '../../lib/apiV5'
import { money, titleCase } from '../../lib/format'
import {
  AdvancedButton, AdvancedDrawer, LabBanner, ReceiptLine, focusPhrase,
  placeOf, useAdvanced, useReceipts,
} from './shared'

type Bucket = 'focused' | 'somewhat' | 'not'
const BUCKETS: { id: Bucket; label: string }[] = [
  { id: 'focused', label: 'Christian-focused' },
  { id: 'somewhat', label: 'Somewhat' },
  { id: 'not', label: 'Not really' },
]

/** What the shipped phrase implies, mapped onto her three buckets. */
function phraseBucket(f: FoundationRowV5): Bucket {
  const p = focusPhrase(f).label
  if (p.startsWith('Mostly')) return 'focused'
  if (p.startsWith('Significant')) return 'somewhat'
  return 'not'
}

// Three bands, six cards each. Chosen by query, not hand-picked, so the
// exercise stays honest — nobody curated easy cases.
const BANDS = [
  'tradition=any_christian&min_pct_christian=80&coverage_band=High&sort=christian',
  'tradition=any_christian&min_pct_christian=40&min_coverage=50&sort=paid',
  'tradition=any_christian&min_paid=1000000&sort=paid',
]

export default function LabThresholds() {
  // Advanced filters scope the POOL the 18 cards are drawn from — e.g. set
  // "gives in TX" and calibrate against funders Emily actually works.
  const adv = useAdvanced()
  const advQs = new URLSearchParams(adv.params).toString()
  const results = useQueries({
    queries: BANDS.map((qs, i) => ({
      queryKey: ['labBand', i, advQs],
      queryFn: () => fetchFoundationsV5(
        advQs ? `${qs}&${advQs}` : qs, 12, 0),
      staleTime: Infinity,
    })),
  })
  const loaded = results.every((r) => r.data)

  // Deterministic-enough shuffle: interleave the bands, dedupe, take 18.
  // (No Math.random — a re-render must not reorder cards mid-exercise.)
  const cards = useMemo(() => {
    if (!loaded) return []
    const seen = new Set<string>()
    const out: FoundationRowV5[] = []
    const rows = results.map((r) => r.data!.rows)
    for (let i = 0; i < 12; i++) {
      for (const band of [1, 0, 2]) {
        const f = rows[band]?.[i]
        if (f && !seen.has(f.ein)) { seen.add(f.ein); out.push(f) }
      }
    }
    return out.slice(0, 18)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, advQs])

  const [votes, setVotes] = useState<Record<string, Bucket>>({})
  const [revealed, setRevealed] = useState(false)
  const { data: receipts } = useReceipts(cards.map((f) => f.ein))
  const done = cards.length > 0
    && cards.every((f) => votes[f.ein] !== undefined)
  const disagreements = cards.filter(
    (f) => votes[f.ein] && votes[f.ein] !== phraseBucket(f))

  return (
    <div className="mx-auto max-w-3xl">
      <LabBanner testing="do the phrase thresholds match a fundraiser's gut?" />

      <div className="flex items-end justify-between">
        <h1 className="font-display text-3xl font-semibold text-primary">
          Calibration: sort these by feel
        </h1>
        <AdvancedButton adv={adv} />
      </div>
      <p className="mt-1 mb-6 text-sm text-muted">
        For each foundation — is it Christian-focused, somewhat, or not
        really? No percentages shown; judge from the names and dollars like
        a person would. When all {cards.length || 18} are sorted, we'll show
        where the software disagrees with you.
      </p>

      {!loaded && <div className="text-sm text-muted">Drawing cards…</div>}

      <div className="space-y-3">
        {cards.map((f) => {
          const vote = votes[f.ein]
          const disagree = revealed && vote && vote !== phraseBucket(f)
          return (
            <div key={f.ein}
              className={`rounded-xl border bg-surface p-4 ${disagree
                ? 'border-scoremid'
                : 'border-line'}`}>
              <div className="flex flex-wrap items-start justify-between
                gap-3">
                <div className="min-w-0">
                  <div className="font-medium text-primary">
                    {titleCase(f.name)}
                    <span className="ml-2 text-xs font-normal text-muted">
                      {placeOf(f)}
                    </span>
                  </div>
                  <div className="mt-1 text-xs">
                    <span className="tabular font-medium text-ink">
                      {money(f.christian_dollars)}
                    </span>{' '}
                    <span className="text-muted">to Christian work of{' '}
                      {money(f.paid_2324)} given
                    </span>
                  </div>
                  <div className="mt-1">
                    <ReceiptLine f={f} receipts={receipts} />
                  </div>
                </div>
                <div className="flex shrink-0 gap-1.5">
                  {BUCKETS.map((b) => (
                    <button key={b.id}
                      onClick={() => setVotes((v) => ({ ...v, [f.ein]: b.id }))}
                      className={`rounded-full border px-2.5 py-1 text-xs
                        transition-colors ${vote === b.id
                          ? 'border-primary bg-primary text-white'
                          : 'border-line text-muted hover:text-ink'}`}>
                      {b.label}
                    </button>
                  ))}
                </div>
              </div>
              {revealed && vote && (
                <div className={`mt-2 border-t border-line/60 pt-2 text-xs
                  ${disagree ? 'text-scoremid' : 'text-muted'}`}>
                  {disagree ? 'DISAGREES — ' : 'Matches — '}
                  the software says “{focusPhrase(f).label}”
                  {' '}({f.pct_christian !== null
                    ? `${Math.round(f.pct_christian)}% of what we could
                       classify, ${Math.round(f.coverage_pct)}% classifiable`
                    : 'nothing classifiable'}).
                </div>
              )}
            </div>
          )
        })}
      </div>

      {loaded && (
        <div className="sticky bottom-4 mt-6 flex items-center justify-between
          rounded-xl border border-line bg-surface/95 px-4 py-3 shadow-lg
          backdrop-blur">
          <span className="text-sm text-muted">
            {Object.keys(votes).length} of {cards.length} sorted
            {revealed && ` — ${disagreements.length} disagreement${
              disagreements.length === 1 ? '' : 's'}`}
          </span>
          <button onClick={() => setRevealed(true)} disabled={!done || revealed}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium
              text-white disabled:opacity-40">
            {revealed ? 'Revealed' : 'Compare with the software'}
          </button>
        </div>
      )}
      <AdvancedDrawer adv={adv} />
    </div>
  )
}
