import { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import DashboardViewer from './components/DashboardViewer'
import AuthCallback from './components/AuthCallback'
import './App.css'

const AuthGuard = ({ children }) => {
  const token = localStorage.getItem('jwt_token')
  const empresaRaw = localStorage.getItem('empresa')

  if (!token || !empresaRaw) {
    const redirectUri = window.location.origin + '/auth-callback'
    window.location.href = `https://auth.sade.com.do/?client_id=sade-dashboard&redirect_uri=${encodeURIComponent(redirectUri)}`
    return null
  }

  return children
}

const MainApp = () => {
  const [selectedDashboardId, setSelectedDashboardId] = useState(null)
  const [empresa, setEmpresa] = useState(null)

  useEffect(() => {
    const emp = localStorage.getItem('empresa')
    if (emp) {
      try {
        setEmpresa(JSON.parse(emp))
      } catch(e) {
        console.error(e)
      }
    }
  }, [])

  return (
    <div style={{ display: 'flex', minHeight: '100vh', width: '100vw' }}>
      <Sidebar onSelectDashboard={setSelectedDashboardId} activeId={selectedDashboardId} />
      
      <main style={{ flex: 1, padding: '2rem', overflowY: 'auto', background: 'radial-gradient(circle at top right, #1e293b, #0f172a)' }}>
        <header style={{ marginBottom: '2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ fontSize: '2rem', fontWeight: 'bold', background: 'linear-gradient(to right, #60a5fa, #a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              SADE ERP - Tableros Dinámicos
            </h1>
            <p style={{ color: 'var(--text-muted)', marginTop: '0.5rem' }}>
              Sistema "Data-Driven" de Visualización
            </p>
          </div>
          {empresa && (
            <div style={{ background: 'rgba(255,255,255,0.05)', padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid var(--border-color)', color: '#cbd5e1' }}>
              <span style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'block' }}>Compañía Activa</span>
              <strong style={{ color: 'white' }}>{empresa.empresa}</strong>
            </div>
          )}
        </header>

        <div className="glass-panel" style={{ minHeight: 'calc(100vh - 8rem)', padding: '1.5rem' }}>
          {selectedDashboardId ? (
            <DashboardViewer idIndicador={selectedDashboardId} />
          ) : (
            <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
              <h2>Selecciona un indicador en el menú lateral</h2>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/auth-callback" element={<AuthCallback />} />
        <Route path="/" element={
          <AuthGuard>
            <MainApp />
          </AuthGuard>
        } />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  )
}

export default App
