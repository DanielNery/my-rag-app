import { useState } from 'react'

import './App.css'
import ChatWindow from './components/ChatWindow'
import DocumentList from './components/DocumentList'
import FileUpload from './components/FileUpload'

function App() {
  const [refreshKey, setRefreshKey] = useState(0)

  return (
    <main className="h-screen w-screen bg-slate-50 text-slate-950">
      <div className="mx-auto flex h-full w-full flex-col px-5 py-6 sm:px-8 lg:px-10">
        <header className="mb-6 flex flex-col justify-between gap-4 border-b border-slate-200 pb-5 sm:flex-row sm:items-end">
          <div>
            <p className="text-base font-semibold uppercase tracking-wide text-sky-700">
              Pipefy Assistant
            </p>
            <h1 className="mt-2 text-4xl font-semibold text-[#082B49] sm:text-5xl">
              Chat com documentos
            </h1>
          </div>

        </header>

        <section className="flex h-full w-full justify-between gap-5">
          <ChatWindow />

          <aside className="flex flex-col gap-5">
            <FileUpload onUploaded={() => setRefreshKey((value) => value + 1)} />
            <DocumentList refreshKey={refreshKey} />
          </aside>

        </section>
      </div>
    </main>
  )
}

export default App
