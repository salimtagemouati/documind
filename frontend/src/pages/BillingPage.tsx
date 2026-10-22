import { useQuery, useMutation } from '@tanstack/react-query'
import { billingApi } from '../services/api'
import { showApiError } from '../services/toasts'
import { useAuthStore } from '../store/authStore'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useEffect } from 'react'
import toast from 'react-hot-toast'

interface BillingStatus {
  tier: string
  status: string
  is_pro: boolean
  limits: {
    documents: { used: number; limit: number | null; remaining: number | null }
    queries_per_day: { used: number; limit: number | null; remaining: number | null }
  }
}

export default function BillingPage() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  // Handle Stripe redirect callbacks
  useEffect(() => {
    const status = searchParams.get('status')
    if (status === 'success') {
      toast.success('🎉 Welcome to Pro! Your upgrade is active.', { duration: 5000 })
    } else if (status === 'canceled') {
      toast('Checkout was canceled. No charges were made.', { icon: '↩️' })
    }
  }, [searchParams])

  const { data: billing, isLoading } = useQuery<BillingStatus>({
    queryKey: ['billingStatus'],
    queryFn: () => billingApi.getStatus().then(r => r.data),
  })
  const { data: billingConfig } = useQuery({
    queryKey: ['billingConfig'],
    queryFn: () => billingApi.getConfig().then(r => r.data),
    staleTime: 5 * 60_000,
  })

  const checkoutMutation = useMutation({
    mutationFn: () => billingApi.createCheckout(),
    onSuccess: (res) => {
      window.location.href = res.data.checkout_url
    },
    onError: (error: unknown) => {
      showApiError(error, 'Unable to start checkout', 'billing-checkout-error')
    },
  })

  const portalMutation = useMutation({
    mutationFn: () => billingApi.createPortal(),
    onSuccess: (res) => {
      window.location.href = res.data.portal_url
    },
    onError: (error: unknown) => {
      showApiError(error, 'Unable to open billing portal', 'billing-portal-error')
    },
  })

  const isPro = billing?.is_pro ?? false
  const paymentsEnabled = billingConfig?.payments_enabled ?? false

  return (
    <div style={{ minHeight: '100vh', background: '#0f1117', color: '#fff', fontFamily: 'inherit' }}>
      {/* Nav */}
      <nav style={{
        height: '56px', borderBottom: '1px solid rgba(255,255,255,0.07)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 24px', background: '#0f1117',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}
          onClick={() => navigate('/dashboard')}>
          <div style={{
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            borderRadius: '8px', padding: '4px 8px', fontSize: '0.85rem', fontWeight: 700,
          }}>DM</div>
          <span style={{ fontWeight: 600, fontSize: '1rem' }}>DocuMind</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button onClick={() => navigate('/dashboard')} style={navBtn}>← Dashboard</button>
          <span style={{ fontSize: '0.82rem', color: '#6b7280' }}>{user?.email}</span>
          <button onClick={logout} style={navBtn}>Sign out</button>
        </div>
      </nav>

      {/* Content */}
      <div style={{ maxWidth: '900px', margin: '0 auto', padding: '48px 24px' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 700, marginBottom: '8px' }}>
          Billing & Subscription
        </h1>
        <p style={{ color: '#6b7280', fontSize: '0.95rem', marginBottom: '48px' }}>
          Manage your plan, track usage, and upgrade for unlimited access.
        </p>

        {isLoading ? (
          <div style={{ display: 'flex', gap: '24px' }}>
            {[1, 2].map(i => (
              <div key={i} style={{ flex: 1, height: '340px', background: 'rgba(255,255,255,0.04)', borderRadius: '16px', animation: 'pulse 1.5s infinite' }} />
            ))}
          </div>
        ) : (
          <>
            {/* Plan cards */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '48px' }}>
              {/* Free Plan */}
              <div style={{
                ...cardBase,
                border: !isPro ? '2px solid rgba(99,102,241,0.5)' : '1px solid rgba(255,255,255,0.08)',
              }}>
                {!isPro && <div style={currentBadge}>Current Plan</div>}
                <h2 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '4px' }}>Free</h2>
                <div style={{ fontSize: '2.2rem', fontWeight: 800, color: '#e5e7eb', marginBottom: '8px' }}>
                  $0<span style={{ fontSize: '0.9rem', fontWeight: 400, color: '#6b7280' }}>/month</span>
                </div>
                <p style={{ color: '#6b7280', fontSize: '0.85rem', marginBottom: '24px' }}>
                  Perfect for trying out DocuMind
                </p>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {[
                    `${billing?.limits.documents.limit ?? 3} documents`,
                    `${billing?.limits.queries_per_day.limit ?? 20} queries/day`,
                    'PDF, DOCX, TXT support',
                    'AI summaries & entities',
                    'RAG Q&A',
                  ].map((f, i) => (
                    <li key={i} style={featureItem}>
                      <span style={{ color: '#6b7280' }}>✓</span> {f}
                    </li>
                  ))}
                </ul>
                {!isPro && (
                  <div style={{ marginTop: '24px', padding: '12px', background: 'rgba(99,102,241,0.08)', borderRadius: '10px', fontSize: '0.8rem', color: '#818cf8' }}>
                    You're on the Free plan
                  </div>
                )}
              </div>

              {/* Pro Plan */}
              <div style={{
                ...cardBase,
                border: isPro ? '2px solid rgba(139,92,246,0.6)' : '1px solid rgba(255,255,255,0.08)',
                background: isPro ? 'rgba(139,92,246,0.06)' : 'rgba(255,255,255,0.03)',
              }}>
                {isPro && <div style={{ ...currentBadge, background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}>Current Plan</div>}
                {!isPro && <div style={{ ...currentBadge, background: 'linear-gradient(135deg, #f59e0b, #f97316)', color: '#fff' }}>{paymentsEnabled ? 'Available' : 'Payments disabled'}</div>}
                <h2 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '4px' }}>Pro</h2>
                <div style={{ fontSize: '2.2rem', fontWeight: 800, color: '#e5e7eb', marginBottom: '8px' }}>
                  Pro<span style={{ fontSize: '0.9rem', fontWeight: 400, color: '#6b7280' }}> via Stripe</span>
                </div>
                <p style={{ color: '#6b7280', fontSize: '0.85rem', marginBottom: '24px' }}>
                  Unlimited document and daily query quotas
                </p>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {[
                    'Unlimited documents',
                    'Unlimited daily query quota',
                    'PDF, DOCX, TXT support',
                    'AI summaries and entities',
                    'RAG Q&A with citations',
                  ].map((f, i) => (
                    <li key={i} style={featureItem}>
                      <span style={{ color: '#8b5cf6' }}>✓</span> {f}
                    </li>
                  ))}
                </ul>

                {isPro ? (
                  <button
                    onClick={() => portalMutation.mutate()}
                    disabled={portalMutation.isPending}
                    style={{ ...actionBtn, background: 'transparent', border: '1px solid rgba(139,92,246,0.4)', color: '#a78bfa', marginTop: '24px' }}
                  >
                    {portalMutation.isPending ? 'Opening...' : 'Manage Subscription'}
                  </button>
                ) : (
                  <button
                    onClick={() => checkoutMutation.mutate()}
                    disabled={checkoutMutation.isPending || !paymentsEnabled}
                    style={{
                      ...actionBtn,
                      marginTop: '24px',
                      cursor: paymentsEnabled ? 'pointer' : 'not-allowed',
                      opacity: paymentsEnabled ? 1 : 0.55,
                    }}
                  >
                    {checkoutMutation.isPending ? 'Redirecting...' : paymentsEnabled ? 'Upgrade to Pro' : 'Payments disabled'}
                  </button>
                )}
              </div>
            </div>

            {/* Usage section */}
            <h2 style={{ fontSize: '1.2rem', fontWeight: 600, marginBottom: '20px' }}>Current Usage</h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <UsageCard
                title="Documents"
                used={billing?.limits.documents.used ?? 0}
                limit={billing?.limits.documents.limit ?? null}
                icon="📄"
                color="#6366f1"
              />
              <UsageCard
                title="Queries Today"
                used={billing?.limits.queries_per_day.used ?? 0}
                limit={billing?.limits.queries_per_day.limit ?? null}
                icon="💬"
                color="#8b5cf6"
              />
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function UsageCard({ title, used, limit, icon, color }: {
  title: string; used: number; limit: number | null; icon: string; color: string
}) {
  const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : null
  const isNearLimit = pct !== null && pct >= 80

  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)', borderRadius: '12px', padding: '20px',
      border: '1px solid rgba(255,255,255,0.08)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <span style={{ fontSize: '0.85rem', color: '#9ca3af', fontWeight: 500 }}>{icon} {title}</span>
        <span style={{
          fontSize: '0.75rem', fontFamily: 'monospace',
          color: isNearLimit ? '#ef4444' : '#6b7280',
        }}>
          {used}{limit !== null ? ` / ${limit}` : ' (unlimited)'}
        </span>
      </div>
      {pct !== null && (
        <div style={{ width: '100%', height: '6px', background: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow: 'hidden' }}>
          <div style={{
            width: '100%', height: '100%',
            background: isNearLimit
              ? 'linear-gradient(90deg, #f59e0b, #ef4444)'
              : `linear-gradient(90deg, ${color}, ${color}88)`,
            borderRadius: '3px', transform: `scaleX(${pct / 100})`,
            transformOrigin: 'left center', transition: 'transform 0.5s ease-out',
          }} />
        </div>
      )}
      {pct === null && (
        <div style={{ fontSize: '0.75rem', color: '#10b981', fontWeight: 500 }}>
          ∞ Unlimited
        </div>
      )}
    </div>
  )
}

// ─── Styles ──────────────────────────────────────────────────────────────────
const navBtn: React.CSSProperties = {
  fontSize: '0.8rem', padding: '6px 14px', borderRadius: '6px',
  background: 'transparent', border: '1px solid rgba(255,255,255,0.1)',
  color: '#9ca3af', cursor: 'pointer',
}

const cardBase: React.CSSProperties = {
  background: 'rgba(255,255,255,0.03)', borderRadius: '16px', padding: '32px',
  position: 'relative',
}

const currentBadge: React.CSSProperties = {
  position: 'absolute', top: '16px', right: '16px',
  fontSize: '0.65rem', fontWeight: 600, textTransform: 'uppercase',
  letterSpacing: '0.05em', padding: '4px 10px', borderRadius: '20px',
  background: 'rgba(99,102,241,0.2)', color: '#818cf8',
}

const featureItem: React.CSSProperties = {
  padding: '6px 0', fontSize: '0.85rem', color: '#d1d5db',
  display: 'flex', gap: '8px', alignItems: 'center',
}

const actionBtn: React.CSSProperties = {
  width: '100%', padding: '12px', borderRadius: '10px',
  background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
  border: 'none', color: '#fff', fontWeight: 600, fontSize: '0.9rem',
  cursor: 'pointer', transition: 'transform 0.15s, box-shadow 0.15s',
}
