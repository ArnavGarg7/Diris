import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { FileText, LayoutDashboard, LogOut, Menu, MessageSquare, Network, Search, Tags } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { api } from '../api'
import { cx, SectionLabel } from './ui'

type NavItem = { to: string; label: string; icon: LucideIcon; end?: boolean }
const GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: 'Workspace',
    items: [
      { to: '', label: 'Overview', icon: LayoutDashboard, end: true },
      { to: 'documents', label: 'Documents', icon: FileText },
      { to: 'search', label: 'Search', icon: Search },
      { to: 'chat', label: 'Chat', icon: MessageSquare },
    ],
  },
  {
    label: 'Explore',
    items: [
      { to: 'graph', label: 'Knowledge Graph', icon: Network },
      { to: 'entities', label: 'Entities', icon: Tags },
    ],
  },
]

function SidebarContent({ email, online, onNavigate, onLogout }: {
  email: string | null
  online: boolean
  onNavigate: () => void
  onLogout: () => void
}) {
  return (
    <div className="flex h-full flex-col">
      {/* Brand */}
      <div className="flex items-center gap-3 px-5 pb-5 pt-6">
        <img src="/mark.png" alt="DIRIS" className="h-9 w-9 rounded-xl ring-1 ring-border" />
        <div className="leading-tight">
          <div className="font-display text-[17px] font-bold tracking-wide text-ink">DIRIS</div>
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-faint">
            Knowledge Intelligence
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-5 overflow-y-auto px-3">
        {GROUPS.map((group) => (
          <div key={group.label} className="space-y-1">
            <div className="px-2 pb-1">
              <SectionLabel>{group.label}</SectionLabel>
            </div>
            {group.items.map((n) => {
              const Icon = n.icon
              return (
                <NavLink
                  key={n.to || 'overview'}
                  to={n.to}
                  end={n.end}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    cx(
                      'group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                      isActive
                        ? 'bg-[rgba(34,211,238,0.08)] font-medium text-ink'
                        : 'text-muted hover:bg-hover hover:text-ink',
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      <span
                        className={cx(
                          'absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-accent transition-opacity',
                          isActive ? 'opacity-100' : 'opacity-0',
                        )}
                      />
                      <Icon size={17} className={isActive ? 'text-accent' : 'text-faint group-hover:text-muted'} />
                      {n.label}
                    </>
                  )}
                </NavLink>
              )
            })}
          </div>
        ))}
      </nav>

      {/* Footer: status + user */}
      <div className="mt-2 space-y-3 border-t border-border px-4 py-4">
        <div className="flex items-center gap-2 px-1">
          <span className={cx('h-1.5 w-1.5 rounded-full', online ? 'bg-good pulse-dot' : 'bg-warn')} />
          <span className="text-xs text-muted">{online ? 'All systems online' : 'Reconnecting…'}</span>
        </div>
        <div className="flex items-center gap-2.5 rounded-lg border border-border bg-elevated px-2.5 py-2">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-[rgba(34,211,238,0.12)] font-mono text-xs font-semibold text-accent">
            {(email ?? '?').slice(0, 1).toUpperCase()}
          </div>
          <span className="min-w-0 flex-1 truncate text-xs text-muted" title={email ?? ''}>{email}</span>
          <button
            onClick={onLogout}
            title="Log out"
            aria-label="Log out"
            className="flex h-7 w-7 items-center justify-center rounded-md text-faint transition-colors hover:bg-hover hover:text-bad"
          >
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </div>
  )
}

export default function AppLayout() {
  const { email, logout } = useAuth()
  const navigate = useNavigate()
  const [online, setOnline] = useState(true)
  const [drawer, setDrawer] = useState(false)

  useEffect(() => {
    let alive = true
    const ping = () =>
      api.get('/health').then(() => alive && setOnline(true)).catch(() => alive && setOnline(false))
    ping()
    const id = setInterval(ping, 20000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [])

  function doLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="app-backdrop flex h-full">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 border-r border-border bg-surface/80 backdrop-blur md:block">
        <SidebarContent email={email} online={online} onNavigate={() => {}} onLogout={doLogout} />
      </aside>

      {/* Mobile drawer */}
      {drawer && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setDrawer(false)} />
          <aside className="absolute left-0 top-0 h-full w-64 border-r border-border bg-surface">
            <SidebarContent email={email} online={online} onNavigate={() => setDrawer(false)} onLogout={doLogout} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile top bar */}
        <header className="flex items-center gap-3 border-b border-border bg-surface/80 px-4 py-3 backdrop-blur md:hidden">
          <button onClick={() => setDrawer(true)} aria-label="Open navigation" className="text-muted hover:text-ink">
            <Menu size={20} />
          </button>
          <img src="/mark.png" alt="DIRIS" className="h-7 w-7 rounded-lg ring-1 ring-border" />
          <span className="font-display font-bold text-ink">DIRIS</span>
        </header>

        <main className="min-h-0 flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
