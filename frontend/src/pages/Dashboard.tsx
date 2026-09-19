import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { documentsApi, analyticsApi, billingApi, getApiErrorMessage, getApiErrorStatus } from '../services/api'
import { useAuthStore } from '../store/authStore'
import { useMultiDocumentProgress } from '../hooks/useDocumentProgress'
import UploadZone from '../components/dashboard/UploadZone'
import DocumentList from '../components/dashboard/DocumentList'
import DocumentViewer from '../components/dashboard/DocumentViewer'
import MultiDocViewer from '../components/dashboard/MultiDocViewer'
import EvalModal from '../components/dashboard/EvalModal'
import StatsBar from '../components/dashboard/StatsBar'
import UpgradePrompt from '../components/dashboard/UpgradePrompt'
import toast from 'react-hot-toast'
import type { DocumentItem } from '../types'

export default function Dashboard() {
  const { user, logout } = useAuthStore()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([])
  const [showEval, setShowEval] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [upgradePrompt, setUpgradePrompt] = useState<'documents' | 'queries' | null>(null)

  // Fetch documents
  const { data: docsData, isLoading: docsLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: () => documentsApi.list().then(r => r.data),
    refetchInterval: 10_000,
  })

  // Fetch user stats
  const { data: stats } = useQuery({
    queryKey: ['myStats'],
    queryFn: () => analyticsApi.myStats().then(r => r.data),
  })

  // Fetch billing status (for tier badge + limit checking)
  const { data: billingStatus } = useQuery({
    queryKey: ['billingStatus'],
    queryFn: () => billingApi.getStatus().then(r => r.data),
    staleTime: 60_000,
  })

  const documents = docsData?.items || []
  const isPro = billingStatus?.is_pro ?? false
  const isDemo = user?.is_demo ?? false

  // ─── WebSocket progress for all processing documents ───────────────────
  const progressMap = useMultiDocumentProgress(
    documents,
    () => {
      qc.invalidateQueries({ queryKey: ['documents'] })
      qc.invalidateQueries({ queryKey: ['myStats'] })
    },
  )

  // Upload mutation — shows upgrade prompt on 429
  const uploadMutation = useMutation({
    mutationFn: (file: File) => documentsApi.upload(file),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['documents'] })
      qc.invalidateQueries({ queryKey: ['billingStatus'] })
      toast.success(`"${res.data.filename}" uploaded — processing started`)
      setSelectedDocIds([res.data.id])
    },
    onError: (error: unknown) => {
      if (getApiErrorStatus(error) === 429) {
        setUpgradePrompt('documents')
      } else {
        toast.error(getApiErrorMessage(error, 'Upload failed'))
      }
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => documentsApi.delete(id),
    onSuccess: (_, deletedId) => {
      qc.invalidateQueries({ queryKey: ['documents'] })
      setSelectedDocIds(prev => prev.filter(id => id !== deletedId))
      toast.success('Document deleted')
    },
  })

  const selectedDocs = (documents as DocumentItem[]).filter(document => selectedDocIds.includes(document.id))

  const handleSelectDoc = (id: string) => {
    setSelectedDocIds([id])
  }

  const handleToggleSelect = (id: string) => {
    setSelectedDocIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    )
  }

  const handleDeselectDoc = (id: string) => {
    setSelectedDocIds(prev => prev.filter(x => x !== id))
  }

  const handleClearAll = () => {
    setSelectedDocIds([])
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#0f1117', color: '#fff', fontFamily: 'inherit' }}>

      {/* Top navbar */}
      <nav className="dashboard-nav" style={{
        height: '56px', borderBottom: '1px solid rgba(255,255,255,0.07)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 24px', flexShrink: 0, background: '#0f1117'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            borderRadius: '8px', padding: '4px 8px', fontSize: '0.85rem', fontWeight: 700
          }}>DM</div>
          <span style={{ fontWeight: 600, fontSize: '1rem' }}>DocuMind</span>

          {/* Tier badge */}
          <span style={{
            fontSize: '0.6rem', fontFamily: 'monospace', padding: '2px 8px',
            borderRadius: '20px',
            background: isPro ? 'rgba(139,92,246,0.2)' : 'rgba(99,102,241,0.15)',
            color: isPro ? '#a78bfa' : '#818cf8',
            border: `1px solid ${isPro ? 'rgba(139,92,246,0.4)' : 'rgba(99,102,241,0.3)'}`,
            fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em',
          }}>
            {isDemo ? 'DEMO' : isPro ? 'PRO' : 'FREE'}
          </span>
        </div>
        <div className="dashboard-nav-actions" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            type="button"
            className="dashboard-sidebar-toggle"
            aria-expanded={sidebarOpen}
            onClick={() => setSidebarOpen(open => !open)}
            style={{
              fontSize: '0.78rem', padding: '8px 10px', borderRadius: '6px', background: 'transparent',
              border: '1px solid rgba(255,255,255,0.14)', color: '#d1d5db', cursor: 'pointer',
            }}
          >Documents</button>
          {/* Scientific RAG Benchmark button */}
          <button
            onClick={() => setShowEval(true)}
            style={{
              fontSize: '0.78rem', padding: '6px 12px', borderRadius: '6px',
              background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.35)',
              color: '#a5b4fc', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px',
              fontWeight: 500,
            }}
            title="View quantitative RAG evaluation metrics"
          >
            <span>🔬</span>
            <span>Quality Benchmark</span>
          </button>

          {!isDemo && !isPro && (
            <button onClick={() => navigate('/billing')} style={{
              fontSize: '0.75rem', padding: '5px 12px', borderRadius: '6px',
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              border: 'none', color: '#fff', cursor: 'pointer', fontWeight: 600,
            }}>Upgrade</button>
          )}
          {!isDemo && <button onClick={() => navigate('/billing')} style={{
            fontSize: '0.8rem', padding: '6px 14px', borderRadius: '6px',
            background: 'transparent', border: '1px solid rgba(255,255,255,0.1)',
            color: '#9ca3af', cursor: 'pointer'
          }}>Billing</button>}
          <span style={{ fontSize: '0.82rem', color: '#6b7280' }}>{user?.email}</span>
          <button onClick={logout} style={{
            fontSize: '0.8rem', padding: '6px 14px', borderRadius: '6px',
            background: 'transparent', border: '1px solid rgba(255,255,255,0.1)',
            color: '#9ca3af', cursor: 'pointer'
          }}>Sign out</button>
        </div>
      </nav>

      {/* Stats bar */}
      <StatsBar stats={stats} />

      {/* Main layout */}
      <div className="dashboard-main-layout" style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* Sidebar */}
        <aside className={`dashboard-sidebar ${sidebarOpen ? 'is-open' : ''}`} style={{
          width: sidebarOpen ? '280px' : '0',
          flexShrink: 0,
          borderRight: '1px solid rgba(255,255,255,0.07)',
          display: 'flex', flexDirection: 'column',
          overflow: 'hidden',
          background: '#0f1117'
        }}>
          {isDemo ? (
            <div style={{ padding: '16px', color: '#c7d2fe', fontSize: '0.78rem', lineHeight: 1.5, borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
              Public demo: seeded documents are read-only and queries are rate-limited.
            </div>
          ) : (
            <div style={{ padding: '16px', borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
              <UploadZone onDrop={(file) => uploadMutation.mutate(file)} loading={uploadMutation.isPending} />
            </div>
          )}
          <div style={{ flex: 1, overflow: 'auto' }}>
            <DocumentList
              documents={documents}
              loading={docsLoading}
              selectedIds={selectedDocIds}
              onSelect={handleSelectDoc}
              onToggleSelect={handleToggleSelect}
              onDelete={(id) => deleteMutation.mutate(id)}
              readOnly={isDemo}
              progressMap={progressMap}
            />
          </div>
        </aside>

        {/* Main content */}
        <main style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          {selectedDocs.length > 1 ? (
            <MultiDocViewer
              selectedDocs={selectedDocs}
              onDeselectDoc={handleDeselectDoc}
              onClearAll={handleClearAll}
            />
          ) : selectedDocs.length === 1 ? (
            <DocumentViewer doc={selectedDocs[0]} />
          ) : (
            <EmptyState docCount={documents.length} />
          )}
        </main>
      </div>

      {/* Upgrade prompt modal */}
      {upgradePrompt && (
        <UpgradePrompt type={upgradePrompt} onClose={() => setUpgradePrompt(null)} />
      )}

      {/* Quality Benchmark modal */}
      {showEval && (
        <EvalModal onClose={() => setShowEval(false)} />
      )}
    </div>
  )
}

function EmptyState({ docCount }: { docCount: number }) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#374151', padding: '40px' }}>
      <div style={{ fontSize: '4rem', marginBottom: '16px', opacity: 0.3 }}>📄</div>
      <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#6b7280', marginBottom: '8px' }}>
        {docCount === 0 ? 'Upload your first document' : 'Select a document'}
      </h2>
      <p style={{ fontSize: '0.85rem', color: '#374151', textAlign: 'center', maxWidth: '340px' }}>
        {docCount === 0
          ? 'Drop a PDF, Word doc, or text file into the sidebar to get started'
          : 'Click a document in the sidebar to view its AI analysis and ask questions'}
      </p>
    </div>
  )
}
