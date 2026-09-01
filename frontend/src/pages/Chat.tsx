import { useEffect, useRef, useState } from 'react'
import {
  ArrowUp, ChevronDown, FileText, Languages, MessageSquarePlus, Quote,
  Sparkles, X,
} from 'lucide-react'
import { api } from '../api'
import { cx } from '../components/ui'
import type { AnswerOut, Citation, ConversationOut, MessageOut } from '../types'

type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  confidence?: number
  answered?: boolean
  reasoning?: string
}

const LANGUAGES = ['Auto', 'English', 'Hindi', 'Spanish', 'French', 'German']
const EXAMPLES = [
  'Who are the main characters?',
  'Summarize the key events.',
  'How are the main characters related?',
]

export default function Chat() {
  const [conversations, setConversations] = useState<ConversationOut[]>([])
  const [activeId, setActiveId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [lang, setLang] = useState('Auto')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [history, setHistory] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)
  const taRef = useRef<HTMLTextAreaElement>(null)

  async function loadConversations() {
    try {
      setConversations(await api.get<ConversationOut[]>('/conversations'))
    } catch (e) {
      setError((e as Error).message)
    }
  }
  useEffect(() => {
    loadConversations()
  }, [])
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busy])

  function newChat() {
    setActiveId(null)
    setMessages([])
    setError('')
    setHistory(false)
    taRef.current?.focus()
  }

  async function selectConversation(id: number) {
    setActiveId(id)
    setError('')
    setHistory(false)
    try {
      const detail = await api.get<{ messages: MessageOut[] }>(`/conversations/${id}`)
      setMessages(detail.messages.map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content })))
    } catch (e) {
      setError((e as Error).message)
    }
  }

  async function send(text?: string) {
    const q = (text ?? input).trim()
    if (!q || busy) return
    setInput('')
    setBusy(true)
    setError('')
    setMessages((m) => [...m, { role: 'user', content: q }])
    try {
      let convId = activeId
      if (convId == null) {
        const conv = await api.post<ConversationOut>('/conversations')
        convId = conv.id
        setActiveId(convId)
      }
      const body: Record<string, unknown> = { question: q, conversation_id: convId }
      if (lang !== 'Auto') body.answer_language = lang
      const ans = await api.post<AnswerOut>('/ask', body)
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: ans.answer,
          citations: ans.citations,
          confidence: ans.confidence,
          answered: ans.answered,
          reasoning: ans.reasoning,
        },
      ])
      loadConversations()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex h-full">
      {/* Conversation rail */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-border bg-surface/50 lg:flex">
        <div className="p-3">
          <button
            onClick={newChat}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-elevated px-3 py-2 text-sm font-medium text-ink transition-colors hover:border-border-strong hover:bg-hover"
          >
            <MessageSquarePlus size={16} className="text-accent" /> New chat
          </button>
        </div>
        <ConversationList conversations={conversations} activeId={activeId} onSelect={selectConversation} />
      </aside>

      {/* Thread */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-border px-6 py-3.5">
          <div>
            <h1 className="font-display text-[17px] font-semibold text-ink">Research Chat</h1>
            <p className="text-xs text-muted">Grounded answers with citations · remembers context</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setHistory((h) => !h)}
              className="rounded-lg border border-border px-2.5 py-1.5 text-xs text-muted hover:bg-hover hover:text-ink lg:hidden"
            >
              History
            </button>
            <button
              onClick={newChat}
              className="flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-xs text-muted hover:bg-hover hover:text-ink lg:hidden"
            >
              <MessageSquarePlus size={14} /> New
            </button>
          </div>
        </header>

        {/* Mobile history overlay */}
        {history && (
          <div className="border-b border-border bg-surface lg:hidden">
            <ConversationList conversations={conversations} activeId={activeId} onSelect={selectConversation} />
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-5 py-6 md:px-6">
            {messages.length === 0 && !busy ? (
              <Welcome onPick={(q) => send(q)} />
            ) : (
              <div className="space-y-7">
                {messages.map((m, i) => (
                  <MessageView key={i} m={m} />
                ))}
                {busy && <Thinking />}
              </div>
            )}
            <div ref={endRef} />
          </div>
        </div>

        {error && (
          <p className="mx-auto w-full max-w-3xl px-6 pb-2 text-sm text-bad">{error}</p>
        )}

        {/* Composer */}
        <div className="px-5 pb-5 md:px-6">
          <div className="mx-auto max-w-3xl">
            <div className="rounded-2xl border border-border bg-panel p-2 shadow-lg focus-within:border-border-strong">
              <textarea
                ref={taRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    send()
                  }
                }}
                rows={1}
                placeholder="Ask about your documents…"
                className="max-h-40 w-full resize-none bg-transparent px-3 py-2 text-sm text-ink outline-none placeholder:text-faint"
              />
              <div className="flex items-center justify-between gap-2 px-1">
                <div className="relative">
                  <Languages size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-faint" />
                  <ChevronDown size={13} className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-faint" />
                  <select
                    value={lang}
                    onChange={(e) => setLang(e.target.value)}
                    title="Answer language"
                    className="appearance-none rounded-lg border border-border bg-elevated py-1.5 pl-8 pr-7 text-[12px] text-muted outline-none hover:text-ink"
                  >
                    {LANGUAGES.map((l) => (
                      <option key={l} className="bg-panel">{l}</option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={() => send()}
                  disabled={busy || !input.trim()}
                  className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-[#04121a] transition-all hover:brightness-110 disabled:opacity-40 disabled:hover:brightness-100"
                  title="Send (Enter)"
                >
                  <ArrowUp size={17} strokeWidth={2.5} />
                </button>
              </div>
            </div>
            <p className="mt-2 text-center text-[11px] text-faint">
              Answers are grounded in your documents · <span className="font-mono">Enter</span> to send · <span className="font-mono">Shift+Enter</span> for a new line
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

function ConversationList({
  conversations, activeId, onSelect,
}: {
  conversations: ConversationOut[]
  activeId: number | null
  onSelect: (id: number) => void
}) {
  return (
    <div className="flex-1 space-y-1 overflow-y-auto px-2 pb-3">
      {conversations.length === 0 ? (
        <p className="px-3 py-3 text-xs text-faint">No conversations yet.</p>
      ) : (
        conversations.map((c) => (
          <button
            key={c.id}
            onClick={() => onSelect(c.id)}
            className={cx(
              'flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition-colors',
              activeId === c.id
                ? 'bg-[rgba(34,211,238,0.08)] text-ink'
                : 'text-muted hover:bg-hover hover:text-ink',
            )}
          >
            <Sparkles size={14} className={activeId === c.id ? 'text-accent' : 'text-faint'} />
            <span className="min-w-0 flex-1">
              <span className="block truncate">Conversation #{c.id}</span>
              <span className="block text-[11px] text-faint">{c.message_count} messages</span>
            </span>
          </button>
        ))
      )}
    </div>
  )
}

function Welcome({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="flex flex-col items-center py-16 text-center">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-border bg-elevated">
        <Sparkles size={26} className="text-accent" />
      </div>
      <h2 className="font-display text-xl font-semibold text-ink">Ask your knowledge base</h2>
      <p className="mt-2 max-w-md text-sm text-muted">
        Every answer is grounded in your documents and cited. Follow-ups remember the conversation, and you can ask in any language.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        {EXAMPLES.map((q) => (
          <button
            key={q}
            onClick={() => onPick(q)}
            className="rounded-full border border-border bg-elevated px-3.5 py-1.5 text-[13px] text-muted transition-colors hover:border-accent/50 hover:text-ink"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}

function Thinking() {
  return (
    <div className="flex items-center gap-2 text-sm text-muted">
      <span className="flex gap-1">
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent [animation-delay:-0.3s]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent [animation-delay:-0.15s]" />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent" />
      </span>
      Searching your knowledge base…
    </div>
  )
}

function MessageView({ m }: { m: ChatMessage }) {
  if (m.role === 'user') {
    return (
      <div className="flex justify-end rise">
        <div className="max-w-[85%] rounded-2xl rounded-br-md border border-[rgba(34,211,238,0.25)] bg-[rgba(34,211,238,0.08)] px-4 py-2.5 text-sm text-ink">
          {m.content}
        </div>
      </div>
    )
  }
  const unanswered = m.answered === false
  const pct = Math.round((m.confidence ?? 0) * 100)
  return (
    <div className="flex gap-3 rise">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-elevated">
        <img src="/mark.png" alt="" className="h-6 w-6 rounded-md" />
      </div>
      <div className="min-w-0 flex-1 space-y-3">
        <div
          className={cx(
            'whitespace-pre-wrap rounded-2xl rounded-tl-md border px-4 py-3 text-sm leading-relaxed',
            unanswered
              ? 'border-[rgba(251,191,36,0.25)] bg-[rgba(251,191,36,0.06)] text-ink'
              : 'border-border bg-panel text-ink',
          )}
        >
          {m.content}
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          {m.confidence != null && (
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] uppercase tracking-wider text-faint">Confidence</span>
              <div className="h-1.5 w-20 overflow-hidden rounded-full bg-elevated">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${pct}%`, background: pct >= 60 ? 'var(--color-good)' : pct >= 30 ? 'var(--color-warn)' : 'var(--color-bad)' }}
                />
              </div>
              <span className="font-mono text-[11px] text-muted">{pct}%</span>
            </div>
          )}
          {m.reasoning && <Reasoning text={m.reasoning} />}
        </div>

        {m.citations && m.citations.length > 0 && (
          <div>
            <div className="mb-1.5 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-faint">
              <Quote size={11} /> {m.citations.length} source{m.citations.length === 1 ? '' : 's'}
            </div>
            <div className="grid gap-1.5 sm:grid-cols-2">
              {m.citations.map((c, i) => (
                <CitationCard key={c.chunk_id} c={c} n={i + 1} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function CitationCard({ c, n }: { c: Citation; n: number }) {
  const [open, setOpen] = useState(false)
  return (
    <button
      onClick={() => setOpen((o) => !o)}
      className="group rounded-lg border border-border bg-elevated p-2.5 text-left transition-colors hover:border-accent/40"
    >
      <div className="flex items-center gap-2">
        <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded bg-[rgba(34,211,238,0.14)] font-mono text-[9px] font-semibold text-accent">
          {n}
        </span>
        <FileText size={12} className="shrink-0 text-faint" />
        <span className="min-w-0 flex-1 truncate text-[12px] font-medium text-ink" title={c.document_name}>
          {c.document_name}
        </span>
        {c.section && (
          <span className="shrink-0 rounded border border-border px-1.5 text-[10px] text-muted">{c.section}</span>
        )}
      </div>
      <p className={cx('mt-1.5 text-[11px] leading-relaxed text-muted', open ? '' : 'line-clamp-2')}>
        {c.snippet}
      </p>
    </button>
  )
}

function Reasoning({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider text-faint hover:text-muted"
      >
        {open ? <X size={11} /> : <ChevronDown size={11} />} Reasoning
      </button>
      {open && (
        <p className="w-full rounded-lg border border-border bg-elevated px-3 py-2 text-[12px] leading-relaxed text-muted">
          {text}
        </p>
      )}
    </>
  )
}
