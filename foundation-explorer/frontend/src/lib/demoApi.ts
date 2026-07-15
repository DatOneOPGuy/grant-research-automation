/* Static demo mode: emulates the FastAPI endpoints client-side over
   bundled JSON in /demo. Active when detectDemo() is true. */

const cache = new Map<string, any>()

async function load(name: string): Promise<any> {
  if (!cache.has(name)) {
    const res = await fetch(`${import.meta.env.BASE_URL}demo/${name}.json`)
    if (!res.ok) throw new Error(`demo data missing: ${name}`)
    cache.set(name, await res.json())
  }
  return cache.get(name)
}

const SIZES: Record<string, (d: number | null) => boolean> = {
  'lt100k': (d) => d !== null && d < 100_000,
  '100k-1m': (d) => d !== null && d >= 100_000 && d < 1_000_000,
  '1m-10m': (d) => d !== null && d >= 1_000_000 && d < 10_000_000,
  'gte10m': (d) => d !== null && d >= 10_000_000,
}

type Preset = {
  where: (r: any) => boolean
  sort: string
  dir: 'asc' | 'desc'
}
const REACHABLE = (r: any) =>
  r.application_status === 'Accepting Applications'
  || r.application_status === 'Contact First'
const STRONG = (r: any) => r.verdict === 'Funds Christian organizations'
const PRESETS: Record<string, Preset> = {
  'best-prospects': {
    where: (r) => STRONG(r) && REACHABLE(r)
      && !Number(r.is_testamentary_trust),
    sort: 'christian_dollars_3yr', dir: 'desc',
  },
  'top-christian-dollars': {
    where: (r) => r.verdict !== 'No confirmed Christian giving'
      && !Number(r.is_testamentary_trust),
    sort: 'christian_dollars_3yr', dir: 'desc',
  },
  'accepting': {
    where: (r) => STRONG(r)
      && r.application_status === 'Accepting Applications'
      && !Number(r.is_testamentary_trust),
    sort: 'christian_dollars_3yr', dir: 'desc',
  },
}

const REGIONS: Record<string, string[]> = {
  northeast: ['CT', 'ME', 'MA', 'NH', 'RI', 'VT', 'NJ', 'NY', 'PA'],
  southeast: ['DE', 'FL', 'GA', 'MD', 'NC', 'SC', 'VA', 'DC', 'WV', 'AL',
    'KY', 'MS', 'TN', 'AR', 'LA'],
  midwest: ['IL', 'IN', 'MI', 'OH', 'WI', 'IA', 'KS', 'MN', 'MO', 'NE',
    'ND', 'SD'],
  southwest: ['AZ', 'NM', 'OK', 'TX'],
  west: ['CO', 'ID', 'MT', 'NV', 'UT', 'WY', 'AK', 'CA', 'HI', 'OR', 'WA'],
}
const TYPICAL: Record<string, (n: number) => boolean> = {
  'lt10k': (n) => n < 10000,
  '10k-50k': (n) => n >= 10000 && n < 50000,
  '50k-250k': (n) => n >= 50000 && n < 250000,
  'gte250k': (n) => n >= 250000,
}
const ASSETS: Record<string, (n: number) => boolean> = {
  'lt1m': (n) => n < 1e6, '1m-10m': (n) => n >= 1e6 && n < 1e7,
  '10m-100m': (n) => n >= 1e7 && n < 1e8, 'gte100m': (n) => n >= 1e8,
}

function foundationList(p: URLSearchParams, rows: any[]) {
  const q = (p.get('q') || '').toLowerCase()
  const states = p.getAll('states')
  const sizes = p.getAll('sizes')
  const traditions = p.getAll('traditions')
  const typicalSizes = p.getAll('typical_sizes')
  const status = p.getAll('status')
  const assetBuckets = p.getAll('asset_buckets')
  const presetKey = p.get('preset') || ''
  const preset = PRESETS[presetKey]
  const numOr = (k: string) => {
    const v = p.get(k)
    return v === null || v === '' ? undefined : Number(v)
  }
  const minOrgs = numOr('min_orgs')
  const christianMin = numOr('christian_min')
  const largestMin = numOr('largest_min')
  const region = p.get('region')
  const givesIn = p.get('gives_in_state')

  let out = rows.filter((r) => {
    if (preset && !preset.where(r)) return false
    // Foundations page (no preset): all confirmed Christian funders.
    if (!preset && r.verdict === 'No confirmed Christian giving') return false
    if (q && !(`${r.foundation_name} ${r.ein} ${r.city}`
      .toLowerCase().includes(q))) return false
    // depth
    if (minOrgs !== undefined && !(r.christian_recipient_count >= minOrgs))
      return false
    if (christianMin !== undefined && !(r.christian_dollars_3yr >= christianMin))
      return false
    if (p.get('recently_active') === 'true'
      && !(r.most_recent_christian_year >= 2024)) return false
    if (traditions.length && !traditions.includes(r.predominant_tradition))
      return false
    // grant size
    if (typicalSizes.length
      && !typicalSizes.some((s) => TYPICAL[s]?.(r.typical_grant_size)))
      return false
    if (largestMin !== undefined && !(r.largest_christian_grant >= largestMin))
      return false
    // reachability detail
    if (status.length && !status.includes(r.application_status)) return false
    for (const [flag, col] of [
      ['has_contact', 'contact_person'], ['has_website', 'website'],
      ['has_phone', 'phone'], ['has_deadline', 'deadlines'],
    ] as const) {
      if (p.get(flag) === 'true' && !r[col]) return false
    }
    // geography
    if (states.length && !states.includes(r.state)) return false
    if (region && REGIONS[region] && !REGIONS[region].includes(r.state))
      return false
    if (givesIn && !(r.states_given_to || '').includes(givesIn)) return false
    // profile
    if (sizes.length && !sizes.some((s) => SIZES[s]?.(r.distributions)))
      return false
    if (assetBuckets.length
      && !assetBuckets.some((s) => ASSETS[s]?.(r.assets))) return false
    if (p.get('actively_giving') === 'true' && !Number(r.is_actively_giving))
      return false
    if (!preset) {
      if (p.get('include_trusts') !== 'true' && Number(r.is_testamentary_trust))
        return false
      if (p.get('include_small') !== 'true' && Number(r.is_small_fund))
        return false
    }
    return true
  })

  let sort = p.get('sort') || ''
  let dir = p.get('direction') === 'asc' ? 1 : -1
  if (preset && !sort) { sort = preset.sort; dir = preset.dir === 'asc' ? 1 : -1 }
  if (!sort) sort = 'christian_dollars_3yr'
  out = out.sort((a, b) => {
    const av = a[sort], bv = b[sort]
    if (av == null) return 1
    if (bv == null) return -1
    return (av > bv ? 1 : av < bv ? -1 : 0) * dir
  })

  const page = Number(p.get('page') || 1)
  const size = Number(p.get('page_size') || 50)
  return {
    total: out.length, page, page_size: size,
    rows: out.slice((page - 1) * size, page * size),
  }
}

export async function demoGet(path: string): Promise<any> {
  const url = new URL(path, 'http://demo')
  const p = url.searchParams
  const parts = url.pathname.replace(/^\/api\//, '').split('/')

  if (parts[0] === 'foundations') {
    if (parts.length === 1) return foundationList(p, await load('foundations'))
    if (parts[1] === 'stats') return load('stats')
    const ein = parts[1]
    const base = (await load('foundations')).find((r: any) => r.ein === ein)
    const d = await load(`f/${ein}`).catch(() => ({}))
    if (parts.length === 2) {
      return { ...base, activities: d.activities || [], filings: [] }
    }
    if (parts[2] === 'grants') {
      const q = (p.get('q') || '').toLowerCase()
      const rows = (d.grants || []).filter((g: any) => !q ||
        `${g.grantee_name} ${g.purpose}`.toLowerCase().includes(q))
      return { total: d.grants_total || rows.length,
        total_dollars: d.grants_dollars || 0, rows }
    }
    if (parts[2] === 'recipients') {
      return { distinct_recipients: (d.recipients || []).length,
        top: d.recipients || [] }
    }
    if (parts[2] === 'christian-evidence') {
      const ev = d.christian_evidence || []
      return { count: ev.length, recipients: ev }
    }
  }

  if (parts[0] === 'grants') {
    let rows = (await load('grants')) as any[]
    const q = (p.get('q') || '').toLowerCase()
    const years = p.getAll('years').map(Number)
    if (q) rows = rows.filter((g) =>
      `${g.grantee_name} ${g.purpose}`.toLowerCase().includes(q))
    if (years.length) rows = rows.filter((g) => years.includes(g.tax_year))
    if (p.get('recipient_state'))
      rows = rows.filter((g) => g.state === p.get('recipient_state'))
    if (p.get('amount_min'))
      rows = rows.filter((g) => g.amount >= Number(p.get('amount_min')))
    if (p.get('foreign_only') === 'true') rows = rows.filter((g) => g.is_foreign)
    const page = Number(p.get('page') || 1)
    return { total: rows.length,
      total_dollars: rows.reduce((s, g) => s + (g.amount || 0), 0),
      page, rows: rows.slice((page - 1) * 50, page * 50) }
  }

  if (parts[0] === 'recipients') {
    if (parts[1] === 'stats') {
      const rows = (await load('recipients')) as any[]
      const bySource: Record<string, number> = {}
      rows.forEach((row) => {
        bySource[row.source] = (bySource[row.source] || 0) + 1
      })
      return { by_source: bySource,
        pipeline_version: rows.some((row) => row.classification) ? 2 : 1 }
    }
    if (parts.length === 1) {
      let rows = (await load('recipients')) as any[]
      const q = (p.get('q') || '').toLowerCase()
      if (q) rows = rows.filter((r) => r.display_name.toLowerCase().includes(q))
      if (p.get('tag')) rows = rows.filter((r) =>
        r.classification === p.get('tag')
        || r.tags.some((t: any) => t.name === p.get('tag')))
      if (p.get('source')) rows = rows.filter((r) => r.source === p.get('source'))
      const page = Number(p.get('page') || 1)
      return { total: rows.length, page,
        rows: rows.slice((page - 1) * 50, page * 50) }
    }
    if (parts[2] === 'funders') return { funders: [] }
  }

  if (parts[0] === 'analytics') {
    const a = await load('analytics')
    if (parts[1] === 'top-funders') {
      const limit = Number(p.get('limit') || 100)
      return a['top-funders'].slice(0, limit)
    }
    return a[parts[1]]
  }

  throw new Error(`demo mode: unhandled path ${path}`)
}
