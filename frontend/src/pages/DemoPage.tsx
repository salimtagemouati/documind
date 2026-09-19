import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import toast from 'react-hot-toast'

export default function DemoPage() {
  const { loginAsDemo } = useAuthStore()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    const initDemo = async () => {
      try {
        await loginAsDemo()
        if (mounted) {
          toast.success('Welcome to DocuMind Public Demo!')
          navigate('/dashboard', { replace: true })
        }
      } catch (err: any) {
        if (mounted) {
          const msg = err?.response?.data?.detail || 'Failed to initialize demo session'
          setError(typeof msg === 'string' ? msg : JSON.stringify(msg))
          toast.error('Could not connect to demo. Please try again.')
        }
      }
    }
    initDemo()
    return () => { mounted = false }
  }, [loginAsDemo, navigate])

  return (
    <div style={{
      minHeight: '100vh',
      background: '#0f1117',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#fff',
      fontFamily: "'Inter', sans-serif",
      padding: '24px'
    }}>
      <div style={{
        background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
        borderRadius: '12px',
        padding: '8px 14px',
        fontSize: '1.2rem',
        fontWeight: 700,
        marginBottom: '20px'
      }}>DM</div>

      <h2 style={{ fontSize: '1.2rem', fontWeight: 600, marginBottom: '8px' }}>
        {error ? 'Demo Connection Issue' : 'Launching DocuMind Public Demo...'}
      </h2>
      <p style={{ color: '#9ca3af', fontSize: '0.85rem', maxWidth: '360px', textAlign: 'center', marginBottom: '20px' }}>
        {error ? error : 'Preparing pre-seeded benchmark documents with pgvector embeddings and AI analysis...'}
      </p>

      {error ? (
        <button
          onClick={() => navigate('/login')}
          style={{
            padding: '10px 20px',
            background: '#6366f1',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '0.85rem',
            fontWeight: 600
          }}
        >
          Go to Sign In
        </button>
      ) : (
        <div style={{
          width: '32px',
          height: '32px',
          border: '3px solid rgba(255,255,255,0.1)',
          borderTopColor: '#6366f1',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite'
        }} />
      )}
    </div>
  )
}
