import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BookOpen, Box, Building2, Calendar, CalendarClock, Circle, Cpu, Hash,
  Lightbulb, MapPin, Network, Search, Tags, User, X,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { api } from '../api'
import { entityColor } from '../lib/entities'
import { Chip, EmptyState, IconButton, LoadingState, Page, PageHeader, SectionLabel } from '../components/ui'
import type { EntityDetail, EntityOut } from '../types'

const ICONS: Record<string, LucideIcon> = {
  PERSON: User, ORGANIZATION: Building2, LOCATION: MapPin, EVENT: CalendarClock,
  CONCEPT: Lightbulb, TECHNOLOGY: Cpu, OBJECT: Box, TOPIC: Hash, WORK: BookOpen, DATE: Calendar,
}
const iconFor = (t: string): LucideIcon => ICONS[t?.toUpperCase()] ?? Circle

export default function Entities() {
  const [entities, setEntities] = useState<EntityOut[] | null>(null)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState<string | null>(null)
  const [selected, setSelected] = useState<EntityDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  useEffect(() => {
    api.get<EntityOut[]>('/entities').then(setEntities).catch((e) => setError((e as Error).message))
  }, [])

  const nameById = useMemo(() => {
    const m = new Map<number, string>()
    entities?.forEach((e) => m.set(e.id, e.canonical_name))
    return m
  }, [entities])

  const types = useMemo(() => [...new Set(entities?.map((e) => e.type) ?? [])].sort(), [entities])

  const shown = useMemo(() => {
    const f = filter.trim().toLowerCase()
    return (entities ?? []).filter(
      (e) =>
        (!typeFilter || e.type === typeFilter) &&
        (!f || e.canonical_name.toLowerCase().includes(f) || e.aliases.some((a) => a.toLowerCase().includes(f))),
    )
  }, [entities, filter, typeFilter])

  async function open(e: EntityOut) {
    setLoadingDetail(true)
    setSelected(null)
    try {
      setSelected(await api.get<EntityDetail>(`/entities/${e.id}`))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoadingDetail(false)
    }
  }

  return (
    <Page>
      <PageHeader
        title="Entities"
        subtitle="Every entity DIRIS resolved across your documents — filter, inspect, and trace its relationships."
      />

      {/* Toolbar */}
      <div className="flex flex-col gap-3">
        <div className="relative max-w-sm">
          <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter by name or alias…"
            className="w-full rounded-lg border border-border bg-panel py-2 pl-9 pr-3 text-sm text-ink outline-none placeholder:text-faint focus:border-[color-mix(in_srgb,var(--color-cyan)_55%,transparent)] focus:ring-2 focus:ring-[rgba(34,211,238,0.14)]"
          />
        </div>
        <div className="flex flex-wrap gap-1.5">
          <TypeButton active={!typeFilter} onClick={() => setTypeFilter(null)}>All</TypeButton>
          {types.map((t) => (
            <TypeButton
              key={t}
              active={t === typeFilter}
              color={entityColor(t)}
              onClick={() => setTypeFilter(t === typeFilter ? null : t)}
            >
              {t}
            </TypeButton>
          ))}
        </div>
      </div>

      {error && <p className="mt-4 text-sm text-bad">{error}</p>}

      <div className="mt-5">
        {entities === null ? (
          <LoadingState label="Loading entities…" />
        ) : shown.length === 0 ? (
          <EmptyState
            icon={<Tags size={22} />}
            title={entities.length === 0 ? 'No entities yet' : 'No entities match your filter'}
            description={entities.length === 0 ? 'Upload and process documents to extract entities and relationships.' : undefined}
          />
        ) : (
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {shown.map((e) => {
              const color = entityColor(e.type)
              const Icon = iconFor(e.type)
              return (
                <button
                  key={e.id}
                  onClick={() => open(e)}
                  className="group flex flex-col rounded-xl border border-border bg-panel p-3.5 text-left transition-all hover:border-border-strong hover:bg-elevated"
                >
                  <div className="flex items-start gap-2.5">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg" style={{ background: `${color}14`, color }}>
                      <Icon size={16} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-medium text-ink" title={e.canonical_name}>{e.canonical_name}</div>
                      <Chip color={color} className="mt-1">{e.type}</Chip>
                    </div>
                  </div>
                  {e.description && <p className="mt-2.5 line-clamp-2 text-[12px] leading-relaxed text-muted">{e.description}</p>}
                  <div className="mt-2.5 flex items-center gap-3 font-mono text-[10px] text-faint">
                    <span>{e.mention_count} mention{e.mention_count === 1 ? '' : 's'}</span>
                    {e.aliases.length > 0 && <span>{e.aliases.length} alias{e.aliases.length === 1 ? '' : 'es'}</span>}
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </div>

      {(selected || loadingDetail) && (
        <div className="fixed inset-0 z-40 flex justify-end bg-black/60 backdrop-blur-sm" onClick={() => setSelected(null)}>
          <div className="h-full w-full max-w-md overflow-y-auto border-l border-border bg-panel shadow-2xl" onClick={(ev) => ev.stopPropagation()}>
            {loadingDetail && <div className="p-6"><LoadingState label="Loading entity…" /></div>}
            {selected && <Inspector e={selected} nameById={nameById} onClose={() => setSelected(null)} />}
          </div>
        </div>
      )}
    </Page>
  )
}

function TypeButton({
  children, active, color, onClick,
}: {
  children: React.ReactNode
  active: boolean
  color?: string
  onClick: () => void
}) {
  const style = active && color ? { color, background: `${color}1f`, borderColor: `${color}55` } : undefined
  return (
    <button
      onClick={onClick}
      style={style}
      className={
        active
          ? `rounded-full border px-3 py-1 text-xs font-medium ${color ? '' : 'border-accent/50 bg-[rgba(34,211,238,0.12)] text-accent'}`
          : 'rounded-full border border-border bg-elevated px-3 py-1 text-xs font-medium text-muted hover:border-border-strong hover:text-ink'
      }
    >
      {children}
    </button>
  )
}

function Inspector({
  e, nameById, onClose,
}: {
  e: EntityDetail
  nameById: Map<number, string>
  onClose: () => void
}) {
  const color = entityColor(e.type)
  const Icon = iconFor(e.type)
  return (
    <>
      <div className="flex items-start justify-between gap-3 border-b border-border p-5">
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" style={{ background: `${color}14`, color }}>
            <Icon size={20} />
          </span>
          <div>
            <h2 className="font-display text-lg font-semibold text-ink">{e.canonical_name}</h2>
            <Chip color={color} className="mt-1">{e.type}</Chip>
          </div>
        </div>
        <IconButton onClick={onClose}><X size={16} /></IconButton>
      </div>

      <div className="space-y-6 p-5">
        <Link
          to={`/app/graph?focus=${e.id}`}
          className="flex items-center justify-center gap-2 rounded-lg border border-border bg-elevated py-2 text-sm font-medium text-ink transition-colors hover:border-accent/50 hover:text-accent"
        >
          <Network size={15} /> Focus in knowledge graph
        </Link>

        {e.description && <p className="text-sm leading-relaxed text-muted">{e.description}</p>}

        <div className="flex gap-2">
          <Stat label="Mentions" value={e.mention_count} />
          <Stat label="Aliases" value={e.aliases.length} />
          <Stat label="Relationships" value={e.relationships.length} />
        </div>

        {e.aliases.length > 0 && (
          <div>
            <SectionLabel>Also known as</SectionLabel>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {e.aliases.map((a) => <Chip key={a}>{a}</Chip>)}
            </div>
          </div>
        )}

        <div>
          <SectionLabel>Relationships</SectionLabel>
          {e.relationships.length === 0 ? (
            <p className="mt-2 text-sm text-faint">No relationships extracted.</p>
          ) : (
            <ul className="mt-2 space-y-1.5">
              {e.relationships.map((r) => {
                const out = r.source_entity_id === e.id
                const otherId = out ? r.target_entity_id : r.source_entity_id
                const other = nameById.get(otherId) ?? `#${otherId}`
                return (
                  <li key={r.id} className="rounded-lg border border-border bg-elevated p-2.5">
                    <div className="flex items-center gap-1.5 text-sm">
                      <span className="text-faint">{out ? '→' : '←'}</span>
                      <span className="font-medium text-accent">{r.type}</span>
                      <span className="min-w-0 truncate text-ink">{other}</span>
                    </div>
                    {r.evidence && <p className="mt-1 text-[11px] italic leading-relaxed text-faint">“{r.evidence}”</p>}
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex-1 rounded-lg border border-border bg-elevated px-3 py-2.5 text-center">
      <div className="font-display text-xl font-semibold text-ink">{value}</div>
      <div className="font-mono text-[10px] uppercase tracking-wider text-faint">{label}</div>
    </div>
  )
}
