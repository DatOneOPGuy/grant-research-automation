import { createContext, useContext } from 'react'

export type SavedContextValue = {
  saved: string[]
  isSaved: (ein: string) => boolean
  toggle: (ein: string) => void
  remove: (ein: string) => void
}

export const SavedContext = createContext<SavedContextValue | null>(null)

export function useSavedFoundations(): SavedContextValue {
  const context = useContext(SavedContext)
  if (!context) throw new Error('useSavedFoundations outside SavedProvider')
  return context
}
