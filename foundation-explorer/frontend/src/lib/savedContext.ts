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
  addTo: (ein: string, folderId: string) => void
  removeFrom: (ein: string, folderId: string) => void
  removeAll: (ein: string) => void
  createFolder: (name: string) => SavedFolder
  renameFolder: (id: string, name: string) => void
  deleteFolder: (id: string) => void
}

export const SavedContext = createContext<SavedContextValue | null>(null)

export function useSavedFoundations(): SavedContextValue {
  const context = useContext(SavedContext)
  if (!context) throw new Error('useSavedFoundations outside SavedProvider')
  return context
}
