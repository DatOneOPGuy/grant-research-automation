// How to actually approach this foundation. Every field here comes from the
// 990-PF; where the filing is silent we say so rather than leaving a blank the
// user might read as "no requirement".
import { ExternalLink } from 'lucide-react'
import { MONTH_NAMES, type FoundationDetailV5 } from '../../../lib/apiV5'
import { propublicaUrl, titleCase, websiteUrl } from '../../../lib/format'
import { StatusPill } from '../../ui/primitives'
import { Empty, SectionTitle } from './parts'

function Row({ label, children }: {
  label: string; children: React.ReactNode
}) {
  return (
    <div className="flex gap-3 py-1.5 border-b border-line/60 text-sm">
      <span className="w-36 shrink-0 text-muted text-xs pt-0.5">{label}</span>
      <span className="flex-1">{children}</span>
    </div>
  )
}

const NOT_STATED = <span className="text-muted">Not stated in the filing</span>

export default function ApplicationTab({ data }: {
  data: FoundationDetailV5
}) {
  const f = data.foundation
  const site = websiteUrl(f.website)
  const months = f.deadline_months
    ? f.deadline_months.split(',')
      .map((m) => MONTH_NAMES[Number(m) - 1]).filter(Boolean)
    : []

  const deadline = () => {
    if (f.deadline_kind === 'dated' && months.length) {
      return <>
        <span className="font-medium">{months.join(', ')}</span>
        <div className="text-[11px] text-muted mt-0.5">
          Parsed from the filing’s own wording, quoted below.
        </div>
      </>
    }
    if (f.deadline_kind === 'rolling') {
      return <span className="font-medium">Accepts applications year-round</span>
    }
    if (f.deadline_kind === 'none') {
      return <>States it has no submission deadline</>
    }
    if (f.deadline_kind === 'unparseable') {
      return <>
        The filing states a deadline we could not reduce to specific months —
        read the wording below.
      </>
    }
    return <>
      {NOT_STATED}
      <div className="text-[11px] text-muted mt-0.5">
        78% of foundations leave this field empty; it does not mean there is no
        deadline.
      </div>
    </>
  }

  return (
    <div className="space-y-6">
      <div>
        <SectionTitle note="Whether this foundation invites unsolicited
          requests, inferred from which application fields its filing
          completed.">
          How to approach
        </SectionTitle>
        <div>
          <Row label="Status"><StatusPill status={f.application_status} /></Row>
          <Row label="Deadline">{deadline()}</Row>
          {f.deadline_text && (
            <Row label="In its own words">
              <span className="italic text-ink">“{f.deadline_text}”</span>
            </Row>
          )}
        </div>
      </div>

      <div>
        <SectionTitle>Contact</SectionTitle>
        <div>
          <Row label="Person">
            {f.contact_person ? titleCase(f.contact_person) : NOT_STATED}
          </Row>
          <Row label="Phone">
            {f.phone
              ? <a href={`tel:${f.phone}`} className="text-primary underline">
                {f.phone}
              </a>
              : NOT_STATED}
          </Row>
          <Row label="Email">
            {f.contact_email
              ? <a href={`mailto:${f.contact_email}`}
                className="text-primary underline">{f.contact_email}</a>
              : NOT_STATED}
          </Row>
          <Row label="Address">
            {f.city ? <>{titleCase(f.city)}, {f.state}</> : NOT_STATED}
          </Row>
          <Row label="Website">
            {site
              ? <a href={site} target="_blank" rel="noreferrer"
                className="text-primary underline inline-flex items-center gap-1">
                {f.website} <ExternalLink size={12} />
              </a>
              : NOT_STATED}
          </Row>
          <Row label="Full filing">
            <a href={propublicaUrl(f.ein)} target="_blank" rel="noreferrer"
              className="text-primary underline inline-flex items-center gap-1">
              ProPublica Nonprofit Explorer <ExternalLink size={12} />
            </a>
          </Row>
        </div>
      </div>

      <div>
        <SectionTitle>Filing</SectionTitle>
        <div>
          <Row label="Most recent return">
            {f.latest_tax_year
              ? <>Tax year {f.latest_tax_year}</> : <Empty>Unknown</Empty>}
          </Row>
          <Row label="Years with giving">
            {[f.active_2023 && '2023', f.active_2024 && '2024']
              .filter(Boolean).join(', ') || 'None in 2023–24'}
          </Row>
          {f.is_testamentary && (
            <Row label="Note">
              Name suggests a testamentary trust — these often make fixed
              distributions set by a will and may not consider new requests.
            </Row>
          )}
        </div>
      </div>
    </div>
  )
}
