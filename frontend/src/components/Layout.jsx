import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api } from '../api'

export default function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const [projects, setProjects] = useState([])
  const [selected, setSelected] = useState(null)
  const [newName, setNewName] = useState('')
  const [showNew, setShowNew] = useState(false)
  const [newApiKey, setNewApiKey] = useState(null)
  const [username, setUsername] = useState('')

  useEffect(() => {
    api.auth.me().then(d => setUsername(d.username)).catch(() => {
      localStorage.removeItem('token')
      navigate('/login')
    })
    loadProjects()
  }, [])

  async function loadProjects() {
    try {
      const data = await api.projects.list()
      setProjects(data)
    } catch {}
  }

  async function createProject() {
    if (!newName.trim()) return
    try {
      const p = await api.projects.create(newName.trim())
      setNewName('')
      setProjects(prev => [...prev, p])
      setSelected(p.id)
      setNewApiKey(p.api_key)
    } catch {}
  }

  function closeModal() {
    setShowNew(false)
    setNewApiKey(null)
    setNewName('')
  }

  function logout() {
    localStorage.removeItem('token')
    navigate('/login')
  }

  const isMapping = location.pathname === '/mapping'

  return (
    <div className="layout">
      {showNew && (
        <div className="modal-overlay">
          <div className="modal-content">
            <button className="modal-close" onClick={closeModal}>×</button>
            <h2 style={{ fontSize: 20, color: '#fff', marginBottom: 8 }}>Create New Project</h2>
            {newApiKey ? (
              <div>
                <p className="text-muted" style={{ marginBottom: 16 }}>Project created successfully! Here is your API Key for the SDK:</p>
                <div className="api-key-box">
                  <span>{newApiKey || 'No Key'}</span>
                  <button className="btn btn-blue btn-sm" onClick={() => navigator.clipboard.writeText(newApiKey)}>Copy</button>
                </div>
                <p className="text-xs text-muted" style={{ marginTop: 12 }}>Store this key securely in your application.</p>
                <button className="btn btn-gray" style={{ width: '100%', marginTop: 24 }} onClick={closeModal}>Done</button>
              </div>
            ) : (
              <div>
                <p className="text-muted" style={{ marginBottom: 20 }}>Give your project a name to generate an API key.</p>
                <input
                  placeholder="Project Name (e.g. My Awesome App)"
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && createProject()}
                  style={{ marginBottom: 20 }}
                  autoFocus
                />
                <button className="btn btn-blue bg-gradient-blue" style={{ width: '100%' }} onClick={createProject}>Create Project</button>
              </div>
            )}
          </div>
        </div>
      )}

      <nav className="topnav">
        <h1>InsightFlow</h1>
        <div className="user-badge">
          <span>{username}</span>
          <button className="btn btn-gray btn-sm" onClick={logout}>Logout</button>
        </div>
      </nav>

      <div className="body">
        <aside className="sidebar">
          <div className="card">
            <div className="flex-between" style={{ marginBottom: 8 }}>
              <h2 style={{ fontSize: 13, margin: 0 }}>Projects</h2>
              <button className="btn btn-blue btn-sm" onClick={() => setShowNew(true)}>+ New</button>
            </div>
            {projects.map(p => (
              <div
                key={p.id}
                className={`project-item${p.id === selected ? ' active' : ''}`}
                onClick={() => setSelected(p.id)}
              >
                {p.name}
              </div>
            ))}
            {projects.length === 0 && (
              <div className="text-muted text-sm" style={{ padding: 16, textAlign: 'center' }}>No projects</div>
            )}
          </div>

          <div className="card" style={{ padding: 12 }}>
            <Link to="/dashboard" className={`nav-link${!isMapping ? ' active' : ''}`}>Dashboard</Link>
            <Link to="/mapping" className={`nav-link${isMapping ? ' active' : ''}`}>Semantic Mapping</Link>
          </div>
        </aside>

        <main className="main">
          <Outlet context={{ selected, projects }} />
        </main>
      </div>
    </div>
  )
}
