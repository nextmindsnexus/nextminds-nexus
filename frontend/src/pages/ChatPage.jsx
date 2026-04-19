import { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import ProfileDropdown from '../components/ProfileDropdown'
import { apiFetch } from '../utils/api'

function createMessage(role, content, activities = []) {
  return {
    id: crypto.randomUUID(),
    role,
    content,
    activities,
  }
}

function sanitizeAssistantText(text) {
  if (!text) {
    return ''
  }

  return text
    .replace(/\s*You can find it here:\s*<?https?:\/\/[^\s>]+>?/gi, '')
    .replace(/<https?:\/\/[^>]+>/g, '')
    .replace(/https?:\/\/\S+/g, '')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function createSession() {
  return {
    id: crypto.randomUUID(),
    apiSessionId: null,
    title: '',
    updatedAt: Date.now(),
    messages: [
      createMessage(
        'assistant',
        'Welcome to Nexus Chat. Ask for activities by grade or invention stage, and I will find curriculum resources for you.',
      ),
    ],
  }
}

function formatTime(timestamp) {
  return new Date(timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function shorten(text, max = 34) {
  if (text.length <= max) return text
  return `${text.slice(0, max).trim()}...`
}

function deriveTopicTitle(message) {
  const normalized = message
    .replace(/[\n\r]+/g, ' ')
    .replace(/[^\w\s-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  if (!normalized) {
    return 'Conversation'
  }

  return shorten(normalized, 36)
}

function displaySessionTitle(title) {
  const cleaned = (title || '').trim()
  if (!cleaned || cleaned.toLowerCase() === 'new chat') {
    return 'Start a topic'
  }

  return cleaned
}

export default function ChatPage() {
  const [sessions, setSessions] = useState(() => {
    const starter = createSession()
    return [starter]
  })
  const [activeSessionId, setActiveSessionId] = useState(() => sessions[0].id)
  const [draft, setDraft] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState('')
  const [theme, setTheme] = useState('light')

  const activeSession = useMemo(
    () => sessions.find((s) => s.id === activeSessionId) ?? sessions[0],
    [sessions, activeSessionId],
  )

  const canSubmit = !isSending && draft.trim().length > 0

  function addSession() {
    const next = createSession()
    setSessions((prev) => [next, ...prev])
    setActiveSessionId(next.id)
    setDraft('')
    setError('')
  }

  function updateSession(localId, updater) {
    setSessions((prev) =>
      prev.map((session) => {
        if (session.id !== localId) return session
        return updater(session)
      }),
    )
  }

  async function sendMessage() {
    const message = draft.trim()
    if (!message || !activeSession || isSending) {
      return
    }
    setError('')
    setDraft('')

    const userMessage = createMessage('user', message)
    updateSession(activeSession.id, (session) => ({
      ...session,
      title: (!session.title || session.title === 'New Chat')
        ? deriveTopicTitle(message)
        : session.title,
      updatedAt: Date.now(),
      messages: [...session.messages, userMessage],
    }))

    setIsSending(true)
    try {
      const response = await apiFetch('/api/chat', {
        method: 'POST',
        body: JSON.stringify({
          message,
          session_id: activeSession.apiSessionId || undefined,
        }),
      })

      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload.detail || `Chat request failed with status ${response.status}.`)
      }

      const assistantMessage = createMessage(
        'assistant',
        payload.reply || 'No response returned from the assistant.',
        payload.activities || [],
      )

      updateSession(activeSession.id, (session) => ({
        ...session,
        apiSessionId: payload.session_id || session.apiSessionId,
        updatedAt: Date.now(),
        messages: [...session.messages, assistantMessage],
      }))
    } catch (requestError) {
      const messageText = requestError instanceof Error ? requestError.message : 'Request failed. Please try again.'
      setError(messageText)
    } finally {
      setIsSending(false)
    }
  }

  function handleSubmit(event) {
    event.preventDefault()
    void sendMessage()
  }

  function handleInputKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (canSubmit) {
        void sendMessage()
      }
    }
  }

  return (
    <div className={`app theme-${theme}`}>
      <div className="layout">
        <aside className="sidebar panel">
          <header className="brand">
            <div className="brand-text-block">
              <span className="brand-name">Nexus</span>
            </div>
          </header>

          <button className="new-chat-btn" type="button" onClick={addSession}>
            Start New Conversation
          </button>

          <nav className="history" aria-label="Chat history">
            <p className="history-title">Recent Conversations</p>
            {sessions.map((session) => (
              <button
                key={session.id}
                type="button"
                className={`history-item ${session.id === activeSession.id ? 'active' : ''}`}
                onClick={() => {
                  setActiveSessionId(session.id)
                  setError('')
                }}
              >
                <span>{displaySessionTitle(session.title)}</span>
                <small>{formatTime(session.updatedAt)}</small>
              </button>
            ))}
          </nav>
        </aside>

        <main className="chat panel">
          <header className="chat-topbar">
            <div>
              <p className="nav-label">Nexus Assistant</p>
              <h2>{displaySessionTitle(activeSession.title)}</h2>
            </div>
            <div className="topbar-actions">
              <button
                className="theme-toggle"
                type="button"
                onClick={() => setTheme((prev) => (prev === 'light' ? 'dark' : 'light'))}
              >
                {theme === 'light' ? 'Dark' : 'Light'}
              </button>
              <ProfileDropdown />
            </div>
          </header>

          <section className="messages" aria-live="polite">
            {activeSession.messages.map((message) => (
              <article
                key={message.id}
                className={`message ${message.role === 'user' ? 'user' : 'assistant'}`}
              >
                <div className="message-content">
                  {message.role === 'assistant' ? (
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        a: ({ ...props }) => <a {...props} target="_blank" rel="noreferrer" />,
                      }}
                    >
                      {sanitizeAssistantText(message.content)}
                    </ReactMarkdown>
                  ) : (
                    <p>{message.content}</p>
                  )}
                </div>
                {message.activities?.length > 0 && (
                  <div className="activity-grid">
                    {message.activities.map((activity) => (
                      <article
                        key={`${message.id}-${activity.resource_url}`}
                        className="activity-card"
                      >
                        <h3>{activity.activity_name}</h3>
                        <p>
                          {activity.grade_band} - {activity.stage}
                        </p>
                        <a
                          className="activity-link"
                          href={activity.resource_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Open resource
                        </a>
                      </article>
                    ))}
                  </div>
                )}
              </article>
            ))}

            {isSending && (
              <article className="message assistant pending">
                <p>Thinking through your request...</p>
              </article>
            )}
          </section>

          <form className="composer" onSubmit={handleSubmit}>
            <label htmlFor="chat-input">Message</label>
            <textarea
              id="chat-input"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleInputKeyDown}
              rows={3}
              placeholder="Example: I need a brainstorming activity for K-2 students"
            />
            <div className="composer-footer">
              {error ? <p className="error-text">{error}</p> : <span />}
              <button type="submit" disabled={!canSubmit}>
                {isSending ? 'Sending...' : 'Send'}
              </button>
            </div>
          </form>
        </main>
      </div>
    </div>
  )
}
