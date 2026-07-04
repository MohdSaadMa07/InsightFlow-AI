import { Outlet, Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api } from '../api'

export default function ProjectLayout() {
  const { id } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  
  const [projects, setProjects] = useState([])
  const [currentProject, setCurrentProject] = useState(null)
  const [username, setUsername] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.auth.me().then(d => {
      setUsername(d.username)
      loadProjects()
    }).catch(() => {
      localStorage.removeItem('token')
      navigate('/')
    })
  }, [id])

  async function loadProjects() {
    try {
      const data = await api.projects.list()
      setProjects(data)
      const current = data.find(p => p.id == id)
      if (current) setCurrentProject(current)
      setLoading(false)
    } catch {}
  }

  function logout() {
    localStorage.removeItem('token')
    navigate('/')
  }

  if (loading) return null

  const navLinks = [
    { name: 'Dashboard', path: 'dashboard' },
    { name: 'Funnels', path: 'funnels' },
    { name: 'Semantic Mapping', path: 'mapping' },
    { name: 'Churn Risk', path: 'churn' },
    { name: 'Settings', path: 'settings' },
  ]

  return (
    <div className="layout">
      <nav className="topnav">
        <h1>
          <Link to="/projects" style={{ color: 'inherit', textDecoration: 'none' }}>InsightFlow</Link>
          <span style={{ margin: '0 12px', color: '#94a3b8' }}>/</span>
          <span className="current-project-name">{currentProject?.name}</span>
        </h1>
        <div className="user-badge">
          <span>{username}</span>
          <button className="btn btn-gray btn-sm" onClick={logout}>Logout</button>
        </div>
      </nav>

      <div className="body">
        <aside className="sidebar">
          
          <div className="card" style={{ padding: 12, marginBottom: 12 }}>
            <div className="text-xs text-muted bold" style={{ marginBottom: 8, paddingLeft: 4, textTransform: 'uppercase' }}>Switch Project</div>
            <select 
              className="project-selector" 
              value={id} 
              onChange={(e) => navigate(`/project/${e.target.value}/dashboard`)}
            >
              {projects.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>

          <div className="card" style={{ padding: '8px 12px' }}>
            {navLinks.map(link => {
              const fullPath = `/project/${id}/${link.path}`
              const isActive = location.pathname.startsWith(fullPath)
              return (
                <Link key={link.name} to={fullPath} className={`nav-link${isActive ? ' active' : ''}`}>
                  <span className="nav-link-dot" style={{ opacity: isActive ? 1 : 0 }}></span>
                  {link.name}
                </Link>
              )
            })}
          </div>
        </aside>

        <main className="main">
          <Outlet context={{ selected: id }} />
        </main>
      </div>
    </div>
  )
}
