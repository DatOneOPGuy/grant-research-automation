/* Persistence boundaries for saved foundations and session filters.
 * Swap LocalSavedStore for API-backed persistence when user accounts land;
 * the interface consumed by the provider stays identical.
 *
 * Foundations are organised into folders. Membership is many-to-many: the same
 * foundation can sit in "Catholic prospects" and "Ask in Q1" at once, which is
 * how a researcher actually works. A foundation is "saved" precisely when it
 * belongs to at least one folder, so removing it from its last folder unsaves
 * it and there is no orphan state to reconcile.
 *
 * Every folder is deletable, including Favorites. A product that seeds a
 * folder you cannot remove is making a filing decision on the user's behalf.
 */

export type SavedFolder = { id: string; name: string; createdAt: string }

export interface SavedFoundationsStore {
  getFolders(): SavedFolder[]
  /** ein -> folder ids, for every saved foundation. */
  getMembership(): Record<string, string[]>
  createFolder(name: string): SavedFolder
  renameFolder(id: string, name: string): void
  deleteFolder(id: string): void
  addTo(ein: string, folderId: string): void
  removeFrom(ein: string, folderId: string): void
  /** Unsave entirely, across every folder. */
  removeAll(ein: string): void
}

const STATE_KEY = 'fe.saved.v2'
const LEGACY_KEY = 'fe.saved.eins'
const FILTER_KEY = 'fe.filters'
const DEFAULT_FOLDER_NAME = 'Favorites'

type State = { folders: SavedFolder[]; members: Record<string, string[]> }

function newId(): string {
  // crypto.randomUUID is unavailable on older Safari; the fallback only needs
  // to be unique within one browser's saved list.
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `f_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

function emptyState(): State {
  return { folders: [], members: {} }
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
  } catch { /* fall through to migration */ }

  // Migrate the flat pre-folder list into a starting Favorites folder, so an
  // existing saved list survives the upgrade instead of silently emptying.
  let legacy: string[] = []
  try { legacy = JSON.parse(localStorage.getItem(LEGACY_KEY) || '[]') }
  catch { legacy = [] }

  const state = emptyState()
  const folder: SavedFolder = {
    id: newId(), name: DEFAULT_FOLDER_NAME, createdAt: new Date().toISOString(),
  }
  state.folders.push(folder)
  legacy.filter(Boolean).forEach((ein) => { state.members[ein] = [folder.id] })
  return state
}

class LocalSavedStore implements SavedFoundationsStore {
  private state: State

  constructor() {
    this.state = readState()
    this.persist()
  }

  private persist() {
    localStorage.setItem(STATE_KEY, JSON.stringify(this.state))
  }

  getFolders() { return [...this.state.folders] }
  getMembership() {
    // Deep-ish copy: callers should not be able to mutate stored arrays.
    const out: Record<string, string[]> = {}
    for (const [ein, ids] of Object.entries(this.state.members)) {
      if (ids.length) out[ein] = [...ids]
    }
    return out
  }

  createFolder(name: string) {
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

  renameFolder(id: string, name: string) {
    const clean = name.trim()
    if (!clean) return
    const folder = this.state.folders.find((f) => f.id === id)
    if (!folder) return
    folder.name = clean
    this.persist()
  }

  deleteFolder(id: string) {
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

  addTo(ein: string, folderId: string) {
    if (!this.state.folders.some((f) => f.id === folderId)) return
    const ids = this.state.members[ein] || []
    if (!ids.includes(folderId)) this.state.members[ein] = [...ids, folderId]
    this.persist()
  }

  removeFrom(ein: string, folderId: string) {
    const ids = this.state.members[ein]
    if (!ids) return
    const next = ids.filter((x) => x !== folderId)
    if (next.length) this.state.members[ein] = next
    else delete this.state.members[ein]
    this.persist()
  }

  removeAll(ein: string) {
    delete this.state.members[ein]
    this.persist()
  }
}

export const savedFoundationsStore: SavedFoundationsStore = new LocalSavedStore()

export function loadPersistedFilters<T>(): Partial<T> | null {
  try { return JSON.parse(sessionStorage.getItem(FILTER_KEY) || 'null') }
  catch { return null }
}

export function persistFilters<T>(filters: T) {
  sessionStorage.setItem(FILTER_KEY, JSON.stringify(filters))
}
