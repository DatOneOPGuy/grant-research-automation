/* Recently viewed foundations.
 *
 * Browser-local on purpose, unlike saved folders. A saved folder is a
 * deliberate act the team shares; a view history is a byproduct of one
 * person's afternoon, and syncing it would publish everyone's browsing to
 * their colleagues without anyone asking for that. It is also cheap to lose --
 * which is the test for whether something needs a database.
 *
 * Most-recent first, de-duplicated by EIN, capped. Re-viewing a foundation
 * moves it to the front rather than adding a second entry, so the list reads
 * as "where I have been" rather than a raw event log.
 */

const KEY = 'fe.recent.v1'
const CAP = 25

export type RecentEntry = {
  ein: string
  name: string
  city: string | null
  state: string | null
  /** ISO timestamp of the most recent view. */
  viewedAt: string
}

function read(): RecentEntry[] {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    // Tolerate anything malformed rather than throwing on a page the user
    // was only passing through: a corrupt history is not worth an error.
    return parsed.filter(
      (e): e is RecentEntry =>
        e && typeof e.ein === 'string' && typeof e.name === 'string')
  } catch {
    return []
  }
}

function write(entries: RecentEntry[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(entries.slice(0, CAP)))
  } catch {
    // Quota exceeded or storage disabled (private windows). The feature is a
    // convenience; failing to record a view must never break the panel.
  }
}

/* Cached snapshot.
 *
 * useSyncExternalStore compares snapshots by reference and re-reads after
 * every render. A getSnapshot that parses JSON afresh returns a new array each
 * time, so React sees the store as perpetually changed and throws
 * "The result of getSnapshot should be cached to avoid an infinite loop".
 * The cache is the contract, not an optimisation: it is invalidated on write
 * and on a storage event from another tab, and at no other time. */
let cache: RecentEntry[] | null = null

/** Stable empty array for the server snapshot -- a fresh [] would have the
 *  same referential-instability problem during hydration. */
const EMPTY: RecentEntry[] = []

/** Subscribers, so every mounted list updates the moment a view is recorded. */
const listeners = new Set<() => void>()

function emit() {
  cache = null
  listeners.forEach((fn) => fn())
}

export function subscribeRecent(fn: () => void): () => void {
  listeners.add(fn)
  // Another tab writing the same key fires 'storage' here, which keeps two
  // open tabs consistent without any polling.
  const onStorage = (e: StorageEvent) => {
    if (e.key === KEY) { cache = null; fn() }
  }
  window.addEventListener('storage', onStorage)
  return () => {
    listeners.delete(fn)
    window.removeEventListener('storage', onStorage)
  }
}

/** Snapshot for useSyncExternalStore. Must return the same reference until
 *  the store actually changes -- see the note on `cache` above. */
export function getRecent(): RecentEntry[] {
  if (cache === null) cache = read()
  return cache
}

export function getRecentServerSnapshot(): RecentEntry[] {
  return EMPTY
}

export function recordView(entry: Omit<RecentEntry, 'viewedAt'>) {
  if (!entry.ein) return
  const next = [
    { ...entry, viewedAt: new Date().toISOString() },
    ...read().filter((e) => e.ein !== entry.ein),
  ]
  write(next)
  emit()
}

export function clearRecent() {
  try { localStorage.removeItem(KEY) } catch { /* see write() */ }
  emit()
}

export function removeRecent(ein: string) {
  write(read().filter((e) => e.ein !== ein))
  emit()
}
