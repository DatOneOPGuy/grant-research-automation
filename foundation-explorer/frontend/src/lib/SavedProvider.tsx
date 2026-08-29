import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { AlertTriangle, Undo2, X } from 'lucide-react'
import { SavedContext } from './savedContext'
import { ApiSavedStore, SavedApiError } from './apiSavedStore'
import { STATIC_MODE } from './apiV5'
import { LocalSavedStore, type SavedFolder, type SavedState } from './savedStore'

// The static demo build has no API, so it keeps the browser-local store.
// The live app never reads localStorage: folders belong to the team and live
// in Postgres, and anything left in fe.saved.v2 from before accounts is
// deliberately ignored rather than migrated into shared team state.
const store = STATIC_MODE ? new LocalSavedStore() : new ApiSavedStore()

const EMPTY: SavedState = { folders: [], members: {} }

function message(err: unknown): string {
  if (err instanceof SavedApiError) return err.message
  if (err instanceof Error && err.message) return err.message
  return 'Something went wrong.'
}

export function SavedProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SavedState>(EMPTY)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [writeError, setWriteError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  // What was just removed, and from where, so it can be put back. Captured
  // before the removal rather than reconstructed after, because by the time
  // the write lands the membership it needs is already gone.
  const [undo, setUndo] = useState<
    { ein: string; label: string | null; folderIds: string[] } | null>(null)
  const alive = useRef(true)

  // The setup half is not optional. StrictMode runs effects setup -> cleanup
  // -> setup on mount in development, so an effect that only ever sets this
  // to false leaves it false for the life of the app: reload() then returns
  // before its setState and the list never updates, while mutate()'s finally
  // skips setBusy(false) and every control stays disabled after the first
  // action. Folders were being created server-side and simply never appearing.
  useEffect(() => {
    alive.current = true
    return () => { alive.current = false }
  }, [])

  const reload = useCallback(async () => {
    try {
      const next = await store.load()
      if (!alive.current) return
      setState(next)
      setLoadError(null)
    } catch (err) {
      if (!alive.current) return
      setLoadError(message(err))
    } finally {
      if (alive.current) setLoading(false)
    }
  }, [])

  useEffect(() => { void reload() }, [reload])

  /* Every mutation refetches rather than patching local state. Folders are
   * shared, so the authoritative answer after a write includes whatever a
   * teammate did in the meantime -- patching would show this client a version
   * of the list that never existed on the server.
   *
   * Failures surface in writeError and are never rethrown. A save that
   * silently does not persist is the worst outcome available here, so the
   * banner is not optional, but neither is it the call site's job to remember. */
  const mutate = useCallback(async <T,>(
    action: () => Promise<T>,
  ): Promise<T | null> => {
    setBusy(true)
    setWriteError(null)
    try {
      // If the very first load failed -- the API was up but its database was
      // not, which is the usual local mishap -- the provider would otherwise
      // stay wedged for the life of the tab, because the load only runs on
      // mount. Retry it here so the next action recovers instead of the user
      // having to know to reload.
      if (loadError) await reload()
      const result = await action()
      await reload()
      return result
    } catch (err) {
      if (alive.current) setWriteError(message(err))
      // Re-read anyway: the write may have landed before the response failed,
      // and showing the server's actual state beats showing our guess.
      await reload()
      return null
    } finally {
      if (alive.current) setBusy(false)
    }
  }, [reload, loadError])

  const { folders, members } = state
  const saved = useMemo(() => Object.keys(members), [members])

  const value = useMemo(() => ({
    folders,
    saved,
    isSaved: (ein: string) => (members[ein]?.length ?? 0) > 0,
    foldersFor: (ein: string) => members[ein] ?? [],
    einsIn: (folderId: string) => Object.entries(members)
      .filter(([, ids]) => ids.includes(folderId))
      .map(([ein]) => ein),

    loading,
    loadError,
    writeError,
    dismissWriteError: () => setWriteError(null),
    busy,
    reload,

    addTo: async (ein: string, folderId: string) => {
      setUndo(null)
      await mutate(() => store.addTo(ein, folderId))
    },
    removeFrom: async (ein: string, folderId: string, label?: string) => {
      const restore = [folderId]
      const ok = await mutate(() => store.removeFrom(ein, folderId))
      if (ok !== null) {
        setUndo({ ein, label: label || null, folderIds: restore })
      }
    },
    removeAll: async (ein: string, label?: string) => {
      // Every folder it belonged to, read before the write.
      const restore = members[ein] ? [...members[ein]] : []
      const ok = await mutate(() => store.removeAll(ein))
      if (ok !== null) {
        setUndo({ ein, label: label || null, folderIds: restore })
      }
    },
    createFolder: (name: string): Promise<SavedFolder | null> =>
      mutate(() => store.createFolder(name)),
    renameFolder: async (id: string, name: string) => {
      await mutate(() => store.renameFolder(id, name))
    },
    deleteFolder: async (id: string) => {
      await mutate(() => store.deleteFolder(id))
    },
  }), [folders, members, saved, loading, loadError, writeError, busy,
       mutate, reload])

  const runUndo = useCallback(async () => {
    if (!undo) return
    const { ein, folderIds } = undo
    setUndo(null)
    // Restoring a multi-folder foundation is several writes; the refetch
    // inside mutate() makes each one visible, so a partial failure leaves
    // the list showing exactly what was actually put back.
    for (const folderId of folderIds) {
      await mutate(() => store.addTo(ein, folderId))
    }
  }, [undo, mutate])

  return (
    <SavedContext.Provider value={value}>
      {children}
      {writeError && (
        <WriteErrorBanner message={writeError}
          onDismiss={() => setWriteError(null)} />
      )}
      {undo && !writeError && (
        <UndoToast label={undo.label}
          folderCount={undo.folderIds.length}
          onUndo={() => void runUndo()}
          onDismiss={() => setUndo(null)} />
      )}
    </SavedContext.Provider>
  )
}

/** Global because a save can be triggered from any page, including from a
 *  bookmark button inside a scrolling table with nowhere to put a message. */
function WriteErrorBanner({ message, onDismiss }: {
  message: string
  onDismiss: () => void
}) {
  const reload = message.includes('Reload the page')
  return (
    <div role="alert"
      className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[60] max-w-md
        flex items-start gap-2.5 rounded-lg border border-scoremid/40
        bg-amber-50 px-4 py-3 text-sm text-scoremid shadow-lg">
      <AlertTriangle size={16} className="shrink-0 mt-0.5" />
      <div className="flex-1">
        <div className="font-medium">That change was not saved.</div>
        <div className="text-xs mt-0.5">{message}</div>
        {reload && (
          <button onClick={() => window.location.reload()}
            className="mt-1.5 text-xs underline underline-offset-2">
            Reload now
          </button>
        )}
      </div>
      <button onClick={onDismiss} aria-label="Dismiss"
        className="p-0.5 rounded hover:bg-amber-100 shrink-0">
        <X size={14} />
      </button>
    </div>
  )
}

/** Undo for a removal.
 *
 *  Saved folders are shared, so a removal is not just this person's mistake
 *  to live with -- it takes the row out of a list a colleague may be working
 *  from. A confirm dialog on every removal would be worse: it slows down the
 *  common case to guard the rare one. This does the reverse, and restores the
 *  full membership rather than just the folder that was on screen.
 *
 *  It expires. Undo that lingers becomes a stale button that reinstates
 *  something the user removed twenty minutes and several decisions ago.
 */
function UndoToast({ label, folderCount, onUndo, onDismiss }: {
  label: string | null
  folderCount: number
  onUndo: () => void
  onDismiss: () => void
}) {
  const SECONDS = 12
  const [left, setLeft] = useState(SECONDS)

  useEffect(() => {
    const tick = setInterval(() => setLeft((n) => n - 1), 1000)
    const done = setTimeout(onDismiss, SECONDS * 1000)
    return () => { clearInterval(tick); clearTimeout(done) }
    // Deliberately not re-armed on every render: the countdown belongs to
    // this toast, and restarting it would make it never expire.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div role="status"
      className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[60] max-w-md
        flex items-center gap-3 rounded-lg border border-line bg-ink
        px-4 py-2.5 text-sm text-white shadow-lg">
      <span className="block min-w-0 truncate">
        {label
          ? <>Removed <span className="font-medium">{label}</span></>
          : <>Removed from {folderCount === 1 ? 'that folder' : 'Saved'}</>}
        {label && folderCount > 1 && (
          <span className="text-white/70"> from {folderCount} folders</span>
        )}
      </span>
      <button onClick={onUndo}
        className="flex items-center gap-1 rounded px-2 py-1 font-medium
          text-accent hover:bg-white/10 shrink-0">
        <Undo2 size={14} /> Undo
      </button>
      <span className="text-white/40 tabular text-xs w-4 text-right shrink-0">
        {Math.max(0, left)}
      </span>
      <button onClick={onDismiss} aria-label="Dismiss"
        className="p-0.5 rounded text-white/60 hover:text-white shrink-0">
        <X size={14} />
      </button>
    </div>
  )
}
