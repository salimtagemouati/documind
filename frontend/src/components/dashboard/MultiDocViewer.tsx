import { useState } from 'react'
import { queryApi } from '../../services/api'
import toast from 'react-hot-toast'

interface Props {
  selectedDocs: any[]
  onDeselectDoc: (id: string) => void
  onClearAll: () => void
}

const SUGGESTED_QUERIES = [
  "Compare liability, SLA, and termination terms across these documents.",
  "What are the main points of consensus and contradiction between them?",
  "Synthesize the key architectural and performance metrics mentioned across the files.",
  "Identify all monetary values, financial targets, and obligations described."
]

export default function MultiDocViewer({ selectedDocs, onDeselectDoc, onClearAll }: Props) {
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [history, setHistory] = useState<any[]>([])

  const docIds = selectedDocs.map(d => d.id)

  const handleAsk = async (queryText?: string) => {
    const q = (queryText || question).trim()
    if (!q || asking) return
    setAsking(true)
    if (!queryText) setQuestion('')

    try {
      const { data } = await queryApi.askMulti(docIds, q)
      setHistory(prev => [data, ...prev])
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Multi-document query failed')
    } finally {
      setAsking(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', background: '#0f1117' }}>
      {/* Header */}
      <div style={{
        padding: '16px 24px', borderBottom: '1px solid rgba(255,255,255,0.07)',
        background: '#131620'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.1rem' }}>📑</span>
              <h2 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: '#fff' }}>
                Multi-Document Synthesis &amp; Cross-Query
              </h2>
              <span style={{
                fontSize: '0.65rem', background: 'rgba(99,102,241,0.2)', color: '#818cf8',
                border: '1px solid rgba(99,102,241,0.4)', padding: '2px 8px', borderRadius: '12px',
                fontWeight: 600, textTransform: 'uppercase'
              }}>Active ({selectedDocs.length} Docs)</span>
            </div>
            <p style={{ margin: '4px 0 0', fontSize: '0.78rem', color: '#9ca3af' }}>
              Synthesizing evidence across multiple documents with balanced retrieval and provenance tracking.
            </p>
          </div>
          <button
            onClick={onClearAll}
            style={{
              padding: '6px 12px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '6px', color: '#9ca3af', fontSize: '0.75rem', cursor: 'pointer'
            }}
          >Clear Selection</button>
        </div>

        {/* Document Pills */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '12px' }}>
          {selectedDocs.map(doc => (
            <div
              key={doc.id}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '6px',
                background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.3)',
                borderRadius: '20px', padding: '4px 10px', fontSize: '0.75rem', color: '#c7d2fe'
              }}
            >
              <span>📄</span>
              <span style={{ maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {doc.original_filename || doc.filename}
              </span>
              <button
                onClick={() => onDeselectDoc(doc.id)}
                style={{
                  background: 'none', border: 'none', color: '#818cf8', cursor: 'pointer',
                  padding: 0, fontSize: '0.9rem', lineHeight: 1, display: 'flex', alignItems: 'center'
                }}
              >×</button>
            </div>
          ))}
        </div>
      </div>

      {/* Suggested Prompts */}
      <div style={{
        padding: '12px 24px', borderBottom: '1px solid rgba(255,255,255,0.05)',
        background: '#0f1117', display: 'flex', alignItems: 'center', gap: '8px', overflowX: 'auto'
      }}>
        <span style={{ fontSize: '0.7rem', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em', flexShrink: 0 }}>
          Suggested:
        </span>
        {SUGGESTED_QUERIES.map((sq, i) => (
          <button
            key={i}
            disabled={asking}
            onClick={() => handleAsk(sq)}
            style={{
              padding: '4px 10px', borderRadius: '16px', fontSize: '0.72rem',
              background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
              color: '#9ca3af', cursor: 'pointer', whiteSpace: 'nowrap', transition: 'all 0.1s'
            }}
          >
            {sq}
          </button>
        ))}
      </div>

      {/* Chat / Results Stream */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {history.length === 0 && (
          <div style={{
            textAlign: 'center', padding: '60px 20px', color: '#4b5563',
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center'
          }}>
            <div style={{ fontSize: '2.5rem', marginBottom: '12px', opacity: 0.4 }}>⚖️</div>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#9ca3af', margin: '0 0 6px' }}>
              Ask a Comparative Cross-Document Question
            </h3>
            <p style={{ fontSize: '0.8rem', maxWidth: '420px', margin: 0 }}>
              DocuMind will retrieve balanced evidence from each selected document, apply two-stage re-ranking, and generate a synthesized answer with provenance citations.
            </p>
          </div>
        )}

        {history.map((item, idx) => (
          <div key={idx} style={{
            background: '#161922', border: '1px solid rgba(255,255,255,0.07)',
            borderRadius: '12px', padding: '18px', display: 'flex', flexDirection: 'column', gap: '14px'
          }}>
            {/* Question */}
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
              <span style={{ fontSize: '1rem' }}>💬</span>
              <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f3f4f6' }}>{item.question}</div>
            </div>

            {/* Answer */}
            <div style={{
              fontSize: '0.85rem', lineHeight: 1.6, color: '#d1d5db',
              whiteSpace: 'pre-wrap', paddingLeft: '24px', borderLeft: '2px solid #6366f1'
            }}>
              {item.answer}
            </div>

            {/* Provenance Sources */}
            {item.sources?.length > 0 && (
              <div style={{ marginTop: '8px', paddingLeft: '24px' }}>
                <div style={{ fontSize: '0.72rem', fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase', marginBottom: '8px' }}>
                  Source Citations &amp; Provenance ({item.sources.length} excerpts)
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '8px' }}>
                  {item.sources.map((src: any, sIdx: number) => (
                    <div key={sIdx} style={{
                      background: '#0f1117', border: '1px solid rgba(255,255,255,0.06)',
                      borderRadius: '8px', padding: '10px', fontSize: '0.72rem'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                        <span style={{ color: '#818cf8', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '160px' }}>
                          📄 {src.document_name}
                        </span>
                        <span style={{ color: '#10b981', fontWeight: 600 }}>
                          {(src.similarity_score * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div style={{ color: '#9ca3af', fontStyle: 'italic', overflow: 'hidden', maxHeight: '48px' }}>
                        "{src.content}"
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Meta tags */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: '12px', fontSize: '0.7rem',
              color: '#6b7280', borderTop: '1px solid rgba(255,255,255,0.04)', paddingTop: '10px'
            }}>
              <span>Model: {item.model_used}</span>
              <span>Latency: {item.latency_ms}ms</span>
              {item.reranked && (
                <span style={{ color: '#10b981', fontWeight: 600 }}>⚡ Two-Stage Reranked</span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Input Box */}
      <div style={{
        padding: '16px 24px', borderTop: '1px solid rgba(255,255,255,0.07)',
        background: '#131620'
      }}>
        <form onSubmit={(e) => { e.preventDefault(); handleAsk(); }} style={{ display: 'flex', gap: '10px' }}>
          <input
            type="text"
            placeholder={`Ask a comparative question across all ${selectedDocs.length} documents...`}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={asking}
            style={{
              flex: 1, padding: '12px 16px', background: '#0f1117',
              border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px',
              color: '#fff', fontSize: '0.85rem', outline: 'none'
            }}
          />
          <button
            type="submit"
            disabled={asking || !question.trim()}
            style={{
              padding: '0 20px', background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              border: 'none', borderRadius: '8px', color: '#fff', fontSize: '0.85rem',
              fontWeight: 600, cursor: asking ? 'not-allowed' : 'pointer', opacity: asking ? 0.6 : 1
            }}
          >
            {asking ? 'Synthesizing...' : 'Synthesize'}
          </button>
        </form>
      </div>
    </div>
  )
}
