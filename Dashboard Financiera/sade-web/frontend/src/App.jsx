import { BrowserRouter, Routes, Route, NavLink, Navigate, useNavigate } from 'react-router-dom'
import { LayoutDashboard, CreditCard, Menu, X, Users } from 'lucide-react'
import { useState } from 'react'
import Dashboard from './pages/Dashboard'
import LoanDetail from './pages/LoanDetail'
import Clientes from './pages/Clientes'

function Sidebar({ open, onClose }) {
  const navigate = useNavigate()
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
          lg:translate-x-0 lg:static lg:h-screen
        `}
      >
        {/* Logo */}
        <div className="px-6 py-5 border-b border-white/10">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-white font-bold text-lg leading-none">SADE Web</h1>
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

        {/* Footer */}
        <div className="px-6 py-4 border-t border-white/10">
          <p className="text-slate-500 text-xs">ERP SADE — Financiera</p>
        </div>
      </aside>
    </>
  )
}

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden bg-slate-100">
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

        {/* Contenido principal */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Topbar móvil */}
          <header className="lg:hidden flex items-center gap-3 px-4 py-3 bg-white border-b border-slate-200">
            <button
              onClick={() => setSidebarOpen(true)}
              className="text-slate-600 hover:text-slate-900 p-1"
            >
              <Menu size={22} />
            </button>
            <span className="font-semibold text-slate-800">SADE Web</span>
          </header>

          {/* Rutas */}
          <main className="flex-1 overflow-y-auto">
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/clientes" element={<Clientes />} />
              <Route path="/prestamos/:idCxc" element={<LoanDetail />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  )
}
