import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight, FileText, MessageSquare, Network, Search, Tags, Upload, Waypoints,
} from 'lucide-react'
import { api } from '../api'
import StatusBadge from '../components/StatusBadge'
import { Button, EmptyState, MetricCard, Page, PageHeader, Panel, SectionLabel, Skeleton } from '../components/ui'
import { fmtDate, type ChunkOut, type DocumentOut, type EntityOut, type GraphOut } from '../types'

const PIPELINE = [
  { icon: FileText, label: 'Documents' },
  { icon: Tags, label: 'Entities' },
  { icon: Network, label: 'Graph' },
  { icon: Search, label: 'Hybrid retrieval' },
  { icon: MessageSquare, label: 'Grounded answers' },
]

const ACTIONS = [
  { to: '/app/documents', icon: Upload, title: 'Upload a document', desc: 'Add a source to your knowledge base', accent: '#22d3ee' },
  { to: '/app/chat', icon: MessageSquare, title: 'Ask a question', desc: 'Grounded answers with evidence', accent: '#8b5cf6' },
  { to: '/app/search', icon: Search, title: 'Search knowledge', desc: 'Semantic + keyword + graph', accent: '#fbbf24' },
  { to: '/app/graph', icon: Waypoints, title: 'Explore the graph', desc: 'Entities and relationships', accent: '#34d399' },
]

export default function Dashboard() {
  const navigate = useNavigate()
  const [docs, setDocs] = useState<DocumentOut[] | null>(null)
  const [entities, setEntities] = useState<number | null>(null)
  const [relationships, setRelationships] = useState<number | null>(null)
  const [chunks, setChunks] = useState<number | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    api.get<DocumentOut[]>('/documents').then((d) => alive && setDocs(d)).catch((e) => alive && setError((e as Error).message))
    api.get<EntityOut[]>('/entities').then((e) => alive && setEntities(e.length)).catch(() => {})
    api.get<GraphOut>('/graph?limit=500').then((g) => alive && setRelationships(g.edges.length)).catch(() => {})
    return () => { alive = false }
  }, [])

  // Total chunks = sum across ready documents (only count-available source).
  useEffect(() => {
    if (!docs) return
    const ready = docs.filter((d) => d.status === 'done')
    if (ready.length === 0) { setChunks(0); return }
    let alive = true
    Promise.all(ready.map((d) => api.get<ChunkOut[]>(`/documents/${d.id}/chunks`).then((c) => c.length).catch(() => 0)))
      .then((counts) => alive && setChunks(counts.reduce((a, b) => a + b, 0)))
    return () => { alive = false }
  }, [docs])

  const recent = docs ? [...docs].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5) : []

  return (
    <Page>
      <PageHeader
        title="Your knowledge workspace"
        subtitle="Documents, entities, and relationships — connected into a searchable knowledge graph."
      />

      {/* Pipeline story */}
      <Panel className="mb-6 flex flex-wrap items-center gap-x-2 gap-y-2 px-5 py-3.5">
        {PIPELINE.map((s, i) => {
          const Icon = s.icon
          return (
            <span key={s.label} className="inline-flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 text-[13px] text-muted">
                <Icon size={14} className="text-accent" /> {s.label}
              </span>
              {i < PIPELINE.length - 1 && <ArrowRight size={13} className="text-border-strong" />}
            </span>
          )
        })}
      </Panel>

      {error && <p className="mb-4 text-sm text-bad">{error}</p>}

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard label="Documents" icon={<FileText size={15} />} accent="#22d3ee"
          value={docs ? docs.length : <Skeleton className="h-7 w-12" />} />
        <MetricCard label="Chunks" icon={<Tags size={15} />} accent="#34d399"
          value={chunks != null ? chunks.toLocaleString() : <Skeleton className="h-7 w-16" />} />
        <MetricCard label="Entities" icon={<Waypoints size={15} />} accent="#8b5cf6"
          value={entities != null ? entities.toLocaleString() : <Skeleton className="h-7 w-16" />} />
        <MetricCard label="Relationships" icon={<Network size={15} />} accent="#fbbf24"
          value={relationships != null ? relationships.toLocaleString() : <Skeleton className="h-7 w-16" />}
          hint={relationships != null ? 'in the knowledge graph' : undefined} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        {/* Recent documents */}
        <div className="lg:col-span-2">
          <div className="mb-2.5 flex items-center justify-between">
            <SectionLabel>Recent documents</SectionLabel>
            <Link to="/app/documents" className="text-xs text-accent hover:underline">View all</Link>
          </div>
          {docs === null ? (
            <Panel className="p-4"><Skeleton className="h-24 w-full" /></Panel>
          ) : recent.length === 0 ? (
            <EmptyState icon={<FileText size={22} />} title="No documents yet"
              description="Upload your first document to start building your knowledge graph."
              action={<Button variant="primary" onClick={() => navigate('/app/documents')}><Upload size={16} /> Upload document</Button>} />
          ) : (
            <Panel className="divide-y divide-border overflow-hidden">
              {recent.map((d) => (
                <Link
                  key={d.id}
                  to={`/app/documents/${d.id}`}
                  className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-hover"
                >
                  <FileText size={16} className="shrink-0 text-faint" />
                  <span className="min-w-0 flex-1 truncate text-sm text-ink" title={d.original_filename}>{d.original_filename}</span>
                  <StatusBadge status={d.status} />
                  <span className="hidden w-28 shrink-0 text-right text-[12px] text-faint sm:block">{fmtDate(d.created_at)}</span>
                  <ArrowRight size={14} className="shrink-0 text-faint" />
                </Link>
              ))}
            </Panel>
          )}
        </div>

        {/* Quick actions */}
        <div>
          <div className="mb-2.5"><SectionLabel>Quick actions</SectionLabel></div>
          <div className="space-y-2.5">
            {ACTIONS.map((a) => {
              const Icon = a.icon
              return (
                <Link
                  key={a.to}
                  to={a.to}
                  className="flex items-center gap-3 rounded-xl border border-border bg-panel p-3 transition-all hover:border-border-strong hover:bg-elevated"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" style={{ background: `${a.accent}14`, color: a.accent }}>
                    <Icon size={17} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-ink">{a.title}</span>
                    <span className="block truncate text-[12px] text-faint">{a.desc}</span>
                  </span>
                  <ArrowRight size={15} className="shrink-0 text-faint" />
                </Link>
              )
            })}
          </div>
        </div>
      </div>
    </Page>
  )
}
