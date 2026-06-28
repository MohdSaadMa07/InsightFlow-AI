import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { api } from '../api'

export default function Login() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      const data = await api.auth.login({ username, password })
      localStorage.setItem('token', data.token)
      navigate('/')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>InsightFlow</h1>
        <p className="text-muted" style={{ marginBottom: 20 }}>Sign in to your account</p>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 12 }}>
            <label>Username</label>
            <input value={username} onChange={e => setUsername(e.target.value)} placeholder="username" required />
          </div>
          <div style={{ marginBottom: 20 }}>
            <label>Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="password" required />
          </div>
          <button className="btn btn-blue" style={{ width: '100%' }} type="submit">Sign In</button>
        </form>
        <p className="text-sm text-muted" style={{ marginTop: 16, textAlign: 'center' }}>
          No account? <Link to="/signup" className="text-blue">Create one</Link>
        </p>
      </div>
    </div>
  )
}
