import { BrowserRouter, Routes, Route, NavLink, Navigate, useNavigate, useLocation } from 'react-router-dom'
import { LayoutDashboard, CreditCard, Menu, X, Users, FileSpreadsheet, LogOut, Building2, User, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import Dashboard from './pages/Dashboard'
import LoanDetail from './pages/LoanDetail'
import Clientes from './pages/Clientes'
import Reportes from './pages/Reportes'
import AuthCallback from './pages/AuthCallback'
import LoginPage from './pages/LoginPage'
import { AuthProvider, useAuth } from './context/AuthContext'

function Sidebar({ open, onClose }) {
  const navigate = useNavigate()
  const { user, empresa, logout } = useAuth()
  const navItem =
    'flex items-center gap-3 px-4 py-3 rounded-lg text-slate-300 hover:bg-white/10 hover:text-white transition-colors text-sm font-medium'
  const activeClass = 'bg-white/20 text-white'

  return (
    <>
      {/* Overlay móvil */}
      {open && (
        <div
          className="fixed inset-0 bg-black/50 z-20 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`
          fixed top-0 left-0 h-screen w-64 bg-[#1e3a5f] flex flex-col z-30
          transform transition-transform duration-300
          ${open ? 'translate-x-0' : '-translate-x-full'}
          lg:translate-x-0 lg:static lg:h-screen shadow-xl
        `}
      >
        {/* Logo */}
        <div className="px-6 py-5 border-b border-white/10">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-white font-bold text-lg leading-none flex items-center gap-2">
                <span>SADE Web</span>
                <span className="text-[10px] font-normal px-1.5 py-0.5 bg-blue-500/30 text-blue-200 rounded border border-blue-400/30">SSO</span>
              </h1>
              <p className="text-blue-300 text-xs mt-1">Cartera de Préstamos</p>
            </div>
            <button
              onClick={onClose}
              className="lg:hidden text-slate-400 hover:text-white p-1"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Info de Usuario y Empresa */}
        <div className="px-4 py-3 bg-black/15 border-b border-white/10">
          <div className="flex items-center gap-2.5 text-xs text-slate-300 mb-1.5">
            <Building2 size={14} className="text-blue-400 shrink-0" />
            <span className="font-semibold text-white truncate" title={empresa?.empresa || 'Empresa'}>
              {empresa?.empresa || 'SADE Principal'}
            </span>
          </div>
          <div className="flex items-center justify-between text-[11px] text-slate-400">
            <div className="flex items-center gap-1.5 truncate">
              <User size={13} className="text-emerald-400 shrink-0" />
              <span className="truncate">{user?.nombre || user?.username || 'Usuario'}</span>
            </div>
            {empresa?.rnc && <span className="text-[10px] text-slate-400 font-mono">RNC: {empresa.rnc}</span>}
          </div>
        </div>

        {/* Navegación */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          <NavLink
            to="/dashboard"
            className={({ isActive }) => `${navItem} ${isActive ? activeClass : ''}`}
            onClick={onClose}
          >
            <LayoutDashboard size={18} />
            Dashboard
          </NavLink>
          <NavLink
            to="/clientes"
            className={({ isActive }) => `${navItem} ${isActive ? activeClass : ''}`}
            onClick={onClose}
          >
            <Users size={18} />
            Clientes
          </NavLink>
          <NavLink
            to="/reportes"
            className={({ isActive }) => `${navItem} ${isActive ? activeClass : ''}`}
            onClick={onClose}
          >
            <FileSpreadsheet size={18} />
            Informes
          </NavLink>
          <NavLink
            to="/prestamos/17481"
            className={({ isActive }) => `${navItem} ${isActive ? activeClass : ''}`}
            onClick={onClose}
          >
            <CreditCard size={18} />
            Estado Préstamo
          </NavLink>

          {/* Buscador rápido en Sidebar */}
          <div className="pt-2 px-1">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                const val = e.currentTarget.elements.quickLoan.value.trim()
                if (val) {
                  navigate(`/prestamos/${val}`)
                  e.currentTarget.reset()
                  onClose()
                }
              }}
              className="relative"
            >
              <input
                name="quickLoan"
                type="text"
                placeholder="Ir a Préstamo #..."
                className="w-full bg-slate-800/80 text-white placeholder-slate-400 text-xs px-3 py-2 rounded-lg border border-slate-700 focus:outline-none focus:border-blue-400 font-mono"
              />
              <button
                type="submit"
                className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white px-1.5 py-0.5 text-[10px] bg-slate-700 rounded font-sans"
              >
                ↵
              </button>
            </form>
          </div>
        </nav>

        {/* Footer con Botón Salir */}
        <div className="p-3 border-t border-white/10 space-y-2">
          <button
            onClick={logout}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium text-rose-300 hover:text-white bg-rose-500/10 hover:bg-rose-600 rounded-lg transition-colors border border-rose-500/30"
          >
            <LogOut size={14} />
            Cerrar Sesión
          </button>
          <p className="text-slate-400 text-[11px] text-center">ERP SADE — Financiera</p>
        </div>
      </aside>
    </>
  )
}

function AuthGuard({ children }) {
  const { isAuthenticated, loading, redirectToLogin, loginDev } = useAuth()
  const location = useLocation()

  // Si estamos en la ruta de retorno de auth, dejamos pasar directamente
  if (location.pathname === '/auth-callback') {
    return children
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-[#0f172a] text-slate-300 gap-4">
        <div className="w-12 h-12 rounded-full border-4 border-slate-700 border-t-blue-500 animate-spin" />
        <p className="text-sm font-medium tracking-wide">Verificando credenciales de acceso...</p>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <LoginPage />
  }

  return children
}

function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { user, logout } = useAuth()

  return (
    <div className="flex h-screen overflow-hidden bg-slate-100">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Contenido principal */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Topbar móvil */}
        <header className="lg:hidden flex items-center justify-between px-4 py-3 bg-white border-b border-slate-200">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="text-slate-600 hover:text-slate-900 p-1"
            >
              <Menu size={22} />
            </button>
            <span className="font-semibold text-slate-800">SADE Web</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 truncate max-w-[120px]">{user?.nombre || user?.username}</span>
            <button
              onClick={logout}
              className="p-1.5 text-rose-500 hover:bg-rose-50 rounded"
              title="Cerrar Sesión"
            >
              <LogOut size={16} />
            </button>
          </div>
        </header>

        {/* Rutas */}
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/clientes" element={<Clientes />} />
            <Route path="/reportes" element={<Reportes />} />
            <Route path="/prestamos/:idCxc" element={<LoanDetail />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AuthGuard>
          <Routes>
            <Route path="/auth-callback" element={<AuthCallback />} />
            <Route path="/*" element={<MainLayout />} />
          </Routes>
        </AuthGuard>
      </AuthProvider>
    </BrowserRouter>
  )
}
