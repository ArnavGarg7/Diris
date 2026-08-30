import { useState } from 'react'
import { api } from '../api'
import type { HybridResult } from '../types'

// Badge colors for which retriever surfaced a chunk (RRF fusion, M8).
const SOURCE_COLORS: Record<string, string> = {
  vector: 'bg-sky-100 text-sky-700',
  keyword: 'bg-amber-100 text-amber-700',
  graph: 'bg-violet-100 text-violet-700',
}

export default function Search() {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<HybridResult[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function run(e?: React.FormEvent) {
    e?.preventDefault()
    if (!q.trim()) return
    setLoading(true)
    setError('')
    try {
      setResults(await api.get<HybridResult[]>(`/search/hybrid?q=${encodeURIComponent(q)}&top_k=10`))
    } catch (err) {
      setError((err as Error).message)
      setResults(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-slate-800">Hybrid Search</h1>
      <p className="text-sm text-slate-500">
        Fuses dense vector, keyword (full-text) and graph retrieval with reciprocal-rank fusion.
        Badges show which retrievers matched each chunk.
      </p>

      <form onSubmit={run} className="flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search across your knowledge base…"
          className="flex-1 rounded-lg border border-slate-300 px-4 py-2.5 text-sm text-slate-800 outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
        />
        <button
          type="submit"
          disabled={loading || !q.trim()}
          className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {results && results.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center text-sm text-slate-500">
          No matches. Try different wording, or upload more documents.
        </div>
      )}

      <div className="space-y-3">
        {results?.map((r, i) => (
          <div key={r.chunk_id} className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-2 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span className="font-medium text-slate-500">#{i + 1}</span>
                {r.document_id != null && <span>doc {r.document_id}</span>}
                <span>chunk {r.chunk_id}</span>
              </div>
              <div className="flex items-center gap-1.5">
                {r.sources.map((s) => (
                  <span key={s} className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${SOURCE_COLORS[s] ?? 'bg-slate-100 text-slate-600'}`}>
                    {s}
                  </span>
                ))}
                <span className="ml-1 text-xs tabular-nums text-slate-400">{r.score.toFixed(3)}</span>
              </div>
            </div>
            <p className="text-sm leading-relaxed text-slate-700">{r.content}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
