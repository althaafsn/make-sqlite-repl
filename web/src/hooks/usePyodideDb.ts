import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchWithTimeout, staticAssetUrl } from '../lib/fetchWithTimeout'
import type { PageMemory } from '../types/pageMemory'
import type { PyodideInterface } from '../types/pyodide'

const PYODIDE_INDEX_URL = 'https://cdn.jsdelivr.net/pyodide/v0.25.0/full/'
const DB_PATH = '/db.db'
const DB_PY_URL = staticAssetUrl('db.py')

export type TreeGraph = {
  nodes: any[]
  edges: any[]
}

export type PyodideDbStatus = 'idle' | 'loading' | 'ready' | 'error'

export type LoadingStage =
  | 'waiting-pyodide-script'
  | 'downloading-pyodide'
  | 'downloading-db-py'
  | 'initializing-database'
  | null

function waitForLoadPyodide(timeoutMs = 30_000): Promise<void> {
  return new Promise((resolve, reject) => {
    const started = Date.now()

    const check = () => {
      if (typeof window.loadPyodide === 'function') {
        resolve()
        return
      }
      if (Date.now() - started > timeoutMs) {
        reject(new Error('Timed out waiting for the Pyodide script.'))
        return
      }
      requestAnimationFrame(check)
    }

    check()
  })
}

export function usePyodideDb() {
  const pyodideRef = useRef<PyodideInterface | null>(null)
  const [status, setStatus] = useState<PyodideDbStatus>('idle')
  const [loadingStage, setLoadingStage] = useState<LoadingStage>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      setStatus('loading')
      setError(null)

      try {
        setLoadingStage('waiting-pyodide-script')
        await waitForLoadPyodide()
        if (cancelled) return

        setLoadingStage('downloading-pyodide')
        const pyodide = await window.loadPyodide!({ indexURL: PYODIDE_INDEX_URL })
        if (cancelled) return

        setLoadingStage('downloading-db-py')
        const dbSource = await fetchWithTimeout(DB_PY_URL, {
          timeoutMs: 20_000,
          label: 'db.py',
        })
        if (cancelled) return

        setLoadingStage('initializing-database')
        await pyodide.runPythonAsync(dbSource)
        pyodide.globals.set('_db_path', DB_PATH)
        await pyodide.runPythonAsync('init_database(_db_path)')

        pyodideRef.current = pyodide
        setLoadingStage(null)
        setStatus('ready')
      } catch (bootstrapError) {
        if (cancelled) return
        const message =
          bootstrapError instanceof Error ? bootstrapError.message : String(bootstrapError)
        setError(message)
        setLoadingStage(null)
        setStatus('error')
      }
    }

    bootstrap()

    return () => {
      cancelled = true
    }
  }, [])

  const ensureOpen = useCallback(async () => {
    const pyodide = pyodideRef.current
    if (!pyodide) throw new Error('Pyodide is not ready.')

    pyodide.globals.set('_db_path', DB_PATH)
    await pyodide.runPythonAsync('init_database(_db_path)')
  }, [])

  const executeCommand = useCallback(
    async (cmd: string): Promise<string> => {
      const pyodide = pyodideRef.current
      if (!pyodide) throw new Error('Pyodide is not ready.')

      pyodide.globals.set('_cmd', cmd)
      let output = String(await pyodide.runPythonAsync('execute_command(_cmd)'))

      if (output.includes('Database not open. Call init_database() first.')) {
        await ensureOpen()
        pyodide.globals.set('_cmd', cmd)
        output = String(await pyodide.runPythonAsync('execute_command(_cmd)'))
      }

      return output
    },
    [ensureOpen],
  )

  const getTreeGraph = useCallback(async (): Promise<TreeGraph> => {
    const pyodide = pyodideRef.current
    if (!pyodide) return { nodes: [], edges: [] }

    const json = await pyodide.runPythonAsync('get_tree_json()')
    return JSON.parse(String(json)) as TreeGraph
  }, [])

  const importDatabase = useCallback(
    async (file: File): Promise<TreeGraph> => {
      const pyodide = pyodideRef.current
      if (!pyodide) throw new Error('Pyodide is not ready.')

      const bytes = new Uint8Array(await file.arrayBuffer())
      pyodide.FS.writeFile(DB_PATH, bytes)
      await ensureOpen()
      return getTreeGraph()
    },
    [ensureOpen, getTreeGraph],
  )

  const exportDatabase = useCallback(async (): Promise<Uint8Array> => {
    const pyodide = pyodideRef.current
    if (!pyodide) throw new Error('Pyodide is not ready.')

    await pyodide.runPythonAsync('flush_database()')
    return pyodide.FS.readFile(DB_PATH)
  }, [])

  const getPageMemory = useCallback(async (pageNum: number): Promise<PageMemory> => {
    const pyodide = pyodideRef.current
    if (!pyodide) return { error: 'Pyodide is not ready.', page: pageNum, pageSize: 0, nodeKind: 'leaf', headerSize: 0, sections: [] }

    pyodide.globals.set('_page_num', pageNum)
    const json = await pyodide.runPythonAsync('get_page_memory_json(_page_num)')
    return JSON.parse(String(json)) as PageMemory
  }, [])

  return {
    status,
    loadingStage,
    error,
    isReady: status === 'ready',
    executeCommand,
    getTreeGraph,
    getPageMemory,
    importDatabase,
    exportDatabase,
  }
}
