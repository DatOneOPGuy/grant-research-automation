export function money(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—'
  if (Math.abs(n) >= 1_000_000_000)
    return `$${(n / 1_000_000_000).toFixed(1)}B`
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 10_000) return `$${(n / 1_000).toFixed(0)}k`
  return `$${Math.round(n).toLocaleString()}`
}

export function moneyFull(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—'
  return `$${Math.round(n).toLocaleString()}`
}

export function num(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—'
  return Math.round(n).toLocaleString()
}

export function scoreColor(score: number | null | undefined): string {
  if (score === null || score === undefined) return 'bg-gray-100 text-scorelow'
  if (score >= 60) return 'bg-green-50 text-scorehigh'
  if (score >= 40) return 'bg-amber-50 text-scoremid'
  return 'bg-gray-100 text-scorelow'
}

// Honest Christian-percentage label: single value when well-classified,
// otherwise a floor–ceiling range. Returns short + long forms.
export function christianPct(row: {
  christian_pct_floor: number | null
  christian_pct_ceiling: number | null
  classification_coverage: number | null
}): { short: string; long: string; well: boolean } {
  const fl = row.christian_pct_floor
  const ce = row.christian_pct_ceiling
  const cov = row.classification_coverage ?? 0
  if (fl == null || ce == null) return { short: '—', long: '—', well: false }
  const well = cov >= 85
  return well
    ? { short: `${fl}%`, long: `${fl}% Christian`, well }
    : {
      short: `${fl}–${ce}%`,
      long: `${fl}–${ce}% Christian (${cov}% classified)`, well,
    }
}

// Title-case all-caps foundation names for display (keep raw data intact).
const KEEP_UPPER = new Set(['LLC', 'INC', 'USA', 'US', 'TUW', 'UW', 'II',
  'III', 'IV', 'MJ', 'JE'])
export function titleCase(s: string | null | undefined): string {
  if (!s) return '—'
  if (s !== s.toUpperCase()) return s // already mixed-case, leave it
  return s.toLowerCase().replace(/\b[a-z']+\b/g, (w) => {
    const up = w.toUpperCase()
    if (KEEP_UPPER.has(up)) return up
    if (w.length <= 2 && /^[a-z]+$/.test(w) && !['of', 'to', 'in', 'by',
      'at', 'on'].includes(w)) return up
    return w.charAt(0).toUpperCase() + w.slice(1)
  })
}

export const US_STATES = [
  'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'DC', 'FL', 'GA',
  'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA',
  'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY',
  'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'PR', 'RI', 'SC', 'SD', 'TN',
  'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
]
