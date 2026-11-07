import React, { createContext, useContext, useEffect, useState } from 'react'

const TOKEN_KEY = 'jwt_token'
const EMPRESA_KEY = 'empresa'
const USUARIO_KEY = 'usuario'

// URL del Centro de Autenticación SSO
// En producción: https://auth.sade.com.do (o la URL configurada en .env o window.__ENV__)
// En desarrollo: http://localhost:5174 con fallback a la URL central
export const AUTH_CENTER_URL =
  import.meta.env.VITE_AUTH_CENTER_URL ||
  (typeof window !== 'undefined' && window.__ENV__?.VITE_AUTH_CENTER_URL) ||
  'https://auth.sade.com.do'

export const CLIENT_ID = 'sade-financiera'

const AuthContext = createContext({
  user: null,
  empresa: null,
  token: null,
  isAuthenticated: false,
  loading: true,
  logout: () => {},
  redirectToLogin: () => {},
  loginDev: () => {},
})

export const getUsuarioFromToken = (token) => {
  if (!token) return null
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return {
      username: payload['idSegUserGrp'] || payload['sub'] || payload['unique_name'] || 'usuario',
      nombre: payload['nombre'] || payload['name'] || payload['unique_name'] || payload['sub'] || 'Usuario',
      roles: payload['role'] ? (Array.isArray(payload['role']) ? payload['role'] : [payload['role']]) : [],
    }
  } catch {
    return null
  }
}

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(null)
  const [user, setUser] = useState(null)
  const [empresa, setEmpresa] = useState(null)
  const [loading, setLoading] = useState(true)

  const redirectToLogin = (isLogout = false) => {
    const callbackUrl = encodeURIComponent(window.location.origin + '/auth-callback')
    const logoutParam = isLogout ? '&logout=true' : ''
    window.location.href = `${AUTH_CENTER_URL}/?client_id=${CLIENT_ID}&redirect_uri=${callbackUrl}${logoutParam}`
  }

  // Permite iniciar sesión simulada para entornos locales de desarrollo si el auth local no está corriendo
  const loginDev = (username = 'admin', empresaNombre = 'Empresa Principal') => {
    const dummyToken = 'dev.' + btoa(JSON.stringify({ sub: username, nombre: username })) + '.sig'
    const dummyEmpresa = { idEmpresa: '01', empresa: empresaNombre, rnc: '101-00000-1' }
    localStorage.setItem(TOKEN_KEY, dummyToken)
    localStorage.setItem(EMPRESA_KEY, JSON.stringify(dummyEmpresa))
    localStorage.setItem(USUARIO_KEY, JSON.stringify({ username, nombre: username }))
    setToken(dummyToken)
    setUser({ username, nombre: username, roles: ['admin'] })
    setEmpresa(dummyEmpresa)
  }

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(EMPRESA_KEY)
    localStorage.removeItem(USUARIO_KEY)
    setToken(null)
    setUser(null)
    setEmpresa(null)
    redirectToLogin(true)
  }

  useEffect(() => {
    // Si estamos en la ruta de callback de SSO, no redirigir
    if (window.location.pathname === '/auth-callback') {
      setLoading(false)
      return
    }

    const storedToken = localStorage.getItem(TOKEN_KEY)
    const storedEmpresa = localStorage.getItem(EMPRESA_KEY)

    if (storedToken && storedEmpresa) {
      try {
        const decodedUser = getUsuarioFromToken(storedToken)
        const parsedEmpresa = JSON.parse(storedEmpresa)
        setToken(storedToken)
        setUser(decodedUser || { username: 'usuario', nombre: 'Usuario' })
        setEmpresa(parsedEmpresa)
        setLoading(false)
        return
      } catch (e) {
        console.error('Error restaurando sesión:', e)
      }
    }

    // Si no hay sesión válida, verificar parámetro de bypass opcional (?dev_auth=1)
    const params = new URLSearchParams(window.location.search)
    if (params.get('dev_auth') === '1') {
      loginDev()
      setLoading(false)
      return
    }

    setLoading(false)
  }, [])

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        empresa,
        isAuthenticated: !!token && !!empresa,
        loading,
        logout,
        redirectToLogin,
        loginDev,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
