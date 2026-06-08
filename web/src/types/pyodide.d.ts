export interface PyodideFS {
  writeFile(path: string, data: string | Uint8Array): void
  readFile(path: string): Uint8Array
}

export interface PyodideGlobals {
  set(name: string, value: unknown): void
  get(name: string): unknown
}

export interface PyodideInterface {
  FS: PyodideFS
  globals: PyodideGlobals
  runPythonAsync(code: string): Promise<unknown>
  loadPackagesFromImports(code: string): Promise<void>
}

export interface LoadPyodideOptions {
  indexURL?: string
}

declare global {
  interface Window {
    loadPyodide?: (options?: LoadPyodideOptions) => Promise<PyodideInterface>
  }
}

export {}
