export type DocumentOut = {
  id: number
  original_filename: string
  content_type: string
  size_bytes: number
  status: string
  created_at: string
  processing_detail?: string | null
}

export type ChunkOut = {
  id: number
  chunk_index: number
  char_count: number
  content: string
}

export type Citation = {
  chunk_id: number
  document_id: number | null
  document_name: string
  section: string | null
  chunk_index: number
  snippet: string
}

export type AnswerOut = {
  answer: string
  answered: boolean
  confidence: number
  citations: Citation[]
  reasoning: string
  conversation_id: number | null
}

export type ConversationOut = {
  id: number
  created_at: string
  message_count: number
}

export type MessageOut = {
  role: string
  content: string
  created_at: string
}

export type EntityOut = {
  id: number
  canonical_name: string
  type: string
  description: string | null
  aliases: string[]
  mention_count: number
}

export type RelationshipOut = {
  id: number
  source_entity_id: number
  target_entity_id: number
  type: string
  evidence: string | null
  confidence: number
}

export type EntityDetail = EntityOut & { relationships: RelationshipOut[] }

export type GraphNode = { entity_id: number; name: string; type: string }
export type GraphEdge = { source: number; target: number; type: string; confidence: number | null }
export type GraphOut = { nodes: GraphNode[]; edges: GraphEdge[] }

export type HybridResult = {
  chunk_id: number
  document_id: number | null
  content: string
  score: number
  sources: string[]
}

export const TERMINAL_STATUSES = ['done', 'failed']

export function isTerminal(status: string): boolean {
  return TERMINAL_STATUSES.includes(status)
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}
