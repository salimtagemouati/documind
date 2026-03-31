interface Stats {
  documents_uploaded: number
  queries_made: number
  ai_tokens_used: number
  avg_query_latency_ms?: number
  cache_hit_rate?: number
}

export default function StatsBar({ stats }: { stats?: Stats }) {
  if (!stats) return null
  const items = [
    { label: 'Documents', value: stats.documents_uploaded },
    { label: 'Queries', value: stats.queries_made },
    { label: 'Tokens used', value: stats.ai_tokens_used.toLocaleString() },
    { label: 'Avg latency', value: stats.avg_query_latency_ms ? `${Math.round(stats.avg_query_latency_ms)}ms` : '—' },
    { label: 'Cache rate', value: stats.cache_hit_rate ? `${Math.round(stats.cache_hit_rate * 100)}%` : '—' },
  ]

  return (
    <div style={{
      display: 'flex', gap: '0', borderBottom: '1px solid rgba(255,255,255,0.07)',
      background: '#0a0d15', flexShrink: 0
    }}>
      {items.map((item, i) => (
        <div key={i} style={{
          padding: '8px 20px', borderRight: '1px solid rgba(255,255,255,0.05)',
          display: 'flex', flexDirection: 'column', gap: '2px'
        }}>
          <div style={{ fontSize: '0.65rem', fontFamily: 'monospace', color: '#374151', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
            {item.label}
          </div>
          <div style={{ fontSize: '0.88rem', fontWeight: 600, color: '#818cf8', fontFamily: 'monospace' }}>
            {item.value}
          </div>
        </div>
      ))}
    </div>
  )
}
