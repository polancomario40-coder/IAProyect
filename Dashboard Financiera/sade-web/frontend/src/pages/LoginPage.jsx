import { useState } from 'react'
import { ShieldCheck, Building2, LogIn, AlertCircle } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const { loginWithCredentials, selectEmpresa } = useAuth()
  const [step, setStep] = useState('login') // 'login' | 'empresa'
  const [usuario, setUsuario] = useState('')
  const [clave, setClave] = useState('')
  const [empresas, setEmpresas] = useState([])
  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState(null)

  const handleLogin = async (e) => {
    e.preventDefault()
    if (!usuario.trim()) {
      setErrorMsg('Debe ingresar su usuario.')
      return
    }
    if (!clave) {
      setErrorMsg('Debe ingresar su contraseña.')
      return
    }

    setLoading(true)
    setErrorMsg(null)

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ usuario: usuario.trim(), clave: clave.trim() }),
      })

      const data = await res.json()

      if (!res.ok || !data.success) {
        throw new Error(data.detail || data.mensaje || 'Usuario o contraseña incorrectos.')
      }

      loginWithCredentials(data.token, data.usuario)

      if (data.empresas && data.empresas.length === 1) {
        selectEmpresa(data.empresas[0])
      } else if (data.empresas && data.empresas.length > 1) {
        setEmpresas(data.empresas)
        setStep('empresa')
      } else {
        selectEmpresa({ idEmpresa: '01', empresa: 'SADE Financiera', rnc: '' })
      }
    } catch (err) {
      console.error('Error de login:', err)
      setErrorMsg(err.message || 'Error al conectar con el servidor.')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectEmpresa = (emp) => {
    selectEmpresa(emp)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0f172a] via-[#1e293b] to-[#0f172a] flex items-center justify-center p-4">
      <div className="bg-slate-900/90 border border-slate-700/80 rounded-2xl p-8 max-w-md w-full shadow-2xl backdrop-blur-md">
        {/* Header con Logo */}
        <div className="text-center mb-6">
          <div className="w-16 h-16 bg-blue-500/10 border border-blue-500/30 rounded-2xl flex items-center justify-center mx-auto mb-4 text-blue-400">
            <ShieldCheck size={36} />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">SADE Web</h1>
          <p className="text-xs text-blue-300 mt-1">Cartera de Préstamos • Centro de Seguridad</p>
        </div>

        {/* Mensaje de Error */}
        {errorMsg && (
          <div className="mb-5 p-3.5 bg-rose-500/15 border border-rose-500/30 rounded-xl flex items-start gap-3 text-rose-300 text-xs leading-relaxed animate-in fade-in duration-200">
            <AlertCircle size={16} className="shrink-0 mt-0.5" />
            <span>{errorMsg}</span>
          </div>
        )}

        {step === 'login' ? (
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Usuario del Sistema
              </label>
              <input
                type="text"
                value={usuario}
                onChange={(e) => setUsuario(e.target.value)}
                placeholder="Ingrese su usuario SADE"
                className="w-full bg-slate-800/90 text-white placeholder-slate-500 text-sm px-3.5 py-2.5 rounded-xl border border-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
                autoCapitalize="none"
                autoComplete="username"
                disabled={loading}
                required
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Contraseña
              </label>
              <input
                type="password"
                value={clave}
                onChange={(e) => setClave(e.target.value)}
                placeholder="Ingrese su contraseña"
                className="w-full bg-slate-800/90 text-white placeholder-slate-500 text-sm px-3.5 py-2.5 rounded-xl border border-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-colors"
                autoComplete="current-password"
                disabled={loading}
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 flex items-center justify-center gap-2 py-3 px-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-semibold text-sm rounded-xl shadow-lg shadow-blue-600/30 transition duration-150 disabled:opacity-50"
            >
              {loading ? (
                <div className="w-5 h-5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
              ) : (
                <>
                  <LogIn size={16} />
                  <span>Ingresar al Portal</span>
                </>
              )}
            </button>
          </form>
        ) : (
          <div>
            <div className="text-center mb-4">
              <h2 className="text-lg font-semibold text-white">Empresas Asignadas</h2>
              <p className="text-xs text-slate-400">Seleccione su espacio de trabajo</p>
            </div>

            <div className="space-y-2.5 max-h-60 overflow-y-auto pr-1 mb-5">
              {empresas.map((emp) => (
                <button
                  key={emp.idEmpresa}
                  type="button"
                  onClick={() => handleSelectEmpresa(emp)}
                  className="w-full text-left p-3.5 rounded-xl bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 hover:border-blue-500/50 transition-all flex items-start gap-3 group"
                >
                  <Building2 size={18} className="text-blue-400 mt-0.5 shrink-0 group-hover:scale-110 transition-transform" />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-white truncate">{emp.empresa}</div>
                    {emp.rnc && <div className="text-[11px] text-slate-400 font-mono">RNC: {emp.rnc}</div>}
                  </div>
                </button>
              ))}
            </div>

            <button
              type="button"
              onClick={() => setStep('login')}
              className="w-full py-2.5 text-xs text-slate-400 hover:text-white bg-slate-800 rounded-xl border border-slate-700"
            >
              ← Volver al login
            </button>
          </div>
        )}

        {/* Footer */}
        <div className="mt-6 pt-4 border-t border-slate-700/50 text-center">
          <p className="text-[11px] text-slate-500">
            SADE Web • Autenticación Segura Integrada
          </p>
        </div>
      </div>
    </div>
  )
}
