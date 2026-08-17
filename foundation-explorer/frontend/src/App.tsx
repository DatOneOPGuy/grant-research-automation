import { Outlet } from 'react-router-dom'
import Sidebar from './components/layout/Sidebar'
import { useQuery } from '@tanstack/react-query'
import { STATIC_MODE, fetchSampleMeta } from './lib/apiV5'
import { num } from './lib/format'

export default function App() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 min-w-0 px-4 lg:px-6 py-6">
        {/* Capped and centred: past ~1800px the table stops gaining useful
            information and just spreads the eye across dead space. */}
        <div className="mx-auto w-full max-w-[1800px]">
        {STATIC_MODE && <SampleBanner />}
        <Outlet />
        </div>
      </main>
    </div>
  )
}

// States plainly what is real and what is sampled. A reviewer judging this
// product needs to know which numbers are the whole database and which are a
// browsable subset -- overstating that would undercut the one thing the
// product sells, which is honest coverage.
function SampleBanner() {
  const { data } = useQuery({ queryKey: ['sampleMeta'], queryFn: fetchSampleMeta })
  return (
    <div className="mb-6 rounded-md border border-accent/40 bg-accent/10
      px-4 py-3 text-sm text-primary">
      <strong>Review build — sampled.</strong>{' '}
      Dashboard, analytics and data-quality figures are computed over the{' '}
      <strong>full database</strong>
      {data && <> ({num(data.foundations_total)} foundations,{' '}
        {num(data.grants_total)} grants, {num(data.recipients_total)}{' '}
        recipients)</>}
      . The browsable tables are a sample
      {data && <> — {num(data.foundations_in_sample)} foundations,{' '}
        {num(data.grants_in_sample)} grants, {num(data.recipients_in_sample)}{' '}
        recipients</>}
      , so counts and pagination inside the tables reflect the sample, not the
      whole universe. Recipient drill-down from the Recipients page is
      disabled in this build. All data is from public IRS Form 990-PF filings,
      tax years 2023–2024.
    </div>
  )
}
