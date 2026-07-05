import { useState, useEffect, useCallback } from 'react'
import { useOutletContext } from 'react-router-dom'
import { api } from '../api'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, LineChart, Line, ReferenceLine,
} from 'recharts'

// ── Constants ──────────────────────────────────────────────────────────────────
const SEV_CONFIG = {
  normal:   { icon: '🟢', label: 'Normal',   color: '#10B981', bg: 'rgba(16,185,129,0.12)',  border: 'rgba(16,185,129,0.3)'  },
  low:      { icon: '🟡', label: 'Low',      color: '#FBBF24', bg: 'rgba(251,191,36,0.12)',  border: 'rgba(251,191,36,0.3)'  },
  medium:   { icon: '🟡', label: 'Medium',   color: '#F97316', bg: 'rgba(249,115,22,0.12)',  border: 'rgba(249,115,22,0.3)'  },
  high:     { icon: '🔴', label: 'High',     color: '#EF4444', bg: 'rgba(239,68,68,0.12)',   border: 'rgba(239,68,68,0.3)'   },
  critical: { icon: '⚫', label: 'Critical', color: '#94a3b8', bg: 'rgba(148,163,184,0.12)', border: 'rgba(148,163,184,0.3)' },
}

const STATUS_ICON = { open: '🔴', investigating: '🟡', resolved: '🟢' }

function SeverityBadge({ severity }) {
  const cfg = SEV_CONFIG[severity] || SEV_CONFIG.low
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '2px 10px', borderRadius: 20, fontSize: 11, fontWeight: 700,
      background: cfg.bg, border: `1px solid ${cfg.border}`, color: cfg.color,
      textTransform: 'uppercase', letterSpacing: '0.06em',
    }}>
      {cfg.icon} {cfg.label}
    </span>
  )
}

// ── System Status Card ─────────────────────────────────────────────────────────
function SystemStatusCard({ status }) {
  if (!status) return null
  const isHealthy = status.status === 'healthy'
  const color = isHealthy ? '#10B981' : '#EF4444'
  const border = isHealthy ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.25)'
  const bg = isHealthy ? 'rgba(16,185,129,0.07)' : 'rgba(239,68,68,0.07)'
  return (
    <div style={{
      borderRadius: 16, padding: '18px 24px', border: `1px solid ${border}`,
      background: bg, display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24,
    }}>
      <span style={{ fontSize: 36 }}>{isHealthy ? '🟢' : '🔴'}</span>
      <div>
        <div style={{ fontSize: 16, fontWeight: 700, color, marginBottom: 3 }}>{status.label}</div>
        <div style={{ fontSize: 13, color: '#94a3b8' }}>{status.message}</div>
      </div>
    </div>
  )
}

// ── Reconstruction Error Panel ─────────────────────────────────────────────────
function ReconErrorPanel({ score, threshold, ratio }) {
  const isAbove = score >= threshold
  const color = isAbove ? '#EF4444' : '#10B981'
  return (
    <div className="card" style={{ padding: 20 }}>
      <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>
        Reconstruction Error
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12 }}>
        {[
          { label: 'Anomaly Score', value: score?.toFixed(4) ?? '—' },
          { label: 'Threshold', value: threshold?.toFixed(4) ?? '—' },
          { label: 'Ratio', value: ratio?.toFixed(3) ?? '—' },
        ].map(({ label, value }) => (
          <div key={label} style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: '#f8fbff', marginBottom: 4 }}>{value}</div>
            <div style={{ fontSize: 11, color: 'var(--muted)' }}>{label}</div>
          </div>
        ))}
      </div>
      <div style={{
        marginTop: 14, padding: '6px 12px', borderRadius: 8, textAlign: 'center',
        background: isAbove ? 'rgba(239,68,68,0.1)' : 'rgba(16,185,129,0.1)',
        color, fontSize: 12, fontWeight: 600,
      }}>
        {isAbove ? '⬆ Above Threshold — Anomaly Detected' : '✓ Below Threshold — Normal'}
      </div>
    </div>
  )
}

// ── Timeline Chart ─────────────────────────────────────────────────────────────
function TimelineChart({ timeline }) {
  if (!timeline || timeline.length === 0)
    return <div className="empty-state">No timeline data</div>

  const data = timeline.map(d => ({
    date: d.date?.substring(5) ?? d.date,
    score: +(d.max_score ?? 0).toFixed(4),
    anomalies: d.anomaly_count ?? 0,
    severity: d.severity ?? 'normal',
  }))

  const CustomBar = (props) => {
    const { x, y, width, height, payload } = props
    const sev = payload?.severity ?? 'normal'
    const color = SEV_CONFIG[sev]?.color ?? '#6366f1'
    return <rect x={x} y={y} width={width} height={height} fill={color} rx={3} ry={3} fillOpacity={0.85} />
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.12)" />
        <XAxis dataKey="date" tick={{ fill: '#8ba0bf', fontSize: 10 }} axisLine={{ stroke: 'rgba(148,163,184,0.16)' }} />
        <YAxis tick={{ fill: '#8ba0bf', fontSize: 10 }} axisLine={{ stroke: 'rgba(148,163,184,0.16)' }} allowDecimals={false} />
        <Tooltip
          contentStyle={{ background: 'rgba(10,18,33,0.96)', border: '1px solid rgba(148,163,184,0.16)', borderRadius: 8, fontSize: 12 }}
          labelStyle={{ color: '#e2e8f0' }}
          formatter={(v, n) => [v, n === 'score' ? 'Anomaly Score' : 'Anomaly Days']}
        />
        <Bar dataKey="anomalies" shape={<CustomBar />} maxBarSize={28} />
      </BarChart>
    </ResponsiveContainer>
  )
}

// ── Expected vs Actual Table ────────────────────────────────────────────────────
function ExpectedVsActualTable({ rows }) {
  if (!rows || rows.length === 0)
    return <div className="empty-state" style={{ padding: 16 }}>No comparison data</div>
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', fontSize: 12 }}>
        <thead>
          <tr>
            <th>Metric</th>
            <th style={{ textAlign: 'right' }}>Expected</th>
            <th style={{ textAlign: 'right' }}>Actual</th>
            <th style={{ textAlign: 'right' }}>Δ</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const up = r.direction === '↑'
            const color = up ? '#34D399' : '#F87171'
            return (
              <tr key={i}>
                <td style={{ fontWeight: 600 }}>{r.label}</td>
                <td style={{ textAlign: 'right', color: '#94a3b8' }}>{r.expected?.toLocaleString()}</td>
                <td style={{ textAlign: 'right', color: '#f8fbff' }}>{r.actual?.toLocaleString()}</td>
                <td style={{ textAlign: 'right', color, fontWeight: 700 }}>{r.direction} {r.delta_pct}%</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── Feature Contributions ──────────────────────────────────────────────────────
function ContributionsBar({ contributions }) {
  if (!contributions || contributions.length === 0)
    return <div className="empty-state" style={{ padding: 16 }}>No data</div>
  const colors = ['#818cf8', '#38bdf8', '#34d399', '#fbbf24', '#f87171', '#a78bfa', '#f97316', '#22d3ee']
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {contributions.map((item, i) => (
        <div key={item.feature}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
            <span style={{ fontSize: 12, color: '#e2e8f0' }}>{item.label}</span>
            <span style={{ fontSize: 12, fontWeight: 700, color: colors[i % colors.length] }}>{item.contribution_pct}%</span>
          </div>
          <div style={{ height: 5, background: 'rgba(148,163,184,0.12)', borderRadius: 3, overflow: 'hidden' }}>
            <div style={{
              height: '100%', width: `${item.contribution_pct}%`,
              background: colors[i % colors.length], borderRadius: 3,
              transition: 'width 0.6s ease',
            }} />
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Recommendations Panel ──────────────────────────────────────────────────────
function RecommendationsPanel({ recommendations }) {
  if (!recommendations || recommendations.length === 0)
    return <div className="text-sm text-muted">No recommendations generated.</div>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {recommendations.map((rec, i) => (
        <div key={i} style={{ padding: 14, borderRadius: 12, background: 'rgba(99,102,241,0.07)', border: '1px solid rgba(99,102,241,0.18)' }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#a5b4fc', marginBottom: 8 }}>{rec.title}</div>
          {rec.description && (
            <div style={{ fontSize: 12, color: '#cbd5e1', marginBottom: 8 }}>{rec.description}</div>
          )}
          {(rec.suggestions && rec.suggestions.length > 0) && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0', marginBottom: 4 }}>Root Causes:</div>
              {rec.suggestions.map((cause, ci) => (
                <div key={ci} style={{ fontSize: 12, color: '#94a3b8', display: 'flex', gap: 8, alignItems: 'flex-start', marginBottom: 4 }}>
                  <span style={{ color: '#6366f1', marginTop: 2 }}>•</span>
                  <span>{cause}</span>
                </div>
              ))}
            </div>
          )}
          {(rec.fixes && rec.fixes.length > 0) && (
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0', marginBottom: 4 }}>Immediate Fixes:</div>
              <ul style={{ margin: 0, paddingLeft: 20, fontSize: 12, color: '#cbd5e1' }}>
                {rec.fixes.map((fix, fi) => (
                  <li key={fi} style={{ marginBottom: 2 }}>{fix}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Incident Log Table ─────────────────────────────────────────────────────────
function IncidentLog({ incidents }) {
  if (!incidents || incidents.length === 0)
    return <div className="empty-state">No incidents recorded yet.</div>
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', fontSize: 12 }}>
        <thead>
          <tr>
            <th>Date</th>
            <th>Severity</th>
            <th>Status</th>
            <th>Description</th>
            <th style={{ textAlign: 'right' }}>Score</th>
          </tr>
        </thead>
        <tbody>
          {incidents.map((inc) => (
            <tr key={inc.id}>
              <td style={{ whiteSpace: 'nowrap' }}>{inc.date}</td>
              <td><SeverityBadge severity={inc.severity} /></td>
              <td>
                <span style={{ fontSize: 12 }}>{STATUS_ICON[inc.status] ?? '⬜'} {inc.status}</span>
              </td>
              <td style={{ maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#94a3b8' }}>
                {inc.description}
              </td>
              <td style={{ textAlign: 'right', fontWeight: 700, color: '#67e8f9' }}>
                {inc.score?.toFixed(4)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Anomaly Detail Row (collapsible) ──────────────────────────────────────────
function AnomalyRow({ anomaly, index }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = SEV_CONFIG[anomaly.severity] || SEV_CONFIG.low
  return (
    <div style={{
      borderRadius: 14, border: `1px solid ${cfg.border}`, marginBottom: 10,
      background: 'rgba(10,18,40,0.6)', overflow: 'hidden', transition: 'all 0.2s',
    }}>
      {/* Header row */}
      <div
        onClick={() => setExpanded(v => !v)}
        style={{
          display: 'flex', alignItems: 'center', gap: 16, padding: '14px 18px',
          cursor: 'pointer', userSelect: 'none',
        }}
      >
        <span style={{ fontSize: 13, color: '#94a3b8', minWidth: 90 }}>{anomaly.date}</span>
        <SeverityBadge severity={anomaly.severity} />
        <span style={{ flex: 1, fontSize: 13, color: '#cbd5e1' }}>{anomaly.description}</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: '#67e8f9', whiteSpace: 'nowrap' }}>
          {anomaly.anomaly_score?.toFixed(4)}
        </span>
        <span style={{ color: '#64748b', fontSize: 14, transition: 'transform 0.2s', transform: expanded ? 'rotate(180deg)' : 'none' }}>▾</span>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div style={{ padding: '0 18px 18px', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
              Expected vs Actual
            </div>
            <ExpectedVsActualTable rows={anomaly.expected_vs_actual} />
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
              Root Cause (Feature Contributions)
            </div>
            <ContributionsBar contributions={anomaly.feature_contributions} />
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
              Recommendations
            </div>
            <RecommendationsPanel recommendations={anomaly.recommendations} />
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function AnomalyMonitor() {
  const { selected } = useOutletContext()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [days, setDays] = useState(14)
  const [activeTab, setActiveTab] = useState('anomalies') // anomalies | timeline | incidents

  const load = useCallback(() => {
    if (!selected) return
    setLoading(true)
    setError(null)
    api.dashboard.anomalies(selected, days)
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [selected, days])

  useEffect(() => { load() }, [load])

  if (!selected) {
    return <div className="empty-state" style={{ padding: '80px 20px' }}>Select a project from the sidebar</div>
  }

  const summary = data?.summary ?? {}
  const recentAnomalies = data?.recent_anomalies ?? []
  const timeline = data?.timeline ?? []
  const incidentLog = data?.incident_log ?? []
  const firstAnomaly = recentAnomalies[0] ?? null

  return (
    <div className="dash">
      {/* Header */}
      <div className="dash-header">
        <div>
          <h2 className="dash-title">Anomaly Monitor</h2>
          <p className="dash-subtitle">Dense autoencoder — behavioral anomaly detection</p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <div className="period-group">
            {[7, 14, 30].map(d => (
              <button key={d} className={`period-btn${days === d ? ' active' : ''}`} onClick={() => setDays(d)}>{d}d</button>
            ))}
          </div>
          <button className="btn btn-sm btn-gray" onClick={load} disabled={loading}>
            {loading ? 'Loading…' : '↺ Refresh'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', borderRadius: 10, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', color: '#fca5a5', marginBottom: 16, fontSize: 13 }}>
          ⚠ {error}
        </div>
      )}

      {/* System Status */}
      <SystemStatusCard status={summary.system_status} />

      {/* KPI Row */}
      <div className="stat-row" style={{ marginBottom: 24 }}>
        {[
          { label: 'Anomaly Count',   value: summary.anomaly_count ?? '—' },
          { label: 'Windows Scored',  value: summary.total_scored ?? '—' },
          { label: 'Anomaly Rate',    value: summary.anomaly_rate != null ? `${(summary.anomaly_rate * 100).toFixed(1)}%` : '—' },
          { label: 'Threshold',       value: summary.threshold?.toFixed(4) ?? '—' },
          { label: 'Model',           value: summary.model_version ?? '—' },
          { label: 'Score Source',    value: summary.score_source ?? '—' },
        ].map(({ label, value }) => (
          <div className="stat-card" key={label}>
            <div className="stat-value" style={{ fontSize: 18 }}>{value}</div>
            <div className="stat-label">{label}</div>
          </div>
        ))}
      </div>

      {/* Reconstruction Error Panel (from latest anomaly) */}
      {firstAnomaly && (
        <div style={{ marginBottom: 24 }}>
          <ReconErrorPanel
            score={firstAnomaly.reconstruction_error}
            threshold={firstAnomaly.threshold}
            ratio={firstAnomaly.ratio}
          />
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, borderBottom: '1px solid rgba(148,163,184,0.14)', paddingBottom: 2 }}>
        {[
          { key: 'anomalies', label: `Anomalies (${recentAnomalies.length})` },
          { key: 'timeline',  label: 'Timeline' },
          { key: 'incidents', label: `Incident Log (${incidentLog.length})` },
        ].map(tab => (
          <button key={tab.key} onClick={() => setActiveTab(tab.key)} style={{
            padding: '8px 18px', borderRadius: '8px 8px 0 0', border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
            background: activeTab === tab.key ? 'rgba(99,102,241,0.18)' : 'transparent',
            color: activeTab === tab.key ? '#a5b4fc' : '#64748b',
            borderBottom: activeTab === tab.key ? '2px solid #6366f1' : '2px solid transparent',
            transition: 'all 0.15s',
          }}>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab: Anomalies */}
      {activeTab === 'anomalies' && (
        <div>
          {recentAnomalies.length === 0 ? (
            <div className="card">
              <div className="empty-state">No anomalies detected in the selected window. System is healthy.</div>
            </div>
          ) : (
            recentAnomalies.map((a, i) => <AnomalyRow key={i} anomaly={a} index={i} />)
          )}
        </div>
      )}

      {/* Tab: Timeline */}
      {activeTab === 'timeline' && (
        <div className="card" style={{ padding: 20 }}>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Daily Anomaly Count
          </div>
          <TimelineChart timeline={timeline} />
        </div>
      )}

      {/* Tab: Incident Log */}
      {activeTab === 'incidents' && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <IncidentLog incidents={incidentLog} />
        </div>
      )}

      {/* Top Affected Features summary */}
      {(summary.top_features ?? []).length > 0 && (
        <div className="dash-section" style={{ marginTop: 24 }}>
          <div className="dash-section-header">
            <div>
              <h3>Top Affected Metrics (across all anomalies)</h3>
              <p className="dash-section-desc">Aggregated reconstruction error per feature</p>
            </div>
          </div>
          <div className="card" style={{ padding: 20 }}>
            <ContributionsBar
              contributions={summary.top_features.map(f => ({
                feature: f.feature,
                label: f.label,
                contribution_pct: f.score,
              }))}
            />
          </div>
        </div>
      )}

      <style>{`
        .anomaly-row-enter { opacity: 0; transform: translateY(8px); }
        .anomaly-row-enter-active { opacity: 1; transform: none; transition: all 0.3s; }
      `}</style>
    </div>
  )
}
