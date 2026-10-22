import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import UploadZone from './UploadZone'

it('passes a supported file to the upload action', async () => {
  const upload = vi.fn()
  render(<UploadZone onDrop={upload} loading={false} />)
  const file = new File(['Warranty lasts 24 months.'], 'terms.txt', { type: 'text/plain' })
  fireEvent.change(screen.getByLabelText('Choose document file'), { target: { files: [file] } })
  await waitFor(() => expect(upload).toHaveBeenCalledWith(file))
})

it('explains rejected files without calling upload', async () => {
  const upload = vi.fn()
  render(<UploadZone onDrop={upload} loading={false} />)
  fireEvent.change(screen.getByLabelText('Choose document file'), {
    target: { files: [new File(['binary'], 'program.exe', { type: 'application/octet-stream' })] },
  })
  expect(await screen.findByRole('alert')).toBeVisible()
  expect(upload).not.toHaveBeenCalled()
})
