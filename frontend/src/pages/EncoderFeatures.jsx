import { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'

const niceNameMap = {
  transaction_count: 'Transaction Count',
  subscription_count: 'Subscription Count',
  session_count: 'Session Count',
  dau: 'DAU',
  revenue_lag1: 'Revenue (Previous Day)',
  revenue_lag7: 'Revenue (7 Days Ago)',
  revenue_lag14: 'Revenue (14 Days Ago)',
  revenue_lag28: 'Revenue (28 Days Ago)',
  rolling_mean_7: '7-Day Average Revenue',
  rolling_mean_28: '28-Day Average Revenue',
  rolling_std_7: '7-Day Revenue Volatility',
  rolling_std_28: '28-Day Revenue Volatility',
  is_weekend: 'Weekend Indicator',
  day_of_week: 'Day of Week',
  day_of_month: 'Day of Month',
  month: 'Month',
}

function prettify(name) {
  return niceNameMap[name] || name.replace(/_/g, ' ').replace(/\b\w/g, ch => ch.toUpperCase())
}

export default function EncoderFeatures() {
  const { selected } = useOutletContext()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!selected) return
    setLoading(true)
    Promise.all([
      fetch(`/api/v1/dashboard/revenue/forecast/?project_id=${selected}&horizon=30`).then(r => r.ok ? r.json() : null),
      fetch(`/api/v1/dashboard/revenue/data/?project_id=${selected}&days=180`).then(r => r.ok ? r.json() : null),
    ])
      .then(([forecast, history]) => setData({ forecast, history }))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [selected])

  if (!selected) return <div className="empty-state" style={{ padding: '80px 20px' }}>Select a project from the sidebar</div>
  if (loading) return <div className="empty-state" style={{ padding: '80px 20px' }}>Loading encoder features...</div>
  if (error) return <div className="empty-state" style={{ padding: '80px 20px', color: '#dc2626' }}>Error: {error}</div>

  const forecast = data?.forecast || {}
  const importance = forecast.feature_importance || {}
  const modelMetadata = forecast.model_metadata || {}

  const entries = Object.entries(importance)
    .filter(([, value]) => typeof value === 'number')
    .map(([key, value]) => ({ key: prettify(key), value }))
    .sort((a, b) => b.value - a.value)

  return (
    <div className="dash">
      <div className="dash-header">
        <div>
          <h2 className="dash-title">Encoder Features</h2>
          <p className="dash-subtitle">Model-side feature signals and metadata used by the revenue forecaster</p>
        </div>
      </div>

      <div className="stat-row" style={{ marginBottom: 16 }}>
        <div className="stat-card">
          <div className="stat-value" style={{ fontSize: 20 }}>{modelMetadata.model || 'Temporal Fusion Transformer'}</div>
          <div className="stat-label">Model</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ fontSize: 20 }}>{modelMetadata.version || forecast.model_version || 'v1'}</div>
          <div className="stat-label">Version</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ fontSize: 20 }}>{modelMetadata.prediction_horizon_days || forecast.horizon || 30}</div>
          <div className="stat-label">Horizon (days)</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ fontSize: 20 }}>{typeof modelMetadata.inference_ms === 'number' ? `${modelMetadata.inference_ms} ms` : '—'}</div>
          <div className="stat-label">Inference</div>
        </div>
      </div>

      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ marginBottom: 12, fontSize: 15, fontWeight: 600 }}>Feature Importance</h3>
        {entries.length > 0 ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 24 }}>
            {entries.slice(0, 8).map(({ key, value }) => (
              <div key={key} style={{ minWidth: 140 }}>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>{key}</div>
                <div style={{ height: 6, background: 'rgba(148,163,184,0.14)', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ width: `${Math.min(100, value * 100)}%`, height: '100%', background: '#6366f1', borderRadius: 3 }} />
                </div>
                <div style={{ fontSize: 11, color: '#8ba0bf', marginTop: 2 }}>{(value * 100).toFixed(0)}%</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-muted">No feature importance data is available for this forecast.</div>
        )}
      </div>
    </div>
  )
}