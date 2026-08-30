import { useEffect, useRef, useState } from 'react'
import { DataSet } from 'vis-data'
import { Network } from 'vis-network'
import { api, API_BASE, getToken } from '../api'
import type { GraphOut } from '../types'

const TYPE_COLORS: Record<string, string> = {
  PERSON: '#60a5fa', ORGANIZATION: '#34d399', LOCATION: '#fbbf24', EVENT: '#f472b6',
  CONCEPT: '#a78bfa', TECHNOLOGY: '#22d3ee', OBJECT: '#f97316', TOPIC: '#94a3b8', WORK: '#e879f9',
}

export default function Graph() {
  const containerRef = useRef<HTMLDivElement>(null)
  const [graph, setGraph] = useState<GraphOut | null>(null)
  const [error, setError] = useState('')

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
    const nodes = new DataSet(
      graph.nodes.map((n) => ({
        id: n.entity_id,
        label: n.name,
        title: n.type,
        color: TYPE_COLORS[n.type] ?? '#94a3b8',
      })),
    )
    const edges = new DataSet(
      graph.edges.map((e, i) => ({
        id: i,
        from: e.source,
        to: e.target,
        label: e.type,
        arrows: 'to',
        font: { size: 10, color: '#64748b' },
      })),
    )
    const network = new Network(
      containerRef.current,
      { nodes, edges },
      {
        nodes: { shape: 'dot', size: 14, font: { color: '#0f172a', size: 13 } },
        edges: { color: { color: '#cbd5e1' }, smooth: true },
        physics: { stabilization: true, barnesHut: { springLength: 130 } },
      },
    )
    return () => network.destroy()
  }, [graph])

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
        <div ref={containerRef} className="h-[calc(100vh-13rem)] rounded-xl border border-slate-200 bg-white" />
      )}
    </div>
  )
}
