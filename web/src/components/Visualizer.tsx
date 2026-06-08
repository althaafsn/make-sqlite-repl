import { useMemo } from 'react'
import ReactFlow, { Background, Controls, type NodeMouseHandler } from 'reactflow'
import BTreeCustomNode from './BTreeCustomNode'
import 'reactflow/dist/style.css'

type VisualizerProps = {
  nodes: any[]
  edges: any[]
  selectedPage: number | null
  onPageSelect: (page: number) => void
}

export default function Visualizer({ nodes, edges, selectedPage, onPageSelect }: VisualizerProps) {
  const nodeTypes = useMemo(() => ({ customNode: BTreeCustomNode }), [])

  const flowNodes = useMemo(
    () =>
      nodes.map((node) => ({
        ...node,
        selected: node.data?.page === selectedPage,
      })),
    [nodes, selectedPage],
  )

  const handleNodeClick: NodeMouseHandler = (_event, node) => {
    if (typeof node.data?.page === 'number') {
      onPageSelect(node.data.page)
    }
  }

  return (
    <div className="h-full w-full bg-zinc-950">
      <ReactFlow
        nodes={flowNodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#3f3f46" gap={20} size={1} />
        <Controls
          showInteractive={false}
          className="!rounded-md !border-zinc-700 !bg-zinc-900 !shadow-lg [&>button]:!border-zinc-700 [&>button]:!bg-zinc-800 [&>button]:!fill-zinc-300 [&>button:hover]:!bg-zinc-700"
        />
      </ReactFlow>
    </div>
  )
}
