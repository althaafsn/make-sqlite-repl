import { useEffect, useRef } from 'react'
import { FitAddon } from '@xterm/addon-fit'
import { Terminal as XTerm } from 'xterm'
import { TERMINAL_QUICK_REFERENCE, TERMINAL_WELCOME } from '../lib/terminalGuide'
import 'xterm/css/xterm.css'

const PROMPT = 'db > '

type TerminalProps = {
  onCommand: (cmd: string) => Promise<string> | string
  isReady: boolean
}

export default function Terminal({ onCommand, isReady }: TerminalProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const termRef = useRef<XTerm | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)
  const bufferRef = useRef('')
  const onCommandRef = useRef(onCommand)
  const isReadyRef = useRef(isReady)
  const readyAnnouncedRef = useRef(false)

  onCommandRef.current = onCommand
  isReadyRef.current = isReady

  useEffect(() => {
    if (!containerRef.current) return

    const term = new XTerm({
      cursorBlink: true,
      convertEol: true,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      fontSize: 14,
      theme: {
        background: '#09090b',
        foreground: '#e4e4e7',
        cursor: '#34d399',
        selectionBackground: '#3f3f46',
      },
    })

    const fitAddon = new FitAddon()
    term.loadAddon(fitAddon)
    term.open(containerRef.current)
    fitAddon.fit()

    termRef.current = term
    fitAddonRef.current = fitAddon

    TERMINAL_WELCOME.forEach((line) => term.writeln(line))
    if (!isReadyRef.current) {
      term.writeln('Waiting for Pyodide to initialize...')
    }
    term.write(PROMPT)

    const dataDisposable = term.onData(async (data) => {
      if (!isReadyRef.current) return

      if (data === '\r') {
        const command = bufferRef.current
        bufferRef.current = ''
        term.write('\r\n')

        try {
          const output = await onCommandRef.current(command)
          if (output) {
            output.replace(/\r?\n$/, '').split('\n').forEach((line) => term.writeln(line))
          }
        } catch (error) {
          const message = error instanceof Error ? error.message : String(error)
          term.writeln(`Error: ${message}`)
        }

        term.write(PROMPT)
        return
      }

      if (data === '\x7f') {
        if (bufferRef.current.length > 0) {
          bufferRef.current = bufferRef.current.slice(0, -1)
          term.write('\b \b')
        }
        return
      }

      if (data >= ' ') {
        bufferRef.current += data
        term.write(data)
      }
    })

    const resizeObserver = new ResizeObserver(() => {
      fitAddonRef.current?.fit()
    })
    resizeObserver.observe(containerRef.current)

    return () => {
      dataDisposable.dispose()
      resizeObserver.disconnect()
      term.dispose()
      termRef.current = null
      fitAddonRef.current = null
    }
  }, [])

  useEffect(() => {
    const term = termRef.current
    if (!term || !isReady || readyAnnouncedRef.current) return

    readyAnnouncedRef.current = true
    TERMINAL_QUICK_REFERENCE.forEach((line) => term.writeln(line))
    term.write(PROMPT)
  }, [isReady])

  return <div ref={containerRef} className="h-full w-full p-2" />
}
