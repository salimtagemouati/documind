import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'

interface Props {
  onDrop: (file: File) => void
  loading: boolean
}

export default function UploadZone({ onDrop, loading }: Props) {
  const [error, setError] = useState<string | null>(null)
  const handleDrop = useCallback((accepted: File[]) => {
    setError(null)
    if (accepted[0]) onDrop(accepted[0])
  }, [onDrop])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleDrop,
    accept: { 'application/pdf': ['.pdf'], 'text/plain': ['.txt'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'], 'text/markdown': ['.md'] },
    maxFiles: 1,
    maxSize: 20 * 1024 * 1024,
    onDropRejected: (rejected) => setError(rejected[0]?.errors[0]?.message || 'This file cannot be uploaded.'),
    disabled: loading,
  })

  return (
    <div
      {...getRootProps({ role: 'button', 'aria-label': 'Upload document' })}
      style={{
        border: `2px dashed ${isDragActive ? '#6366f1' : 'rgba(255,255,255,0.1)'}`,
        borderRadius: '10px',
        padding: '20px 16px',
        textAlign: 'center',
        cursor: loading ? 'not-allowed' : 'pointer',
        background: isDragActive ? 'rgba(99,102,241,0.08)' : 'transparent',
        transition: 'all 0.15s',
        opacity: loading ? 0.6 : 1,
      }}
    >
      <input {...getInputProps({ 'aria-label': 'Choose document file' })} />
      <div style={{ fontSize: '1.5rem', marginBottom: '8px' }}>{loading ? '⏳' : '📤'}</div>
      <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#9ca3af', marginBottom: '4px' }}>
        {loading ? 'Uploading...' : isDragActive ? 'Drop it!' : 'Upload Document'}
      </div>
      <div style={{ fontSize: '0.65rem', color: '#4b5563', fontFamily: 'monospace' }}>
        PDF · DOCX · TXT · MD · max 20MB
      </div>
      {error && <p role="alert" style={{ color: '#fca5a5', fontSize: '0.8rem', marginTop: '10px' }}>{error}</p>}
    </div>
  )
}
