import { Link } from 'react-router-dom'

export default function Landing() {
  return (
    <div className="landing">
      <nav className="landing-nav">
        <h1>InsightFlow</h1>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <Link to="/login" className="text-muted" style={{ fontWeight: 500 }}>Sign In</Link>
          <Link to="/signup" className="btn btn-blue bg-gradient-blue">Get Started</Link>
        </div>
      </nav>

      <main className="landing-hero">
        <h2>Product Analytics, Supercharged with AI</h2>
        <p>
          Understand why users drop off, predict churn, and get AI-generated business explanations. 
          The power of Mixpanel, Amplitude, and an AI analyst in one platform.
        </p>
        <div className="landing-actions">
          <Link to="/signup" className="btn btn-blue bg-gradient-blue" style={{ fontSize: '16px', padding: '14px 28px' }}>
            Start Building Free
          </Link>
          <a href="#features" className="btn btn-gray" style={{ fontSize: '16px', padding: '14px 28px', background: 'rgba(255,255,255,0.1)' }}>
            View Features
          </a>
        </div>
      </main>

      <section id="features" className="landing-features">
        <div className="feature-card">
          <div style={{ fontSize: '24px', marginBottom: '16px' }}>⚡</div>
          <h3>Event Tracking SDK</h3>
          <p>Easily integrate our lightweight SDK to capture signups, clicks, and custom user events in real-time.</p>
        </div>
        <div className="feature-card">
          <div style={{ fontSize: '24px', marginBottom: '16px' }}>🧠</div>
          <h3>AI Analyst</h3>
          <p>Ask questions in plain English and let the AI instantly explain drops in retention or revenue anomalies.</p>
        </div>
        <div className="feature-card">
          <div style={{ fontSize: '24px', marginBottom: '16px' }}>🔮</div>
          <h3>Predictive ML</h3>
          <p>Spot at-risk users before they churn with our built-in deep learning classification and time-series forecasting.</p>
        </div>
      </section>
    </div>
  )
}
