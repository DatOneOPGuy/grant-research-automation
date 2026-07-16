import { NavLink } from 'react-router-dom'
import {
  BarChart3, Bookmark, Building2, DollarSign, Home, ShieldCheck, Target,
  Users, BadgeInfo,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { fetchStatsV5 } from '../../lib/apiV5'
import { useSavedFoundations } from '../../lib/savedContext'
import { num } from '../../lib/format'

const NAV = [
  { to: '/', label: 'Dashboard', icon: Home },
  { to: '/best-prospects', label: 'Best Prospects', icon: Target },
  { to: '/foundations', label: 'Foundations', icon: Building2 },
  { to: '/saved', label: 'Saved', icon: Bookmark, badge: true },
  { to: '/grants', label: 'Grants', icon: DollarSign },
  { to: '/recipients', label: 'Recipients', icon: Users },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/data-quality', label: 'Data Quality', icon: ShieldCheck },
  { to: '/trust', label: 'Trust & Data', icon: BadgeInfo },
]

export default function Sidebar() {
  const { saved } = useSavedFoundations()
  const { data } = useQuery({
    queryKey: ['v5stats'],
    queryFn: fetchStatsV5,
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
        {NAV.map(({ to, label, icon: Icon, badge }) => (
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
            {badge && saved.length > 0 && (
              <span className="ml-auto text-xs bg-accent text-primary rounded-full px-1.5 py-0.5 font-medium">
                {saved.length}
              </span>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="px-5 py-4 text-[11px] leading-4 text-white/40 border-t border-white/10">
        {data
          ? `${num(data.foundations)} foundations · ${num(data.recipients)} recipients`
          : 'Loading…'}
      </div>
    </aside>
  )
}
