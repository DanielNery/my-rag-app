import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'

type SourceChunk = {
  chunk: string
  source: string
  score: number
}

type Message = {
  id: string
  role: 'user' | 'assistant' | 'system'
  text: string
  createdAt: string
  sources?: SourceChunk[]
}

type ChatSession = {
  id: string
  name: string
  messages: Message[]
  createdAt: string
  updatedAt: string
}

type ApiMessage = {
  id: string
  role: 'user' | 'assistant' | 'system'
  text: string
  created_at: string
}

type ApiChatSession = {
  id: string
  name: string
  messages: ApiMessage[]
  created_at: string
  updated_at: string
}

type StreamingBuffer = {
  sessionId: string
  text: string
}

const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

function getChatUrl() {
  const url = new URL(apiUrl)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = '/chat/'
  return url.toString()
}

function mapSession(session: ApiChatSession): ChatSession {
  return {
    id: session.id,
    name: session.name,
    messages: session.messages.map((message) => ({
      id: message.id,
      role: message.role,
      text: message.text,
      createdAt: message.created_at,
    })),
    createdAt: session.created_at,
    updatedAt: session.updated_at,
  }
}

function createLocalMessage(
  role: Message['role'],
  text: string,
  sources?: SourceChunk[],
): Message {
  return {
    id: crypto.randomUUID(),
    role,
    text,
    createdAt: new Date().toISOString(),
    sources,
  }
}

function formatSessionTime(value: string) {
  return new Intl.DateTimeFormat('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

// Mapeador de componentes para Markdown, criei para formatar resposta
const markdownComponents: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  ul: ({ children }) => <ul className="mb-2 list-disc space-y-0.5 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 list-decimal space-y-0.5 pl-5">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  pre: ({ children }) => (
    <pre className="mb-2 overflow-x-auto rounded-md bg-slate-100 p-3 text-sm text-slate-800">
      {children}
    </pre>
  ),
  code: ({ className, children }) => {
    const isBlock = Boolean(className)
    if (isBlock) {
      return <code className="font-mono">{children}</code>
    }
    return (
      <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-sm text-slate-700">
        {children}
      </code>
    )
  },
  h1: ({ children }) => <h1 className="mb-2 text-lg font-bold">{children}</h1>,
  h2: ({ children }) => <h2 className="mb-2 font-bold">{children}</h2>,
  h3: ({ children }) => <h3 className="mb-1 font-semibold">{children}</h3>,
  blockquote: ({ children }) => (
    <blockquote className="mb-2 border-l-4 border-slate-300 pl-4 italic text-slate-600">
      {children}
    </blockquote>
  ),
}

function LoadingDots() {
  // Bot digitando, carregando resposta...
  return (
    <div className="flex items-center gap-1 px-1 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-2 w-2 rounded-full bg-slate-400 animate-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  )
}

function MessageBubble({ message }: { message: Message }) {
  // Bubble de mensagem, com role do usuário, sistema ou assistente.
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[88%] overflow-hidden rounded-lg px-3 py-2 text-base leading-7 break-words shadow-sm sm:max-w-[82%] sm:px-4 sm:py-3 ${
          isUser
            ? 'bg-[#0B4A78] text-white'
            : isSystem
              ? 'border border-amber-200 bg-amber-50 text-amber-900'
              : 'border border-slate-200 bg-white text-slate-800'
        }`}
      >
        {isUser || isSystem ? (
          message.text
        ) : (
          <ReactMarkdown components={markdownComponents}>{message.text}</ReactMarkdown>
        )}

        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 space-y-2 border-t border-slate-200 pt-3">
            {message.sources.map((source, index) => (
              <div
                className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600"
                key={`${source.source}-${index}`}
              >
                <p className="font-semibold text-[#082B49]">
                  {source.source} · score {source.score.toFixed(4)}
                </p>
                <p className="mt-1 line-clamp-3">{source.chunk}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default function ChatWindow() {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState('')
  const [editingName, setEditingName] = useState('')
  const [input, setInput] = useState('')
  const [error, setError] = useState('')
  const [isLoadingSessions, setIsLoadingSessions] = useState(true)
  const [isAsking, setIsAsking] = useState(false)
  const [deletingSessionId, setDeletingSessionId] = useState<string | null>(null)
  const [streamingMessage, setStreamingMessage] = useState<StreamingBuffer | null>(null)
  const [socketStatus, setSocketStatus] = useState<'connecting' | 'connected' | 'offline'>(
    'connecting',
  )
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const activeSessionIdRef = useRef(activeSessionId)
  const streamingBufferRef = useRef<StreamingBuffer | null>(null)

  const activeSession = sessions.find((session) => session.id === activeSessionId)

  useEffect(() => {
    activeSessionIdRef.current = activeSessionId
  }, [activeSessionId])

  useEffect(() => {
    // Carrega as sessões do backend.
    async function loadSessions() {
      setIsLoadingSessions(true)
      setError('')

      try {
        const response = await fetch(`${apiUrl}/session/`)
        if (!response.ok) {
          throw new Error('Nao foi possivel carregar as sessoes')
        }

        const data = (await response.json()) as ApiChatSession[]
        if (data.length > 0) {
          const mappedSessions = data.map(mapSession)
          setSessions(mappedSessions)
          setActiveSessionId(mappedSessions[0].id)
          return
        }

        await createSession('Atendimento inicial')
      } catch (requestError) {
        setError(
          requestError instanceof Error ? requestError.message : 'Erro ao carregar sessoes',
        )
      } finally {
        setIsLoadingSessions(false)
      }
    }

    loadSessions()
  }, [])

  useEffect(() => {
    // Conecta ao WebSocket do backend.
    const socket = new WebSocket(getChatUrl())
    socketRef.current = socket

    socket.addEventListener('open', () => {
      // Conexao estabelecida com sucesso, atualiza o estado da conexao.
      setSocketStatus('connected')
      setError('')
    })

    socket.addEventListener('close', () => {
      // Conexao fechada, atualiza o estado da conexao.
      setSocketStatus('offline')
      setIsAsking(false)
      streamingBufferRef.current = null
      setStreamingMessage(null)
    })

    socket.addEventListener('error', () => {
      // Erro na conexao, atualiza o estado da conexao.
      setSocketStatus('offline')
      setIsAsking(false)
      streamingBufferRef.current = null
      setStreamingMessage(null)
    })

    socket.addEventListener('message', (event) => {
      // Mensagem recebida do backend, processa a mensagem.
      try {
        console.log('Mensagem recebida do backend:', event.data)
        const data = JSON.parse(event.data as string) as {
          type?: string
          session_id?: string
          text?: string
          sources?: SourceChunk[]
        }

        console.log('Dados da mensagem:', data)

        const sessionId = data.session_id ?? activeSessionIdRef.current

        if (data.type === 'token') {
          const text = data.text ?? ''
          if (!streamingBufferRef.current) {
            streamingBufferRef.current = { sessionId, text }
          } else {
            streamingBufferRef.current.text += text
          }
          setStreamingMessage({ ...streamingBufferRef.current })
          return
        }

        if (data.type === 'done') {
          const buffer = streamingBufferRef.current
          if (buffer) {
            appendMessage(
              buffer.sessionId,
              createLocalMessage('assistant', buffer.text, data.sources ?? []),
            )
          }
          streamingBufferRef.current = null
          setStreamingMessage(null)
          setIsAsking(false)
          return
        }

        if (data.type === 'error') {
          streamingBufferRef.current = null
          setStreamingMessage(null)
          appendMessage(sessionId, createLocalMessage('system', data.text ?? 'Erro desconhecido'))
          setIsAsking(false)
          return
        }

        // Fallback para protocolo sem type
        appendMessage(
          sessionId,
          createLocalMessage('assistant', data.text ?? event.data, data.sources ?? []),
        )
        setIsAsking(false)
      } catch {
        appendMessage(activeSessionIdRef.current, createLocalMessage('assistant', event.data))
        setIsAsking(false)
      }
    })

    return () => {
      socket.close()
    }
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activeSession?.messages, streamingMessage?.text])

  useEffect(() => {
    setEditingName(activeSession?.name ?? '')
  }, [activeSession?.id, activeSession?.name])

  function appendMessage(sessionId: string, message: Message) {
    if (!sessionId) return

    setSessions((current) =>
      current.map((session) =>
        session.id === sessionId
          ? {
              ...session,
              messages: [...session.messages, message],
              updatedAt: message.createdAt,
            }
          : session,
      ),
    )
  }

  async function createSession(name: string) {
    // Cria uma nova sessão no backend.
    const response = await fetch(`${apiUrl}/session/`, {
      body: JSON.stringify({ name }),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
    })

    if (!response.ok) {
      throw new Error('Nao foi possivel criar a sessao')
    }

    const session = mapSession((await response.json()) as ApiChatSession)
    setSessions((current) => [session, ...current])
    setActiveSessionId(session.id)
    setInput('')
    return session
  }

  async function handleCreateSession() {
    // Cria uma nova sessão no backend.
    setError('')

    try {
      await createSession(`Sessao ${sessions.length + 1}`)
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : 'Erro ao criar sessao',
      )
    }
  }

  async function handleDeleteSession(sessionId: string) {
    // Deleta uma sessão no backend.
    setDeletingSessionId(sessionId)
    setError('')

    try {
      const response = await fetch(`${apiUrl}/session/${sessionId}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        throw new Error('Nao foi possivel excluir a sessao')
      }

      setSessions((current) => {
        const next = current.filter((s) => s.id !== sessionId)

        if (activeSessionId === sessionId) {
          if (next.length > 0) {
            setActiveSessionId(next[0].id)
          } else {
            setActiveSessionId('')
          }
        }

        return next
      })
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : 'Erro ao excluir sessao',
      )
    } finally {
      setDeletingSessionId(null)
    }
  }

  async function renameActiveSession(name: string) {
    // Renomeia uma sessão no backend.
    const nextName = name.trim()
    if (!nextName || !activeSession || nextName === activeSession.name) return

    setSessions((current) =>
      current.map((session) =>
        session.id === activeSession.id ? { ...session, name: nextName } : session,
      ),
    )

    try {
      const response = await fetch(`${apiUrl}/session/${activeSession.id}`, {
        body: JSON.stringify({ name: nextName }),
        headers: { 'Content-Type': 'application/json' },
        method: 'PUT',
      })

      if (!response.ok) {
        throw new Error('Nao foi possivel renomear a sessao')
      }

      const updatedSession = mapSession((await response.json()) as ApiChatSession)
      setSessions((current) =>
        current.map((session) =>
          session.id === updatedSession.id ? updatedSession : session,
        ),
      )
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : 'Erro ao renomear sessao',
      )
    }
  }

  function handleRenameSession(event: FormEvent<HTMLFormElement>) {
    // Renomeia uma sessão no backend.
    event.preventDefault()
    renameActiveSession(editingName)
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const text = input.trim()
    if (!text || !activeSession) return

    appendMessage(activeSession.id, createLocalMessage('user', text))
    setInput('')
    setError('')
    setIsAsking(true)

    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(
        JSON.stringify({
          session_id: activeSession.id,
          text,
        }),
      )
      return
    }

    setIsAsking(false)
    setSocketStatus('offline')
    appendMessage(
      activeSession.id,
      createLocalMessage(
        'system',
        'Chat indisponivel. Verifique se o WebSocket do backend esta rodando.',
      ),
    )
  }

  function getStatusLabel() {
    // Label de status, com role do usuário, sistema ou assistente.
    if (isAsking && !streamingMessage) return 'Buscando'
    if (isAsking && streamingMessage) return 'Respondendo'
    if (socketStatus === 'connected') return 'Online'
    if (socketStatus === 'connecting') return 'Conectando'
    return 'Offline'
  }

  function getSendDisabled() {
    // Desabilita o botão de enviar se o input estiver vazio, não houver sessão ativa, estiver carregando ou a conexão não estiver estabelecida.
    return !input.trim() || !activeSession || isAsking || socketStatus !== 'connected'
  }

  function getStatusClassName() {
    // Classe de status, com role do usuário, sistema ou assistente.
    if (isAsking) return 'bg-sky-50 text-[#0B4A78]'
    if (socketStatus === 'connected') return 'bg-emerald-50 text-emerald-700'
    if (socketStatus === 'connecting') return 'bg-sky-50 text-[#0B4A78]'
    return 'bg-amber-50 text-amber-800'
  }

  const showLoadingDots = isAsking && !streamingMessage
  const showStreamingBubble =
    streamingMessage && streamingMessage.sessionId === activeSessionId

  return (
    <section className="flex w-full overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <aside className="flex w-1/4 flex-col border-b border-slate-200 bg-slate-50 md:border-r md:border-b-0">
        <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
          <h2 className="text-lg font-semibold text-[#082B49]">Sessoes</h2>
          <button
            className="rounded-md bg-[#082B49] px-3 py-2 text-sm font-semibold text-white transition hover:bg-[#0B4A78] disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={isLoadingSessions}
            onClick={handleCreateSession}
            type="button"
          >
            Novo
          </button>
        </div>

        <div className="flex gap-2 overflow-x-auto p-3 md:flex-1 md:flex-col md:overflow-y-auto md:overflow-x-hidden">
          {isLoadingSessions ? (
            <p className="px-2 py-3 text-base text-slate-500">Carregando...</p>
          ) : (
            sessions.map((session) => {
              const isActive = session.id === activeSession?.id
              const isDeleting = deletingSessionId === session.id

              return (
                <div
                  className={`group relative min-w-44 rounded-md border transition md:min-w-0 ${
                    isActive
                      ? 'border-[#0B4A78] bg-white shadow-sm'
                      : 'border-transparent bg-transparent hover:border-slate-200 hover:bg-white'
                  }`}
                  key={session.id}
                >
                  <button
                    className="w-full px-3 py-3 text-left"
                    onClick={() => {
                      setActiveSessionId(session.id)
                      setInput('')
                    }}
                    type="button"
                  >
                    <span className="block truncate pr-6 text-base font-semibold text-slate-800">
                      {session.name}
                    </span>
                    <span className="mt-1 block text-sm text-slate-500">
                      {session.messages.length} mensagens ·{' '}
                      {formatSessionTime(session.updatedAt)}
                    </span>
                  </button>

                  <button
                    aria-label={`Excluir sessao ${session.name}`}
                    className="absolute top-2.5 right-2 rounded p-1 text-slate-300 opacity-0 transition hover:bg-red-50 hover:text-red-500 disabled:cursor-not-allowed group-hover:opacity-100"
                    disabled={isDeleting}
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDeleteSession(session.id)
                    }}
                    type="button"
                  >
                    {isDeleting ? (
                      <svg className="h-3.5 w-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" fill="currentColor" />
                      </svg>
                    ) : (
                      <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                        <path d="M6 18L18 6M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                  </button>
                </div>
              )
            })
          )}
        </div>
      </aside>

      <div className="flex w-3/4 flex-col">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3 sm:px-5 sm:py-4">
          <form className="min-w-0 flex-1" onSubmit={handleRenameSession}>
            <label className="sr-only" htmlFor="session-name">
              Nome da sessao
            </label>
            <input
              className="w-full min-w-0 rounded-md border border-slate-200 bg-white/50 px-3 py-2 text-lg font-semibold outline-none transition placeholder:text-slate-400 focus:border-[#0B4A78] sm:text-xl"
              disabled={!activeSession}
              id="session-name"
              onBlur={(event) => renameActiveSession(event.currentTarget.value)}
              onChange={(event) => setEditingName(event.target.value)}
              placeholder="Nome da sessao"
              value={editingName}
            />
            <p className="mt-1 truncate text-sm text-slate-500 sm:text-base">
              Edite o nome e pressione Enter
            </p>
          </form>

          <span
            className={`shrink-0 rounded-full px-3 py-1 text-sm font-semibold transition ${getStatusClassName()}`}
          >
            {getStatusLabel()}
          </span>
        </div>

        {error && (
          <div className="border-b border-amber-200 bg-amber-50 px-5 py-3 text-base text-amber-900">
            {error}
          </div>
        )}

        <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50 px-3 py-4 sm:space-y-4 sm:px-5 sm:py-5">
          {activeSession?.messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {showLoadingDots && (
            <div className="flex justify-start">
              <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
                <LoadingDots />
              </div>
            </div>
          )}

          {showStreamingBubble && (
            <div className="flex justify-start">
              <div className="max-w-[88%] overflow-hidden rounded-lg border border-slate-200 bg-white px-3 py-2 text-base leading-7 break-words text-slate-800 shadow-sm sm:max-w-[82%] sm:px-4 sm:py-3">
                <ReactMarkdown components={markdownComponents}>
                  {streamingMessage.text}
                </ReactMarkdown>
                <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-slate-400 align-middle" />
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        <form
          className="flex flex-col gap-3 border-t border-slate-200 bg-white p-3 sm:flex-row sm:p-4"
          onSubmit={handleSubmit}
        >
          <input
            className="min-h-11 min-w-0 flex-1 rounded-md border border-slate-300 px-4 text-base outline-none transition focus:border-[#0B4A78] focus:ring-2 focus:ring-sky-100"
            disabled={!activeSession}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Digite sua pergunta..."
            type="text"
            value={input}
          />
          <button
            className="min-h-11 rounded-md bg-[#082B49] px-5 text-base font-semibold text-white transition hover:bg-[#0B4A78] disabled:cursor-not-allowed disabled:bg-slate-300 sm:w-auto"
            disabled={getSendDisabled()}
            type="submit"
          >
            {isAsking ? 'Aguarde...' : 'Enviar'}
          </button>
        </form>
      </div>
    </section>
  )
}
