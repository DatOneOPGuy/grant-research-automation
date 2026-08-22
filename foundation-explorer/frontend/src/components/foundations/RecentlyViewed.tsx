// Recently viewed foundations, most recent first.
//
// Prospect research is not linear: you open a funder, follow a grantee, open
// two more, and then want the one from four clicks ago. Without a trail the
// only way back is to remember the name and search again.
import { useSyncExternalStore } from 'react'
import { Clock, X } from 'lucide-react'
import {
  clearRecent, getRecent, getRecentServerSnapshot, removeRecent,
  subscribeRecent,
} from '../../lib/recentStore'
import { titleCase } from '../../lib/format'

function ago(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = seconds / 60
  if (minutes < 60) return `${Math.floor(minutes)}m ago`
  const hours = minutes / 60
  if (hours < 24) return `${Math.floor(hours)}h ago`
  const days = Math.floor(hours / 24)
  return days === 1 ? 'yesterday' : `${days}d ago`
}

export default function RecentlyViewed({ onOpen, limit = 8 }: {
  onOpen: (ein: string) => void
  limit?: number
}) {
  // useSyncExternalStore keeps every mounted copy of this list in step with
  // the store, including across tabs, without a provider or a polling loop.
  const entries = useSyncExternalStore(
    subscribeRecent, getRecent, getRecentServerSnapshot)
  if (!entries.length) return null

  const shown = entries.slice(0, limit)

  return (
    <section className="border border-line rounded-lg bg-surface p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5 text-[11px] uppercase
          tracking-wide text-muted">
          <Clock size={12} /> Recently viewed
        </div>
        <button onClick={clearRecent}
          className="text-[11px] text-muted hover:text-ink underline
            underline-offset-2">
          Clear
        </button>
      </div>
      <ul className="flex flex-wrap gap-1.5">
        {shown.map((e) => (
          <li key={e.ein}>
            <span className="group inline-flex items-center gap-1 rounded-md
              border border-line bg-canvas pl-2 pr-1 py-1 text-xs
              hover:border-primary/40">
              <button onClick={() => onOpen(e.ein)}
                title={`${titleCase(e.name)} — viewed ${ago(e.viewedAt)}`}
                className="max-w-[16rem] truncate text-ink hover:text-primary">
                {titleCase(e.name)}
              </button>
              <span className="text-muted tabular text-[10px] shrink-0">
                {ago(e.viewedAt)}
              </span>
              <button onClick={() => removeRecent(e.ein)}
                aria-label={`Remove ${e.name} from recently viewed`}
                className="p-0.5 rounded text-muted opacity-0
                  group-hover:opacity-100 focus:opacity-100 hover:text-scoremid">
                <X size={11} />
              </button>
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
