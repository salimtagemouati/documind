import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import './LandingPage.css'

/* ─── SVG Icon Components ─── */
const IconSearch = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
  </svg>
)

const IconFileText = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
    <polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/><line x1="10" x2="8" y1="9" y2="9"/>
  </svg>
)

const IconUsers = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
    <path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
  </svg>
)

const IconBarChart = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" x2="12" y1="20" y2="10"/><line x1="18" x2="18" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="16"/>
  </svg>
)

const IconClock = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
  </svg>
)

const IconUpload = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>
  </svg>
)

const IconCpu = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/>
    <path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/>
  </svg>
)

const IconMessageCircle = () => (
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22z"/>
  </svg>
)

const IconCheck = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12"/>
  </svg>
)

const IconArrowRight = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>
  </svg>
)

const IconGithub = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
  </svg>
)

/* ─── Data ─── */
const features = [
  {
    icon: <IconSearch />,
    color: 'indigo',
    title: 'RAG-Powered Q&A',
    desc: 'Ask natural language questions and get precise answers grounded in your documents with source citations.',
  },
  {
    icon: <IconFileText />,
    color: 'violet',
    title: 'Smart Summarization',
    desc: 'Map-reduce summarization that captures key insights from lengthy documents in seconds.',
  },
  {
    icon: <IconUsers />,
    color: 'cyan',
    title: 'Entity Extraction',
    desc: 'Automatically identify and extract people, organizations, locations, dates, and monetary values.',
  },
  {
    icon: <IconBarChart />,
    color: 'emerald',
    title: 'Sentiment Analysis',
    desc: 'Understand the emotional tone and sentiment distribution across your document content.',
  },
  {
    icon: <IconClock />,
    color: 'amber',
    title: 'Query History',
    desc: 'Full history of every question asked, with cached responses for instant retrieval.',
  },
]

const steps = [
  {
    icon: <IconUpload />,
    title: 'Upload Documents',
    desc: 'Drop any PDF, Word document, or text file. Processing starts instantly in the background.',
  },
  {
    icon: <IconCpu />,
    title: 'AI Processes',
    desc: 'Documents are chunked, embedded into vectors, and analyzed with Gemini AI for entities, sentiment, and summaries.',
  },
  {
    icon: <IconMessageCircle />,
    title: 'Ask Questions',
    desc: 'Query your documents in natural language. Get grounded answers with exact source citations.',
  },
]

const stats = [
  { value: '200+', label: 'Documents analyzed' },
  { value: '10k+', label: 'Queries answered' },
  { value: '<2s', label: 'Avg response time' },
]

const freePlanFeatures = [
  `Up to ${10} documents`,
  'Unlimited AI queries',
  'PDF, DOCX, TXT support',
  'Entity extraction',
  'Sentiment analysis',
  'RAG Q&A',
]

/* ─── Intersection Observer Hook ─── */
function useReveal() {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.classList.add('revealed')
          observer.unobserve(el)
        }
      },
      { threshold: 0.15, rootMargin: '0px 0px -40px 0px' }
    )

    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return ref
}

function RevealSection({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  const ref = useReveal()
  return (
    <div ref={ref} className={`reveal ${className}`}>
      {children}
    </div>
  )
}

/* ─── LANDING PAGE COMPONENT ─── */
export default function LandingPage() {
  return (
    <div className="landing">
      {/* ─── NAVBAR ─── */}
      <nav className="landing-nav" id="landing-nav">
        <Link to="/" className="nav-logo">
          <span className="nav-logo-mark">DM</span>
          DocuMind
        </Link>
        <ul className="nav-links nav-links-desktop">
          <li><a href="#features">Features</a></li>
          <li><a href="#how-it-works">How It Works</a></li>
          <li><a href="#pricing">Pricing</a></li>
          <li><Link to="/login">Sign In</Link></li>
          <li><Link to="/register" className="nav-cta">Get Started Free</Link></li>
        </ul>
      </nav>

      {/* ─── HERO ─── */}
      <section className="hero" id="hero">
        <div className="hero-bg">
          <div className="hero-orb hero-orb--indigo" />
          <div className="hero-orb hero-orb--violet" />
          <div className="hero-orb hero-orb--cyan" />
          <div className="hero-grid" />
        </div>

        <div className="hero-content">
          <div className="hero-badge fade-up">
            <span className="hero-badge-dot" />
            Powered by Gemini AI &amp; FAISS Vector Search
          </div>

          <h1 className="hero-title fade-up fade-up-d1">
            Turn Documents Into<br />
            <span className="hero-title-gradient">Actionable Intelligence</span>
          </h1>

          <p className="hero-subtitle fade-up fade-up-d2">
            Upload any document and instantly extract summaries, entities,
            sentiment — then ask questions and get AI-grounded answers
            with source citations.
          </p>

          <div className="hero-actions fade-up fade-up-d3">
            <Link to="/register" className="btn btn-primary" id="cta-get-started">
              Get Started Free
              <IconArrowRight />
            </Link>
            <a href="#how-it-works" className="btn btn-secondary" id="cta-view-demo">
              See How It Works
            </a>
          </div>
        </div>
      </section>

      <div className="section-divider" />

      {/* ─── FEATURES ─── */}
      <section className="landing-section" id="features">
        <div className="section-inner">
          <RevealSection>
            <div className="section-header">
              <div className="section-label">
                <span className="section-label-line" />
                Capabilities
              </div>
              <h2 className="section-title">Everything You Need to<br />Understand Your Documents</h2>
              <p className="section-subtitle">
                A complete AI document intelligence toolkit — from extraction to conversation.
              </p>
            </div>
          </RevealSection>

          <RevealSection>
            <div className="features-grid">
              {features.slice(0, 3).map((f, i) => (
                <div className="feature-card" key={i} id={`feature-card-${i}`}>
                  <div className={`feature-icon feature-icon--${f.color}`}>
                    {f.icon}
                  </div>
                  <h3 className="feature-title">{f.title}</h3>
                  <p className="feature-desc">{f.desc}</p>
                </div>
              ))}
            </div>
            <div className="features-bottom-row">
              {features.slice(3).map((f, i) => (
                <div className="feature-card" key={i + 3} id={`feature-card-${i + 3}`}>
                  <div className={`feature-icon feature-icon--${f.color}`}>
                    {f.icon}
                  </div>
                  <h3 className="feature-title">{f.title}</h3>
                  <p className="feature-desc">{f.desc}</p>
                </div>
              ))}
            </div>
          </RevealSection>
        </div>
      </section>

      <div className="section-divider" />

      {/* ─── HOW IT WORKS ─── */}
      <section className="landing-section" id="how-it-works">
        <div className="section-inner">
          <RevealSection>
            <div className="section-header">
              <div className="section-label">
                <span className="section-label-line" />
                Workflow
              </div>
              <h2 className="section-title">Three Steps to Document Intelligence</h2>
              <p className="section-subtitle">
                From raw document to intelligent conversation in under a minute.
              </p>
            </div>
          </RevealSection>

          <RevealSection>
            <div className="steps-grid">
              {steps.map((s, i) => (
                <div className="step-card" key={i} id={`step-card-${i}`}>
                  <div className="step-number">
                    {s.icon}
                  </div>
                  <h3 className="step-title">{s.title}</h3>
                  <p className="step-desc">{s.desc}</p>
                </div>
              ))}
            </div>
          </RevealSection>
        </div>
      </section>

      <div className="section-divider" />

      {/* ─── STATS ─── */}
      <section className="landing-section" id="stats">
        <div className="section-inner">
          <RevealSection>
            <div className="landing-stats">
              {stats.map((s, i) => (
                <div className="stat-item" key={i} id={`stat-item-${i}`}>
                  <div className="stat-value">{s.value}</div>
                  <div className="stat-label">{s.label}</div>
                </div>
              ))}
            </div>
          </RevealSection>
        </div>
      </section>

      <div className="section-divider" />

      {/* ─── PRICING ─── */}
      <section className="landing-section" id="pricing">
        <div className="section-inner">
          <RevealSection>
            <div className="section-header">
              <div className="section-label">
                <span className="section-label-line" />
                Pricing
              </div>
              <h2 className="section-title">Free While in Beta</h2>
              <p className="section-subtitle">
                No payments, no credit card. Just sign up and start analyzing documents.
              </p>
            </div>
          </RevealSection>

          <RevealSection>
            <div className="pricing-grid" style={{ justifyContent: 'center' }}>
              {/* Free Tier */}
              <div className="pricing-card" id="pricing-free">
                <div className="pricing-name">Free</div>
                <div className="pricing-price">
                  <span className="pricing-amount">$0</span>
                  <span className="pricing-period">/ month</span>
                </div>
                <p className="pricing-desc">Everything you need to try DocuMind today.</p>
                <ul className="pricing-features">
                  {freePlanFeatures.map((feat, i) => (
                    <li key={i}>
                      <span className="pricing-check pricing-check--free"><IconCheck /></span>
                      {feat}
                    </li>
                  ))}
                </ul>
                <Link to="/register" className="btn btn-primary btn-pricing" id="pricing-free-cta">
                  Get Started Free
                  <IconArrowRight />
                </Link>
              </div>
            </div>
          </RevealSection>
        </div>
      </section>

      <div className="section-divider" />

      {/* ─── FOOTER ─── */}
      <footer className="landing-footer" id="landing-footer">
        <div className="footer-inner">
          <div className="footer-brand">
            <span className="nav-logo-mark" style={{ fontSize: '0.7rem', padding: '3px 7px' }}>DM</span>
            DocuMind
          </div>
          <ul className="footer-links">
            <li><a href="#features">Features</a></li>
            <li><a href="#pricing">Pricing</a></li>
            <li>
              <a href="https://github.com" target="_blank" rel="noopener noreferrer" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                <IconGithub /> GitHub
              </a>
            </li>
          </ul>
          <span className="footer-copyright">© {new Date().getFullYear()} DocuMind. All rights reserved.</span>
        </div>
      </footer>
    </div>
  )
}
