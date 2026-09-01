import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, Boxes, FileText, Hash, Search as SearchIcon, Sparkles } from 'lucide-react'
import { api } from '../api'
import { Button, EmptyState, Page, PageHeader, Panel, Spinner } from '../components/ui'
import type { HybridResult } from '../types'

// The three retrievers DIRIS fuses (RRF). Badge color + description per source.
const SOURCES: Record<string, { label: string; color: string; icon: typeof Sparkles; desc: string }> = {
  vector: { label: 'Semantic', color: '#22d3ee', icon: Sparkles, desc: 'Dense embeddings — meaning, not words' },
  keyword: { label: 'Keyword', color: '#fbbf24', icon: Hash, desc: 'Full-text — exact terms & phrases' },
  graph: { label: 'Graph', color: '#a78bfa', icon: Boxes, desc: 'Entity & relationship matches' },
}

function SourceBadge({ source }: { source: string }) {
  const s = SOURCES[source]
  if (!s) return null
  const Icon = s.icon
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium"
      style={{ color: s.color, background: `${s.color}14`, borderColor: `${s.color}33` }}
    >
      <Icon size={10} /> {s.label}
    </span>
  )
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
    <Page>
      <PageHeader
        title="Hybrid Search"
        subtitle="One query, three retrievers — dense vectors, keyword full-text, and the knowledge graph — fused with reciprocal-rank fusion."
      />

      {/* Search bar */}
      <form onSubmit={run} className="flex gap-2">
        <div className="relative flex-1">
          <SearchIcon size={18} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-faint" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search across your knowledge base…"
            className="w-full rounded-xl border border-border bg-panel py-3 pl-11 pr-4 text-sm text-ink outline-none transition-colors placeholder:text-faint focus:border-[color-mix(in_srgb,var(--color-cyan)_55%,transparent)] focus:ring-2 focus:ring-[rgba(34,211,238,0.14)]"
          />
        </div>
        <Button type="submit" variant="primary" loading={loading} className="px-6">
          Search
        </Button>
      </form>

      {/* Retriever legend */}
      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        {Object.entries(SOURCES).map(([key, s]) => {
          const Icon = s.icon
          return (
            <div key={key} className="flex items-center gap-2.5 rounded-lg border border-border bg-panel/50 px-3 py-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-md" style={{ background: `${s.color}14`, color: s.color }}>
                <Icon size={14} />
              </span>
              <div className="min-w-0">
                <div className="text-[12px] font-medium text-ink">{s.label}</div>
                <div className="truncate text-[11px] text-faint">{s.desc}</div>
              </div>
            </div>
          )
        })}
      </div>

      {error && <p className="mt-4 text-sm text-bad">{error}</p>}

      {/* Results */}
      <div className="mt-6">
        {loading ? (
          <Panel className="flex items-center justify-center gap-3 py-16 text-sm text-muted"><Spinner /> Searching…</Panel>
        ) : results === null ? (
          <EmptyState
            icon={<SearchIcon size={22} />}
            title="Search your knowledge base"
            description="Try a concept, an exact phrase, or an entity name — the badges on each result show which retrievers matched."
          />
        ) : results.length === 0 ? (
          <EmptyState icon={<SearchIcon size={22} />} title="No matches" description="Try different wording, or ingest more documents." />
        ) : (
          <div className="space-y-2.5">
            <div className="font-mono text-[11px] uppercase tracking-wider text-faint">{results.length} results</div>
            {results.map((r, i) => (
              <Panel key={r.chunk_id} className="p-4 transition-colors hover:border-border-strong">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 font-mono text-[11px] text-faint">
                    <span className="text-accent">#{i + 1}</span>
                    <span>chunk {r.chunk_id}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {r.sources.map((s) => <SourceBadge key={s} source={s} />)}
                    <span className="ml-1 font-mono text-[11px] tabular-nums text-muted" title="Reciprocal-rank-fusion score">
                      {r.score.toFixed(3)}
                    </span>
                  </div>
                </div>
                <p className="text-[13px] leading-relaxed text-muted">{r.content}</p>
                {r.document_id != null && (
                  <Link
                    to={`/app/documents/${r.document_id}`}
                    className="mt-2.5 inline-flex items-center gap-1 text-[12px] text-muted transition-colors hover:text-accent"
                  >
                    <FileText size={12} /> Open source document <ArrowUpRight size={12} />
                  </Link>
                )}
              </Panel>
            ))}
          </div>
        )}
      </div>
    </Page>
  )
}
