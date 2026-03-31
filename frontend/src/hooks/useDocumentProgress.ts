import { useEffect, useRef, useState, useCallback } from 'react'

export interface ProgressEvent {
  stage: 'extracting' | 'chunking' | 'embedding' | 'analyzing' | 'complete' | 'error' | 'waiting'
  progress: number
  message: string
  document_id?: string
}

interface UseDocumentProgressOptions {
  documentId: string | null
  enabled?: boolean
  onComplete?: () => void
  onError?: (message: string) => void
}

/**
 * Hook for real-time document processing progress via WebSocket.
 *
 * Connects to the backend WebSocket endpoint and receives processing
 * stage updates. Automatically reconnects on failure (up to 3 attempts).
 *
 * Usage:
 *   const { progress, stage, message, isConnected } = useDocumentProgress({
 *     documentId: doc.id,
 *     enabled: doc.status === 'processing' || doc.status === 'pending',
 *     onComplete: () => queryClient.invalidateQueries(['documents']),
 *   })
 */
export function useDocumentProgress({
  documentId,
  enabled = true,
  onComplete,
  onError,
}: UseDocumentProgressOptions) {
  const [event, setEvent] = useState<ProgressEvent | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const retryCountRef = useRef(0)
  const retryTimerRef = useRef<number | null>(null)
  const maxRetries = 3

  const connect = useCallback(() => {
    if (!documentId || !enabled) return

    const token = localStorage.getItem('access_token')
    if (!token) return

    // Build WebSocket URL
    const apiUrl = import.meta.env.VITE_API_URL || ''
    let wsBase: string

    if (apiUrl) {
      // Production: VITE_API_URL is like https://api.example.com/api/v1
      wsBase = apiUrl.replace(/^http/, 'ws')
    } else {
      // Local dev: use the current host (Vite proxy doesn't support WS, connect directly)
      wsBase = `ws://localhost:8000/api/v1`
    }

    const wsUrl = `${wsBase}/ws/documents/${documentId}?token=${token}`

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        retryCountRef.current = 0
      }

      ws.onmessage = (e) => {
        try {
          const data: ProgressEvent = JSON.parse(e.data)
          setEvent(data)

          if (data.stage === 'complete') {
            onComplete?.()
          } else if (data.stage === 'error') {
            onError?.(data.message)
          }
        } catch {
          // Ignore malformed messages
        }
      }

      ws.onclose = (e) => {
        setIsConnected(false)
        wsRef.current = null

        // Don't retry on normal closure or auth failure
        if (e.code === 4001 || e.code === 1000) return

        // Retry with backoff
        if (retryCountRef.current < maxRetries) {
          const delay = Math.min(1000 * Math.pow(2, retryCountRef.current), 5000)
          retryCountRef.current += 1
          retryTimerRef.current = window.setTimeout(connect, delay)
        }
      }

      ws.onerror = () => {
        // onclose will fire after onerror, so handle retry there
      }
    } catch {
      // WebSocket constructor can throw in some environments
    }
  }, [documentId, enabled, onComplete, onError])

  useEffect(() => {
    connect()

    return () => {
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close(1000)
        wsRef.current = null
      }
      setIsConnected(false)
    }
  }, [connect])

  return {
    event,
    stage: event?.stage ?? null,
    progress: event?.progress ?? 0,
    message: event?.message ?? '',
    isConnected,
  }
}


/**
 * Manages WebSocket progress for multiple documents simultaneously.
 * Tracks progress for all documents that are in pending/processing state.
 */
export function useMultiDocumentProgress(
  documents: Array<{ id: string; status: string }>,
  onDocumentComplete?: () => void,
) {
  const [progressMap, setProgressMap] = useState<Record<string, ProgressEvent>>({})
  const wsMapRef = useRef<Record<string, WebSocket>>({})
  const cleanedUpRef = useRef(new Set<string>())

  useEffect(() => {
    const processingDocs = documents.filter(
      (d) => (d.status === 'pending' || d.status === 'processing') && !cleanedUpRef.current.has(d.id)
    )

    const token = localStorage.getItem('access_token')
    if (!token) return

    // Build WebSocket base URL
    const apiUrl = import.meta.env.VITE_API_URL || ''
    let wsBase: string
    if (apiUrl) {
      wsBase = apiUrl.replace(/^http/, 'ws')
    } else {
      wsBase = `ws://localhost:8000/api/v1`
    }

    for (const doc of processingDocs) {
      // Skip if already connected
      if (wsMapRef.current[doc.id]) continue

      const wsUrl = `${wsBase}/ws/documents/${doc.id}?token=${token}`
      try {
        const ws = new WebSocket(wsUrl)
        wsMapRef.current[doc.id] = ws

        ws.onmessage = (e) => {
          try {
            const data: ProgressEvent = JSON.parse(e.data)
            setProgressMap((prev) => ({ ...prev, [doc.id]: data }))

            if (data.stage === 'complete') {
              onDocumentComplete?.()
              cleanedUpRef.current.add(doc.id)
            } else if (data.stage === 'error') {
              cleanedUpRef.current.add(doc.id)
            }
          } catch {
            // ignore
          }
        }

        ws.onclose = () => {
          delete wsMapRef.current[doc.id]
        }
      } catch {
        // ignore
      }
    }

    return () => {
      // Close all WebSocket connections on unmount
      Object.values(wsMapRef.current).forEach((ws) => {
        try { ws.close(1000) } catch { /* ignore */ }
      })
      wsMapRef.current = {}
    }
  }, [documents, onDocumentComplete])

  return progressMap
}
