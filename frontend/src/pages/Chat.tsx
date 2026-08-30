import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { AnswerOut, Citation, ConversationOut, MessageOut } from '../types'

type ChatMessage = {
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  confidence?: number
  answered?: boolean
}

const LANGUAGES = ['Auto', 'English', 'Hindi', 'Spanish', 'French', 'German']

export default function Chat() {
  const [conversations, setConversations] = useState<ConversationOut[]>([])
  const [activeId, setActiveId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [lang, setLang] = useState('Auto')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const endRef = useRef<HTMLDivElement>(null)

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
  }, [messages])

  function newChat() {
    setActiveId(null)
    setMessages([])
    setError('')
  }

  async function selectConversation(id: number) {
    setActiveId(id)
    setError('')
    try {
      const detail = await api.get<{ messages: MessageOut[] }>(`/conversations/${id}`)
      setMessages(detail.messages.map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content })))
    } catch (e) {
      setError((e as Error).message)
    }
  }

  async function send() {
    const q = input.trim()
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
    <div className="flex h-[calc(100vh-7rem)] gap-4">
      {/* Conversations sidebar */}
      <div className="flex w-60 flex-col rounded-xl border border-slate-200 bg-white">
        <button
          onClick={newChat}
          className="m-3 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-500"
        >
          + New chat
        </button>
        <div className="flex-1 overflow-auto px-2 pb-2">
          {conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => selectConversation(c.id)}
              className={`mb-1 block w-full rounded-lg px-3 py-2 text-left text-sm ${
                activeId === c.id ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              Conversation #{c.id}
              <span className="block text-xs text-slate-400">{c.message_count} messages</span>
            </button>
          ))}
          {conversations.length === 0 && <p className="px-3 py-2 text-xs text-slate-400">No conversations yet.</p>}
        </div>
      </div>

      {/* Thread */}
      <div className="flex flex-1 flex-col rounded-xl border border-slate-200 bg-white">
        <div className="flex-1 space-y-4 overflow-auto p-5">
          {messages.length === 0 && (
            <div className="mt-16 text-center text-sm text-slate-400">
              Ask a question about your documents. Answers are grounded and cited; follow-ups remember context.
            </div>
          )}
          {messages.map((m, i) => (
            <MessageBubble key={i} m={m} />
          ))}
          {busy && <div className="text-sm text-slate-400">Thinking…</div>}
          <div ref={endRef} />
        </div>

        {error && <p className="px-5 text-sm text-red-600">{error}</p>}

        <div className="flex items-end gap-2 border-t border-slate-200 p-3">
          <select
            value={lang}
            onChange={(e) => setLang(e.target.value)}
            className="rounded-lg border border-slate-300 px-2 py-2 text-sm text-slate-600"
            title="Answer language"
          >
            {LANGUAGES.map((l) => (
              <option key={l}>{l}</option>
            ))}
          </select>
          <textarea
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
            className="flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
          />
          <button
            onClick={send}
            disabled={busy}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}

function MessageBubble({ m }: { m: ChatMessage }) {
  if (m.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-indigo-600 px-4 py-2 text-sm text-white">{m.content}</div>
      </div>
    )
  }
  const unanswered = m.answered === false
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] space-y-2">
        <div
          className={`rounded-2xl rounded-bl-sm px-4 py-2 text-sm ${
            unanswered ? 'bg-amber-50 text-amber-800' : 'bg-slate-100 text-slate-800'
          }`}
        >
          {m.content}
        </div>
        {m.confidence != null && (
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span>confidence</span>
            <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-200">
              <div className="h-full bg-indigo-500" style={{ width: `${Math.round((m.confidence || 0) * 100)}%` }} />
            </div>
            <span>{Math.round((m.confidence || 0) * 100)}%</span>
          </div>
        )}
        {m.citations && m.citations.length > 0 && (
          <div className="space-y-1">
            {m.citations.map((c) => (
              <div key={c.chunk_id} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs">
                <div className="font-medium text-slate-600">
                  {c.document_name}
                  {c.section && <span className="text-slate-400"> · {c.section}</span>}
                </div>
                <div className="text-slate-500">{c.snippet}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
