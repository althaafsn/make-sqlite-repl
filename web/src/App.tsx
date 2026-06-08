import { useCallback, useEffect, useRef, useState, type ChangeEvent } from 'react'
import { BookOpen, Database, Download, TerminalSquare, Upload, Workflow } from 'lucide-react'
import EngineLoader from './components/EngineLoader'
import GuidePanel from './components/GuidePanel'
import PageMemoryPanel from './components/PageMemoryPanel'
import Terminal from './components/Terminal'
import Visualizer from './components/Visualizer'
import { usePyodideDb } from './hooks/usePyodideDb'
import type { PageMemory } from './types/pageMemory'

function shouldRefreshTree(cmd: string): boolean {
  const trimmed = cmd.trim()
  if (!trimmed || trimmed === 'select' || trimmed === '.constants' || trimmed === '.help' || trimmed === '.exit') {
    return false
  }
  return true
}

function App() {
  const {
    status,
    loadingStage,
    error,
    isReady,
    executeCommand,
    getTreeGraph,
    getPageMemory,
    importDatabase,
    exportDatabase,
  } = usePyodideDb()
  const [nodes, setNodes] = useState<any[]>([])
  const [edges, setEdges] = useState<any[]>([])
  const [guideOpen, setGuideOpen] = useState(false)
  const [selectedPage, setSelectedPage] = useState<number | null>(null)
  const [pageMemory, setPageMemory] = useState<PageMemory | null>(null)
  const [memoryLoading, setMemoryLoading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!isReady) return

    getTreeGraph()
      .then((graph) => {
        setNodes(graph.nodes)
        setEdges(graph.edges)
      })
      .catch(() => {
        setNodes([])
        setEdges([])
      })
  }, [isReady, getTreeGraph])

  const refreshTree = useCallback(async () => {
    const graph = await getTreeGraph()
    setNodes(graph.nodes)
    setEdges(graph.edges)
  }, [getTreeGraph])

  const handlePageSelect = useCallback(
    async (page: number) => {
      setSelectedPage(page)
      setMemoryLoading(true)
      try {
        const memory = await getPageMemory(page)
        setPageMemory(memory)
      } catch {
        setPageMemory({
          page,
          pageSize: 4096,
          nodeKind: 'leaf',
          headerSize: 0,
          sections: [],
          error: 'Failed to load page memory.',
        })
      } finally {
        setMemoryLoading(false)
      }
    },
    [getPageMemory],
  )

  const handleCloseMemory = useCallback(() => {
    setSelectedPage(null)
    setPageMemory(null)
  }, [])

  const handleCommand = useCallback(
    async (cmd: string): Promise<string> => {
      const trimmed = cmd.trim()

      if (trimmed === '.exit') {
        const output = await executeCommand(cmd)
        setNodes([])
        setEdges([])
        handleCloseMemory()
        return output
      }

      const output = await executeCommand(cmd)

      if (shouldRefreshTree(cmd)) {
        await refreshTree()
        if (selectedPage !== null) {
          const memory = await getPageMemory(selectedPage)
          setPageMemory(memory)
        }
      }

      return output
    },
    [executeCommand, refreshTree, handleCloseMemory, selectedPage, getPageMemory],
  )

  const handleImportClick = () => {
    fileInputRef.current?.click()
  }

  const handleImportFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    try {
      const graph = await importDatabase(file)
      setNodes(graph.nodes)
      setEdges(graph.edges)
    } catch (importError) {
      const message = importError instanceof Error ? importError.message : String(importError)
      window.alert(`Import failed: ${message}`)
    }
  }

  const handleExport = async () => {
    try {
      const data = await exportDatabase()
      const blob = new Blob([Uint8Array.from(data)], { type: 'application/octet-stream' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = 'db.db'
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (exportError) {
      const message = exportError instanceof Error ? exportError.message : String(exportError)
      window.alert(`Export failed: ${message}`)
    }
  }

  const statusLabel =
    status === 'ready'
      ? 'Engine ready'
      : status === 'loading'
        ? 'Downloading Python Engine...'
        : status === 'error'
          ? 'Engine error'
          : 'Starting...'

  const statusClass =
    status === 'ready'
      ? 'bg-emerald-500/10 text-emerald-400'
      : status === 'error'
        ? 'bg-red-500/10 text-red-400'
        : 'bg-amber-500/10 text-amber-400'

  return (
    <div className="flex h-full min-h-screen flex-col">
      <header className="flex items-center justify-between border-b border-zinc-800 bg-zinc-900 px-6 py-4">
        <div className="flex items-center gap-3">
          <Database className="h-5 w-5 text-emerald-400" />
          <div>
            <h1 className="text-sm font-semibold text-zinc-100">B-Tree DB</h1>
            <p className="text-xs text-zinc-500">Client-side engine via Pyodide</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept=".db,application/octet-stream"
            className="hidden"
            onChange={handleImportFile}
          />
          <button
            type="button"
            onClick={() => setGuideOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:bg-zinc-700"
          >
            <BookOpen className="h-3.5 w-3.5" />
            Guide
          </button>
          <button
            type="button"
            onClick={handleImportClick}
            disabled={!isReady}
            className="inline-flex items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Upload className="h-3.5 w-3.5" />
            Import .db
          </button>
          <button
            type="button"
            onClick={handleExport}
            disabled={!isReady}
            className="inline-flex items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" />
            Export .db
          </button>
          <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusClass}`}>
            {statusLabel}
          </span>
        </div>
      </header>

      <EngineLoader stage={loadingStage} />

      {error && (
        <div className="border-b border-red-900/50 bg-red-950/40 px-6 py-2 text-xs text-red-300">
          {error}
        </div>
      )}

      <main className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-2">
        <section className="flex min-h-[360px] min-h-0 flex-col border-b border-zinc-800 lg:border-r lg:border-b-0">
          <div className="flex items-center gap-2 border-b border-zinc-800 px-4 py-3 text-sm text-zinc-400">
            <TerminalSquare className="h-4 w-4" />
            Terminal
          </div>
          <div className="min-h-0 flex-1 bg-zinc-950">
            <Terminal onCommand={handleCommand} isReady={isReady} />
          </div>
        </section>

        <section className="flex min-h-[360px] min-h-0 flex-col">
          <div className="flex items-center gap-2 border-b border-zinc-800 px-4 py-3 text-sm text-zinc-400">
            <Workflow className="h-4 w-4" />
            B-Tree Visualizer
            <span className="ml-auto text-xs text-zinc-600">Click a node to inspect page memory</span>
          </div>
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="min-h-0 flex-1">
              <Visualizer
                nodes={nodes}
                edges={edges}
                selectedPage={selectedPage}
                onPageSelect={handlePageSelect}
              />
            </div>
            {(selectedPage !== null || memoryLoading) && (
              <PageMemoryPanel
                memory={pageMemory}
                loading={memoryLoading}
                onClose={handleCloseMemory}
              />
            )}
          </div>
        </section>
      </main>

      <GuidePanel open={guideOpen} onClose={() => setGuideOpen(false)} />
    </div>
  )
}

export default App
