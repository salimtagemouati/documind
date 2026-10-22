import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, expect, it, vi } from 'vitest'
import DocumentViewer from './DocumentViewer'
import { documentsApi, queryApi } from '../../services/api'

vi.mock('../../services/api', () => ({
  documentsApi: { getAnalysis: vi.fn(), retry: vi.fn() },
  queryApi: { ask: vi.fn(), history: vi.fn() },
}))
vi.mock('../../services/toasts', () => ({ showApiError: vi.fn() }))

const doc = { id: 'doc-1', filename: 'contract.pdf', file_type: 'pdf', file_size_bytes: 100,
  status: 'ready', chunk_count: 4, token_count: 100, page_count: 4, created_at: '2026-10-20' }

function renderViewer(status = 'ready') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><DocumentViewer doc={{ ...doc, status }} /></QueryClientProvider>)
}

beforeEach(() => {
  vi.mocked(documentsApi.getAnalysis).mockResolvedValue({ data: { summary: 'Contract summary' } } as never)
})

it('shows every complete evidence passage with physical page labels', async () => {
  vi.mocked(queryApi.ask).mockResolvedValue({ data: { question: 'Warranty duration?', answer: '24 months [Source 4].',
    sources: [1, 2, 3, 4].map(n => ({ content: `Evidence passage ${n}`, chunk_index: n, page_number: n, similarity_score: .8 })),
    tokens_used: 20, latency_ms: 50, from_cache: false } } as never)
  renderViewer()
  fireEvent.click(screen.getByRole('button', { name: /Q&A/ }))
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Warranty duration?' } })
  fireEvent.click(screen.getByRole('button', { name: 'Ask' }))
  expect(await screen.findByText('Evidence passage 4')).toBeVisible()
  expect(screen.getByText('Source 4 · Page 4')).toBeVisible()
  expect(screen.getByText(/estimated tokens/)).toBeVisible()
})

it('preserves a question after a failed request and rejects short questions', async () => {
  vi.mocked(queryApi.ask).mockRejectedValue(new Error('service unavailable'))
  renderViewer()
  fireEvent.click(screen.getByRole('button', { name: /Q&A/ }))
  const input = screen.getByRole('textbox')
  fireEvent.change(input, { target: { value: 'Hi' } })
  expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled()
  fireEvent.change(input, { target: { value: 'Warranty duration?' } })
  fireEvent.click(screen.getByRole('button', { name: 'Ask' }))
  await waitFor(() => expect(input).toHaveValue('Warranty duration?'))
})

it('retries a failed original from the failed state', async () => {
  vi.mocked(documentsApi.retry).mockResolvedValue({ data: { id: doc.id, status: 'pending' } } as never)
  renderViewer('failed')
  fireEvent.click(screen.getByRole('button', { name: 'Retry processing' }))
  await waitFor(() => expect(documentsApi.retry).toHaveBeenCalledWith(doc.id))
})
