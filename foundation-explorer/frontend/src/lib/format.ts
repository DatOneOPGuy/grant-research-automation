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

export const US_STATES = [
  'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'DC', 'FL', 'GA',
  'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA',
  'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY',
  'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'PR', 'RI', 'SC', 'SD', 'TN',
  'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
]
