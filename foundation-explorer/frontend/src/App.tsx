import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './components/layout/Sidebar'
import { useQuery } from '@tanstack/react-query'
import { STATIC_MODE, fetchSampleMeta } from './lib/apiV5'
import { num } from './lib/format'
import GlobalSearch from './components/search/GlobalSearch'
import DetailPanel from './components/foundations/DetailPanel'

export default function App() {
  const [selected, setSelected] = useState<string | null>(null)

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 min-w-0">
        {/* Search sits above every page rather than on one of them: the thing
            a user wants to find is rarely on the page they happen to be on.
            Not rendered in the demo build, which has no API to query.

            The honey band runs the full width of the main column while its
            contents stay on the same 1800px measure as the page below, so the
            search box lines up with the table rather than floating over it.
            It is a background only -- nothing inside it is honey-on-honey,
            since #E0AC69 behind body text does not clear contrast. */}
        {!STATIC_MODE && (
          <div className="border-b border-honey-200/70 bg-gradient-to-b
            from-honey-100 to-honey-50 px-4 lg:px-6 py-4">
            <div className="mx-auto w-full max-w-[1800px]">
              <GlobalSearch onOpen={setSelected} />
            </div>
          </div>
        )}
        {/* Capped and centred: past ~1800px the table stops gaining useful
            information and just spreads the eye across dead space. */}
        <div className="px-4 lg:px-6 py-6">
          <div className="mx-auto w-full max-w-[1800px]">
            {STATIC_MODE && <SampleBanner />}
            <Outlet />
          </div>
        </div>
      </main>
      {selected && (
        <DetailPanel ein={selected} onClose={() => setSelected(null)} />
      )}
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
