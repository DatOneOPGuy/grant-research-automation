import { useEffect, useRef, useState } from 'react'
import { StickyNote } from 'lucide-react'
import { keepPreviousData, useMutation, useQuery, useQueryClient }
  from '@tanstack/react-query'
import { STATIC_MODE, fetchNotesV5, saveNoteV5, type NoteV5 } from '../../lib/apiV5'

/** The team's notes, fetched once and shared by every consumer via the
 *  query cache — one indexed request per page load however many rows,
 *  tabs, or tables render them. */
export function useNotes(): Map<string, NoteV5> {
  const { data } = useQuery({
    queryKey: ['v5notes'],
    queryFn: fetchNotesV5,
    enabled: !STATIC_MODE,
    staleTime: 5 * 60_000,
    placeholderData: keepPreviousData,
  })
  const map = new Map<string, NoteV5>()
  for (const n of data ?? []) map.set(n.ein, n)
  return map
}

/** The one editor every surface shares — table popover, detail tab, saved
 *  list. Blank-and-save deletes; the backend treats an empty note as
 *  removal, so the box does what it looks like it does. */
export function NoteEditor({ ein, note, rows = 4, autoFocus = true, onDone }: {
  ein: string
  note: NoteV5 | undefined
  rows?: number
  autoFocus?: boolean
  onDone?: () => void
}) {
  const [draft, setDraft] = useState(note?.note ?? '')
  const areaRef = useRef<HTMLTextAreaElement>(null)
  const qc = useQueryClient()

  const save = useMutation({
    mutationFn: (text: string) => saveNoteV5(ein, text),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['v5notes'] })
      onDone?.()
    },
  })

  // A teammate's save landing mid-edit must not clobber the draft — only
  // resync when the editor is not dirty.
  useEffect(() => {
    setDraft((d) => (d === '' || d === note?.note ? note?.note ?? '' : d))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [note?.note])

  useEffect(() => {
    if (autoFocus) {
      setTimeout(() => {
        areaRef.current?.focus()
        areaRef.current?.setSelectionRange(9999, 9999)
      }, 0)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div onClick={(e) => e.stopPropagation()}>
      <textarea
        ref={areaRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') onDone?.()
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) save.mutate(draft)
        }}
        rows={rows}
        maxLength={2000}
        placeholder="Notes for your team — e.g. spoke to director, deadline is rolling…"
        className="w-full text-sm border border-line rounded p-2
          placeholder:text-muted/60 focus:outline-none
          focus:border-honey-500 focus:ring-2 focus:ring-honey-400/30
          resize-y" />
      <div className="flex items-center justify-between mt-1.5 gap-2">
        <span className="text-[10px] text-muted min-w-0">
          {save.isError
            ? 'Could not save — is the account service up?'
            : 'Shared with your whole team. Clear + save to delete.'}
        </span>
        <div className="flex gap-1.5 shrink-0">
          {onDone && (
            <button onClick={onDone}
              className="text-xs px-2 py-1 rounded border border-line
                text-muted hover:text-ink">
              Cancel
            </button>
          )}
          <button onClick={() => save.mutate(draft)}
            disabled={save.isPending}
            className="text-xs px-2.5 py-1 rounded bg-primary text-white
              hover:bg-primary/90 disabled:opacity-50">
            {save.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

/** One editable note cell, used by the foundations table AND the saved
 *  table. Lives inside clickable rows, so every interaction stops
 *  propagation — otherwise opening the editor would also open the detail
 *  panel and Emily would lose her place on every edit. */
export default function NoteCell({ ein, note }: {
  ein: string
  note: NoteV5 | undefined
}) {
  const [open, setOpen] = useState(false)
  const boxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  const stop = (e: React.MouseEvent) => e.stopPropagation()

  if (STATIC_MODE) return <td className="px-2 text-muted text-xs">—</td>

  return (
    <td className="px-2 align-middle relative" onClick={stop}>
      <div ref={boxRef}>
        <button
          onClick={(e) => { stop(e); setOpen((o) => !o) }}
          title={note ? `${note.note}\n— ${note.updated_by ?? 'your team'}`
            : 'Add a note'}
          className={`w-full text-left text-xs rounded px-1.5 py-1
            hover:bg-honey-50 ${note ? 'text-ink' : 'text-muted/50'}`}>
          {note ? (
            <span className="line-clamp-2 leading-snug whitespace-normal
              break-words">{note.note}</span>
          ) : (
            <span className="flex items-center gap-1">
              <StickyNote size={12} className="shrink-0" /> note
            </span>
          )}
        </button>
        {open && (
          <div className="absolute z-40 right-0 top-full mt-1 w-72 rounded-lg
            border border-line bg-surface shadow-xl p-2" onClick={stop}>
            <NoteEditor ein={ein} note={note} onDone={() => setOpen(false)} />
          </div>
        )}
      </div>
    </td>
  )
}

/** The Notes tab inside the foundation detail panel: the same single team
 *  note, with room to write, plus its edit trail. */
export function NotesTab({ ein }: { ein: string }) {
  const notes = useNotes()
  const note = notes.get(ein)
  return (
    <div className="max-w-2xl">
      <h3 className="font-display text-lg font-semibold text-primary mb-1">
        Team notes
      </h3>
      <p className="text-sm text-muted mb-3">
        One note per foundation, shared with everyone on your account. It also
        appears in the Notes column of the main table and on the Saved page.
      </p>
      <NoteEditor ein={ein} note={note} rows={8} autoFocus={false} />
      {note && (
        <p className="text-xs text-muted mt-2">
          Last edited by {note.updated_by ?? 'your team'} ·{' '}
          {new Date(note.updated_at).toLocaleString()}
        </p>
      )}
    </div>
  )
}
