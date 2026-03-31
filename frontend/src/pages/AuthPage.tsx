import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import toast from 'react-hot-toast'

type Mode = 'login' | 'register'

export default function AuthPage({ mode }: { mode: Mode }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [loading, setLoading] = useState(false)
  const { login, register } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      if (mode === 'login') {
        await login(email, password)
        toast.success('Welcome back!')
      } else {
        await register(email, password, fullName)
        toast.success('Account created!')
      }
      navigate('/dashboard')
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Something went wrong'
      toast.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', background: '#0f1117',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: "'Inter', sans-serif", padding: '24px'
    }}>
      <div style={{ width: '100%', maxWidth: '400px' }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '40px' }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: '10px',
            fontSize: '1.5rem', fontWeight: 700, color: '#fff'
          }}>
            <span style={{
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
              borderRadius: '10px', padding: '6px 10px', fontSize: '1.1rem'
            }}>DM</span>
            DocuMind
          </div>
          <p style={{ color: '#6b7280', marginTop: '8px', fontSize: '0.9rem' }}>
            {mode === 'login' ? 'Sign in to your workspace' : 'Create your free account'}
          </p>
        </div>

        {/* Card */}
        <div style={{
          background: '#1a1d27', border: '1px solid rgba(255,255,255,0.07)',
          borderRadius: '16px', padding: '32px'
        }}>
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {mode === 'register' && (
              <div>
                <label style={labelStyle}>Full name</label>
                <input
                  type="text" placeholder="Salim Tazi" value={fullName}
                  onChange={e => setFullName(e.target.value)}
                  style={inputStyle}
                />
              </div>
            )}
            <div>
              <label style={labelStyle}>Email</label>
              <input
                type="email" required placeholder="you@example.com" value={email}
                onChange={e => setEmail(e.target.value)} style={inputStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>Password</label>
              <input
                type="password" required placeholder={mode === 'register' ? 'Min 8 chars, 1 upper, 1 digit' : '••••••••'}
                value={password} onChange={e => setPassword(e.target.value)} style={inputStyle}
              />
            </div>
            <button type="submit" disabled={loading} style={{
              ...btnPrimary,
              opacity: loading ? 0.6 : 1,
              cursor: loading ? 'not-allowed' : 'pointer',
              marginTop: '8px'
            }}>
              {loading ? 'Please wait...' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>

          <p style={{ textAlign: 'center', marginTop: '20px', fontSize: '0.85rem', color: '#6b7280' }}>
            {mode === 'login' ? (
              <>Don't have an account? <Link to="/register" style={{ color: '#818cf8', textDecoration: 'none' }}>Sign up free</Link></>
            ) : (
              <>Already have an account? <Link to="/login" style={{ color: '#818cf8', textDecoration: 'none' }}>Sign in</Link></>
            )}
          </p>
        </div>

        <p style={{ textAlign: 'center', marginTop: '24px', fontSize: '0.75rem', color: '#374151' }}>
          RAG · Entity Extraction · Sentiment · Q&A · Powered by GPT-4
        </p>
      </div>
    </div>
  )
}

const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: '0.8rem', fontWeight: 500,
  color: '#9ca3af', marginBottom: '6px'
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '10px 14px',
  background: '#0f1117', border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: '8px', color: '#fff', fontSize: '0.9rem',
  outline: 'none', boxSizing: 'border-box'
}

const btnPrimary: React.CSSProperties = {
  width: '100%', padding: '12px',
  background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
  border: 'none', borderRadius: '8px', color: '#fff',
  fontSize: '0.9rem', fontWeight: 600, cursor: 'pointer'
}
