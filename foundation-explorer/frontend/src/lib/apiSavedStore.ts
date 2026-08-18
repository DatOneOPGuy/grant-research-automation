/* API-backed saved folders: the live app's store.
 *
 * Folders are shared across the team, so two people can be editing the same
 * list at once. There is no realtime sync here on purpose -- it would be a lot
 * of machinery for a team of a few researchers -- but every mutation is
 * followed by a refetch in SavedProvider, so a stale client corrects itself on
 * its next action rather than accumulating divergence.
 *
 * Identity comes from Cloudflare Access, which authenticates the user before
 * the request reaches us and forwards a signed token. The browser therefore
 * sends nothing: no login page, no token handling, no credentials in JS. A 401
 * here means the Access session expired, and the fix is a page reload, which
 * Access answers with its own login flow.
 */

import { V5_BASE } from './apiV5'
import type {
  SavedFolder, SavedFoundationsStore, SavedState,
} from './savedStore'

export class SavedApiError extends Error {
  status: number
  /** True when the Access session is gone and a reload will re-authenticate. */
  needsReload: boolean

  constructor(message: string, status: number) {
    super(message)
    this.name = 'SavedApiError'
    this.status = status
    this.needsReload = status === 401 || status === 403
  }
}

type ApiItem = { ein: string; note: string | null; added_by: string | null }
type ApiFolder = {
  id: number
  name: string
  created_by: string | null
  created_at: string
  items: ApiItem[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${V5_BASE}/api/v5${path}`, {
      ...init,
      headers: init?.body
        ? { 'Content-Type': 'application/json', ...(init?.headers || {}) }
        : init?.headers,
    })
  } catch {
    // fetch only rejects on a transport failure, which is the one case the
    // user can act on directly.
    throw new SavedApiError('No connection to the server.', 0)
  }

  if (!res.ok) throw new SavedApiError(await describe(res), res.status)
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

async function describe(res: Response): Promise<string> {
  if (res.status === 401 || res.status === 403) {
    return 'Your session has expired. Reload the page to sign in again.'
  }
  if (res.status === 503) {
    return 'Saved folders are temporarily unavailable. Reads still work.'
  }
  try {
    const body = await res.json()
    const detail = body?.detail
    if (typeof detail === 'string') return detail
    // FastAPI validation errors arrive as a list of objects.
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg)
  } catch { /* fall through to the generic message */ }
  return `Request failed (${res.status}).`
}

/** Folder ids are integers server-side and strings everywhere in the UI, so
 *  that the two stores present the same type and no component has to care. */
function toFolder(f: ApiFolder): SavedFolder {
  return { id: String(f.id), name: f.name, createdAt: f.created_at }
}

export class ApiSavedStore implements SavedFoundationsStore {
  async load(): Promise<SavedState> {
    const raw = await request<ApiFolder[]>('/folders')
    const folders = raw.map(toFolder)
    // Invert folders-with-items into the ein -> folder-ids map the UI reads.
    // One response, no N+1: the whole saved surface derives from this.
    const members: Record<string, string[]> = {}
    for (const folder of raw) {
      for (const item of folder.items) {
        const ids = members[item.ein] || (members[item.ein] = [])
        if (!ids.includes(String(folder.id))) ids.push(String(folder.id))
      }
    }
    return { folders, members }
  }

  async createFolder(name: string): Promise<SavedFolder> {
    // The server returns the existing folder if the name is already taken,
    // case-insensitively, so a duplicate is a merge rather than an error.
    return toFolder(await request<ApiFolder>('/folders', {
      method: 'POST', body: JSON.stringify({ name }),
    }))
  }

  async renameFolder(id: string, name: string): Promise<void> {
    await request<ApiFolder>(`/folders/${id}`, {
      method: 'PATCH', body: JSON.stringify({ name }),
    })
  }

  async deleteFolder(id: string): Promise<void> {
    await request<void>(`/folders/${id}`, { method: 'DELETE' })
  }

  async addTo(ein: string, folderId: string): Promise<void> {
    // Idempotent server-side: adding a foundation already in the folder is a
    // no-op, so a double-click or a teammate's concurrent save is not an error.
    await request<ApiFolder>(`/folders/${folderId}/items`, {
      method: 'POST', body: JSON.stringify({ ein }),
    })
  }

  async removeFrom(ein: string, folderId: string): Promise<void> {
    await request<void>(`/folders/${folderId}/items/${ein}`, {
      method: 'DELETE',
    })
  }

  async removeAll(ein: string): Promise<void> {
    // One transaction server-side rather than a delete per folder: a fan-out
    // that half-fails would leave the foundation saved in some folders and not
    // others, with nothing in the UI to show which.
    await request<void>(`/items/${ein}`, { method: 'DELETE' })
  }
}
