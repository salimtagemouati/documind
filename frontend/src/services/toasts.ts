import toast from 'react-hot-toast'
import { getApiErrorMessage } from './api'

const MAX_VISIBLE_ERRORS = 3
const ERROR_DURATION_MS = 5000
const visibleErrors = new Map<string, number>()

function stableToastId(message: string): string {
  let hash = 0
  for (const character of message) {
    hash = ((hash << 5) - hash + character.charCodeAt(0)) | 0
  }
  return `api-error-${Math.abs(hash)}`
}

export function showErrorToast(message: string, id = stableToastId(message)): string {
  if (!visibleErrors.has(id) && visibleErrors.size >= MAX_VISIBLE_ERRORS) {
    const oldestId = visibleErrors.keys().next().value
    if (oldestId) {
      toast.dismiss(oldestId)
      window.clearTimeout(visibleErrors.get(oldestId))
      visibleErrors.delete(oldestId)
    }
  }

  const previousTimeout = visibleErrors.get(id)
  if (previousTimeout) window.clearTimeout(previousTimeout)

  toast.error(message, { id, duration: ERROR_DURATION_MS })
  const timeoutId = window.setTimeout(() => visibleErrors.delete(id), ERROR_DURATION_MS)
  visibleErrors.set(id, timeoutId)
  return message
}

export function showApiError(error: unknown, fallback: string, id?: string): string {
  const message = getApiErrorMessage(error, fallback)
  return showErrorToast(message, id)
}
