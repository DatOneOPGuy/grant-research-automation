import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { SavedProvider } from './lib/SavedProvider'
import Dashboard from './pages/Dashboard'
import Foundations from './pages/Foundations'
import BestProspects from './pages/BestProspects'
import Saved from './pages/Saved'
import Grants from './pages/Grants'
import Recipients from './pages/Recipients'
import Analytics from './pages/Analytics'
import DataQuality from './pages/DataQuality'
import Trust from './pages/Trust'
import './styles/index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 60_000, retry: 1 },
  },
})

// Every page now runs against the v5 API. Nothing reads the retired v1
// endpoints, so the honest-coverage semantics hold across the whole app.
const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'best-prospects', element: <BestProspects /> },
      { path: 'foundations', element: <Foundations /> },
      { path: 'saved', element: <Saved /> },
      { path: 'grants', element: <Grants /> },
      { path: 'recipients', element: <Recipients /> },
      { path: 'analytics', element: <Analytics /> },
      { path: 'data-quality', element: <DataQuality /> },
      { path: 'trust', element: <Trust /> },
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
