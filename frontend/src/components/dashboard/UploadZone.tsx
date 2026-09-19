import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'

interface Props {
  onDrop: (file: File) => void
  loading: boolean
}

export default function UploadZone({ onDrop, loading }: Props) {
  const handleDrop = useCallback((accepted: File[]) => {
    if (accepted[0]) onDrop(accepted[0])
  }, [onDrop])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleDrop,
    accept: { 'application/pdf': ['.pdf'], 'text/plain': ['.txt'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'], 'text/markdown': ['.md'] },
    maxFiles: 1,
    disabled: loading,
  })

  return (
    <div
      {...getRootProps()}
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
      <input {...getInputProps()} />
      <div style={{ fontSize: '1.5rem', marginBottom: '8px' }}>{loading ? '⏳' : '📤'}</div>
      <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#9ca3af', marginBottom: '4px' }}>
        {loading ? 'Uploading...' : isDragActive ? 'Drop it!' : 'Upload Document'}
      </div>
      <div style={{ fontSize: '0.65rem', color: '#4b5563', fontFamily: 'monospace' }}>
        PDF · DOCX · TXT · MD · max 20MB
      </div>
    </div>
  )
}
