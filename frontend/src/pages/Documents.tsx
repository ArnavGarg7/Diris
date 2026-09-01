import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight, FileText, Layers, Replace as ReplaceIcon, RotateCw, Trash2, Upload, UploadCloud, X,
} from 'lucide-react'
import { api } from '../api'
import StatusBadge from '../components/StatusBadge'
import { Button, EmptyState, IconButton, PageHeader, Panel, Spinner } from '../components/ui'
import { fmtDate, formatBytes, isTerminal, type ChunkOut, type DocumentOut, type EntityOut } from '../types'

const FORMATS = ['PDF', 'DOCX', 'TXT', 'MD', 'HTML']
const PIPELINE = ['Upload', 'Extract text', 'Chunk', 'Analyze entities', 'Build graph']

export default function Documents() {
  const [docs, setDocs] = useState<DocumentOut[]>([])
  const [meta, setMeta] = useState<Record<number, { chunks: number; entities: number }>>({})
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [chunksFor, setChunksFor] = useState<DocumentOut | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const replaceInput = useRef<HTMLInputElement>(null)
  const replaceId = useRef<number | null>(null)
  const fetched = useRef<Set<number>>(new Set())

  async function load() {
    try {
      setDocs(await api.get<DocumentOut[]>('/documents'))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  // Poll while any document is still processing.
  useEffect(() => {
    const id = setInterval(() => {
      if (docs.some((d) => !isTerminal(d.status))) load()
    }, 2500)
    return () => clearInterval(id)
  }, [docs])

  // Lazily pull chunk + entity counts for each ready document (once).
  useEffect(() => {
    docs
      .filter((d) => d.status === 'done' && !fetched.current.has(d.id))
      .forEach(async (d) => {
        fetched.current.add(d.id)
        try {
          const [ch, en] = await Promise.all([
            api.get<ChunkOut[]>(`/documents/${d.id}/chunks`),
            api.get<EntityOut[]>(`/documents/${d.id}/entities`),
          ])
          setMeta((m) => ({ ...m, [d.id]: { chunks: ch.length, entities: en.length } }))
        } catch {
          fetched.current.delete(d.id)
        }
      })
  }, [docs])

  async function upload(file: File) {
    setError('')
    setUploading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      await api.post('/documents', form)
      await load()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setUploading(false)
    }
  }

  async function replace(id: number, file: File) {
    setError('')
    fetched.current.delete(id)
    setMeta((m) => {
      const n = { ...m }
      delete n[id]
      return n
    })
    try {
      const form = new FormData()
      form.append('file', file)
      await api.put(`/documents/${id}`, form)
      await load()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  async function reprocess(id: number) {
    setError('')
    fetched.current.delete(id)
    setMeta((m) => {
      const n = { ...m }
      delete n[id]
      return n
    })
    try {
      await api.post(`/documents/${id}/reprocess`)
      await load()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  async function remove(id: number) {
    if (!confirm('Delete this document and everything extracted from it?')) return
    try {
      await api.del(`/documents/${id}`)
      fetched.current.delete(id)
      await load()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <>
      <PageHeader
        title="Documents"
        subtitle="Ingest sources — DIRIS extracts chunks, entities, and relationships into your knowledge graph."
        actions={
          <Button variant="primary" onClick={() => fileInput.current?.click()} loading={uploading}>
            <Upload size={16} /> Upload document
          </Button>
        }
      />

      <input ref={fileInput} type="file" className="hidden"
        onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
      <input ref={replaceInput} type="file" className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f && replaceId.current != null) replace(replaceId.current, f)
        }} />

      {/* Drop zone */}
      <div
        onClick={() => fileInput.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          if (e.dataTransfer.files?.[0]) upload(e.dataTransfer.files[0])
        }}
        className={`group relative cursor-pointer overflow-hidden rounded-2xl border border-dashed p-8 text-center transition-all ${
          dragging
            ? 'border-accent bg-[rgba(34,211,238,0.06)]'
            : 'border-border bg-panel/40 hover:border-border-strong hover:bg-panel'
        }`}
      >
        <div className="grid-dots pointer-events-none absolute inset-0 opacity-30" />
        <div className="relative flex flex-col items-center">
          <div className={`mb-3 flex h-12 w-12 items-center justify-center rounded-xl border transition-colors ${
            dragging ? 'border-accent text-accent' : 'border-border bg-elevated text-accent'
          }`}>
            <UploadCloud size={22} />
          </div>
          <p className="text-sm text-ink">
            <span className="font-medium text-accent">Click to upload</span> or drag & drop a document
          </p>
          <div className="mt-3 flex flex-wrap items-center justify-center gap-1.5">
            {FORMATS.map((f) => (
              <span key={f} className="rounded border border-border bg-elevated px-1.5 py-0.5 font-mono text-[10px] text-muted">
                {f}
              </span>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 font-mono text-[11px] text-faint">
            {PIPELINE.map((step, i) => (
              <span key={step} className="inline-flex items-center gap-2">
                {step}
                {i < PIPELINE.length - 1 && <ArrowRight size={11} className="text-border-strong" />}
              </span>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <p className="mt-4 rounded-lg border border-[rgba(251,113,133,0.28)] bg-[rgba(251,113,133,0.08)] px-3 py-2 text-sm text-bad">
          {error}
        </p>
      )}

      {/* Library */}
      <div className="mt-6">
        {loading ? (
          <Panel className="flex items-center justify-center gap-3 py-16 text-sm text-muted">
            <Spinner /> Loading library…
          </Panel>
        ) : docs.length === 0 ? (
          <EmptyState
            icon={<FileText size={22} />}
            title="Your knowledge base is empty"
            description="Upload a document to start building your graph. Books, reports, and notes all work."
          />
        ) : (
          <Panel className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left font-mono text-[11px] uppercase tracking-wider text-faint">
                    <th className="px-5 py-3 font-medium">Document</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 text-right font-medium">Size</th>
                    <th className="px-4 py-3 text-right font-medium">Chunks</th>
                    <th className="px-4 py-3 text-right font-medium">Entities</th>
                    <th className="px-4 py-3 font-medium">Added</th>
                    <th className="px-5 py-3 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {docs.map((d) => {
                    const m = meta[d.id]
                    return (
                      <tr key={d.id} className="border-b border-border/60 transition-colors last:border-0 hover:bg-hover/60">
                        <td className="max-w-[260px] px-5 py-3.5">
                          <Link to={`/app/documents/${d.id}`} className="flex items-center gap-2.5 hover:text-accent">
                            <FileText size={16} className="shrink-0 text-faint" />
                            <span className="truncate font-medium text-ink hover:text-accent" title={d.original_filename}>
                              {d.original_filename}
                            </span>
                          </Link>
                        </td>
                        <td className="px-4 py-3.5">
                          <div className="flex flex-col gap-1">
                            <StatusBadge status={d.status} />
                            {!isTerminal(d.status) && d.processing_detail && (
                              <span className="font-mono text-[10px] text-faint">{d.processing_detail}</span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3.5 text-right font-mono text-[13px] text-muted">{formatBytes(d.size_bytes)}</td>
                        <td className="px-4 py-3.5 text-right font-mono text-[13px] text-muted">{m ? m.chunks : '—'}</td>
                        <td className="px-4 py-3.5 text-right font-mono text-[13px] text-muted">{m ? m.entities : '—'}</td>
                        <td className="whitespace-nowrap px-4 py-3.5 text-[13px] text-muted">{fmtDate(d.created_at)}</td>
                        <td className="px-5 py-3.5">
                          <div className="flex items-center justify-end gap-0.5">
                            <IconButton title="View chunks" aria-label="View chunks" onClick={() => setChunksFor(d)}><Layers size={15} /></IconButton>
                            <IconButton title="Reprocess" aria-label="Reprocess document" onClick={() => reprocess(d.id)}><RotateCw size={15} /></IconButton>
                            <IconButton title="Replace file" aria-label="Replace file" onClick={() => { replaceId.current = d.id; replaceInput.current?.click() }}><ReplaceIcon size={15} /></IconButton>
                            <IconButton title="Delete" aria-label="Delete document" className="hover:text-bad" onClick={() => remove(d.id)}><Trash2 size={15} /></IconButton>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Panel>
        )}
      </div>

      {chunksFor && <ChunksModal doc={chunksFor} onClose={() => setChunksFor(null)} />}
    </>
  )
}

function ChunksModal({ doc, onClose }: { doc: DocumentOut; onClose: () => void }) {
  const [chunks, setChunks] = useState<ChunkOut[] | null>(null)
  useEffect(() => {
    api.get<ChunkOut[]>(`/documents/${doc.id}/chunks`).then(setChunks).catch(() => setChunks([]))
  }, [doc.id])
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm" onClick={onClose}>
      <div className="flex max-h-[82vh] w-full max-w-2xl flex-col rounded-2xl border border-border bg-panel shadow-2xl rise" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
          <div className="flex min-w-0 items-center gap-2.5">
            <Layers size={16} className="shrink-0 text-accent" />
            <span className="truncate font-medium text-ink" title={doc.original_filename}>{doc.original_filename}</span>
            {chunks && <span className="shrink-0 font-mono text-[11px] text-faint">{chunks.length} chunks</span>}
          </div>
          <IconButton onClick={onClose}><X size={16} /></IconButton>
        </div>
        <div className="overflow-y-auto p-5">
          {chunks === null ? (
            <div className="flex items-center justify-center gap-3 py-10 text-sm text-muted"><Spinner /> Loading chunks…</div>
          ) : chunks.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted">No chunks — not processed yet, or processing failed.</p>
          ) : (
            <div className="space-y-2.5">
              {chunks.map((c) => (
                <div key={c.id} className="rounded-lg border border-border bg-elevated p-3.5">
                  <div className="mb-1.5 flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-faint">
                    <span className="text-accent">#{c.chunk_index}</span>
                    <span>{c.char_count} chars</span>
                  </div>
                  <div className="text-[13px] leading-relaxed text-muted">{c.content}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
