import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getApiErrorMessage, waitForApi } from '../services/api'
import { useAuthStore } from '../store/authStore'

type DemoState = 'connecting' | 'waking' | 'error'

export default function DemoPage() {
  const { loginAsDemo } = useAuthStore()
  const navigate = useNavigate()
  const [demoState, setDemoState] = useState<DemoState>('connecting')
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const wakeMessageTimer = window.setTimeout(() => setDemoState('waking'), 3000)

    const initDemo = async () => {
      setDemoState('connecting')
      setError(null)
      try {
        await waitForApi(60_000, controller.signal)
        if (controller.signal.aborted) return
        await loginAsDemo()
        if (!controller.signal.aborted) navigate('/dashboard', { replace: true })
      } catch (caught: unknown) {
        if (controller.signal.aborted) return
        setError(getApiErrorMessage(caught, 'Impossible de démarrer la démo. Réessaie dans un instant.'))
        setDemoState('error')
      } finally {
        window.clearTimeout(wakeMessageTimer)
      }
    }

    void initDemo()
    return () => {
      controller.abort()
      window.clearTimeout(wakeMessageTimer)
    }
  }, [attempt, loginAsDemo, navigate])

  const isWaiting = demoState !== 'error'

  return (
    <div style={{
      minHeight: '100vh',
      background: '#0f1117',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#fff',
      fontFamily: 'inherit',
      padding: '24px',
    }}>
      <div style={{
        background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
        borderRadius: '12px',
        padding: '8px 14px',
        fontSize: '1.2rem',
        fontWeight: 700,
        marginBottom: '20px',
      }}>DM</div>

      <h1 style={{ fontSize: '1.2rem', fontWeight: 600, marginBottom: '8px' }}>
        {demoState === 'error' ? 'Demo connection issue' : 'Launching the public demo'}
      </h1>
      <p aria-live="polite" style={{ color: '#9ca3af', fontSize: '0.9rem', lineHeight: 1.5, maxWidth: '420px', textAlign: 'center', marginBottom: '20px' }}>
        {demoState === 'waking'
          ? 'Réveil du serveur… ça peut prendre jusqu’à une minute. La connexion sera retentée automatiquement.'
          : error ?? 'Checking the API and preparing the seeded read-only workspace…'}
      </p>

      {isWaiting ? (
        <div
          role="status"
          aria-label="Connecting to the demo"
          style={{
            width: '32px',
            height: '32px',
            border: '3px solid rgba(255,255,255,0.1)',
            borderTopColor: '#818cf8',
            borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
          }}
        />
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', justifyContent: 'center' }}>
          <button type="button" onClick={() => setAttempt(value => value + 1)} style={primaryButtonStyle}>
            Retry demo
          </button>
          <button type="button" onClick={() => navigate('/login')} style={secondaryButtonStyle}>
            Go to sign in
          </button>
        </div>
      )}
    </div>
  )
}

const primaryButtonStyle: React.CSSProperties = {
  padding: '10px 20px',
  background: '#6366f1',
  color: '#fff',
  border: 'none',
  borderRadius: '8px',
  cursor: 'pointer',
  fontSize: '0.85rem',
  fontWeight: 600,
}

const secondaryButtonStyle: React.CSSProperties = {
  ...primaryButtonStyle,
  background: 'transparent',
  border: '1px solid rgba(255,255,255,0.16)',
  color: '#d1d5db',
}
