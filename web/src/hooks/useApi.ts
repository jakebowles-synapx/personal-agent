import { useCallback, useState } from 'react'

interface FetchOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
}

export function useApi() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchApi = useCallback(async <T>(
    url: string,
    options: FetchOptions = {}
  ): Promise<T | null> => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(url, {
        method: options.method || 'GET',
        headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
        body: options.body ? JSON.stringify(options.body) : undefined,
      })

      if (!response.ok) {
        if (response.status === 204) {
          return null as T
        }
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Request failed: ${response.status}`)
      }

      if (response.status === 204) {
        return null as T
      }

      return await response.json()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'An error occurred'
      setError(message)
      console.error('API error:', err)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  return { fetchApi, loading, error }
}
