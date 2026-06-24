import { useRef, useState } from 'react'
import type { ChangeEvent, DragEvent, FormEvent } from 'react'

type FileUploadProps = {
  onUploaded?: () => void
}

const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const ACCEPTED_EXTENSIONS = /\.(pdf|txt|md|docx)$/i // Formatos aceitos.

export default function FileUpload({ onUploaded }: FileUploadProps) {
  const [files, setFiles] = useState<File[]>([])
  const [status, setStatus] = useState('')
  const [isSuccess, setIsSuccess] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const dragCounterRef = useRef(0)

  function addFiles(incoming: File[]) {
    // Adiciona arquivos ao estado.
    const valid = incoming.filter((f) => ACCEPTED_EXTENSIONS.test(f.name))
    if (valid.length < incoming.length) {
      setStatus('Alguns arquivos foram ignorados. Somente PDF, TXT, MD e DOCX são aceitos.')
      setIsSuccess(false)
    } else {
      setStatus('')
    }
    setFiles((prev) => {
      const existingNames = new Set(prev.map((f) => f.name))
      return [...prev, ...valid.filter((f) => !existingNames.has(f.name))]
    })
  }

  function removeFile(name: string) {
    // Remove arquivo do estado.
    setFiles((prev) => prev.filter((f) => f.name !== name))
    setStatus('')
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    // Muda o arquivo no estado.
    addFiles(Array.from(event.target.files ?? []))
    event.target.value = ''
  }

  function handleDragEnter(event: DragEvent<HTMLLabelElement>) {
    // Previne o comportamento padrão do evento.
    event.preventDefault()
    dragCounterRef.current++
    setIsDragging(true)
  }

  function handleDragLeave() {
    // Decrementa o contador de drag.
    dragCounterRef.current--
    if (dragCounterRef.current === 0) {
      setIsDragging(false)
    }
  }

  function handleDragOver(event: DragEvent<HTMLLabelElement>) {
    // Previne o comportamento padrão do evento.
    event.preventDefault()
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    // Previne o comportamento padrão do evento.
    event.preventDefault()
    dragCounterRef.current = 0
    setIsDragging(false)
    addFiles(Array.from(event.dataTransfer.files))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    // Envia os arquivos para o backend.
    event.preventDefault()
    if (files.length === 0) return

    setIsUploading(true)
    setStatus('')
    setIsSuccess(false)

    try {
      // Cria o formulário com os arquivos.
      const formData = new FormData()
      for (const file of files) {
        formData.append('files', file)
      }

      // Envia os arquivos para o backend.
      const response = await fetch(`${apiUrl}/upload/`, {
        body: formData,
        method: 'POST',
      })

      if (!response.ok) {
        throw new Error('Falha ao enviar arquivo')
      }

      const data = (await response.json()) as Array<{ filename: string }>
      console.log('Arquivos enviados para o backend:', data)
      setStatus(`${data.length} arquivo(s) processado(s) com sucesso.`)
      setIsSuccess(true)
      setFiles([])
      onUploaded?.()
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Erro ao enviar arquivo')
      setIsSuccess(false)
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-[#082B49]">Arquivos</h2>
        <p className="mt-1 text-base text-slate-500">Suba documentos para consulta no chat.</p>
      </div>

      <form className="space-y-4" onSubmit={handleSubmit}>
        <label
          className={`flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed px-4 py-6 text-center transition ${
            isDragging
              ? 'border-[#0B4A78] bg-sky-50'
              : 'border-slate-300 bg-slate-50 hover:border-[#0B4A78] hover:bg-sky-50'
          }`}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          <svg
            className={`mb-2 h-8 w-8 ${isDragging ? 'text-[#0B4A78]' : 'text-slate-400'}`}
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            viewBox="0 0 24 24"
          >
            <path
              d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span className={`text-base font-semibold ${isDragging ? 'text-[#0B4A78]' : 'text-[#082B49]'}`}>
            {isDragging ? 'Solte os arquivos aqui' : 'Arraste ou clique para selecionar'}
          </span>
          <span className="mt-1 text-sm text-slate-500">PDF, TXT, MD ou DOCX</span>
          <input
            accept=".pdf,.txt,.md,.docx"
            className="sr-only"
            multiple
            onChange={handleFileChange}
            type="file"
          />
        </label>

        {files.length > 0 && (
          <ul className="space-y-2">
            {files.map((selectedFile) => (
              <li
                className="flex items-center justify-between gap-2 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600"
                key={`${selectedFile.name}-${selectedFile.size}`}
              >
                <span className="truncate">{selectedFile.name}</span>
                <button
                  aria-label={`Remover ${selectedFile.name}`}
                  className="shrink-0 rounded p-0.5 text-slate-400 transition hover:bg-slate-200 hover:text-slate-700"
                  onClick={() => removeFile(selectedFile.name)}
                  type="button"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                    <path d="M6 18L18 6M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              </li>
            ))}
          </ul>
        )}

        <button
          className="min-h-11 w-full rounded-md bg-[#082B49] px-4 text-base font-semibold text-white transition hover:bg-[#0B4A78] disabled:cursor-not-allowed disabled:bg-slate-300"
          disabled={files.length === 0 || isUploading}
          type="submit"
        >
          {isUploading ? 'Processando...' : 'Enviar arquivos'}
        </button>
      </form>

      {status && (
        <p className={`mt-4 text-base ${isSuccess ? 'text-emerald-700' : 'text-amber-700'}`}>
          {status}
        </p>
      )}
    </section>
  )
}
