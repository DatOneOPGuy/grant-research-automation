/** Lab 6 — The receipt column.
 *
 *  The reviewer's #1 bet: a fundraiser thinks in names, not percentages.
 *  This is the Quiet table with the focus phrase REPLACED by the receipt —
 *  "Funded Wycliffe, Samaritan's Purse + 14 more" — benchmark ministries
 *  first (bold, because recognition is the mechanism), then biggest
 *  recipients by dollars. It is the evidence chain surfaced as prose, and
 *  the line Emily would paste into an opening paragraph.
 *
 *  Save is the primary action here (bookmark leads every row) and each row
 *  carries the quiet "this looks wrong" flag — reviewer items 3 and 5
 *  riding along so one session tests three ideas.
 */
import { useState } from 'react'
import DetailPanel from '../../components/foundations/DetailPanel'
import { ANY_CHRISTIAN } from '../../lib/apiV5'
import { US_STATES, money, num, titleCase } from '../../lib/format'
import {
  AdvancedButton, AdvancedDrawer, CauseSelect, FlagButton, LabBanner,
  QuickSave, ReceiptLine, applyPhrase, placeOf, useAdvanced, useLab,
  useReceipts,
} from './shared'

export default function LabReceipts() {
  const [state, setState] = useState('')
  const [cause, setCause] = useState('')
  const [accepting, setAccepting] = useState(false)
  const [international, setInternational] = useState(false)
  const [page, setPage] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const adv = useAdvanced()

  const { data, isFetching } = useLab({
    tradition: ANY_CHRISTIAN,
    ntee: cause,
    gives_to_state: state,
    application_status: accepting ? 'Accepting Applications' : '',
    min_benchmarks: international ? '1' : '',
    sort: 'christian',
    ...adv.params,
  }, 25, page)
  const { data: receipts } = useReceipts(
    (data?.rows ?? []).map((f) => f.ein))

  return (
    <div className="mx-auto max-w-5xl">
      <LabBanner testing="names instead of percentages — does the receipt beat the phrase?" />

      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl font-semibold text-primary">
            Who funded whom
          </h1>
          <div className="mt-0.5 text-sm text-muted">
            {data ? `${num(data.total)} Christian funders` : '…'} — the names
            do the explaining.
          </div>
        </div>
        <div className="flex items-center gap-2">
          <CauseSelect value={cause}
            onChange={(v) => { setCause(v); setPage(0) }} />
          <select value={state} onChange={(e) => { setState(e.target.value); setPage(0) }}
            className="rounded-lg border border-line bg-surface px-2.5 py-1.5
              text-sm focus:outline-none focus:border-honey-500">
            <option value="">Gives anywhere</option>
            {US_STATES.map((s) => (
              <option key={s} value={s}>Gives in {s}</option>
            ))}
          </select>
          <Chip on={accepting} onClick={() => { setAccepting(!accepting); setPage(0) }}>
            I can apply
          </Chip>
          <Chip on={international} onClick={() => { setInternational(!international); setPage(0) }}>
            International
          </Chip>
          <AdvancedButton adv={adv} />
        </div>
      </div>

      <div className="overflow-hidden rounded-xl border border-line bg-surface">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b-2 border-honey-300 bg-honey-50/60
              text-left text-xs text-muted">
              <th className="w-10 py-2.5" />
              <th className="py-2.5 pr-3 font-medium">Foundation</th>
              <th className="px-3 font-medium">What they funded</th>
              <th className="px-3 font-medium text-right">
                To Christian work
              </th>
              <th className="px-3 font-medium">Apply?</th>
              <th className="w-10" />
            </tr>
          </thead>
          <tbody className={isFetching ? 'opacity-60' : ''}>
            {(data?.rows ?? []).map((f) => {
              const apply = applyPhrase(f.application_status)
              return (
                <tr key={f.ein} onClick={() => setSelected(f.ein)}
                  className="cursor-pointer border-b border-line/60
                    align-top hover:bg-canvas">
                  <td className="py-2.5 pl-2"
                    onClick={(e) => e.stopPropagation()}>
                    <QuickSave ein={f.ein} />
                  </td>
                  <td className="py-2.5 pr-3">
                    <div className="font-medium text-primary leading-snug">
                      {titleCase(f.name)}
                    </div>
                    <div className="text-xs text-muted">{placeOf(f)}</div>
                  </td>
                  <td className="px-3 py-2.5 max-w-[22rem]">
                    <ReceiptLine f={f} receipts={receipts} />
                  </td>
                  <td className="px-3 py-2.5 text-right tabular font-medium
                    whitespace-nowrap">
                    {money(f.christian_dollars)}
                  </td>
                  <td className="px-3 py-2.5">
                    <span className={`text-xs font-medium ${
                      apply.open === true ? 'text-scorehigh'
                        : apply.open === false ? 'text-muted'
                          : 'text-muted/60'}`}>
                      {apply.label}
                    </span>
                  </td>
                  <td className="py-2.5 pr-2"
                    onClick={(e) => e.stopPropagation()}>
                    <FlagButton ein={f.ein} />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {data && data.total > 25 && (
        <div className="mt-4 flex justify-center gap-3 text-sm">
          <button onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="rounded-lg border border-line px-4 py-2
              hover:bg-canvas disabled:opacity-40">Previous</button>
          <button onClick={() => setPage((p) => p + 1)}
            disabled={(page + 1) * 25 >= data.total}
            className="rounded-lg border border-line px-4 py-2
              hover:bg-canvas disabled:opacity-40">Next</button>
        </div>
      )}

      <AdvancedDrawer adv={adv} />
      {selected && (
        <DetailPanel ein={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}

function Chip({ on, onClick, children }: {
  on: boolean; onClick: () => void; children: React.ReactNode
}) {
  return (
    <button onClick={onClick}
      className={`rounded-full border px-3 py-1.5 text-sm transition-colors
        ${on ? 'border-primary bg-primary text-white'
          : 'border-line bg-surface text-muted hover:text-ink'}`}>
      {children}
    </button>
  )
}
