import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Languages, Network, Quote, Search } from 'lucide-react'
import { loginRequest } from '../api'
import { useAuth } from '../auth/AuthContext'
import { Button } from '../components/ui'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const token = await loginRequest(email, password)
      login(token, email)
      navigate('/app')
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title="Sign in" subtitle="Access your knowledge workspace.">
      <form onSubmit={submit} className="space-y-4">
        <Field label="Email" type="email" value={email} onChange={setEmail} />
        <Field label="Password" type="password" value={password} onChange={setPassword} />
        <AuthError error={error} />
        <Button type="submit" variant="primary" loading={busy} className="w-full">
          {busy ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>
      <p className="mt-5 text-center text-sm text-muted">
        No account?{' '}
        <Link to="/register" className="font-medium text-accent hover:underline">
          Create one
        </Link>
      </p>
    </AuthShell>
  )
}

const FEATURES = [
  { icon: Network, text: 'Knowledge graph of entities & relationships' },
  { icon: Search, text: 'Hybrid retrieval — vector + keyword + graph' },
  { icon: Quote, text: 'Grounded answers with citations' },
  { icon: Languages, text: 'Multilingual — ask in your language' },
]

export function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: string
  children: ReactNode
}) {
  return (
    <div className="app-backdrop grid min-h-full lg:grid-cols-2">
      {/* Brand showcase */}
      <div className="relative hidden flex-col justify-between overflow-hidden border-r border-border p-12 lg:flex">
        <div className="grid-dots pointer-events-none absolute inset-0 opacity-50" />
        <div
          className="pointer-events-none absolute inset-0"
          style={{ background: 'radial-gradient(600px 400px at 20% 15%, rgba(34,211,238,0.10), transparent 60%)' }}
        />
        <img src="/logo.png" alt="DIRIS — Data. Insight. Relationships." className="relative w-72" />
        <div className="relative max-w-md space-y-7">
          <h2 className="font-display text-[32px] font-semibold leading-[1.15] tracking-tight text-ink">
            Turn documents into a queryable web of knowledge.
          </h2>
          <ul className="space-y-3.5">
            {FEATURES.map((f) => {
              const Icon = f.icon
              return (
                <li key={f.text} className="flex items-center gap-3 text-sm text-muted">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-elevated text-accent">
                    <Icon size={16} />
                  </span>
                  {f.text}
                </li>
              )
            })}
          </ul>
        </div>
        <div className="relative font-mono text-[11px] uppercase tracking-[0.22em] text-faint">
          Data · Insight · Relationships
        </div>
      </div>

      {/* Form */}
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm rise">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <img src="/mark.png" alt="DIRIS" className="h-10 w-10 rounded-xl ring-1 ring-border" />
            <span className="font-display text-xl font-bold text-ink">DIRIS</span>
          </div>
          <h1 className="font-display text-[26px] font-semibold tracking-tight text-ink">{title}</h1>
          {subtitle && <p className="mt-1.5 text-sm text-muted">{subtitle}</p>}
          <div className="mt-7">{children}</div>
        </div>
      </div>
    </div>
  )
}

export function Field({
  label,
  type,
  value,
  onChange,
}: {
  label: string
  type: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13px] font-medium text-muted">{label}</span>
      <input
        type={type}
        value={value}
        required
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-border bg-elevated px-3.5 py-2.5 text-sm text-ink outline-none transition-colors placeholder:text-faint focus:border-[color-mix(in_srgb,var(--color-cyan)_55%,transparent)] focus:ring-2 focus:ring-[rgba(34,211,238,0.14)]"
      />
    </label>
  )
}

export function AuthError({ error }: { error: string }) {
  if (!error) return null
  return (
    <p className="rounded-lg border border-[rgba(251,113,133,0.28)] bg-[rgba(251,113,133,0.08)] px-3 py-2 text-sm text-bad">
      {error}
    </p>
  )
}
