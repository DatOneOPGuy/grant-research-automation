// The save control: a bookmark button that opens a folder picker rather than
// silently dropping the foundation into one list. Checking a folder saves into
// it; unchecking the last one unsaves the foundation entirely.
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Bookmark, Check, FolderPlus, Plus, Search } from 'lucide-react'
import { useSavedFoundations } from '../../lib/savedContext'

type Props = {
  ein: string
  /** Rendered inside a scrolling table, so the menu is portalled to the body
   *  and positioned from the trigger's rect -- inside the row it would be
   *  clipped by the table's overflow container. */
  align?: 'left' | 'right'
}

const MENU_WIDTH = 248
// Roughly how tall the menu wants to be with a full list. Used only to decide
// whether it fits below the trigger; the real height is set by max-h below.
const MENU_MAX_HEIGHT = 420
// Above this many folders, scrolling to find one is slower than typing it.
const FILTER_THRESHOLD = 8

export default function SaveMenu({ ein, align = 'right' }: Props) {
  const {
    folders, foldersFor, isSaved, addTo, removeFrom, createFolder, busy,
  } = useSavedFoundations()
  const [open, setOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [query, setQuery] = useState('')
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState<
    { top: number; left: number; flipped: boolean } | null>(null)

  const saved = isSaved(ein)
  const mine = foldersFor(ein)

  // Folders this foundation is already in sort to the top, so what is
  // currently checked is never hidden below the fold -- otherwise the one
  // piece of state the menu exists to show is the easiest thing to miss.
  const q = query.trim().toLowerCase()
  const visible = folders
    .filter((f) => !q || f.name.toLowerCase().includes(q))
    .slice()
    .sort((a, b) => {
      const inA = mine.includes(a.id) ? 0 : 1
      const inB = mine.includes(b.id) ? 0 : 1
      return inA - inB || a.name.localeCompare(b.name)
    })

  const place = () => {
    const r = triggerRef.current?.getBoundingClientRect()
    if (!r) return
    const left = align === 'right'
      ? Math.max(8, r.right - MENU_WIDTH)
      : Math.min(window.innerWidth - MENU_WIDTH - 8, r.left)
    // Open upward when there is not room below. The menu is taller now, and
    // a bookmark on one of the last rows of a long table would otherwise put
    // its folder list off the bottom of the window.
    const below = window.innerHeight - r.bottom
    const flipped = below < MENU_MAX_HEIGHT && r.top > below
    setPos({
      top: flipped ? Math.max(8, r.top - 6) : r.bottom + 6,
      left,
      flipped,
    })
  }

  useEffect(() => {
    if (!open) { setQuery(''); setCreating(false); return }
    place()
    const close = (e: MouseEvent) => {
      if (menuRef.current?.contains(e.target as Node)) return
      if (triggerRef.current?.contains(e.target as Node)) return
      setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    // Reposition rather than follow: the trigger lives in a scrolling table,
    // and a menu that stays put while its row moves is worse than one that
    // closes.
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const stop = (e: React.MouseEvent) => e.stopPropagation()

  // Two round trips, and the second depends on the first: the folder has to
  // exist server-side before anything can be filed into it. The input stays
  // put until both land, so a failed create does not silently discard what
  // the user typed.
  const submitNew = async () => {
    const clean = name.trim()
    if (!clean) return
    const folder = await createFolder(clean)
    if (!folder) return // the provider is already showing why
    await addTo(ein, folder.id)
    setName('')
    setCreating(false)
  }

  return (
    <>
      <button
        ref={triggerRef}
        onClick={(e) => { stop(e); setOpen((o) => !o) }}
        title={saved
          ? `Saved in ${mine.length} folder${mine.length === 1 ? '' : 's'}`
          : 'Save to a folder'}
        aria-label={saved ? 'Edit saved folders' : 'Save this foundation'}
        aria-expanded={open}
        className={`p-1 rounded hover:bg-canvas ${
          saved ? 'text-primary' : 'text-muted hover:text-ink'}`}>
        <Bookmark size={15} fill={saved ? 'currentColor' : 'none'} />
      </button>

      {open && pos && createPortal(
        <div ref={menuRef} onClick={stop}
          style={{
            left: pos.left, width: MENU_WIDTH,
            ...(pos.flipped
              ? { bottom: window.innerHeight - pos.top }
              : { top: pos.top }),
          }}
          className="fixed z-50 bg-surface border border-line rounded-lg
            shadow-xl py-1 text-sm">
          <div className="px-3 py-1.5 flex items-center justify-between
            text-[11px] uppercase tracking-wide text-muted">
            <span>Save to folder</span>
            {folders.length > 0 && (
              <span className="tabular normal-case">
                {mine.length}/{folders.length}
              </span>
            )}
          </div>

          {folders.length > FILTER_THRESHOLD && (
            <div className="px-2 pb-1">
              <div className="relative">
                <Search size={12}
                  className="absolute left-2 top-1/2 -translate-y-1/2
                    text-muted pointer-events-none" />
                <input autoFocus value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Escape') {
                      if (query) { setQuery(''); e.stopPropagation() }
                    }
                  }}
                  placeholder={`Filter ${folders.length} folders…`}
                  aria-label="Filter folders"
                  className="w-full border border-line rounded pl-6 pr-2 py-1
                    text-xs placeholder:text-muted/70 focus:outline-none
                    focus:border-primary/40" />
              </div>
            </div>
          )}

          {folders.length === 0 && !creating && (
            <div className="px-3 py-2 text-xs text-muted">
              No folders yet — create one to start saving.
            </div>
          )}

          {/* scrollbar-gutter keeps the track visible on macOS, where an
              overlay scrollbar fades out and makes a scrollable list look
              like a list that simply ends. */}
          <div className="max-h-72 overflow-y-auto"
            style={{ scrollbarGutter: 'stable', scrollbarWidth: 'thin' }}>
            {visible.length === 0 && q && (
              <div className="px-3 py-2 text-xs text-muted">
                No folder matches “{query}”.
              </div>
            )}
            {visible.map((f) => {
              const on = mine.includes(f.id)
              return (
                <button key={f.id}
                  onClick={() => void (on
                    ? removeFrom(ein, f.id) : addTo(ein, f.id))}
                  disabled={busy}
                  className="w-full flex items-center gap-2 px-3 py-1.5
                    hover:bg-canvas text-left disabled:opacity-50">
                  <span className={`w-4 h-4 rounded border flex items-center
                    justify-center shrink-0 ${on
                      ? 'bg-primary border-primary text-white'
                      : 'border-line'}`}>
                    {on && <Check size={11} strokeWidth={3} />}
                  </span>
                  <span className="truncate flex-1">{f.name}</span>
                </button>
              )
            })}
          </div>

          <div className="border-t border-line/60 mt-1 pt-1">
            {creating ? (
              <div className="px-2 py-1 flex items-center gap-1">
                <input autoFocus value={name}
                  onChange={(e) => setName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') void submitNew()
                    if (e.key === 'Escape') { setCreating(false); setName('') }
                  }}
                  placeholder="Folder name"
                  className="flex-1 min-w-0 border border-line rounded px-2
                    py-1 text-sm" />
                <button onClick={() => void submitNew()}
                  disabled={!name.trim() || busy}
                  aria-label="Create folder"
                  className="p-1.5 rounded text-primary hover:bg-canvas
                    disabled:opacity-40">
                  <Plus size={15} />
                </button>
              </div>
            ) : (
              <button onClick={() => setCreating(true)}
                className="w-full flex items-center gap-2 px-3 py-1.5
                  hover:bg-canvas text-primary text-left">
                <FolderPlus size={14} /> New folder
              </button>
            )}
          </div>
        </div>,
        document.body,
      )}
    </>
  )
}
