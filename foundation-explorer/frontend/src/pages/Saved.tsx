import { useState } from 'react'
import { useQueries } from '@tanstack/react-query'
import { Bookmark, Trash2 } from 'lucide-react'
import { fetchFoundationDetailV5, type FoundationRowV5 } from '../lib/apiV5'
import { useSavedFoundations } from '../lib/savedContext'
import { money, num, TAX_WINDOW_LABEL, titleCase } from '../lib/format'
import { Card, StatusPill } from '../components/ui/primitives'
import DetailPanel from '../components/foundations/DetailPanel'

const CSV_COLUMNS: (keyof FoundationRowV5)[] = [
  'ein', 'name', 'city', 'state', 'paid_2324', 'christian_dollars',
  'coverage_pct', 'coverage_band', 'application_status', 'website',
  'recipient_count', 'median_grant',
]

function toCsv(rows: FoundationRowV5[]): string {
  const esc = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`
  return [
    [...CSV_COLUMNS, 'propublica_url'].join(','),
    ...rows.map((r) => [
      ...CSV_COLUMNS.map((c) => esc(r[c])),
      esc(`https://projects.propublica.org/nonprofits/organizations/${r.ein}`),
    ].join(',')),
  ].join('\n')
}

export default function Saved() {
  const { saved, remove } = useSavedFoundations()
  const [selected, setSelected] = useState<string | null>(null)

  const results = useQueries({
    queries: saved.map((ein) => ({
      queryKey: ['v5foundation', ein],
      queryFn: () => fetchFoundationDetailV5(ein),
    })),
  })
  const rows = results
    .map((r) => r.data?.foundation)
    .filter(Boolean) as FoundationRowV5[]

  const exportCsv = () => {
    const blob = new Blob([toCsv(rows)], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'saved_foundations.csv'
    a.click()
    URL.revokeObjectURL(a.href)
  }

  if (saved.length === 0) {
    return (
      <div>
        <h1 className="font-display text-3xl font-semibold text-primary mb-6">
          Saved Foundations
        </h1>
        <div className="border border-line rounded-lg bg-surface p-12
          text-center">
          <Bookmark size={28} className="mx-auto text-line mb-3" />
          <div className="text-muted">
            No saved foundations yet. Click the bookmark icon on any foundation
            to save it here.
          </div>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <h1 className="font-display text-3xl font-semibold text-primary">
          Saved Foundations
        </h1>
        <button onClick={exportCsv} disabled={rows.length === 0}
          className="text-sm px-3 py-1.5 border border-line rounded
            hover:bg-canvas disabled:opacity-40">
          Export CSV
        </button>
      </div>
      <p className="text-sm text-muted mb-4">
        {num(saved.length)} saved · paid grants, tax years {TAX_WINDOW_LABEL}.
        Saved list lives in this browser only.
      </p>

      <Card>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted border-b border-line">
                <th className="py-2">Foundation</th>
                <th>Location</th>
                <th className="text-right">Christian</th>
                <th className="text-right">Paid</th>
                <th className="text-right">Coverage</th>
                <th>Applications</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((f) => (
                <tr key={f.ein} className="border-b border-line/60
                  hover:bg-canvas">
                  <td className="py-2 pr-3 font-medium cursor-pointer"
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
                    {Math.round(f.coverage_pct)}%
                  </td>
                  <td className="pr-3">
                    <StatusPill status={f.application_status} />
                  </td>
                  <td>
                    <button onClick={() => remove(f.ein)}
                      title="Remove from saved"
                      className="p-1 text-muted hover:text-ink">
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {selected && (
        <DetailPanel ein={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
