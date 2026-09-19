import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { documentsApi, getApiErrorMessage, queryApi } from '../../services/api'
import toast from 'react-hot-toast'
import type { DocumentAnalysis, DocumentItem, QueryAnswer, QueryHistoryItem } from '../../types'

interface Props {
  doc: DocumentItem
}

type Tab = 'overview' | 'entities' | 'qa' | 'history'

export default function DocumentViewer({ doc }: Props) {
  const [tab, setTab] = useState<Tab>('overview')
  const [question, setQuestion] = useState('')
  const [answers, setAnswers] = useState<QueryAnswer[]>([])
  const [asking, setAsking] = useState(false)

  const isReady = doc.status === 'ready'
  const isProcessing = ['pending', 'processing'].includes(doc.status)

  // Fetch full analysis (only when ready)
  const { data: analysis, isLoading: analysisLoading } = useQuery({
    queryKey: ['analysis', doc.id],
    queryFn: () => documentsApi.getAnalysis(doc.id).then(r => r.data),
    enabled: isReady,
    staleTime: 5 * 60 * 1000,
  })

  const askQuestion = async () => {
    if (!question.trim() || asking) return
    setAsking(true)
    const q = question.trim()
    setQuestion('')
    try {
      const { data } = await queryApi.ask(doc.id, q)
      setAnswers(prev => [data, ...prev])
    } catch (error: unknown) {
      toast.error(getApiErrorMessage(error, 'Query failed'))
    } finally {
      setAsking(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>

      {/* Doc header */}
      <div style={{
        padding: '16px 24px', borderBottom: '1px solid rgba(255,255,255,0.07)',
        display: 'flex', alignItems: 'center', gap: '16px', flexShrink: 0
      }}>
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: '1rem', fontWeight: 600, color: '#f9fafb', margin: 0 }}>
            {doc.original_filename || doc.filename}
          </h1>
          <div style={{ display: 'flex', gap: '12px', marginTop: '4px' }}>
            <StatusPill status={doc.status} />
            {doc.chunk_count > 0 && <Meta label="Chunks" value={doc.chunk_count} />}
            {doc.token_count > 0 && <Meta label="Tokens" value={doc.token_count.toLocaleString()} />}
            {doc.page_count && <Meta label="Pages" value={doc.page_count} />}
          </div>
        </div>
      </div>

      {/* Processing state */}
      {isProcessing && (
        <div style={{ padding: '24px', display: 'flex', alignItems: 'center', gap: '12px', color: '#f59e0b' }}>
          <span style={{ fontSize: '1.2rem' }}>⟳</span>
          <div>
            <div style={{ fontWeight: 500, fontSize: '0.9rem' }}>Processing document...</div>
            <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '2px' }}>Extracting text → chunking → building embeddings → running AI analysis</div>
          </div>
        </div>
      )}

      {doc.status === 'failed' && (
        <div style={{ padding: '24px', color: '#ef4444' }}>
          <div style={{ fontWeight: 500 }}>Processing failed</div>
          <div style={{ fontSize: '0.82rem', marginTop: '4px', color: '#9ca3af' }}>{doc.error_message}</div>
        </div>
      )}

      {/* Tabs */}
      {isReady && (
        <>
          <div style={{ display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.07)', flexShrink: 0 }}>
            {([['overview', '📊 Overview'], ['entities', '🏷 Entities'], ['qa', '💬 Q&A'], ['history', '🕐 History']] as const).map(([t, label]) => (
              <button key={t} onClick={() => setTab(t)} style={{
                padding: '12px 20px', background: 'none', border: 'none',
                borderBottom: tab === t ? '2px solid #6366f1' : '2px solid transparent',
                color: tab === t ? '#818cf8' : '#6b7280', cursor: 'pointer',
                fontSize: '0.82rem', fontWeight: tab === t ? 600 : 400,
                transition: 'all 0.15s'
              }}>{label}</button>
            ))}
          </div>

          <div style={{ flex: 1, overflow: 'auto', padding: '24px' }}>
            {tab === 'overview' && <OverviewTab analysis={analysis} loading={analysisLoading} />}
            {tab === 'entities' && <EntitiesTab analysis={analysis} loading={analysisLoading} />}
            {tab === 'qa' && (
              <QATab
                question={question} setQuestion={setQuestion}
                onAsk={askQuestion} asking={asking} answers={answers}
                docReady={isReady}
              />
            )}
            {tab === 'history' && <HistoryTab docId={doc.id} />}
          </div>
        </>
      )}
    </div>
  )
}

// ─── Overview Tab ─────────────────────────────────────────────────────────────
function OverviewTab({ analysis, loading }: { analysis?: DocumentAnalysis, loading: boolean }) {
  if (loading) return <Skeleton />
  if (!analysis) return null
  const s = analysis.sentiment
  const keywords = analysis.keywords ?? []

  return (
    <div style={{ maxWidth: '760px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Summary */}
      {analysis.summary && (
        <Card title="AI Summary">
          <p style={{ fontSize: '0.9rem', lineHeight: 1.7, color: '#d1d5db', margin: 0 }}>{analysis.summary}</p>
        </Card>
      )}

      {/* Keywords */}
      {keywords.length > 0 && (
        <Card title="Keywords">
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {keywords.map((k: string) => (
              <span key={k} style={{
                padding: '4px 10px', borderRadius: '20px', fontSize: '0.75rem',
                fontFamily: 'monospace', background: 'rgba(99,102,241,0.12)',
                color: '#818cf8', border: '1px solid rgba(99,102,241,0.25)'
              }}>{k}</span>
            ))}
          </div>
        </Card>
      )}

      {/* Sentiment */}
      {s && (
        <Card title="Sentiment Analysis">
          <div style={{ display: 'flex', gap: '24px', alignItems: 'center', flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: '2rem', fontWeight: 700, color: sentimentColor(s.label) }}>{Math.round(s.score * 100)}%</div>
              <div style={{ fontSize: '0.75rem', color: '#6b7280', fontFamily: 'monospace' }}>positive score</div>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
                <Chip label={s.label} color={sentimentColor(s.label)} />
                <Chip label={s.tone} color="#818cf8" />
                <Chip label={`${Math.round(s.confidence * 100)}% confidence`} color="#6b7280" />
              </div>
              <p style={{ fontSize: '0.85rem', color: '#9ca3af', margin: 0 }}>{s.explanation}</p>
            </div>
          </div>
          <div style={{ marginTop: '12px', height: '6px', background: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow: 'hidden' }}>
            <div style={{
              height: '100%', width: '100%', background: sentimentColor(s.label), borderRadius: '3px',
              transform: `scaleX(${Math.min(1, Math.max(0, s.score))})`,
              transformOrigin: 'left center', transition: 'transform 0.8s ease-out',
            }} />
          </div>
        </Card>
      )}
    </div>
  )
}

// ─── Entities Tab ─────────────────────────────────────────────────────────────
function EntitiesTab({ analysis, loading }: { analysis?: DocumentAnalysis, loading: boolean }) {
  if (loading) return <Skeleton />
  if (!analysis?.entities) return <div style={{ color: '#6b7280' }}>No entities found.</div>

  const e = analysis.entities
  const categories = [
    { key: 'persons', label: 'People', color: '#f472b6' },
    { key: 'organizations', label: 'Organizations', color: '#60a5fa' },
    { key: 'locations', label: 'Locations', color: '#34d399' },
    { key: 'dates', label: 'Dates', color: '#fbbf24' },
    { key: 'technologies', label: 'Technologies', color: '#a78bfa' },
    { key: 'monetary_values', label: 'Monetary', color: '#10b981' },
    { key: 'other', label: 'Other', color: '#9ca3af' },
  ]

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '16px', maxWidth: '900px' }}>
      {categories.map(({ key, label, color }) => {
        const items = e[key] || []
        if (!items.length) return null
        return (
          <Card key={key} title={label}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {items.map((item: string) => (
                <span key={item} style={{
                  padding: '3px 10px', borderRadius: '20px', fontSize: '0.75rem',
                  background: `${color}18`, color: color, border: `1px solid ${color}30`,
                  fontFamily: 'monospace'
                }}>{item}</span>
              ))}
            </div>
          </Card>
        )
      })}
    </div>
  )
}

// ─── Q&A Tab ──────────────────────────────────────────────────────────────────
interface QATabProps {
  question: string
  setQuestion: (value: string) => void
  onAsk: () => void
  asking: boolean
  answers: QueryAnswer[]
  docReady: boolean
}

function QATab({ question, setQuestion, onAsk, asking, answers, docReady }: QATabProps) {
  return (
    <div style={{ maxWidth: '760px' }}>
      <div style={{ display: 'flex', gap: '10px', marginBottom: '24px' }}>
        <input
          aria-label="Question about this document"
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && onAsk()}
          placeholder="Ask anything about this document..."
          disabled={!docReady || asking}
          style={{
            flex: 1, padding: '11px 16px',
            background: '#1a1d27', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '8px', color: '#fff', fontSize: '0.9rem', outline: 'none'
          }}
        />
        <button onClick={onAsk} disabled={asking || !question.trim()} style={{
          padding: '11px 20px', borderRadius: '8px',
          background: asking ? 'rgba(99,102,241,0.4)' : '#6366f1',
          border: 'none', color: '#fff', fontWeight: 600, cursor: 'pointer', fontSize: '0.85rem',
          opacity: asking || !question.trim() ? 0.6 : 1
        }}>
          {asking ? '...' : 'Ask'}
        </button>
      </div>

      {answers.length === 0 && (
        <div style={{ textAlign: 'center', padding: '40px 0', color: '#374151' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '10px', opacity: 0.4 }}>💬</div>
          <div style={{ fontSize: '0.85rem' }}>Ask a question to get a grounded, cited answer</div>
          <div style={{ fontSize: '0.75rem', marginTop: '6px', fontFamily: 'monospace', color: '#4b5563' }}>
            Powered by RAG — only uses content from this document
          </div>
        </div>
      )}

      {answers.map((a, i) => (
        <div key={i} style={{ marginBottom: '20px', animation: 'fadeIn 0.3s ease' }}>
          <Card title={`Q: ${a.question}`}>
            <p style={{ fontSize: '0.9rem', lineHeight: 1.7, color: '#d1d5db', margin: '0 0 16px' }}>{a.answer}</p>
            {a.sources?.length > 0 && (
              <div>
                <div style={{ fontSize: '0.65rem', fontFamily: 'monospace', color: '#4b5563', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                  Sources used ({a.sources.length} chunks · similarity ≥ {Math.min(...a.sources.map(s => s.similarity_score)).toFixed(2)})
                </div>
                {a.sources.slice(0, 3).map((s, j) => (
                  <div key={j} style={{
                    padding: '8px 12px', marginBottom: '6px', borderRadius: '6px',
                    background: 'rgba(255,255,255,0.03)', borderLeft: '2px solid rgba(99,102,241,0.4)',
                    fontSize: '0.78rem', color: '#9ca3af', lineHeight: 1.6
                  }}>
                    <span style={{ fontFamily: 'monospace', color: '#6366f1', marginRight: '8px' }}>
                      [{j + 1}] {s.similarity_score.toFixed(2)}
                    </span>
                    {s.content}
                  </div>
                ))}
                <div style={{ fontSize: '0.65rem', color: '#374151', fontFamily: 'monospace', marginTop: '4px' }}>
                  {a.tokens_used} tokens · {a.latency_ms}ms {a.from_cache && '· ⚡ cached'}
                </div>
              </div>
            )}
          </Card>
        </div>
      ))}
    </div>
  )
}

// ─── History Tab ──────────────────────────────────────────────────────────────
function HistoryTab({ docId }: { docId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['queryHistory', docId],
    queryFn: () => queryApi.history(docId).then(r => r.data),
  })

  if (isLoading) return <Skeleton />
  const items: QueryHistoryItem[] = data?.items || []
  if (!items.length) return <div style={{ color: '#6b7280', fontSize: '0.85rem' }}>No queries yet for this document.</div>

  return (
    <div style={{ maxWidth: '760px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {items.map(q => (
        <div key={q.id} style={{
          padding: '12px 16px', borderRadius: '8px',
          background: '#1a1d27', border: '1px solid rgba(255,255,255,0.07)'
        }}>
          <div style={{ fontSize: '0.82rem', fontWeight: 500, color: '#c7d2fe', marginBottom: '6px' }}>{q.question}</div>
          <div style={{ fontSize: '0.8rem', color: '#9ca3af', lineHeight: 1.6 }}>{q.answer.substring(0, 200)}{q.answer.length > 200 ? '...' : ''}</div>
          <div style={{ fontSize: '0.65rem', color: '#374151', marginTop: '6px', fontFamily: 'monospace' }}>
            {q.tokens_used} tokens · {q.latency_ms}ms {q.from_cache && '⚡'}
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Shared components ────────────────────────────────────────────────────────
function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ background: '#1a1d27', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '10px', overflow: 'hidden' }}>
      <div style={{ padding: '10px 16px', borderBottom: '1px solid rgba(255,255,255,0.05)', fontSize: '0.7rem', fontFamily: 'monospace', textTransform: 'uppercase', letterSpacing: '0.1em', color: '#4b5563' }}>
        {title}
      </div>
      <div style={{ padding: '14px 16px' }}>{children}</div>
    </div>
  )
}

function Skeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {[1, 2, 3].map(i => (
        <div key={i} style={{ height: '80px', background: 'rgba(255,255,255,0.04)', borderRadius: '8px', animation: 'pulse 1.5s infinite' }} />
      ))}
    </div>
  )
}

function StatusPill({ status }: { status: string }) {
  const colors: Record<string, string> = { ready: '#10b981', processing: '#f59e0b', pending: '#6b7280', failed: '#ef4444' }
  return (
    <span style={{ fontSize: '0.68rem', fontFamily: 'monospace', padding: '2px 8px', borderRadius: '20px', background: `${colors[status] || '#6b7280'}20`, color: colors[status] || '#6b7280', border: `1px solid ${colors[status] || '#6b7280'}40` }}>
      {status}
    </span>
  )
}

function Meta({ label, value }: { label: string; value: string | number }) {
  return (
    <span style={{ fontSize: '0.7rem', color: '#4b5563', fontFamily: 'monospace' }}>
      {label}: <span style={{ color: '#9ca3af' }}>{value}</span>
    </span>
  )
}

function Chip({ label, color }: { label: string; color: string }) {
  return (
    <span style={{ fontSize: '0.7rem', padding: '3px 8px', borderRadius: '20px', background: `${color}18`, color, border: `1px solid ${color}30`, fontFamily: 'monospace' }}>
      {label}
    </span>
  )
}

function sentimentColor(label: string) {
  return { Positive: '#10b981', Negative: '#ef4444', Neutral: '#6b7280', Mixed: '#f59e0b' }[label] || '#6b7280'
}
