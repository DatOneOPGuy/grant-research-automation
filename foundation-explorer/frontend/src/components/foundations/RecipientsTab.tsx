import { Fragment, useEffect, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import {
  BookOpen, ChevronDown, ChevronRight, ExternalLink, Loader2, Search, X,
} from 'lucide-react'
import {
  fetchFoundationRecipients, fetchRecipientV5,
  type FoundationRecipientV5,
} from '../../lib/apiV5'
import { moneyFull, titleCase, propublicaUrl } from '../../lib/format'
import { Skeleton } from '../ui/primitives'
import { DafChip, IdentityChip, TraditionChip } from './V5Chips'

// Evidence table: every recipient this foundation paid, with honest identity
// status and classification provenance. Mission text is fetched lazily.
export default function RecipientsTab({ ein, recipients, total }: {
  ein: string
  recipients: FoundationRecipientV5[]
  /** Every recipient the foundation has, which may exceed what was passed. */
  total: number
}) {
  const [open, setOpen] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [query, setQuery] = useState('')

  // Debounced so a search runs on a pause in typing rather than per keystroke.
  useEffect(() => {
    const t = setTimeout(() => setQuery(draft.trim()), 220)
    return () => clearTimeout(t)
  }, [draft])

  // Searching goes to the server. The prop holds the top 500 by dollars, so
  // filtering it here would quietly miss every recipient below that cut.
  const { data, isFetching } = useQuery({
    queryKey: ['v5foundationRecipients', ein, query],
    queryFn: () => fetchFoundationRecipients(ein, query),
    enabled: query.length > 0,
    placeholderData: keepPreviousData,
  })

  const searching = query.length > 0
  const rows = searching ? (data?.rows ?? []) : recipients
  const truncated = !searching && total > recipients.length

  if (!recipients.length && !searching) {
    return <div className="text-sm text-muted">
      No recipients recorded in the 2023–24 window.
    </div>
  }

  return (
    <div>
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="relative w-72">
          <Search size={14}
            className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted
              pointer-events-none" />
          <input value={draft} onChange={(e) => setDraft(e.target.value)}
            placeholder="Search recipients by name or EIN…"
            aria-label="Search this foundation's recipients"
            className="w-full text-sm border border-line rounded-md bg-surface
              pl-8 pr-7 py-1.5 placeholder:text-muted/70 focus:outline-none
              focus:border-primary/40" />
          {draft && (
            <button onClick={() => setDraft('')} aria-label="Clear search"
              className="absolute right-1.5 top-1/2 -translate-y-1/2 p-0.5
                rounded text-muted hover:text-ink">
              <X size={13} />
            </button>
          )}
        </div>
        <div className="text-xs text-muted flex items-center gap-2">
          {isFetching && <Loader2 size={13} className="animate-spin" />}
          {searching
            ? <>{rows.length} of {total.toLocaleString()} recipients match</>
            : truncated
              ? <>Showing the largest {recipients.length} of{' '}
                  {total.toLocaleString()} — search to reach the rest</>
              : <>{total.toLocaleString()} recipient{total === 1 ? '' : 's'}</>}
        </div>
      </div>

      {searching && rows.length === 0 && !isFetching && (
        <div className="text-sm text-muted py-6 text-center border
          border-line rounded-lg">
          No recipient of this foundation matches “{query}”.
          <div className="text-xs mt-1">
            All {total.toLocaleString()} were searched, not just the visible
            ones.
          </div>
        </div>
      )}

      {rows.length > 0 && (
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
        {rows.map((r) => (
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
      )}
    </div>
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
