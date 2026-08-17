import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { SavedContext } from './savedContext'
import { savedFoundationsStore as store, type SavedFolder } from './savedStore'

export function SavedProvider({ children }: { children: ReactNode }) {
  const [folders, setFolders] = useState<SavedFolder[]>(() => store.getFolders())
  const [members, setMembers] = useState<Record<string, string[]>>(
    () => store.getMembership())

  // Every mutation re-reads from the store rather than patching local state,
  // so the two can never drift -- the store stays the single source of truth
  // and swapping it for an API-backed one changes nothing here.
  const sync = useCallback(() => {
    setFolders(store.getFolders())
    setMembers(store.getMembership())
  }, [])

  const saved = useMemo(() => Object.keys(members), [members])

  const value = useMemo(() => ({
    folders,
    saved,
    isSaved: (ein: string) => (members[ein]?.length ?? 0) > 0,
    foldersFor: (ein: string) => members[ein] ?? [],
    einsIn: (folderId: string) => Object.entries(members)
      .filter(([, ids]) => ids.includes(folderId))
      .map(([ein]) => ein),
    addTo: (ein: string, folderId: string) => { store.addTo(ein, folderId); sync() },
    removeFrom: (ein: string, folderId: string) => {
      store.removeFrom(ein, folderId); sync()
    },
    removeAll: (ein: string) => { store.removeAll(ein); sync() },
    createFolder: (name: string) => {
      const folder = store.createFolder(name)
      sync()
      return folder
    },
    renameFolder: (id: string, name: string) => {
      store.renameFolder(id, name); sync()
    },
    deleteFolder: (id: string) => { store.deleteFolder(id); sync() },
  }), [folders, members, saved, sync])

  return (
    <SavedContext.Provider value={value}>{children}</SavedContext.Provider>
  )
}
