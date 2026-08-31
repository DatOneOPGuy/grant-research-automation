import { Globe2 } from 'lucide-react'
import { BENCHMARK_CATEGORIES, type BenchmarkHit } from '../../../lib/apiV5'
import { money } from '../../../lib/format'
import { SectionTitle } from './parts'

/** The international ministries this funder has already given to.
 *
 *  This is the evidence behind the International filter, and it is the part a
 *  fundraiser actually uses: "you funded Wycliffe and the Seed Company, my
 *  client does Bible translation in Papua" is an opening line. A tier badge
 *  on its own is not.
 *
 *  Renders nothing at all when there are no hits. An empty panel here would
 *  read as "we checked and they fund no international work", which is a
 *  stronger claim than the data supports -- the list is 41 curated
 *  ministries, not every international organisation that exists. */
export default function BenchmarkHits({ hits }: { hits: BenchmarkHit[] }) {
  if (!hits.length) return null

  const byCategory: Record<string, BenchmarkHit[]> = {}
  for (const h of hits) (byCategory[h.category] ??= []).push(h)
  const total = hits.reduce((sum, h) => sum + h.dollars, 0)

  return (
    <div>
      <SectionTitle note="Major internationally-operating ministries this
        foundation has funded. Nearly all of them are headquartered in the US,
        so this giving does not appear under International — that measures
        foreign mailing addresses.">
        <span className="flex items-center gap-1.5">
          <Globe2 size={15} className="text-honey-600" />
          International track record
        </span>
      </SectionTitle>

      <div className="mt-2 rounded-lg border border-honey-200 bg-honey-50/60
        px-3 py-2.5">
        <div className="text-sm text-ink">
          <span className="font-semibold">{hits.length}</span>
          {hits.length === 1 ? ' ministry' : ' ministries'} funded
          <span className="text-muted"> · {money(total)} total</span>
        </div>

        {Object.entries(BENCHMARK_CATEGORIES).map(([key, label]) => {
          const rows = byCategory[key]
          if (!rows?.length) return null
          return (
            <div key={key} className="mt-2">
              <div className="text-[11px] uppercase tracking-wide
                text-honey-800">{label}</div>
              <div className="flex flex-wrap gap-1 mt-1">
                {rows.sort((a, b) => b.dollars - a.dollars).map((h) => (
                  <span key={h.slug}
                    title={`${h.grants} ${h.grants === 1 ? 'grant' : 'grants'}`}
                    className="text-xs rounded-full bg-surface border
                      border-honey-200 px-2 py-0.5 text-ink">
                    {h.name}
                    <span className="text-muted tabular"> {money(h.dollars)}</span>
                  </span>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
