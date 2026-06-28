import { useState } from 'react'
import { api } from '../api'

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
      <nav className="landing-nav">
        <h1>InsightFlow</h1>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <button onClick={() => setAuthMode('login')} className="btn-text">Sign In</button>
          <button onClick={() => setAuthMode('signup')} className="btn btn-primary bg-gradient">Get Started</button>
        </div>
      </nav>

      <main className="landing-hero">
        <div className="glow-orb"></div>
        <h2 className="hero-title">Product Analytics,<br/>Built for Growth.</h2>
        <p className="hero-subtitle">
          Turn raw events into actionable insights. Map funnels, track conversions, and understand your user journey.
        </p>
        <div className="landing-actions">
          <button onClick={() => setAuthMode('signup')} className="btn btn-primary bg-gradient btn-lg">Start Building Free</button>
          <a href="#features" className="btn btn-gray btn-lg glass-btn">Explore Features</a>
        </div>
      </main>

      <section id="features" className="features-grid">
        <div className="feature-card">
          <div className="feature-icon">⚡</div>
          <h3>Real-time SDK</h3>
          <p>Drop in a lightweight script to start capturing behavior, funnels, and revenue events seamlessly.</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">📊</div>
          <h3>Conversion Funnels</h3>
          <p>Build and analyze multi-step funnels from semantic event categories. Identify where users drop off.</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">🔗</div>
          <h3>Semantic Mapping</h3>
          <p>Map raw events to meaningful categories. Your entire analytics model stays consistent as your product grows.</p>
        </div>
      </section>

      {authMode && (
        <div className="modal-overlay">
          <div className="modal-content auth-modal">
            <button className="modal-close" onClick={() => { setAuthMode(null); setError(''); setForm({ username: '', email: '', password: '', organization_name: '' }) }}>×</button>
            <h2 style={{ fontSize: 24, color: '#fff', marginBottom: 8, textAlign: 'center' }}>
              {authMode === 'login' ? 'Welcome Back' : 'Create an Account'}
            </h2>
            <p className="text-muted" style={{ textAlign: 'center', marginBottom: 24 }}>
              {authMode === 'login' ? 'Sign in to access your dashboard.' : 'Start turning your data into insights.'}
            </p>
            {error && <div className="alert alert-error">{error}</div>}
            
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
            
            <p className="text-sm text-muted" style={{ marginTop: 24, textAlign: 'center' }}>
              {authMode === 'login' ? (
                <>Don't have an account? <span className="text-accent cursor-pointer" onClick={() => { setAuthMode('signup'); setError('') }}>Sign up</span></>
              ) : (
                <>Already have an account? <span className="text-accent cursor-pointer" onClick={() => { setAuthMode('login'); setError('') }}>Sign in</span></>
              )}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
