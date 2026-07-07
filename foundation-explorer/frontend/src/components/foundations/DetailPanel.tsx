import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink, X } from 'lucide-react'
import { apiGet } from '../../lib/api'
import { money, moneyFull, num, titleCase } from '../../lib/format'
import { Badge, Skeleton, StatusPill } from '../ui/primitives'

type Props = { ein: string; onClose: () => void }

const TABS = ['Overview', 'Grants', 'Recipients', 'Activities', 'Raw'] as const

export default function DetailPanel({ ein, onClose }: Props) {
  const [tab, setTab] = useState<(typeof TABS)[number]>('Overview')
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

function Overview({ d }: { d: any }) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-4 gap-3">
        <Stat label="Christian $ (3yr)"
          value={money(d.christian_dollars_3yr)} />
        <Stat label="Total giving (3yr)"
          value={money(d.total_giving_3yr)} />
        <Stat label="Qualifying distributions"
          value={money(d.distributions)} />
        <Stat label="Grants classified"
          value={d.classification_coverage != null
            ? `${d.classification_coverage}%` : '—'} />
      </div>
      <div className="border border-line rounded-lg p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="font-display font-medium text-primary">
            Christian giving
          </div>
          <Badge className={(d.classification_coverage ?? 0) >= 85
            ? 'bg-green-50 text-scorehigh' : 'bg-amber-50 text-scoremid'}>
            {d.christian_pct_floor != null
              ? ((d.classification_coverage ?? 0) >= 85
                ? `${d.christian_pct_floor}% Christian`
                : `${d.christian_pct_floor}–${d.christian_pct_ceiling}% Christian`)
              : '—'}
          </Badge>
        </div>
        <div className="text-sm text-muted">
          {(d.classification_coverage ?? 0) >= 85
            ? `We've classified ${d.classification_coverage}% of this `
              + `foundation's grants.`
            : `Range shown because we've classified `
              + `${d.classification_coverage ?? 0}% of grants — the true `
              + `figure sits between the floor and ceiling.`}
        </div>
        {(d.christian_dollars_2023 != null
          || d.christian_dollars_2024 != null) && (
          <div className="flex gap-4 mt-3 text-sm">
            {[['2023', d.christian_dollars_2023],
              ['2024', d.christian_dollars_2024],
              ['2025', d.christian_dollars_2025]].map(([y, v]) => (
              <div key={y as string}>
                <div className="text-xs text-muted">Christian $ {y}</div>
                <div className="tabular font-medium">{money(v as number)}</div>
              </div>
            ))}
          </div>
        )}
        {d.faith_categories && (
          <div className="flex flex-wrap gap-1 mt-3">
            {String(d.faith_categories).split('; ').slice(0, 8).map(
              (c: string) => (
                <Badge key={c} className="bg-canvas text-primary border border-line">
                  {c}
                </Badge>
              ),
            )}
          </div>
        )}
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
