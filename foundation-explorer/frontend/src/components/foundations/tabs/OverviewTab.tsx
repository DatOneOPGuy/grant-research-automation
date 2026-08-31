// The "is this worth my time" tab: scale, typical grant size, what the money
// funds, and whether the pattern is steady or a one-off spike.
import {
  traditionLabel, type FoundationDetailV5,
} from '../../../lib/apiV5'
import { money } from '../../../lib/format'
import { BarRow, Empty, SectionTitle, Stat } from './parts'
import SectorBreakdown from './SectorBreakdown'
import BenchmarkHits from './BenchmarkHits'

export default function OverviewTab({ data }: { data: FoundationDetailV5 }) {
  const f = data.foundation
  const years = data.yearly
  // "any" tier is the full picture; the authoritative tier is the rigor dial
  // and gets its own treatment in the Evidence tab.
  const mix = data.traditions.filter((t) => t.tier === 'any' && t.dollars > 0)
  const mixMax = Math.max(...mix.map((t) => t.dollars), 1)
  const bandMax = Math.max(...data.size_bands.map((b) => b.dollars), 1)
  const activeYears = [f.active_2023 && 2023, f.active_2024 && 2024]
    .filter(Boolean) as number[]

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-4 gap-2">
        <Stat label="Paid 2023–24" value={money(f.paid_2324)} />
        <Stat label="Grants" value={f.grant_count_2324.toLocaleString()} />
        <Stat label="Recipients" value={f.recipient_count.toLocaleString()} />
        <Stat label="Median grant" value={money(f.median_grant)}
          hint="Half of grants were larger" />
        <Stat label="Christian giving" value={money(f.christian_dollars)}
          hint={f.pct_christian === null
            ? 'nothing classifiable'
            : `${f.pct_christian}% of classified`} />
        <Stat label="International" value={money(f.foreign_dollars)}
          hint={f.foreign_country_count > 0
            ? `${f.foreign_country_count} countries`
            : 'domestic only'} />
        <Stat label="Assets" value={money(f.assets)} />
        <Stat label="Revenue" value={money(f.revenue)} />
      </div>

      <div>
        <SectionTitle note="Where this foundation's classified dollars went.
          Unclassified giving is money we could not attribute a character to —
          it is not evidence of anything, in either direction.">
          What it funds
        </SectionTitle>
        {mix.length ? (
          <div className="space-y-1.5 max-w-xl">
            {mix.map((t) => (
              <BarRow key={t.tradition} label={traditionLabel(t.tradition)}
                dollars={t.dollars} max={mixMax}
                sub={`${t.recipients.toLocaleString()} orgs`} />
            ))}
          </div>
        ) : <Empty>No classified giving to break down.</Empty>}
      </div>

      {/* Sits directly under the faith mix: the question it answers is the
          one the faith mix provokes. */}
      <SectorBreakdown sectors={data.sectors ?? []} />

      {/* Renders nothing when there are no hits, so it costs no space on the
          domestic funders that are most of the database. */}
      <BenchmarkHits hits={data.benchmarks ?? []} />

      <div>
        <SectionTitle note="What a realistic ask looks like. The tallest bar is
          where most of the money actually moves, which is often not where most
          of the grants are.">
          Grant sizes
        </SectionTitle>
        {data.size_bands.length ? (
          <div className="space-y-1.5 max-w-xl">
            {data.size_bands.map((b) => (
              <BarRow key={b.band} label={b.band} dollars={b.dollars}
                max={bandMax}
                sub={`${b.grants.toLocaleString()} ${b.grants === 1 ? 'grant' : 'grants'}`} />
            ))}
          </div>
        ) : <Empty>No grant amounts recorded.</Empty>}
      </div>

      <div>
        <SectionTitle note={activeYears.length === 1
          ? `Filed giving in ${activeYears[0]} only. A single year may mean a`
            + ' new foundation, a wind-down, or simply that the other year’s'
            + ' return has not been published yet — not necessarily that'
            + ' giving stopped.'
          : 'Two comparable years. A steep change is worth understanding'
            + ' before you build a strategy on the larger one.'}>
          By year
        </SectionTitle>
        {years.length ? (
          <table className="text-sm">
            <thead>
              <tr className="text-left text-xs text-muted border-b border-line">
                <th className="py-1.5 pr-8">Tax year</th>
                <th className="pr-8 text-right">Paid</th>
                <th className="pr-8 text-right">Grants</th>
                <th className="text-right">Recipients</th>
              </tr>
            </thead>
            <tbody>
              {years.map((y) => (
                <tr key={y.tax_year} className="border-b border-line/60">
                  <td className="py-1.5 pr-8 font-medium">{y.tax_year}</td>
                  <td className="pr-8 text-right tabular">{money(y.dollars)}</td>
                  <td className="pr-8 text-right tabular text-muted">
                    {y.grants.toLocaleString()}
                  </td>
                  <td className="text-right tabular text-muted">
                    {y.recipients.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <Empty>No yearly detail.</Empty>}
      </div>
    </div>
  )
}
