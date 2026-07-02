import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import Dashboard from './pages/Dashboard'
import Foundations from './pages/Foundations'
import Grants from './pages/Grants'
import Recipients from './pages/Recipients'
import Analytics from './pages/Analytics'
import DataQuality from './pages/DataQuality'
import './styles/index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 60_000, retry: 1 },
  },
})

const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'foundations', element: <Foundations /> },
      { path: 'grants', element: <Grants /> },
      { path: 'recipients', element: <Recipients /> },
      { path: 'analytics', element: <Analytics /> },
      { path: 'data-quality', element: <DataQuality /> },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
