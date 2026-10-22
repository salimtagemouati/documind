import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { analyticsApi } from '../../services/api'
import type { BenchmarkReport } from '../../types'

interface Props {
  onClose: () => void
}

const surface = '#181b26'
const muted = '#a9b1bf'

export default function EvalModal({ onClose }: Props) {
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  const { data: benchmark, isLoading, error, refetch, isFetching } = useQuery<BenchmarkReport>({
    queryKey: ['evalBenchmark'],
    queryFn: () => analyticsApi.evalBenchmark().then(response => response.data),
    staleTime: 60_000,
  })

  useEffect(() => {
    closeButtonRef.current?.focus()
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    <div
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.78)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px',
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="benchmark-title"
        aria-describedby="benchmark-description"
        style={{
          background: '#131620', border: '1px solid rgba(255,255,255,0.14)', borderRadius: '16px',
          width: '100%', maxWidth: '820px', maxHeight: '90vh', display: 'flex', flexDirection: 'column',
          overflow: 'hidden', boxShadow: '0 24px 60px 12px rgba(0,0,0,0.45)',
        }}
      >
        <header style={{
          padding: '20px 24px', borderBottom: '1px solid rgba(255,255,255,0.08)',
          display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '20px',
        }}>
          <div>
            <h2 id="benchmark-title" style={{ margin: 0, fontSize: '1.1rem', color: '#fff' }}>
              RAG quality benchmark
            </h2>
            <p id="benchmark-description" style={{ margin: '6px 0 0', fontSize: '0.82rem', color: muted }}>
              In-memory dense retrieval compared with a larger dense candidate pool and one batched LLM rerank.
            </p>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            aria-label="Close benchmark"
            style={{
              background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.1)',
              color: '#d1d5db', borderRadius: '8px', minWidth: '64px', height: '44px', cursor: 'pointer',
            }}
          >
            Close
          </button>
        </header>

        <div style={{ padding: '24px', overflowY: 'auto', flex: 1 }}>
          {isLoading && (
            <div role="status" style={{ textAlign: 'center', padding: '56px 20px', color: muted }}>
              Loading stored benchmark results…
            </div>
          )}

          {error && (
            <div role="alert" style={{ padding: '20px', background: 'rgba(239,68,68,0.12)', color: '#fca5a5', borderRadius: '10px' }}>
              <strong>Benchmark unavailable.</strong>
              <p style={{ margin: '6px 0 14px' }}>The API did not return a readable evaluation artifact.</p>
              <button type="button" onClick={() => refetch()} disabled={isFetching} style={secondaryButton}>
                {isFetching ? 'Retrying…' : 'Retry'}
              </button>
            </div>
          )}

          {benchmark && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {!benchmark.results_validated && (
                <div role="alert" style={{ padding: '14px 16px', background: 'rgba(245,158,11,0.12)', color: '#fde68a', borderRadius: '10px' }}>
                  <strong>Historical results — validation expired.</strong>{' '}
                  This artifact predates the corrected Precision@K formula. Rerun methodology v2 before citing its values.
                </div>
              )}

              <div style={{ background: 'rgba(99,102,241,0.09)', borderRadius: '10px', padding: '14px 16px', color: '#d8dcff' }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 18px', fontSize: '0.78rem' }}>
                  <span><strong>Mode:</strong> {benchmark.mode}</span>
                  <span><strong>Cases:</strong> {benchmark.total_cases}</span>
                  <span><strong>Top K:</strong> {benchmark.parameters.k}</span>
                  <span><strong>Method:</strong> {benchmark.methodology_version}</span>
                </div>
                <p style={{ margin: '9px 0 0', fontSize: '0.75rem', color: muted }}>
                  This run does not exercise pgvector, HNSW, PostgreSQL FTS, RRF, or tenant filters. Groundedness is lexical overlap, not an independent LLM judge.
                </p>
              </div>

              {benchmark.metrics.length === 0 ? (
                <div style={{ padding: '36px', textAlign: 'center', color: muted }}>No aggregate metrics are present in this artifact.</div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
                  {benchmark.metrics.map(metric => (
                    <article key={metric.name} style={{ background: surface, borderRadius: '12px', padding: '14px' }}>
                      <div style={{ fontSize: '0.76rem', color: muted }}>{metric.name}</div>
                      <div style={{ marginTop: '8px', fontSize: '1.4rem', fontWeight: 700, color: '#fff' }}>
                        {(metric.reranked * 100).toFixed(1)}%
                      </div>
                      <div style={{ marginTop: '4px', fontSize: '0.72rem', color: muted }}>
                        Baseline {(metric.baseline * 100).toFixed(1)}% · Δ {(metric.delta * 100).toFixed(1)} pp
                      </div>
                    </article>
                  ))}
                </div>
              )}

              <section style={{ background: surface, borderRadius: '12px', overflow: 'hidden' }}>
                <h3 style={{ margin: 0, padding: '14px 16px', fontSize: '0.85rem', color: '#e5e7eb' }}>
                  Test cases ({benchmark.details.length})
                </h3>
                {benchmark.details.length === 0 ? (
                  <div style={{ padding: '28px 16px', color: muted }}>No case-level results are present.</div>
                ) : (
                  <div style={{ maxHeight: '260px', overflowY: 'auto' }}>
                    {benchmark.details.map(testCase => {
                      const expanded = selectedCaseId === testCase.case_id
                      return (
                        <button
                          key={testCase.case_id}
                          type="button"
                          aria-expanded={expanded}
                          onClick={() => setSelectedCaseId(expanded ? null : testCase.case_id)}
                          style={{
                            width: '100%', textAlign: 'left', padding: '12px 16px', color: '#f3f4f6',
                            background: expanded ? 'rgba(99,102,241,0.12)' : 'transparent',
                            border: 0, borderTop: '1px solid rgba(255,255,255,0.06)', cursor: 'pointer',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', fontSize: '0.76rem' }}>
                            <span>{testCase.question}</span>
                            <span style={{ color: muted, flexShrink: 0 }}>
                              P@K {(testCase.reranked.precision_at_k * 100).toFixed(0)}%
                            </span>
                          </div>
                          {expanded && (
                            <div style={{ marginTop: '10px', color: muted, lineHeight: 1.5 }}>
                              {testCase.reranked.answer_preview || 'No answer preview stored.'}
                            </div>
                          )}
                        </button>
                      )
                    })}
                  </div>
                )}
              </section>
            </div>
          )}
        </div>

        <footer style={{ padding: '14px 24px', borderTop: '1px solid rgba(255,255,255,0.08)', color: muted, fontSize: '0.75rem' }}>
          Reproduce with <code>python -m app.eval.runner --cases 3</code> after configuring provider credentials.
        </footer>
      </section>
    </div>
  )
}

const secondaryButton: React.CSSProperties = {
  padding: '10px 16px', background: '#353a4a', color: '#fff', border: 0,
  borderRadius: '8px', cursor: 'pointer', minHeight: '44px',
}
