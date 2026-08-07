import { Fragment, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BookOpen, ChevronDown, ChevronRight, ExternalLink } from 'lucide-react'
import { fetchRecipientV5, type FoundationRecipientV5 } from '../../lib/apiV5'
import { moneyFull, titleCase, propublicaUrl } from '../../lib/format'
import { Skeleton } from '../ui/primitives'
import { DafChip, IdentityChip, TraditionChip } from './V5Chips'

// Evidence table: every recipient this foundation paid, with honest identity
// status and classification provenance. Mission text is fetched lazily.
export default function RecipientsTab({ recipients }: {
  recipients: FoundationRecipientV5[]
}) {
  const [open, setOpen] = useState<string | null>(null)
  if (!recipients.length) {
    return <div className="text-sm text-muted">
      No recipients recorded in the 2023–24 window.
    </div>
  }
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-xs text-muted border-b border-line">
          <th className="py-2">Recipient</th>
          <th>Tradition</th>
          <th>Identity</th>
          <th className="text-right">$ 2023–24</th>
          <th className="text-right">Grants</th>
          <th />
        </tr>
      </thead>
      <tbody>
        {recipients.map((r) => (
          <Fragment key={r.entity_id}>
            <tr className="border-b border-line/60">
              <td className="py-2 pr-3 font-medium">
                {titleCase(r.name)}
                {Boolean(r.is_daf) && <span className="ml-1.5"><DafChip /></span>}
                {r.recipient_ein && (
                  <a href={propublicaUrl(r.recipient_ein)}
                    target="_blank" rel="noreferrer"
                    title="View this recipient on ProPublica"
                    className="ml-1.5 inline-flex text-muted hover:text-primary align-middle">
                    <ExternalLink size={12} />
                  </a>
                )}
              </td>
              <td className="pr-2">
                <TraditionChip tradition={r.tradition} method={r.method}
                  confidence={r.confidence} reason={r.reason} />
              </td>
              <td className="pr-2"><IdentityChip status={r.identity_status} /></td>
              <td className="text-right tabular pr-3 whitespace-nowrap">
                {moneyFull(r.dollars)}
              </td>
              <td className="text-right tabular text-muted pr-2">{r.grants}</td>
              <td className="text-right">
                {Boolean(r.has_mission) && (
                  <button
                    onClick={() => setOpen(open === r.entity_id ? null : r.entity_id)}
                    title="Show this organization's own mission statement"
                    className="flex items-center gap-1 text-xs text-primary hover:underline ml-auto">
                    <BookOpen size={13} /> Mission
                    {open === r.entity_id
                      ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                  </button>
                )}
              </td>
            </tr>
            {open === r.entity_id && (
              <tr className="border-b border-line/60">
                <td colSpan={6} className="py-2 pl-4">
                  <Mission entityId={r.entity_id} />
                </td>
              </tr>
            )}
          </Fragment>
        ))}
      </tbody>
    </table>
  )
}

function Mission({ entityId }: { entityId: string }) {
  const { data, isError } = useQuery({
    queryKey: ['v5recipient', entityId],
    queryFn: () => fetchRecipientV5(entityId),
  })
  if (isError) {
    return <div className="text-xs text-scoremid">
      Could not load mission text.
    </div>
  }
  if (!data) return <Skeleton className="h-10" />
  // Never dereference blindly: a recipient outside the sample, or one with no
  // 990 on file, must degrade to a message rather than crash the whole route.
  if (!data.recipient?.mission_text) {
    return <div className="text-xs text-muted">
      No mission text on file for this recipient.
    </div>
  }
  return (
    <blockquote className="border-l-2 border-accent pl-3 text-sm italic text-ink max-w-2xl">
      “{data.recipient.mission_text}”
      <div className="text-xs text-muted not-italic mt-1">
        From the organization’s own Form 990
      </div>
    </blockquote>
  )
}
