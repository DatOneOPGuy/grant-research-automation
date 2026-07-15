/* Persistence boundaries for saved foundations and session filters.
 * Swap LocalSavedStore for API-backed persistence when user accounts land;
 * the interface consumed by the provider stays identical. */

export interface SavedFoundationsStore {
  getSaved(): string[]
  save(ein: string): void
  remove(ein: string): void
  isSaved(ein: string): boolean
}

const SAVED_KEY = 'fe.saved.eins'
const FILTER_KEY = 'fe.filters'

class LocalSavedStore implements SavedFoundationsStore {
  private set: Set<string>

  constructor() {
    let values: string[] = []
    try { values = JSON.parse(localStorage.getItem(SAVED_KEY) || '[]') }
    catch { values = [] }
    this.set = new Set(values)
  }

  private persist() {
    localStorage.setItem(SAVED_KEY, JSON.stringify([...this.set]))
  }

  getSaved() { return [...this.set] }
  save(ein: string) { this.set.add(ein); this.persist() }
  remove(ein: string) { this.set.delete(ein); this.persist() }
  isSaved(ein: string) { return this.set.has(ein) }
}

export const savedFoundationsStore: SavedFoundationsStore = new LocalSavedStore()

export function loadPersistedFilters<T>(): Partial<T> | null {
  try { return JSON.parse(sessionStorage.getItem(FILTER_KEY) || 'null') }
  catch { return null }
}

export function persistFilters<T>(filters: T) {
  sessionStorage.setItem(FILTER_KEY, JSON.stringify(filters))
}
