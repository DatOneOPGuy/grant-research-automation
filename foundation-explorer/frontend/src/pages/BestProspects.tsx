import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../lib/api'
import { money, num } from '../lib/format'
import Foundations from './Foundations'

export default function BestProspects() {
  const { data: stats } = useQuery({
    queryKey: ['stats'], queryFn: () => apiGet<any>('/api/foundations/stats'),
  })
  return (
    <div>
      <div className="rounded-lg bg-primary text-white p-6 mb-6">
        <div className="font-display text-2xl font-semibold text-accent">
          Best Prospects
        </div>
        <p className="text-white/80 mt-2 max-w-3xl text-sm leading-relaxed">
          Foundations that accept applications (or take a first contact) and
          have given more than $100k to Christian causes over the last three
          years.
          {stats && <> Total addressable: <strong className="text-white">
            {money(stats.best_prospect_dollars)}</strong> across{' '}
            <strong className="text-white">
              {num(stats.best_prospects)}</strong> foundations.</>}
        </p>
      </div>
      <Foundations presetLock="best-prospects" />
    </div>
  )
}
