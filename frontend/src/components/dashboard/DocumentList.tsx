import { formatDistanceToNow } from 'date-fns'
import type { ProgressEvent } from '../../hooks/useDocumentProgress'

interface Doc {
  id: string
  original_filename?: string
  filename: string
  status: string
  file_type: string
  file_size_bytes: number
  created_at: string
}

interface Props {
  documents: Doc[]
  loading: boolean
  selectedId: string | null
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  progressMap?: Record<string, ProgressEvent>
}

const statusColor: Record<string, string> = {
  ready: '#10b981',
  processing: '#f59e0b',
  pending: '#6b7280',
  failed: '#ef4444',
}

const statusLabel: Record<string, string> = {
  ready: '✓ Ready',
  processing: '⟳ Processing',
  pending: '· Queued',
  failed: '✗ Failed',
}

const stageColors: Record<string, string> = {
  extracting: '#6366f1',
  chunking: '#8b5cf6',
  embedding: '#06b6d4',
  analyzing: '#f59e0b',
  complete: '#10b981',
  error: '#ef4444',
}

function fmtSize(bytes: number) {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

export default function DocumentList({ documents, loading, selectedId, onSelect, onDelete, progressMap = {} }: Props) {
  if (loading) {
    return (
      <div style={{ padding: '16px' }}>
        {[1, 2, 3].map(i => (
          <div key={i} style={{ height: '64px', background: 'rgba(255,255,255,0.04)', borderRadius: '8px', marginBottom: '8px', animation: 'pulse 1.5s infinite' }} />
        ))}
      </div>
    )
  }

  if (!documents.length) {
    return (
      <div style={{ padding: '24px 16px', textAlign: 'center', color: '#374151', fontSize: '0.8rem' }}>
        No documents yet
      </div>
    )
  }

  return (
    <div style={{ padding: '8px' }}>
      <div style={{ fontSize: '0.65rem', fontFamily: 'monospace', color: '#4b5563', padding: '4px 8px 8px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
        Documents ({documents.length})
      </div>
      {documents.map(doc => {
        const progress = progressMap[doc.id]
        const isProcessing = doc.status === 'processing' || doc.status === 'pending'
        const hasProgress = isProcessing && progress

        return (
          <div
            key={doc.id}
            onClick={() => onSelect(doc.id)}
            style={{
              padding: '10px 12px',
              borderRadius: '8px',
              cursor: 'pointer',
              marginBottom: '2px',
              background: selectedId === doc.id ? 'rgba(99,102,241,0.15)' : 'transparent',
              border: `1px solid ${selectedId === doc.id ? 'rgba(99,102,241,0.3)' : 'transparent'}`,
              transition: 'all 0.1s',
              position: 'relative',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px' }}>
              <div style={{ flex: 1, overflow: 'hidden' }}>
                <div style={{
                  fontSize: '0.82rem', fontWeight: 500, color: '#e5e7eb',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
                }}>
                  {doc.original_filename || doc.filename}
                </div>
                <div style={{ display: 'flex', gap: '8px', marginTop: '4px', alignItems: 'center' }}>
                  <span style={{
                    fontSize: '0.62rem', fontFamily: 'monospace',
                    color: statusColor[doc.status] || '#6b7280',
                  }}>
                    {statusLabel[doc.status] || doc.status}
                    {doc.status === 'processing' && !progress && <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>…</span>}
                  </span>
                  <span style={{ fontSize: '0.62rem', color: '#4b5563', fontFamily: 'monospace' }}>
                    {doc.file_type.toUpperCase()} · {fmtSize(doc.file_size_bytes)}
                  </span>
                </div>

                {/* ─── Real-time Progress Bar ─── */}
                {hasProgress && (
                  <div style={{ marginTop: '8px' }}>
                    {/* Progress message */}
                    <div style={{
                      fontSize: '0.6rem',
                      color: stageColors[progress.stage] || '#818cf8',
                      marginBottom: '4px',
                      fontWeight: 500,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}>
                      {progress.message}
                    </div>

                    {/* Progress bar track */}
                    <div style={{
                      width: '100%',
                      height: '3px',
                      background: 'rgba(255,255,255,0.06)',
                      borderRadius: '2px',
                      overflow: 'hidden',
                    }}>
                      {/* Progress bar fill */}
                      <div
                        style={{
                          width: `${progress.progress}%`,
                          height: '100%',
                          background: `linear-gradient(90deg, ${stageColors[progress.stage] || '#6366f1'}, ${stageColors[progress.stage] || '#8b5cf6'}88)`,
                          borderRadius: '2px',
                          transition: 'width 0.5s ease-out',
                          position: 'relative',
                        }}
                      >
                        {/* Shimmer animation on the progress bar */}
                        <div style={{
                          position: 'absolute',
                          top: 0,
                          left: 0,
                          right: 0,
                          bottom: 0,
                          background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent)',
                          animation: 'progressShimmer 1.5s infinite',
                        }} />
                      </div>
                    </div>

                    {/* Percentage */}
                    <div style={{
                      fontSize: '0.55rem',
                      color: '#4b5563',
                      marginTop: '2px',
                      fontFamily: 'monospace',
                      textAlign: 'right',
                    }}>
                      {progress.progress}%
                    </div>
                  </div>
                )}

                {!hasProgress && (
                  <div style={{ fontSize: '0.6rem', color: '#374151', marginTop: '2px' }}>
                    {formatDistanceToNow(new Date(doc.created_at), { addSuffix: true })}
                  </div>
                )}
              </div>
              <button
                onClick={e => { e.stopPropagation(); onDelete(doc.id) }}
                style={{
                  background: 'transparent', border: 'none', color: '#4b5563',
                  cursor: 'pointer', padding: '2px 4px', fontSize: '0.75rem', borderRadius: '4px',
                  flexShrink: 0,
                }}
                title="Delete"
              >✕</button>
            </div>
          </div>
        )
      })}

      {/* Inline keyframes for shimmer */}
      <style>{`
        @keyframes progressShimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(200%); }
        }
      `}</style>
    </div>
  )
}
