import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { billingApi } from '../../services/api'
import { showApiError } from '../../services/toasts'

interface Props {
  type: 'documents' | 'queries'
  onClose: () => void
}

export default function UpgradePrompt({ type, onClose }: Props) {
  const [isRedirecting, setIsRedirecting] = useState(false)
  const { data: billingConfig } = useQuery({
    queryKey: ['billingConfig'],
    queryFn: () => billingApi.getConfig().then(response => response.data),
    staleTime: 5 * 60_000,
  })
  const paymentsEnabled = billingConfig?.payments_enabled ?? false

  const checkoutMutation = useMutation({
    mutationFn: () => billingApi.createCheckout(),
    onSuccess: (res) => {
      setIsRedirecting(true)
      window.location.href = res.data.checkout_url
    },
    onError: (error: unknown) => {
      showApiError(error, 'Unable to start checkout', 'upgrade-checkout-error')
    },
  })

  const messages = {
    documents: {
      title: 'Document Limit Reached',
      description: "You've reached the Free tier limit of 3 documents. Upgrade to Pro for unlimited uploads.",
      icon: '📄',
    },
    queries: {
      title: 'Daily Query Limit Reached',
      description: "You've used all 20 daily queries on the Free tier. Upgrade to Pro for unlimited queries.",
      icon: '💬',
    },
  }

  const msg = messages[type]

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)',
    }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#1a1b23', borderRadius: '20px', padding: '40px',
          maxWidth: '440px', width: '90%',
          border: '1px solid rgba(139,92,246,0.3)',
          boxShadow: '0 0 60px rgba(99,102,241,0.15)',
          animation: 'modalAppear 0.2s ease-out',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ fontSize: '3rem', textAlign: 'center', marginBottom: '16px' }}>{msg.icon}</div>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 700, textAlign: 'center', color: '#fff', marginBottom: '8px' }}>
          {msg.title}
        </h2>
        <p style={{ color: '#9ca3af', textAlign: 'center', fontSize: '0.9rem', lineHeight: 1.5, marginBottom: '32px' }}>
          {msg.description}
        </p>

        {/* Pro features mini-list */}
        <div style={{
          background: 'rgba(99,102,241,0.08)', borderRadius: '12px', padding: '16px',
          marginBottom: '24px',
        }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#818cf8', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Pro includes
          </div>
          {['Unlimited documents', 'Unlimited daily query quota'].map((f, i) => (
            <div key={i} style={{ fontSize: '0.82rem', color: '#d1d5db', padding: '3px 0', display: 'flex', gap: '6px', alignItems: 'center' }}>
              <span style={{ color: '#8b5cf6' }}>✓</span> {f}
            </div>
          ))}
        </div>

        <button
          onClick={() => checkoutMutation.mutate()}
          disabled={checkoutMutation.isPending || isRedirecting || !paymentsEnabled}
          style={{
            width: '100%', padding: '14px', borderRadius: '12px',
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            border: 'none', color: '#fff', fontWeight: 600, fontSize: '0.95rem',
            cursor: paymentsEnabled ? 'pointer' : 'not-allowed', marginBottom: '12px',
            opacity: (checkoutMutation.isPending || isRedirecting || !paymentsEnabled) ? 0.7 : 1,
          }}
        >
          {isRedirecting ? 'Redirecting to Stripe...' : checkoutMutation.isPending ? 'Loading...' : paymentsEnabled ? 'Upgrade to Pro' : 'Payments disabled'}
        </button>

        <button
          onClick={onClose}
          style={{
            width: '100%', padding: '10px', borderRadius: '10px',
            background: 'transparent', border: '1px solid rgba(255,255,255,0.1)',
            color: '#6b7280', fontSize: '0.85rem', cursor: 'pointer',
          }}
        >
          Maybe Later
        </button>
      </div>

      <style>{`
        @keyframes modalAppear {
          from { opacity: 0; transform: scale(0.95) translateY(10px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
      `}</style>
    </div>
  )
}
