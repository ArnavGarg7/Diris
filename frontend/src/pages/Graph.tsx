import { useEffect, useRef, useState } from 'react'
import { DataSet } from 'vis-data'
import { Network } from 'vis-network'
import { Download, Maximize2, Minus, Plus, RefreshCw, Waypoints, X } from 'lucide-react'
import { api, API_BASE, getToken } from '../api'
import { entityColor } from '../lib/entities'
import { Button, EmptyState, IconButton, SectionLabel, Spinner } from '../components/ui'
import type { GraphOut } from '../types'

type Rel = { type: string; other: string; out: boolean }
type Focus = { name: string; type: string; rels: Rel[] }

export default function Graph() {
  const containerRef = useRef<HTMLDivElement>(null)
  const networkRef = useRef<Network | null>(null)
  const [graph, setGraph] = useState<GraphOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [focus, setFocus] = useState<Focus | null>(null)

  async function load() {
    setError('')
    setLoading(true)
    try {
      setGraph(await api.get<GraphOut>('/graph?limit=500'))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    if (!graph || !containerRef.current || graph.nodes.length === 0) return

    const nodeName = new Map(graph.nodes.map((n) => [n.entity_id, n.name]))
    const nodeType = new Map(graph.nodes.map((n) => [n.entity_id, n.type]))
    const degree = new Map<number, number>()
    for (const e of graph.edges) {
      degree.set(e.source, (degree.get(e.source) ?? 0) + 1)
      degree.set(e.target, (degree.get(e.target) ?? 0) + 1)
    }

    const nodes = new DataSet(
      graph.nodes.map((n) => {
        const c = entityColor(n.type)
        return {
          id: n.entity_id,
          label: n.name,
          title: `${n.name} · ${n.type}`,
          value: (degree.get(n.entity_id) ?? 0) + 1,
          color: { background: c, border: c, highlight: { background: c, border: '#e7edf6' }, hover: { background: c, border: '#e7edf6' } },
          font: { color: '#c7d2e0', size: 13, face: 'Inter' },
        }
      }),
    )
    const edges = new DataSet(
      graph.edges.map((e, i) => ({
        id: i,
        from: e.source,
        to: e.target,
        title: e.type,
        arrows: { to: { scaleFactor: 0.5 } },
      })),
    )
    const network = new Network(
      containerRef.current,
      { nodes, edges },
      {
        nodes: {
          shape: 'dot',
          scaling: { min: 8, max: 34, label: { min: 12, max: 20, drawThreshold: 5 } },
          borderWidth: 1.5,
        },
        edges: {
          color: { color: '#2a3854', opacity: 0.55, highlight: '#22d3ee', hover: '#22d3ee' },
          width: 1,
          selectionWidth: 3,
          smooth: { enabled: true, type: 'continuous', roundness: 0.2 },
        },
        interaction: { hover: true, tooltipDelay: 120, hideEdgesOnDrag: true },
        physics: {
          stabilization: { iterations: 250 },
          barnesHut: {
            springLength: 220,
            gravitationalConstant: -14000,
            centralGravity: 0.15,
            avoidOverlap: 0.6,
            damping: 0.35,
          },
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
        setFocus(null)
        return
      }
      const id = selected
      const rels: Rel[] = graph.edges
        .filter((e) => e.source === id || e.target === id)
        .map((e) => {
          const out = e.source === id
          return { type: e.type, other: nodeName.get(out ? e.target : e.source) ?? '?', out }
        })
      setFocus({ name: nodeName.get(id) ?? '?', type: nodeType.get(id) ?? '', rels })
    })

    return () => {
      network.destroy()
      networkRef.current = null
    }
  }, [graph])

  function zoom(factor: number) {
    const n = networkRef.current
    if (n) n.moveTo({ scale: n.getScale() * factor, animation: { duration: 200, easingFunction: 'easeInOutQuad' } })
  }
  function fit() {
    networkRef.current?.fit({ animation: { duration: 300, easingFunction: 'easeInOutQuad' } })
  }
  function clearFocus() {
    networkRef.current?.unselectAll()
    setFocus(null)
  }

  async function download(format: 'json' | 'graphml') {
    const res = await fetch(`${API_BASE}/graph/export?format=${format}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `graph.${format === 'graphml' ? 'graphml' : 'json'}`
    a.click()
    URL.revokeObjectURL(url)
  }

  const types = graph ? [...new Set(graph.nodes.map((n) => n.type))].sort() : []
  const empty = graph && graph.nodes.length === 0

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
            {graph && !empty && (
              <p className="font-mono text-[11px] text-faint">
                {graph.nodes.length} entities · {graph.edges.length} relationships
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={load}><RefreshCw size={14} /> Refresh</Button>
          <Button size="sm" onClick={() => download('json')}><Download size={14} /> JSON</Button>
          <Button size="sm" onClick={() => download('graphml')}><Download size={14} /> GraphML</Button>
        </div>
      </header>

      {/* Legend */}
      {types.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-b border-border px-5 py-2.5 md:px-6">
          {types.map((t) => (
            <span key={t} className="inline-flex items-center gap-1.5 text-[11px] text-muted">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: entityColor(t) }} />
              {t}
            </span>
          ))}
        </div>
      )}

      {/* Canvas */}
      <div className="relative min-h-0 flex-1">
        {loading ? (
          <div className="flex h-full items-center justify-center gap-3 text-sm text-muted"><Spinner /> Building graph…</div>
        ) : error ? (
          <div className="flex h-full items-center justify-center p-8">
            <EmptyState icon={<Waypoints size={22} />} title="Couldn't load the graph" description={error}
              action={<Button variant="primary" onClick={load}>Retry</Button>} />
          </div>
        ) : empty ? (
          <div className="flex h-full items-center justify-center p-8">
            <EmptyState icon={<Waypoints size={22} />} title="No graph yet"
              description="Upload and process documents — their entities and relationships will appear here as an explorable graph." />
          </div>
        ) : (
          <>
            <div ref={containerRef} className="grid-dots absolute inset-0 bg-surface" />

            {/* Zoom controls */}
            <div className="absolute bottom-4 left-4 flex flex-col overflow-hidden rounded-lg border border-border bg-panel/90 backdrop-blur">
              <ZoomBtn onClick={() => zoom(1.3)} title="Zoom in"><Plus size={15} /></ZoomBtn>
              <div className="h-px bg-border" />
              <ZoomBtn onClick={() => zoom(0.75)} title="Zoom out"><Minus size={15} /></ZoomBtn>
              <div className="h-px bg-border" />
              <ZoomBtn onClick={fit} title="Fit to view"><Maximize2 size={14} /></ZoomBtn>
            </div>

            <p className="pointer-events-none absolute bottom-4 right-4 font-mono text-[10px] text-faint">
              click a node to inspect · scroll to zoom · drag to pan
            </p>

            {/* Inspector */}
            {focus && (
              <div className="absolute right-4 top-4 flex max-h-[calc(100%-2rem)] w-72 flex-col rounded-xl border border-border bg-panel/95 shadow-2xl backdrop-blur rise">
                <div className="flex items-start justify-between gap-2 border-b border-border p-4">
                  <div className="flex items-start gap-2.5">
                    <span className="mt-0.5 h-3 w-3 shrink-0 rounded-full" style={{ background: entityColor(focus.type) }} />
                    <div>
                      <div className="font-display font-semibold leading-tight text-ink">{focus.name}</div>
                      <div className="mt-0.5 font-mono text-[10px] uppercase tracking-wider" style={{ color: entityColor(focus.type) }}>
                        {focus.type}
                      </div>
                    </div>
                  </div>
                  <IconButton onClick={clearFocus}><X size={15} /></IconButton>
                </div>
                <div className="overflow-y-auto p-4">
                  <SectionLabel>{focus.rels.length} relationship{focus.rels.length === 1 ? '' : 's'}</SectionLabel>
                  {focus.rels.length === 0 ? (
                    <p className="mt-2 text-sm text-faint">No relationships extracted.</p>
                  ) : (
                    <ul className="mt-2 space-y-1">
                      {focus.rels.map((r, i) => (
                        <li key={i} className="flex items-baseline gap-1.5 rounded-md px-1.5 py-1 text-[13px] hover:bg-hover">
                          <span className="text-faint">{r.out ? '→' : '←'}</span>
                          <span className="font-medium text-accent">{r.type}</span>
                          <span className="min-w-0 truncate text-ink">{r.other}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function ZoomBtn({ onClick, title, children }: { onClick: () => void; title: string; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="flex h-8 w-8 items-center justify-center text-muted transition-colors hover:bg-hover hover:text-ink"
    >
      {children}
    </button>
  )
}
