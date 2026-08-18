import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { AlertTriangle, X } from 'lucide-react'
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
  const alive = useRef(true)

  useEffect(() => () => { alive.current = false }, [])

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
  }, [reload])

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
      await mutate(() => store.addTo(ein, folderId))
    },
    removeFrom: async (ein: string, folderId: string) => {
      await mutate(() => store.removeFrom(ein, folderId))
    },
    removeAll: async (ein: string) => {
      await mutate(() => store.removeAll(ein))
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

  return (
    <SavedContext.Provider value={value}>
      {children}
      {writeError && (
        <WriteErrorBanner message={writeError}
          onDismiss={() => setWriteError(null)} />
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
