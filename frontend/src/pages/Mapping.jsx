import { useState, useEffect } from 'react'
import { useOutletContext } from 'react-router-dom'
import { api } from '../api'

const CATEGORIES = [
  'discovery', 'purchase_intent', 'checkout', 'conversion', 'engagement', 'unknown',
]

const CATEGORY_LABELS = {
  discovery: 'Discovery',
  purchase_intent: 'Purchase Intent',
  checkout: 'Checkout',
  conversion: 'Conversion',
  engagement: 'Engagement',
  unknown: 'Unknown',
}

export default function Mapping() {
  const { selected } = useOutletContext()
  const [mappings, setMappings] = useState([])
  const [detected, setDetected] = useState([])
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    if (!selected) return
    loadMappings()
    setDetected([])
  }, [selected])

  async function loadMappings() {
    try {
      const data = await api.mapping.list(selected)
      setMappings(data)
    } catch {}
  }

  async function detect() {
    setLoading(true)
    setMsg('')
    try {
      const data = await api.mapping.detect(selected)
      setDetected(data)
      if (data.length === 0) setMsg('No new events found to map.')
      loadMappings()
    } catch (err) {
      setMsg(err.message)
    }
    setLoading(false)
  }

  async function updateMapping(mapping) {
    try {
      await api.mapping.update(mapping.id, { category: mapping.category })
      loadMappings()
    } catch {}
  }

  function setCategory(id, category) {
    setMappings(prev => prev.map(m => m.id === id ? { ...m, category } : m))
  }

  if (!selected) {
    return <div className="empty-state" style={{ padding: '80px 20px' }}>Select a project from the sidebar</div>
  }

  return (
    <div>
      <div className="flex-between" style={{ marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>Semantic Mapping</h2>
        <button className="btn btn-blue" onClick={detect} disabled={loading}>
          {loading ? 'Scanning...' : 'Scan for New Events'}
        </button>
      </div>

      {msg && <div className="alert alert-success">{msg}</div>}

      {detected.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3 style={{ marginBottom: 8 }}>New Events Detected</h3>
          <table>
            <thead>
              <tr>
                <th>Event Name</th>
                <th>Suggested</th>
                <th>Confidence</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {detected.map((d, i) => (
                <tr key={i}>
                  <td className="mono">{d.event_name}</td>
                  <td>
                    <span className={`badge ${d.confidence > 0.8 ? 'badge-green' : d.confidence > 0.5 ? 'badge-yellow' : 'badge-red'}`}>
                      {CATEGORY_LABELS[d.suggested_category] || d.suggested_category}
                    </span>
                  </td>
                  <td>{(d.confidence * 100).toFixed(0)}%</td>
                  <td>
                    <span className={`badge ${d.status === 'new' ? 'badge-yellow' : 'badge-green'}`}>
                      {d.status === 'new' ? 'Needs Review' : 'Auto-mapped'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card">
        <h3 style={{ marginBottom: 8 }}>Event Mappings</h3>
        {mappings.length === 0 ? (
          <div className="text-muted text-sm" style={{ padding: 30, textAlign: 'center' }}>
            No event mappings yet. Click "Scan for New Events" to detect them.
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Event Name</th>
                <th>Category</th>
                <th>Source</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {mappings.map(m => (
                <tr key={m.id}>
                  <td className="mono">{m.event_name}</td>
                  <td>
                    <select
                      value={m.category}
                      onChange={e => setCategory(m.id, e.target.value)}
                      style={{ fontSize: 12, padding: '4px 8px', width: 'auto' }}
                    >
                      {CATEGORIES.map(c => (
                        <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <span className={`badge ${m.is_auto_detected ? 'badge-yellow' : 'badge-blue'}`}>
                      {m.is_auto_detected ? 'Auto' : 'Manual'}
                    </span>
                  </td>
                  <td>
                    <button className="btn btn-green btn-sm" onClick={() => updateMapping(m)}>Save</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
