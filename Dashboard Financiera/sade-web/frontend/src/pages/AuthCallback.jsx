import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AUTH_CENTER_URL, CLIENT_ID } from '../context/AuthContext'

export default function AuthCallback() {
  const [status, setStatus] = useState('Procesando credenciales de acceso...')
  const navigate = useNavigate()

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('token')
    const empresaId = params.get('empresaId')
    const empresaNombre = params.get('empresaNombre')
    const empresaRNC = params.get('empresaRNC')

    let timeoutId = null

    if (token && empresaId) {
      try {
        localStorage.setItem('jwt_token', token)
        localStorage.setItem(
          'empresa',
          JSON.stringify({
            idEmpresa: empresaId,
            empresa: empresaNombre || 'Empresa Seleccionada',
            rnc: empresaRNC || '',
          })
        )

        // Limpiar parámetros de la URL visible
        window.history.replaceState({}, document.title, '/')

        setStatus('¡Sesión establecida con éxito! Redirigiendo a SADE Web...')
        timeoutId = setTimeout(() => {
          navigate('/dashboard', { replace: true })
        }, 600)
      } catch (e) {
        console.error('Error guardando credenciales:', e)
        setStatus('Error al guardar la sesión.')
      }
    } else {
      // Si ya existía sesión
      const existingToken = localStorage.getItem('jwt_token')
      const existingEmpresa = localStorage.getItem('empresa')

      if (existingToken && existingEmpresa) {
        setStatus('¡Sesión activa detectada! Redirigiendo...')
        timeoutId = setTimeout(() => {
          navigate('/dashboard', { replace: true })
        }, 400)
      } else {
        setStatus('Credenciales no recibidas o expiradas. Redirigiendo al login central...')
        timeoutId = setTimeout(() => {
          const redirectUri = encodeURIComponent(window.location.origin + '/auth-callback')
          window.location.href = `${AUTH_CENTER_URL}/?client_id=${CLIENT_ID}&redirect_uri=${redirectUri}`
        }, 1500)
      }
    }

    return () => {
      if (timeoutId) clearTimeout(timeoutId)
    }
  }, [navigate])

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-[#0f172a] text-white p-6 font-sans">
      <div className="bg-[#1e293b]/80 border border-slate-700/80 rounded-2xl p-8 max-w-md w-full shadow-2xl flex flex-col items-center text-center">
        {/* Spinner */}
        <div className="w-12 h-12 rounded-full border-4 border-slate-700 border-t-blue-500 animate-spin mb-6" />

        <h2 className="text-xl font-bold tracking-tight text-white mb-2">Autenticación SADE</h2>
        <p className="text-sm text-slate-300 leading-relaxed">{status}</p>

        <div className="mt-6 pt-4 border-t border-slate-700/50 w-full text-xs text-slate-500">
          Centro de Autenticación Unificado
        </div>
      </div>
    </div>
  )
}
