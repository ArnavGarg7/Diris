import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft, CheckCircle2, Layers, Loader2, Network, Tags, XCircle,
} from 'lucide-react'
import { api } from '../api'
import StatusBadge from '../components/StatusBadge'
import { Button, Chip, EmptyState, LoadingState, MetricCard, Page, Panel, SectionLabel } from '../components/ui'
import { entityColor } from '../lib/entities'
import {
  fmtDate, formatBytes, type ChunkOut, type DocumentOut, type EntityOut, type ProcessingStatusOut,
} from '../types'

// Collapse consecutive same-stage records (e.g. 523 "extracting entities N/M"
// progress rows) into a single milestone showing the final message.
function collapseHistory(history: ProcessingStatusOut[]): ProcessingStatusOut[] {
  const out: ProcessingStatusOut[] = []
  for (const h of history) {
    const prev = out[out.length - 1]
    if (prev && prev.stage === h.stage && prev.status === h.status) out[out.length - 1] = h
    else out.push(h)
  }
  return out
}

export default function DocumentDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [doc, setDoc] = useState<DocumentOut | null>(null)
  const [history, setHistory] = useState<ProcessingStatusOut[]>([])
  const [chunks, setChunks] = useState<ChunkOut[] | null>(null)
  const [entities, setEntities] = useState<EntityOut[] | null>(null)
  const [tab, setTab] = useState<'chunks' | 'entities'>('chunks')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    setLoading(true)
    api.get<DocumentOut>(`/documents/${id}`)
      .then((d) => alive && setDoc(d))
      .catch((e) => alive && setError((e as Error).message))
      .finally(() => alive && setLoading(false))
    api.get<ProcessingStatusOut[]>(`/documents/${id}/status`).then((h) => alive && setHistory(h)).catch(() => {})
    api.get<ChunkOut[]>(`/documents/${id}/chunks`).then((c) => alive && setChunks(c)).catch(() => alive && setChunks([]))
    api.get<EntityOut[]>(`/documents/${id}/entities`).then((e) => alive && setEntities(e)).catch(() => alive && setEntities([]))
    return () => { alive = false }
  }, [id])

  if (loading) return <Page><LoadingState label="Loading document…" /></Page>
  if (error || !doc) {
    return (
      <Page>
        <EmptyState icon={<XCircle size={22} />} title="Couldn't load this document" description={error || 'Not found.'}
          action={<Button variant="primary" onClick={() => navigate('/app/documents')}>Back to documents</Button>} />
      </Page>
    )
  }

  return (
    <Page>
      <Link to="/app/documents" className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
        <ArrowLeft size={15} /> Documents
      </Link>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="font-display text-2xl font-semibold tracking-tight text-ink">{doc.original_filename}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-muted">
            <StatusBadge status={doc.status} />
            <span className="font-mono">{doc.content_type || '—'}</span>
            <span className="font-mono">{formatBytes(doc.size_bytes)}</span>
            <span>Added {fmtDate(doc.created_at)}</span>
          </div>
        </div>
        <Button onClick={() => navigate('/app/graph')}><Network size={15} /> Explore in graph</Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <MetricCard label="Chunks" icon={<Layers size={15} />} accent="#34d399" value={chunks ? chunks.length : '—'} />
        <MetricCard label="Entities" icon={<Tags size={15} />} accent="#8b5cf6" value={entities ? entities.length : '—'} />
        <MetricCard label="Size" accent="#22d3ee" value={formatBytes(doc.size_bytes)} />
      </div>

      {/* Processing timeline */}
      {history.length > 0 && (
        <div className="mt-6">
          <div className="mb-2.5"><SectionLabel>Processing pipeline</SectionLabel></div>
          <Panel className="p-4">
            <ol className="space-y-3">
              {collapseHistory(history).map((h, i) => {
                const Icon = h.status === 'done' ? CheckCircle2 : h.status === 'failed' ? XCircle : Loader2
                const color = h.status === 'done' ? 'text-good' : h.status === 'failed' ? 'text-bad' : 'text-cyan'
                return (
                  <li key={i} className="flex items-start gap-3">
                    <Icon size={15} className={`mt-0.5 shrink-0 ${color}`} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium capitalize text-ink">{h.stage || h.status}</span>
                        <span className="font-mono text-[10px] text-faint">{fmtDate(h.created_at)}</span>
                      </div>
                      {h.message && <p className="mt-0.5 text-[12px] leading-relaxed text-muted">{h.message}</p>}
                    </div>
                  </li>
                )
              })}
            </ol>
          </Panel>
        </div>
      )}

      {/* Tabs: chunks / entities */}
      <div className="mt-6">
        <div className="mb-3 flex gap-1 border-b border-border">
          <Tab active={tab === 'chunks'} onClick={() => setTab('chunks')}>Chunks {chunks && `· ${chunks.length}`}</Tab>
          <Tab active={tab === 'entities'} onClick={() => setTab('entities')}>Entities {entities && `· ${entities.length}`}</Tab>
        </div>

        {tab === 'chunks' ? (
          chunks === null ? (
            <LoadingState label="Loading chunks…" />
          ) : chunks.length === 0 ? (
            <EmptyState icon={<Layers size={22} />} title="No chunks" description="This document hasn't produced chunks yet, or processing failed." />
          ) : (
            <div className="space-y-2.5">
              {chunks.map((c) => (
                <Panel key={c.id} className="p-3.5">
                  <div className="mb-1.5 flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-faint">
                    <span className="text-accent">Chunk #{c.chunk_index}</span>
                    <span>{c.char_count} chars</span>
                  </div>
                  <p className="text-[13px] leading-relaxed text-muted">{c.content}</p>
                </Panel>
              ))}
            </div>
          )
        ) : entities === null ? (
          <LoadingState label="Loading entities…" />
        ) : entities.length === 0 ? (
          <EmptyState icon={<Tags size={22} />} title="No entities" description="No entities were extracted from this document." />
        ) : (
          <div className="flex flex-wrap gap-2">
            {entities.map((e) => (
              <Link key={e.id} to={`/app/graph?focus=${e.id}`} title={`Focus ${e.canonical_name} in the graph`}>
                <Chip color={entityColor(e.type)} className="cursor-pointer hover:brightness-125">{e.canonical_name}</Chip>
              </Link>
            ))}
          </div>
        )}
      </div>
    </Page>
  )
}

function Tab({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={
        active
          ? 'border-b-2 border-accent px-3 py-2 text-sm font-medium text-ink'
          : 'border-b-2 border-transparent px-3 py-2 text-sm text-muted hover:text-ink'
      }
    >
      {children}
    </button>
  )
}
