import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ExternalLink } from 'lucide-react'
import { ANY_CHRISTIAN, fetchFoundationsV5 } from '../lib/apiV5'
import { money, num, TAX_WINDOW_LABEL, titleCase } from '../lib/format'
import { Card, Skeleton, StatusPill } from '../components/ui/primitives'
import DetailPanel from '../components/foundations/DetailPanel'

// The actionable set: demonstrably funds Christian work, accepts applications,
// and can be contacted. Coverage is restricted to High/Moderate so a prospect
// is never surfaced on the strength of a foundation we barely classified.
const MIN_CHRISTIAN = 50_000

function query(): string {
  const p = new URLSearchParams()
  p.set('tradition', ANY_CHRISTIAN)
  p.set('min_tradition_dollars', String(MIN_CHRISTIAN))
  p.set('application_status', 'Accepting Applications')
  p.set('coverage_band', 'High,Moderate')
  p.set('has_website', 'true')
  p.set('exclude_micro', 'true')
  p.set('exclude_testamentary', 'true')
  p.set('sort', 'christian')
  return p.toString()
}

export default function BestProspects() {
  const [selected, setSelected] = useState<string | null>(null)
  const { data } = useQuery({
    queryKey: ['v5bestProspects'],
    queryFn: () => fetchFoundationsV5(query(), 200, 0),
  })

  return (
    <div>
      <h1 className="font-display text-3xl font-semibold text-primary mb-1">
        Best Prospects
      </h1>
      <p className="text-sm text-muted mb-4 max-w-3xl">
        Foundations that gave at least {money(MIN_CHRISTIAN)} to Christian
        organizations in {TAX_WINDOW_LABEL}, accept applications, have a
        website, and whose giving we have classified with High or Moderate
        coverage. Every row is defensible: open one to see the recipients and
        the evidence behind each classification.
      </p>

      {!data && <Skeleton className="h-96" />}
      {data && (
        <>
          <div className="text-sm text-muted mb-2">
            {num(data.total)} actionable prospects
          </div>
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-muted border-b
                    border-line">
                    <th className="py-2">#</th>
                    <th>Foundation</th>
                    <th>Location</th>
                    <th className="text-right">Christian</th>
                    <th className="text-right">Paid</th>
                    <th className="text-right">Median grant</th>
                    <th className="text-right">Coverage</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((f, i) => (
                    <tr key={f.ein} className="border-b border-line/60
                      hover:bg-canvas">
                      <td className="py-2 text-muted tabular">{i + 1}</td>
                      <td className="pr-3 font-medium cursor-pointer"
                        onClick={() => setSelected(f.ein)}>
                        {titleCase(f.name)}
                      </td>
                      <td className="pr-3 text-muted whitespace-nowrap">
                        {f.city && `${titleCase(f.city)}, `}{f.state}
                      </td>
                      <td className="text-right tabular pr-3">
                        {money(f.christian_dollars)}
                      </td>
                      <td className="text-right tabular pr-3">
                        {money(f.paid_2324)}
                      </td>
                      <td className="text-right tabular pr-3">
                        {money(f.median_grant)}
                      </td>
                      <td className="text-right tabular pr-3">
                        {Math.round(f.coverage_pct)}%
                      </td>
                      <td className="pr-3">
                        <StatusPill status={f.application_status} />
                      </td>
                      <td>
                        {f.website && (
                          <a href={f.website.startsWith('http')
                            ? f.website : `https://${f.website}`}
                            target="_blank" rel="noreferrer"
                            title="Foundation website"
                            className="text-primary inline-flex p-1">
                            <ExternalLink size={13} />
                          </a>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}

      {selected && (
        <DetailPanel ein={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
