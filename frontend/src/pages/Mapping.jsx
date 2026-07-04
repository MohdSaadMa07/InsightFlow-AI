import { useState, useEffect } from 'react'
import { useOutletContext, Link } from 'react-router-dom'
import { api } from '../api'

const ALL_CATEGORIES = [
  { key: 'discovery', label: 'Discovery', color: '#22D3EE', funnel: true },
  { key: 'engagement', label: 'Engagement', color: '#F59E0B', funnel: true },
  { key: 'purchase_intent', label: 'Purchase Intent', color: '#EC4899', funnel: true },
  { key: 'conversion', label: 'Conversion', color: '#34D399', funnel: true },
  { key: 'exit', label: 'Exit', color: '#F87171', funnel: true },
  { key: 'checkout', label: 'Checkout', color: '#FBBF24', funnel: false },
  { key: 'authentication', label: 'Authentication', color: '#A78BFA', funnel: false },
  { key: 'support', label: 'Support', color: '#60A5FA', funnel: false },
]

const FUNNEL_STAGES = ALL_CATEGORIES.filter(c => c.funnel)

const FULL_CATEGORIES = [...ALL_CATEGORIES, { key: 'unknown', label: 'Unknown', color: '#606088', funnel: false }]

const CATEGORY_MAP = {}
FULL_CATEGORIES.forEach(c => { CATEGORY_MAP[c.key] = c })

export default function Mapping() {
  const { selected } = useOutletContext()
  const [mappings, setMappings] = useState([])
  const [detected, setDetected] = useState([])
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState('')
  const [cat, setCat] = useState({})
  const [funnel, setFunnel] = useState({})
  const [dirty, setDirty] = useState({})
  const [saving, setSaving] = useState(null)

  useEffect(() => {
    if (!selected) return
    loadMappings()
    setDetected([])
  }, [selected])

  async function loadMappings() {
    try {
      const data = await api.mapping.list(selected)
      setMappings(data)
      const c = {}, f = {}
      data.forEach(m => { c[m.id] = m.category; f[m.id] = m.used_in_funnel })
      setCat(c)
      setFunnel(f)
    } catch {}
  }

  async function detect() {
    setLoading(true)
    setMsg('')
    try {
      const data = await api.mapping.detect(selected)
      setDetected(data)
      if (!data.length) setMsg('No new events found.')
      loadMappings()
    } catch (err) { setMsg(err.message) }
    setLoading(false)
  }

  function onCategory(id, v) { setCat(p => ({ ...p, [id]: v })); setDirty(p => ({ ...p, [id]: true })) }
  function onToggle(id) { setFunnel(p => ({ ...p, [id]: !p[id] })); setDirty(p => ({ ...p, [id]: true })) }

  async function save(id) {
    setSaving(id)
    try {
      await api.mapping.update(id, { category: cat[id], used_in_funnel: funnel[id] })
      await api.mapping.computeFunnel(selected, 30)
      const next = { ...dirty }; delete next[id]; setDirty(next)
      await loadMappings()
      setMsg('Saved and funnel updated.')
    } catch (err) {
      setMsg(err.message)
    }
    setSaving(null)
  }

  function accept(d) {
    const m = mappings.find(x => x.event_name === d.event_name)
    if (m) {
      setCat(p => ({ ...p, [m.id]: d.suggested_category }))
      setFunnel(p => ({ ...p, [m.id]: d.used_in_funnel }))
      setDirty(p => ({ ...p, [m.id]: true }))
    }
  }

  if (!selected) return <div className="empty-state" style={{ padding: '80px 20px' }}>Select a project from the sidebar</div>

  const groups = {}
  ALL_CATEGORIES.forEach(c => { groups[c.key] = [] })
  const unknown = []
  mappings.forEach(m => {
    const c = cat[m.id] !== undefined ? cat[m.id] : m.category
    if (c === 'unknown') unknown.push(m)
    else if (groups[c]) groups[c].push(m)
  })

  const funnelCount = ALL_CATEGORIES.filter(c => c.funnel).reduce((s, c) => s + groups[c.key].length, 0)
  const otherCount = ALL_CATEGORIES.filter(c => !c.funnel).reduce((s, c) => s + groups[c.key].length, 0)

  return (
    <div>
      <div className="flex-between" style={{ marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 700, color: '#1e293b', margin: 0, letterSpacing: '-0.5px' }}>Semantic Mapping</h2>
          <p className="text-muted" style={{ marginTop: 2, fontSize: 12 }}>
            {mappings.length} events mapped &middot; <span style={{ color: '#22D3EE' }}>{funnelCount} in funnel</span> &middot; <span style={{ color: '#F59E0B' }}>{otherCount} other</span>
          </p>
        </div>
        <button className="btn btn-primary" onClick={detect} disabled={loading} style={{ fontSize: 12 }}>
          {loading ? 'Scanning…' : 'Scan for new events'}
        </button>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid #e2e8f0' }}>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
            {FUNNEL_STAGES.map((stage, i) => (
              <div key={stage.key} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{
                  padding: '3px 10px', borderRadius: 5, fontSize: 11, fontWeight: 600,
                  background: `${stage.color}10`, color: stage.color,
                }}>{stage.label}</span>
                {i < FUNNEL_STAGES.length - 1 && <span style={{ color: '#94a3b8', fontSize: 11 }}>&rarr;</span>}
              </div>
            ))}
            <span style={{ fontSize: 10, color: '#94a3b8', marginLeft: 4 }}>
              Funnel stages — events with <span style={{ color: '#22D3EE' }}>Funnel</span> checked appear here
            </span>
          </div>
        </div>

        {msg && <div className="alert alert-success" style={{ margin: '12px 20px 0' }}>{msg}</div>}

        {detected.length > 0 && (
          <div style={{ padding: '12px 20px', background: 'rgba(34,211,238,0.02)', borderBottom: '1px solid #e2e8f0' }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: '#1e293b', marginBottom: 8 }}>New events detected ({detected.length})</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {detected.map((d, i) => {
                const pct = (d.confidence || 0) * 100
                const cc = pct >= 80 ? '#34D399' : pct >= 50 ? '#FBBF24' : '#F87171'
                const n = d.status === 'new'
                return (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 10, padding: '6px 10px',
                    background: n ? 'rgba(248,113,113,0.03)' : 'transparent',
                    border: `1px solid ${n ? 'rgba(248,113,113,0.08)' : 'rgba(255,255,255,0.02)'}`,
                    borderRadius: 6, fontSize: 12,
                  }}>
                    {n && <span style={{ color: '#F87171' }}>&#9888;</span>}
                    <span style={{ fontFamily: "'SF Mono','Fira Code',monospace", color: '#334155', flex: 1 }}>{d.event_name}</span>
                    <span style={{ padding: '1px 6px', borderRadius: 3, background: `${cc}15`, color: cc, fontWeight: 600, fontSize: 10 }}>
                      {CATEGORY_MAP[d.suggested_category]?.label || d.suggested_category}
                    </span>
                    <span style={{ color: cc, fontWeight: 600, fontSize: 10, minWidth: 30 }}>{pct.toFixed(0)}%</span>
                    <button className="btn btn-green btn-sm" onClick={() => accept(d)} style={{ fontSize: 10, padding: '2px 8px' }}>Accept</button>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {mappings.length === 0 ? (
          <div className="text-muted text-sm" style={{ padding: 40, textAlign: 'center' }}>
            No events yet. Click <strong>Scan for new events</strong> to auto-detect them.
          </div>
        ) : (
          <div>
            {unknown.length > 0 && (
              <div style={{ padding: '10px 20px', background: 'rgba(248,113,113,0.02)', borderBottom: '1px solid #e2e8f0' }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: '#F87171', marginBottom: 6 }}>{unknown.length} unknown event{unknown.length > 1 ? 's' : ''}</div>
                {unknown.map(m => (
                  <Row key={m.id} m={m} cat={cat} funnel={funnel} dirty={dirty} saving={saving} onCategory={onCategory} onToggle={onToggle} onSave={save} />
                ))}
              </div>
            )}

            {ALL_CATEGORIES.map(group => {
              const items = groups[group.key] || []
              if (!items.length && unknown.length === 0) return null
              return (
                <div key={group.key}>
                  <div style={{
                    padding: '5px 20px', fontSize: 10, fontWeight: 600, color: group.color,
                    textTransform: 'uppercase', letterSpacing: '0.06em',
                    background: '#f8fafc',
                    borderBottom: '1px solid #e2e8f0',
                    display: 'flex', alignItems: 'center', gap: 6,
                  }}>
                    <span style={{ width: 5, height: 5, borderRadius: '50%', background: group.color, display: 'inline-block' }}></span>
                    {group.label}
                    {group.funnel && <span style={{ fontSize: 8, color: '#94a3b8', fontWeight: 400, textTransform: 'none' }}>FUNNEL</span>}
                    <span style={{ marginLeft: 'auto', color: '#94a3b8', fontWeight: 400, textTransform: 'none', fontSize: 10 }}>{items.length}</span>
                  </div>
                    {items.map(m => (
                    <Row key={m.id} m={m} cat={cat} funnel={funnel} dirty={dirty} saving={saving} onCategory={onCategory} onToggle={onToggle} onSave={save} />
                  ))}
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div style={{ marginTop: 12, textAlign: 'right', fontSize: 11 }}>
        <Link to={`/project/${selected}/funnels`} style={{ color: '#22D3EE' }}>View conversion funnel &rarr;</Link>
      </div>
    </div>
  )
}

function Row({ m, cat, funnel, dirty, saving, onCategory, onToggle, onSave }) {
  const c = cat[m.id] !== undefined ? cat[m.id] : m.category
  const f = funnel[m.id] !== undefined ? funnel[m.id] : CATEGORY_MAP[c]?.funnel || false
  const changed = dirty[m.id]
  const meta = CATEGORY_MAP[c] || CATEGORY_MAP.unknown

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '6px 20px', fontSize: 12,
      background: changed ? 'rgba(34,211,238,0.02)' : 'transparent',
      borderBottom: '1px solid #e2e8f0',
    }}>
      <span style={{ fontFamily: "'SF Mono','Fira Code',monospace", color: '#334155', flex: '1 1 140px', minWidth: 0 }}>
        {m.event_name}
        {m.is_auto_detected && (
          <span style={{ marginLeft: 4, fontSize: 9, color: '#34D399', fontWeight: 600, background: 'rgba(52,211,153,0.08)', padding: '1px 5px', borderRadius: 3 }}>
            auto
          </span>
        )}
      </span>
      <select
        value={c}
        onChange={e => onCategory(m.id, e.target.value)}
        style={{
          fontSize: 11, padding: '2px 6px', width: 120, borderRadius: 5, flexShrink: 0,
          borderColor: changed ? 'rgba(34,211,238,0.3)' : undefined,
          background: changed ? 'rgba(34,211,238,0.03)' : undefined,
        }}
      >
        {FULL_CATEGORIES.map(g => <option key={g.key} value={g.key}>{g.label}</option>)}
      </select>
      <label style={{ display: 'flex', alignItems: 'center', gap: 3, cursor: 'pointer', flexShrink: 0, fontSize: 10, color: f ? '#22D3EE' : '#94a3b8', fontWeight: 600, userSelect: 'none' }}>
        <input type="checkbox" checked={f} onChange={() => onToggle(m.id)} style={{ accentColor: '#22D3EE', width: 12, height: 12 }} />
        Funnel
      </label>
      {saving === m.id ? (
        <span style={{ fontSize: 10, color: '#64748b', flexShrink: 0, width: 44, textAlign: 'center' }}>Saving…</span>
      ) : changed ? (
        <button className="btn btn-green btn-sm" onClick={() => onSave(m.id)} style={{ fontSize: 10, padding: '2px 8px', flexShrink: 0 }}>Save</button>
      ) : (
        <div style={{ width: 44, flexShrink: 0 }}></div>
      )}
    </div>
  )
}
