export type FoundationRow = {
  ein: string
  foundation_name: string
  city: string | null
  state: string | null
  distributions: number | null
  revenue: number | null
  christian_dollars_3yr: number | null
  total_giving_3yr: number | null
  verdict: string | null
  christian_preview: string | null
  christian_recipient_count: number | null
  most_recent_christian_year: number | null
  application_status: string | null
  is_testamentary_trust: number | null
  is_small_fund: number | null
  data_found: string
  propublica_url: string
  latest_tax_year: number | null
}

export type Paged<T> = {
  total: number
  page: number
  page_size: number
  rows: T[]
}

export type FoundationFilterState = {
  q: string
  states: string[]
  verdict: string            // strong (default) | some | any
  christian_min?: number
  recently_active: boolean
  sizes: string[]
  has_contact: boolean
  has_website: boolean
  has_phone: boolean
  include_invite: boolean
  include_trusts: boolean
  include_small: boolean
  preset: string
  sort: string
  direction: 'asc' | 'desc'
  page: number
  page_size: number
}

export const defaultFilters: FoundationFilterState = {
  q: '',
  states: [],
  verdict: 'strong',
  recently_active: false,
  sizes: [],
  has_contact: false,
  has_website: false,
  has_phone: false,
  include_invite: false,
  include_trusts: false,
  include_small: false,
  preset: '',
  sort: '',
  direction: 'desc',
  page: 1,
  page_size: 50,
}

export function filterParams(f: FoundationFilterState): URLSearchParams {
  const p = new URLSearchParams()
  if (f.q) p.set('q', f.q)
  f.states.forEach((s) => p.append('states', s))
  f.sizes.forEach((s) => p.append('sizes', s))
  if (f.verdict) p.set('verdict', f.verdict)
  if (f.christian_min !== undefined)
    p.set('christian_min', String(f.christian_min))
  for (const k of ['recently_active', 'has_contact', 'has_website',
    'has_phone', 'include_invite', 'include_trusts', 'include_small'] as const) {
    if (f[k]) p.set(k, 'true')
  }
  if (f.preset) p.set('preset', f.preset)
  if (f.sort) p.set('sort', f.sort)
  p.set('direction', f.direction)
  p.set('page', String(f.page))
  p.set('page_size', String(f.page_size))
  return p
}

// Demo mode: single build works on localhost (real backend) and Netlify
// (bundled static JSON). Override with ?demo=1 / ?live=1.
function detectDemo(): boolean {
  const params = new URLSearchParams(location.search)
  if (params.get('demo') === '1') return true
  if (params.get('live') === '1') return false
  const h = location.hostname
  return h !== 'localhost' && h !== '127.0.0.1' && h !== '[::1]'
}

export const DEMO = detectDemo()

export async function apiGet<T>(path: string): Promise<T> {
  if (DEMO) {
    const { demoGet } = await import('./demoApi')
    return demoGet(path)
  }
  const res = await fetch(path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}
