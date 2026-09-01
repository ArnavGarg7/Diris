import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { DataSet } from 'vis-data'
import { Network } from 'vis-network'
import {
  Crosshair, Download, Maximize2, Minus, Plus, RefreshCw, Search, Waypoints, X,
} from 'lucide-react'
import { api, API_BASE, getToken } from '../api'
import { entityColor } from '../lib/entities'
import { nodeImage } from '../lib/nodeIcons'
import { Button, EmptyState, IconButton, SectionLabel, Spinner } from '../components/ui'
import type { EntityOut, GraphOut } from '../types'

type Rel = { type: string; other: string; out: boolean }
type Inspect = { id: number; name: string; type: string; rels: Rel[] }

export default function Graph() {
  const [params] = useSearchParams()
  const containerRef = useRef<HTMLDivElement>(null)
  const networkRef = useRef<Network | null>(null)
  const [full, setFull] = useState<GraphOut | null>(null)
  const [view, setView] = useState<GraphOut | null>(null)
  const [focused, setFocused] = useState<{ id: number; name: string } | null>(null)
  const [mentions, setMentions] = useState<Map<number, number>>(new Map())
  const [entityIdx, setEntityIdx] = useState<EntityOut[]>([])
  const [enabled, setEnabled] = useState<Set<string> | null>(null) // null = all types shown
  const [inspect, setInspect] = useState<Inspect | null>(null)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // asView=false loads the full graph into `full` (for legend/reset) WITHOUT
  // taking over the view — so a deep-linked ?focus neighborhood isn't clobbered.
  async function loadFull(asView = true) {
    setError('')
    try {
      const g = await api.get<GraphOut>('/graph?limit=500')
      setFull(g)
      if (asView) {
        setView(g)
        setFocused(null)
        setInspect(null)
      }
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const f = params.get('focus')
    loadFull(!(f && !Number.isNaN(Number(f))))
    api.get<EntityOut[]>('/entities').then((list) => {
      setEntityIdx(list)
      setMentions(new Map(list.map((e) => [e.id, e.mention_count])))
    }).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function focusEntity(id: number, name?: string) {
    try {
      const n = await api.get<GraphOut>(`/entities/${id}/neighborhood?hops=1`)
      if (n.nodes.length === 0) return
      const nm = name ?? n.nodes.find((x) => x.entity_id === id)?.name ?? `#${id}`
      setEnabled(null)
      setView(n)
      setFocused({ id, name: nm })
      setInspect(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  // Deep-link: /app/graph?focus=<entityId>
  useEffect(() => {
    const f = params.get('focus')
    if (f && !Number.isNaN(Number(f))) focusEntity(Number(f))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params])

  function resetView() {
    setView(full)
    setFocused(null)
    setInspect(null)
  }

  function runSearch(e?: React.FormEvent) {
    e?.preventDefault()
    const q = query.trim().toLowerCase()
    if (!q) return
    const match =
      entityIdx.find((x) => x.canonical_name.toLowerCase() === q) ??
      entityIdx.find((x) => x.canonical_name.toLowerCase().includes(q))
    if (match) focusEntity(match.id, match.canonical_name)
    else setError(`No entity matches “${query}”.`)
  }

  // Render network from the current view, filtered by enabled types.
  useEffect(() => {
    if (!view || !containerRef.current || view.nodes.length === 0) return

    const nodes0 = enabled ? view.nodes.filter((n) => enabled.has(n.type)) : view.nodes
    const idset = new Set(nodes0.map((n) => n.entity_id))
    const edges0 = view.edges.filter((e) => idset.has(e.source) && idset.has(e.target))

    const nodeName = new Map(view.nodes.map((n) => [n.entity_id, n.name]))
    const nodeType = new Map(view.nodes.map((n) => [n.entity_id, n.type]))
    const degree = new Map<number, number>()
    for (const e of edges0) {
      degree.set(e.source, (degree.get(e.source) ?? 0) + 1)
      degree.set(e.target, (degree.get(e.target) ?? 0) + 1)
    }

    const nodes = new DataSet(
      nodes0.map((n) => ({
        id: n.entity_id,
        label: n.name,
        title: `${n.name} · ${n.type}`,
        value: (degree.get(n.entity_id) ?? 0) + 1,
        shape: 'image',
        image: nodeImage(n.type),
        // Transparent box so only the disc shows (no square halo behind it).
        color: { background: 'rgba(0,0,0,0)', border: 'rgba(0,0,0,0)' },
        font: { color: '#c7d2e0', size: 13, face: 'Inter' },
      })),
    )
    const edges = new DataSet(
      edges0.map((e, i) => ({ id: i, from: e.source, to: e.target, title: e.type, arrows: { to: { scaleFactor: 0.5 } } })),
    )
    const network = new Network(
      containerRef.current,
      { nodes, edges },
      {
        nodes: {
          shape: 'image',
          scaling: { min: 18, max: 46, label: { min: 12, max: 20, drawThreshold: 5 } },
          shapeProperties: { useBorderWithImage: false },
        },
        edges: {
          color: { color: '#2a3854', opacity: 0.55, highlight: '#22d3ee', hover: '#22d3ee' },
          width: 1, selectionWidth: 3, smooth: { enabled: true, type: 'continuous', roundness: 0.2 },
        },
        interaction: { hover: true, tooltipDelay: 120, hideEdgesOnDrag: true },
        physics: {
          stabilization: { iterations: 250 },
          barnesHut: { springLength: 220, gravitationalConstant: -14000, centralGravity: 0.15, avoidOverlap: 0.6, damping: 0.35 },
        },
      },
    )
    networkRef.current = network

    let selected: number | null = null
    network.on('click', (p: { nodes: number[] }) => {
      const clicked = p.nodes.length ? p.nodes[0] : null
      selected = clicked !== null && clicked === selected ? null : clicked
      if (selected === null) {
        network.unselectAll()
        setInspect(null)
        return
      }
      const id = selected
      const rels: Rel[] = view.edges
        .filter((e) => e.source === id || e.target === id)
        .map((e) => {
          const out = e.source === id
          return { type: e.type, other: nodeName.get(out ? e.target : e.source) ?? '?', out }
        })
      setInspect({ id, name: nodeName.get(id) ?? '?', type: nodeType.get(id) ?? '', rels })
    })

    return () => {
      network.destroy()
      networkRef.current = null
    }
  }, [view, enabled])

  function zoom(factor: number) {
    const n = networkRef.current
    if (n) n.moveTo({ scale: n.getScale() * factor, animation: { duration: 200, easingFunction: 'easeInOutQuad' } })
  }
  function fit() {
    networkRef.current?.fit({ animation: { duration: 300, easingFunction: 'easeInOutQuad' } })
  }

  async function download(format: 'json' | 'graphml') {
    const res = await fetch(`${API_BASE}/graph/export?format=${format}`, { headers: { Authorization: `Bearer ${getToken()}` } })
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `graph.${format === 'graphml' ? 'graphml' : 'json'}`
    a.click()
    URL.revokeObjectURL(url)
  }

  const allTypes = full ? [...new Set(full.nodes.map((n) => n.type))].sort() : []
  const empty = full && full.nodes.length === 0

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3.5 md:px-6">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-elevated text-accent">
            <Waypoints size={18} />
          </span>
          <div>
            <h1 className="font-display text-[17px] font-semibold text-ink">Knowledge Graph</h1>
            {view && !empty && (
              <p className="font-mono text-[11px] text-faint">{view.nodes.length} entities · {view.edges.length} relationships</p>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <form onSubmit={runSearch} className="relative">
            <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-faint" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); runSearch() } }}
              placeholder="Find entity…"
              className="w-40 rounded-lg border border-border bg-elevated py-1.5 pl-8 pr-2.5 text-[13px] text-ink outline-none placeholder:text-faint focus:border-[color-mix(in_srgb,var(--color-cyan)_55%,transparent)]"
            />
          </form>
          <Button size="sm" onClick={() => loadFull()}><RefreshCw size={14} /> Refresh</Button>
          <Button size="sm" onClick={() => download('json')}><Download size={14} /> JSON</Button>
          <Button size="sm" onClick={() => download('graphml')}><Download size={14} /> GraphML</Button>
        </div>
      </header>

      {/* Focus banner */}
      {focused && (
        <div className="flex items-center justify-between gap-2 border-b border-border bg-[rgba(34,211,238,0.06)] px-5 py-2 md:px-6">
          <span className="flex items-center gap-2 text-[13px] text-muted">
            <Crosshair size={14} className="text-accent" /> Focused on <span className="font-medium text-ink">{focused.name}</span> · 1-hop neighborhood
          </span>
          <button onClick={resetView} className="text-[13px] text-accent hover:underline">Reset to full graph</button>
        </div>
      )}

      {/* Type filter legend */}
      {allTypes.length > 0 && !focused && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-border px-5 py-2.5 md:px-6">
          {allTypes.map((t) => {
            const on = !enabled || enabled.has(t)
            return (
              <button
                key={t}
                onClick={() => {
                  setEnabled((prev) => {
                    const base = prev ?? new Set(allTypes)
                    const next = new Set(base)
                    if (next.has(t)) next.delete(t)
                    else next.add(t)
                    return next.size === allTypes.length ? null : next
                  })
                }}
                className={`inline-flex items-center gap-1.5 text-[11px] transition-opacity ${on ? 'text-muted' : 'text-faint opacity-40'}`}
              >
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: entityColor(t) }} />
                {t}
              </button>
            )
          })}
        </div>
      )}

      {/* Canvas */}
      <div className="relative min-h-0 flex-1">
        {loading ? (
          <div className="flex h-full items-center justify-center gap-3 text-sm text-muted"><Spinner /> Building graph visualization…</div>
        ) : error && !view ? (
          <div className="flex h-full items-center justify-center p-8">
            <EmptyState icon={<Waypoints size={22} />} title="Couldn't load the graph" description={error}
              action={<Button variant="primary" onClick={() => loadFull()}>Retry</Button>} />
          </div>
        ) : empty ? (
          <div className="flex h-full items-center justify-center p-8">
            <EmptyState icon={<Waypoints size={22} />} title="No graph yet"
              description="Process a document to start building your knowledge graph — its entities and relationships appear here." />
          </div>
        ) : (
          <>
            <div ref={containerRef} className="grid-dots absolute inset-0 bg-surface" />

            <div className="absolute bottom-4 left-4 flex flex-col overflow-hidden rounded-lg border border-border bg-panel/90 backdrop-blur">
              <ZoomBtn onClick={() => zoom(1.3)} label="Zoom in"><Plus size={15} /></ZoomBtn>
              <div className="h-px bg-border" />
              <ZoomBtn onClick={() => zoom(0.75)} label="Zoom out"><Minus size={15} /></ZoomBtn>
              <div className="h-px bg-border" />
              <ZoomBtn onClick={fit} label="Fit to view"><Maximize2 size={14} /></ZoomBtn>
            </div>

            <p className="pointer-events-none absolute bottom-4 right-4 font-mono text-[10px] text-faint">
              click a node to inspect · scroll to zoom · drag to pan
            </p>

            {inspect && (
              <div className="absolute right-4 top-4 flex max-h-[calc(100%-2rem)] w-72 flex-col rounded-xl border border-border bg-panel/95 shadow-2xl backdrop-blur rise">
                <div className="flex items-start justify-between gap-2 border-b border-border p-4">
                  <div className="flex items-start gap-2.5">
                    <span className="mt-0.5 h-3 w-3 shrink-0 rounded-full" style={{ background: entityColor(inspect.type) }} />
                    <div>
                      <div className="font-display font-semibold leading-tight text-ink">{inspect.name}</div>
                      <div className="mt-0.5 font-mono text-[10px] uppercase tracking-wider" style={{ color: entityColor(inspect.type) }}>{inspect.type}</div>
                    </div>
                  </div>
                  <IconButton aria-label="Close" onClick={() => { networkRef.current?.unselectAll(); setInspect(null) }}><X size={15} /></IconButton>
                </div>
                <div className="flex gap-2 border-b border-border p-3">
                  <MiniStat label="Mentions" value={mentions.get(inspect.id) ?? '—'} />
                  <MiniStat label="Links" value={inspect.rels.length} />
                </div>
                <div className="overflow-y-auto p-4">
                  <SectionLabel>Connected entities</SectionLabel>
                  {inspect.rels.length === 0 ? (
                    <p className="mt-2 text-sm text-faint">No relationships in view.</p>
                  ) : (
                    <ul className="mt-2 space-y-1">
                      {inspect.rels.map((r, i) => (
                        <li key={i} className="flex items-baseline gap-1.5 rounded-md px-1.5 py-1 text-[13px] hover:bg-hover">
                          <span className="text-faint">{r.out ? '→' : '←'}</span>
                          <span className="font-medium text-accent">{r.type}</span>
                          <span className="min-w-0 truncate text-ink">{r.other}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="border-t border-border p-3">
                  <button
                    onClick={() => focusEntity(inspect.id, inspect.name)}
                    className="flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-elevated py-2 text-[13px] font-medium text-ink transition-colors hover:border-accent/50 hover:text-accent"
                  >
                    <Crosshair size={14} /> Focus neighborhood
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function ZoomBtn({ onClick, label, children }: { onClick: () => void; label: string; children: React.ReactNode }) {
  return (
    <button onClick={onClick} title={label} aria-label={label} className="flex h-8 w-8 items-center justify-center text-muted transition-colors hover:bg-hover hover:text-ink">
      {children}
    </button>
  )
}

function MiniStat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex-1 rounded-lg border border-border bg-elevated px-2 py-1.5 text-center">
      <div className="font-display text-base font-semibold tabular-nums text-ink">{value}</div>
      <div className="font-mono text-[9px] uppercase tracking-wider text-faint">{label}</div>
    </div>
  )
}
