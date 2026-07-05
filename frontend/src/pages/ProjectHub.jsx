import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'

export default function ProjectHub() {
  const navigate = useNavigate()
  const [projects, setProjects] = useState([])
  const [username, setUsername] = useState('')
  const [loading, setLoading] = useState(true)
  
  const [showNew, setShowNew] = useState(false)
  const [newName, setNewName] = useState('')
  const [newApiKey, setNewApiKey] = useState(null)

  useEffect(() => {
    api.auth.me().then(d => {
      setUsername(d.username)
      loadProjects()
    }).catch(() => {
      localStorage.removeItem('token')
      navigate('/')
    })
  }, [])

  async function loadProjects() {
    try {
      const data = await api.projects.list()
      setProjects(data)
    } finally {
      setLoading(false)
    }
  }

  function logout() {
    localStorage.removeItem('token')
    navigate('/')
  }

  async function createProject() {
    if (!newName.trim()) return
    try {
      const p = await api.projects.create(newName.trim())
      setNewName('')
      setProjects(prev => [...prev, p])
      setNewApiKey(p.api_key)
    } catch {}
  }

  function closeModal() {
    setShowNew(false)
    setNewApiKey(null)
    setNewName('')
  }

  if (loading) return null

  return (
    <div className="layout">
      <nav className="topnav">
        <h1>InsightFlow</h1>
        <div className="user-badge">
          <span>{username}</span>
          <button className="btn btn-gray btn-sm" onClick={logout}>Logout</button>
        </div>
      </nav>

      <div className="hub-container" style={{ padding: '60px 40px', maxWidth: 1000, margin: '0 auto', width: '100%' }}>
        
        {projects.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '100px 20px' }}>
            <div className="glow-orb" style={{ top: '100px', opacity: 0.5 }}></div>
            <h2 className="hero-title" style={{ fontSize: 48, marginBottom: 16 }}>Welcome to InsightFlow</h2>
            <p className="hero-subtitle" style={{ margin: '0 auto 40px' }}>
              You don't have any projects yet. Create your first project to generate an API key and start streaming events.
            </p>
            <button className="btn btn-primary bg-gradient btn-lg" onClick={() => setShowNew(true)}>
              + Create Project to Get Started
            </button>
          </div>
        ) : (
          <>
            <div className="hub-header">
              <div>
                <h2 className="hub-title-main">Your Projects</h2>
                <p className="hub-subtitle-main">Select a project to view analytics or create a new one.</p>
              </div>
              <button className="btn btn-primary bg-gradient" onClick={() => setShowNew(true)}>+ New Project</button>
            </div>
            
            <div className="hub-grid">
              {projects.map(p => (
                <Link to={`/project/${p.id}/dashboard`} key={p.id} className="hub-card">
                  <div className="hub-card-header">
                    <div className="hub-card-icon">
                      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <rect x="2" y="12" width="3" height="6" rx="0.5" fill="#22D3EE" opacity="0.5"/>
                        <rect x="7" y="8" width="3" height="10" rx="0.5" fill="#22D3EE" opacity="0.7"/>
                        <rect x="12" y="4" width="3" height="14" rx="0.5" fill="#22D3EE"/>
                      </svg>
                    </div>
                    <span className="hub-card-status">Active</span>
                  </div>
                  <div className="hub-card-title">{p.name}</div>
                  <div className="hub-card-desc">View analytics and insights for this project</div>
                  <div className="hub-card-footer">
                    <span className="hub-card-key-label">API Key</span>
                    <span className="hub-card-key">{p.api_key ? `...${p.api_key.slice(-6)}` : 'Not setup'}</span>
                  </div>
                </Link>
              ))}
              
              <div className="hub-card hub-card-create" onClick={() => setShowNew(true)}>
                <div className="hub-card-create-btn">+</div>
                <div style={{ color: '#1e293b', fontWeight: 600, fontSize: 16 }}>Create New Project</div>
              </div>
            </div>
          </>
        )}
      </div>

      {showNew && (
        <div className="modal-overlay">
          <div className="modal-content">
            <button className="modal-close" onClick={closeModal}>×</button>
            {newApiKey ? (
              <div>
                <div style={{ textAlign: 'center', marginBottom: 24 }}>
                  <div className="success-icon">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#4ade80" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                  </div>
                  <h2 style={{ fontSize: 20, color: '#f8fbff', margin: 0 }}>Create New Project</h2>
                  <p className="text-muted" style={{ marginTop: 6, fontSize: 13, lineHeight: 1.5 }}>
                    Project created. Use the API key below to connect your app to InsightFlow.
                  </p>
                </div>

                <label>API Key</label>
                <div className="api-key-box">
                  <span>{newApiKey || 'No Key'}</span>
                  <button className="btn btn-primary btn-sm" onClick={() => navigator.clipboard.writeText(newApiKey)}>Copy</button>
                </div>

                <div style={{ marginTop: 20 }}>
                  <label>CDN Setup (Recommended)</label>
                  <div className="code-snippet">
                    <pre>{`<script src="https://cdn.insightflow.ai/sdk.js" data-api-key="${newApiKey}"></script>`}</pre>
                    <button className="btn btn-gray btn-sm" onClick={() => navigator.clipboard.writeText(`<script src="https://cdn.insightflow.ai/sdk.js" data-api-key="${newApiKey}"></script>`)}>Copy</button>
                  </div>
              <p className="text-xs text-muted" style={{ marginTop: 8, lineHeight: 1.5 }}>
                Paste this tag in your HTML <code style={{ color: '#e2e8f0', background: 'rgba(15, 23, 42, 0.8)', padding: '1px 5px', borderRadius: 4, fontSize: 11 }}>&lt;head&gt;</code> to start tracking page views and events automatically.
              </p>
                </div>

                <button className="btn btn-gray" style={{ width: '100%', marginTop: 24 }} onClick={closeModal}>Done</button>
              </div>
            ) : (
              <div>
                <h2 style={{ fontSize: 20, color: '#f8fbff', marginBottom: 20 }}>Create New Project</h2>
                <p className="text-muted" style={{ marginBottom: 20 }}>Give your project a name to generate an API key.</p>
                <input
                  placeholder="Project Name (e.g. My Awesome App)"
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && createProject()}
                  style={{ marginBottom: 20 }}
                  autoFocus
                />
                <button className="btn btn-primary bg-gradient" style={{ width: '100%' }} onClick={createProject}>Create Project</button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
