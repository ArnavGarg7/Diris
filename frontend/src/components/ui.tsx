import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Loader2 } from 'lucide-react'

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ')
}

/* ----------------------------------------------------------------- Button */
type Variant = 'primary' | 'subtle' | 'ghost' | 'danger'
type Size = 'sm' | 'md'

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-accent text-[#04121a] font-semibold hover:brightness-110 shadow-[0_6px_20px_-8px_rgba(34,211,238,0.6)]',
  subtle: 'bg-elevated text-ink border border-border hover:bg-hover hover:border-border-strong',
  ghost: 'text-muted hover:text-ink hover:bg-hover',
  danger: 'text-bad border border-[rgba(251,113,133,0.28)] hover:bg-[rgba(251,113,133,0.1)]',
}
const SIZES: Record<Size, string> = {
  sm: 'h-8 px-3 text-[13px]',
  md: 'h-10 px-4 text-sm',
}

export function Button({
  variant = 'subtle',
  size = 'md',
  loading,
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size; loading?: boolean }) {
  return (
    <button
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-lg transition-all focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      disabled={loading || rest.disabled}
      {...rest}
    >
      {loading && <Loader2 size={15} className="animate-spin" />}
      {children}
    </button>
  )
}

export function IconButton({
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cx(
        'inline-flex h-9 w-9 items-center justify-center rounded-lg text-muted transition-colors hover:bg-hover hover:text-ink focus-visible:outline-none',
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  )
}

/* ------------------------------------------------------------------ Panel */
export function Panel({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cx('rounded-2xl border border-border bg-panel', className)}>{children}</div>
  )
}

/* ------------------------------------------------------------ SectionLabel */
export function SectionLabel({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <span className={cx('font-mono text-[11px] uppercase tracking-[0.18em] text-faint', className)}>
      {children}
    </span>
  )
}

/* ------------------------------------------------------------------- Chip */
// Generic pill. Pass `color` (hex) for entity-typed / colored chips.
export function Chip({
  children,
  color,
  className,
}: {
  children: ReactNode
  color?: string
  className?: string
}) {
  const style = color
    ? { color, background: `${color}1a`, borderColor: `${color}33` }
    : undefined
  return (
    <span
      style={style}
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium',
        !color && 'border-border bg-elevated text-muted',
        className,
      )}
    >
      {children}
    </span>
  )
}

/* -------------------------------------------------------------- EmptyState */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-panel/40 px-8 py-16 text-center">
      {icon && (
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-elevated text-accent">
          {icon}
        </div>
      )}
      <h3 className="font-display text-base font-semibold text-ink">{title}</h3>
      {description && <p className="mt-1.5 max-w-sm text-sm text-muted">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

/* ---------------------------------------------------------------- Spinner */
export function Spinner({ size = 18, className }: { size?: number; className?: string }) {
  return <Loader2 size={size} className={cx('animate-spin text-accent', className)} />
}

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 rounded-2xl border border-border bg-panel py-16 text-sm text-muted">
      <Spinner />
      {label}
    </div>
  )
}

/* --------------------------------------------------------------- Page shell */
// Scrolling reading page (Documents / Search / Entities). Graph & Chat use
// their own full-height layouts instead.
export function Page({ children }: { children: ReactNode }) {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl px-5 py-7 md:px-8 md:py-9">{children}</div>
    </div>
  )
}

/* ------------------------------------------------------------ PageHeader */
export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string
  subtitle?: string
  actions?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="font-display text-[26px] font-semibold leading-tight tracking-tight text-ink">
          {title}
        </h1>
        {subtitle && <p className="mt-1.5 max-w-2xl text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  )
}

/* ------------------------------------------------------------- MetricCard */
export function MetricCard({
  label,
  value,
  icon,
  accent = '#22d3ee',
  hint,
}: {
  label: string
  value: ReactNode
  icon?: ReactNode
  accent?: string
  hint?: string
}) {
  return (
    <div className="rounded-xl border border-border bg-panel p-4">
      <div className="flex items-center justify-between">
        <SectionLabel>{label}</SectionLabel>
        {icon && (
          <span className="flex h-7 w-7 items-center justify-center rounded-lg" style={{ background: `${accent}14`, color: accent }}>
            {icon}
          </span>
        )}
      </div>
      <div className="mt-2 font-display text-[28px] font-semibold leading-none tabular-nums text-ink">{value}</div>
      {hint && <div className="mt-1.5 text-[11px] text-faint">{hint}</div>}
    </div>
  )
}

/* --------------------------------------------------------------- Skeleton */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cx('animate-pulse rounded-md bg-elevated', className)} />
}

/* ------------------------------------------------------------------- Kbd */
export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded border border-border-strong bg-elevated px-1.5 py-0.5 font-mono text-[11px] text-muted">
      {children}
    </kbd>
  )
}
