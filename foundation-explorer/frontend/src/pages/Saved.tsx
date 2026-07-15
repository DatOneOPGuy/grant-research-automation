import { useState } from 'react'
import { useQueries } from '@tanstack/react-query'
import { Bookmark, ExternalLink, Trash2 } from 'lucide-react'
import { apiGet, DEMO } from '../lib/api'
import { useSavedFoundations } from '../lib/savedContext'
import { money, num, TAX_WINDOW_LABEL, titleCase } from '../lib/format'
import { StatusPill, VerdictBadge } from '../components/ui/primitives'
import DetailPanel from '../components/foundations/DetailPanel'

function toCsv(rows: any[]): string {
  const cols = ['ein', 'foundation_name', 'city', 'state', 'verdict',
    'christian_dollars_3yr', 'christian_recipient_count',
    'typical_grant_size', 'application_status', 'propublica_url']
  const esc = (v: any) => `"${String(v ?? '').replace(/"/g, '""')}"`
  return [cols.join(','),
    ...rows.map((r) => cols.map((c) => esc(r[c])).join(','))].join('\n')
}

export default function Saved() {
  const { saved, remove } = useSavedFoundations()
  const [selected, setSelected] = useState<string | null>(null)

  const results = useQueries({
    queries: saved.map((ein) => ({
      queryKey: ['foundation', ein],
      queryFn: () => apiGet<any>(`/api/foundations/${ein}`),
    })),
  })
  const rows = results.map((r) => r.data).filter(Boolean)

  const exportCsv = () => {
    const blob = new Blob([toCsv(rows)], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'saved_foundations.csv'
    a.click()
  }

  if (saved.length === 0) {
    return (
      <div>
        <h1 className="font-display text-3xl font-semibold text-primary mb-6">
          Saved Foundations
        </h1>
        <div className="border border-line rounded-lg bg-surface p-12 text-center">
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
      <div className="flex items-end justify-between mb-6">
        <div>
          <h1 className="font-display text-3xl font-semibold text-primary">
            Saved Foundations
          </h1>
          <div className="text-sm text-muted mt-1">
            {num(saved.length)} saved
          </div>
        </div>
        {!DEMO && (
          <button onClick={exportCsv}
            className="flex items-center gap-2 bg-primary text-white text-sm rounded-md px-4 py-2 hover:bg-primary/90">
            Export saved to CSV
          </button>
        )}
        {DEMO && (
          <button onClick={exportCsv}
            className="flex items-center gap-2 bg-primary text-white text-sm rounded-md px-4 py-2 hover:bg-primary/90">
            Export saved to CSV
          </button>
        )}
      </div>

      <div className="bg-surface border border-line rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted border-b border-line bg-canvas/50">
              <th className="px-3 py-3">Foundation</th>
              <th className="px-3">Location</th>
              <th className="px-3">Christian giving</th>
              <th className="px-3">Christian $ ({TAX_WINDOW_LABEL})</th>
              <th className="px-3">Typical grant</th>
              <th className="px-3">Application</th>
              <th className="px-3"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.ein} onClick={() => setSelected(r.ein)}
                className="border-b border-line/60 hover:bg-canvas/70 cursor-pointer">
                <td className="px-3 py-2.5 font-medium text-primary max-w-72 truncate">
                  {titleCase(r.foundation_name)}
                </td>
                <td className="px-3 text-muted whitespace-nowrap">
                  {titleCase(r.city)}, {r.state}
                </td>
                <td className="px-3 py-2">
                  <VerdictBadge verdict={r.verdict} />
                  {r.christian_preview && (
                    <div className="text-xs text-muted mt-1 max-w-64 truncate">
                      {titleCase(r.christian_preview)}
                    </div>
                  )}
                </td>
                <td className="px-3 tabular font-medium">
                  {money(r.christian_dollars_3yr)}
                </td>
                <td className="px-3 tabular text-muted">
                  {money(r.typical_grant_size)}
                </td>
                <td className="px-3"><StatusPill status={r.application_status} /></td>
                <td className="px-3">
                  <div className="flex items-center gap-1">
                    <a href={r.propublica_url} target="_blank" rel="noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="text-muted hover:text-primary p-1">
                      <ExternalLink size={14} />
                    </a>
                    <button onClick={(e) => { e.stopPropagation(); remove(r.ein) }}
                      title="Remove"
                      className="text-muted hover:text-red-600 p-1">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected && (
        <DetailPanel ein={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
