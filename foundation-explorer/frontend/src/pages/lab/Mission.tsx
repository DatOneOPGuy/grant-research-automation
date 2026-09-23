/** Lab 7 — Mission-first onboarding.
 *
 *  The reviewer's replacement for Intent home: instead of asking users to
 *  categorize themselves ("what do you want?"), ask who they RESEMBLE —
 *  "we're most like Compassion / Cru / a Catholic school" — which is a
 *  question fundraisers already know how to answer. It's the email
 *  campaign's mini-list offer built into the product: the landing page
 *  becomes "funders already giving to work like yours," and one click
 *  saves the first ten as a starter folder so nobody arrives at an empty
 *  table.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Check, FolderPlus, RotateCcw } from 'lucide-react'
import DetailPanel from '../../components/foundations/DetailPanel'
import { fetchBenchmarkOrgs } from '../../lib/apiV5'
import { useSavedFoundations } from '../../lib/savedContext'
import { US_STATES, num } from '../../lib/format'
import { FoundationCard, LabBanner, useLab } from './shared'

/** Hand-picked peers, most-recognized first. Slugs are benchmark ministries
 *  (filter: foundations that funded them); the two tradition entries cover
 *  identities the benchmark list can't express. */
const PEERS: { id: string; label: string; kind: 'benchmark' | 'tradition'
  value: string }[] = [
  { id: 'compassion', label: 'Compassion International', kind: 'benchmark', value: 'compassion' },
  { id: 'cru', label: 'Cru / Campus Crusade', kind: 'benchmark', value: 'cru' },
  { id: 'wycliffe', label: 'Wycliffe Bible Translators', kind: 'benchmark', value: 'wycliffe' },
  { id: 'samaritans', label: "Samaritan's Purse", kind: 'benchmark', value: 'samaritans-purse' },
  { id: 'young-life', label: 'Young Life', kind: 'benchmark', value: 'young-life' },
  { id: 'ijm', label: 'International Justice Mission', kind: 'benchmark', value: 'ijm' },
  { id: 'catholic', label: 'A Catholic school or parish', kind: 'tradition', value: 'catholic' },
  { id: 'church', label: 'A local church or ministry', kind: 'tradition', value: 'evangelical_protestant' },
]

export default function LabMission() {
  const [peer, setPeer] = useState<typeof PEERS[number] | null>(null)
  const [state, setState] = useState('')
  const [started, setStarted] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const [seeded, setSeeded] = useState<'idle' | 'working' | 'done'>('idle')
  const { createFolder, addTo, folders } = useSavedFoundations()

  // Funder counts on the picker cards, so even the choosing step teaches
  // ("437 foundations fund work like Compassion's").
  const { data: bench } = useQuery({
    queryKey: ['benchmarkOrgs'], queryFn: fetchBenchmarkOrgs,
    staleTime: Infinity,
  })
  const funderCount = (slug: string) =>
    bench?.rows.find((r) => r.slug === slug)?.funders

  const { data, isFetching } = useLab(started && peer ? {
    benchmark: peer.kind === 'benchmark' ? peer.value : '',
    tradition: peer.kind === 'tradition' ? peer.value : '',
    gives_to_state: state,
    sort: 'christian',
  } : {}, 24, 0)

  const seedFolder = async () => {
    if (!data || !peer) return
    setSeeded('working')
    const name = `Starter: like ${peer.label.split('/')[0].trim()}`
    let folder = folders.find((f) => f.name === name)
      ?? await createFolder(name)
    if (folder) {
      for (const f of data.rows.slice(0, 10)) {
        await addTo(f.ein, String(folder.id))
      }
      setSeeded('done')
    } else {
      setSeeded('idle')
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <LabBanner testing="onboarding by resemblance — the mini-list offer built into the product" />

      {!started && (
        <>
          <div className="mt-8 text-center">
            <h1 className="font-display text-3xl font-semibold text-primary">
              What does your organization do?
            </h1>
            <p className="mt-2 text-sm text-muted">
              Pick whoever you're most like — we'll find the foundations
              already funding that kind of work.
            </p>
          </div>

          <div className="mt-6 grid gap-2.5 sm:grid-cols-2">
            {PEERS.map((p) => {
              const n = p.kind === 'benchmark' ? funderCount(p.value) : null
              const on = peer?.id === p.id
              return (
                <button key={p.id} onClick={() => setPeer(p)}
                  className={`flex items-center justify-between rounded-xl
                    border p-4 text-left transition-colors ${on
                      ? 'border-primary bg-primary/5'
                      : 'border-line bg-surface hover:border-honey-400'}`}>
                  <span>
                    <span className="block text-sm font-medium text-ink">
                      We're most like {p.label}
                    </span>
                    {n != null && (
                      <span className="block text-xs text-muted mt-0.5">
                        {num(n)} foundations fund work like theirs
                      </span>
                    )}
                  </span>
                  {on && <Check size={16} className="text-primary shrink-0" />}
                </button>
              )
            })}
          </div>

          <div className="mt-5 flex flex-col items-center gap-3 sm:flex-row">
            <select value={state} onChange={(e) => setState(e.target.value)}
              className="w-full rounded-xl border border-line bg-surface
                px-3 py-3 text-sm focus:outline-none focus:border-honey-500
                sm:w-56">
              <option value="">We work everywhere</option>
              {US_STATES.map((s) => (
                <option key={s} value={s}>We work in {s}</option>
              ))}
            </select>
            <button onClick={() => setStarted(true)} disabled={!peer}
              className="w-full flex-1 rounded-xl bg-primary py-3 text-sm
                font-medium text-white disabled:opacity-40">
              Show my funders
            </button>
          </div>
        </>
      )}

      {started && peer && (
        <div>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h1 className="font-display text-2xl font-semibold text-primary">
                Funders already giving to work like yours
              </h1>
              <p className="mt-0.5 text-sm text-muted">
                {data ? `${num(data.total)} foundations` : '…'} · like{' '}
                {peer.label}{state && ` · giving in ${state}`}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={seedFolder}
                disabled={seeded !== 'idle' || !data}
                className="flex items-center gap-1.5 rounded-lg bg-primary
                  px-3 py-2 text-sm font-medium text-white
                  disabled:opacity-50">
                <FolderPlus size={14} />
                {seeded === 'done' ? 'Starter folder created ✓'
                  : seeded === 'working' ? 'Saving…'
                    : 'Save the top 10 as my starter folder'}
              </button>
              <button onClick={() => { setStarted(false); setSeeded('idle') }}
                className="flex items-center gap-1 text-sm text-muted
                  hover:text-ink">
                <RotateCcw size={13} /> Change
              </button>
            </div>
          </div>

          <div className={`mt-5 grid gap-3 sm:grid-cols-2
            ${isFetching ? 'opacity-60' : ''}`}>
            {(data?.rows ?? []).map((f) => (
              <FoundationCard key={f.ein} f={f} onOpen={setSelected} />
            ))}
          </div>
        </div>
      )}

      {selected && (
        <DetailPanel ein={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
