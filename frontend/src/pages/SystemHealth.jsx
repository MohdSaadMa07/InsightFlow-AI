import { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { api } from '../api'

export default function SystemHealth() {
  const { selected } = useOutletContext()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!selected) return
    setLoading(true)
    api.dashboard.anomalies(selected, 14)
      .then(setData)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [selected])

  if (!selected) return <div className="empty-state" style={{ padding: '80px 20px' }}>Select a project from the sidebar</div>
  if (loading) return <div className="empty-state" style={{ padding: '80px 20px' }}>Loading system health...</div>
  if (error) return <div className="empty-state" style={{ padding: '80px 20px', color: '#dc2626' }}>Error: {error}</div>

  return (
    <div className="dash">
      <div className="dash-header">
        <div>
          <h2 className="dash-title">System Health</h2>
          <p className="dash-subtitle">Project-level anomaly monitoring across recent behavior windows</p>
        </div>
      </div>

      <div className="stat-row" style={{ marginBottom: 16 }}>
        <div className="stat-card stat-primary">
          <div className="stat-value">{data?.anomaly_count ?? 0}</div>
          <div className="stat-label">Anomalies</div>
        </div>
        <div className="stat-card stat-info">
          <div className="stat-value">{((data?.anomaly_rate ?? 0) * 100).toFixed(1)}%</div>
          <div className="stat-label">Anomaly Rate</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{data?.total_scored ?? 0}</div>
          <div className="stat-label">Windows Scored</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{data?.threshold?.toFixed?.(3) ?? '-'}</div>
          <div className="stat-label">Threshold</div>
        </div>
      </div>

      <div className="card" style={{ padding: 20, marginBottom: 16 }}>
        <h3 style={{ marginBottom: 12, fontSize: 15, fontWeight: 600 }}>Top Affected Features</h3>
        <div style={{ display: 'grid', gap: 10 }}>
          {(data?.top_features || []).length > 0 ? data.top_features.map(feature => (
            <div key={feature.feature} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '10px 12px', borderRadius: 12, background: 'rgba(15,23,42,0.45)', border: '1px solid rgba(148,163,184,0.12)' }}>
              <div>
                <div className="bold" style={{ fontSize: 13, color: '#f8fbff' }}>{feature.label}</div>
                <div className="text-xs text-muted">{feature.feature}</div>
              </div>
              <div className="bold" style={{ color: '#67e8f9' }}>{feature.score?.toFixed?.(2) ?? feature.score}</div>
            </div>
          )) : <div className="text-sm text-muted">No feature signal available yet.</div>}
        </div>
      </div>

      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ marginBottom: 12, fontSize: 15, fontWeight: 600 }}>Anomaly Trend</h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {(data?.daily_anomalies || []).length > 0 ? data.daily_anomalies.map(point => (
            <span key={point.date} className="badge" style={{ background: 'rgba(99,102,241,0.12)', color: '#a5b4fc' }}>
              {point.date}: {point.count}
            </span>
          )) : <div className="text-sm text-muted">No anomaly trend available yet.</div>}
        </div>
      </div>
    </div>
  )
}