import { useState, useEffect, useRef, useCallback } from 'react'
import { useOutletContext } from 'react-router-dom'
import { api } from '../api'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid,
  PieChart, Pie, Cell
} from 'recharts'

const COLORS = ['#22D3EE', '#EC4899', '#34D399', '#FBBF24', '#A78BFA', '#F87171', '#F97316', '#06B6D4']
const PIE_COLORS = ['#22D3EE', '#EC4899', '#34D399', '#FBBF24', '#A78BFA', '#F87171', '#F97316', '#06B6D4', '#8B5CF6', '#14B8A6']
const FUNNEL_ORDER = ['pageview', 'view_product', 'signup', 'add_to_cart', 'purchase']
const POLL_INTERVAL = 10000

function formatDuration(seconds) {
  if (!seconds || seconds === 0) return '0s'
  const mins = Math.floor(seconds / 60)
  const secs = Math.round(seconds % 60)
  if (mins > 0) return `${mins}m ${secs}s`
  return `${secs}s`
}

function getDomainFromUrl(url) {
  try {
    return new URL(url).hostname.replace('www.', '')
  } catch {
    return url
  }
}

function InsightIcon({ type }) {
  const icons = {
    trend: '📈',
    anomaly: '⚠️',
    funnel_bottleneck: '🔻',
    suggestion: '💡',
    behavior: '👤',
  }
  return <span style={{ fontSize: 20 }}>{icons[type] || '📊'}</span>
}

function SeverityDot({ severity }) {
  const colors = { critical: '#F87171', warning: '#FBBF24', info: '#22D3EE' }
  return <span style={{ width: 8, height: 8, borderRadius: '50%', background: colors[severity] || colors.info, display: 'inline-block', flexShrink: 0 }} />
}

export default function Dashboard() {
  const { selected } = useOutletContext()
  const [overview, setOverview] = useState(null)
  const [events, setEvents] = useState([])
  const [retention, setRetention] = useState([])
  const [days, setDays] = useState(7)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [useCustom, setUseCustom] = useState(false)

  const [realtime, setRealtime] = useState(null)
  const [pages, setPages] = useState([])
  const [countries, setCountries] = useState([])
  const [devices, setDevices] = useState(null)
  const [sessions, setSessions] = useState(null)
  const [insights, setInsights] = useState([])
  const [anomalyHealth, setAnomalyHealth] = useState(null)
  const [timeAgo, setTimeAgo] = useState('')

  const pollRef = useRef(null)

  const loadRealtime = useCallback(() => {
    if (!selected) return
    api.dashboard.realtime(selected).then(data => {
      setRealtime(data)
      setTimeAgo(new Date().toLocaleTimeString())
    }).catch(() => {})
  }, [selected])

  useEffect(() => {
    if (!selected) return

    api.dashboard.overview(selected).then(setOverview).catch(() => {})
    if (useCustom && dateFrom && dateTo) {
      api.dashboard.events(selected, days, dateFrom, dateTo).then(setEvents).catch(() => {})
    } else {
      api.dashboard.events(selected, days).then(setEvents).catch(() => {})
    }
    api.dashboard.retention(selected).then(setRetention).catch(() => {})
    api.dashboard.pages(selected, days).then(setPages).catch(() => {})
    api.dashboard.countries(selected).then(setCountries).catch(() => {})
    api.dashboard.devices(selected).then(setDevices).catch(() => {})
    api.dashboard.sessions(selected).then(setSessions).catch(() => {})
    api.dashboard.insights(selected).then(setInsights).catch(() => {})
    api.dashboard.anomalies(selected, 14).then(setAnomalyHealth).catch(() => setAnomalyHealth(null))

    loadRealtime()
    pollRef.current = setInterval(loadRealtime, POLL_INTERVAL)

    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [selected, days, useCustom, dateFrom, dateTo, loadRealtime])

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

      {/* Real-time Live Indicator */}
      <div className="card" style={{ padding: '16px 24px' }}>
        <div className="flex-between">
          <div className="flex" style={{ gap: 12 }}>
            <span style={{
              width: 10, height: 10, borderRadius: '50%',
              background: realtime?.online_users > 0 ? '#10B981' : '#94a3b8',
              display: 'inline-block',
              boxShadow: realtime?.online_users > 0 ? '0 0 12px rgba(52, 211, 153, 0.6)' : 'none',
              animation: realtime?.online_users > 0 ? 'pulse 2s infinite' : 'none',
            }} />
            <div>
              <span className="bold" style={{ fontSize: 18, color: '#f8fbff' }}>
                {realtime?.online_users ?? '-'}
              </span>
              <span className="text-muted" style={{ fontSize: 12, marginLeft: 6 }}>
                visitors online now
              </span>
            </div>
          </div>
          <div className="flex" style={{ gap: 16 }}>
            <div className="text-center">
              <div className="text-sm bold" style={{ color: '#e2e8f0' }}>{realtime?.events_last_5min ?? '-'}</div>
              <div className="text-xs text-muted">Events (5min)</div>
            </div>
            <div className="text-center">
              <div className="text-sm bold" style={{ color: '#e2e8f0' }}>{realtime?.users_last_5min ?? '-'}</div>
              <div className="text-xs text-muted">Users (5min)</div>
            </div>
            <div className="text-xs text-muted" style={{ alignSelf: 'center' }}>
              Updated {timeAgo}
            </div>
          </div>
        </div>
      </div>

      {/* Stat Cards */}
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
        <div className="stat-card">
          <div className="stat-value">{sessions?.total_sessions?.toLocaleString() ?? '-'}</div>
          <div className="stat-label">Total Sessions</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{sessions ? formatDuration(sessions.avg_duration_seconds) : '-'}</div>
          <div className="stat-label">Avg Session Duration</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: (sessions?.bounce_rate ?? 0) > 50 ? '#F87171' : '#34D399' }}>
            {sessions ? `${sessions.bounce_rate}%` : '-'}
          </div>
          <div className="stat-label">Bounce Rate</div>
        </div>
      </div>

      {/* System Health Panel */}
      <div className="dash-section">
        <div className="dash-section-header">
          <div>
            <h3>System Health</h3>
            <p className="dash-section-desc">Behavioral anomaly signals from recent event windows</p>
          </div>
        </div>
        <div className="card" style={{ padding: 20 }}>
          {anomalyHealth ? (
            <>
              <div className="stat-row" style={{ marginBottom: 16 }}>
                <div className="stat-card stat-primary">
                  <div className="stat-value">{anomalyHealth.anomaly_count ?? 0}</div>
                  <div className="stat-label">Anomalies</div>
                </div>
                <div className="stat-card stat-info">
                  <div className="stat-value">{((anomalyHealth.anomaly_rate ?? 0) * 100).toFixed(1)}%</div>
                  <div className="stat-label">Anomaly Rate</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{anomalyHealth.total_scored ?? 0}</div>
                  <div className="stat-label">Windows Scored</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{anomalyHealth.threshold?.toFixed?.(3) ?? '-'}</div>
                  <div className="stat-label">Threshold</div>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1.25fr 0.95fr', gap: 16 }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    Top Affected Features
                  </div>
                  <div style={{ display: 'grid', gap: 10 }}>
                    {(anomalyHealth.top_features || []).length > 0 ? anomalyHealth.top_features.map(feature => (
                      <div key={feature.feature} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '10px 12px', borderRadius: 12, background: 'rgba(15,23,42,0.45)', border: '1px solid rgba(148,163,184,0.12)' }}>
                        <div>
                          <div className="bold" style={{ fontSize: 13, color: '#f8fbff' }}>{feature.label}</div>
                          <div className="text-xs text-muted">{feature.feature}</div>
                        </div>
                        <div className="bold" style={{ color: '#67e8f9', fontSize: 13 }}>{feature.score?.toFixed?.(2) ?? feature.score}</div>
                      </div>
                    )) : (
                      <div className="text-sm text-muted">No feature signal available yet.</div>
                    )}
                  </div>
                </div>

              </div>

              {(anomalyHealth.daily_anomalies || []).length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    Anomaly Trend
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {anomalyHealth.daily_anomalies.map(point => (
                      <span key={point.date} className="badge" style={{ background: 'rgba(99,102,241,0.12)', color: '#a5b4fc' }}>
                        {point.date}: {point.count}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="text-sm text-muted">No anomaly summary available yet.</div>
          )}
        </div>
      </div>

      {/* Insights Panel */}
      {insights.length > 0 && (
        <div className="dash-section">
          <div className="dash-section-header">
            <div>
              <h3>Insights</h3>
              <p className="dash-section-desc">Automated observations about your data</p>
            </div>
          </div>
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {insights.map((insight, i) => (
                <div key={i} style={{
                  display: 'flex', gap: 14, padding: '16px 20px',
                  borderBottom: i < insights.length - 1 ? '1px solid #e2e8f0' : 'none',
                  alignItems: 'flex-start',
                }}>
                  <InsightIcon type={insight.type} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="flex" style={{ gap: 8, marginBottom: 2 }}>
                      <SeverityDot severity={insight.severity} />
                      <span className="bold" style={{ fontSize: 13, color: '#f8fbff' }}>{insight.title}</span>
                      <span style={{
                        fontSize: 10, padding: '1px 8px', borderRadius: 4,
                        background: insight.type === 'anomaly' ? 'rgba(248, 113, 113, 0.1)' :
                          insight.type === 'suggestion' ? 'rgba(251, 191, 36, 0.1)' :
                          'rgba(34, 211, 238, 0.1)',
                        color: insight.type === 'anomaly' ? '#F87171' :
                          insight.type === 'suggestion' ? '#FBBF24' : '#22D3EE',
                        fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em',
                      }}>{insight.type.replace('_', ' ')}</span>
                    </div>
                    <p className="text-sm text-muted" style={{ lineHeight: 1.5 }}>{insight.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Event Trends */}
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
              <label style={{ fontSize: 11, color: 'var(--muted)', margin: 0, textTransform: 'none', letterSpacing: 0, whiteSpace: 'nowrap' }}>From</label>
              <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
                style={{ fontSize: 12, padding: '5px 8px', width: 140, borderRadius: 8, border: '1px solid rgba(148,163,184,0.16)', background: 'rgba(15,23,42,0.72)', color: '#e2e8f0' }} />
              <label style={{ fontSize: 11, color: 'var(--muted)', margin: 0, textTransform: 'none', letterSpacing: 0, whiteSpace: 'nowrap' }}>To</label>
              <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
                style={{ fontSize: 12, padding: '5px 8px', width: 140, borderRadius: 8, border: '1px solid rgba(148,163,184,0.16)', background: 'rgba(15,23,42,0.72)', color: '#e2e8f0' }} />
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
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.14)" />
                <XAxis dataKey="date" tick={{ fill: '#8ba0bf', fontSize: 11 }} axisLine={{ stroke: 'rgba(148,163,184,0.16)' }} />
                <YAxis tick={{ fill: '#8ba0bf', fontSize: 11 }} axisLine={{ stroke: 'rgba(148,163,184,0.16)' }} />
                <Tooltip
                  contentStyle={{ background: 'rgba(10,18,33,0.96)', border: '1px solid rgba(148,163,184,0.16)', borderRadius: 8, fontSize: 12, color: '#e2e8f0' }}
                  labelStyle={{ color: '#e2e8f0' }}
                />
                <Legend wrapperStyle={{ fontSize: 11, color: '#8ba0bf' }} />
                {eventNames.map((name, i) => (
                  <Bar key={name} dataKey={name} fill={COLORS[i % COLORS.length]} radius={[3, 3, 0, 0]} maxBarSize={32} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Top Pages + Countries + Devices Grid */}
      <div className="dash-grid-2">
        {/* Top Pages */}
        <div className="dash-section">
          <div className="dash-section-header">
            <div>
              <h3>Top Pages</h3>
              <p className="dash-section-desc">Most visited pages in this period</p>
            </div>
          </div>
          <div className="card" style={{ padding: 0 }}>
            {pages.length === 0 ? (
              <div className="empty-state">No page data yet</div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table>
                  <thead>
                    <tr>
                      <th>Page</th>
                      <th style={{ textAlign: 'right' }}>Views</th>
                      <th style={{ textAlign: 'right' }}>Visitors</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pages.slice(0, 10).map((p, i) => (
                      <tr key={i}>
                        <td style={{ maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          <span className="text-sm">{getDomainFromUrl(p.page)}</span>
                          <span className="text-xs text-muted" style={{ marginLeft: 6 }}>{p.page.replace(/^https?:\/\//, '').substring(0, 40)}</span>
                        </td>
                        <td style={{ textAlign: 'right' }}><span className="bold">{p.views}</span></td>
                        <td style={{ textAlign: 'right' }}><span className="text-muted">{p.unique_visitors}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Countries */}
        <div className="dash-section">
          <div className="dash-section-header">
            <div>
              <h3>Countries</h3>
              <p className="dash-section-desc">User distribution by country</p>
            </div>
          </div>
          <div className="card" style={{ padding: 0 }}>
            {countries.length === 0 ? (
              <div className="empty-state">No country data yet</div>
            ) : (
              <div style={{ padding: 16 }}>
                {countries.slice(0, 8).map((c, i) => {
                  const maxUsers = countries[0]?.users || 1
                  const pct = (c.users / maxUsers) * 100
                  return (
                    <div key={c.country} style={{ marginBottom: 12 }}>
                      <div className="flex-between" style={{ marginBottom: 4 }}>
                        <div className="flex" style={{ gap: 8 }}>
                          <span className="text-xs text-muted" style={{ width: 16 }}>{i + 1}</span>
                          <span className="text-sm">{c.country}</span>
                        </div>
                        <span className="text-sm bold">{c.users.toLocaleString()}</span>
                      </div>
                      <div style={{ height: 4, background: '#e2e8f0', borderRadius: 2, overflow: 'hidden' }}>
                        <div style={{ width: `${pct}%`, height: '100%', background: PIE_COLORS[i % PIE_COLORS.length], borderRadius: 2, transition: 'width 0.4s' }} />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Devices Section */}
      <div className="dash-section">
        <div className="dash-section-header">
          <div>
            <h3>Devices & Browsers</h3>
            <p className="dash-section-desc">Breakdown by device type, browser, and OS</p>
          </div>
        </div>
        <div className="dash-grid-2">
          <div className="card">
            <h3 style={{ fontSize: 13, marginBottom: 16 }}>Device Types</h3>
            {!devices?.device_types?.length ? (
              <div className="empty-state" style={{ padding: '20px' }}>No data</div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={devices.device_types}
                    cx="50%" cy="50%" innerRadius={50} outerRadius={80}
                    dataKey="users" nameKey="name"
                    stroke="none"
                  >
                    {devices.device_types.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 12 }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11, color: '#64748b' }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
          <div className="card">
            <h3 style={{ fontSize: 13, marginBottom: 16 }}>Browsers</h3>
            {!devices?.browsers?.length ? (
              <div className="empty-state" style={{ padding: '20px' }}>No data</div>
            ) : (
              <div>
                {devices.browsers.slice(0, 6).map((b, i) => {
                  const maxUsers = devices.browsers[0]?.users || 1
                  const pct = (b.users / maxUsers) * 100
                  return (
                    <div key={b.name} style={{ marginBottom: 10 }}>
                      <div className="flex-between" style={{ marginBottom: 3 }}>
                        <span className="text-sm">{b.name}</span>
                        <span className="text-sm bold">{b.users.toLocaleString()}</span>
                      </div>
                      <div style={{ height: 4, background: '#e2e8f0', borderRadius: 2, overflow: 'hidden' }}>
                        <div style={{ width: `${pct}%`, height: '100%', background: PIE_COLORS[i % PIE_COLORS.length], borderRadius: 2, transition: 'width 0.4s' }} />
                      </div>
                    </div>
                  )
                })}
                {devices.browsers.length > 6 && (
                  <div className="text-xs text-muted text-center" style={{ marginTop: 8 }}>+{devices.browsers.length - 6} more</div>
                )}
              </div>
            )}
          </div>
        </div>
        <div className="card">
          <h3 style={{ fontSize: 13, marginBottom: 16 }}>Operating Systems</h3>
          {!devices?.os?.length ? (
            <div className="empty-state" style={{ padding: '20px' }}>No data</div>
          ) : (
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              {devices.os.map((o, i) => {
                const maxUsers = devices.os[0]?.users || 1
                const pct = (o.users / maxUsers) * 100
                return (
                  <div key={o.name} style={{ flex: 1, minWidth: 120 }}>
                    <div className="flex-between" style={{ marginBottom: 4 }}>
                      <span className="text-sm">{o.name}</span>
                      <span className="text-xs text-muted">{o.users.toLocaleString()}</span>
                    </div>
                    <div style={{ height: 4, background: '#1E1E3A', borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ width: `${pct}%`, height: '100%', background: PIE_COLORS[i % PIE_COLORS.length], borderRadius: 2, transition: 'width 0.4s' }} />
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Retention */}
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
                        <circle cx="40" cy="40" r="34" fill="none" stroke="#e2e8f0" strokeWidth="6" />
                        <circle cx="40" cy="40" r="34" fill="none" stroke="#10B981" strokeWidth="6"
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

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  )
}
