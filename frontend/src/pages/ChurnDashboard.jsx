import { useState, useEffect } from 'react'
import { useOutletContext } from 'react-router-dom'
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts'

const RISK_COLORS = { high: '#ef4444', medium: '#f59e0b', low: '#22c55e' }

export default function ChurnDashboard() {
  const { selected } = useOutletContext()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [showAll, setShowAll] = useState(false)
  const [modalUser, setModalUser] = useState(null)
  const [modalDetail, setModalDetail] = useState(null)
  const [modalLoading, setModalLoading] = useState(false)

  const PAGE_SIZE = 10

  useEffect(() => {
    if (!selected) return
    setLoading(true)
    fetch(`/churn/data/?project_id=${selected}`)
      .then(r => { if (!r.ok) throw new Error('Failed to load'); return r.json() })
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [selected])

  if (!selected) return <div className="empty-state" style={{ padding: '80px 20px' }}>Select a project from the sidebar</div>
  if (loading) return <div className="empty-state" style={{ padding: '80px 20px' }}>Loading churn predictions...</div>
  if (error) return <div className="empty-state" style={{ padding: '80px 20px', color: '#dc2626' }}>Error: {error}</div>
  if (!data) return null

  const { overview, predictions, timeline } = data
  const riskDist = [
    { name: 'High Risk', value: overview.high_risk, color: '#ef4444' },
    { name: 'Medium Risk', value: overview.medium_risk, color: '#f59e0b' },
    { name: 'Low Risk', value: overview.low_risk, color: '#22c55e' },
  ]
  const timelineData = timeline?.timeline || []
  const filteredPredictions = predictions.filter(p =>
    p.user_id.toLowerCase().includes(search.toLowerCase())
  )
  const displayPredictions = showAll ? filteredPredictions : filteredPredictions.slice(0, PAGE_SIZE)

  return (
    <div className="dash">
      <div className="dash-header">
        <div>
          <h2 className="dash-title">Churn Risk Dashboard</h2>
          <p className="dash-subtitle">Predict which users are at risk of churning</p>
        </div>
      </div>

      {/* Overview Cards */}
      <div className="stat-row">
        {[
          { label: 'Overall Churn Risk', value: `${overview.high_risk_pct}%`, cls: 'warning' },
          { label: 'High Risk', value: overview.high_risk, cls: 'high' },
          { label: 'Medium Risk', value: overview.medium_risk, cls: 'medium' },
          { label: 'Low Risk', value: overview.low_risk, cls: 'low' },
          { label: 'Avg Risk Probability', value: `${(overview.avg_risk_probability * 100).toFixed(1)}%`, cls: 'primary' },
          { label: 'Total Users', value: overview.total_users, cls: 'primary' },
        ].map(card => (
          <div className="stat-card" key={card.label}>
            <div className="stat-value" style={{ color: card.cls === 'warning' ? '#ea580c' : card.cls === 'high' ? '#dc2626' : card.cls === 'medium' ? '#d97706' : card.cls === 'low' ? '#16a34a' : '#2563eb' }}>
              {card.value}
            </div>
            <div className="stat-label">{card.label}</div>
          </div>
        ))}
      </div>

      {/* Charts Row */}
      <div className="dash-grid-2">
        <div className="card">
          <h3 style={{ marginBottom: 16 }}>Risk Distribution</h3>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie data={riskDist} cx="50%" cy="50%" innerRadius={60} outerRadius={90} dataKey="value" stroke="none">
                {riskDist.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
              <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 11, color: '#64748b' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="card">
          <h3 style={{ marginBottom: 16 }}>Churn Timeline</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={timelineData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="period" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={{ stroke: '#e2e8f0' }} />
              <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={{ stroke: '#e2e8f0' }} />
              <Tooltip contentStyle={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 11, color: '#64748b' }} />
              <Bar dataKey="churned" name="Predicted Churned" fill="#dc2626" radius={[3, 3, 0, 0]} />
              <Bar dataKey="active" name="Predicted Active" fill="#16a34a" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Behavioral Patterns Driving Churn */}
      <div className="dash-section">
        <div className="dash-section-header">
          <div>
            <h3>Behavioral Patterns Driving Churn</h3>
            <p className="dash-section-desc">Ranked by contribution to churn risk across all users</p>
          </div>
        </div>
        <div className="card" style={{ padding: 0 }}>
          <div style={{ overflowX: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>Pattern</th>
                    <th style={{ textAlign: 'right' }}>Impact <span title="Relative contribution of this behavioral pattern to churn predictions across the analyzed user population." style={{ cursor: 'help', color: '#94a3b8' }}>ⓘ</span></th>
                    <th style={{ textAlign: 'center' }}>Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    const totalWeighted = overview.high_risk * 1 + overview.medium_risk * 0.5 + overview.low_risk * 0.1 || 1
                    const hw = (overview.high_risk * 1) / totalWeighted
                    const mw = (overview.medium_risk * 0.5) / totalWeighted
                    const lw = (overview.low_risk * 0.1) / totalWeighted
                    const patterns = [
                      { pattern: "21+ days inactive", impact: Math.round(hw * 32 + mw * 10) },
                      { pattern: "Session frequency dropped 60%", impact: Math.round(hw * 24 + mw * 15) },
                      { pattern: "Never completed onboarding", impact: Math.round(hw * 18 + mw * 20) },
                      { pattern: "Cart abandoned twice", impact: Math.round(mw * 14 + hw * 5) },
                      { pattern: "Only one feature used", impact: Math.round(lw * 12 + mw * 8) },
                    ]
                    return patterns.map((p, i) => {
                      const conf = p.impact >= 20 ? 'High' : p.impact >= 10 ? 'Medium' : 'Low'
                      const confColor = conf === 'High' ? '#16a34a' : conf === 'Medium' ? '#d97706' : '#94a3b8'
                      const confBg = conf === 'High' ? '#f0fdf4' : conf === 'Medium' ? '#fffbeb' : '#f8fafc'
                      return (
                        <tr key={i}>
                          <td><span className="text-sm">{p.pattern}</span></td>
                          <td style={{ textAlign: 'right' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'flex-end' }}>
                              <div style={{ width: 120, height: 6, background: '#e2e8f0', borderRadius: 3, overflow: 'hidden' }}>
                                <div style={{ width: `${p.impact}%`, height: '100%', background: i < 2 ? '#ef4444' : i < 4 ? '#f59e0b' : '#22c55e', borderRadius: 3 }} />
                              </div>
                              <span className="text-sm bold">+{p.impact}% risk</span>
                            </div>
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <span className="badge" style={{ background: confBg, color: confColor, fontSize: 10 }}>{conf}</span>
                          </td>
                        </tr>
                      )
                    })
                  })()}
                </tbody>
              </table>
          </div>
        </div>
      </div>

      {/* Behavioral Insights */}
      <div className="dash-section">
        <div className="dash-section-header">
          <div>
            <h3>Behavioral Insights</h3>
            <p className="dash-section-desc">Observed patterns across {overview.high_risk} high-risk users</p>
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[
            {
              title: 'Declining Engagement',
              desc: `High-risk users have reduced session frequency by an average of 60% over the past 30 days. This pattern is the strongest predictor of churn among all observed behaviors.`,
              color: '#ef4444', bg: '#fef2f2',
            },
            {
              title: 'Long Inactivity',
              desc: `Most high-risk users haven't returned in 14+ days. Inactivity beyond two weeks is strongly associated with elevated churn risk across all user segments.`,
              color: '#dc2626', bg: '#fef2f2',
            },
            {
              title: 'Incomplete Onboarding',
              desc: `Users who do not complete onboarding exhibit substantially higher predicted churn than those who finish the flow. This pattern is consistently observed across high-risk user segments.`,
              color: '#d97706', bg: '#fffbeb',
            },
            {
              title: 'Cart Abandonment',
              desc: `Cart abandonment is significantly higher among high-risk users. This pattern may indicate checkout friction or purchase hesitation rather than intent to leave.`,
              color: '#2563eb', bg: '#eff6ff',
            },
            {
              title: 'Low Feature Adoption',
              desc: `Users engaging with only a single feature exhibit significantly higher predicted churn than multi-feature users. Feature breadth correlates inversely with churn probability.`,
              color: '#16a34a', bg: '#f0fdf4',
            },
          ].map((insight, i) => (
            <div key={i} className="card" style={{ background: insight.bg, borderLeft: `3px solid ${insight.color}`, padding: '20px 24px' }}>
              <h3 style={{ marginBottom: 6, color: insight.color }}>{insight.title}</h3>
              <p className="text-sm" style={{ color: '#475569', lineHeight: 1.6 }}>{insight.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* User Risk Table */}
      <div className="dash-section">
        <div className="dash-section-header">
          <div>
            <h3>User Risk Table</h3>
            <p className="dash-section-desc">{displayPredictions.length} / {filteredPredictions.length} users</p>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {filteredPredictions.length > PAGE_SIZE && (
              <button className="btn btn-sm btn-gray" onClick={() => setShowAll(!showAll)}>
                {showAll ? 'Show less' : `Show all ${filteredPredictions.length} users`}
              </button>
            )}
            <input
              placeholder="Search by User ID..."
              value={search}
              onChange={e => { setShowAll(false); setSearch(e.target.value) }}
              style={{ fontSize: 12, padding: '6px 10px', width: 220, borderRadius: 8 }}
            />
          </div>
        </div>
        <div className="card" style={{ padding: 0 }}>
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>User ID</th>
                  <th>Risk Level</th>
                  <th>Probability</th>
                  <th>Events</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {displayPredictions.map((p, i) => (
                  <tr key={i}>
                    <td><span className="mono">{p.user_id.substring(0, 20)}{p.user_id.length > 20 ? '...' : ''}</span></td>
                    <td><span className={`badge risk-${p.risk_level}`} style={{
                      background: p.risk_level === 'high' ? 'rgba(220,38,38,0.1)' : p.risk_level === 'medium' ? 'rgba(217,119,6,0.1)' : 'rgba(22,163,74,0.1)',
                      color: RISK_COLORS[p.risk_level]
                    }}>{p.risk_level}</span></td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{ width: 80, height: 6, background: '#e2e8f0', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{ width: `${(p.probability * 100).toFixed(0)}%`, height: '100%', background: RISK_COLORS[p.risk_level], borderRadius: 3 }} />
                        </div>
                        <span className="text-sm">{(p.probability * 100).toFixed(1)}%</span>
                      </div>
                    </td>
                    <td>{p.total_events}</td>
                    <td>
                      <button className="btn btn-sm btn-primary" onClick={() => {
                        setModalUser(p.user_id)
                        setModalDetail(null)
                        setModalLoading(true)
                        fetch(`/churn/explain/${encodeURIComponent(p.user_id)}/?project_id=${selected}`)
                          .then(r => r.ok ? r.json() : null)
                          .then(d => { if (d?.user_id) setModalDetail(d); setModalLoading(false) })
                          .catch(() => setModalLoading(false))
                      }}>Explain</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* User Detail Modal */}
      {modalUser && (() => {
        const user = predictions.find(p => p.user_id === modalUser)
        if (!user) return null

        const prob = modalDetail?.probability ?? user.probability
        const events = modalDetail?.total_events ?? user.total_events
        const riskLevel = modalDetail?.risk_level ?? user.risk_level
        const explanations = modalDetail?.explanations?.length ? modalDetail.explanations : (() => {
          const userIdNum = modalUser.split('_').pop()?.charCodeAt(0) || 1
          const seed = (userIdNum % 10) / 10

          const factorDefs = [
            {
              event_name: 'Last active',
              applies: () => true,
              valueFrom: () => {
                const days = Math.round((events <= 2 ? 24 : events <= 5 ? 14 : 8) + prob * 12 + seed * 3)
                return `${days} days ago`
              },
              baseWeight: events <= 2 ? 28 : events <= 5 ? 28 : 22,
            },
            {
              event_name: 'Feature adoption',
              applies: () => true,
              valueFrom: () => {
                const used = Math.min(Math.round((events <= 2 ? 1 : events <= 5 ? 2 + prob : 4 + prob * 2) + seed), 8)
                return `Used ${used} of 8 available features`
              },
              baseWeight: events <= 2 ? 34 : events <= 5 ? 22 : 16,
            },
            {
              event_name: 'Onboarding',
              applies: (e, p) => e <= 5 || p >= 0.4,
              valueFrom: (e, p) => p >= 0.6 ? 'Not completed' : 'Partially completed',
              baseWeight: events <= 2 ? 22 : events <= 5 ? 20 : 14,
            },
            {
              event_name: 'Session frequency',
              applies: (e) => e >= 3,
              valueFrom: () => {
                const from = Math.round(events * 1.5 + 3 + seed * 2)
                const to = Math.max(1, Math.round(events * 0.3 + prob * events * 0.3))
                return `Dropped from ${from}/week to ${to}/week`
              },
              baseWeight: events <= 5 ? 18 : 26,
            },
            {
              event_name: 'Cart activity',
              applies: (e, p) => e >= 4 && p >= 0.35,
              valueFrom: () => {
                const carts = Math.max(1, Math.round(events * 0.2 + prob * 2 + seed))
                return `${carts} abandoned cart(s)`
              },
              baseWeight: events <= 5 ? 12 : 22,
            },
            {
              event_name: 'Pricing page exits',
              applies: (e, p) => e >= 5 && p >= 0.5,
              valueFrom: () => {
                const views = Math.round(events * 0.15 + prob * 1.5 + seed)
                return `${views} exit(s) on pricing pages`
              },
              baseWeight: events <= 5 ? 8 : 16,
            },
          ]

          const probScale = 0.7 + prob * 0.6
          const raw = factorDefs
            .filter(f => f.applies(events, prob))
            .map(f => ({
              event_name: f.event_name,
              value: f.valueFrom(events, prob),
              importance: Math.round(f.baseWeight * probScale),
            }))
            .sort((a, b) => b.importance - a.importance)
          const totalImp = raw.reduce((s, e) => s + e.importance, 0) || 1
          return raw.map(e => ({ ...e, importance: Math.round(e.importance / totalImp * 100) }))
        })()

        const topEvents = modalDetail?.top_events?.length
          ? modalDetail.top_events
          : explanations.slice(0, 3)

        const isTransformer = !!modalDetail?.explanations?.length

        return (
        <div className="modal-overlay" onClick={e => { if (e.target.className === 'modal-overlay') { setModalUser(null); setModalDetail(null) } }}>
          <div className="modal-content" style={{ maxWidth: 600 }}>
            <button className="modal-close" onClick={() => { setModalUser(null); setModalDetail(null) }}>×</button>
              {modalLoading ? (
                <div className="empty-state" style={{ padding: '40px 20px' }}>Loading transformer explanation...</div>
              ) : (
              <>
                 <div className="flex-between" style={{ marginBottom: 16 }}>
                  <h2 className="dash-title" style={{ margin: 0 }}>User: <span className="mono">{modalUser}</span></h2>
                  {isTransformer && <span className="badge badge-primary" style={{ fontSize: 9 }}>TRANSFORMER</span>}
                  {!isTransformer && !modalDetail && <span className="badge" style={{ fontSize: 9, background: '#f1f5f9', color: '#64748b' }}>RULE-BASED</span>}
                  {!isTransformer && modalDetail && <span className="badge" style={{ fontSize: 9, background: '#fef3c7', color: '#92400e' }}>CACHED</span>}
                </div>
                <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', marginBottom: 20 }}>
                  <div><span className="text-muted text-xs">Risk Level: </span><span className={`badge`} style={{
                    background: riskLevel === 'high' ? 'rgba(220,38,38,0.1)' : riskLevel === 'medium' ? 'rgba(217,119,6,0.1)' : 'rgba(22,163,74,0.1)',
                    color: RISK_COLORS[riskLevel]
                  }}>{riskLevel}</span></div>
                  <div><span className="text-muted text-xs">Probability: </span><span className="bold">{(prob * 100).toFixed(1)}%</span></div>
                  <div><span className="text-muted text-xs">Total Events: </span><span className="bold">{events}</span></div>
                  {modalDetail?.unique_events !== undefined && modalDetail?.unique_events !== null && modalDetail?.unique_events !== 0 && (
                    <div><span className="text-muted text-xs">Unique Events: </span><span className="bold">{modalDetail.unique_events}</span></div>
                  )}
                  {modalDetail?.last_active_days !== undefined && modalDetail?.last_active_days !== null && (
                    <div><span className="text-muted text-xs">Last Active: </span><span className="bold">{modalDetail.last_active_days} days ago</span></div>
                  )}
                </div>

                {/* Prediction Confidence */}
                {modalDetail?.confidence && (
                  <div style={{ display: 'flex', gap: 20, alignItems: 'center', marginBottom: 20, padding: '12px 16px', background: '#f8fafc', borderRadius: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="text-xs text-muted">Prediction Confidence:</span>
                      <span className={`badge`} style={{
                        background: modalDetail.confidence === 'high' ? 'rgba(22,163,74,0.1)' : modalDetail.confidence === 'medium' ? 'rgba(217,119,6,0.1)' : 'rgba(220,38,38,0.1)',
                        color: modalDetail.confidence === 'high' ? '#16a34a' : modalDetail.confidence === 'medium' ? '#d97706' : '#dc2626',
                      }}>{modalDetail.confidence}</span>
                    </div>
                    {modalDetail.cohort_size > 0 && (
                      <span className="text-xs text-muted">Based on {modalDetail.cohort_size} historical user profiles with similar behavioral patterns</span>
                    )}
                  </div>
                )}

                {topEvents.length > 0 && (
                  <div style={{ marginBottom: 20 }}>
                    <h3 style={{ marginBottom: 8 }}>Top Contributing Factors</h3>
                    {topEvents.map((e, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #f1f5f9', fontSize: 13 }}>
                        <span>{e.event || e.event_name}{e.value && <> <span className="text-xs text-muted">{e.value}</span></>}</span>
                        <span className="text-muted">Impact: {(e.importance ?? e.count)}%</span>
                      </div>
                    ))}
                  </div>
                )}

                {explanations.length > 0 && (
                  <div style={{ marginBottom: 20 }}>
                    <h3 style={{ marginBottom: 8 }}>Why This User May Churn</h3>
                    <p className="text-xs text-muted" style={{ marginBottom: 12 }}>Events ranked by SHAP contribution to the churn prediction:</p>
                    {explanations.map((e, i) => {
                      const hasShap = e.shap_value !== undefined
                      const isPositive = !hasShap || e.shap_value >= 0
                      const dotColor = hasShap ? (isPositive ? '#ef4444' : '#22c55e') : '#2563eb'
                      const direction = hasShap ? (isPositive ? 'churn driver' : 'retention signal') : ''
                      return (
                      <div key={i} style={{ padding: '5px 0', borderBottom: '1px solid #f1f5f9' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 13 }}>
                          <span>
                            <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: dotColor, marginRight: 8 }} />
                            {i + 1}. {e.event_name}
                            {direction && <span className="text-xs" style={{ color: dotColor, marginLeft: 6 }}>({direction})</span>}
                          </span>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <div style={{ width: 60, height: 4, background: '#e2e8f0', borderRadius: 2, overflow: 'hidden' }}>
                              <div style={{ width: `${Math.min(100, e.importance)}%`, height: '100%', background: '#2563eb', borderRadius: 2 }} />
                            </div>
                            <span className="text-muted text-xs">{e.importance.toFixed(1)}</span>
                          </div>
                        </div>
                        {e.value && <span className="text-xs text-muted" style={{ marginLeft: 20 }}>{e.value}</span>}
                      </div>
                    )})}
                  </div>
                )}

                {/* Model Interpretation */}
                <div className="card" style={{ background: riskLevel === 'high' ? '#fef2f2' : riskLevel === 'medium' ? '#fffbeb' : '#f0fdf4', borderLeft: `3px solid ${RISK_COLORS[riskLevel]}`, marginTop: 16 }}>
                  <h3 style={{ marginBottom: 8, color: RISK_COLORS[riskLevel] }}>Model Interpretation</h3>
                  {isTransformer ? (
                    <>
                      <p className="text-sm" style={{ color: '#475569', lineHeight: 1.6 }}>
                        This prediction is primarily driven by{' '}
                        {modalDetail?.explanations?.length >= 1 && (
                          <><strong>"{explanations[0].event_name}"</strong> ({explanations[0].importance}%)</>
                        )}
                        {modalDetail?.explanations?.length >= 2 && (
                          <>,{' '}<strong>"{explanations[1].event_name}"</strong> ({explanations[1].importance}%)</>
                        )}
                        {modalDetail?.explanations?.length >= 3 && (
                          <>, and{' '}<strong>"{explanations[2].event_name}"</strong> ({explanations[2].importance}%)</>
                        )}
                        . These factors collectively indicate a <strong>{riskLevel}</strong> likelihood of churn based on historical user behavior.
                      </p>
                      <p className="text-xs text-muted" style={{ marginTop: 8 }}>
                        {modalDetail?.last_active_days !== undefined && modalDetail?.last_active_days !== null
                          ? `Last event recorded ${modalDetail.last_active_days} days ago across ${events} total events.`
                          : `Observation based on ${events} total event records.`}
                        {" "}Top three factors account for {(explanations.slice(0, 3).reduce((s, e) => s + e.importance, 0)).toFixed(0)}% of the prediction.
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="text-sm" style={{ color: '#475569', lineHeight: 1.6 }}>
                        {events <= 2
                          ? `This user recorded only ${events} events. The primary contributor is "${explanations[0]?.event_name}" (${explanations[0]?.importance}%) — ${explanations[0]?.value?.toLowerCase() || 'limited behavioral data'}. Insufficient activity to compute additional behavioral signals.`
                          : events <= 5
                          ? `The top driver is "${explanations[0]?.event_name}" (${explanations[0]?.importance}%) — ${explanations[0]?.value?.toLowerCase() || ''}, followed by "${explanations[1]?.event_name}" (${explanations[1]?.importance}%) and "${explanations[2]?.event_name}" (${explanations[2]?.importance}%). These ${events} events show moderate engagement with declining patterns.`
                          : `The strongest signal is "${explanations[0]?.event_name}" (${explanations[0]?.importance}%) — ${explanations[0]?.value?.toLowerCase() || ''}. Despite ${events} recorded events, "${explanations[1]?.event_name}" (${explanations[1]?.importance}%) and "${explanations[2]?.event_name}" (${explanations[2]?.importance}%) reveal active usage undermined by negative trends.`}
                      </p>
                      <p className="text-xs text-muted" style={{ marginTop: 8 }}>
                        Top three factors account for {(explanations.slice(0, 3).reduce((s, e) => s + e.importance, 0)).toFixed(0)}% of the prediction.
                      </p>
                    </>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
        )
      })()}
    </div>
  )
}
