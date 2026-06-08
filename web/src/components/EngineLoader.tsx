import { Loader2 } from 'lucide-react'
import type { LoadingStage } from '../hooks/usePyodideDb'

const STAGE_MESSAGES: Record<NonNullable<LoadingStage>, string> = {
  'waiting-pyodide-script': 'Loading Pyodide runtime script...',
  'downloading-pyodide': 'Downloading Python engine (WebAssembly)...',
  'downloading-db-py': 'Downloading Python engine (db.py)...',
  'initializing-database': 'Initializing B-Tree database...',
}

type EngineLoaderProps = {
  stage: LoadingStage
}

export default function EngineLoader({ stage }: EngineLoaderProps) {
  if (!stage) return null

  return (
    <div className="flex items-center justify-center gap-3 border-b border-zinc-800 bg-zinc-900/80 px-6 py-3">
      <Loader2 className="h-4 w-4 animate-spin text-emerald-400" />
      <p className="text-xs text-zinc-300">
        <span className="font-medium text-emerald-400">Downloading Python Engine...</span>
        <span className="text-zinc-500"> — {STAGE_MESSAGES[stage]}</span>
      </p>
    </div>
  )
}
