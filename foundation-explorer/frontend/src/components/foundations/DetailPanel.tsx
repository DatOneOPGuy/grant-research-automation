import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink, X } from 'lucide-react'
import {
  fetchFoundationDetailV5, fetchFoundationGrantsV5, type GrantRowV5,
} from '../../lib/apiV5'
import {
  money, moneyFull, propublicaUrl, titleCase, websiteUrl,
} from '../../lib/format'
import { Skeleton, StatusPill } from '../ui/primitives'
import { BucketBarLabeled } from './BucketBar'
import { IdentityChip, TraditionChip } from './V5Chips'
import RecipientsTab from './RecipientsTab'

type Props = { ein: string; onClose: () => void }

// Three different truths that used to share one vague message. Each is the
// real legal or filing reason the dollars could not be attributed; see
// logs/parser_recipient_audit.md for the raw-XML evidence behind each class.
function unattributableMessage(reason: string | null, amount: string) {
  switch (reason) {
    case 'hipaa':
      return `${amount} went to individual patients through a
        patient-assistance program. Federal privacy law (HIPAA) prohibits
        naming them, so these dollars cannot be attributed to an organization
        — they are excluded from the coverage figure rather than counted
        against it.`
    case 'foreign_4948':
      return `${amount} was paid by a foreign private foundation, which is not
        required to itemize grant recipients under IRC §4948(b). These dollars
        cannot be attributed and are excluded from coverage.`
    case 'pdf_attachment':
      return `${amount} went to recipients this foundation listed in a PDF
        attachment rather than in machine-readable form, so they cannot be
        extracted from the electronic filing. The list exists — it just isn’t
        machine-readable. These dollars are excluded from coverage rather than
        counted against it.`
    default:
      return `${amount} went to recipients that are not itemized in the
        machine-readable filing, so they cannot be attributed to an
        organization. These dollars are excluded from the coverage figure
        rather than counted against it.`
  }
}

const TABS = ['Recipients', 'Grants', 'Geography'] as const

export default function DetailPanel({ ein, onClose }: Props) {
  const [tab, setTab] = useState<(typeof TABS)[number]>('Recipients')
  const { data, isError } = useQuery({
    queryKey: ['v5foundation', ein],
    queryFn: () => fetchFoundationDetailV5(ein),
  })
  const f = data?.foundation

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/20" onClick={onClose} />
      <div className="relative w-[52%] min-w-[560px] h-full bg-surface shadow-2xl overflow-y-auto">
        <div className="sticky top-0 bg-surface border-b border-line px-6 py-4 z-10">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="font-display text-2xl font-semibold text-primary">
                {f ? titleCase(f.name) : <Skeleton className="h-7 w-72" />}
              </h2>
              <div className="text-sm text-muted mt-1 flex items-center gap-2 flex-wrap">
                <span>EIN {ein}
                  {f?.city && <> · {titleCase(f.city)}, {f.state}</>}</span>
                {f && <span className="tabular font-medium text-ink">
                  {money(f.paid_2324)} paid 2023–24</span>}
                {f && <StatusPill status={f.application_status} />}
                {websiteUrl(f?.website) && (
                  <a href={websiteUrl(f?.website) as string}
                    target="_blank" rel="noreferrer"
                    className="text-primary underline flex items-center gap-1">
                    Website <ExternalLink size={12} />
                  </a>
                )}
                <a href={propublicaUrl(ein)}
                  target="_blank" rel="noreferrer"
                  className="text-primary underline flex items-center gap-1">
                  ProPublica <ExternalLink size={12} />
                </a>
              </div>
            </div>
            <button onClick={onClose} className="p-1.5 rounded hover:bg-canvas">
              <X size={18} />
            </button>
          </div>

          {f && (
            <div className="mt-4">
              <BucketBarLabeled b={{
                christian: f.christian_dollars,
                nonchristian: f.nonchristian_dollars,
                unclassified: f.unclassified_dollars,
                daf: f.daf_dollars,
              }} />
              <div className="text-xs text-muted mt-1.5">
                {f.classifiable_dollars > 0 && (
                  <>
                    We have classified {Math.round(f.coverage_pct)}% of this
                    foundation’s {money(f.classifiable_dollars)} in 2023–24
                    giving to identifiable organizations ({f.coverage_band}{' '}
                    coverage).
                  </>
                )}
                {f.nonclassifiable_dollars > 0 && (
                  <div className="mt-1">
                    {unattributableMessage(f.unattributable_reason,
                      money(f.nonclassifiable_dollars))}
                  </div>
                )}
              </div>
            </div>
          )}

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
          {isError && (
            <div className="text-sm text-scoremid">
              Could not load foundation detail — is the v5 API running on
              localhost:8000?
            </div>
          )}
          {!data && !isError && <Skeleton className="h-64" />}
          {data && (
            <>
              {tab === 'Recipients' && (
                <RecipientsTab recipients={data.recipients} />
              )}
              {tab === 'Grants' && <GrantsTab ein={ein} />}
              {tab === 'Geography' && <GeographyTab states={data.states} />}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

const GRANTS_PAGE = 100

function GrantsTab({ ein }: { ein: string }) {
  const [limit, setLimit] = useState(GRANTS_PAGE)
  const { data } = useQuery({
    queryKey: ['v5grants', ein, limit],
    queryFn: () => fetchFoundationGrantsV5(ein, limit, 0),
  })
  if (!data) return <Skeleton className="h-40" />
  return (
    <div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-muted border-b border-line">
            <th className="py-2">Recipient</th>
            <th>Location</th>
            <th className="text-right">Amount</th>
            <th>Year</th>
            <th>Purpose</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((g: GrantRowV5, i: number) => (
            <tr key={i} className="border-b border-line/60">
              <td className="py-2 pr-3 font-medium">
                {titleCase(g.recipient_name)}
                {g.tradition && <span className="ml-1.5">
                  <TraditionChip tradition={g.tradition} /></span>}
                {g.identity_status && g.identity_status !== 'matched' && (
                  <span className="ml-1">
                    <IdentityChip status={g.identity_status} /></span>
                )}
              </td>
              <td className="pr-3 text-muted whitespace-nowrap">
                {g.recipient_city && `${titleCase(g.recipient_city)}, `}
                {g.recipient_state}
              </td>
              <td className="text-right tabular pr-3 whitespace-nowrap">
                {moneyFull(g.amount)}
              </td>
              <td className="tabular pr-3">{g.tax_year}</td>
              <td className="text-muted max-w-56 truncate"
                title={g.purpose || undefined}>{g.purpose}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {data.rows.length >= limit && (
        <button onClick={() => setLimit(limit + GRANTS_PAGE)}
          className="text-sm text-primary mt-3 hover:underline">
          Load more grants
        </button>
      )}
    </div>
  )
}

function GeographyTab({ states }: {
  states: { state: string; dollars: number }[]
}) {
  if (!states.length) {
    return <div className="text-sm text-muted">
      No recipient geography recorded.
    </div>
  }
  const max = Math.max(...states.map((s) => s.dollars), 1)
  return (
    <div className="space-y-1.5 max-w-md">
      {states.map((s) => (
        <div key={s.state} className="flex items-center gap-3 text-sm">
          <span className="w-8 text-muted tabular">{s.state || '—'}</span>
          <div className="flex-1 h-3 bg-line/40 rounded overflow-hidden">
            <div className="h-full bg-scorehigh/70 rounded"
              style={{ width: `${(s.dollars / max) * 100}%` }} />
          </div>
          <span className="w-20 text-right tabular font-medium">
            {money(s.dollars)}
          </span>
        </div>
      ))}
    </div>
  )
}
