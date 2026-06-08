export type MemoryField = {
  name: string
  label: string
  description: string
  offset: number
  size: number
  rawHex: string
  value: string
}

export type MemorySection = {
  title: string
  offset: number
  size: number
  fields: MemoryField[]
}

export type MemoryBlock = {
  start: number
  end: number
  size: number
  byteRange: string
  label: string
  kind: 'header' | 'key' | 'value' | 'child' | 'waste'
  cellIndex: number | null
  value: string
  used: boolean
}

export type MemoryLayoutRow =
  | { type: 'header'; blocks: MemoryBlock[] }
  | { type: 'cell'; cellIndex: number; blocks: MemoryBlock[] }
  | { type: 'ellipsis'; start: number; end: number; byteRange: string; label: string }
  | { type: 'waste'; blocks: MemoryBlock[] }

export type PageMemory = {
  page: number
  pageSize: number
  nodeKind: 'leaf' | 'internal'
  headerSize: number
  sections: MemorySection[]
  memoryLayout?: MemoryLayoutRow[]
  error?: string
}
