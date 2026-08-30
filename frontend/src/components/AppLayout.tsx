import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

const NAV = [
  { to: 'documents', label: 'Documents', icon: '📄' },
  { to: 'chat', label: 'Chat', icon: '💬' },
  { to: 'graph', label: 'Graph', icon: '🕸️' },
  { to: 'search', label: 'Search', icon: '🔍' },
  { to: 'entities', label: 'Entities', icon: '🔖' },
]

export default function AppLayout() {
  const { email, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <div className="flex h-full bg-slate-50">
      <aside className="flex w-56 flex-col border-r border-slate-200 bg-white">
        <div className="flex items-center gap-2 px-5 py-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 font-bold text-white">D</div>
          <span className="font-semibold text-slate-800">DIRIS</span>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${
                  isActive ? 'bg-indigo-50 font-medium text-indigo-700' : 'text-slate-600 hover:bg-slate-100'
                }`
              }
            >
              <span>{n.icon}</span>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-3 text-xs text-slate-400">v0.1 · phased build</div>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <span className="text-sm text-slate-500">Your knowledge base</span>
          <div className="flex items-center gap-3">
            <span className="text-sm text-slate-600">{email}</span>
            <button
              onClick={() => {
                logout()
                navigate('/login')
              }}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100"
            >
              Log out
            </button>
          </div>
        </header>
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
