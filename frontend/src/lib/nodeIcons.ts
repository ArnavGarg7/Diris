import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  BookOpen, Box, Building2, Calendar, CalendarClock, Circle, Cpu, Hash,
  Lightbulb, MapPin, User,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { entityColor } from './entities'

// One glyph per entity type — the same icons the Entities page uses.
const ICONS: Record<string, LucideIcon> = {
  PERSON: User, ORGANIZATION: Building2, LOCATION: MapPin, EVENT: CalendarClock,
  CONCEPT: Lightbulb, TECHNOLOGY: Cpu, OBJECT: Box, TOPIC: Hash, WORK: BookOpen, DATE: Calendar,
}

const cache = new Map<string, string>()

// Returns a data-URI SVG (a colored disc with the type's glyph) for a graph
// node. Built once per type and cached — no network, works for any corpus.
export function nodeImage(type: string | null | undefined): string {
  const key = (type ?? 'DEFAULT').toUpperCase()
  const hit = cache.get(key)
  if (hit) return hit

  const color = entityColor(key)
  const Icon = ICONS[key] ?? Circle
  // Render the lucide glyph to markup; pin the stroke to a dark ink so it
  // reads as a cut-out on the vivid disc.
  const glyph = renderToStaticMarkup(createElement(Icon, { size: 22, strokeWidth: 2.4 })).replace(
    /currentColor/g,
    '#06121a',
  )
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" viewBox="0 0 44 44">` +
    `<circle cx="22" cy="22" r="20" fill="${color}"/>` +
    `<g transform="translate(11,11)">${glyph}</g>` +
    `</svg>`
  const uri = `data:image/svg+xml,${encodeURIComponent(svg)}`
  cache.set(key, uri)
  return uri
}
