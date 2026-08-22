// Recently viewed foundations, as a dropdown beside the filters button.
//
// Prospect research is not linear: you open a funder, follow a grantee, open
// two more, and then want the one from four clicks ago. Without a trail the
// only way back is to remember the name and search for it again.
//
// A menu rather than a permanent strip. The list matters at the moment you
// want to backtrack and is noise the rest of the time, and the toolbar is
// where the other view controls already live.
import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { createPortal } from 'react-dom'
import { Clock, X } from 'lucide-react'
import {
  clearRecent, getRecent, getRecentServerSnapshot, removeRecent,
  subscribeRecent,
} from '../../lib/recentStore'
import { titleCase } from '../../lib/format'

const MENU_WIDTH = 340

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

export default function RecentlyViewed({ onOpen }: {
  onOpen: (ein: string) => void
}) {
  // useSyncExternalStore keeps every mounted copy in step with the store,
  // including across tabs, without a provider or a polling loop.
  const entries = useSyncExternalStore(
    subscribeRecent, getRecent, getRecentServerSnapshot)
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  const place = () => {
    const r = triggerRef.current?.getBoundingClientRect()
    if (!r) return
    // Right-aligned to the trigger, clamped into the viewport.
    setPos({
      top: r.bottom + 6,
      left: Math.max(8, Math.min(r.right - MENU_WIDTH,
        window.innerWidth - MENU_WIDTH - 8)),
    })
  }

  useEffect(() => {
    if (!open) return
    place()
    const close = (e: MouseEvent) => {
      if (menuRef.current?.contains(e.target as Node)) return
      if (triggerRef.current?.contains(e.target as Node)) return
      setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    // Reposition rather than follow: a menu anchored to a control that has
    // scrolled away is worse than one that closes.
    const onScrollOrResize = () => setOpen(false)
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', onKey)
    window.addEventListener('resize', onScrollOrResize)
    window.addEventListener('scroll', onScrollOrResize, true)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', onKey)
      window.removeEventListener('resize', onScrollOrResize)
      window.removeEventListener('scroll', onScrollOrResize, true)
    }
  }, [open])

  const disabled = entries.length === 0

  return (
    <>
      <button
        ref={triggerRef}
        onClick={() => setOpen((o) => !o)}
        disabled={disabled}
        aria-expanded={open}
        aria-haspopup="menu"
        title={disabled
          ? 'No foundations viewed yet'
          : `${entries.length} recently viewed`}
        className={`flex items-center gap-2 text-sm rounded-md border px-3
          py-1.5 transition-colors ${open
            ? 'border-primary/30 bg-primary/5 text-primary'
            : 'border-line text-muted hover:text-ink hover:bg-canvas'}
          disabled:opacity-40 disabled:hover:bg-transparent
          disabled:hover:text-muted`}>
        <Clock size={15} />
        Recent
        {entries.length > 0 && (
          <span className="text-xs bg-primary/10 text-primary rounded-full
            px-1.5 py-0.5 font-medium tabular">
            {entries.length}
          </span>
        )}
      </button>

      {open && pos && createPortal(
        <div ref={menuRef} style={{ ...pos, width: MENU_WIDTH }}
          role="menu"
          className="fixed z-50 rounded-lg border border-line bg-surface
            shadow-xl text-sm overflow-hidden">
          <div className="flex items-center justify-between px-3 py-2
            border-b border-line">
            <span className="text-[11px] uppercase tracking-wide text-muted">
              Recently viewed
            </span>
            <button onClick={() => { clearRecent(); setOpen(false) }}
              className="text-[11px] text-muted hover:text-ink underline
                underline-offset-2">
              Clear all
            </button>
          </div>

          <ul className="max-h-[24rem] overflow-y-auto">
            {entries.map((e) => (
              <li key={e.ein} className="group flex items-center
                border-b border-line/50 last:border-0 hover:bg-canvas">
                <button
                  onClick={() => { onOpen(e.ein); setOpen(false) }}
                  className="flex-1 min-w-0 text-left px-3 py-2">
                  <div className="truncate text-ink">{titleCase(e.name)}</div>
                  <div className="text-xs text-muted truncate">
                    {e.city && `${titleCase(e.city)}, `}{e.state}
                    {(e.city || e.state) && ' · '}{ago(e.viewedAt)}
                  </div>
                </button>
                <button onClick={() => removeRecent(e.ein)}
                  aria-label={`Remove ${e.name} from recently viewed`}
                  className="p-1.5 mr-1 rounded text-muted opacity-0
                    group-hover:opacity-100 focus:opacity-100
                    hover:text-scoremid shrink-0">
                  <X size={13} />
                </button>
              </li>
            ))}
          </ul>
        </div>,
        document.body,
      )}
    </>
  )
}
