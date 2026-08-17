// International giving. Only rendered when there is any, so the tab's presence
// is itself a signal.
import { methodLabel, type FoundationDetailV5 } from '../../../lib/apiV5'
import { money, titleCase } from '../../../lib/format'
import { TraditionChip } from '../V5Chips'
import { BarRow, Empty, SectionTitle, Stat } from './parts'

export default function InternationalTab({ data }: {
  data: FoundationDetailV5
}) {
  const f = data.foundation
  const named = data.countries.filter((c) => c.country_code !== '(unspecified)')
  const unplaced = data.countries.find(
    (c) => c.country_code === '(unspecified)')
  const max = Math.max(...data.countries.map((c) => c.dollars), 1)

  if (!data.countries.length) {
    return <Empty>
      No grants left the United States in 2023–24, according to the filing.
    </Empty>
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-4 gap-2">
        <Stat label="Sent abroad" value={money(f.foreign_dollars)}
          hint={f.pct_foreign !== null
            ? `${f.pct_foreign}% of all giving` : undefined} />
        <Stat label="Christian abroad"
          value={money(f.foreign_christian_dollars)} />
        <Stat label="Countries" value={named.length.toLocaleString()} />
        <Stat label="Grants abroad"
          value={f.foreign_grant_count.toLocaleString()} />
      </div>

      <div>
        <SectionTitle note="Destinations as coded on the 990-PF. The IRS uses
          FIPS country codes rather than ISO, which invert some countries
          outright, so every code here was verified against the recipient city
          text in the same filing.">
          Where the money went
        </SectionTitle>
        <div className="space-y-1.5 max-w-xl">
          {data.countries.map((c) => (
            <BarRow key={c.country_code} label={c.country_name}
              dollars={c.dollars} christian={c.christian_dollars} max={max}
              title={`${c.country_name} (${c.country_code})`}
              sub={`${c.grants.toLocaleString()} ${c.grants === 1 ? 'grant' : 'grants'}`} />
          ))}
        </div>
        <p className="text-[11px] text-muted mt-2 max-w-xl leading-snug">
          The darker segment is giving to organizations we classify as
          Christian.
          {unplaced && ` ${money(unplaced.dollars)} could not be placed to a`
            + ' country: the filing gave a code we could not verify. It is'
            + ' shown here rather than dropped, so the total reconciles.'}
        </p>
      </div>

      <div>
        <SectionTitle note="Ranked by dollars received. Where a recipient could
          not be matched to an organization, the filing gave only a name and a
          city — common for overseas grantees, who have no US IRS record.">
          Overseas recipients
        </SectionTitle>
        {data.top_foreign.length ? (
          <table className="w-full text-sm min-w-[520px]">
            <thead>
              <tr className="text-left text-xs text-muted border-b border-line">
                <th className="py-1.5">Recipient</th>
                <th>Country</th>
                <th>Basis</th>
                <th className="text-right">Dollars</th>
                <th className="text-right pl-3">Grants</th>
              </tr>
            </thead>
            <tbody>
              {data.top_foreign.map((r, i) => (
                <tr key={i} className="border-b border-line/60">
                  <td className="py-1.5 pr-3">
                    <span className="font-medium">{titleCase(r.name)}</span>
                    {r.tradition && (
                      <span className="ml-1.5">
                        <TraditionChip tradition={r.tradition} />
                      </span>
                    )}
                    {r.recipient_city && (
                      <div className="text-[11px] text-muted">
                        {titleCase(r.recipient_city)}
                      </div>
                    )}
                  </td>
                  <td className="pr-3 text-muted whitespace-nowrap">
                    {r.country_name || (
                      <span title={`Filing code “${r.recipient_country}” could`
                        + ' not be verified'}>Unspecified</span>
                    )}
                  </td>
                  <td className="pr-3 text-muted text-xs">
                    {r.tradition ? methodLabel(r.method) : '—'}
                  </td>
                  <td className="text-right tabular font-medium whitespace-nowrap">
                    {money(r.dollars)}
                  </td>
                  <td className="text-right tabular text-muted pl-3">
                    {r.grants}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <Empty>No itemized overseas recipients.</Empty>}
      </div>
    </div>
  )
}
