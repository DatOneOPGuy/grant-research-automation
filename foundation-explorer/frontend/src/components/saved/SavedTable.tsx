// The saved list itself. Row removal is folder-aware: inside a folder it
// removes only that membership, in the All view it unsaves outright, and the
// tooltip says which so the button is never ambiguous.
import { FolderMinus, Trash2 } from 'lucide-react'
import type { FoundationRowV5 } from '../../lib/apiV5'
import { useSavedFoundations } from '../../lib/savedContext'
import { money, titleCase } from '../../lib/format'
import { Card, Skeleton, StatusPill } from '../ui/primitives'

export default function SavedTable({
  rows, loading, expected, folderId, onOpen,
}: {
  rows: FoundationRowV5[]
  loading: boolean
  expected: number
  /** null in the "All saved" view. */
  folderId: string | null
  onOpen: (ein: string) => void
}) {
  const {
    folders, foldersFor, removeFrom, removeAll, busy,
  } = useSavedFoundations()

  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted border-b border-line">
              <th className="py-2">Foundation</th>
              <th>Location</th>
              {folderId === null && <th>Folders</th>}
              <th className="text-right">Christian</th>
              <th className="text-right">Paid</th>
              <th className="text-right">Coverage</th>
              <th>Applications</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => (
              <tr key={f.ein} className="border-b border-line/60 hover:bg-canvas">
                <td className="py-2 pr-3 font-medium cursor-pointer"
                  onClick={() => onOpen(f.ein)}>
                  {titleCase(f.name)}
                </td>
                <td className="pr-3 text-muted whitespace-nowrap">
                  {f.city && `${titleCase(f.city)}, `}{f.state}
                </td>
                {folderId === null && (
                  <td className="pr-3 text-muted text-xs max-w-40 truncate"
                    title={foldersFor(f.ein)
                      .map((id) => folders.find((x) => x.id === id)?.name)
                      .filter(Boolean).join(', ')}>
                    {foldersFor(f.ein)
                      .map((id) => folders.find((x) => x.id === id)?.name)
                      .filter(Boolean).join(', ')}
                  </td>
                )}
                <td className="text-right tabular pr-3">
                  {money(f.christian_dollars)}
                </td>
                <td className="text-right tabular pr-3">{money(f.paid_2324)}</td>
                <td className="text-right tabular pr-3">
                  {Math.round(f.coverage_pct)}%
                </td>
                <td className="pr-3">
                  <StatusPill status={f.application_status} />
                </td>
                <td>
                  <button
                    onClick={() => void (folderId
                      ? removeFrom(f.ein, folderId) : removeAll(f.ein))}
                    disabled={busy}
                    title={folderId
                      ? 'Remove from this folder'
                      : 'Remove from Saved entirely'}
                    aria-label={folderId
                      ? 'Remove from this folder'
                      : 'Remove from Saved'}
                    className="p-1 text-muted hover:text-scoremid
                      disabled:opacity-40">
                    {folderId
                      ? <FolderMinus size={14} /> : <Trash2 size={14} />}
                  </button>
                </td>
              </tr>
            ))}
            {loading && Array.from({ length: expected - rows.length })
              .map((_, i) => (
                <tr key={`s${i}`}>
                  <td colSpan={folderId === null ? 8 : 7} className="py-2">
                    <Skeleton className="h-6" />
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
