import { useMemo, useState } from 'react'
import { useQueries } from '@tanstack/react-query'
import { Bookmark } from 'lucide-react'
import { fetchFoundationDetailV5, type FoundationRowV5 } from '../lib/apiV5'
import { useSavedFoundations } from '../lib/savedContext'
import { num, propublicaUrl, TAX_WINDOW_LABEL } from '../lib/format'
import DetailPanel from '../components/foundations/DetailPanel'
import FolderList from '../components/saved/FolderList'
import SavedTable from '../components/saved/SavedTable'
import { ALL } from '../components/saved/views'

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
      esc(propublicaUrl(r.ein)),
    ].join(',')),
  ].join('\n')
}

export default function Saved() {
  const {
    folders, saved, einsIn, loading, loadError, reload,
  } = useSavedFoundations()
  const [selected, setSelected] = useState<string | null>(null)
  const [view, setView] = useState<string>(ALL)

  // A deleted folder must not leave the page pointing at nothing.
  const activeView = view !== ALL && !folders.some((f) => f.id === view)
    ? ALL : view
  const activeFolder = folders.find((f) => f.id === activeView) || null
  const eins = activeView === ALL ? saved : einsIn(activeView)

  const results = useQueries({
    queries: eins.map((ein) => ({
      queryKey: ['v5foundation', ein],
      queryFn: () => fetchFoundationDetailV5(ein),
    })),
  })
  const rows = useMemo(
    () => results.map((r) => r.data?.foundation).filter(Boolean) as FoundationRowV5[],
    [results],
  )

  const exportCsv = () => {
    const blob = new Blob([toCsv(rows)], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    const label = activeFolder
      ? activeFolder.name.replace(/[^a-z0-9]+/gi, '_').toLowerCase()
      : 'all'
    a.download = `saved_foundations_${label}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <div>
      <div className="flex items-end justify-between mb-1">
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
        {num(saved.length)} saved in {folders.length}{' '}
        {folders.length === 1 ? 'folder' : 'folders'} · paid grants, tax years{' '}
        {TAX_WINDOW_LABEL}. Folders are shared with your team — everyone sees
        and edits the same lists.
      </p>

      {loadError && (
        <div className="mb-4 rounded-md border border-scoremid/40 bg-amber-50
          px-4 py-2.5 text-sm text-scoremid flex items-center gap-3">
          <span className="flex-1">
            Could not load your saved folders. {loadError}
          </span>
          <button onClick={() => void reload()}
            className="underline underline-offset-2 shrink-0">
            Try again
          </button>
        </div>
      )}

      <div className="flex gap-6 items-start">
        <FolderList activeView={activeView} onSelect={setView} />

        <div className="flex-1 min-w-0">
          {/* An empty list before the first load resolves is not "nothing
              saved" -- it is "not known yet", and saying the former would be
              a claim we cannot support. */}
          {loading ? (
            <div className="border border-line rounded-lg bg-surface p-12
              text-center text-muted text-sm">
              Loading your team's saved folders…
            </div>
          ) : loadError ? null : saved.length === 0 ? (
            <EmptyState hasFolders={folders.length > 0} />
          ) : eins.length === 0 ? (
            <div className="border border-line rounded-lg bg-surface p-12
              text-center text-muted text-sm">
              Nothing in{' '}
              <span className="font-medium text-ink">
                {activeFolder?.name}
              </span>{' '}
              yet. Use the bookmark button on any foundation to add it.
            </div>
          ) : (
            <SavedTable rows={rows} loading={rows.length < eins.length}
              expected={eins.length}
              folderId={activeView === ALL ? null : activeView}
              onOpen={setSelected} />
          )}
        </div>
      </div>

      {selected && (
        <DetailPanel ein={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}

function EmptyState({ hasFolders }: { hasFolders: boolean }) {
  return (
    <div className="border border-line rounded-lg bg-surface p-12 text-center">
      <Bookmark size={28} className="mx-auto text-line mb-3" />
      <div className="text-muted text-sm">
        No saved foundations yet. Click the bookmark icon on any foundation and
        choose a folder.
        {!hasFolders && (
          <>
            {' '}You have no folders — the bookmark menu will offer to create
            one.
          </>
        )}
      </div>
    </div>
  )
}
