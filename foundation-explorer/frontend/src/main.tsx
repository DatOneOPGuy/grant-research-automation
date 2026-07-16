import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { SavedProvider } from './lib/SavedProvider'
import Dashboard from './pages/Dashboard'
import Foundations from './pages/Foundations'
import BestProspects from './pages/BestProspects'
import NotRewired from './pages/NotRewired'
import './styles/index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 60_000, retry: 1 },
  },
})

// Dashboard + Foundations run against the v5 API. The remaining pages were
// wired to the retired v1 API and render a placeholder until migrated.
const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'best-prospects', element: <BestProspects /> },
      { path: 'foundations', element: <Foundations /> },
      { path: 'saved', element: <NotRewired name="Saved" /> },
      { path: 'grants', element: <NotRewired name="Grants" /> },
      { path: 'recipients', element: <NotRewired name="Recipients" /> },
      { path: 'analytics', element: <NotRewired name="Analytics" /> },
      { path: 'data-quality', element: <NotRewired name="Data Quality" /> },
      { path: 'trust', element: <NotRewired name="Trust & Data" /> },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <SavedProvider>
        <RouterProvider router={router} />
      </SavedProvider>
    </QueryClientProvider>
  </StrictMode>,
)
