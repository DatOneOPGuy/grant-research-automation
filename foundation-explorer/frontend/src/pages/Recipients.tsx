import { Fragment, useEffect, useMemo, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { apiGet } from '../lib/api'
import { moneyFull, num } from '../lib/format'
import { Badge, Card } from '../components/ui/primitives'

const TAGS = ['Christian Ministry', 'Church', 'Bible Translation',
  'Evangelism', 'Church Planting', 'Pregnancy Center', 'Christian School',
  'International Missions', 'Disaster Relief', 'Jewish Ministry',
  'Faith-Based Education', 'Rescue Mission', 'Youth Ministry',
  'Medical Missions']

export default function Recipients() {
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  const [tag, setTag] = useState('')
  const [source, setSource] = useState('')
  const [page, setPage] = useState(1)
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    const t = setTimeout(() => { setDebounced(q); setPage(1) }, 300)
    return () => clearTimeout(t)
  }, [q])

  const qs = useMemo(() => {
    const p = new URLSearchParams()
    if (debounced) p.set('q', debounced)
    if (tag) p.set('tag', tag)
    if (source) p.set('source', source)
    p.set('page', String(page))
    return p.toString()
  }, [debounced, tag, source, page])

  const { data, isFetching } = useQuery({
    queryKey: ['recipients', qs],
    queryFn: () => apiGet<any>(`/api/recipients?${qs}`),
    placeholderData: keepPreviousData,
  })
  const { data: funders } = useQuery({
    queryKey: ['funders', expanded],
    queryFn: () => apiGet<any>(`/api/recipients/${expanded}/funders`),
    enabled: !!expanded,
  })

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold text-primary mb-1">
        Recipients
      </h1>
      <div className="text-sm text-muted mb-6">
        {data ? `${num(data.total)} recipients in the knowledge base`
          : 'Loading…'}
      </div>

      <Card className="mb-4">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <input placeholder="Search recipient name…"
            className="border border-line rounded px-3 py-1.5 w-64"
            value={q} onChange={(e) => setQ(e.target.value)} />
          <select className="border border-line rounded px-2 py-1.5"
            value={tag} onChange={(e) => { setTag(e.target.value); setPage(1) }}>
            <option value="">Any tag</option>
            {TAGS.map((t) => <option key={t}>{t}</option>)}
          </select>
          <select className="border border-line rounded px-2 py-1.5"
            value={source}
            onChange={(e) => { setSource(e.target.value); setPage(1) }}>
            <option value="">Any source</option>
            <option value="seed">Seed</option>
            <option value="rule">Rule-tagged</option>
            <option value="llm">LLM-classified</option>
            <option value="pending">Pending</option>
          </select>
        </div>
      </Card>

      <Card>
        <table className={`w-full text-sm ${isFetching ? 'opacity-60' : ''}`}>
          <thead>
            <tr className="text-left text-xs text-muted border-b border-line">
              <th className="py-2 pr-3">Recipient</th>
              <th className="text-right pr-3">Largest grant</th>
              <th className="pr-3">Tags</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {data?.rows.map((r: any) => (
              <Fragment key={r.name_norm}>
                <tr
                  onClick={() => setExpanded(
                    expanded === r.name_norm ? null : r.name_norm,
                  )}
                  className="border-b border-line/60 hover:bg-canvas/70 cursor-pointer">
                  <td className="py-2 pr-3 font-medium">{r.display_name}</td>
                  <td className="text-right tabular pr-3">
                    {moneyFull(r.max_grant)}
                  </td>
                  <td className="pr-3">
                    <div className="flex flex-wrap gap-1">
                      {r.tags.slice(0, 4).map((t: any) => (
                        <Badge key={t.name}
                          className="bg-green-50 text-scorehigh">
                          {t.name}
                        </Badge>
                      ))}
                    </div>
                  </td>
                  <td className="text-muted text-xs">{r.source}</td>
                </tr>
                {expanded === r.name_norm && (
                  <tr className="bg-canvas/50">
                    <td colSpan={4} className="px-4 py-3">
                      <div className="text-xs text-muted mb-2">
                        Foundations that funded this recipient:
                      </div>
                      {funders?.funders?.length ? (
                        <table className="w-full text-xs">
                          <tbody>
                            {funders.funders.slice(0, 15).map((f: any) => (
                              <tr key={f.ein}>
                                <td className="py-0.5 pr-3">
                                  {f.foundation_name || f.ein}
                                </td>
                                <td className="tabular pr-3">
                                  {f.n} grant(s)
                                </td>
                                <td className="tabular pr-3">
                                  {moneyFull(f.dollars)}
                                </td>
                                <td className="text-muted">{f.years}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      ) : <div className="text-xs text-muted">Loading…</div>}
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
        <div className="flex justify-end gap-2 pt-3 text-sm">
          <button disabled={page <= 1} onClick={() => setPage(page - 1)}
            className="border border-line rounded px-3 py-1 disabled:opacity-40">
            Prev
          </button>
          <span className="py-1 text-muted tabular">Page {page}</span>
          <button onClick={() => setPage(page + 1)}
            className="border border-line rounded px-3 py-1">
            Next
          </button>
        </div>
      </Card>
    </div>
  )
}
