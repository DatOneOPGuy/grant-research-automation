// The saved list itself. Row removal is folder-aware: inside a folder it
// removes only that membership, in the All view it unsaves outright, and the
// tooltip says which so the button is never ambiguous.
import { ExternalLink, FolderMinus, Globe, Trash2 } from 'lucide-react'
import type { FoundationRowV5 } from '../../lib/apiV5'
import { useSavedFoundations } from '../../lib/savedContext'
import { money, propublicaUrl, titleCase, websiteUrl } from '../../lib/format'
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

  // The All view carries an extra Folders column, so the widths differ.
  // Declared rather than left to the browser: auto-layout sized columns from
  // whatever happened to be in them, so the same table changed shape between
  // folders and left the money columns floating in the middle of the row.
  const showFolders = folderId === null
  const widths = showFolders
    ? ['24%', '13%', '12%', '11%', '11%', '8%', '15%', '6%']
    : ['30%', '16%', '12%', '12%', '9%', '14%', '7%']
  const columnCount = widths.length

  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-sm table-fixed min-w-[820px]">
          <colgroup>
            {widths.map((w, i) => (
              <col key={i} style={{ width: w }} />
            ))}
          </colgroup>
          <thead>
            <tr className="text-left text-xs text-muted border-b border-line">
              <th className="py-2 px-3 font-medium">Foundation</th>
              <th className="px-3 font-medium">Location</th>
              {showFolders && <th className="px-3 font-medium">Folders</th>}
              <th className="px-3 font-medium text-right">Christian</th>
              <th className="px-3 font-medium text-right">Paid</th>
              <th className="px-3 font-medium text-right">Coverage</th>
              <th className="px-3 font-medium">Applications</th>
              <th className="px-2" />
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => {
              const folderNames = foldersFor(f.ein)
                .map((id) => folders.find((x) => x.id === id)?.name)
                .filter(Boolean).join(', ')
              const site = websiteUrl(f.website)
              return (
                <tr key={f.ein}
                  className="border-b border-line/60 last:border-0
                    hover:bg-canvas align-top">
                  <td className="py-2.5 px-3 font-medium cursor-pointer"
                    onClick={() => onOpen(f.ein)}>
                    <span className="line-clamp-2 leading-snug">
                      {titleCase(f.name)}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-muted text-xs">
                    <span className="line-clamp-2">
                      {f.city && `${titleCase(f.city)}, `}{f.state}
                    </span>
                  </td>
                  {showFolders && (
                    <td className="py-2.5 px-3 text-muted text-xs"
                      title={folderNames}>
                      <span className="line-clamp-2">{folderNames}</span>
                    </td>
                  )}
                  <td className="py-2.5 px-3 text-right tabular
                    whitespace-nowrap">
                    {money(f.christian_dollars)}
                  </td>
                  <td className="py-2.5 px-3 text-right tabular
                    whitespace-nowrap">
                    {money(f.paid_2324)}
                  </td>
                  <td className="py-2.5 px-3 text-right tabular
                    whitespace-nowrap">
                    {Math.round(f.coverage_pct)}%
                  </td>
                  <td className="py-2.5 px-3">
                    <StatusPill status={f.application_status} />
                  </td>
                  <td className="py-2.5 px-2">
                    <div className="flex items-center justify-end gap-0.5">
                      {site ? (
                        <a href={site} target="_blank" rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          title={f.website ?? undefined} aria-label="Website"
                          className="p-1 text-muted hover:text-primary shrink-0">
                          <Globe size={13} />
                        </a>
                      ) : (
                        <a href={propublicaUrl(f.ein)}
                          target="_blank" rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          title="No website on file — open on ProPublica"
                          aria-label="Open on ProPublica"
                          className="p-1 text-muted/60 hover:text-primary
                            shrink-0">
                          <ExternalLink size={13} />
                        </a>
                      )}
                      <button
                        onClick={() => void (folderId
                          ? removeFrom(f.ein, folderId, titleCase(f.name))
                          : removeAll(f.ein, titleCase(f.name)))}
                        disabled={busy}
                        title={folderId
                          ? 'Remove from this folder'
                          : 'Remove from Saved entirely'}
                        aria-label={folderId
                          ? 'Remove from this folder'
                          : 'Remove from Saved'}
                        className="p-1 text-muted hover:text-scoremid
                          disabled:opacity-40 shrink-0">
                        {folderId
                          ? <FolderMinus size={14} /> : <Trash2 size={14} />}
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
            {loading && Array.from({ length: expected - rows.length })
              .map((_, i) => (
                <tr key={`s${i}`}>
                  <td colSpan={columnCount} className="py-2 px-3">
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
