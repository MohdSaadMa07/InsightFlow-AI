import { useState, useEffect, useRef } from 'react'
import { api } from '../api'

function useReveal() {
  const ref = useRef(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setVisible(true); obs.disconnect() } }, { threshold: 0.1 })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])
  return [ref, visible]
}

function Reveal({ children, delay = 0 }) {
  const [ref, visible] = useReveal()
  return (
    <div ref={ref} style={{
      opacity: visible ? 1 : 0, transform: visible ? 'translateY(0)' : 'translateY(30px)',
      transition: `all 0.7s cubic-bezier(0.16, 1, 0.3, 1) ${delay}s`,
    }}>{children}</div>
  )
}

export default function Landing({ onAuth }) {
  const [authMode, setAuthMode] = useState(null)
  const [form, setForm] = useState({ username: '', email: '', password: '', organization_name: '' })
  const [error, setError] = useState('')

  function set(field) {
    return (e) => setForm(prev => ({ ...prev, [field]: e.target.value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      if (authMode === 'login') {
        const data = await api.auth.login({ username: form.username, password: form.password })
        onAuth(data.token)
      } else {
        const data = await api.auth.signup(form)
        onAuth(data.token)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="landing">
      <div className="noise-overlay" />

      <nav className="landing-nav">
        <div className="landing-logo">InsightFlowAI</div>
        <div className="landing-nav-links">
          <a href="#how-it-works">How It Works</a>
          <a href="#features">Features</a>
          <a href="#tech">Technology</a>
          <a href="/developers" style={{ color: '#22d3ee' }}>{'</>'} Developers</a>
        </div>
        <div className="landing-nav-actions">
          <button onClick={() => setAuthMode('login')} className="btn btn-ghost btn-sm">Sign In</button>
          <button onClick={() => setAuthMode('signup')} className="btn btn-primary bg-gradient btn-sm">Get Started</button>
        </div>
      </nav>

      {/* ── HERO ── */}
      <section className="landing-hero">
        <div className="hero-grid-bg" />
        <div className="hero-glow-g" />
        <div className="hero-glow-p" />
        <div className="floating-dots">
          {[...Array(12)].map((_, i) => <div key={i} className="dot" style={{
            left: `${10 + (i * 7.5) % 85}%`, top: `${15 + (i * 13) % 70}%`,
            width: `${2 + (i % 3) * 2}px`, height: `${2 + (i % 3) * 2}px`,
            animationDelay: `${i * 1.3}s`, animationDuration: `${3 + (i % 3)}s`,
          }} />)}
        </div>

        <Reveal>
          <div className="hero-badge-row">
            <span className="hero-badge">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#22D3EE" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              Deep Learning
            </span>
            <span className="hero-badge">Autoencoder Engine</span>
            <span className="hero-badge">Real-time Analytics</span>
          </div>
        </Reveal>

        <Reveal delay={0.15}>
          <h1 className="hero-title">
            <span className="hero-title-line">Surface every signal</span>
            <span className="hero-title-line hero-title-accent">before it matters</span>
          </h1>
        </Reveal>

        <Reveal delay={0.3}>
          <p className="hero-subtitle">
            Open-source product intelligence with dense autoencoder anomaly detection,
            TFT revenue forecasting, and transformer-powered churn prediction —
            <span className="text-highlight"> catch everything.</span>
          </p>
        </Reveal>

        <Reveal delay={0.45}>
          <div className="landing-actions">
            <button onClick={() => setAuthMode('signup')} className="btn btn-primary bg-gradient btn-lg hero-cta">
              Deploy Your First Project
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
            </button>
            <a href="#features" className="btn btn-glass btn-lg">Explore Features</a>
          </div>
        </Reveal>
      </section>

      {/* ── STATS ── */}
      <Reveal>
        <section className="stats-bar">
          <div className="stats-item"><span className="stats-value">4</span><span className="stats-label">ML Models</span></div>
          <div className="stats-item"><span className="stats-value">Real-time</span><span className="stats-label">Event Pipeline</span></div>
          <div className="stats-item"><span className="stats-value">3</span><span className="stats-label">Prediction Engines</span></div>
          <div className="stats-item"><span className="stats-value">Kafka → CH</span><span className="stats-label">Data Stack</span></div>
        </section>
      </Reveal>

      {/* ── HOW IT WORKS ── */}
      <section id="how-it-works" className="section">
        <Reveal>
          <h2 className="section-title">How It Works</h2>
          <p className="section-desc">From raw events to actionable intelligence in three steps</p>
        </Reveal>

        <div className="steps-wrapper">
          <svg className="steps-connector" viewBox="0 0 300 60" preserveAspectRatio="none">
            <path d="M 0 30 Q 75 0, 150 30 T 300 30" fill="none" stroke="url(#sg)" strokeWidth="1.5" strokeDasharray="6 6"/>
            <defs><linearGradient id="sg" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor="#22D3EE" stopOpacity="0"/><stop offset="50%" stopColor="#22D3EE" stopOpacity="0.3"/><stop offset="100%" stopColor="#22D3EE" stopOpacity="0"/></linearGradient></defs>
          </svg>
          <div className="steps-grid">
            <Reveal delay={0}><div className="step-card">
              <div className="step-number">01</div>
              <div className="step-icon"><svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#22D3EE" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg></div>
              <h3>Capture Events</h3>
              <p>Drop in our lightweight SDK to stream pageviews, clicks, purchases, and custom events directly to ClickHouse via Kafka.</p>
            </div></Reveal>
            <Reveal delay={0.15}><div className="step-card">
              <div className="step-number">02</div>
              <div className="step-icon"><svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#A78BFA" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg></div>
              <h3>Analyze with ML</h3>
              <p>Four specialized models — autoencoder, transformer, TFT, and clustering — process your data nightly.</p>
            </div></Reveal>
            <Reveal delay={0.3}><div className="step-card">
              <div className="step-number">03</div>
              <div className="step-icon"><svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg></div>
              <h3>Act on Insights</h3>
              <p>Get real-time dashboards, anomaly alerts with root-cause analysis, and actionable recommendations for your team.</p>
            </div></Reveal>
          </div>
        </div>
      </section>

      {/* ── FEATURES ── */}
      <section id="features" className="section">
        <Reveal>
          <h2 className="section-title">Production-Grade Feature Set</h2>
          <p className="section-desc">Everything you need to understand user behavior and grow your product</p>
        </Reveal>

        <div className="features-grid">
          {[
            { icon: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#22D3EE" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>, title: 'Anomaly Detection', desc: 'Dense autoencoder learns normal behavior patterns and flags anomalies via reconstruction error — with per-feature root cause analysis.', tags: ['Autoencoder', 'Unsupervised'], gradient: '#22D3EE' },
            { icon: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>, title: 'Revenue Forecasting', desc: 'Temporal Fusion Transformer generates 30-day forecasts with uncertainty bounds. MRR projections and transaction volume predictions included.', tags: ['TFT', 'Quantile'], gradient: '#F59E0B' },
            { icon: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#EF4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>, title: 'Churn Prediction', desc: 'Transformer model analyzes user session histories with SHAP-based explanations — identify exactly which behaviors drive churn risk.', tags: ['Transformer', 'SHAP'], gradient: '#EF4444' },
            { icon: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>, title: 'Conversion Funnels', desc: 'Multi-step funnel analysis with semantic event mapping. See drop-off rates, compare cohorts, and correlate with churn and revenue.', tags: ['Funnels', 'Semantic'], gradient: '#10B981' },
            { icon: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#06B6D4" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>, title: 'Real-time Pipeline', desc: 'Kafka stream ingestion into ClickHouse for sub-second analytics. Auto-buffering, retry logic, and automatic event schema discovery.', tags: ['Kafka', 'ClickHouse'], gradient: '#06B6D4' },
            { icon: <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#A78BFA" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>, title: 'Self-hosted & Private', desc: 'All models run on your infrastructure. No data leaves your network. Full control — retrain on your schedule, customize features.', tags: ['Privacy-first', 'Open-source'], gradient: '#A78BFA' },
          ].map((f, i) => (
            <Reveal key={f.title} delay={i * 0.08}>
              <div className="feature-card-new" style={{ '--accent': f.gradient }}>
                <div className="card-glow" />
                <div className="fc-icon" style={{ color: f.gradient }}>{f.icon}</div>
                <h3>{f.title}</h3>
                <p>{f.desc}</p>
                <div className="fc-tags">{f.tags.map(t => <span key={t} style={{ borderColor: `${f.gradient}33`, color: f.gradient, background: `${f.gradient}0d` }}>{t}</span>)}</div>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ── TECH ── */}
      <section id="tech" className="section">
        <Reveal>
          <h2 className="section-title">Technology Stack</h2>
          <p className="section-desc">Built with proven, scalable technologies</p>
        </Reveal>
        <div className="tech-grid">
          {[
            ['Django', 'Python API', '#22D3EE'],
            ['React', 'Dashboard UI', '#61DAFB'],
            ['PyTorch', 'ML Engine', '#EF4444'],
            ['ClickHouse', 'Analytics DB', '#F59E0B'],
            ['Kafka', 'Event Stream', '#10B981'],
            ['Celery', 'Task Queue', '#A78BFA'],
            ['Redis', 'Cache & Broker', '#EF4444'],
            ['PostgreSQL', 'App Database', '#3B82F6'],
          ].map(([name, meta, color]) => (
            <Reveal key={name} delay={0.04 * Math.random()}>
              <div className="tech-item" style={{ '--accent': color }}>
                <span>{name}</span>
                <span className="tech-meta">{meta}</span>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="section" style={{ paddingBottom: 40 }}>
        <Reveal>
          <div className="cta-card">
            <div className="cta-glow" />
            <h2>Ready to understand your users?</h2>
            <p>Deploy InsightFlowAI on your infrastructure and get ML-powered product intelligence running in minutes.</p>
            <button onClick={() => setAuthMode('signup')} className="btn btn-primary bg-gradient btn-lg cta-btn">
              Start Building Free
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>
            </button>
          </div>
        </Reveal>
      </section>

      {/* ── FOOTER ── */}
      <footer className="landing-footer">
        <div className="footer-inner">
          <div className="footer-logo">InsightFlowAI</div>
          <span className="footer-text">Open-source product intelligence platform</span>
          <span className="footer-copy">© {new Date().getFullYear()} InsightFlowAI</span>
        </div>
      </footer>

      {/* ── AUTH MODAL ── */}
      {authMode && (
        <div className="modal-overlay" onClick={() => { setAuthMode(null); setError(''); setForm({ username: '', email: '', password: '', organization_name: '' }) }}>
          <div className="modal-content glass-card auth-modal" onClick={e => e.stopPropagation()} style={{ animation: 'modalIn 0.35s cubic-bezier(0.16, 1, 0.3, 1)' }}>
            <button className="modal-close" onClick={() => { setAuthMode(null); setError(''); setForm({ username: '', email: '', password: '', organization_name: '' }) }}>×</button>
            <div style={{ textAlign: 'center', marginBottom: 28 }}>
              
              <h2 style={{ fontSize: 22, fontWeight: 800, color: '#f1f5f9', marginBottom: 4 }}>
                {authMode === 'login' ? 'Welcome Back' : 'Create an Account'}
              </h2>
              <p style={{ color: '#64748b', fontSize: 14 }}>
                {authMode === 'login' ? 'Sign in to your workspace.' : 'Start your free trial — no credit card needed.'}
              </p>
            </div>
            {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}
            <form onSubmit={handleSubmit}>
              <div style={{ marginBottom: 16 }}>
                <label>Username</label>
                <input value={form.username} onChange={set('username')} placeholder="username" required autoFocus />
              </div>
              {authMode === 'signup' && (
                <div style={{ marginBottom: 16 }}>
                  <label>Email</label>
                  <input type="email" value={form.email} onChange={set('email')} placeholder="you@example.com" required />
                </div>
              )}
              <div style={{ marginBottom: 16 }}>
                <label>Password</label>
                <input type="password" value={form.password} onChange={set('password')} placeholder="••••••••" required />
              </div>
              {authMode === 'signup' && (
                <div style={{ marginBottom: 24 }}>
                  <label>Organization Name</label>
                  <input value={form.organization_name} onChange={set('organization_name')} placeholder="My Company" required />
                </div>
              )}
              <button className="btn btn-primary bg-gradient" style={{ width: '100%', padding: '12px', fontSize: '15px' }} type="submit">
                {authMode === 'login' ? 'Sign In' : 'Create Account'}
              </button>
            </form>
            <p style={{ marginTop: 24, textAlign: 'center', fontSize: 13, color: '#64748b' }}>
              {authMode === 'login' ? (
                <>Don't have an account? <span className="text-accent cursor-pointer" onClick={() => { setAuthMode('signup'); setError('') }}>Sign up</span></>
              ) : (
                <>Already have an account? <span className="text-accent cursor-pointer" onClick={() => { setAuthMode('login'); setError('') }}>Sign in</span></>
              )}
            </p>
          </div>
        </div>
      )}

      <style>{`
        /* ── RESET BASE ── */
        .landing { min-height: 100vh; background: #030712; color: #e2e8f0; position: relative; overflow-x: hidden; }
        .noise-overlay {
          position: fixed; inset: 0; z-index: 9999; pointer-events: none;
          opacity: 0.025;
          background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
        }
        * { scroll-behavior: smooth; }
        .text-highlight { color: #67e8f9; }

        /* ── NAV ── */
        .landing-logo { font-size: 20px; font-weight: 800; background: linear-gradient(135deg, #22D3EE, #A78BFA); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -0.5px; display: flex; align-items: center; }
        .landing-nav { display: flex; justify-content: space-between; align-items: center; padding: 16px 40px; position: fixed; top: 0; left: 0; right: 0; z-index: 100; background: rgba(3,7,18,0.75); backdrop-filter: blur(16px); border-bottom: 1px solid rgba(148,163,184,0.06); }
        .landing-nav-links { display: flex; gap: 32px; align-items: center; }
        .landing-nav-links a { color: #64748b; font-size: 14px; font-weight: 500; transition: color 0.2s; text-decoration: none; }
        .landing-nav-links a:hover { color: #e2e8f0; }
        .landing-nav-actions { display: flex; gap: 10px; align-items: center; }
        .btn-ghost { background: transparent; border: 1px solid rgba(148,163,184,0.2); color: #cbd5e1; }
        .btn-ghost:hover { border-color: rgba(148,163,184,0.4); background: rgba(148,163,184,0.06); }

        /* ── HERO ── */
        .landing-hero { min-height: 100vh; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 120px 24px 60px; position: relative; overflow: hidden; }
        .hero-grid-bg {
          position: absolute; inset: 0; z-index: 0;
          background-image:
            linear-gradient(rgba(148,163,184,0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(148,163,184,0.03) 1px, transparent 1px);
          background-size: 60px 60px;
          mask-image: radial-gradient(ellipse 60% 50% at center, black 30%, transparent 70%);
          -webkit-mask-image: radial-gradient(ellipse 60% 50% at center, black 30%, transparent 70%);
        }
        .hero-glow-g {
          position: absolute; width: 600px; height: 600px; border-radius: 50%; pointer-events: none; z-index: 0;
          background: radial-gradient(circle, rgba(34,211,238,0.1) 0%, transparent 60%);
          top: -200px; left: 10%;
          animation: glowFloat 8s ease-in-out infinite alternate;
        }
        .hero-glow-p {
          position: absolute; width: 500px; height: 500px; border-radius: 50%; pointer-events: none; z-index: 0;
          background: radial-gradient(circle, rgba(167,139,250,0.08) 0%, transparent 60%);
          bottom: -100px; right: 15%;
          animation: glowFloat 10s ease-in-out infinite alternate-reverse;
        }
        @keyframes glowFloat { 0% { transform: translate(0, 0) scale(1); } 100% { transform: translate(30px, -30px) scale(1.08); } }
        .floating-dots { position: absolute; inset: 0; z-index: 0; pointer-events: none; }
        .dot {
          position: absolute; border-radius: 50%;
          background: rgba(34,211,238,0.2);
          animation: dotFloat 4s ease-in-out infinite alternate;
        }
        @keyframes dotFloat { 0% { transform: translateY(0) scale(1); opacity: 0.2; } 100% { transform: translateY(-20px) scale(1.3); opacity: 0.6; } }

        .hero-badge-row { display: flex; gap: 10px; margin-bottom: 28px; position: relative; z-index: 1; flex-wrap: wrap; justify-content: center; }
        .hero-badge { padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 600; background: rgba(34,211,238,0.06); border: 1px solid rgba(34,211,238,0.12); color: #67e8f9; letter-spacing: 0.04em; display: inline-flex; align-items: center; gap: 5px; }

        .hero-title { position: relative; z-index: 1; margin-bottom: 20px; }
        .hero-title-line {
          display: block; font-size: clamp(40px, 8vw, 72px); font-weight: 800; letter-spacing: -3px; line-height: 1.05;
          color: #f1f5f9;
        }
        .hero-title-accent {
          background: linear-gradient(135deg, #22D3EE, #A78BFA, #22D3EE);
          background-size: 200% auto;
          -webkit-background-clip: text; -webkit-text-fill-color: transparent;
          animation: shimmer 4s linear infinite;
        }
        @keyframes shimmer { 0% { background-position: 0% center; } 100% { background-position: 200% center; } }

        .hero-subtitle { font-size: 17px; color: #94a3b8; max-width: 620px; margin-bottom: 36px; line-height: 1.7; position: relative; z-index: 1; }

        .hero-cta { box-shadow: 0 8px 32px rgba(34,211,238,0.25); display: inline-flex; align-items: center; gap: 8px; transition: all 0.25s; }
        .hero-cta:hover { box-shadow: 0 12px 48px rgba(34,211,238,0.4) !important; transform: translateY(-2px); }
        .btn-glass { background: rgba(15,23,42,0.5); backdrop-filter: blur(12px); border: 1px solid rgba(148,163,184,0.12); color: #cbd5e1; transition: all 0.25s; }
        .btn-glass:hover { background: rgba(15,23,42,0.7); border-color: rgba(148,163,184,0.25); transform: translateY(-2px); }

        /* ── STATS ── */
        .stats-bar { display: flex; justify-content: center; gap: 56px; padding: 32px 24px; max-width: 800px; margin: 0 auto; border-top: 1px solid rgba(148,163,184,0.06); border-bottom: 1px solid rgba(148,163,184,0.06); }
        .stats-item { display: flex; flex-direction: column; align-items: center; gap: 4px; }
        .stats-value { font-size: 20px; font-weight: 800; background: linear-gradient(135deg, #22D3EE, #67e8f9); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .stats-label { font-size: 11px; color: #475569; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; }

        /* ── SECTIONS ── */
        .section { padding: 100px 24px; max-width: 1200px; margin: 0 auto; width: 100%; }
        .section-title { font-size: clamp(28px, 4vw, 36px); font-weight: 800; text-align: center; margin-bottom: 12px; background: linear-gradient(135deg, #f1f5f9, #94a3b8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -1px; }
        .section-desc { text-align: center; color: #64748b; font-size: 16px; margin-bottom: 56px; max-width: 560px; margin-left: auto; margin-right: auto; }

        /* ── STEPS ── */
        .steps-wrapper { position: relative; max-width: 960px; margin: 0 auto; }
        .steps-connector { position: absolute; top: 60px; left: 10%; right: 10%; height: 60px; z-index: 0; width: 80%; }
        .steps-grid { display: flex; align-items: flex-start; justify-content: center; gap: 24px; position: relative; z-index: 1; }
        .step-card { background: rgba(15,23,42,0.4); border: 1px solid rgba(148,163,184,0.06); border-radius: 16px; padding: 36px 28px; flex: 1; max-width: 300px; transition: all 0.4s; position: relative; overflow: hidden; }
        .step-card::before { content: ''; position: absolute; inset: 0; border-radius: 16px; padding: 1px; background: linear-gradient(135deg, rgba(34,211,238,0.1), transparent 50%, rgba(167,139,250,0.05)); -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0); -webkit-mask-composite: xor; mask-composite: exclude; pointer-events: none; opacity: 0; transition: opacity 0.4s; }
        .step-card:hover { transform: translateY(-6px) scale(1.02); border-color: rgba(34,211,238,0.15); }
        .step-card:hover::before { opacity: 1; }
        .step-number { font-size: 12px; font-weight: 700; color: rgba(103,232,249,0.3); margin-bottom: 16px; letter-spacing: 0.12em; }
        .step-icon { margin-bottom: 16px; }
        .step-card h3 { font-size: 18px; font-weight: 700; color: #e2e8f0; margin-bottom: 10px; }
        .step-card p { font-size: 13px; color: #64748b; line-height: 1.7; }

        /* ── FEATURES ── */
        .features-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; max-width: 1100px; margin: 0 auto; }
        .feature-card-new {
          background: rgba(15,23,42,0.3);
          border: 1px solid rgba(148,163,184,0.06);
          border-radius: 16px; padding: 32px;
          transition: all 0.4s; position: relative; overflow: hidden;
        }
        .card-glow {
          position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
          background: radial-gradient(circle at 30% 20%, var(--accent, #22D3EE) 0%, transparent 60%);
          opacity: 0; transition: opacity 0.5s; pointer-events: none;
        }
        .feature-card-new:hover { transform: translateY(-6px); border-color: rgba(148,163,184,0.12); background: rgba(15,23,42,0.45); }
        .feature-card-new:hover .card-glow { opacity: 0.04; }
        .fc-icon { margin-bottom: 16px; }
        .feature-card-new h3 { font-size: 17px; font-weight: 700; color: #e2e8f0; margin-bottom: 10px; }
        .feature-card-new p { font-size: 13px; color: #64748b; line-height: 1.7; margin-bottom: 18px; }
        .fc-tags { display: flex; gap: 6px; flex-wrap: wrap; }
        .fc-tags span { padding: 3px 10px; border-radius: 6px; font-size: 11px; font-weight: 600; border: 1px solid; }

        /* ── TECH ── */
        .tech-grid { display: flex; flex-wrap: wrap; justify-content: center; gap: 12px; max-width: 680px; margin: 0 auto; }
        .tech-item {
          background: rgba(15,23,42,0.4);
          border: 1px solid rgba(148,163,184,0.06);
          border-radius: 12px; padding: 16px 24px;
          display: flex; flex-direction: column; align-items: center; gap: 4px;
          min-width: 110px; transition: all 0.3s; position: relative; overflow: hidden;
        }
        .tech-item::before {
          content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
          background: linear-gradient(90deg, transparent, var(--accent, #22D3EE), transparent);
          opacity: 0; transition: opacity 0.3s;
        }
        .tech-item:hover { border-color: rgba(148,163,184,0.15); transform: translateY(-3px); }
        .tech-item:hover::before { opacity: 0.6; }
        .tech-item span:first-child { font-size: 15px; font-weight: 700; color: #e2e8f0; }
        .tech-meta { font-size: 11px; color: #475569; }

        /* ── CTA ── */
        .cta-card {
          background: linear-gradient(135deg, rgba(34,211,238,0.04), rgba(167,139,250,0.04));
          border: 1px solid rgba(34,211,238,0.08);
          border-radius: 20px; padding: 64px 40px; text-align: center;
          max-width: 680px; margin: 0 auto; position: relative; overflow: hidden;
        }
        .cta-glow {
          position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
          background: radial-gradient(circle at 50% 50%, rgba(34,211,238,0.04) 0%, transparent 50%);
          animation: ctaPulse 6s ease-in-out infinite alternate;
          pointer-events: none;
        }
        @keyframes ctaPulse { 0% { transform: scale(1); opacity: 0.5; } 100% { transform: scale(1.1); opacity: 1; } }
        .cta-card h2 { font-size: 28px; font-weight: 800; color: #f1f5f9; margin-bottom: 14px; position: relative; z-index: 1; }
        .cta-card p { font-size: 15px; color: #94a3b8; margin-bottom: 28px; max-width: 460px; margin-left: auto; margin-right: auto; line-height: 1.6; position: relative; z-index: 1; }
        .cta-btn { display: inline-flex; align-items: center; gap: 8px; box-shadow: 0 8px 32px rgba(34,211,238,0.25); position: relative; z-index: 1; }
        .cta-btn:hover { box-shadow: 0 12px 48px rgba(34,211,238,0.4) !important; transform: translateY(-2px); }

        /* ── FOOTER ── */
        .landing-footer { border-top: 1px solid rgba(148,163,184,0.04); padding: 32px 24px; }
        .footer-inner { display: flex; justify-content: center; align-items: center; gap: 24px; max-width: 900px; margin: 0 auto; flex-wrap: wrap; }
        .footer-logo { font-weight: 800; background: linear-gradient(135deg, #22D3EE, #A78BFA); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 14px; display: flex; align-items: center; }
        .footer-text { color: #475569; font-size: 13px; }
        .footer-copy { color: #334155; font-size: 12px; }

        /* ── MODAL ── */
        .glass-card { background: rgba(10,22,40,0.85); backdrop-filter: blur(20px); border: 1px solid rgba(148,163,184,0.08); }
        @keyframes modalIn { from { opacity: 0; transform: scale(0.95) translateY(10px); } to { opacity: 1; transform: scale(1) translateY(0); } }

        @media (max-width: 768px) {
          .landing-nav-links { display: none; }
          .stats-bar { flex-wrap: wrap; gap: 20px; }
          .steps-grid { flex-direction: column; align-items: center; }
          .steps-connector { display: none; }
          .section-title { font-size: 26px; }
        }
      `}</style>
    </div>
  )
}
