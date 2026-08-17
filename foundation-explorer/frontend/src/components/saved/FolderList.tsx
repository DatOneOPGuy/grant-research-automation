// Folder rail for the Saved page: switch view, create, rename, delete.
// Every folder is deletable, Favorites included -- it is seeded as a
// convenience, not as a fixture the user is stuck with.
import { useState } from 'react'
import { Check, FolderPlus, Layers, Pencil, Trash2, X } from 'lucide-react'
import { useSavedFoundations } from '../../lib/savedContext'
import { ALL } from './views'

export default function FolderList({ activeView, onSelect }: {
  activeView: string
  onSelect: (view: string) => void
}) {
  const {
    folders, saved, einsIn, createFolder, renameFolder, deleteFolder,
  } = useSavedFoundations()
  const [creating, setCreating] = useState(false)
  const [draft, setDraft] = useState('')
  const [editing, setEditing] = useState<string | null>(null)
  const [editName, setEditName] = useState('')

  const submitNew = () => {
    const clean = draft.trim()
    if (!clean) return
    onSelect(createFolder(clean).id)
    setDraft('')
    setCreating(false)
  }

  const confirmDelete = (id: string, name: string) => {
    // Deleting a folder can unsave foundations that live nowhere else, so the
    // prompt says how many rather than just asking "are you sure".
    const orphans = einsIn(id).filter((ein) => {
      const others = folders.filter((f) => f.id !== id)
      return !others.some((f) => einsIn(f.id).includes(ein))
    }).length
    const detail = orphans > 0
      ? `\n\n${orphans} foundation${orphans === 1 ? '' : 's'} `
        + `${orphans === 1 ? 'is' : 'are'} in no other folder and will be `
        + 'removed from Saved entirely.'
      : '\n\nEvery foundation in it is also in another folder, so nothing '
        + 'will be lost from Saved.'
    if (confirm(`Delete the folder "${name}"?${detail}`)) {
      deleteFolder(id)
      if (activeView === id) onSelect(ALL)
    }
  }

  const rowClass = (on: boolean) => `w-full flex items-center gap-2 rounded-md
    px-2.5 py-1.5 text-sm text-left ${on
      ? 'bg-primary/10 text-primary font-medium'
      : 'text-muted hover:bg-canvas hover:text-ink'}`

  return (
    <div className="w-56 shrink-0">
      <button onClick={() => onSelect(ALL)} className={rowClass(activeView === ALL)}>
        <Layers size={14} className="shrink-0" />
        <span className="flex-1 truncate">All saved</span>
        <span className="text-xs tabular">{saved.length}</span>
      </button>

      <div className="mt-2 space-y-0.5">
        {folders.map((f) => {
          const count = einsIn(f.id).length
          if (editing === f.id) {
            return (
              <div key={f.id} className="flex items-center gap-1 px-1 py-1">
                <input autoFocus value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      renameFolder(f.id, editName); setEditing(null)
                    }
                    if (e.key === 'Escape') setEditing(null)
                  }}
                  className="flex-1 min-w-0 border border-line rounded px-2
                    py-1 text-sm" />
                <button onClick={() => { renameFolder(f.id, editName); setEditing(null) }}
                  aria-label="Save name"
                  className="p-1 text-primary hover:bg-canvas rounded">
                  <Check size={14} />
                </button>
                <button onClick={() => setEditing(null)} aria-label="Cancel"
                  className="p-1 text-muted hover:bg-canvas rounded">
                  <X size={14} />
                </button>
              </div>
            )
          }
          return (
            <div key={f.id} className="group flex items-center">
              <button onClick={() => onSelect(f.id)}
                className={rowClass(activeView === f.id)}>
                <span className="flex-1 truncate">{f.name}</span>
                <span className="text-xs tabular">{count}</span>
              </button>
              <div className="flex opacity-0 group-hover:opacity-100
                focus-within:opacity-100 transition-opacity">
                <button
                  onClick={() => { setEditing(f.id); setEditName(f.name) }}
                  title="Rename folder" aria-label={`Rename ${f.name}`}
                  className="p-1 text-muted hover:text-ink rounded">
                  <Pencil size={13} />
                </button>
                <button onClick={() => confirmDelete(f.id, f.name)}
                  title="Delete folder" aria-label={`Delete ${f.name}`}
                  className="p-1 text-muted hover:text-scoremid rounded">
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          )
        })}
      </div>

      <div className="mt-2 pt-2 border-t border-line/60">
        {creating ? (
          <div className="flex items-center gap-1">
            <input autoFocus value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') submitNew()
                if (e.key === 'Escape') { setCreating(false); setDraft('') }
              }}
              placeholder="Folder name"
              className="flex-1 min-w-0 border border-line rounded px-2 py-1
                text-sm" />
            <button onClick={submitNew} disabled={!draft.trim()}
              aria-label="Create folder"
              className="p-1.5 text-primary hover:bg-canvas rounded
                disabled:opacity-40">
              <Check size={14} />
            </button>
          </div>
        ) : (
          <button onClick={() => setCreating(true)}
            className="w-full flex items-center gap-2 px-2.5 py-1.5 text-sm
              text-primary hover:bg-canvas rounded-md">
            <FolderPlus size={14} /> New folder
          </button>
        )}
      </div>
    </div>
  )
}
