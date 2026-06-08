import { BookOpen, X } from 'lucide-react'

type GuidePanelProps = {
  open: boolean
  onClose: () => void
}

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="overflow-x-auto rounded-md border border-zinc-800 bg-zinc-950 px-3 py-2 font-mono text-xs leading-relaxed text-emerald-300">
      {children}
    </pre>
  )
}

export default function GuidePanel({ open, onClose }: GuidePanelProps) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm">
      <button
        type="button"
        aria-label="Close guide"
        className="absolute inset-0 cursor-default"
        onClick={onClose}
      />

      <aside className="relative flex h-full w-full max-w-lg flex-col border-l border-zinc-800 bg-zinc-900 shadow-2xl">
        <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-emerald-400" />
            <h2 className="text-sm font-semibold text-zinc-100">How to Use B-Tree DB</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-zinc-400 transition hover:bg-zinc-800 hover:text-zinc-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-5 py-5 text-sm text-zinc-300">
          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Getting started
            </h3>
            <p className="leading-relaxed">
              This app runs a B-Tree database entirely in your browser using Pyodide (Python compiled
              to WebAssembly). Wait until the status badge shows <strong className="text-emerald-400">Engine ready</strong> before typing commands.
            </p>
          </section>

          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Layout
            </h3>
            <ul className="list-inside list-disc space-y-1 leading-relaxed text-zinc-400">
              <li>
                <span className="text-zinc-200">Terminal (left)</span> — type commands at the{' '}
                <code className="text-emerald-300">db &gt; </code> prompt
              </li>
              <li>
                <span className="text-zinc-200">Visualizer (right)</span> — live B-Tree graph
              </li>
              <li>
                <span className="text-zinc-200">Header</span> — import/export database files
              </li>
            </ul>
          </section>

          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Insert a row
            </h3>
            <CodeBlock>{'insert <id> <username> <email>'}</CodeBlock>
            <div className="mt-2 space-y-2">
              <CodeBlock>{'insert 1 alice alice@example.com\ninsert 42 bob bob@test.com'}</CodeBlock>
            </div>
          </section>

          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Select all rows
            </h3>
            <CodeBlock>select</CodeBlock>
          </section>

          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Meta-commands
            </h3>
            <div className="overflow-hidden rounded-md border border-zinc-800">
              <table className="w-full text-left text-xs">
                <thead className="bg-zinc-950 text-zinc-500">
                  <tr>
                    <th className="px-3 py-2 font-medium">Command</th>
                    <th className="px-3 py-2 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800">
                  <tr>
                    <td className="px-3 py-2 font-mono text-emerald-300">.btree</td>
                    <td className="px-3 py-2 text-zinc-400">Print text tree and refresh visualizer</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 font-mono text-emerald-300">.constants</td>
                    <td className="px-3 py-2 text-zinc-400">Show page layout constants</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 font-mono text-emerald-300">.help</td>
                    <td className="px-3 py-2 text-zinc-400">Show the command reference in the terminal</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 font-mono text-emerald-300">.exit</td>
                    <td className="px-3 py-2 text-zinc-400">Close the database and clear visualizer</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Visualizer
            </h3>
            <ul className="list-inside list-disc space-y-1 text-zinc-400">
              <li>
                <span className="text-amber-400">Amber nodes</span> — internal pages
              </li>
              <li>
                <span className="text-emerald-400">Emerald nodes</span> — leaf pages
              </li>
            </ul>
            <p className="mt-2 text-xs text-zinc-500">
              Click a node to inspect its memory map. Scroll to zoom, drag to pan.
            </p>
          </section>

          <section>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Capacity limits
            </h3>
            <div className="overflow-hidden rounded-md border border-zinc-800">
              <table className="w-full text-left text-xs">
                <tbody className="divide-y divide-zinc-800">
                  <tr>
                    <td className="px-3 py-2 text-zinc-400">Max keys per leaf page</td>
                    <td className="px-3 py-2 font-mono text-zinc-200">3</td>
                  </tr>
                  <tr>
                    <td className="px-3 py-2 text-zinc-400">Max keys per internal page</td>
                    <td className="px-3 py-2 font-mono text-zinc-200">3</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>
      </aside>
    </div>
  )
}
