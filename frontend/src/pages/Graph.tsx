import { useEffect, useRef, useState } from 'react'
import { DataSet } from 'vis-data'
import { Network } from 'vis-network'
import { api, API_BASE, getToken } from '../api'
import type { GraphOut } from '../types'

const TYPE_COLORS: Record<string, string> = {
  PERSON: '#60a5fa', ORGANIZATION: '#34d399', LOCATION: '#fbbf24', EVENT: '#f472b6',
  CONCEPT: '#a78bfa', TECHNOLOGY: '#22d3ee', OBJECT: '#f97316', TOPIC: '#94a3b8', WORK: '#e879f9',
}

type Rel = { type: string; other: string; out: boolean }
type Focus = { name: string; type: string; rels: Rel[] }

export default function Graph() {
  const containerRef = useRef<HTMLDivElement>(null)
  const networkRef = useRef<Network | null>(null)
  const [graph, setGraph] = useState<GraphOut | null>(null)
  const [error, setError] = useState('')
  const [focus, setFocus] = useState<Focus | null>(null)

  async function load() {
    setError('')
    try {
      setGraph(await api.get<GraphOut>('/graph?limit=500'))
    } catch (e) {
      setError((e as Error).message)
    }
  }
  useEffect(() => {
    load()
  }, [])

  // Render the network whenever the graph data changes.
  useEffect(() => {
    if (!graph || !containerRef.current || graph.nodes.length === 0) return

    const nodeName = new Map(graph.nodes.map((n) => [n.entity_id, n.name]))
    const nodeType = new Map(graph.nodes.map((n) => [n.entity_id, n.type]))

    // Size each node by how connected it is, so hubs (Harry, Hogwarts) stand out.
    const degree = new Map<number, number>()
    for (const e of graph.edges) {
      degree.set(e.source, (degree.get(e.source) ?? 0) + 1)
      degree.set(e.target, (degree.get(e.target) ?? 0) + 1)
    }

    const nodes = new DataSet(
      graph.nodes.map((n) => ({
        id: n.entity_id,
        label: n.name,
        title: `${n.name} · ${n.type}`,
        value: (degree.get(n.entity_id) ?? 0) + 1,
        color: TYPE_COLORS[n.type] ?? '#94a3b8',
      })),
    )
    // No edge labels on the canvas (they clutter and are hard to clear reliably);
    // the relationship type lives in the tooltip and the side panel instead.
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
          font: { color: '#0f172a', size: 13 },
        },
        edges: {
          color: { color: '#cbd5e1', opacity: 0.55, highlight: '#6366f1', hover: '#6366f1' },
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

    // Clicking a node highlights its edges (vis selection) and opens a panel
    // listing its relationships. Clicking it again, or empty space, clears both.
    let currentId: number | null = null
    network.on('click', (p: { nodes: number[] }) => {
      const clicked = p.nodes.length ? p.nodes[0] : null
      currentId = clicked !== null && clicked === currentId ? null : clicked
      if (currentId === null) {
        network.unselectAll()
        setFocus(null)
        return
      }
      const id = currentId
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

  const types = graph ? [...new Set(graph.nodes.map((n) => n.type))] : []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-800">Knowledge Graph</h1>
        <div className="flex gap-2">
          <button onClick={load} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
            Refresh
          </button>
          <button onClick={() => download('json')} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
            Export JSON
          </button>
          <button onClick={() => download('graphml')} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
            Export GraphML
          </button>
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {types.length > 0 && (
        <div className="flex flex-wrap gap-3 text-xs text-slate-500">
          {types.map((t) => (
            <span key={t} className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: TYPE_COLORS[t] ?? '#94a3b8' }} />
              {t}
            </span>
          ))}
        </div>
      )}

      {graph && graph.nodes.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-16 text-center text-sm text-slate-500">
          No graph yet. Upload and process documents, then their entities and relationships appear here.
        </div>
      ) : (
        <>
          {graph && (
            <p className="text-xs text-slate-400">
              Click a node to highlight its links and list them on the right · scroll to zoom · drag to pan · bigger nodes are more connected
            </p>
          )}
          <div className="relative">
            <div ref={containerRef} className="h-[calc(100vh-13rem)] rounded-xl border border-slate-200 bg-white" />

            {focus && (
              <div className="absolute right-4 top-4 flex max-h-[calc(100%-2rem)] w-72 flex-col rounded-xl border border-slate-200 bg-white/95 shadow-lg backdrop-blur">
                <div className="flex items-start justify-between gap-2 border-b border-slate-100 p-4">
                  <div>
                    <div className="font-semibold text-slate-800">{focus.name}</div>
                    <span className="mt-1 inline-flex items-center gap-1.5 text-xs text-slate-500">
                      <span className="h-2 w-2 rounded-full" style={{ background: TYPE_COLORS[focus.type] ?? '#94a3b8' }} />
                      {focus.type}
                    </span>
                  </div>
                  <button onClick={clearFocus} className="text-slate-400 hover:text-slate-700" aria-label="Close">✕</button>
                </div>
                <div className="overflow-y-auto p-4">
                  <div className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
                    {focus.rels.length} relationship{focus.rels.length === 1 ? '' : 's'}
                  </div>
                  {focus.rels.length === 0 ? (
                    <p className="text-sm text-slate-400">No relationships extracted for this entity.</p>
                  ) : (
                    <ul className="space-y-1.5">
                      {focus.rels.map((r, i) => (
                        <li key={i} className="flex items-baseline gap-1.5 text-sm">
                          <span className="text-slate-400">{r.out ? '→' : '←'}</span>
                          <span className="font-medium text-indigo-600">{r.type}</span>
                          <span className="text-slate-700">{r.other}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
