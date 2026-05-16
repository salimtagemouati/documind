/**
 * API Service Layer
 * Single source of truth for all backend requests.
 * Axios instance with auto-injected auth token + refresh logic.
 */
import axios, { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse } from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

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

  history: (documentId?: string, page = 1) =>
    api.get('/query/history', { params: { document_id: documentId, page } }),
}

// ─── Analytics ────────────────────────────────────────────────────────────────
export const analyticsApi = {
  myStats: () => api.get('/analytics/me'),
  adminStats: () => api.get('/analytics/admin'),
}

export default api
