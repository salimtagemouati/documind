import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { analyticsApi } from '../../services/api'

interface Props {
  onClose: () => void
}

export default function EvalModal({ onClose }: Props) {
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null)

  const { data: benchmark, isLoading, error } = useQuery({
    queryKey: ['evalBenchmark'],
    queryFn: () => analyticsApi.evalBenchmark().then(r => r.data),
    staleTime: 60_000,
  })

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(6px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '20px', fontFamily: "'Inter', sans-serif"
    }}>
      <div style={{
        background: '#131620', border: '1px solid rgba(255,255,255,0.12)',
        borderRadius: '16px', width: '100%', maxWidth: '820px', maxHeight: '90vh',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
        boxShadow: '0 25px 50px -12px rgba(0,0,0,0.7)'
      }}>
        {/* Header */}
        <div style={{
          padding: '20px 24px', borderBottom: '1px solid rgba(255,255,255,0.08)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          background: '#0f1117'
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '1.2rem' }}>🔬</span>
              <h2 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: '#fff' }}>
                Scientific RAG Quality Benchmark
              </h2>
              <span style={{
                fontSize: '0.65rem', background: 'rgba(16,185,129,0.15)', color: '#10b981',
                border: '1px solid rgba(16,185,129,0.3)', padding: '2px 8px', borderRadius: '12px',
                fontWeight: 600, textTransform: 'uppercase'
              }}>Empirical Results</span>
            </div>
            <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: '#9ca3af' }}>
              Measured before and after Two-Stage Retrieval with Cross-Encoder / LLM Re-ranking.
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'rgba(255,255,255,0.06)', border: 'none', color: '#9ca3af',
              borderRadius: '8px', width: '32px', height: '32px', cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.1rem'
            }}
          >✕</button>
        </div>

        {/* Content Body */}
        <div style={{ padding: '24px', overflowY: 'auto', flex: 1 }}>
          {isLoading && (
            <div style={{ textAlign: 'center', padding: '60px', color: '#9ca3af' }}>
              <div style={{
                width: '36px', height: '36px', border: '3px solid rgba(255,255,255,0.1)',
                borderTopColor: '#6366f1', borderRadius: '50%', animation: 'spin 0.8s linear infinite',
                margin: '0 auto 16px'
              }} />
              Running evaluation harness across benchmark test cases...
            </div>
          )}

          {error && (
            <div style={{ padding: '20px', background: 'rgba(239,68,68,0.1)', color: '#ef4444', borderRadius: '8px' }}>
              Failed to load benchmark results.
            </div>
          )}

          {benchmark && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Architecture Info Banner */}
              <div style={{
                background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)',
                borderRadius: '10px', padding: '12px 16px', display: 'flex', flexWrap: 'wrap',
                gap: '16px', fontSize: '0.75rem', color: '#c7d2fe'
              }}>
                <div><strong>Stack:</strong> pgvector (HNSW) + PostgreSQL FTS</div>
                <div><strong>Chat Model:</strong> {benchmark.evaluated_models?.chat_model}</div>
                <div><strong>Embedding:</strong> {benchmark.evaluated_models?.embedding_model} (768d)</div>
                <div><strong>Test Suite:</strong> {benchmark.total_cases} labeled test cases</div>
              </div>

              {/* Metrics Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
                {benchmark.metrics?.map((m: any, idx: number) => {
                  const deltaPercent = (m.delta * 100).toFixed(1)
                  const isPositive = m.delta > 0
                  return (
                    <div key={idx} style={{
                      background: '#181b26', border: '1px solid rgba(255,255,255,0.07)',
                      borderRadius: '12px', padding: '14px', display: 'flex', flexDirection: 'column'
                    }}>
                      <div style={{ fontSize: '0.75rem', color: '#9ca3af', marginBottom: '8px' }}>{m.name}</div>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
                        <span style={{ fontSize: '1.4rem', fontWeight: 700, color: '#fff' }}>
                          {(m.reranked * 100).toFixed(1)}%
                        </span>
                        {m.delta !== 0 && (
                          <span style={{
                            fontSize: '0.75rem', fontWeight: 600,
                            color: isPositive ? '#10b981' : '#ef4444'
                          }}>
                            {isPositive ? `+${deltaPercent}%` : `${deltaPercent}%`}
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: '#6b7280', marginTop: '6px' }}>
                        Baseline: {(m.baseline * 100).toFixed(1)}%
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Comparison Visualizer */}
              <div style={{
                background: '#181b26', border: '1px solid rgba(255,255,255,0.07)',
                borderRadius: '12px', padding: '16px'
              }}>
                <h3 style={{ margin: '0 0 14px', fontSize: '0.85rem', fontWeight: 600, color: '#e5e7eb' }}>
                  Retrieval Quality Delta: Vector Search vs. Re-ranking
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {benchmark.metrics?.filter((m: any) => m.name.includes('Precision') || m.name.includes('Groundedness') || m.name.includes('Recall')).map((m: any, i: number) => (
                    <div key={i}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '4px' }}>
                        <span style={{ color: '#d1d5db' }}>{m.name}</span>
                        <span style={{ color: '#10b981', fontWeight: 600 }}>
                          {(m.baseline * 100).toFixed(0)}% → {(m.reranked * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div style={{ height: '8px', background: 'rgba(255,255,255,0.06)', borderRadius: '4px', overflow: 'hidden', position: 'relative' }}>
                        <div style={{
                          height: '100%', width: `${m.baseline * 100}%`,
                          background: '#4b5563', position: 'absolute', left: 0
                        }} />
                        <div style={{
                          height: '100%', width: `${m.reranked * 100}%`,
                          background: 'linear-gradient(90deg, #6366f1, #10b981)',
                          position: 'absolute', left: 0, opacity: 0.85
                        }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Test Cases Table */}
              <div style={{
                background: '#181b26', border: '1px solid rgba(255,255,255,0.07)',
                borderRadius: '12px', overflow: 'hidden'
              }}>
                <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.07)', fontSize: '0.8rem', fontWeight: 600, color: '#e5e7eb' }}>
                  Test Cases &amp; Ground Truth Verification ({benchmark.details?.length} cases)
                </div>
                <div style={{ maxHeight: '240px', overflowY: 'auto' }}>
                  {benchmark.details?.map((c: any) => (
                    <div
                      key={c.case_id}
                      onClick={() => setSelectedCaseId(selectedCaseId === c.case_id ? null : c.case_id)}
                      style={{
                        padding: '10px 16px', borderBottom: '1px solid rgba(255,255,255,0.04)',
                        cursor: 'pointer', fontSize: '0.75rem',
                        background: selectedCaseId === c.case_id ? 'rgba(99,102,241,0.1)' : 'transparent'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{
                            padding: '2px 6px', borderRadius: '4px', fontSize: '0.65rem',
                            background: c.is_negative ? 'rgba(239,68,68,0.2)' : 'rgba(99,102,241,0.2)',
                            color: c.is_negative ? '#f87171' : '#a5b4fc',
                          }}>
                            {c.category}
                          </span>
                          <span style={{ color: '#f3f4f6', fontWeight: 500 }}>{c.question}</span>
                        </div>
                        <div style={{ display: 'flex', gap: '12px', flexShrink: 0 }}>
                          <span style={{ color: '#9ca3af' }}>Baseline: {(c.baseline.precision_at_5 * 100).toFixed(0)}%</span>
                          <span style={{ color: '#10b981', fontWeight: 600 }}>Reranked: {(c.reranked.precision_at_5 * 100).toFixed(0)}%</span>
                        </div>
                      </div>

                      {selectedCaseId === c.case_id && (
                        <div style={{ marginTop: '10px', padding: '8px 12px', background: '#0f1117', borderRadius: '6px' }}>
                          <div style={{ color: '#9ca3af', marginBottom: '4px' }}><strong>Answer Preview (Reranked Pipeline):</strong></div>
                          <div style={{ color: '#d1d5db', fontStyle: 'italic' }}>"{c.reranked.answer_preview}..."</div>
                          <div style={{ color: '#10b981', marginTop: '6px' }}>Groundedness Score: {(c.reranked.groundedness * 100).toFixed(1)}%</div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '14px 24px', borderTop: '1px solid rgba(255,255,255,0.08)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          background: '#0f1117', fontSize: '0.75rem', color: '#6b7280'
        }}>
          <div>Reproducible via CLI: <code>python -m app.eval.runner</code></div>
          <button
            onClick={onClose}
            style={{
              padding: '8px 18px', background: '#6366f1', color: '#fff',
              border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600
            }}
          >Close Benchmark</button>
        </div>
      </div>
    </div>
  )
}
