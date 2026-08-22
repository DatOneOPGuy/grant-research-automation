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
import SearchResults from './pages/SearchResults'
import Grants from './pages/Grants'
import Recipients from './pages/Recipients'
import Analytics from './pages/Analytics'
import DataQuality from './pages/DataQuality'
import Trust from './pages/Trust'
import RouteError from './components/layout/RouteError'
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
    // One bad record must cost the reviewer a page, not the whole app.
    errorElement: <RouteError />,
    children: [
      { index: true, element: <Dashboard />, errorElement: <RouteError /> },
      { path: 'best-prospects', element: <BestProspects />, errorElement: <RouteError /> },
      { path: 'foundations', element: <Foundations />, errorElement: <RouteError /> },
      { path: 'saved', element: <Saved />, errorElement: <RouteError /> },
      { path: 'search', element: <SearchResults />, errorElement: <RouteError /> },
      { path: 'grants', element: <Grants />, errorElement: <RouteError /> },
      { path: 'recipients', element: <Recipients />, errorElement: <RouteError /> },
      { path: 'analytics', element: <Analytics />, errorElement: <RouteError /> },
      { path: 'data-quality', element: <DataQuality />, errorElement: <RouteError /> },
      { path: 'trust', element: <Trust />, errorElement: <RouteError /> },
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
