import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  BarChart3, Bookmark, Building2, DollarSign, Home, PanelLeftClose,
  HelpCircle, Landmark, PanelLeftOpen, PieChart, ShieldCheck, Target,
  Users, BadgeInfo, Globe, ExternalLink,
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
  { to: '/nonprofits', label: 'Nonprofits', icon: Landmark },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/non-christian', label: 'Non-Christian', icon: PieChart },
  { to: '/data-quality', label: 'Data Quality', icon: ShieldCheck },
  { to: '/how-to', label: 'How to Filter', icon: HelpCircle },
  { to: '/trust', label: 'Trust & Data', icon: BadgeInfo },
]

// The marketing site, mounted at /website by nginx as a static copy of the
// Next.js build. Not a route in this app, so it cannot be a NavLink -- React
// Router would try to resolve it internally and render the app's 404 instead
// of leaving the SPA.
//
// Opens in a new tab on purpose: a reviewer clicking away and losing their
// filters and saved-folder state would be a poor trade for a link.
const WEBSITE_URL = '/website/'

export default function Sidebar() {
  const { saved } = useSavedFoundations()
  // Collapses to an icon rail rather than disappearing: navigation stays one
  // click away, and the table gets back 144px on a laptop.
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem('fe.navCollapsed') === 'true')
  useEffect(() => {
    localStorage.setItem('fe.navCollapsed', String(collapsed))
  }, [collapsed])

  const { data } = useQuery({
    queryKey: ['v5stats'],
    queryFn: fetchStatsV5,
    staleTime: Infinity,
  })

  return (
    <aside className={`shrink-0 h-screen sticky top-0 bg-primary text-white
      flex flex-col transition-[width] duration-150 ${
        collapsed ? 'w-14' : 'w-52 min-[1800px]:w-60'}`}>
      {!collapsed && (
        // The title owns its row outright. Sharing it with the collapse
        // control truncated "Foundation Explorer" to "Foundation…", which
        // makes the product look broken before a user reads anything else.
        <div className="px-5 py-6">
          <div className="font-display text-xl font-semibold leading-tight">
            Foundation Explorer
          </div>
          <div className="text-xs text-white/50 mt-1">
            Christian Foundation Database
          </div>
        </div>
      )}

      {/* Collapsed, the title block is gone, so the nav needs its own top
          padding or the first icon sits flush against the window edge. */}
      <nav className={`flex-1 space-y-1 ${
        collapsed ? 'px-2 pt-4' : 'px-3'}`}>
        {NAV.map(({ to, label, icon: Icon, badge }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              `flex items-center rounded-md py-2 text-sm transition-colors
               relative ${collapsed ? 'justify-center px-2' : 'gap-3 px-3'} ${
                isActive
                  ? 'bg-white/10 text-accent font-medium'
                  : 'text-white/70 hover:bg-white/5 hover:text-white'
              }`
            }
          >
            <Icon size={16} className="shrink-0" />
            {!collapsed && label}
            {badge && saved.length > 0 && (
              collapsed ? (
                // A dot, because a number would not fit and an unread count
                // still needs to be visible from the rail.
                <span className="absolute top-1 right-1 w-2 h-2 rounded-full
                  bg-accent" />
              ) : (
                <span className="ml-auto text-xs bg-accent text-primary
                  rounded-full px-1.5 py-0.5 font-medium">
                  {saved.length}
                </span>
              )
            )}
          </NavLink>
        ))}
        {/* Sits below the app's own pages, separated, because it leaves the
            product rather than navigating within it. */}
        <a
          href={WEBSITE_URL}
          target="_blank"
          rel="noreferrer"
          title={collapsed ? 'Website (opens in a new tab)' : undefined}
          className={`mt-2 pt-2 border-t border-white/10 flex items-center
            rounded-md py-2 text-sm transition-colors text-white/70
            hover:bg-white/5 hover:text-white ${
              collapsed ? 'justify-center px-2' : 'gap-3 px-3'}`}
        >
          <Globe size={16} className="shrink-0" />
          {!collapsed && (
            <>
              Website
              <ExternalLink size={12} className="ml-auto opacity-50" />
            </>
          )}
        </a>
      </nav>

      <div className={`border-t border-white/10 flex items-center gap-2 ${
        collapsed ? 'px-2 py-3 justify-center' : 'px-5 py-3'}`}>
        {!collapsed && (
          <div className="text-[11px] leading-4 text-white/40 flex-1 min-w-0">
            {data
              ? `${num(data.foundations)} foundations · ${num(data.recipients)} recipients`
              : 'Loading…'}
          </div>
        )}
        <button
          onClick={() => setCollapsed((c) => !c)}
          title={collapsed ? 'Expand menu' : 'Collapse menu'}
          aria-label={collapsed ? 'Expand menu' : 'Collapse menu'}
          className="p-1.5 rounded text-white/50 hover:text-white
            hover:bg-white/10 shrink-0 focus:outline-none focus-visible:ring-2
            focus-visible:ring-accent/70">
          {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
        </button>
      </div>
    </aside>
  )
}
