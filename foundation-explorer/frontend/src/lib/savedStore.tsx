/* Saved-foundations persistence.
 *
 * SavedFoundationsStore is the seam: the interface stays identical when we
 * move from localStorage to a REST-backed store. Swap LocalSavedStore for an
 * ApiSavedStore (hitting /api/users/{userId}/saved) when user accounts land;
 * components never touch localStorage — they go through useSavedFoundations().
 */
import {
  createContext, useCallback, useContext, useState, type ReactNode,
} from 'react'

export interface SavedFoundationsStore {
  getSaved(): string[]
  save(ein: string): void
  remove(ein: string): void
  isSaved(ein: string): boolean
}

const KEY = 'fe.saved.eins'

class LocalSavedStore implements SavedFoundationsStore {
  private set: Set<string>
  constructor() {
    let arr: string[] = []
    try { arr = JSON.parse(localStorage.getItem(KEY) || '[]') } catch { /* */ }
    this.set = new Set(arr)
  }
  private persist() {
    localStorage.setItem(KEY, JSON.stringify([...this.set]))
  }
  getSaved() { return [...this.set] }
  save(ein: string) { this.set.add(ein); this.persist() }
  remove(ein: string) { this.set.delete(ein); this.persist() }
  isSaved(ein: string) { return this.set.has(ein) }
}

// Single app-wide store instance. Replace with ApiSavedStore later.
const store: SavedFoundationsStore = new LocalSavedStore()

type Ctx = {
  saved: string[]
  isSaved: (ein: string) => boolean
  toggle: (ein: string) => void
  remove: (ein: string) => void
}
const SavedContext = createContext<Ctx | null>(null)

export function SavedProvider({ children }: { children: ReactNode }) {
  const [saved, setSaved] = useState<string[]>(() => store.getSaved())
  const toggle = useCallback((ein: string) => {
    if (store.isSaved(ein)) store.remove(ein)
    else store.save(ein)
    setSaved(store.getSaved())
  }, [])
  const remove = useCallback((ein: string) => {
    store.remove(ein); setSaved(store.getSaved())
  }, [])
  const isSaved = useCallback((ein: string) => saved.includes(ein), [saved])
  return (
    <SavedContext.Provider value={{ saved, isSaved, toggle, remove }}>
      {children}
    </SavedContext.Provider>
  )
}

export function useSavedFoundations(): Ctx {
  const ctx = useContext(SavedContext)
  if (!ctx) throw new Error('useSavedFoundations outside SavedProvider')
  return ctx
}

/* Filter-state persistence — same swappable pattern, session-scoped so
 * navigating into a foundation and back doesn't reset filters. */
const FILTER_KEY = 'fe.filters'

export function loadPersistedFilters<T>(): Partial<T> | null {
  try { return JSON.parse(sessionStorage.getItem(FILTER_KEY) || 'null') }
  catch { return null }
}
export function persistFilters<T>(f: T) {
  sessionStorage.setItem(FILTER_KEY, JSON.stringify(f))
}
