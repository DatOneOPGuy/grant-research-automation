export type FoundationRow = {
  ein: string
  foundation_name: string
  city: string | null
  state: string | null
  distributions: number | null
  assets: number | null
  revenue: number | null
  faith_alignment_score: number | null
  faith_tier: string | null
  application_status: string | null
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
  score_min?: number
  score_max?: number
  tiers: string[]
  status: string[]
  sizes: string[]
  has_filings: boolean
  has_contact: boolean
  has_website: boolean
  has_phone: boolean
  has_deadline: boolean
  sort: string
  direction: 'asc' | 'desc'
  page: number
  page_size: number
}

export const defaultFilters: FoundationFilterState = {
  q: '',
  states: [],
  tiers: [],
  status: [],
  sizes: [],
  has_filings: false,
  has_contact: false,
  has_website: false,
  has_phone: false,
  has_deadline: false,
  sort: 'faith_alignment_score',
  direction: 'desc',
  page: 1,
  page_size: 50,
}

export function filterParams(f: FoundationFilterState): URLSearchParams {
  const p = new URLSearchParams()
  if (f.q) p.set('q', f.q)
  f.states.forEach((s) => p.append('states', s))
  f.tiers.forEach((t) => p.append('tiers', t))
  f.status.forEach((s) => p.append('status', s))
  f.sizes.forEach((s) => p.append('sizes', s))
  if (f.score_min !== undefined) p.set('score_min', String(f.score_min))
  if (f.score_max !== undefined) p.set('score_max', String(f.score_max))
  for (const k of ['has_filings', 'has_contact', 'has_website',
    'has_phone', 'has_deadline'] as const) {
    if (f[k]) p.set(k, 'true')
  }
  p.set('sort', f.sort)
  p.set('direction', f.direction)
  p.set('page', String(f.page))
  p.set('page_size', String(f.page_size))
  return p
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}
