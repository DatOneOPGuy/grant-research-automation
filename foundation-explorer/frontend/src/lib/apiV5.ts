// Typed client for the v5 API (paid grants, TY2023–2024).
export const V5_BASE = ''

export type StatsV5 = {
  foundations: number
  active: number
  paid: number
  christian: number
  nonchristian: number
  unclassified: number
  daf: number
  recipients: number
  with_mission: number
  window: string
  identity_run: string
}

export type FoundationRowV5 = {
  ein: string
  name: string
  city: string | null
  state: string | null
  paid_2324: number
  grant_count_2324: number
  recipient_count: number
  median_grant: number | null
  christian_dollars: number
  nonchristian_dollars: number
  unclassified_dollars: number
  daf_dollars: number
  nonclassifiable_dollars: number
  classifiable_dollars: number
  classified_dollars: number
  // null means "nothing could be classified" -- never render this as 0%.
  pct_christian: number | null
  auth_christian_dollars: number
  pct_christian_auth: number | null
  unattributable_reason: string | null
  deadline_kind: string | null
  deadline_months: string | null
  deadline_text: string | null
  coverage_pct: number
  coverage_band: string
  application_status: string | null
  website: string | null
  assets: number | null
  revenue: number | null
  is_testamentary: boolean
  is_micro: boolean
  // Present on the detail response (SELECT *), absent from the list query,
  // hence optional rather than a required field the list would have to fake.
  active_2023?: number
  active_2024?: number
  phone?: string | null
  contact_person?: string | null
  contact_email?: string | null
  latest_tax_year?: number
  // International giving. pct_foreign is null when the foundation gave
  // nothing at all -- "no giving" is not "0% international".
  foreign_dollars: number
  foreign_grant_count: number
  foreign_country_count: number
  foreign_top_countries: string | null
  foreign_christian_dollars: number
  pct_foreign: number | null
  // Static/Netlify export only: full destination code list, so client-side
  // country filtering matches the server instead of approximating from the
  // truncated foreign_top_countries label. Absent in API responses, where the
  // server does the filtering.
  foreign_country_codes?: string[]
}

export type FoundationsResponseV5 = { total: number; rows: FoundationRowV5[] }

export type TraditionRollupV5 = {
  tradition: string
  tier: string
  dollars: number
  recipients: number
}

export type FoundationRecipientV5 = {
  entity_id: string
  name: string
  recipient_ein: string | null
  identity_status: string
  tradition: string | null
  method: string | null
  confidence: number | null
  reason: string | null
  is_daf: boolean
  has_mission: boolean
  dollars: number
  grants: number
  last_year: number
}

export type StateDollarsV5 = { state: string; dollars: number }

export type FoundationDetailV5 = {
  foundation: FoundationRowV5
  traditions: TraditionRollupV5[]
  recipients: FoundationRecipientV5[]
  states: StateDollarsV5[]
  countries: CountryDollarsV5[]
  methods: MethodRollupV5[]
  size_bands: SizeBandV5[]
  yearly: YearRollupV5[]
  top_foreign: ForeignRecipientV5[]
}

export type MethodRollupV5 = {
  method: string
  christian_dollars: number
  dollars: number
  recipients: number
}

export type SizeBandV5 = {
  band: string
  grants: number
  dollars: number
}

export type YearRollupV5 = {
  tax_year: number
  grants: number
  dollars: number
  recipients: number
}

export type ForeignRecipientV5 = {
  name: string
  country_name: string | null
  recipient_country: string | null
  recipient_city: string | null
  tradition: string | null
  method: string | null
  dollars: number
  grants: number
}

export type CountryDollarsV5 = {
  country_code: string
  country_name: string
  dollars: number
  grants: number
  christian_dollars: number
}

export type GrantRowV5 = {
  recipient_name: string
  recipient_city: string | null
  recipient_state: string | null
  amount: number
  tax_year: number
  purpose: string | null
  entity_id: string | null
  tradition: string | null
  identity_status: string | null
  recipient_country: string | null
  // null when the filing's code could not be trusted -- render as Unspecified.
  country_name: string | null
  is_foreign: boolean
}

export type RecipientDetailV5 = {
  recipient: {
    entity_id: string
    ein: string | null
    name: string
    identity_status: string
    tradition: string | null
    method: string | null
    confidence: number | null
    is_daf: boolean
    mission_text: string | null
    website: string | null
    total_received: number
    funder_count: number
  }
  funders: { ein: string; name: string; dollars: number; grants: number; last_year: number }[]
}

// ---- tradition vocabulary --------------------------------------------------
export const CHRISTIAN_TRADITIONS: [string, string][] = [
  ['evangelical_protestant', 'Evangelical / Protestant'],
  ['catholic', 'Catholic'],
  ['orthodox_christian', 'Orthodox'],
  ['christian_unspecified', 'Christian (unspecified)'],
]
export const OTHER_TRADITIONS: [string, string][] = [
  ['jewish', 'Jewish'],
  ['muslim', 'Muslim'],
  ['mormon_lds', 'Mormon / LDS'],
  ['christian_science', 'Christian Science'],
  ['other_religion', 'Other religion'],
  ['secular', 'Secular'],
  ['unclassified', 'Unclassified'],
]
export const ANY_CHRISTIAN = 'any_christian'

const TRADITION_LABELS: Record<string, string> = Object.fromEntries([
  ...CHRISTIAN_TRADITIONS, ...OTHER_TRADITIONS, [ANY_CHRISTIAN, 'Any Christian'],
])
export function traditionLabel(t: string | null | undefined): string {
  if (!t) return 'Unclassified'
  return TRADITION_LABELS[t] || t
}

export const APPLICATION_STATUSES = [
  'Accepting Applications', 'Contact First', 'Invite Only', 'Unknown',
]
export const COVERAGE_BANDS = ['High', 'Moderate', 'Low', 'Not Classifiable']

// When a foundation accepts APPLICATIONS. A 990-PF carries no date on an
// individual grant, so we cannot say when a foundation gave -- only when it
// asks to be approached, which is what a fundraiser schedules around.
// Must stay identical to SEASONS in backend/v5.py: static mode filters
// client-side and any drift would make Netlify disagree with localhost.
export const SEASON_MONTHS: Record<string, number[]> = {
  spring: [3, 4, 5], summer: [6, 7, 8],
  fall: [9, 10, 11], autumn: [9, 10, 11], winter: [12, 1, 2],
  q1: [1, 2, 3], q2: [4, 5, 6], q3: [7, 8, 9], q4: [10, 11, 12],
  first_half: [1, 2, 3, 4, 5, 6], second_half: [7, 8, 9, 10, 11, 12],
  year_end: [11, 12], new_year: [1, 2],
}

export const DEADLINE_SEASONS: [string, string][] = [
  ['spring', 'Spring (Mar–May)'],
  ['summer', 'Summer (Jun–Aug)'],
  ['fall', 'Fall (Sep–Nov)'],
  ['winter', 'Winter (Dec–Feb)'],
]
export const DEADLINE_QUARTERS: [string, string][] = [
  ['q1', 'Q1 (Jan–Mar)'], ['q2', 'Q2 (Apr–Jun)'],
  ['q3', 'Q3 (Jul–Sep)'], ['q4', 'Q4 (Oct–Dec)'],
  ['year_end', 'Year end (Nov–Dec)'], ['new_year', 'New year (Jan–Feb)'],
]
export const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
export const DEADLINE_KINDS: [string, string][] = [
  ['dated', 'Has a stated deadline'],
  ['rolling', 'Accepts applications year-round'],
  ['none', 'States no deadline'],
]

export type CountryRowV5 = {
  country_code: string
  country_name: string
  foundations: number
  dollars: number
  grants: number
  christian: number
}

// Evidence tiers, in the ledger's priority order. `rank` mirrors the server
// priority so the Evidence tab can separate independently-verifiable evidence
// from name-only inference -- the single most important caveat in the product.
export const METHODS: {
  key: string; label: string; hint: string; independent: boolean
}[] = [
  { key: 'human', label: 'Human review', independent: true,
    hint: 'A correction from your team. Overrides every automated method.' },
  { key: 'ntee', label: 'IRS activity code', independent: true,
    hint: 'An official NTEE religion code on the recipient’s IRS record.' },
  { key: 'church_code_name', label: 'IRS church coding', independent: true,
    hint: 'The IRS classifies the recipient as a house of worship.' },
  { key: 'group_exemption', label: 'Denominational ruling', independent: true,
    hint: 'A diocese or denomination formally covers this organization.' },
  { key: 'llm', label: 'Own mission statement', independent: true,
    hint: 'Read from the recipient’s own 990 filing.' },
  { key: 'grant_purpose', label: 'Funder’s stated purpose', independent: true,
    hint: 'What this foundation itself said the money was for.' },
  { key: 'rule', label: 'Organization name only', independent: false,
    hint: 'Inferred from the recipient’s name because the filing gave nothing '
      + 'else — often just a name and a city. Cannot be independently '
      + 'verified, so treat it as a lead rather than a fact.' },
  { key: 'unclassified', label: 'Not classified', independent: false,
    hint: 'We could not determine this recipient’s character.' },
]
const METHOD_BY_KEY = Object.fromEntries(METHODS.map((m) => [m.key, m]))
export function methodLabel(key: string | null | undefined): string {
  if (!key) return 'Not classified'
  return METHOD_BY_KEY[key]?.label || key
}
export function methodIsIndependent(key: string | null | undefined): boolean {
  return !!(key && METHOD_BY_KEY[key]?.independent)
}

// Mission-field groupings, so a researcher can filter by region rather than
// picking twenty country codes. Codes are FIPS as filed, not ISO
// (see src/country_codes.py) -- NI is Nigeria, SZ is Switzerland.
export const MISSION_REGIONS: [string, string[]][] = [
  ['Sub-Saharan Africa', ['KE', 'UG', 'TZ', 'NI', 'SF', 'GH', 'ET', 'RW',
    'CG', 'CF', 'ZI', 'ZA', 'MI', 'MZ', 'SL', 'LI', 'IV', 'SG', 'CM', 'BC',
    'WA', 'BY', 'UV', 'TO', 'BN', 'ML', 'SO', 'SU', 'OD', 'MA', 'GV', 'GA',
    'PU', 'NG', 'CD', 'CT', 'ER', 'LT', 'WZ', 'MP', 'GB']],
  ['Latin America & Caribbean', ['MX', 'BR', 'CO', 'PE', 'GT', 'HA', 'CS',
    'HO', 'ES', 'DR', 'EC', 'CI', 'AR', 'BL', 'PA', 'PM', 'NU', 'UY', 'VE',
    'JM', 'BH', 'TD', 'GY', 'NS', 'CU', 'BB', 'ST', 'GJ', 'VC', 'DO']],
  ['South & Central Asia', ['IN', 'PK', 'NP', 'BG', 'AF', 'CE', 'KZ', 'KG',
    'TI', 'UZ', 'BT', 'MV']],
  ['East & Southeast Asia', ['CH', 'ID', 'RP', 'TH', 'VM', 'MY', 'CB', 'KS',
    'JA', 'TW', 'HK', 'SN', 'BM', 'LA', 'MG', 'MC']],
  ['Middle East & North Africa', ['IS', 'LE', 'JO', 'EG', 'TU', 'IZ', 'AE',
    'SA', 'MO', 'TS', 'YM', 'QA', 'BA', 'KU', 'SY', 'IR', 'AG', 'LY', 'WI']],
  ['Europe', ['UK', 'SZ', 'GM', 'FR', 'NL', 'IT', 'BE', 'SP', 'EI', 'NO',
    'SW', 'DA', 'AU', 'PL', 'FI', 'PO', 'GR', 'UP', 'RS', 'RO', 'HU', 'EZ',
    'AL', 'MK', 'RI', 'BK', 'MD', 'HR', 'LH', 'EN', 'LG', 'LO', 'SI', 'BU',
    'MJ', 'KV', 'LS', 'LU', 'MN', 'MT', 'CY', 'IC', 'AM', 'GG', 'AJ', 'BO',
    'SM', 'JE', 'FO', 'GI', 'IM']],
  ['Oceania', ['AS', 'NZ', 'PP', 'FJ', 'WS', 'NC', 'FM', 'BP', 'NR', 'PC']],
]

// ---- geographic regions ----------------------------------------------------
// Census divisions plus a domain-specific "Bible Belt" grouping that maps to
// how faith-based fundraisers actually think about territory. Each expands to
// state codes for the `state` / `gives_to_state` filters.
export const US_REGIONS: [string, string[]][] = [
  ['Northeast', ['CT', 'ME', 'MA', 'NH', 'RI', 'VT', 'NJ', 'NY', 'PA']],
  ['Southeast', ['AL', 'AR', 'FL', 'GA', 'KY', 'LA', 'MS', 'NC', 'SC',
    'TN', 'VA', 'WV']],
  ['Midwest', ['IL', 'IN', 'IA', 'KS', 'MI', 'MN', 'MO', 'NE', 'ND',
    'OH', 'SD', 'WI']],
  ['Southwest', ['AZ', 'NM', 'OK', 'TX']],
  ['West', ['AK', 'CA', 'CO', 'HI', 'ID', 'MT', 'NV', 'OR', 'UT', 'WA', 'WY']],
  ['Bible Belt', ['AL', 'AR', 'GA', 'KY', 'LA', 'MS', 'MO', 'NC', 'OK',
    'SC', 'TN', 'TX', 'VA', 'WV']],
]

// ---- presets ---------------------------------------------------------------
// Each preset is a full filter state (applied over defaults) — a curated
// starting point a fundraiser can then refine. Ordered by how often they'd
// reach for it.
export type Preset = { id: string; label: string; hint: string
  filters: Partial<V5Filters> }
export const PRESETS: Preset[] = [
  {
    id: 'reachable-christian',
    label: 'Reachable Christian funders',
    hint: 'Give to Christian orgs, accept applications or contact, non-micro',
    filters: {
      tradition: [ANY_CHRISTIAN], min_tradition_dollars: '50000',
      application_status: ['Accepting Applications', 'Contact First'],
      has_contact: true, exclude_micro: true, exclude_testamentary: true,
      sort: 'christian',
    },
  },
  {
    id: 'high-confidence-christian',
    label: 'High-confidence Christian',
    hint: 'Only NTEE / church-code / GEN / human-confirmed Christian giving',
    filters: {
      tradition: [ANY_CHRISTIAN], tier: 'authoritative',
      min_tradition_recipients: '3', coverage_band: ['High', 'Moderate'],
      sort: 'christian',
    },
  },
  {
    id: 'accepting',
    label: 'Accepting applications',
    hint: 'Foundations with affirmative application evidence, non-micro',
    filters: {
      application_status: ['Accepting Applications'], exclude_micro: true,
    },
  },
  {
    id: 'catholic',
    label: 'Catholic funders',
    hint: 'Give to Catholic-classified recipients',
    filters: { tradition: ['catholic'], min_tradition_dollars: '50000',
      sort: 'christian' },
  },
  {
    id: 'evangelical',
    label: 'Evangelical funders',
    hint: 'Give to Evangelical / Protestant recipients',
    filters: { tradition: ['evangelical_protestant'],
      min_tradition_dollars: '50000', sort: 'christian' },
  },
  {
    id: 'major',
    label: 'Major funders ($1M+)',
    hint: 'Large grantmakers, excluding trusts and pass-through DAFs',
    filters: {
      min_paid: '1000000', exclude_testamentary: true, daf: 'exclude',
      sort: 'paid',
    },
  },
]

// ---- filter state ----------------------------------------------------------
// Numeric fields are kept as strings ('' = unset) so text inputs and URL
// round-tripping stay trivial; they are parsed when building query params.
export type V5Filters = {
  tradition: string[]
  tier: 'any' | 'authoritative' | 'mission'
  min_tradition_dollars: string
  min_tradition_recipients: string
  min_paid: string
  max_paid: string
  min_median: string
  max_median: string
  min_grants: string
  active_year: string // '' | '2023' | '2024'
  recipient_search: string
  state: string[]
  gives_to_state: string[]
  application_status: string[]
  has_website: boolean
  has_email: boolean
  has_contact: boolean
  min_assets: string
  max_assets: string
  min_revenue: string
  exclude_testamentary: boolean
  exclude_micro: boolean
  daf: 'include' | 'exclude' | 'only'
  coverage_band: string[]
  min_coverage: string
  min_christian: string
  min_pct_christian: string
  include_inactive: boolean
  deadline_season: string[]
  deadline_months: string[]
  deadline_from_month: string
  deadline_to_month: string
  deadline_kind: string[]
  gives_internationally: boolean
  country: string[]
  min_foreign: string
  min_pct_foreign: string
  min_foreign_christian: string
  min_countries: string
  sort: string
  order: 'asc' | 'desc'
}

export const defaultV5Filters: V5Filters = {
  tradition: [],
  tier: 'any',
  min_tradition_dollars: '',
  min_tradition_recipients: '',
  min_paid: '',
  max_paid: '',
  min_median: '',
  max_median: '',
  min_grants: '',
  active_year: '',
  recipient_search: '',
  state: [],
  gives_to_state: [],
  application_status: [],
  has_website: false,
  has_email: false,
  has_contact: false,
  min_assets: '',
  max_assets: '',
  min_revenue: '',
  exclude_testamentary: false,
  exclude_micro: false,
  daf: 'include',
  coverage_band: [],
  min_coverage: '',
  // No default Christian-dollar floor. A $50k floor was tried and hid 27,759
  // foundations that genuinely fund Christian work under that amount -- real
  // prospects, since a $10k grant matters to a small nonprofit. It also bought
  // nothing: sorting is % Christian desc with christian_dollars desc as the
  // tie-break, so large funders already lead each percentage band and the top
  // of the list is identical with or without the floor.
  min_christian: '',
  min_pct_christian: '',
  include_inactive: false,
  deadline_season: [],
  deadline_months: [],
  deadline_from_month: '',
  deadline_to_month: '',
  deadline_kind: [],
  gives_internationally: false,
  country: [],
  min_foreign: '',
  min_pct_foreign: '',
  min_foreign_christian: '',
  min_countries: '',
  sort: 'pct_christian',
  order: 'desc',
}

const LIST_KEYS = ['tradition', 'state', 'gives_to_state',
  'application_status', 'coverage_band', 'deadline_season', 'deadline_months',
  'deadline_kind', 'country'] as const
const NUM_KEYS = ['min_tradition_dollars', 'min_tradition_recipients',
  'min_paid', 'max_paid', 'min_median', 'max_median', 'min_grants',
  'min_assets', 'max_assets', 'min_revenue', 'min_coverage',
  'min_christian', 'min_pct_christian', 'deadline_from_month',
  'deadline_to_month', 'min_foreign', 'min_pct_foreign',
  'min_foreign_christian', 'min_countries'] as const
const BOOL_KEYS = ['has_website', 'has_email', 'has_contact',
  'exclude_testamentary', 'exclude_micro', 'include_inactive',
  'gives_internationally'] as const

// Build API query params (also used verbatim for URL sharing).
export function v5FilterParams(f: V5Filters): URLSearchParams {
  const p = new URLSearchParams()
  LIST_KEYS.forEach((k) => { if (f[k].length) p.set(k, f[k].join(',')) })
  if (f.tier !== 'any') p.set('tier', f.tier)
  NUM_KEYS.forEach((k) => {
    const n = Number(f[k])
    if (f[k] !== '' && Number.isFinite(n)) p.set(k, String(Math.round(n)))
  })
  BOOL_KEYS.forEach((k) => { if (f[k]) p.set(k, 'true') })
  if (f.active_year) p.set('active_year', f.active_year)
  if (f.recipient_search.trim()) p.set('recipient_search', f.recipient_search.trim())
  if (f.daf !== 'include') p.set('daf', f.daf)
  if (f.sort !== defaultV5Filters.sort) p.set('sort', f.sort)
  if (f.order !== defaultV5Filters.order) p.set('order', f.order)
  return p
}

// Restore filter state from a shared URL query string.
export function v5FiltersFromParams(sp: URLSearchParams): V5Filters {
  const f: V5Filters = { ...defaultV5Filters }
  LIST_KEYS.forEach((k) => {
    const v = sp.get(k)
    if (v) f[k] = v.split(',').filter(Boolean)
  })
  const tier = sp.get('tier')
  if (tier === 'authoritative' || tier === 'mission') f.tier = tier
  NUM_KEYS.forEach((k) => { const v = sp.get(k); if (v) f[k] = v })
  BOOL_KEYS.forEach((k) => { if (sp.get(k) === 'true') f[k] = true })
  f.active_year = sp.get('active_year') || ''
  f.recipient_search = sp.get('recipient_search') || ''
  const daf = sp.get('daf')
  if (daf === 'exclude' || daf === 'only') f.daf = daf
  f.sort = sp.get('sort') || defaultV5Filters.sort
  f.order = sp.get('order') === 'asc' ? 'asc' : defaultV5Filters.order
  return f
}

// ---- fetchers ---------------------------------------------------------------
async function getV5<T>(path: string): Promise<T> {
  if (STATIC_MODE) return staticRoute(path) as Promise<T>
  const res = await fetch(`${V5_BASE}${path}`)
  if (!res.ok) throw new Error(`v5 API ${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export function fetchStatsV5(): Promise<StatsV5> {
  return getV5('/api/v5/stats')
}

export function fetchFoundationsV5(
  queryString: string, limit = 500, offset = 0,
): Promise<FoundationsResponseV5> {
  const p = new URLSearchParams(queryString)
  p.set('limit', String(limit))
  p.set('offset', String(offset))
  return getV5(`/api/v5/foundations?${p.toString()}`)
}

export async function fetchFoundationDetailV5(
  ein: string,
): Promise<FoundationDetailV5> {
  const d = await getV5<FoundationDetailV5>(`/api/v5/foundations/${ein}`)
  // Static exports and any pre-existing cached payload predate the newer
  // rollups. Defaulting them to empty arrays here means a tab renders its own
  // empty state instead of throwing on `.filter` of undefined — the same
  // failure mode that once blanked the recipient panel.
  return {
    ...d,
    traditions: d.traditions ?? [],
    recipients: d.recipients ?? [],
    states: d.states ?? [],
    countries: d.countries ?? [],
    methods: d.methods ?? [],
    size_bands: d.size_bands ?? [],
    yearly: d.yearly ?? [],
    top_foreign: d.top_foreign ?? [],
  }
}

export function fetchFoundationGrantsV5(
  ein: string, limit = 100, offset = 0,
): Promise<{ rows: GrantRowV5[] }> {
  return getV5(`/api/v5/foundations/${ein}/grants?limit=${limit}&offset=${offset}`)
}

export function fetchRecipientV5(entityId: string): Promise<RecipientDetailV5> {
  return getV5(`/api/v5/recipients/${entityId}`)
}

// --- pages beyond the foundations explorer ----------------------------------

export type GrantsExplorerRow = {
  grantee_name: string
  city: string | null
  state: string | null
  amount: number
  tax_year: number
  purpose: string | null
  entity_id: string | null
  ein: string
  foundation_name: string
  tradition: string | null
  identity_status: string | null
}

export function fetchGrantsV5(qs: string): Promise<{
  total: number; total_dollars: number; rows: GrantsExplorerRow[]
}> {
  return getV5(`/api/v5/grants?${qs}`)
}

export type RecipientRowV5 = {
  entity_id: string
  name: string
  ein: string | null
  identity_status: string
  tradition: string | null
  method: string | null
  confidence: number | null
  reason: string | null
  is_daf: boolean
  total_received: number
  funder_count: number
  has_mission: boolean
}

export function fetchRecipientsV5(qs: string): Promise<{
  total: number; rows: RecipientRowV5[]
}> {
  return getV5(`/api/v5/recipients?${qs}`)
}

export function fetchRecipientsStatsV5(): Promise<{
  by_tradition: { tradition: string; recipients: number; dollars: number }[]
  by_method: { method: string; recipients: number }[]
  by_identity: { identity_status: string; recipients: number; dollars: number }[]
}> {
  return getV5('/api/v5/recipients-stats')
}

export function fetchStateBreakdownV5(): Promise<{
  state: string; foundations: number; paid: number; christian: number
}[]> {
  return getV5('/api/v5/analytics/state-breakdown')
}

export type TopFunderV5 = {
  ein: string; foundation_name: string; city: string | null
  state: string | null; paid_2324: number; christian_dollars: number
  coverage_pct: number; coverage_band: string
  application_status: string | null; recipient_count: number
}

export function fetchTopFundersV5(limit = 100, by = 'christian'):
  Promise<TopFunderV5[]> {
  return getV5(`/api/v5/analytics/top-funders?limit=${limit}&by=${by}`)
}

export function fetchYearlyTrendsV5(): Promise<{
  tax_year: number; grants: number; paid: number
  foundations: number; christian: number
}[]> {
  return getV5('/api/v5/analytics/yearly-trends')
}

export type DataQualityV5 = {
  totals: Record<string, number>
  coverage_bands: { coverage_band: string; foundations: number; paid: number }[]
  unattributable_reasons: { reason: string; foundations: number; dollars: number }[]
  identity: { identity_status: string; recipients: number; dollars: number }[]
  methods: { method: string; recipients: number }[]
  window: string
}

export function fetchDataQualityV5(): Promise<DataQualityV5> {
  return getV5('/api/v5/analytics/data-quality')
}

// --- static review build ----------------------------------------------------
// Netlify serves files, not queries. When no live API is present the app reads
// a pre-generated sample from /demo-v5 and applies the same filter, sort and
// pagination semantics client-side, so the reviewer sees the real product
// behaviour rather than a mock. Headline aggregates in that dataset are
// computed over the FULL database; only the browsable rows are sampled.
export const STATIC_MODE = import.meta.env.VITE_DEMO === '1'

let staticCache: Record<string, unknown> = {}

// Deterministic 2-hex bucket. Must match shard_for() in make_demo_v5.py.
function shardFor(entityId: string): string {
  let total = 0
  for (const char of entityId) total = (total * 31 + char.charCodeAt(0)) % 4096
  return (total % 128).toString(16).padStart(2, '0')
}

async function staticJson<T>(path: string): Promise<T> {
  if (staticCache[path] === undefined) {
    const res = await fetch(`/demo-v5/${path}`)
    if (!res.ok) throw new Error(`sample data missing: ${path}`)
    staticCache[path] = await res.json()
  }
  return staticCache[path] as T
}

export type SampleMeta = {
  generated_utc: string; sample: boolean
  foundations_in_sample: number; foundations_total: number
  foundations_with_giving: number
  grants_in_sample: number; grants_total: number
  recipients_in_sample: number; recipients_total: number
  window: string
}

export function fetchSampleMeta(): Promise<SampleMeta> {
  return staticJson<SampleMeta>('meta.json')
}

const CHRISTIAN_SET = new Set(CHRISTIAN_TRADITIONS.map(([v]) => v))

function num(p: URLSearchParams, k: string): number | null {
  const v = p.get(k)
  return v === null || v === '' ? null : Number(v)
}

// Mirrors the server's foundations endpoint for the filters the UI exposes.
async function staticFoundations(qs: string) {
  const p = new URLSearchParams(qs)
  let rows = (await staticJson<FoundationRowV5[]>('foundations.json')).slice()
  if (p.get('include_inactive') !== 'true') rows = rows.filter((r) => r.paid_2324 > 0)

  const tradition = p.get('tradition')
  const tier = p.get('tier') || 'any'
  const minTradDollars = num(p, 'min_tradition_dollars') ?? 0
  if (tradition) {
    const wanted = new Set(
      tradition.split(',').flatMap((t) =>
        t === ANY_CHRISTIAN ? [...CHRISTIAN_SET] : [t]))
    const anyChristian = [...wanted].every((t) => CHRISTIAN_SET.has(t))
    rows = rows.filter((r) => {
      // The sample carries per-foundation totals, not the full tradition
      // breakdown, so Christian filters use christian_dollars directly.
      const dollars = anyChristian ? r.christian_dollars : r.nonchristian_dollars
      return dollars > Math.max(minTradDollars, 0)
    })
  }
  const pairs: [string, (r: FoundationRowV5, v: number) => boolean][] = [
    ['min_paid', (r, v) => r.paid_2324 >= v],
    ['max_paid', (r, v) => r.paid_2324 <= v],
    ['min_median', (r, v) => (r.median_grant ?? 0) >= v],
    ['max_median', (r, v) => (r.median_grant ?? 0) <= v],
    ['min_grants', (r, v) => r.grant_count_2324 >= v],
    ['min_assets', (r, v) => (r.assets ?? 0) >= v],
    ['max_assets', (r, v) => (r.assets ?? 0) <= v],
    ['min_revenue', (r, v) => (r.revenue ?? 0) >= v],
    ['min_coverage', (r, v) => r.coverage_pct >= v],
    ['min_christian', (r, v) => r.christian_dollars >= v],
    ['min_pct_christian', (r, v) => (r.pct_christian ?? -1) >= v],
    ['min_foreign', (r, v) => r.foreign_dollars >= v],
    ['min_pct_foreign', (r, v) => (r.pct_foreign ?? -1) >= v],
    ['min_foreign_christian', (r, v) => r.foreign_christian_dollars >= v],
    ['min_countries', (r, v) => r.foreign_country_count >= v],
  ]
  for (const [key, test] of pairs) {
    const v = num(p, key)
    if (v !== null) rows = rows.filter((r) => test(r, v))
  }
  const listFilter = (key: string, get: (r: FoundationRowV5) => string | null) => {
    const raw = p.get(key)
    if (!raw) return
    const set = new Set(raw.split(',').map((s) => s.trim()))
    rows = rows.filter((r) => set.has(String(get(r))))
  }
  listFilter('state', (r) => (r.state || '').toUpperCase())
  listFilter('application_status', (r) => r.application_status)
  listFilter('coverage_band', (r) => r.coverage_band)
  if (p.get('has_website') === 'true') rows = rows.filter((r) => !!websiteUrlSafe(r.website))
  if (p.get('has_email') === 'true') rows = rows.filter(() => false)
  if (p.get('exclude_testamentary') === 'true') rows = rows.filter((r) => !r.is_testamentary)
  if (p.get('exclude_micro') === 'true') rows = rows.filter((r) => !r.is_micro)
  if (p.get('daf') === 'exclude') rows = rows.filter((r) => r.daf_dollars === 0)
  if (p.get('daf') === 'only') rows = rows.filter((r) => r.daf_dollars > 0)
  if (p.get('gives_internationally') === 'true') {
    rows = rows.filter((r) => r.foreign_dollars > 0)
  }
  const wantedCountries = p.get('country')
  if (wantedCountries) {
    const want = new Set(wantedCountries.split(',').map((c) => c.trim().toUpperCase()))
    rows = rows.filter((r) => (r.foreign_country_codes
      // Without the exported code list we cannot answer this precisely, so
      // fall back to "gave internationally at all" rather than silently
      // returning a wrong subset.
      ? r.foreign_country_codes.some((c) => want.has(c))
      : r.foreign_dollars > 0))
  }
  // Deadline months, mirroring the server's bitmask overlap test.
  const months = new Set<number>()
  for (const token of (p.get('deadline_season') || '').split(',')) {
    for (const m of SEASON_MONTHS[token.trim().toLowerCase()] || []) months.add(m)
  }
  for (const token of (p.get('deadline_months') || '').split(',')) {
    const m = Number(token)
    if (m >= 1 && m <= 12) months.add(m)
  }
  const from = num(p, 'deadline_from_month'), to = num(p, 'deadline_to_month')
  if (from && to) {
    // Walk forward so Nov->Feb wraps across the year end, as the server does.
    let m = from
    for (;;) { months.add(m); if (m === to) break; m = (m % 12) + 1 }
  }
  if (months.size) {
    rows = rows.filter((r) => (r.deadline_months || '')
      .split(',').some((x) => months.has(Number(x.trim()))))
  }
  listFilter('deadline_kind', (r) => r.deadline_kind)

  const sortKey = p.get('sort') || 'pct_christian'
  const desc = (p.get('order') || 'desc') === 'desc'
  const pctField = tier === 'authoritative' ? 'pct_christian_auth' : 'pct_christian'
  const value = (r: FoundationRowV5): number | string | null => {
    switch (sortKey) {
      case 'pct_christian': return r[pctField] as number | null
      case 'christian': return r.christian_dollars
      case 'coverage': return r.coverage_pct
      case 'assets': return r.assets ?? 0
      case 'median': return r.median_grant ?? 0
      case 'recipients': return r.recipient_count
      case 'name': return r.name
      case 'foreign': return r.foreign_dollars
      case 'foreign_christian': return r.foreign_christian_dollars
      case 'pct_foreign': return r.pct_foreign
      case 'countries': return r.foreign_country_count
      default: return r.paid_2324
    }
  }
  rows.sort((a, b) => {
    const av = value(a), bv = value(b)
    // NULL means "nothing could be classified" -- always last, never treated
    // as 0, matching the server's NULLS LAST behaviour.
    if (av === null && bv === null) return b.christian_dollars - a.christian_dollars
    if (av === null) return 1
    if (bv === null) return -1
    if (typeof av === 'string' || typeof bv === 'string') {
      const cmp = String(av).localeCompare(String(bv))
      return desc ? -cmp : cmp
    }
    if (av === bv) return b.christian_dollars - a.christian_dollars
    return desc ? (bv as number) - (av as number) : (av as number) - (bv as number)
  })
  const limit = Number(p.get('limit') || 50)
  const offset = Number(p.get('offset') || 0)
  return { total: rows.length, rows: rows.slice(offset, offset + limit) }
}

function websiteUrlSafe(raw: string | null): boolean {
  const v = (raw ?? '').trim().toLowerCase()
  if (!v || ['n/a', 'na', 'none', 'not applicable', '-'].includes(v)) return false
  return v.includes('.')
}

async function staticGrants(qs: string) {
  const p = new URLSearchParams(qs)
  let rows = (await staticJson<GrantsExplorerRow[]>('grants.json')).slice()
  const q = (p.get('q') || '').toLowerCase()
  if (q) rows = rows.filter((r) =>
    r.grantee_name.toLowerCase().includes(q) ||
    r.foundation_name.toLowerCase().includes(q))
  if (p.get('recipient_state')) rows = rows.filter((r) => r.state === p.get('recipient_state'))
  if (p.get('tax_year')) rows = rows.filter((r) => String(r.tax_year) === p.get('tax_year'))
  const min = num(p, 'amount_min')
  if (min !== null) rows = rows.filter((r) => r.amount >= min)
  const tradition = p.get('tradition')
  if (tradition === ANY_CHRISTIAN) rows = rows.filter((r) => r.tradition && CHRISTIAN_SET.has(r.tradition))
  else if (tradition) rows = rows.filter((r) => r.tradition === tradition)
  const size = Number(p.get('page_size') || 50)
  const page = Number(p.get('page') || 1)
  return {
    total: rows.length,
    total_dollars: rows.reduce((s, r) => s + r.amount, 0),
    rows: rows.slice((page - 1) * size, page * size),
  }
}

async function staticRecipients(qs: string) {
  const p = new URLSearchParams(qs)
  let rows = (await staticJson<RecipientRowV5[]>('recipients.json')).slice()
  const q = (p.get('q') || '').toLowerCase()
  if (q) rows = rows.filter((r) => r.name.toLowerCase().includes(q))
  const tradition = p.get('tradition')
  if (tradition === ANY_CHRISTIAN) rows = rows.filter((r) => r.tradition && CHRISTIAN_SET.has(r.tradition))
  else if (tradition === 'unclassified') rows = rows.filter((r) => !r.tradition)
  else if (tradition) rows = rows.filter((r) => r.tradition === tradition)
  if (p.get('identity_status')) rows = rows.filter((r) => r.identity_status === p.get('identity_status'))
  const min = num(p, 'min_received')
  if (min !== null) rows = rows.filter((r) => r.total_received >= min)
  const size = Number(p.get('page_size') || 50)
  const page = Number(p.get('page') || 1)
  return { total: rows.length, rows: rows.slice((page - 1) * size, page * size) }
}

type StaticDetail = FoundationDetailV5 & { grants: GrantRowV5[] }

export async function staticRoute(path: string): Promise<unknown> {
  const [route, qs = ''] = path.replace('/api/v5/', '').split('?')
  if (route === 'stats') return staticJson('stats.json')
  if (route === 'recipients-stats') return staticJson('recipients-stats.json')
  if (route.startsWith('analytics/')) return staticJson(`${route}.json`)
  if (route === 'foundations') return staticFoundations(qs)
  if (route === 'grants') return staticGrants(qs)
  if (route === 'recipients') return staticRecipients(qs)
  const detail = route.match(/^foundations\/(\d+)$/)
  if (detail) return staticJson<StaticDetail>(`foundation/${detail[1]}.json`)
  const grants = route.match(/^foundations\/(\d+)\/grants$/)
  if (grants) {
    const d = await staticJson<StaticDetail>(`foundation/${grants[1]}.json`)
    return { rows: d.grants }
  }
  const recipient = route.match(/^recipients\/(.+)$/)
  if (recipient) {
    const entityId = decodeURIComponent(recipient[1])
    const shard = await staticJson<Record<string, RecipientDetailV5>>(
      `recipient/${shardFor(entityId)}.json`)
    const found = shard[entityId]
    if (!found) throw new Error(`recipient not in sample: ${entityId}`)
    return found
  }
  throw new Error(`no sample data for ${route}`)
}
