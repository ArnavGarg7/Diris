import { CheckCircle2, Clock, Loader2, XCircle } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

type Meta = { label: string; cls: string; Icon: LucideIcon; spin?: boolean }

const MAP: Record<string, Meta> = {
  uploaded: { label: 'Queued', cls: 'text-muted border-border bg-elevated', Icon: Clock },
  processing: {
    label: 'Processing',
    cls: 'text-cyan border-[rgba(34,211,238,0.3)] bg-[rgba(34,211,238,0.08)]',
    Icon: Loader2,
    spin: true,
  },
  done: {
    label: 'Ready',
    cls: 'text-good border-[rgba(52,211,153,0.3)] bg-[rgba(52,211,153,0.08)]',
    Icon: CheckCircle2,
  },
  failed: {
    label: 'Failed',
    cls: 'text-bad border-[rgba(251,113,133,0.3)] bg-[rgba(251,113,133,0.08)]',
    Icon: XCircle,
  },
}

export default function StatusBadge({ status }: { status: string }) {
  const m = MAP[status] ?? MAP.uploaded
  const { Icon } = m
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${m.cls}`}
    >
      <Icon size={12} className={m.spin ? 'animate-spin' : ''} />
      {m.label}
    </span>
  )
}
