// Individual grant rows, largest first. Paged rather than capped so a large
// funder's tail is reachable without loading 30,000 rows up front.
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchFoundationGrantsV5, type GrantRowV5 } from '../../../lib/apiV5'
import { money, moneyFull, titleCase } from '../../../lib/format'
import { Skeleton } from '../../ui/primitives'
import { IdentityChip, TraditionChip } from '../V5Chips'

const PAGE = 100

export default function GrantsTab({ ein }: { ein: string }) {
  const [limit, setLimit] = useState(PAGE)
  const { data } = useQuery({
    queryKey: ['v5grants', ein, limit],
    queryFn: () => fetchFoundationGrantsV5(ein, limit, 0),
  })
  if (!data) return <Skeleton className="h-40" />
  const shown = data.rows as GrantRowV5[]
  const total = shown.reduce((sum, g) => sum + g.amount, 0)
  return (
    <div>
      <p className="text-[11px] text-muted mb-2">
        {shown.length.toLocaleString()} largest grants shown,{' '}
        {money(total)} combined. Purpose text is the funder’s own wording.
      </p>
      <table className="w-full text-sm min-w-[520px]">
        <thead>
          <tr className="text-left text-xs text-muted border-b border-line">
            <th className="py-2">Recipient</th>
            <th>Location</th>
            <th className="text-right">Amount</th>
            <th>Year</th>
            <th>Purpose</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((g, i) => (
            <tr key={i} className="border-b border-line/60">
              <td className="py-2 pr-3 font-medium">
                {titleCase(g.recipient_name)}
                {g.tradition && <span className="ml-1.5">
                  <TraditionChip tradition={g.tradition} /></span>}
                {g.identity_status && g.identity_status !== 'matched' && (
                  <span className="ml-1">
                    <IdentityChip status={g.identity_status} /></span>
                )}
              </td>
              <td className="pr-3 text-muted whitespace-nowrap">
                {g.country_name && g.is_foreign ? (
                  <>
                    {g.recipient_city && `${titleCase(g.recipient_city)}, `}
                    <span className="text-primary">{g.country_name}</span>
                  </>
                ) : (
                  <>
                    {g.recipient_city && `${titleCase(g.recipient_city)}, `}
                    {g.recipient_state}
                    {g.is_foreign && !g.country_name && (
                      <span className="text-muted italic"> abroad</span>
                    )}
                  </>
                )}
              </td>
              <td className="text-right tabular pr-3 whitespace-nowrap">
                {moneyFull(g.amount)}
              </td>
              <td className="tabular pr-3">{g.tax_year}</td>
              <td className="text-muted max-w-56 truncate"
                title={g.purpose || undefined}>{g.purpose}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {shown.length >= limit && (
        <button onClick={() => setLimit(limit + PAGE)}
          className="text-sm text-primary mt-3 hover:underline">
          Load more grants
        </button>
      )}
    </div>
  )
}
