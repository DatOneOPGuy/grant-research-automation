// The save control: a bookmark button that opens a folder picker rather than
// silently dropping the foundation into one list. Checking a folder saves into
// it; unchecking the last one unsaves the foundation entirely.
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Bookmark, Check, FolderPlus, Plus } from 'lucide-react'
import { useSavedFoundations } from '../../lib/savedContext'

type Props = {
  ein: string
  /** Rendered inside a scrolling table, so the menu is portalled to the body
   *  and positioned from the trigger's rect -- inside the row it would be
   *  clipped by the table's overflow container. */
  align?: 'left' | 'right'
}

const MENU_WIDTH = 232

export default function SaveMenu({ ein, align = 'right' }: Props) {
  const {
    folders, foldersFor, isSaved, addTo, removeFrom, createFolder, busy,
  } = useSavedFoundations()
  const [open, setOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)

  const saved = isSaved(ein)
  const mine = foldersFor(ein)

  const place = () => {
    const r = triggerRef.current?.getBoundingClientRect()
    if (!r) return
    const left = align === 'right'
      ? Math.max(8, r.right - MENU_WIDTH)
      : Math.min(window.innerWidth - MENU_WIDTH - 8, r.left)
    setPos({ top: r.bottom + 6, left })
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
        <div ref={menuRef} onClick={stop} style={{ ...pos, width: MENU_WIDTH }}
          className="fixed z-50 bg-surface border border-line rounded-lg
            shadow-xl py-1 text-sm">
          <div className="px-3 py-1.5 text-[11px] uppercase tracking-wide
            text-muted">
            Save to folder
          </div>

          {folders.length === 0 && !creating && (
            <div className="px-3 py-2 text-xs text-muted">
              No folders yet — create one to start saving.
            </div>
          )}

          <div className="max-h-56 overflow-y-auto">
            {folders.map((f) => {
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
