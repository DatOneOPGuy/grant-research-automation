// Client for the unified search endpoint.
//
// One query hits four indexes -- foundation names, grantee names, grantee
// mission statements and grant purposes -- and comes back as a ranked list of
// foundations, each carrying the evidence for why it is in the list.

import { V5_BASE } from './apiV5'

/** Which index produced a match. Ordered by rank, strongest first. */
export type MatchField =
  | 'name' | 'location' | 'recipient' | 'mission' | 'purpose'

export type SearchMatch = {
  field: MatchField
  /** Human label for the field, from the server. */
  label: string
  /** Matched text with <b> around the hit terms. Server-generated. */
  snippet: string
  /** Names the entity behind an indirect match, e.g. which grantee. */
  detail: string | null
}

export type SearchResult = {
  ein: string
  name: string
  city: string | null
  state: string | null
  paid_2324: number
  christian_dollars: number
  pct_christian: number | null
  coverage_band: string | null
  application_status: string | null
  score: number
  matches: SearchMatch[]
}

export type SearchResponse = {
  query: string
  took_ms: number
  count: number
  results: SearchResult[]
}

export async function searchFoundations(
  q: string, limit = 20, signal?: AbortSignal,
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q, limit: String(limit) })
  const res = await fetch(`${V5_BASE}/api/v5/search?${params}`, { signal })
  if (!res.ok) throw new Error(`Search failed (${res.status})`)
  return res.json() as Promise<SearchResponse>
}

/** Colour and short name per match type, for the badges. */
export const MATCH_STYLE: Record<MatchField, { short: string; cls: string }> = {
  name: { short: 'Name', cls: 'bg-primary/10 text-primary border-primary/25' },
  location: { short: 'Location', cls: 'bg-scorelow/15 text-muted border-line' },
  recipient: { short: 'Grantee', cls: 'bg-accent/15 text-scoremid border-accent/30' },
  mission: { short: 'Mission', cls: 'bg-scorehigh/10 text-scorehigh border-scorehigh/25' },
  purpose: { short: 'Purpose', cls: 'bg-scorelow/15 text-muted border-line' },
}
