import type { MemoryBlock, MemoryLayoutRow } from '../types/pageMemory'

const HEADER_COLORS: Record<string, string> = {
  node_type: 'bg-rose-300/90 text-rose-950',
  is_root: 'bg-lime-300/90 text-lime-950',
  parent_pointer: 'bg-violet-300/90 text-violet-950',
  num_cells: 'bg-orange-300/90 text-orange-950',
  num_keys: 'bg-orange-300/90 text-orange-950',
  next_leaf: 'bg-cyan-300/90 text-cyan-950',
  right_child: 'bg-cyan-300/90 text-cyan-950',
}

const CELL_PALETTE = [
  { key: 'bg-red-400/85 text-red-950', value: 'bg-red-500/80 text-red-50', child: 'bg-red-300/90 text-red-950' },
  { key: 'bg-sky-300/90 text-sky-950', value: 'bg-sky-500/80 text-sky-50', child: 'bg-sky-300/90 text-sky-950' },
  { key: 'bg-pink-300/90 text-pink-950', value: 'bg-pink-500/80 text-pink-50', child: 'bg-pink-300/90 text-pink-950' },
  { key: 'bg-amber-300/90 text-amber-950', value: 'bg-amber-500/80 text-amber-50', child: 'bg-amber-300/90 text-amber-950' },
]

function blockColor(block: MemoryBlock): string {
  if (block.kind === 'waste') return 'bg-zinc-500/70 text-zinc-100'
  if (block.kind === 'header') return HEADER_COLORS[block.label] ?? 'bg-zinc-400/80 text-zinc-900'
  const palette = CELL_PALETTE[(block.cellIndex ?? 0) % CELL_PALETTE.length]
  return palette[block.kind as 'key' | 'value' | 'child']
}

function MemoryBlockView({ block, pageSize }: { block: MemoryBlock; pageSize: number }) {
  const widthPercent = (block.size / pageSize) * 100
  const isLarge = block.size > 32
  const color = blockColor(block)

  return (
    <div
      title={block.value ? `${block.label}: ${block.value}` : block.label}
      className={`flex flex-col justify-between border border-black/10 px-2 py-1.5 text-center ${color} ${
        block.used ? '' : 'opacity-50'
      } ${isLarge ? 'min-h-[72px]' : 'min-h-[52px]'}`}
      style={{
        flexGrow: block.size,
        flexShrink: 0,
        flexBasis: `${Math.max(widthPercent, block.kind === 'header' ? 6 : 8)}%`,
        minWidth: block.kind === 'header' ? '56px' : '72px',
      }}
    >
      <span className="font-mono text-[10px] font-medium leading-tight">{block.byteRange}</span>
      <span className="font-mono text-[11px] font-semibold leading-tight">{block.label}</span>
      {block.value && (
        <span className="truncate font-mono text-[9px] leading-tight opacity-90">{block.value}</span>
      )}
      {isLarge && !block.value && <span className="text-lg leading-none opacity-60">…</span>}
    </div>
  )
}

function HeaderRow({ blocks, pageSize }: { blocks: MemoryBlock[]; pageSize: number }) {
  return (
    <div className="flex w-full flex-wrap">
      {blocks.map((block) => (
        <MemoryBlockView key={`${block.start}-${block.label}`} block={block} pageSize={pageSize} />
      ))}
    </div>
  )
}

function CellRow({ blocks, pageSize }: { blocks: MemoryBlock[]; pageSize: number }) {
  return (
    <div className="flex w-full">
      {blocks.map((block) => (
        <MemoryBlockView key={`${block.start}-${block.label}`} block={block} pageSize={pageSize} />
      ))}
    </div>
  )
}

function EllipsisRow({ row }: { row: Extract<MemoryLayoutRow, { type: 'ellipsis' }> }) {
  return (
    <div className="flex w-full items-center gap-2 rounded border border-zinc-700 bg-zinc-800/80 px-4 py-3">
      <span className="font-mono text-[10px] text-zinc-500">{row.byteRange}</span>
      <span className="flex-1 text-center font-mono text-sm tracking-widest text-zinc-400">• • •</span>
      <span className="font-mono text-[11px] text-zinc-400">{row.label}</span>
    </div>
  )
}

type PageMemoryMapProps = {
  layout: MemoryLayoutRow[]
  pageSize: number
}

export default function PageMemoryMap({ layout, pageSize }: PageMemoryMapProps) {
  return (
    <div className="space-y-1.5 rounded-lg border border-zinc-700 bg-zinc-950 p-2">
      {layout.map((row, index) => {
        if (row.type === 'header') {
          return <HeaderRow key={`header-${index}`} blocks={row.blocks} pageSize={pageSize} />
        }
        if (row.type === 'cell') {
          return <CellRow key={`cell-${row.cellIndex}`} blocks={row.blocks} pageSize={pageSize} />
        }
        if (row.type === 'ellipsis') {
          return <EllipsisRow key={`ellipsis-${index}`} row={row} />
        }
        if (row.type === 'waste') {
          return (
            <div key={`waste-${index}`} className="flex w-full">
              {row.blocks.map((block) => (
                <MemoryBlockView key={`${block.start}-waste`} block={block} pageSize={pageSize} />
              ))}
            </div>
          )
        }
        return null
      })}
    </div>
  )
}
