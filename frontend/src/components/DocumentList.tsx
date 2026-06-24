import { useEffect, useState } from 'react'

type DocumentItem = {
  id: string
  filename?: string
  file_name?: string
  name?: string
  reader_method?: string
  chunks_count?: number
  created_at?: string
}

type DocumentListProps = {
  refreshKey?: number
}

const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

function getDocumentName(document: DocumentItem) {
  // Obtém o nome do documento.
  return document.file_name ?? document.filename ?? document.name ?? 'Documento sem nome'
}

function formatDate(value: string) {
  // Formata a data e hora no formato brasileiro.
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

export default function DocumentList({ refreshKey = 0 }: DocumentListProps) {
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [message, setMessage] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  useEffect(() => {
    // Carrega os documentos do backend.
    let isMounted = true

    async function loadDocuments() {
      setIsLoading(true)
      setMessage('')

      try {
        const response = await fetch(`${apiUrl}/documents/`)
        if (!response.ok) {
          throw new Error('Nao foi possivel carregar os documentos')
        }

        const data = (await response.json()) as DocumentItem[]
        if (!isMounted) return
        setDocuments(Array.isArray(data) ? data : [])
      } catch (error) {
        if (!isMounted) return
        setMessage(error instanceof Error ? error.message : 'Erro ao carregar documentos')
      } finally {
        if (isMounted) setIsLoading(false)
      }
    }

    loadDocuments()

    return () => {
      isMounted = false
    }
  }, [refreshKey])

  async function handleDelete(documentId: string) {
    // Deleta um documento no backend.
    setDeletingId(documentId)
    try {
      const response = await fetch(`${apiUrl}/documents/${documentId}`, {
        method: 'DELETE',
      })
      if (!response.ok) {
        throw new Error('Nao foi possivel excluir o documento')
      }
      setDocuments((prev) => prev.filter((d) => d.id !== documentId))
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Erro ao excluir documento')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <section className="flex min-h-64 flex-col rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-[#082B49]">Documentos</h2>
          <p className="mt-1 text-base text-slate-500">Arquivos disponiveis para consulta.</p>
        </div>
        <span className="rounded-full bg-sky-50 px-3 py-1 text-sm font-semibold text-[#0B4A78]">
          {documents.length}
        </span>
      </div>

      {message && (
        <p className="mb-3 text-sm text-amber-700">{message}</p>
      )}

      <div className="flex-1">
        {isLoading ? (
          <p className="text-base text-slate-500">Carregando documentos...</p>
        ) : documents.length > 0 ? (
          <ul className="space-y-3">
            {documents.map((document) => (
              <li
                className="group flex items-start gap-3 rounded-md border border-slate-200 bg-slate-50 px-4 py-3"
                key={document.id}
              >
                <div className="min-w-0 flex-1">
                  <p className="break-words text-base font-semibold text-slate-800">
                    {getDocumentName(document)}
                  </p>
                  {document.created_at && (
                    <p className="mt-1 text-sm text-slate-500">{formatDate(document.created_at)}</p>
                  )}
                  {(document.reader_method || document.chunks_count !== undefined) && (
                    <p className="mt-1 text-sm text-slate-500">
                      {document.reader_method ?? 'reader'} · {document.chunks_count ?? 0} chunks
                    </p>
                  )}
                </div>

                <button
                  aria-label={`Excluir ${getDocumentName(document)}`}
                  className="mt-0.5 shrink-0 rounded p-1 text-slate-300 transition hover:bg-red-50 hover:text-red-500 disabled:cursor-not-allowed disabled:opacity-50 group-hover:text-slate-400"
                  disabled={deletingId === document.id}
                  onClick={() => handleDelete(document.id)}
                  type="button"
                >
                  {deletingId === document.id ? (
                    <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" fill="currentColor" />
                    </svg>
                  ) : (
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                      <path d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <div className="rounded-md border border-slate-200 bg-slate-50 px-4 py-5 text-base text-slate-500">
            {message || 'Nenhum documento encontrado.'}
          </div>
        )}
      </div>
    </section>
  )
}
