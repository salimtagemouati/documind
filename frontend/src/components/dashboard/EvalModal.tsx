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
                borderRadius: '10px', padding: '12px 16px', display: 'flex', flexDirection: 'column',
                gap: '8px', fontSize: '0.75rem', color: '#c7d2fe'
              }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{
                      padding: '2px 8px', borderRadius: '6px', fontSize: '0.65rem', fontWeight: 700,
                      background: benchmark.evaluated_models?.in_memory_mode ? 'rgba(245,158,11,0.2)' : 'rgba(16,185,129,0.2)',
                      color: benchmark.evaluated_models?.in_memory_mode ? '#fbbf24' : '#34d399',
                      border: `1px solid ${benchmark.evaluated_models?.in_memory_mode ? 'rgba(245,158,11,0.4)' : 'rgba(16,185,129,0.4)'}`,
                    }}>
                      {benchmark.evaluated_models?.in_memory_mode ? '⚡ In-Memory Evaluation' : '🛡️ pgvector Durability'}
                    </span>
                    <span><strong>Stack:</strong> pgvector + PostgreSQL FTS + Cross-Encoder</span>
                  </div>
                  {benchmark.timestamp && (
                    <span style={{ color: '#9ca3af', fontSize: '0.7rem' }}>
                      Run Date: {new Date(benchmark.timestamp).toLocaleDateString()} {new Date(benchmark.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', color: '#9ca3af', fontSize: '0.72rem' }}>
                  <div>LLM: <span style={{ color: '#e0e7ff' }}>{benchmark.evaluated_models?.chat_model}</span></div>
                  <div>Embedding: <span style={{ color: '#e0e7ff' }}>{benchmark.evaluated_models?.embedding_model} (768d)</span></div>
                  <div>Test Cases: <span style={{ color: '#e0e7ff' }}>{benchmark.total_cases} labeled</span></div>
                  {benchmark.summary?.baseline_avg_latency_sec && (
                    <div>Avg Latency: <span style={{ color: '#e0e7ff' }}>{benchmark.summary.baseline_avg_latency_sec.toFixed(2)}s → {benchmark.summary.reranked_avg_latency_sec?.toFixed(2)}s</span></div>
                  )}
                </div>
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
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                  <h3 style={{ margin: 0, fontSize: '0.85rem', fontWeight: 600, color: '#e5e7eb' }}>
                    Retrieval Quality Comparison: Baseline vs. Two-Stage Reranked
                  </h3>
                  <div style={{ display: 'flex', gap: '14px', fontSize: '0.7rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <div style={{ width: '10px', height: '10px', background: '#4b5563', borderRadius: '2px' }} />
                      <span style={{ color: '#9ca3af' }}>Baseline Dense Vector</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <div style={{ width: '10px', height: '10px', background: 'linear-gradient(90deg, #6366f1, #10b981)', borderRadius: '2px' }} />
                      <span style={{ color: '#34d399', fontWeight: 600 }}>Two-Stage Hybrid + Rerank</span>
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {benchmark.metrics?.map((m: any, i: number) => (
                    <div key={i}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '4px' }}>
                        <span style={{ color: '#d1d5db' }}>{m.name}</span>
                        <span style={{ color: '#10b981', fontWeight: 600 }}>
                          {(m.baseline * 100).toFixed(0)}% → {(m.reranked * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {/* Baseline bar */}
                        <div style={{ height: '6px', background: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${Math.max(m.baseline * 100, 2)}%`, background: '#64748b', borderRadius: '3px' }} />
                        </div>
                        {/* Reranked bar */}
                        <div style={{ height: '6px', background: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${Math.max(m.reranked * 100, 2)}%`, background: 'linear-gradient(90deg, #6366f1, #10b981)', borderRadius: '3px' }} />
                        </div>
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
