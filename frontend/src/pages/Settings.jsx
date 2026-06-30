import { useState, useEffect } from 'react'
import { useOutletContext, useParams } from 'react-router-dom'
import { api } from '../api'

export default function Settings() {
  const { selected } = useOutletContext()
  const { id } = useParams()
  const [project, setProject] = useState(null)
  const [keys, setKeys] = useState([])
  const [name, setName] = useState('')
  const [saving, setSaving] = useState(false)
  const [regenerating, setRegenerating] = useState(false)
  const [copied, setCopied] = useState(null)

  useEffect(() => {
    if (!selected) return
    api.projects.get(selected).then(p => {
      setProject(p)
      setName(p.name)
    }).catch(() => {})
    api.projects.keys(selected).then(setKeys).catch(() => {})
  }, [selected])

  async function saveName() {
    if (!selected || !name.trim()) return
    setSaving(true)
    try {
      const p = await api.put(`/api/v1/projects/${selected}/`, { name: name.trim() })
      setProject(p)
    } catch {}
    setSaving(false)
  }

  async function regenerate() {
    if (!selected) return
    setRegenerating(true)
    try {
      const newKey = await api.projects.regenerateKey(selected)
      const updated = await api.projects.keys(selected)
      setKeys(updated)
    } catch {}
    setRegenerating(false)
  }

  function copy(text, id) {
    navigator.clipboard.writeText(text)
    setCopied(id)
    setTimeout(() => setCopied(null), 2000)
  }

  const activeKey = keys.find(k => k.is_active)
  const apiKey = activeKey?.key || project?.api_key || ''

  const cdnSnippet = `<script src="/sdk/insightflow.js"><\/script>
<script>
  InsightFlow.init('${apiKey}', {
    apiHost: 'http://localhost:8000'
  });
  InsightFlow.track('pageview');
<\/script>`

  const npmSnippet = `import InsightFlow from 'insightflow-sdk'

InsightFlow.init('${apiKey}', {
  apiHost: 'http://localhost:8000'
})
InsightFlow.track('pageview')`

  if (!selected) {
    return <div className="empty-state" style={{ padding: '80px 20px' }}>Select a project from the sidebar</div>
  }

  return (
    <div className="dash">
      <div className="dash-header">
        <div>
          <h2 className="dash-title">Project Settings</h2>
          <p className="dash-subtitle">Manage your project configuration and API keys</p>
        </div>
      </div>

      <div className="dash-section">
        <div className="dash-section-header">
          <div>
            <h3>Project Name</h3>
            <p className="dash-section-desc">Rename your project</p>
          </div>
        </div>
        <div className="card" style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            style={{ flex: 1, maxWidth: 400 }}
          />
          <button className="btn btn-primary btn-sm" onClick={saveName} disabled={saving || !name.trim() || name === project?.name}>
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      <div className="dash-section">
        <div className="dash-section-header">
          <div>
            <h3>API Key</h3>
            <p className="dash-section-desc">Your secret key used to authenticate SDK requests</p>
          </div>
        </div>
        <div className="card">
          {activeKey ? (
            <div>
              <div className="api-key-box" style={{ marginTop: 0 }}>
                <span>{activeKey.key}</span>
                <button className="btn btn-sm btn-gray" onClick={() => copy(activeKey.key, 'key')} style={{ whiteSpace: 'nowrap' }}>
                  {copied === 'key' ? 'Copied!' : 'Copy'}
                </button>
              </div>
              <div style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
                <button className="btn btn-sm btn-red" onClick={regenerate} disabled={regenerating}>
                  {regenerating ? 'Regenerating...' : 'Regenerate Key'}
                </button>
                <span className="text-xs text-muted">
                  Created {new Date(activeKey.created_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          ) : (
            <div className="empty-state" style={{ padding: '30px 20px' }}>
              No active API keys. Create one to start tracking events.
            </div>
          )}
        </div>
      </div>

      <div className="dash-section">
        <div className="dash-section-header">
          <div>
            <h3>SDK Integration</h3>
            <p className="dash-section-desc">Add InsightFlow to your website or app</p>
          </div>
        </div>
        <div className="card">
          <label style={{ marginBottom: 10 }}>CDN (script tag)</label>
          <div className="code-snippet" style={{ marginTop: 0 }}>
            <pre>{cdnSnippet}</pre>
            <button className="btn btn-sm btn-gray" onClick={() => copy(cdnSnippet, 'cdn')} style={{ whiteSpace: 'nowrap' }}>
              {copied === 'cdn' ? 'Copied!' : 'Copy'}
            </button>
          </div>

          <label style={{ marginTop: 20, marginBottom: 10 }}>npm / bundler</label>
          <div className="code-snippet" style={{ marginTop: 0 }}>
            <pre>{npmSnippet}</pre>
            <button className="btn btn-sm btn-gray" onClick={() => copy(npmSnippet, 'npm')} style={{ whiteSpace: 'nowrap' }}>
              {copied === 'npm' ? 'Copied!' : 'Copy'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
