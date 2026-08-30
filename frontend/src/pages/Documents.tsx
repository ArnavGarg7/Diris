import { useEffect, useRef, useState, type ReactNode } from 'react'
import { api } from '../api'
import StatusBadge from '../components/StatusBadge'
import { type ChunkOut, type DocumentOut, formatBytes, isTerminal } from '../types'

export default function Documents() {
  const [docs, setDocs] = useState<DocumentOut[]>([])
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [chunksFor, setChunksFor] = useState<DocumentOut | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const replaceInput = useRef<HTMLInputElement>(null)
  const replaceId = useRef<number | null>(null)

  async function load() {
    try {
      setDocs(await api.get<DocumentOut[]>('/documents'))
    } catch (e) {
      setError((e as Error).message)
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
    try {
      const form = new FormData()
      form.append('file', file)
      await api.put(`/documents/${id}`, form)
      await load()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  async function remove(id: number) {
    if (!confirm('Delete this document and its knowledge?')) return
    try {
      await api.del(`/documents/${id}`)
      await load()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-800">Documents</h1>
        <button
          onClick={() => fileInput.current?.click()}
          disabled={uploading}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {uploading ? 'Uploading…' : 'Upload document'}
        </button>
      </div>

      <input
        ref={fileInput}
        type="file"
        className="hidden"
        onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
      />
      <input
        ref={replaceInput}
        type="file"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f && replaceId.current != null) replace(replaceId.current, f)
        }}
      />

      {/* Drag & drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          if (e.dataTransfer.files?.[0]) upload(e.dataTransfer.files[0])
        }}
        className={`rounded-xl border-2 border-dashed p-8 text-center text-sm transition ${
          dragging ? 'border-indigo-400 bg-indigo-50 text-indigo-600' : 'border-slate-300 text-slate-500'
        }`}
      >
        Drag & drop a PDF, DOCX, TXT, MD, or HTML file here — or use the button above.
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {docs.length === 0 ? (
        <p className="text-sm text-slate-500">No documents yet. Upload one to build your knowledge base.</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Size</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-4 py-3 font-medium text-slate-700">{d.original_filename}</td>
                  <td className="px-4 py-3 text-slate-500">{formatBytes(d.size_bytes)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <StatusBadge status={d.status} />
                      {!isTerminal(d.status) && d.processing_detail && (
                        <span className="text-xs text-slate-400">{d.processing_detail}</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-2">
                      <ActionBtn onClick={() => setChunksFor(d)}>Chunks</ActionBtn>
                      <ActionBtn
                        onClick={() => {
                          replaceId.current = d.id
                          replaceInput.current?.click()
                        }}
                      >
                        Replace
                      </ActionBtn>
                      <ActionBtn danger onClick={() => remove(d.id)}>Delete</ActionBtn>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {chunksFor && <ChunksModal doc={chunksFor} onClose={() => setChunksFor(null)} />}
    </div>
  )
}

function ActionBtn({ children, onClick, danger }: { children: ReactNode; onClick: () => void; danger?: boolean }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-md border px-2.5 py-1 text-xs ${
        danger
          ? 'border-red-200 text-red-600 hover:bg-red-50'
          : 'border-slate-300 text-slate-600 hover:bg-slate-100'
      }`}
    >
      {children}
    </button>
  )
}

function ChunksModal({ doc, onClose }: { doc: DocumentOut; onClose: () => void }) {
  const [chunks, setChunks] = useState<ChunkOut[] | null>(null)
  useEffect(() => {
    api.get<ChunkOut[]>(`/documents/${doc.id}/chunks`).then(setChunks).catch(() => setChunks([]))
  }, [doc.id])
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="max-h-[80vh] w-full max-w-2xl overflow-auto rounded-xl bg-white p-6" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-800">Chunks · {doc.original_filename}</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700">✕</button>
        </div>
        {chunks === null ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : chunks.length === 0 ? (
          <p className="text-sm text-slate-500">No chunks (not processed yet, or processing failed).</p>
        ) : (
          <div className="space-y-3">
            {chunks.map((c) => (
              <div key={c.id} className="rounded-lg border border-slate-200 p-3">
                <div className="mb-1 text-xs text-slate-400">#{c.chunk_index} · {c.char_count} chars</div>
                <div className="text-sm text-slate-700">{c.content}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
