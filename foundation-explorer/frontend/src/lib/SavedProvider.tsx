import { useCallback, useState, type ReactNode } from 'react'
import { SavedContext } from './savedContext'
import { savedFoundationsStore as store } from './savedStore'

export function SavedProvider({ children }: { children: ReactNode }) {
  const [saved, setSaved] = useState<string[]>(() => store.getSaved())
  const toggle = useCallback((ein: string) => {
    if (store.isSaved(ein)) store.remove(ein)
    else store.save(ein)
    setSaved(store.getSaved())
  }, [])
  const remove = useCallback((ein: string) => {
    store.remove(ein)
    setSaved(store.getSaved())
  }, [])
  const isSaved = useCallback((ein: string) => saved.includes(ein), [saved])
  return (
    <SavedContext.Provider value={{ saved, isSaved, toggle, remove }}>
      {children}
    </SavedContext.Provider>
  )
}
