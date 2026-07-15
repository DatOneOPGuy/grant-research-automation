import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bookmark, ExternalLink, X } from 'lucide-react'
import { apiGet } from '../../lib/api'
import { useSavedFoundations } from '../../lib/savedContext'
import { money, moneyFull, num, taxWindow, titleCase } from '../../lib/format'
import { Badge, Skeleton, StatusPill, VerdictBadge } from '../ui/primitives'

type Props = { ein: string; onClose: () => void }

const TABS = ['Overview', 'Grants', 'Recipients', 'Activities', 'Raw'] as const

export default function DetailPanel({ ein, onClose }: Props) {
  const [tab, setTab] = useState<(typeof TABS)[number]>('Overview')
  const { isSaved, toggle } = useSavedFoundations()
  const { data } = useQuery({
    queryKey: ['foundation', ein],
    queryFn: () => apiGet<any>(`/api/foundations/${ein}`),
  })

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/20" onClick={onClose} />
      <div className="relative w-[52%] min-w-[560px] h-full bg-surface shadow-2xl overflow-y-auto">
        <div className="sticky top-0 bg-surface border-b border-line px-6 py-4 z-10">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="font-display text-2xl font-semibold text-primary">
                {data ? titleCase(data.foundation_name)
                  : <Skeleton className="h-7 w-72" />}
              </h2>
              <div className="text-sm text-muted mt-1">
                EIN {ein} · {data?.city}{data?.city && ','} {data?.state}
                {data?.latest_tax_year && ` · TY ${data.latest_tax_year}`}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => toggle(ein)}
                className={`flex items-center gap-1 text-sm rounded-md px-2.5 py-1 border ${
                  isSaved(ein)
                    ? 'bg-accent/10 border-accent text-primary'
                    : 'border-line text-muted hover:border-primary'}`}>
                <Bookmark size={14}
                  className={isSaved(ein) ? 'fill-accent text-accent' : ''} />
                {isSaved(ein) ? 'Saved' : 'Save'}
              </button>
              {data?.propublica_url && (
                <a href={data.propublica_url} target="_blank" rel="noreferrer"
                  className="text-sm text-primary underline flex items-center gap-1">
                  ProPublica <ExternalLink size={13} />
                </a>
              )}
              <button onClick={onClose}
                className="p-1.5 rounded hover:bg-canvas">
                <X size={18} />
              </button>
            </div>
          </div>
          <div className="flex gap-1 mt-4">
            {TABS.map((t) => (
              <button key={t} onClick={() => setTab(t)}
                className={`px-3 py-1.5 text-sm rounded-md ${
                  tab === t ? 'bg-primary text-white'
                    : 'text-muted hover:bg-canvas'}`}>
                {t}
              </button>
            ))}
          </div>
        </div>
        <div className="p-6">
          {!data ? <Skeleton className="h-64" /> : (
            <>
              {tab === 'Overview' && <Overview d={data} />}
              {tab === 'Grants' && <GrantsTab ein={ein} />}
              {tab === 'Recipients' && <RecipientsTab ein={ein} />}
              {tab === 'Activities' && <Activities d={data} />}
              {tab === 'Raw' && (
                <pre className="text-xs bg-canvas rounded p-4 overflow-x-auto">
                  {JSON.stringify(data, null, 2)}
                </pre>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <div className="font-medium tabular">{value}</div>
    </div>
  )
}

function ChristianEvidence({ ein, years }: { ein: string; years: string }) {
  const [showAll, setShowAll] = useState(false)
  const { data } = useQuery({
    queryKey: ['evidence', ein],
    queryFn: () => apiGet<any>(`/api/foundations/${ein}/christian-evidence`),
  })
  if (!data) return <Skeleton className="h-24" />
  if (!data.count) {
    return <div className="text-sm text-muted">
      No confirmed Christian recipients in {years} filings.
    </div>
  }
  const rows = showAll ? data.recipients : data.recipients.slice(0, 15)
  return (
    <div>
      <table className="w-full text-sm">
        <tbody>
          {rows.map((r: any, i: number) => (
            <tr key={i} className="border-b border-line/50">
              <td className="py-1.5 pr-2 font-medium">
                {titleCase(r.name)}
                {r.tradition && (
                  <span className="text-xs text-muted font-normal ml-1">
                    · {r.tradition}
                  </span>
                )}
              </td>
              <td className="text-right tabular pr-3 whitespace-nowrap">
                {moneyFull(r.total)}
              </td>
              <td className="text-right tabular text-muted text-xs whitespace-nowrap">
                most recent: {r.most_recent_year}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {data.count > 15 && (
        <button onClick={() => setShowAll(!showAll)}
          className="text-sm text-primary mt-2 hover:underline">
          {showAll ? 'Show fewer'
            : `Show all ${data.count} Christian organizations`}
        </button>
      )}
    </div>
  )
}

function Overview({ d }: { d: any }) {
  const years = taxWindow(d.tax_year_start, d.tax_year_end)
  const staleChristian = d.most_recent_christian_year
    && d.latest_tax_year
    && d.most_recent_christian_year < d.latest_tax_year
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <VerdictBadge verdict={d.verdict} />
        <StatusPill status={d.application_status} />
      </div>
      <div className="grid grid-cols-3 gap-3">
        <Stat label={`Confirmed Christian $ (${years})`}
          value={money(d.christian_dollars_3yr)} />
        <Stat label="Christian orgs funded"
          value={d.christian_recipient_count ?? '—'} />
        <Stat label={`Reported grant dollars (${years})`}
          value={money(d.total_giving_3yr)} />
      </div>

      {/* Evidence — the Christian organizations funded */}
      <div className="border border-line rounded-lg p-4">
        <div className="font-display font-medium text-primary mb-1">
          Christian organizations this foundation has funded ({years})
        </div>
        {staleChristian && (
          <div className="text-xs text-scoremid mb-2">
            Note: most recent Christian grant was {d.most_recent_christian_year}
            {' '}(latest filing {d.latest_tax_year}) — Christian giving may have
            decreased recently.
          </div>
        )}
        <ChristianEvidence ein={d.ein} years={years} />
      </div>

      <div className="text-xs text-muted italic border-l-2 border-line pl-3">
        Based on grants reported in IRS 990-PF filings, {years}. We recommend
        confirming current priorities and application requirements directly with
        the foundation before applying.
      </div>

      <div className="border border-line rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="font-display font-medium text-primary">
            Application
          </div>
          <StatusPill status={d.application_status} />
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <Stat label="Contact" value={d.contact_person || '—'} />
          <Stat label="Phone" value={d.phone || '—'} />
          <Stat label="Email" value={d.contact_email || '—'} />
          <Stat label="Website" value={d.website || '—'} />
        </div>
        {d.contact_address && (
          <div className="text-sm mt-3">
            <span className="text-xs text-muted block">Address</span>
            {d.contact_address}
          </div>
        )}
        {d.application_format && (
          <div className="text-sm mt-3">
            <span className="text-xs text-muted block">Format</span>
            {d.application_format}
          </div>
        )}
        {d.deadlines && (
          <div className="text-sm mt-3">
            <span className="text-xs text-muted block">Deadlines</span>
            {d.deadlines}
          </div>
        )}
        {d.restrictions && (
          <div className="text-sm mt-3">
            <span className="text-xs text-muted block">Restrictions</span>
            {d.restrictions}
          </div>
        )}
      </div>
      {d.states_given_to && (
        <div className="text-sm">
          <span className="text-xs text-muted block mb-1">
            States given to
          </span>
          {d.states_given_to}
        </div>
      )}
    </div>
  )
}

function GrantsTab({ ein }: { ein: string }) {
  const [q, setQ] = useState('')
  const { data } = useQuery({
    queryKey: ['fgrants', ein, q],
    queryFn: () => apiGet<any>(
      `/api/foundations/${ein}/grants?page_size=100&q=${encodeURIComponent(q)}`,
    ),
  })
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <input
          placeholder="Search recipients or purpose…"
          className="border border-line rounded px-3 py-1.5 text-sm w-72"
          value={q} onChange={(e) => setQ(e.target.value)}
        />
        {data && (
          <div className="text-sm text-muted tabular">
            {num(data.total)} grants · {money(data.total_dollars)}
          </div>
        )}
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-muted border-b border-line">
            <th className="py-2">Recipient</th>
            <th>Location</th>
            <th className="text-right">Amount</th>
            <th>Purpose</th>
            <th>Year</th>
          </tr>
        </thead>
        <tbody>
          {data?.rows.map((g: any, i: number) => (
            <tr key={i} className="border-b border-line/60">
              <td className="py-2 pr-3 font-medium">{g.grantee_name}</td>
              <td className="pr-3 text-muted">
                {g.is_foreign ? g.country : `${g.city}, ${g.state}`}
              </td>
              <td className="text-right tabular pr-3">
                {moneyFull(g.amount)}
              </td>
              <td className="pr-3 text-muted max-w-56 truncate"
                title={g.purpose}>{g.purpose}</td>
              <td className="tabular">{g.tax_year}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RecipientsTab({ ein }: { ein: string }) {
  const { data } = useQuery({
    queryKey: ['frecipients', ein],
    queryFn: () => apiGet<any>(`/api/foundations/${ein}/recipients`),
  })
  return (
    <div>
      {data && (
        <div className="text-sm text-muted mb-3">
          {num(data.distinct_recipients)} unique recipients. Top 20 by dollars:
        </div>
      )}
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-muted border-b border-line">
            <th className="py-2">Recipient</th>
            <th className="text-right">Grants</th>
            <th className="text-right">Total</th>
            <th className="text-right">Years</th>
            <th>Tags</th>
          </tr>
        </thead>
        <tbody>
          {data?.top.map((r: any) => (
            <tr key={r.grantee_name} className="border-b border-line/60">
              <td className="py-2 pr-3 font-medium">{r.grantee_name}</td>
              <td className="text-right tabular pr-3">{r.grant_count}</td>
              <td className="text-right tabular pr-3">
                {moneyFull(r.total_amount)}
              </td>
              <td className="text-right tabular pr-3">{r.years}</td>
              <td>
                <div className="flex flex-wrap gap-1">
                  {r.tags?.slice(0, 3).map((t: any) => (
                    <Badge key={t.name}
                      className="bg-green-50 text-scorehigh">
                      {t.name}
                    </Badge>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Activities({ d }: { d: any }) {
  if (!d.activities?.length) {
    return <div className="text-sm text-muted">
      No charitable activity descriptions in the filings.
    </div>
  }
  return (
    <div className="space-y-3">
      {d.activities.map((a: any, i: number) => (
        <div key={i} className="border border-line rounded-lg p-4 text-sm">
          <div className="flex justify-between text-xs text-muted mb-1">
            <span>TY {a.tax_year}</span>
            {a.expenses > 0 && <span className="tabular">
              {moneyFull(a.expenses)}</span>}
          </div>
          {a.description}
        </div>
      ))}
    </div>
  )
}
