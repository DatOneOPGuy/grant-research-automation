import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink, X } from 'lucide-react'
import { MONTH_NAMES, fetchFoundationDetailV5 } from '../../lib/apiV5'
import { recordView } from '../../lib/recentStore'
import SaveMenu from './SaveMenu'
import { money, propublicaUrl, titleCase, websiteUrl } from '../../lib/format'
import { Skeleton, StatusPill } from '../ui/primitives'
import { BucketBarLabeled } from './BucketBar'
import RecipientsTab from './RecipientsTab'
import OverviewTab from './tabs/OverviewTab'
import GrantsTab from './tabs/GrantsTab'
import GeographyTab from './tabs/GeographyTab'
import InternationalTab from './tabs/InternationalTab'
import EvidenceTab from './tabs/EvidenceTab'
import ApplicationTab from './tabs/ApplicationTab'

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

const ALL_TABS = ['Overview', 'Recipients', 'Grants', 'International',
  'Geography', 'Evidence', 'Application'] as const
type Tab = (typeof ALL_TABS)[number]

export default function DetailPanel({ ein, onClose }: Props) {
  const [tab, setTab] = useState<Tab>('Overview')
  const { data, isError } = useQuery({
    queryKey: ['v5foundation', ein],
    queryFn: () => fetchFoundationDetailV5(ein),
  })
  const f = data?.foundation

  // Recorded once the name has loaded, so the history never holds a bare EIN.
  // Keyed on ein rather than on the object: re-renders must not re-record.
  useEffect(() => {
    if (!f?.name) return
    recordView({ ein, name: f.name, city: f.city, state: f.state })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ein, f?.name])

  // International is hidden when there is none, so the tab's presence is
  // itself information rather than a dead end.
  const tabs = ALL_TABS.filter(
    (t) => t !== 'International' || (f ? f.foreign_dollars > 0 : false))
  const active: Tab = tabs.includes(tab) ? tab : 'Overview'

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/20" onClick={onClose} />
      <div className="relative w-[56%] min-w-[600px] max-w-[1000px] h-full bg-surface shadow-2xl overflow-y-auto">
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
                {f?.deadline_kind === 'dated' && f.deadline_months && (
                  <span title={f.deadline_text || undefined}
                    className="text-xs px-1.5 py-0.5 rounded bg-accent/15
                      text-primary">
                    Deadline: {f.deadline_months.split(',')
                      .map((m) => MONTH_NAMES[Number(m) - 1]).join(', ')}
                  </span>
                )}
                {f?.deadline_kind === 'rolling' && (
                  <span title={f.deadline_text || undefined}
                    className="text-xs px-1.5 py-0.5 rounded bg-accent/15
                      text-primary">
                    Applications year-round
                  </span>
                )}
                {f && f.foreign_dollars > 0 && (
                  <span title={f.foreign_top_countries || undefined}
                    className="text-xs px-1.5 py-0.5 rounded bg-primary/10
                      text-primary">
                    {money(f.foreign_dollars)} international
                  </span>
                )}
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
            <div className="flex items-center gap-1 shrink-0">
              {/* Saving belongs where the decision is made. Reading the
                  detail is when someone decides a foundation is worth
                  keeping, and sending them back to the table to bookmark it
                  loses the thought. */}
              <SaveMenu ein={ein} align="right" />
              <button onClick={onClose} className="p-1.5 rounded hover:bg-canvas">
                <X size={18} />
              </button>
            </div>
          </div>

          {f && (
            <div className="mt-4">
              <BucketBarLabeled sectors={data?.sectors ?? []} b={{
                christian: f.christian_dollars,
                nonchristian: f.nonchristian_dollars,
                unclassified: f.unclassified_dollars,
                daf: f.daf_dollars,
                nonclassifiable: f.nonclassifiable_dollars,
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

          <div className="flex gap-1 mt-4 flex-wrap">
            {tabs.map((t) => (
              <button key={t} onClick={() => setTab(t)}
                className={`px-3 py-1.5 text-sm rounded-md ${
                  active === t ? 'bg-primary text-white'
                    : 'text-muted hover:bg-canvas'}`}>
                {t}
              </button>
            ))}
          </div>
        </div>

        <div className="p-6 overflow-x-auto">
          {isError && (
            <div className="text-sm text-scoremid">
              Could not load foundation detail — is the v5 API running on
              localhost:8000?
            </div>
          )}
          {!data && !isError && <Skeleton className="h-64" />}
          {data && (
            <>
              {active === 'Overview' && <OverviewTab data={data} />}
              {active === 'Recipients' && (
                <RecipientsTab ein={ein} recipients={data.recipients}
                  total={f?.recipient_count ?? data.recipients.length} />
              )}
              {active === 'Grants' && <GrantsTab ein={ein} />}
              {active === 'International' && <InternationalTab data={data} />}
              {active === 'Geography' && <GeographyTab data={data} />}
              {active === 'Evidence' && <EvidenceTab data={data} />}
              {active === 'Application' && <ApplicationTab data={data} />}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
