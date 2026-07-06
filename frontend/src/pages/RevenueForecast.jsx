import { useState, useEffect } from 'react'
import { useOutletContext } from 'react-router-dom'
import { BASE } from '../api'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Area, AreaChart, ComposedChart, Legend, ReferenceLine, Label } from 'recharts'

const FORECAST_COLOR = '#6366f1'
const REVENUE_COLOR = '#22c55e'
const MRR_COLOR = '#06b6d4'
const BOUND_COLOR = '#c7d2fe'

export default function RevenueForecast() {
  const { selected } = useOutletContext()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [view, setView] = useState('revenue')

  useEffect(() => {
    if (!selected) return
    setLoading(true)
    Promise.all([
      fetch(`${BASE}/api/v1/dashboard/revenue/data/?project_id=${selected}&days=180`).then(r => r.ok ? r.json() : null),
      fetch(`${BASE}/api/v1/dashboard/revenue/forecast/?project_id=${selected}&horizon=30`).then(r => r.ok ? r.json() : null),
    ])
      .then(([hist, forecast]) => {
        setData({ hist, forecast })
        setLoading(false)
      })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [selected])

  if (!selected) return <div className="empty-state" style={{ padding: '80px 20px' }}>Select a project from the sidebar</div>
  if (loading) return <div className="empty-state" style={{ padding: '80px 20px' }}>Loading revenue data...</div>
  if (error) return <div className="empty-state" style={{ padding: '80px 20px', color: '#dc2626' }}>Error: {error}</div>
  if (!data || !data.hist) return <div className="empty-state" style={{ padding: '80px 20px' }}>Connect your project to start collecting events — revenue forecasts will appear once enough data is available</div>

  const metrics = data.hist.metrics || []
  const forecast = data.forecast
  const forecasts = forecast?.forecasts || []
  const mrrForecasts = forecast?.mrr_forecasts || []
  const historical = forecast?.historical || []
  const featureImportance = forecast?.feature_importance || {}
  const featureImportanceSource = forecast?.feature_importance_source || 'correlation_fallback'
  const modelMetadata = forecast?.model_metadata || {}

  function normalizeFeatureImportance(importance) {
    if (!importance || typeof importance !== 'object') return []

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

    const prettify = (name) => niceNameMap[name] || name.replace(/_/g, ' ').replace(/\b\w/g, ch => ch.toUpperCase())

    const flattenGroup = (groupName, groupValue) => {
      if (!groupValue || typeof groupValue !== 'object') return []
      return Object.entries(groupValue)
        .filter(([, value]) => typeof value === 'number')
        .map(([key, value]) => ({ key: `${groupName}: ${prettify(key)}`, value }))
    }

    if (importance.encoder_variables || importance.decoder_variables || importance.static_variables) {
      return [
        ...flattenGroup('Encoder', importance.encoder_variables),
        ...flattenGroup('Decoder', importance.decoder_variables),
        ...flattenGroup('Static', importance.static_variables),
      ]
    }

    return Object.entries(importance)
      .filter(([, value]) => typeof value === 'number')
      .map(([key, value]) => ({ key: prettify(key), value }))
      .sort((a, b) => b.value - a.value)
  }

  function formatTrend(current, previous) {
    if (!previous || !current || previous <= 0) return null
    const change = ((current - previous) / previous) * 100
    const sign = change >= 0 ? '↑' : '↓'
    return { change: Math.abs(change).toFixed(0), sign, positive: change >= 0 }
  }

  const featureImportanceEntries = normalizeFeatureImportance(featureImportance)

  // Build chart data: historical + forecast
  const chartData = []
  const historicalSlice = historical.slice(-90)
  for (const h of historicalSlice) {
    chartData.push({
      date: h.date?.slice(5, 10) || h.date,
      actual: h.total_revenue,
      actualMrr: h.mrr,
    })
  }
  // Mark last historical point
  let forecastStartDate = null
  if (chartData.length > 0) {
    chartData[chartData.length - 1].isLast = true
    forecastStartDate = chartData[chartData.length - 1].date
  }
  for (const f of forecasts) {
    chartData.push({
      date: f.forecast_date?.slice(5, 10) || f.forecast_date,
      forecast: f.predicted_revenue,
      lower: f.lower_bound,
      upper: f.upper_bound,
      isForecast: true,
    })
  }

  // Stat cards
  const latestMetric = metrics[metrics.length - 1] || {}
  const prevMetric = metrics[metrics.length - 2] || {}
  const revenueChange = prevMetric.total_revenue
    ? ((latestMetric.total_revenue - prevMetric.total_revenue) / prevMetric.total_revenue * 100).toFixed(1)
    : 0

  const next30dRevenue = forecasts.reduce((s, f) => s + f.predicted_revenue, 0)
  const forecastMrr = mrrForecasts[mrrForecasts.length - 1]?.predicted_mrr ?? latestMetric.mrr ?? 0

  const statCards = [
    { label: 'Last 30d Revenue', value: `$${(metrics.slice(-30).reduce((s, r) => s + r.total_revenue, 0)).toFixed(0)}`, cls: '' },
    { label: 'Next 30d Forecast', value: `$${next30dRevenue.toFixed(0)}`, cls: 'primary' },
    { label: 'Current MRR', value: `$${latestMetric.mrr?.toFixed(0) || '0'}`, cls: '' },
    { label: 'Forecast MRR (month-end)', value: `$${forecastMrr.toFixed(0)}`, cls: 'info' },
    { label: 'DAU (avg 7d)', value: `${metrics.slice(-7).reduce((s, r) => s + (r.dau || 0), 0) / 7 | 0}`, cls: '' },
    { label: 'Transactions (30d)', value: `${metrics.slice(-30).reduce((s, r) => s + (r.transaction_count || 0), 0)}`, cls: '' },
  ]

  return (
    <div className="dash">
      <div className="dash-header">
        <div>
          <h2 className="dash-title">Revenue Forecast</h2>
          <p className="dash-subtitle">Historical revenue with TFT-based 30-day forecast and uncertainty bounds</p>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="stat-row">
        {statCards.map((card, i) => (
          <div key={i} className={`stat-card${card.cls ? ` stat-${card.cls}` : ''}`}>
            <div className="stat-label">{card.label}</div>
            <div className="stat-value">{card.value}</div>
          </div>
        ))}
      </div>

      {/* View Toggle */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {['revenue', 'mrr', 'volume'].map(v => (
          <button
            key={v}
            className={`btn btn-sm ${view === v ? 'btn-primary' : 'btn-gray'}`}
            onClick={() => setView(v)}
          >
            {v === 'revenue' ? 'Revenue' : v === 'mrr' ? 'MRR' : 'Transaction Volume'}
          </button>
        ))}
      </div>

      {/* Forecast Chart */}
      <div className="card" style={{ padding: 20, marginBottom: 16 }}>
        <ResponsiveContainer width="100%" height={350}>
          <ComposedChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.14)" />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#8ba0bf' }} interval="preserveStartEnd" axisLine={{ stroke: 'rgba(148,163,184,0.16)' }} />
            <YAxis tick={{ fontSize: 11, fill: '#8ba0bf' }} axisLine={{ stroke: 'rgba(148,163,184,0.16)' }} />
            <Tooltip
              contentStyle={{ background: 'rgba(10,18,33,0.96)', border: '1px solid rgba(148,163,184,0.16)', borderRadius: 8, fontSize: 13, color: '#e2e8f0' }}
            />
            <Legend wrapperStyle={{ color: '#8ba0bf' }} />
            {forecastStartDate && (
              <ReferenceLine x={forecastStartDate} stroke="#94a3b8" strokeDasharray="6 4" strokeWidth={1.5}>
                <Label value="Forecast Starts" position="top" offset={10} style={{ fontSize: 11, fill: '#8ba0bf', fontWeight: 600 }} />
              </ReferenceLine>
            )}
            {view === 'revenue' && (
              <>
                <Area type="monotone" dataKey="upper" stroke="none" fill={BOUND_COLOR} fillOpacity={0.3} />
                <Area type="monotone" dataKey="lower" stroke="none" fill="#fff" fillOpacity={0.8} />
                <Line type="monotone" dataKey="actual" stroke={REVENUE_COLOR} strokeWidth={2} dot={false} name="Actual Revenue" />
                <Line type="monotone" dataKey="forecast" stroke={FORECAST_COLOR} strokeWidth={2} strokeDasharray="5 5" dot={false} name="Forecast" />
                <Line type="monotone" dataKey="upper" stroke={BOUND_COLOR} strokeWidth={1} strokeDasharray="3 3" dot={false} name="Uncertainty Bound" />
              </>
            )}
            {view === 'mrr' && (
              <>
                <Line type="monotone" dataKey="actualMrr" stroke={MRR_COLOR} strokeWidth={2} dot={false} name="Actual MRR" />
              </>
            )}
            {view === 'volume' && (
              <Bar dataKey="actual" fill={REVENUE_COLOR} opacity={0.6} name="Daily Revenue" />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Feature Importance */}
      <div className="card" style={{ padding: 20, marginBottom: 16 }}>
        <div className="flex-between" style={{ marginBottom: 12, gap: 12, flexWrap: 'wrap' }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>Feature Importance</h3>
          <span className="badge" style={{ background: 'rgba(34,211,238,0.08)', color: '#67e8f9', fontSize: 10 }}>
            Temporal Fusion Transformer Variable Importance
          </span>
        </div>
        {featureImportanceEntries.length > 0 ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 24 }}>
            {featureImportanceEntries.slice(0, 8).map(({ key, value }) => (
              <div key={key} style={{ minWidth: 140 }}>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>
                  {key}
                </div>
                <div style={{ height: 6, background: 'rgba(148,163,184,0.14)', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ width: `${Math.min(100, value * 100)}%`, height: '100%', background: FORECAST_COLOR, borderRadius: 3 }} />
                </div>
                <div style={{ fontSize: 11, color: '#8ba0bf', marginTop: 2 }}>
                  {(value * 100).toFixed(0)}%
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted" style={{ lineHeight: 1.5, margin: 0 }}>
            No feature attribution was returned for this forecast. The dashboard still shows the model's forecast, but explanation details are unavailable for this project.
          </p>
        )}
      </div>

      {/* Model Metadata */}
      <div className="card" style={{ padding: 20, marginBottom: 16 }}>
        <h3 style={{ marginBottom: 12, fontSize: 15, fontWeight: 600 }}>Forecast Model</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
          <div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Model</div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{modelMetadata.model || 'Temporal Fusion Transformer'}</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Version</div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{modelMetadata.version || forecast?.model_version || 'v1'}</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Prediction Horizon</div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{modelMetadata.prediction_horizon_days || forecast?.horizon || 30} days</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Last Trained</div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{modelMetadata.last_trained ? new Date(modelMetadata.last_trained).toLocaleDateString() : 'Not available'}</div>
          </div>
          <div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 4 }}>Inference</div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{typeof modelMetadata.inference_ms === 'number' ? `${modelMetadata.inference_ms} ms` : '—'}</div>
          </div>
        </div>
      </div>

      {/* Recent Metrics Table */}
      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ marginBottom: 12, fontSize: 15, fontWeight: 600 }}>Recent Daily Metrics</h3>
        <div style={{ overflowX: 'auto' }}>
          <table className="table" style={{ width: '100%', fontSize: 13 }}>
            <thead>
              <tr>
                <th>Date</th>
                <th>Revenue</th>
                <th>MRR</th>
                <th>DAU</th>
                <th>Sessions</th>
                <th>Transactions</th>
                <th>Subscriptions</th>
              </tr>
            </thead>
            <tbody>
              {metrics.slice(-30).reverse().map((r, i, arr) => {
                const previous = arr[i + 1] || null
                const revenueTrend = formatTrend(r.total_revenue, previous?.total_revenue)
                const mrrTrend = formatTrend(r.mrr, previous?.mrr)

                return (
                  <tr key={i}>
                    <td>{r.date}</td>
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <span>${r.total_revenue?.toFixed(0) || '0'}</span>
                        {revenueTrend && (
                          <span style={{ fontSize: 11, color: revenueTrend.positive ? '#22c55e' : '#f97316' }}>
                            {revenueTrend.sign}{revenueTrend.change}% vs prior day
                          </span>
                        )}
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <span>${r.mrr?.toFixed(0) || '0'}</span>
                        {mrrTrend && (
                          <span style={{ fontSize: 11, color: mrrTrend.positive ? '#22c55e' : '#f97316' }}>
                            {mrrTrend.sign}{mrrTrend.change}% vs prior day
                          </span>
                        )}
                      </div>
                    </td>
                    <td>{r.dau || 0}</td>
                    <td>{r.session_count || 0}</td>
                    <td>{r.transaction_count || 0}</td>
                    <td>{r.subscription_count || 0}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      <style>{`
        .stat-primary .stat-value { color: #a5b4fc; }
        .stat-info .stat-value { color: #67e8f9; }
      `}</style>
    </div>
  )
}
