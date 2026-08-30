import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import type { EntityDetail, EntityOut } from '../types'

const TYPE_COLORS: Record<string, string> = {
  PERSON: 'bg-blue-100 text-blue-700', ORGANIZATION: 'bg-emerald-100 text-emerald-700',
  LOCATION: 'bg-amber-100 text-amber-700', EVENT: 'bg-pink-100 text-pink-700',
  CONCEPT: 'bg-violet-100 text-violet-700', TECHNOLOGY: 'bg-cyan-100 text-cyan-700',
  OBJECT: 'bg-orange-100 text-orange-700', TOPIC: 'bg-slate-100 text-slate-600',
}

function typeClass(t: string) {
  return TYPE_COLORS[t] ?? 'bg-slate-100 text-slate-600'
}

export default function Entities() {
  const [entities, setEntities] = useState<EntityOut[] | null>(null)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState<string | null>(null)
  const [selected, setSelected] = useState<EntityDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  useEffect(() => {
    api.get<EntityOut[]>('/entities').then(setEntities).catch((e) => setError((e as Error).message))
  }, [])

  // id -> name map so relationship endpoints (which return ids) can show names.
  const nameById = useMemo(() => {
    const m = new Map<number, string>()
    entities?.forEach((e) => m.set(e.id, e.canonical_name))
    return m
  }, [entities])

  const types = useMemo(
    () => [...new Set(entities?.map((e) => e.type) ?? [])].sort(),
    [entities],
  )

  const shown = useMemo(() => {
    const f = filter.trim().toLowerCase()
    return (entities ?? []).filter(
      (e) =>
        (!typeFilter || e.type === typeFilter) &&
        (!f || e.canonical_name.toLowerCase().includes(f) || e.aliases.some((a) => a.toLowerCase().includes(f))),
    )
  }, [entities, filter, typeFilter])

  async function open(e: EntityOut) {
    setLoadingDetail(true)
    setSelected(null)
    try {
      setSelected(await api.get<EntityDetail>(`/entities/${e.id}`))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoadingDetail(false)
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold text-slate-800">Entities</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex flex-wrap items-center gap-2">
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by name or alias…"
          className="w-64 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
        />
        <button
          onClick={() => setTypeFilter(null)}
          className={`rounded-full px-3 py-1 text-xs font-medium ${!typeFilter ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
        >
          All
        </button>
        {types.map((t) => (
          <button
            key={t}
            onClick={() => setTypeFilter(t === typeFilter ? null : t)}
            className={`rounded-full px-3 py-1 text-xs font-medium ${t === typeFilter ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}
          >
            {t}
          </button>
        ))}
      </div>

      {entities && shown.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center text-sm text-slate-500">
          {entities.length === 0 ? 'No entities yet. Upload and process documents to extract them.' : 'No entities match your filter.'}
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {shown.map((e) => (
          <button
            key={e.id}
            onClick={() => open(e)}
            className="rounded-xl border border-slate-200 bg-white p-4 text-left transition hover:border-indigo-300 hover:shadow-sm"
          >
            <div className="flex items-start justify-between gap-2">
              <span className="font-medium text-slate-800">{e.canonical_name}</span>
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${typeClass(e.type)}`}>{e.type}</span>
            </div>
            {e.description && <p className="mt-1 line-clamp-2 text-xs text-slate-500">{e.description}</p>}
            <div className="mt-2 flex items-center gap-2 text-[11px] text-slate-400">
              <span>{e.mention_count} mention{e.mention_count === 1 ? '' : 's'}</span>
              {e.aliases.length > 0 && <span>· {e.aliases.length} alias{e.aliases.length === 1 ? '' : 'es'}</span>}
            </div>
          </button>
        ))}
      </div>

      {(selected || loadingDetail) && (
        <div className="fixed inset-0 z-20 flex justify-end bg-slate-900/30" onClick={() => setSelected(null)}>
          <div
            className="h-full w-full max-w-md overflow-y-auto bg-white p-6 shadow-xl"
            onClick={(ev) => ev.stopPropagation()}
          >
            {loadingDetail && <p className="text-sm text-slate-500">Loading…</p>}
            {selected && (
              <>
                <div className="mb-4 flex items-start justify-between gap-2">
                  <div>
                    <h2 className="text-lg font-semibold text-slate-800">{selected.canonical_name}</h2>
                    <span className={`mt-1 inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${typeClass(selected.type)}`}>{selected.type}</span>
                  </div>
                  <button onClick={() => setSelected(null)} className="text-slate-400 hover:text-slate-700">✕</button>
                </div>

                {selected.description && <p className="mb-4 text-sm text-slate-600">{selected.description}</p>}

                {selected.aliases.length > 0 && (
                  <div className="mb-4">
                    <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">Aliases</p>
                    <div className="flex flex-wrap gap-1.5">
                      {selected.aliases.map((a) => (
                        <span key={a} className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{a}</span>
                      ))}
                    </div>
                  </div>
                )}

                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
                  Relationships ({selected.relationships.length})
                </p>
                {selected.relationships.length === 0 ? (
                  <p className="text-sm text-slate-400">No relationships extracted.</p>
                ) : (
                  <ul className="space-y-2">
                    {selected.relationships.map((r) => {
                      const outgoing = r.source_entity_id === selected.id
                      const otherId = outgoing ? r.target_entity_id : r.source_entity_id
                      const otherName = nameById.get(otherId) ?? `#${otherId}`
                      return (
                        <li key={r.id} className="rounded-lg border border-slate-200 p-2.5 text-sm">
                          <div className="flex items-center gap-1.5">
                            <span className="text-slate-400">{outgoing ? '→' : '←'}</span>
                            <span className="font-medium text-indigo-600">{r.type}</span>
                            <span className="text-slate-700">{otherName}</span>
                          </div>
                          {r.evidence && <p className="mt-1 text-xs italic text-slate-400">“{r.evidence}”</p>}
                        </li>
                      )
                    })}
                  </ul>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
