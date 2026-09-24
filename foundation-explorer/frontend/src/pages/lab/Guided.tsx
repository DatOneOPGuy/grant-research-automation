/** Lab 2 — Three questions.
 *
 *  For the person Emily described: someone who doesn't know what she knows.
 *  No filter has a name here; the user answers three questions in their own
 *  vocabulary and the answers BECOME the filters. The test: does a wizard
 *  feel guiding or patronising to a real fundraiser?
 */
import { useState } from 'react'
import { ArrowLeft, RotateCcw } from 'lucide-react'
import DetailPanel from '../../components/foundations/DetailPanel'
import { ANY_CHRISTIAN } from '../../lib/apiV5'
import { US_STATES, num } from '../../lib/format'
import { AdvancedButton, AdvancedDrawer, CauseSelect, FoundationCard,
  LabBanner, useAdvanced, useLab } from './shared'

const WORK = [
  { id: 'christian', label: 'Christian ministry or church work',
    blurb: 'Churches, ministries, Christian schools, discipleship' },
  { id: 'international', label: 'International missions',
    blurb: 'Overseas evangelism, translation, relief, child sponsorship' },
  { id: 'catholic', label: 'Catholic work',
    blurb: 'Parishes, Catholic schools, religious orders' },
  { id: 'any', label: 'Something else / not sure',
    blurb: 'Start broad — you can narrow later' },
] as const

export default function LabGuided() {
  const [step, setStep] = useState(0)
  const [work, setWork] = useState<string | null>(null)
  const [state, setState] = useState<string>('')
  const [openOnly, setOpenOnly] = useState<boolean | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [cause, setCause] = useState('')
  const adv = useAdvanced()

  const done = step >= 3
  const { data, isFetching } = useLab({
    tradition: work === 'catholic' ? 'catholic'
      : work === 'christian' ? ANY_CHRISTIAN : '',
    min_benchmarks: work === 'international' ? '1' : '',
    gives_to_state: state,
    ntee: cause,
    application_status: openOnly ? 'Accepting Applications' : '',
    sort: 'christian',
    ...adv.params,
  }, 24, 0)

  const reset = () => {
    setStep(0); setWork(null); setState(''); setOpenOnly(null)
  }

  return (
    <div className="mx-auto max-w-2xl">
      <LabBanner testing="three questions instead of named filters" />

      {!done && (
        <div className="mt-4">
          {/* Progress: words, not a widget. */}
          <div className="mb-6 flex items-center justify-between">
            <span className="text-xs uppercase tracking-widest text-honey-700">
              Question {step + 1} of 3
            </span>
            {step > 0 && (
              <button onClick={() => setStep((s) => s - 1)}
                className="flex items-center gap-1 text-xs text-muted
                  hover:text-ink">
                <ArrowLeft size={12} /> Back
              </button>
            )}
          </div>

          {step === 0 && (
            <>
              <h1 className="font-display text-2xl font-semibold text-primary">
                What kind of work are you raising money for?
              </h1>
              <div className="mt-5 grid gap-3">
                {WORK.map((w) => (
                  <button key={w.id}
                    onClick={() => { setWork(w.id); setStep(1) }}
                    className="rounded-xl border border-line bg-surface p-4
                      text-left hover:border-honey-400 hover:shadow-sm">
                    <div className="font-medium text-ink">{w.label}</div>
                    <div className="text-xs text-muted mt-0.5">{w.blurb}</div>
                  </button>
                ))}
              </div>
            </>
          )}

          {step === 1 && (
            <>
              <h1 className="font-display text-2xl font-semibold text-primary">
                Where does the money need to go?
              </h1>
              <p className="text-sm text-muted mt-1">
                We'll find foundations that actually pay grants there.
              </p>
              <div className="mt-5 flex flex-col gap-3">
                <select value={state}
                  onChange={(e) => setState(e.target.value)}
                  className="rounded-xl border border-line bg-surface p-3.5
                    text-sm focus:outline-none focus:border-honey-500">
                  <option value="">Choose a state…</option>
                  {US_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <div className="flex gap-3">
                  <button onClick={() => setStep(2)} disabled={!state}
                    className="flex-1 rounded-xl bg-primary py-3 text-sm
                      font-medium text-white disabled:opacity-40">
                    Next
                  </button>
                  <button
                    onClick={() => { setState(''); setStep(2) }}
                    className="flex-1 rounded-xl border border-line py-3
                      text-sm text-muted hover:text-ink">
                    Anywhere / national
                  </button>
                </div>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <h1 className="font-display text-2xl font-semibold text-primary">
                Only show funders you can apply to?
              </h1>
              <p className="text-sm text-muted mt-1">
                Most foundations are invite-only. We can hide them — or keep
                them, since they're often worth a relationship.
              </p>
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <button onClick={() => { setOpenOnly(true); setStep(3) }}
                  className="rounded-xl border border-line bg-surface p-4
                    text-left hover:border-honey-400">
                  <div className="font-medium text-ink">
                    Yes — open applications only
                  </div>
                  <div className="text-xs text-muted mt-0.5">
                    The list I can act on this month
                  </div>
                </button>
                <button onClick={() => { setOpenOnly(false); setStep(3) }}
                  className="rounded-xl border border-line bg-surface p-4
                    text-left hover:border-honey-400">
                  <div className="font-medium text-ink">Show me everyone</div>
                  <div className="text-xs text-muted mt-0.5">
                    Including invite-only funders
                  </div>
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {done && (
        <div>
          <div className="flex items-end justify-between">
            <div>
              <h1 className="font-display text-2xl font-semibold text-primary">
                {data ? `${num(data.total)} funders for you` : 'Finding…'}
              </h1>
              <p className="text-sm text-muted mt-0.5">
                {WORK.find((w) => w.id === work)?.label}
                {state && ` · gives in ${state}`}
                {openOnly && ' · open to applications'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <CauseSelect value={cause} onChange={setCause} />
              <AdvancedButton adv={adv} />
              <button onClick={reset}
                className="flex items-center gap-1.5 text-sm text-muted
                  hover:text-ink">
                <RotateCcw size={13} /> Start over
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

      <AdvancedDrawer adv={adv} />
      {selected && (
        <DetailPanel ein={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
