// Shared visual language for entity types — one source of truth for the graph,
// the entities browser, search matches, and chat citations.
export const ENTITY_COLORS: Record<string, string> = {
  PERSON: '#38bdf8',
  ORGANIZATION: '#34d399',
  LOCATION: '#fbbf24',
  EVENT: '#f472b6',
  CONCEPT: '#a78bfa',
  TECHNOLOGY: '#22d3ee',
  OBJECT: '#fb923c',
  TOPIC: '#94a3b8',
  WORK: '#e879f9',
  DATE: '#818cf8',
}

export function entityColor(type: string | null | undefined): string {
  if (!type) return '#94a3b8'
  return ENTITY_COLORS[type.toUpperCase()] ?? '#94a3b8'
}

// Tinted chip styles for a type badge on dark surfaces.
export function typeChipStyle(type: string): { color: string; background: string; borderColor: string } {
  const c = entityColor(type)
  return { color: c, background: `${c}1a`, borderColor: `${c}33` }
}
