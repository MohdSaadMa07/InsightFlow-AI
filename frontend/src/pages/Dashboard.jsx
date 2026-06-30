import { useState, useEffect } from 'react'
import { useOutletContext } from 'react-router-dom'
import { api } from '../api'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid
} from 'recharts'

const COLORS = ['#22D3EE', '#EC4899', '#34D399', '#FBBF24', '#A78BFA', '#F87171', '#F97316']
const FUNNEL_ORDER = ['pageview', 'view_product', 'signup', 'add_to_cart', 'purchase']

export default function Dashboard() {
  const { selected } = useOutletContext()
  const [overview, setOverview] = useState(null)
  const [events, setEvents] = useState([])
  const [retention, setRetention] = useState([])
  const [days, setDays] = useState(7)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [useCustom, setUseCustom] = useState(false)

  useEffect(() => {
    if (!selected) return
    api.dashboard.overview(selected).then(setOverview).catch(() => {})
    if (useCustom && dateFrom && dateTo) {
      api.dashboard.events(selected, days, dateFrom, dateTo).then(setEvents).catch(() => {})
    } else {
      api.dashboard.events(selected, days).then(setEvents).catch(() => {})
    }
    api.dashboard.retention(selected).then(setRetention).catch(() => {})
  }, [selected, days, useCustom, dateFrom, dateTo])

  function setPreset(d) {
    setDays(d)
    setUseCustom(false)
    setDateFrom('')
    setDateTo('')
  }

  function applyCustom() {
    if (!dateFrom || !dateTo) return
    setUseCustom(true)
    const [y1, m1, d1] = dateFrom.split('-').map(Number)
    const [y2, m2, d2] = dateTo.split('-').map(Number)
    const from = new Date(y1, m1 - 1, d1)
    const to = new Date(y2, m2 - 1, d2)
    const diff = Math.round((to - from) / (1000 * 60 * 60 * 24))
    setDays(Math.max(1, diff))
  }

  if (!selected) {
    return <div className="empty-state" style={{ padding: '80px 20px' }}>Select a project from the sidebar</div>
  }

  const dateLabels = [...new Set(events.map(e => e.date))].sort()
  const eventNames = [...new Set(events.map(e => e.event_name))]
    .filter(name => name !== 'exit')
    .sort((a, b) => FUNNEL_ORDER.indexOf(a) - FUNNEL_ORDER.indexOf(b))
  const chartData = dateLabels.map(date => {
    const row = { date: date.substring(5) }
    eventNames.forEach(name => {
      row[name] = events.filter(e => e.event_name === name && e.date === date).reduce((s, e) => s + e.count, 0)
    })
    return row
  })

  const hasOverview = overview?.dau !== undefined

  return (
    <div className="dash">
      <div className="dash-header">
        <div>
          <h2 className="dash-title">Dashboard</h2>
          <p className="dash-subtitle">
            {hasOverview
              ? `Your project had ${overview.total_events?.toLocaleString()} events from ${overview.total_users?.toLocaleString()} users`
              : 'Select a date range to view event trends'}
          </p>
        </div>
      </div>

      <div className="stat-row">
        <div className="stat-card">
          <div className="stat-value">{overview?.dau ?? '-'}</div>
          <div className="stat-label">Daily Active Users</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{overview?.total_users?.toLocaleString() ?? '-'}</div>
          <div className="stat-label">Total Users</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{overview?.total_events?.toLocaleString() ?? '-'}</div>
          <div className="stat-label">Total Events</div>
        </div>
      </div>

      <div className="dash-section">
        <div className="dash-section-header">
          <div>
            <h3>Event Trends</h3>
            <p className="dash-section-desc">Track how your key events perform over time</p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <div className="period-group">
              {[7, 30, 90].map(d => (
                <button key={d} className={`period-btn${days === d && !useCustom ? ' active' : ''}`} onClick={() => setPreset(d)}>{d}d</button>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <label style={{ fontSize: 11, color: '#606088', margin: 0, textTransform: 'none', letterSpacing: 0, whiteSpace: 'nowrap' }}>From</label>
              <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
                style={{ fontSize: 12, padding: '5px 8px', width: 140, borderRadius: 8, border: '1px solid #1E1E3A', background: '#0A0A18', color: '#EAEAFA' }} />
              <label style={{ fontSize: 11, color: '#606088', margin: 0, textTransform: 'none', letterSpacing: 0, whiteSpace: 'nowrap' }}>To</label>
              <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
                style={{ fontSize: 12, padding: '5px 8px', width: 140, borderRadius: 8, border: '1px solid #1E1E3A', background: '#0A0A18', color: '#EAEAFA' }} />
              <button className="btn btn-sm btn-gray" onClick={applyCustom} disabled={!dateFrom || !dateTo}>Apply</button>
            </div>
          </div>
        </div>
        <div className="card">
          {chartData.length === 0 ? (
            <div className="empty-state">No event data for this period</div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E1E3A" />
                <XAxis dataKey="date" tick={{ fill: '#606088', fontSize: 11 }} axisLine={{ stroke: '#1E1E3A' }} />
                <YAxis tick={{ fill: '#606088', fontSize: 11 }} axisLine={{ stroke: '#1E1E3A' }} />
                <Tooltip
                  contentStyle={{ background: '#0D0D1A', border: '1px solid #1E1E3A', borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: '#C0C0D8' }}
                />
                <Legend wrapperStyle={{ fontSize: 11, color: '#606088' }} />
                {eventNames.map((name, i) => (
                  <Bar key={name} dataKey={name} fill={COLORS[i % COLORS.length]} radius={[3, 3, 0, 0]} maxBarSize={32} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="dash-section">
          <div className="dash-section-header">
            <div>
              <h3>Retention</h3>
              <p className="dash-section-desc">How often users return after their first visit</p>
            </div>
          </div>
          <div className="card">
            {retention.length === 0 ? (
              <div className="empty-state">No retention data yet</div>
            ) : (
              <div className="retention-grid">
                {['D1', 'D7', 'D30'].map(p => {
                  const items = retention.filter(r => r.period === p)
                  if (items.length === 0) return null
                  const avg = (items.reduce((s, r) => s + r.rate, 0) / items.length * 100).toFixed(1)
                  const label = p === 'D1' ? '1 Day' : p === 'D7' ? '7 Days' : '30 Days'
                  return (
                    <div key={p} className="retention-tile">
                      <div className="retention-ring">
                        <svg width="80" height="80" viewBox="0 0 80 80">
                          <circle cx="40" cy="40" r="34" fill="none" stroke="#1E1E3A" strokeWidth="6" />
                          <circle cx="40" cy="40" r="34" fill="none" stroke="#34D399" strokeWidth="6"
                            strokeDasharray={`${(parseFloat(avg) / 100) * 213.6} 213.6`}
                            strokeLinecap="round" transform="rotate(-90 40 40)" />
                        </svg>
                        <span className="retention-ring-value">{avg}%</span>
                      </div>
                      <div className="retention-tile-label">{label}</div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
    </div>
  )
}
