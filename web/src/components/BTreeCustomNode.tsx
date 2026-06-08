import { Handle, Position, type NodeProps } from 'reactflow'

export type BTreeNodeData = {
  label: string
  page: number
  nodeKind: 'leaf' | 'internal'
  keys: number[]
}

export default function BTreeCustomNode({ data }: NodeProps<BTreeNodeData>) {
  const isLeaf = data.nodeKind === 'leaf'

  return (
    <div
      className={`min-w-[168px] rounded-lg border-2 px-4 py-3 shadow-lg ${
        isLeaf
          ? 'border-emerald-500/60 bg-emerald-950/50'
          : 'border-amber-500/60 bg-amber-950/40'
      }`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!h-2 !w-2 !border-zinc-600 !bg-zinc-300"
      />
      <div className="text-center">
        <span
          className={`text-[10px] font-semibold uppercase tracking-wider ${
            isLeaf ? 'text-emerald-400' : 'text-amber-400'
          }`}
        >
          {isLeaf ? 'Leaf Page' : 'Internal Page'}
        </span>
        <p className="mt-0.5 font-mono text-[10px] text-zinc-500">p{data.page}</p>
        <pre className="mt-2 whitespace-pre-wrap font-mono text-xs leading-snug text-zinc-100">
          {data.label}
        </pre>
        {data.keys.length > 0 && (
          <div className="mt-2 flex flex-wrap justify-center gap-1">
            {data.keys.map((key) => (
              <span
                key={key}
                className={`rounded px-1.5 py-0.5 font-mono text-[10px] ${
                  isLeaf
                    ? 'bg-emerald-500/20 text-emerald-300'
                    : 'bg-amber-500/20 text-amber-300'
                }`}
              >
                {key}
              </span>
            ))}
          </div>
        )}
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-2 !w-2 !border-zinc-600 !bg-zinc-300"
      />
    </div>
  )
}
