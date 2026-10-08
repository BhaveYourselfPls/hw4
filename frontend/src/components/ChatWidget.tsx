import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { getToken, useAuth } from '../auth'
import { useMatches, type MatchedProduct } from '../matches'
import { useSize } from '../size'
import { renderInline } from '../markdown'
import { money } from '../api'

/**
 * Chat panel, wired to the Pydantic AI agent behind POST /api/chat.
 *
 * The agent returns prose *and* a structured product list, so every reply can
 * render real cards with photos beside the text. The message shape mirrors the
 * chat_messages table (role + content + products).
 */

interface Message {
  role: 'user' | 'assistant'
  content: string
  products?: MatchedProduct[]
  /** Loaded from the database rather than sent this session. */
  restored?: boolean
}

interface StoredMessage {
  id: number
  role: string
  content: string
  products: MatchedProduct[]
  created_at: string
}

const greetingFor = (firstName?: string | null): Message => ({
  role: 'assistant',
  content: firstName
    ? `Hi ${firstName}! I'm the Campus Customs merch assistant. Ask me about our Yale apparel — styles, colors, prices or what's in stock in your size.`
    : "Hi! I'm the Campus Customs merch assistant. Ask me about our Yale apparel — styles, colors, prices or what's in stock in your size.",
})

const HINTS = ['What hoodies do you have?', 'How much is a crewneck?', 'Anything for a Yale mom?']

/** Minimal Markdown: **bold** and a leading "- " bullet, which is all the
 *  assistant is asked to produce. */
function renderText(text: string) {
  return text.split('\n').map((line, i) => {
    const bullet = line.trimStart().startsWith('- ')
    const body = bullet ? line.trimStart().slice(2) : line
    const nodes = renderInline(body)
    return (
      <div key={i} className={bullet ? 'chat-bullet' : undefined}>
        {bullet ? '• ' : ''}
        {nodes}
      </div>
    )
  })
}

export default function ChatWidget() {
  const { user } = useAuth()
  const { setMatches } = useMatches()
  const { size } = useSize()
  const navigate = useNavigate()
  const location = useLocation()
  const firstName = user?.first_name || user?.name.split(' ')[0] || null

  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([greetingFor(firstName)])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [returnFocus, setReturnFocus] = useState(false)
  const logRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const fabRef = useRef<HTMLButtonElement>(null)

  /** What the shopper is looking at — sent with every message so "is this in
   *  large?" resolves to the product on screen. */
  function pageContext() {
    const match = location.pathname.match(/^\/products\/(.+)$/)
    const category = new URLSearchParams(location.search).get('category')
    return {
      path: location.pathname,
      product_id: match ? decodeURIComponent(match[1]) : null,
      category,
      preferred_size: size,
    }
  }

  // Load the signed-in shopper's stored conversation; fall back to a fresh
  // greeting for guests and for accounts with no history yet.
  useEffect(() => {
    let cancelled = false

    if (!user) {
      setMessages([greetingFor(null)])
      return
    }

    setLoadingHistory(true)
    fetch('/api/chat/history', { headers: { Authorization: `Bearer ${getToken()}` } })
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data: { messages: StoredMessage[] }) => {
        if (cancelled) return
        const restored: Message[] = (data.messages ?? []).map((m) => ({
          role: m.role === 'user' ? 'user' : 'assistant',
          content: m.content,
          products: m.products ?? [],
          restored: true,
        }))
        setMessages(restored.length ? [greetingFor(firstName), ...restored] : [greetingFor(firstName)])
      })
      .catch(() => {
        if (!cancelled) setMessages([greetingFor(firstName)])
      })
      .finally(() => !cancelled && setLoadingHistory(false))

    return () => {
      cancelled = true
    }
  }, [user, firstName])

  async function clearHistory() {
    if (!user) return
    await fetch('/api/chat/history', {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${getToken()}` },
    }).catch(() => undefined)
    setMessages([greetingFor(firstName)])
  }

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, open, busy])

  // Keyboard and focus handling. Opening the panel used to leave focus on the
  // page behind it: you had to mouse into the input, and Escape did nothing.
  useEffect(() => {
    if (!open) return

    inputRef.current?.focus()

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.stopPropagation()
        close()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open])

  // Closing swaps the panel back for the button, so focus has to move after
  // that render — otherwise it falls to <body> and keyboard users lose their
  // place on the page.
  useEffect(() => {
    if (!open && returnFocus) {
      fabRef.current?.focus()
      setReturnFocus(false)
    }
  }, [open, returnFocus])

  function close() {
    setOpen(false)
    setReturnFocus(true)
  }

  async function send(text: string) {
    const content = text.trim()
    if (!content || busy) return

    // Guests send their in-memory turns. Signed-in shoppers do not: the server
    // reads their real thread from the database rather than trusting the client.
    const history = user ? [] : messages.slice(1).map((m) => ({ role: m.role, content: m.content }))

    setMessages((prev) => [...prev, { role: 'user', content }])
    setDraft('')
    setBusy(true)

    try {
      const token = getToken()
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message: content, history, page: pageContext() }),
      })
      const data = await res.json().catch(() => ({}))

      if (!res.ok) {
        const detail = typeof data.detail === 'string' ? data.detail : 'Something went wrong.'
        throw new Error(detail)
      }

      const products: MatchedProduct[] = data.products ?? []
      setMessages((prev) => [...prev, { role: 'assistant', content: data.message, products }])

      // Publish the matches so the Products page can show them as full cards.
      setMatches(products, content)
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content:
            err instanceof Error
              ? `Sorry — ${err.message}`
              : 'Sorry, I could not reach the shop just now. Please try again.',
        },
      ])
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <button
        ref={fabRef}
        className="chat-fab"
        onClick={() => setOpen(true)}
        aria-label="Open merch chat"
        aria-expanded={false}
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 8.3 8.3 0 0 1-3.8-.9L3 21l1.9-5.1A8.4 8.4 0 0 1 12 3a8.4 8.4 0 0 1 9 8.5z" />
        </svg>
      </button>
    )
  }

  return (
    <div className="chat-panel" role="dialog" aria-modal="false" aria-label="Campus Customs merch chat">
      <div className="chat-head">
        <div>
          <strong>Merch Assistant</strong>
          <small>
            {user ? `Saved to ${firstName}'s account` : 'Styles · prices · stock'}
          </small>
        </div>
        <div className="chat-head-actions">
          {user && messages.length > 1 && (
            <button className="chat-x chat-clear" onClick={clearHistory} title="Clear saved conversation">
              Clear
            </button>
          )}
          <button className="chat-x" onClick={close} aria-label="Close chat">
            ×
          </button>
        </div>
      </div>

      {/* role="log" + aria-live means a screen reader announces each new reply
          as it arrives, instead of the conversation changing silently. */}
      <div className="chat-log" ref={logRef} role="log" aria-live="polite" aria-relevant="additions">
        {loadingHistory && <div className="chat-meta">Loading your conversation…</div>}
        {!loadingHistory && messages.some((m) => m.restored) && (
          <div className="chat-meta">Picking up where you left off</div>
        )}
        {messages.map((message, i) => (
          <div key={i} className="chat-turn">
            <div className={message.role === 'user' ? 'bubble me' : 'bubble bot'}>
              {renderText(message.content)}
            </div>

            {message.products && message.products.length > 0 && (
              <div className="chat-cards">
                {message.products.map((product) => (
                  <Link
                    key={product.product_id}
                    to={`/products/${product.product_id}`}
                    className="chat-card"
                  >
                    <img src={product.image_url} alt={product.name} loading="lazy" />
                    <div className="chat-card-body">
                      <span className="chat-card-name">{product.name}</span>
                      <span className="chat-card-price">{money(product.price)}</span>
                      {product.note && (
                        <span className="chat-card-note">{renderInline(product.note)}</span>
                      )}
                    </div>
                  </Link>
                ))}

                <button
                  className="chat-see-all"
                  onClick={() => {
                    setMatches(message.products!, '')
                    navigate('/products?from=chat')
                  }}
                >
                  See {message.products.length === 1 ? 'it' : `all ${message.products.length}`} in
                  the shop →
                </button>
              </div>
            )}
          </div>
        ))}

        {busy && (
          <div className="bubble bot typing" aria-label="Assistant is typing">
            <span />
            <span />
            <span />
          </div>
        )}
      </div>

      {messages.length === 1 && !busy && (
        <div className="chat-hints">
          {HINTS.map((hint) => (
            <button key={hint} className="hint" onClick={() => send(hint)}>
              {hint}
            </button>
          ))}
        </div>
      )}

      <form
        className="chat-form"
        onSubmit={(e) => {
          e.preventDefault()
          send(draft)
        }}
      >
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask about our merch…"
          aria-label="Message"
          disabled={busy}
        />
        <button className="chat-send" type="submit" disabled={!draft.trim() || busy} aria-label="Send">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z" />
          </svg>
        </button>
      </form>
    </div>
  )
}
