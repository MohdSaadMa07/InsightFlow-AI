import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useState } from 'react'
import Dashboard from './pages/Dashboard'
import Funnels from './pages/Funnels'
import Mapping from './pages/Mapping'
import ProjectHub from './pages/ProjectHub'
import ProjectLayout from './components/ProjectLayout'
import Placeholder from './pages/Placeholder'
import Landing from './pages/Landing'

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token'))

  const handleAuth = (newToken) => {
    localStorage.setItem('token', newToken)
    setToken(newToken)
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={token ? <Navigate to="/projects" /> : <Landing onAuth={handleAuth} />} />
        
        <Route path="/projects" element={token ? <ProjectHub /> : <Navigate to="/" />} />
        
        <Route path="/project/:id" element={token ? <ProjectLayout /> : <Navigate to="/" />}>
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="funnels" element={<Funnels />} />

          <Route path="mapping" element={<Mapping />} />
          <Route path="settings" element={<Placeholder title="Settings" />} />
          
          <Route index element={<Navigate to="dashboard" replace />} />
        </Route>
        
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  )
}
