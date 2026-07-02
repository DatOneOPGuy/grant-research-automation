import { Outlet } from 'react-router-dom'
import Sidebar from './components/layout/Sidebar'
import { DEMO } from './lib/api'

export default function App() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 min-w-0 p-8">
        {DEMO && (
          <div className="mb-6 rounded-md border border-accent/40 bg-accent/10 px-4 py-2.5 text-sm text-primary">
            <strong>Demo build.</strong> Dashboard and analytics numbers are
            computed from the full 139,965-foundation database; the browsable
            tables contain a 2,000-foundation sample (top faith-aligned +
            random). All data is from public IRS 990-PF filings.
          </div>
        )}
        <Outlet />
      </main>
    </div>
  )
}
