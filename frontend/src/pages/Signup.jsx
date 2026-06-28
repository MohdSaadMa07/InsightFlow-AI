import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { api } from '../api'

export default function Signup() {
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', email: '', password: '', organization_name: '', project_name: '' })
  const [error, setError] = useState('')

  function set(field) {
    return (e) => setForm(prev => ({ ...prev, [field]: e.target.value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    try {
      const data = await api.auth.signup(form)
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
        <p className="text-muted" style={{ marginBottom: 20 }}>Create your account</p>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1, marginBottom: 12 }}>
              <label>Username</label>
              <input value={form.username} onChange={set('username')} placeholder="username" required />
            </div>
            <div style={{ flex: 1, marginBottom: 12 }}>
              <label>Email</label>
              <input type="email" value={form.email} onChange={set('email')} placeholder="you@example.com" required />
            </div>
          </div>
          <div style={{ marginBottom: 12 }}>
            <label>Password</label>
            <input type="password" value={form.password} onChange={set('password')} placeholder="min 8 characters" required />
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1, marginBottom: 20 }}>
              <label>Organization</label>
              <input value={form.organization_name} onChange={set('organization_name')} placeholder="My Company" required />
            </div>
            <div style={{ flex: 1, marginBottom: 20 }}>
              <label>Project</label>
              <input value={form.project_name} onChange={set('project_name')} placeholder="My Website" required />
            </div>
          </div>
          <button className="btn btn-green" style={{ width: '100%' }} type="submit">Create Account</button>
        </form>
        <p className="text-sm text-muted" style={{ marginTop: 16, textAlign: 'center' }}>
          Already have an account? <Link to="/login" className="text-blue">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
