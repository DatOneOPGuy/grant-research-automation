import { createContext, useContext } from 'react'
import type { SavedFolder } from './savedStore'

export type SavedContextValue = {
  folders: SavedFolder[]
  /** Every saved EIN, across all folders. */
  saved: string[]
  isSaved: (ein: string) => boolean
  /** Folder ids containing this foundation. */
  foldersFor: (ein: string) => string[]
  /** EINs in one folder. */
  einsIn: (folderId: string) => string[]

  /** True until the first load resolves. Folders are empty and unreliable
   *  until then, so an empty list must not be rendered as "nothing saved". */
  loading: boolean
  /** The initial load failed. Distinct from a mutation failing: the state on
   *  screen is not merely stale, it was never fetched. */
  loadError: string | null
  /** The last write that failed, for the banner. Null once dismissed. */
  writeError: string | null
  dismissWriteError: () => void
  /** A mutation is in flight. Controls disabled at the call sites. */
  busy: boolean
  reload: () => Promise<void>

  // Mutations resolve once the server has confirmed and the client has
  // refetched. They never reject: a failure lands in writeError instead, so
  // no call site has to remember a try/catch to avoid an unhandled rejection.
  addTo: (ein: string, folderId: string) => Promise<void>
  /** `label` is only used for the undo toast; removal works without it. */
  removeFrom: (ein: string, folderId: string, label?: string) => Promise<void>
  removeAll: (ein: string, label?: string) => Promise<void>
  /** Resolves to the folder, or null if the create failed. */
  createFolder: (name: string) => Promise<SavedFolder | null>
  renameFolder: (id: string, name: string) => Promise<void>
  deleteFolder: (id: string) => Promise<void>
}

export const SavedContext = createContext<SavedContextValue | null>(null)

export function useSavedFoundations(): SavedContextValue {
  const context = useContext(SavedContext)
  if (!context) throw new Error('useSavedFoundations outside SavedProvider')
  return context
}
