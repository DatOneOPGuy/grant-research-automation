/* Persistence boundary for saved foundations, and the browser-local
 * implementation of it.
 *
 * Two stores implement this interface. ApiSavedStore (the live app) keeps
 * folders in Postgres, shared across the team. LocalSavedStore (the static
 * demo build) keeps them in localStorage, because a demo build has no API to
 * talk to. Which one is used is decided in SavedProvider.
 *
 * Foundations are organised into folders. Membership is many-to-many: the same
 * foundation can sit in "Catholic prospects" and "Ask in Q1" at once, which is
 * how a researcher actually works. A foundation is "saved" precisely when it
 * belongs to at least one folder, so removing it from its last folder unsaves
 * it and there is no orphan state to reconcile.
 *
 * Every folder is deletable, including Favorites. A product that seeds a
 * folder you cannot remove is making a filing decision on the user's behalf.
 *
 * The interface is asynchronous because the real store is a network away.
 * Even LocalSavedStore returns promises: one shape for both means the
 * components never need to know which one they are talking to.
 */

export type SavedFolder = { id: string; name: string; createdAt: string }

/** Everything the UI derives its saved state from, in one shape. */
export type SavedState = {
  folders: SavedFolder[]
  /** ein -> folder ids, for every saved foundation. */
  members: Record<string, string[]>
}

export interface SavedFoundationsStore {
  /** Full state. Called on mount and again after every mutation. */
  load(): Promise<SavedState>
  createFolder(name: string): Promise<SavedFolder>
  renameFolder(id: string, name: string): Promise<void>
  deleteFolder(id: string): Promise<void>
  addTo(ein: string, folderId: string): Promise<void>
  removeFrom(ein: string, folderId: string): Promise<void>
  /** Unsave entirely, across every folder. */
  removeAll(ein: string): Promise<void>
}

const STATE_KEY = 'fe.saved.v2'
const FILTER_KEY = 'fe.filters'

type State = { folders: SavedFolder[]; members: Record<string, string[]> }

function newId(): string {
  // crypto.randomUUID is unavailable on older Safari; the fallback only needs
  // to be unique within one browser's saved list.
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `f_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

function readState(): State {
  try {
    const raw = localStorage.getItem(STATE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as State
      if (Array.isArray(parsed?.folders) && parsed?.members) {
        return { folders: parsed.folders, members: parsed.members }
      }
    }
  } catch { /* fall through to an empty store */ }
  return { folders: [], members: {} }
}

/** localStorage-backed store. Used only by the static demo build. */
export class LocalSavedStore implements SavedFoundationsStore {
  private state: State

  constructor() {
    this.state = readState()
  }

  private persist() {
    localStorage.setItem(STATE_KEY, JSON.stringify(this.state))
  }

  async load(): Promise<SavedState> {
    const members: Record<string, string[]> = {}
    for (const [ein, ids] of Object.entries(this.state.members)) {
      if (ids.length) members[ein] = [...ids]
    }
    return { folders: [...this.state.folders], members }
  }

  async createFolder(name: string): Promise<SavedFolder> {
    const clean = name.trim() || 'Untitled folder'
    const existing = this.state.folders.find(
      (f) => f.name.toLowerCase() === clean.toLowerCase())
    if (existing) return existing
    const folder: SavedFolder = {
      id: newId(), name: clean, createdAt: new Date().toISOString(),
    }
    this.state.folders.push(folder)
    this.persist()
    return folder
  }

  async renameFolder(id: string, name: string): Promise<void> {
    const clean = name.trim()
    if (!clean) return
    const folder = this.state.folders.find((f) => f.id === id)
    if (!folder) return
    folder.name = clean
    this.persist()
  }

  async deleteFolder(id: string): Promise<void> {
    this.state.folders = this.state.folders.filter((f) => f.id !== id)
    for (const [ein, ids] of Object.entries(this.state.members)) {
      const next = ids.filter((x) => x !== id)
      // A foundation left in no folder is no longer saved; dropping the key
      // keeps "saved" derivable from membership alone.
      if (next.length) this.state.members[ein] = next
      else delete this.state.members[ein]
    }
    this.persist()
  }

  async addTo(ein: string, folderId: string): Promise<void> {
    if (!this.state.folders.some((f) => f.id === folderId)) return
    const ids = this.state.members[ein] || []
    if (!ids.includes(folderId)) this.state.members[ein] = [...ids, folderId]
    this.persist()
  }

  async removeFrom(ein: string, folderId: string): Promise<void> {
    const ids = this.state.members[ein]
    if (!ids) return
    const next = ids.filter((x) => x !== folderId)
    if (next.length) this.state.members[ein] = next
    else delete this.state.members[ein]
    this.persist()
  }

  async removeAll(ein: string): Promise<void> {
    delete this.state.members[ein]
    this.persist()
  }
}

export function loadPersistedFilters<T>(): Partial<T> | null {
  try { return JSON.parse(sessionStorage.getItem(FILTER_KEY) || 'null') }
  catch { return null }
}

export function persistFilters<T>(filters: T) {
  sessionStorage.setItem(FILTER_KEY, JSON.stringify(filters))
}
