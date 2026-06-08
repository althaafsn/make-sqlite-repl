export async function fetchWithTimeout(
  url: string,
  options: { timeoutMs?: number; label?: string } = {},
): Promise<string> {
  const { timeoutMs = 20_000, label = url } = options
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(url, {
      signal: controller.signal,
      cache: 'no-cache',
    })

    if (!response.ok) {
      throw new Error(
        `Failed to load ${label} (${response.status} ${response.statusText}).`,
      )
    }

    return await response.text()
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error(
        `Timed out loading ${label} after ${timeoutMs / 1000}s. Check your network or CDN configuration.`,
      )
    }

    if (error instanceof TypeError) {
      throw new Error(
        `Network error while loading ${label}. The asset may be missing from the CDN or blocked by CORS.`,
      )
    }

    throw error
  } finally {
    window.clearTimeout(timeout)
  }
}

export function staticAssetUrl(filename: string): string {
  const base = import.meta.env.BASE_URL.endsWith('/')
    ? import.meta.env.BASE_URL
    : `${import.meta.env.BASE_URL}/`
  return `${base}${filename}`
}
