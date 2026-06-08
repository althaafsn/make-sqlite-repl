import { X } from 'lucide-react'
import type { PageMemory } from '../types/pageMemory'
import PageMemoryMap from './PageMemoryMap'

type PageMemoryPanelProps = {
  memory: PageMemory | null
  loading: boolean
  onClose: () => void
}

export default function PageMemoryPanel({ memory, loading, onClose }: PageMemoryPanelProps) {
  if (!memory && !loading) return null

  const isLeaf = memory?.nodeKind === 'leaf'
  const accent = isLeaf ? 'text-emerald-400' : 'text-amber-400'
  const border = isLeaf ? 'border-emerald-500/30' : 'border-amber-500/30'

  return (
    <div className={`flex max-h-[50%] min-h-[220px] flex-col border-t ${border} bg-zinc-900`}>
      <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-2">
        <div className="flex items-center gap-2 text-xs">
          <span className={`font-semibold uppercase tracking-wider ${accent}`}>
            Page Memory Map
          </span>
          {memory && (
            <span className="font-mono text-zinc-400">
              p{memory.page} · {memory.nodeKind} · {memory.pageSize} bytes
            </span>
          )}
          {loading && <span className="text-zinc-500">Loading...</span>}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md p-1 text-zinc-400 transition hover:bg-zinc-800 hover:text-zinc-100"
          aria-label="Close page memory panel"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
        {memory?.error && <p className="text-xs text-red-300">{memory.error}</p>}

        {memory && !memory.error && memory.memoryLayout && (
          <PageMemoryMap layout={memory.memoryLayout} pageSize={memory.pageSize} />
        )}

        {memory && !memory.error && memory.sections.length > 0 && (
          <details className="mt-3 text-xs text-zinc-500">
            <summary className="cursor-pointer select-none text-zinc-400 hover:text-zinc-200">
              Field reference (offsets &amp; hex)
            </summary>
            <div className="mt-2 space-y-3">
              {memory.sections.map((section) => (
                <div key={`${section.title}-${section.offset}`}>
                  <p className="mb-1 font-medium text-zinc-300">{section.title}</p>
                  <div className="overflow-hidden rounded border border-zinc-800">
                    <table className="w-full text-left text-[10px]">
                      <tbody className="divide-y divide-zinc-800">
                        {section.fields.map((field) => (
                          <tr key={field.name}>
                            <td className="px-2 py-1 font-mono text-zinc-500">{field.offset}</td>
                            <td className="px-2 py-1 text-zinc-300">{field.label}</td>
                            <td className="px-2 py-1 font-mono text-emerald-300">{field.value}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  )
}
