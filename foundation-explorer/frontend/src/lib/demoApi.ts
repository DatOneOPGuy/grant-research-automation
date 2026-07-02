/* Static demo mode: emulates the FastAPI endpoints client-side over
   bundled JSON in /demo. Active when VITE_DEMO=1. */

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

function foundationList(p: URLSearchParams, rows: any[]) {
  const q = (p.get('q') || '').toLowerCase()
  const states = p.getAll('states')
  const tiers = p.getAll('tiers')
  const status = p.getAll('status')
  const sizes = p.getAll('sizes')
  const scoreMin = p.get('score_min')
  const scoreMax = p.get('score_max')

  let out = rows.filter((r) => {
    if (q && !(`${r.foundation_name} ${r.ein}`.toLowerCase().includes(q)))
      return false
    if (states.length && !states.includes(r.state)) return false
    if (scoreMin !== null && scoreMin !== '' &&
      !(r.faith_alignment_score >= Number(scoreMin))) return false
    if (scoreMax !== null && scoreMax !== '' &&
      !(r.faith_alignment_score <= Number(scoreMax))) return false
    if (tiers.length) {
      const ok = tiers.some((t) => t === 'Unclassified'
        ? r.faith_tier == null : r.faith_tier === t)
      if (!ok) return false
    }
    if (status.length) {
      const ok = status.some((s) => s === 'Unknown'
        ? !r.application_status : r.application_status === s)
      if (!ok) return false
    }
    if (sizes.length && !sizes.some((s) => SIZES[s]?.(r.distributions)))
      return false
    for (const [flag, col] of [
      ['has_filings', 'data_found'], ['has_contact', 'contact_person'],
      ['has_website', 'website'], ['has_phone', 'phone'],
      ['has_deadline', 'deadlines'],
    ] as const) {
      if (p.get(flag) === 'true') {
        const v = r[col]
        if (flag === 'has_filings' ? v !== 'Yes' : !v) return false
      }
    }
    return true
  })

  const sort = p.get('sort') || 'faith_alignment_score'
  const dir = p.get('direction') === 'asc' ? 1 : -1
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
    if (parts.length === 1) {
      return foundationList(p, await load('foundations'))
    }
    if (parts[1] === 'stats') return load('stats')
    const ein = parts[1]
    const base = (await load('foundations'))
      .find((r: any) => r.ein === ein)
    if (parts.length === 2) {
      const d = await load(`f/${ein}`)
      return { ...base, activities: d.activities, filings: [] }
    }
    const d = await load(`f/${ein}`)
    if (parts[2] === 'grants') {
      const q = (p.get('q') || '').toLowerCase()
      const rows = d.grants.filter((g: any) => !q ||
        `${g.grantee_name} ${g.purpose}`.toLowerCase().includes(q))
      return {
        total: d.grants_total, total_dollars: d.grants_dollars, rows,
      }
    }
    if (parts[2] === 'recipients') {
      return {
        distinct_recipients: d.recipients.length, top: d.recipients,
      }
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
    if (p.get('foreign_only') === 'true')
      rows = rows.filter((g) => g.is_foreign)
    const page = Number(p.get('page') || 1)
    const total_dollars = rows.reduce((s, g) => s + (g.amount || 0), 0)
    return {
      total: rows.length, total_dollars, page,
      rows: rows.slice((page - 1) * 50, page * 50),
    }
  }

  if (parts[0] === 'recipients') {
    if (parts.length === 1) {
      let rows = (await load('recipients')) as any[]
      const q = (p.get('q') || '').toLowerCase()
      if (q) rows = rows.filter((r) =>
        r.display_name.toLowerCase().includes(q))
      if (p.get('tag')) rows = rows.filter((r) =>
        r.tags.some((t: any) => t.name === p.get('tag')))
      if (p.get('source'))
        rows = rows.filter((r) => r.source === p.get('source'))
      const page = Number(p.get('page') || 1)
      return {
        total: rows.length, page,
        rows: rows.slice((page - 1) * 50, page * 50),
      }
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
