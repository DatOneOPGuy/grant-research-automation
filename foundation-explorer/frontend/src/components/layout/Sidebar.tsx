import { NavLink } from 'react-router-dom'
import {
  BarChart3, Building2, DollarSign, Home, ShieldCheck, Users,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../../lib/api'
import { num } from '../../lib/format'

const NAV = [
  { to: '/', label: 'Dashboard', icon: Home },
  { to: '/foundations', label: 'Foundations', icon: Building2 },
  { to: '/grants', label: 'Grants', icon: DollarSign },
  { to: '/recipients', label: 'Recipients', icon: Users },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/data-quality', label: 'Data Quality', icon: ShieldCheck },
]

export default function Sidebar() {
  const { data } = useQuery({
    queryKey: ['stats'],
    queryFn: () => apiGet<Record<string, number>>('/api/foundations/stats'),
    staleTime: Infinity,
  })
  return (
    <aside className="w-60 shrink-0 h-screen sticky top-0 bg-primary text-white flex flex-col">
      <div className="px-5 py-6">
        <div className="font-display text-xl font-semibold">
          Foundation Explorer
        </div>
        <div className="text-xs text-white/50 mt-1">
          Christian Foundation Database
        </div>
      </div>
      <nav className="flex-1 px-3 space-y-1">
        {NAV.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                isActive
                  ? 'bg-white/10 text-accent font-medium'
                  : 'text-white/70 hover:bg-white/5 hover:text-white'
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="px-5 py-4 text-[11px] leading-4 text-white/40 border-t border-white/10">
        {data
          ? `${num(data.total)} foundations · ${num(data.total_grants)} grants`
          : 'Loading…'}
      </div>
    </aside>
  )
}
