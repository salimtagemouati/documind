/**
 * API Service Layer
 * Single source of truth for all backend requests.
 * Axios instance with auto-injected auth token + refresh logic.
 */
import axios, { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse } from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'
const HEALTH_URL = (() => {
  if (BASE_URL.startsWith('/')) return '/health'
  const url = new URL(BASE_URL)
  url.pathname = '/health'
  url.search = ''
  url.hash = ''
  return url.toString()
})()

const sleep = (milliseconds: number, signal?: AbortSignal) => new Promise<void>((resolve, reject) => {
  const handleAbort = () => {
    window.clearTimeout(timeoutId)
    reject(new DOMException('Request aborted', 'AbortError'))
  }
  const timeoutId = window.setTimeout(() => {
    signal?.removeEventListener('abort', handleAbort)
    resolve()
  }, milliseconds)
  signal?.addEventListener('abort', handleAbort, { once: true })
})

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) return fallback
  if (!error.response) return 'Serveur injoignable, réessaie dans un instant'

  if (error.response.status === 429) {
    const retryAfter = Number(error.response.headers['retry-after'])
    const seconds = Number.isFinite(retryAfter) && retryAfter > 0 ? Math.ceil(retryAfter) : 60
    return `Trop de requêtes, réessaie dans ${seconds} s`
  }

  const detail = error.response?.data?.detail
  if (
    error.response.status === 403
    && typeof detail === 'string'
    && /demo|read.?only/i.test(detail)
  ) {
    return 'Action non disponible en mode démo'
  }
  if (typeof detail === 'string') return detail
  return fallback
}

export function getApiErrorStatus(error: unknown): number | undefined {
  return axios.isAxiosError(error) ? error.response?.status : undefined
}

export async function prewarmApi(): Promise<void> {
  try {
    await axios.get(HEALTH_URL, { timeout: 5000 })
  } catch {
    // Prewarming is intentionally silent; the demo route owns recovery UI.
  }
}

export async function waitForApi(timeoutMs = 60_000, signal?: AbortSignal): Promise<void> {
  const deadline = Date.now() + timeoutMs
  let lastError: unknown = new Error('API unavailable')

  while (Date.now() < deadline) {
    if (signal?.aborted) throw new DOMException('Request aborted', 'AbortError')
    try {
      await axios.get(HEALTH_URL, { timeout: 5000, signal })
      return
    } catch (error: unknown) {
      lastError = error
      const remaining = deadline - Date.now()
      if (remaining <= 0) break
      await sleep(Math.min(2000, remaining), signal)
    }
  }

  throw lastError
}

// ─── Axios instance ───────────────────────────────────────────────────────────
const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// Inject Bearer token on every request
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Auto-refresh on 401
api.interceptors.response.use(
  (res: AxiosResponse) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      const refresh = localStorage.getItem('refresh_token')
      if (refresh) {
        try {
          const { data } = await axios.post(`${BASE_URL}/auth/refresh`, { refresh_token: refresh })
          localStorage.setItem('access_token', data.access_token)
          localStorage.setItem('refresh_token', data.refresh_token)
          original.headers.Authorization = `Bearer ${data.access_token}`
          return api(original)
        } catch {
          localStorage.clear()
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

// ─── Auth ─────────────────────────────────────────────────────────────────────
export const authApi = {
  register: (email: string, password: string, fullName?: string) =>
    api.post('/auth/register', { email, password, full_name: fullName }),

  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),

  loginDemo: () => api.post('/auth/demo'),

  me: () => api.get('/auth/me'),
}

// ─── Documents ────────────────────────────────────────────────────────────────
export const documentsApi = {
  upload: (file: File, onProgress?: (pct: number) => void) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post('/documents/upload', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
      },
    })
  },

  list: (page = 1, pageSize = 20) =>
    api.get('/documents/', { params: { page, page_size: pageSize } }),

  get: (id: string) => api.get(`/documents/${id}`),

  getAnalysis: (id: string) => api.get(`/documents/${id}/analysis`),

  delete: (id: string) => api.delete(`/documents/${id}`),
}

// ─── Query / RAG ──────────────────────────────────────────────────────────────
export const queryApi = {
  ask: (documentId: string, question: string, maxTokens = 800) =>
    api.post('/query/', { document_id: documentId, question, max_tokens: maxTokens }),

  askMulti: (documentIds: string[], question: string, maxTokens = 1000) =>
    api.post('/query/multi', { document_ids: documentIds, question, max_tokens: maxTokens }),

  history: (documentId?: string, page = 1) =>
    api.get('/query/history', { params: { document_id: documentId, page } }),
}

// ─── Analytics ────────────────────────────────────────────────────────────────
export const analyticsApi = {
  myStats: () => api.get('/analytics/me'),
  adminStats: () => api.get('/analytics/admin'),
  evalBenchmark: () => api.get('/analytics/eval'),
}

// ─── Billing ──────────────────────────────────────────────────────────────────
export const billingApi = {
  /** Create Stripe checkout session → returns { checkout_url } */
  createCheckout: () => api.post('/billing/checkout'),

  /** Create Stripe customer portal session → returns { portal_url } */
  createPortal: () => api.post('/billing/portal'),

  /** Get current subscription status, tier, and usage limits */
  getStatus: () => api.get('/billing/status'),
}

export default api
