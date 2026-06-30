import { useState, useEffect } from 'react'
import { useOutletContext, Link } from 'react-router-dom'
import { api } from '../api'

const CATEGORY_LABELS = {
  authentication: 'Authentication',
  discovery: 'Discovery',
  engagement: 'Engagement',
  purchase_intent: 'Purchase Intent',
  checkout: 'Checkout',
  conversion: 'Conversion',
  exit: 'Exit',
  support: 'Support',
  unknown: 'Unknown',
}

const FUNNEL_STEP_LABELS = {
  discovery: 'Discovery',
  engagement: 'Engagement',
  purchase_intent: 'Purchase Intent',
  conversion: 'Conversion',
}

function dropColor(pct) {
  if (pct < 15) return { color: '#34D399', bg: 'rgba(16,185,129,0.1)', label: 'Low drop' }
  if (pct <= 35) return { color: '#FBBF24', bg: 'rgba(251,191,36,0.1)', label: 'Medium drop' }
  return { color: '#F87171', bg: 'rgba(248,113,113,0.1)', label: 'High drop' }
}

function generateInsight(steps) {
  if (steps.length < 2) return null
  let biggestDrop = { pct: 0, from: '', to: '' }
  for (let i = 1; i < steps.length; i++) {
    const prev = steps[i - 1].count
    const curr = steps[i].count
    if (prev > 0) {
      const pct = ((prev - curr) / prev) * 100
      if (pct > biggestDrop.pct) {
        biggestDrop = { pct, from: steps[i - 1].step_name, to: steps[i].step_name }
      }
    }
  }
  if (biggestDrop.pct === 0) return null

  const last = steps[steps.length - 1]
  const lastPrev = steps[steps.length - 2]
  const fullConversion = lastPrev.count > 0 && ((last.count / lastPrev.count) * 100) >= 99

  const tips = {
    engagement: ['Simplify your signup form', 'Add social login options', 'Offer a guest checkout path'],
    discovery: ['Improve product page CTAs', 'Add customer reviews and social proof', 'Reduce page load time'],
    purchase_intent: ['Make Add to Cart button more prominent', 'Offer free shipping threshold', 'Add urgency indicators'],
    conversion: ['Streamline checkout flow', 'Add multiple payment options', 'Offer coupon codes for first purchase'],
    exit: ['Analyze exit pages for friction', 'Improve on-page engagement', 'Add exit-intent popups'],
  }

  const recommendations = tips[biggestDrop.to] || [`Review the ${biggestDrop.to} experience`, 'Run A/B tests on this step', 'Analyze user session recordings at this stage']

  return { biggestDrop, fullConversion, recommendations }
}

export default function Funnels() {
  const { selected } = useOutletContext()
  const [rows, setRows] = useState([])
  const [mappings, setMappings] = useState([])
  const [days, setDays] = useState(30)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [useCustom, setUseCustom] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    if (!selected) return
    if (useCustom && dateFrom && dateTo) {
      api.dashboard.funnels(selected, days, dateFrom, dateTo).then(setRows).catch(() => {})
    } else {
      api.dashboard.funnels(selected, days).then(setRows).catch(() => {})
    }
    api.mapping.list(selected).then(setMappings).catch(() => {})
  }, [selected, days, useCustom, dateFrom, dateTo])

  async function refreshFunnel() {
    if (!selected) return
    setRefreshing(true)
    try {
      await api.mapping.computeFunnel(selected, days)
      if (useCustom && dateFrom && dateTo) {
        const newRows = await api.dashboard.funnels(selected, days, dateFrom, dateTo)
        setRows(newRows || [])
      } else {
        const newRows = await api.dashboard.funnels(selected, days)
        setRows(newRows || [])
      }
    } catch {}
    setRefreshing(false)
  }

  if (!selected) {
    return <div className="empty-state" style={{ padding: '80px 20px' }}>Select a project from the sidebar</div>
  }

  const eventCategory = {}
  mappings.forEach(m => { eventCategory[m.event_name] = m.category })

  const grouped = {}
  rows.forEach(r => {
    const key = `${r.funnel_name || 'default'}|${r.date}`
    if (!grouped[key]) grouped[key] = []
    grouped[key].push(r)
  })
  const sortedKeys = Object.keys(grouped).sort().reverse()

  return (
    <div>
      <div className="flex-between" style={{ marginBottom: 24 }}>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 700, color: '#EAEAFA', margin: 0, letterSpacing: '-0.5px' }}>Conversion Funnel</h2>
          <p className="text-muted" style={{ marginTop: 4, fontSize: 13 }}>
            Track how users progress through each stage of your product
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="btn btn-sm btn-gray" onClick={refreshFunnel} disabled={refreshing} style={{ fontSize: 11 }}>
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
          <div className="period-group">
            {[7, 30, 90].map(d => (
              <button key={d} className={`period-btn${days === d && !useCustom ? ' active' : ''}`} onClick={() => { setDays(d); setUseCustom(false); setDateFrom(''); setDateTo('') }}>{d}d</button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <label style={{ fontSize: 11, color: '#606088', margin: 0, textTransform: 'none', letterSpacing: 0, whiteSpace: 'nowrap' }}>From</label>
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
              style={{ fontSize: 12, padding: '5px 8px', width: 140, borderRadius: 8, border: '1px solid #1E1E3A', background: '#0A0A18', color: '#EAEAFA' }} />
            <label style={{ fontSize: 11, color: '#606088', margin: 0, textTransform: 'none', letterSpacing: 0, whiteSpace: 'nowrap' }}>To</label>
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
              style={{ fontSize: 12, padding: '5px 8px', width: 140, borderRadius: 8, border: '1px solid #1E1E3A', background: '#0A0A18', color: '#EAEAFA' }} />
            <button className="btn btn-sm btn-gray" onClick={() => {
              if (!dateFrom || !dateTo) return
              setUseCustom(true)
              const [y1, m1, d1] = dateFrom.split('-').map(Number)
              const [y2, m2, d2] = dateTo.split('-').map(Number)
              const from = new Date(y1, m1 - 1, d1)
              const to = new Date(y2, m2 - 1, d2)
              const diff = Math.round((to - from) / (1000 * 60 * 60 * 24))
              setDays(Math.max(1, diff))
            }} disabled={!dateFrom || !dateTo}>Apply</button>
          </div>
        </div>
      </div>

      {sortedKeys.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
          <div style={{ fontSize: 14, color: '#606088', marginBottom: 12 }}>No funnel data yet</div>
          <div style={{ fontSize: 12, color: '#404068', marginBottom: 24 }}>Configure event mappings on the Semantic Mapping page, then events will automatically build your funnel.</div>
          <Link to={`/project/${selected}/mapping`} className="btn btn-primary">Go to Semantic Mapping</Link>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {sortedKeys.map(key => {
            const steps = grouped[key].sort((a, b) => a.step_order - b.step_order)
            const firstCount = steps[0]?.count || 1
            const funnelName = rows.find(r => `${r.funnel_name || 'default'}|${r.date}` === key)?.funnel_name || 'Funnel'
            const date = steps[0]?.date || ''
            const lastCount = steps[steps.length - 1]?.count || 0
            const overallRate = firstCount > 0 ? ((lastCount / firstCount) * 100).toFixed(1) : '0.0'
            const insight = generateInsight(steps)

            return (
              <div className="card" key={key} style={{ padding: 28 }}>
                <div className="flex-between" style={{ marginBottom: 24 }}>
                  <div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: '#EAEAFA', letterSpacing: '-0.3px' }}>{funnelName}</div>
                    <div className="text-muted text-xs" style={{ marginTop: 2 }}>{date}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 22, fontWeight: 800, color: '#22D3EE' }}>{overallRate}%</div>
                    <div className="text-xs text-muted">overall conversion</div>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  {steps.map((s, i) => {
                    const pct = firstCount > 0 ? (s.count / firstCount) * 100 : 0
                    const dropPct = i > 0 && steps[i - 1].count > 0
                      ? ((steps[i - 1].count - s.count) / steps[i - 1].count) * 100
                      : 0
                    const cat = FUNNEL_STEP_LABELS[s.step_name] ? s.step_name : eventCategory[s.step_name]
                    const isLast = i === steps.length - 1
                    const dc = dropColor(dropPct)

                    return (
                      <div key={i}>
                        <div style={{
                          display: 'flex', alignItems: 'center', gap: 16,
                          padding: '12px 0',
                        }}>
                          <div style={{
                            width: 28, height: 28, borderRadius: 8,
                            background: 'rgba(34,211,238,0.08)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: 12, fontWeight: 700, color: '#22D3EE', flexShrink: 0
                          }}>{i + 1}</div>

                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                                <span style={{ fontSize: 14, fontWeight: 600, color: '#EAEAFA' }}>
                                  {FUNNEL_STEP_LABELS[s.step_name] || s.step_name}
                                </span>
                                {FUNNEL_STEP_LABELS[s.step_name] ? (
                                  <span className="badge badge-primary" style={{ fontSize: 10, letterSpacing: '0.05em', background: 'rgba(52,211,153,0.08)', color: '#34D399' }}>
                                    funnel
                                  </span>
                                ) : cat && (
                                  <span className="badge badge-primary" style={{ fontSize: 10, letterSpacing: '0.05em' }}>
                                    {CATEGORY_LABELS[cat] || cat}
                                  </span>
                                )}
                              </div>
                            </div>

                            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                              <div style={{ flex: 1 }}>
                                <div style={{ position: 'relative', height: 10 }}>
                                  <div style={{
                                    position: 'absolute', left: 0, top: 0, bottom: 0, right: 0,
                                    background: 'rgba(34,211,238,0.04)', borderRadius: 5
                                  }}></div>
                                  <div style={{
                                    position: 'absolute', left: 0, top: 0, bottom: 0,
                                    width: `${pct}%`, minWidth: pct > 0 ? 20 : 0,
                                    background: `linear-gradient(90deg, rgba(34,211,238,${0.7 - i * 0.12}), rgba(236,73,153,${0.4 - i * 0.08}))`,
                                    borderRadius: 5,
                                    transition: 'width 0.6s cubic-bezier(0.16, 1, 0.3, 1)'
                                  }}></div>
                                </div>
                              </div>
                              <div style={{ textAlign: 'right', flexShrink: 0, minWidth: 90 }}>
                                <div style={{ fontSize: 14, fontWeight: 700, color: '#EAEAFA', lineHeight: 1.2 }}>
                                  {s.count} <span style={{ fontSize: 11, fontWeight: 500, color: '#606088' }}>users</span>
                                </div>
                                <div style={{ fontSize: 12, color: '#8888B0', fontWeight: 500 }}>
                                  {s.conversion_rate}%
                                </div>
                              </div>
                            </div>

                            {dropPct > 0 && (
                              <div style={{
                                display: 'inline-flex', alignItems: 'center', gap: 4, marginTop: 6,
                                fontSize: 11, fontWeight: 600, color: dc.color,
                                background: dc.bg, padding: '2px 8px', borderRadius: 4
                              }}>
                                <svg width="10" height="10" viewBox="0 0 10 10" fill="none" style={{ transform: 'rotate(180deg)' }}>
                                  <path d="M5 1L5 9M5 9L2 6M5 9L8 6" stroke={dc.color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                                </svg>
                                {dropPct.toFixed(0)}% drop
                                <span style={{ fontWeight: 400, opacity: 0.7 }}>({dc.label})</span>
                              </div>
                            )}
                          </div>
                        </div>

                        {!isLast && (
                          <div style={{ paddingLeft: 44, paddingBottom: 4 }}>
                            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                              <path d="M7 2L7 12M7 12L3 8M7 12L11 8" stroke="#404068" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>

                {insight && (
                  <div style={{
                    marginTop: 20, padding: 20,
                    background: 'linear-gradient(135deg, rgba(34,211,238,0.04), rgba(236,73,153,0.03))',
                    border: '1px solid rgba(34,211,238,0.08)',
                    borderRadius: 12,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                      <div style={{
                        width: 28, height: 28, borderRadius: 6,
                        background: 'linear-gradient(135deg, #22D3EE, #EC4899)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 14
                      }}>
                        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                          <path d="M7 1C3.686 1 1 3.686 1 7C1 10.314 3.686 13 7 13C10.314 13 13 10.314 13 7C13 3.686 10.314 1 7 1Z" stroke="white" strokeWidth="1.2"/>
                          <path d="M7 4.5V7.5M7 9V9.005" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
                        </svg>
                      </div>
                      <span style={{ fontSize: 14, fontWeight: 700, color: '#EAEAFA' }}>Insight</span>
                    </div>

                    <p style={{ fontSize: 13, color: '#C0C0D8', lineHeight: 1.6, marginBottom: 12 }}>
                      <strong style={{ color: '#F87171' }}>{insight.biggestDrop.pct.toFixed(0)}%</strong> of users abandon the journey between{' '}
                      <strong style={{ color: '#22D3EE' }}>{insight.biggestDrop.from}</strong> and{' '}
                      <strong style={{ color: '#22D3EE' }}>{insight.biggestDrop.to}</strong>.
                      {insight.fullConversion && (
                        <> Users reaching the final step convert at <strong style={{ color: '#34D399' }}>100%</strong>.</>
                      )}
                    </p>

                    <div style={{ fontSize: 12, fontWeight: 600, color: '#606088', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>Recommendations</div>
                    <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
                      {insight.recommendations.slice(0, 3).map((r, ri) => (
                        <li key={ri} style={{
                          fontSize: 12, color: '#8888B0', lineHeight: 1.5,
                          padding: '4px 0', paddingLeft: 16,
                          position: 'relative'
                        }}>
                          <span style={{ position: 'absolute', left: 0, top: 7, width: 6, height: 6, borderRadius: '50%', background: '#22D3EE', opacity: 0.5 }}></span>
                          {r}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div style={{
                  marginTop: 20, paddingTop: 16, borderTop: '1px solid rgba(255,255,255,0.03)',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                }}>
                  <div className="text-xs text-muted">
                    Started with <span style={{ color: '#EAEAFA', fontWeight: 600 }}>{firstCount} users</span>
                    &nbsp;&middot;&nbsp;
                    <span style={{ color: '#22D3EE', fontWeight: 600 }}>{lastCount} converted</span>
                  </div>
                  <Link to={`/project/${selected}/mapping`} style={{ fontSize: 12, color: '#22D3EE' }}>
                    Edit mappings &rarr;
                  </Link>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
