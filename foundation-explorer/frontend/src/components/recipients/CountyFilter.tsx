import { useEffect, useRef, useState } from 'react'
import { MapPin, X } from 'lucide-react'
import { fetchCounties, type CountyOption } from '../../lib/apiV5'
import { num } from '../../lib/format'

// Counties as "CA|Los Angeles County", the same wire format the foundations
// filter uses, so the two pages stay one vocabulary.
const countyId = (c: CountyOption) => `${c.state}|${c.county}`
const countyLabel = (id: string) => {
  const [state, county] = id.split('|')
  return `${county.replace(/ County$/, '')}, ${state}`
}

/** Type-ahead over counties, ranked by how many recipients are in each.
 *
 *  Ranked rather than alphabetical because there are 3,162 of them and the
 *  one a user wants is nearly always a large one. The list opens with the
 *  biggest counties before anything is typed, so the control shows what it
 *  does without being asked. */
export default function CountyFilter({ value, onChange }: {
  value: string[]
  onChange: (next: string[]) => void
}) {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [rows, setRows] = useState<CountyOption[]>([])
  const boxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    let alive = true
    const t = setTimeout(() => {
      fetchCounties(q, [], 40, 'recipients')
        .then((r) => { if (alive) setRows(r.rows) })
        .catch(() => { if (alive) setRows([]) })
    }, 200)
    return () => { alive = false; clearTimeout(t) }
  }, [q, open])

  // Close on an outside click, so the list does not sit over the table.
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  const toggle = (id: string) => onChange(
    value.includes(id) ? value.filter((v) => v !== id) : [...value, id])

  return (
    <div className="flex flex-col text-xs text-muted" ref={boxRef}>
      County
      <div className="relative mt-1">
        <MapPin size={13} className="absolute left-2 top-1/2 -translate-y-1/2
          text-honey-600 pointer-events-none" />
        <input
          value={q}
          onChange={(e) => { setQ(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          placeholder={value.length
            ? `${value.length} selected`
            : 'County or city — try Brooklyn'}
          aria-label="Filter by county"
          className="border border-line rounded pl-7 pr-2 py-1.5 text-sm w-52
            focus:outline-none focus:ring-2 focus:ring-honey-400/40
            focus:border-honey-500" />

        {open && (
          <div className="absolute z-40 mt-1 w-72 max-h-72 overflow-y-auto
            rounded-lg border border-line bg-surface shadow-xl">
            {rows.length === 0 && (
              <div className="px-3 py-4 text-center text-xs text-muted">
                {q ? `Nothing matches “${q}” — try a city name.` : 'Loading…'}
              </div>
            )}
            {rows.map((c) => {
              const id = countyId(c)
              const on = value.includes(id)
              return (
                <button key={id} onClick={() => toggle(id)}
                  className={`w-full text-left px-3 py-1.5 text-sm flex
                    items-center justify-between gap-2 hover:bg-honey-50
                    ${on ? 'bg-honey-100' : ''}`}>
                  <span className="truncate text-ink">
                    {c.county}, {c.state}
                    {c.matched_city && (
                      <span className="text-muted"> · {c.matched_city}</span>
                    )}
                  </span>
                  <span className="text-[11px] text-muted tabular shrink-0">
                    {num(c.recipients ?? 0)}
                  </span>
                </button>
              )
            })}
          </div>
        )}
      </div>

      {value.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1.5 max-w-52">
          {value.map((id) => (
            <button key={id} onClick={() => toggle(id)}
              className="flex items-center gap-1 text-[11px] rounded-full
                bg-honey-100 text-honey-800 border border-honey-200
                px-2 py-0.5 hover:bg-honey-200">
              {countyLabel(id)}
              <X size={10} />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
