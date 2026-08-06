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

export const TAX_WINDOW_LABEL = '2023–2024'

export function taxWindow(start?: number | null, end?: number | null): string {
  if (!start && !end) return TAX_WINDOW_LABEL
  if (!start || start === end) return String(end || start)
  return `${start}–${end}`
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

// IRS 990 website fields are free text and arrive in several broken shapes.
// A previous bug shipped "https/example.org" straight into an href: it starts
// with "http", so a naive startsWith('http') check passed it through, and the
// browser resolved it as a relative path. Returns null when there is no usable
// URL, so callers render nothing rather than a dead link.
const WEB_PLACEHOLDERS = new Set([
  '', '-', '--', 'n/a', 'na', 'n.a.', 'none', 'not applicable', 'no',
  'not available', 'nonexistent', 'n/a.', 'tbd', 'pending', 'null',
])

export function websiteUrl(raw: string | null | undefined): string | null {
  const value = (raw ?? '').trim()
  if (WEB_PLACEHOLDERS.has(value.toLowerCase())) return null
  // An email in the website field is not a website.
  if (value.includes('@') && !value.includes('/')) return null
  // Repair a missing colon: "https//host", "http//host", "https:/host".
  let url = value
    .replace(/^(https?)\/\//i, '$1://')
    .replace(/^(https?):\/(?!\/)/i, '$1://')
  if (!/^https?:\/\//i.test(url)) {
    // Reject anything that still isn't host-shaped (needs a dot, no spaces).
    if (!/^[\w.-]+\.[a-z]{2,}(\/|$|\?)/i.test(url)) return null
    url = `https://${url}`
  }
  try {
    const parsed = new URL(url)
    if (!parsed.hostname.includes('.')) return null
    return parsed.href
  } catch {
    return null
  }
}

export function propublicaUrl(ein: string): string {
  return `https://projects.propublica.org/nonprofits/organizations/${ein}`
}
