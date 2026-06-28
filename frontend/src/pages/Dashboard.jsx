import { useState, useEffect } from 'react'
import { useOutletContext } from 'react-router-dom'
import { api } from '../api'

export default function Dashboard() {
  const { selected } = useOutletContext()
  const [overview, setOverview] = useState(null)
  const [events, setEvents] = useState([])
  const [funnels, setFunnels] = useState([])
  const [retention, setRetention] = useState([])
  const [days, setDays] = useState(7)

  useEffect(() => {
    if (!selected) return
    api.dashboard.overview(selected).then(setOverview).catch(() => {})
    api.dashboard.events(selected, days).then(setEvents).catch(() => {})
    api.dashboard.funnels(selected).then(setFunnels).catch(() => {})
    api.dashboard.retention(selected).then(setRetention).catch(() => {})
  }, [selected, days])

  if (!selected) {
    return <div className="empty-state" style={{ padding: '80px 20px' }}>Select a project from the sidebar</div>
  }

  const grouped = {}
  events.forEach(e => {
    if (!grouped[e.event_name]) grouped[e.event_name] = []
    grouped[e.event_name].push(e)
  })

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>Dashboard</h2>

      <div className="stat-row">
        <div className="stat-card">
          <div className="stat-value">{overview?.dau ?? 0}</div>
          <div className="stat-label">Daily Active Users</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{overview?.total_users ?? 0}</div>
          <div className="stat-label">Total Users</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{overview?.total_events ?? 0}</div>
          <div className="stat-label">Total Events</div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="flex-between" style={{ marginBottom: 8 }}>
          <h3 style={{ margin: 0 }}>Event Trends</h3>
          <div className="period-group">
            {[7, 30, 90].map(d => (
              <button key={d} className={`period-btn${days === d ? ' active' : ''}`} onClick={() => setDays(d)}>{d}d</button>
            ))}
          </div>
        </div>
        {Object.keys(grouped).length === 0 ? (
          <div className="text-muted text-sm" style={{ padding: 30, textAlign: 'center' }}>No events yet</div>
        ) : (
          Object.entries(grouped).map(([name, vals]) => {
            const sorted = vals.sort((a, b) => a.date.localeCompare(b.date))
            const max = Math.max(...sorted.map(v => v.count), 1)
            return (
              <div key={name} style={{ marginBottom: 16 }}>
                <div className="text-sm bold" style={{ marginBottom: 8 }}>{name}</div>
                <div className="bar-chart">
                  {sorted.map(v => (
                    <div key={v.date} className="bar" style={{ height: `${Math.max(5, (v.count / max) * 100)}%` }} title={`${v.date}: ${v.count}`}>
                      <span className="bar-value">{v.count}</span>
                      <span className="bar-label">{v.date.substring(5)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )
          })
        )}
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3 style={{ marginBottom: 8 }}>Funnels</h3>
        {funnels.length === 0 ? (
          <div className="text-muted text-sm" style={{ padding: 30, textAlign: 'center' }}>No funnel data</div>
        ) : (
          Object.entries(
            funnels.reduce((acc, a) => {
              const key = `${a.funnel}|${a.date}`
              if (!acc[key]) acc[key] = []
              acc[key].push(a)
              return acc
            }, {})
          ).slice(0, 3).map(([key, steps]) => {
            const sorted = steps.sort((a, b) => a.step_order - b.step_order)
            const initial = sorted[0]?.count || 1
            return (
              <div key={key} style={{ marginBottom: 8 }}>
                <div className="pipeline">
                  {sorted.map((s, i) => (
                    <div key={i} className="pipeline-step">
                      <div className="pipeline-count">{s.count}</div>
                      <div className="pipeline-rate">{((s.count / initial) * 100).toFixed(1)}%</div>
                      <div className="pipeline-name">{s.step_name}</div>
                    </div>
                  ))}
                </div>
                <div className="text-xs text-muted" style={{ marginTop: 4 }}>{sorted[0]?.date}</div>
              </div>
            )
          })
        )}
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3 style={{ marginBottom: 8 }}>Retention</h3>
        {retention.length === 0 ? (
          <div className="text-muted text-sm" style={{ padding: 30, textAlign: 'center' }}>No retention data</div>
        ) : (
          <div className="retention-row">
            {['D1', 'D7', 'D30'].map(p => {
              const items = retention.filter(r => r.period === p)
              if (items.length === 0) return null
              const avg = (items.reduce((s, r) => s + r.rate, 0) / items.length * 100).toFixed(1)
              return (
                <div key={p} className="retention-card">
                  <div className="retention-value">{avg}%</div>
                  <div className="retention-label">{p} Retention</div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
