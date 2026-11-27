import React, { useState, useEffect } from 'react'
import { ShieldAlert, KeyRound, AlertTriangle, CheckCircle2, Lock, Clock, ExternalLink } from 'lucide-react'

export default function LicenseModal() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [codigo, setCodigo] = useState('')
  const [activando, setActivando] = useState(false)
  const [mensajeExito, setMensajeExito] = useState(null)
  const [mensajeError, setMensajeError] = useState(null)
  const [cerradoTemporal, setCerradoTemporal] = useState(false)

  // Consultar estado de licencia al montar
  const fetchStatus = async () => {
    try {
      setLoading(true)
      const res = await fetch('/api/license/status')
      if (res.ok) {
        const data = await res.json()
        setStatus(data)
      }
    } catch (e) {
      console.warn('No se pudo verificar estado de licencia:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
  }, [])

  const handleActivar = async (e) => {
    e.preventDefault()
    if (!codigo.trim()) {
      setMensajeError('Debe ingresar un código de activación.')
      return
    }

    setActivando(true)
    setMensajeError(null)
    setMensajeExito(null)

    try {
      const res = await fetch('/api/license/activate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ codigo: codigo.trim() }),
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || 'Código de activación inválido.')
      }

      setMensajeExito(data.mensaje)
      setCodigo('')
      // Re-verificar estado
      setTimeout(() => {
        fetchStatus()
        setCerradoTemporal(true)
      }, 1500)
    } catch (err) {
      setMensajeError(err.message || 'Error al validar el código.')
    } finally {
      setActivando(false)
    }
  }

  if (loading || !status) return null

  // Si está en fase silenciosa o licencia permanente activa
  if (status.fase === 'SILENT' || status.fase === 'ACTIVE_PERMANENT' || (status.activado && status.fase === 'ACTIVE')) {
    return null
  }

  // Si el usuario cerró temporalmente en fases no bloqueantes (Ámbar o Rojo)
  if (cerradoTemporal && !status.bloqueado) {
    return null
  }

  const isExpired = status.bloqueado || status.fase === 'EXPIRED'
  const isRed = status.fase === 'WARNING_RED'
  const isAmber = status.fase === 'WARNING_AMBER'

  // =========================================================================
  // 1. FASE DE BLOQUEO TOTAL (VENTANA EN NEGRO - DÍA 15+)
  // =========================================================================
  if (isExpired) {
    return (
      <div className="fixed inset-0 bg-black/95 backdrop-blur-md z-[9999] flex items-center justify-center p-4">
        <div className="bg-[#0b101b] border-2 border-red-600/80 rounded-2xl max-w-lg w-full p-8 shadow-2xl text-center text-white relative overflow-hidden animate-in fade-in zoom-in-95 duration-200">
          
          {/* Luz de advertencia */}
          <div className="absolute -top-12 -left-12 w-36 h-36 bg-red-600/20 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute -bottom-12 -right-12 w-36 h-36 bg-red-600/20 rounded-full blur-3xl pointer-events-none" />

          {/* Ícono de candado bloqueado */}
          <div className="w-20 h-20 bg-red-950/80 border-2 border-red-500/80 text-red-500 rounded-full flex items-center justify-center mx-auto mb-5 shadow-lg shadow-red-950/50">
            <Lock size={38} className="animate-pulse" />
          </div>

          <h2 className="text-2xl font-black tracking-wide text-white mb-2 uppercase">
            Sistema Bloqueado por Licencia
          </h2>

          <div className="bg-red-950/40 border border-red-800/60 rounded-xl p-3.5 mb-5 text-left text-xs text-red-200 leading-relaxed">
            <p className="font-semibold text-red-100 mb-1 flex items-center gap-1.5">
              <ShieldAlert size={14} className="text-red-400" />
              Período de gracia finalizado
            </p>
            <p>
              El acceso a <strong>SADE Web</strong> se encuentra temporalmente suspendido. Para desbloquear el sistema y continuar utilizando los módulos financieros, ingrese el código de activación oficial provisto por su proveedor.
            </p>
          </div>

          <form onSubmit={handleActivar} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 text-left mb-1.5 uppercase tracking-wider">
                Código de Activación Oficial:
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={codigo}
                  onChange={(e) => setCodigo(e.target.value.toUpperCase())}
                  placeholder="SADE-XXXX-XXXXXXXX-XXXX"
                  disabled={activando}
                  className="w-full bg-slate-900/90 border-2 border-slate-700 text-white font-mono text-sm px-4 py-3 rounded-xl focus:outline-none focus:border-red-500 transition-colors uppercase tracking-widest placeholder:text-slate-600 text-center"
                />
                <KeyRound size={16} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
              </div>
            </div>

            {mensajeError && (
              <div className="p-3 bg-red-900/40 border border-red-700 rounded-xl text-red-200 text-xs font-medium text-left flex items-center gap-2">
                <AlertTriangle size={15} className="text-red-400 shrink-0" />
                <span>{mensajeError}</span>
              </div>
            )}

            {mensajeExito && (
              <div className="p-3 bg-emerald-900/40 border border-emerald-600 rounded-xl text-emerald-200 text-xs font-semibold text-left flex items-center gap-2">
                <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
                <span>{mensajeExito}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={activando}
              className="w-full bg-gradient-to-r from-red-600 to-rose-700 hover:from-red-500 hover:to-rose-600 text-white font-bold py-3.5 px-4 rounded-xl shadow-lg transition-all duration-150 text-sm flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {activando ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Validando Código...</span>
                </>
              ) : (
                <>
                  <KeyRound size={16} />
                  <span>Desbloquear y Activar Sistema</span>
                </>
              )}
            </button>
          </form>

          <p className="text-[11px] text-slate-500 mt-5">
            SADE Web — Sistema de Gestión Financiera &copy; 2026
          </p>
        </div>
      </div>
    )
  }

  // =========================================================================
  // 2. FASES DE AVISO PREVENTIVO (ÁMBAR DÍAS 5-10 / ROJO DÍAS 10-15)
  // =========================================================================
  const themeBg = isRed ? 'bg-red-50 border-red-300' : 'bg-amber-50 border-amber-300'
  const themeCardBorder = isRed ? 'border-red-500' : 'border-amber-500'
  const themeIconColor = isRed ? 'bg-red-100 text-red-600 border-red-300' : 'bg-amber-100 text-amber-700 border-amber-300'
  const themeBtnColor = isRed 
    ? 'bg-red-600 hover:bg-red-700 text-white' 
    : 'bg-amber-600 hover:bg-amber-700 text-white'

  return (
    <div className="fixed inset-0 bg-slate-900/70 backdrop-blur-sm z-[9999] flex items-center justify-center p-4">
      <div className={`bg-white border-2 ${themeCardBorder} rounded-2xl max-w-xl w-full p-6 lg:p-8 shadow-2xl relative overflow-hidden animate-in fade-in zoom-in-95 duration-150`}>
        
        {/* Cabecera */}
        <div className="flex items-start gap-4 mb-5">
          <div className={`w-14 h-14 ${themeIconColor} border-2 rounded-2xl flex items-center justify-center shrink-0`}>
            {isRed ? <AlertTriangle size={30} className="animate-bounce" /> : <Clock size={30} />}
          </div>

          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className={`text-[11px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full border ${isRed ? 'bg-red-100 text-red-800 border-red-200' : 'bg-amber-100 text-amber-900 border-amber-200'}`}>
                {isRed ? 'Vencimiento Inminente' : 'Aviso de Licencia'}
              </span>
              <span className="text-xs text-slate-500 font-mono">
                {status.diasRestantes} día(s) restante(s)
              </span>
            </div>

            <h3 className={`text-xl font-bold leading-tight ${isRed ? 'text-red-950' : 'text-slate-900'}`}>
              {isRed ? '¡Atención: Licencia a Punto de Expirar!' : 'Aviso de Vencimiento de Licencia'}
            </h3>
          </div>
        </div>

        {/* Mensaje principal */}
        <div className={`p-4 rounded-xl border mb-5 text-xs ${themeBg} leading-relaxed font-medium`}>
          <p className="mb-2">
            {status.mensaje}
          </p>
          <p className="text-[11px] text-slate-600">
            {isRed 
              ? 'Transcurridos los 15 días, el sistema entrará en bloqueo total y no permitirá realizar consultas ni descargas.'
              : 'Puede ingresar el código suministrado por su proveedor ahora o continuar temporalmente.'}
          </p>
        </div>

        {/* Formulario de activación */}
        <form onSubmit={handleActivar} className="space-y-3.5 mb-5">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Ingrese su Código de Activación:
            </label>
            <div className="relative">
              <input
                type="text"
                value={codigo}
                onChange={(e) => setCodigo(e.target.value.toUpperCase())}
                placeholder="Ejemplo: SADE-1Y-20271127-XXXXXX"
                disabled={activando}
                className="w-full bg-slate-50 border border-slate-300 text-slate-900 font-mono text-xs px-3.5 py-2.5 rounded-xl focus:outline-none focus:border-blue-500 transition-colors uppercase tracking-wider"
              />
              <KeyRound size={15} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>

          {mensajeError && (
            <div className="p-2.5 bg-red-100 border border-red-300 rounded-lg text-red-900 text-xs flex items-center gap-2">
              <AlertTriangle size={14} className="text-red-600 shrink-0" />
              <span>{mensajeError}</span>
            </div>
          )}

          {mensajeExito && (
            <div className="p-2.5 bg-emerald-100 border border-emerald-300 rounded-lg text-emerald-900 text-xs font-semibold flex items-center gap-2">
              <CheckCircle2 size={15} className="text-emerald-600 shrink-0" />
              <span>{mensajeExito}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={activando || !codigo.trim()}
            className={`w-full ${themeBtnColor} font-bold py-2.5 px-4 rounded-xl shadow transition-colors text-xs flex items-center justify-center gap-2 disabled:opacity-50`}
          >
            {activando ? 'Validando...' : 'Activar Licencia Ahora'}
          </button>
        </form>

        {/* Botón continuar / postergar */}
        <div className="pt-3 border-t border-slate-200 flex items-center justify-between">
          <span className="text-[11px] text-slate-400">
            Corte: {status.expiraEn}
          </span>
          <button
            type="button"
            onClick={() => setCerradoTemporal(true)}
            className="px-4 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors"
          >
            {isRed ? 'Continuar (Riesgo de bloqueo)' : 'Entendido, Continuar al Sistema'}
          </button>
        </div>

      </div>
    </div>
  )
}
