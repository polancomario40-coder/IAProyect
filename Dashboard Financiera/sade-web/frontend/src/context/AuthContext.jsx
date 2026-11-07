import React, { createContext, useContext, useEffect, useState } from 'react'

const TOKEN_KEY = 'jwt_token'
const EMPRESA_KEY = 'empresa'
const USUARIO_KEY = 'usuario'

// Configuración opcional para SSO externo si la empresa lo requiere
export const CLIENT_ID = 'sade-financiera'

const AuthContext = createContext({
  user: null,
  empresa: null,
  token: null,
  isAuthenticated: false,
  loading: true,
  logout: () => {},
  loginWithCredentials: () => {},
  selectEmpresa: () => {},
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

  const loginWithCredentials = (newToken, userData) => {
    localStorage.setItem(TOKEN_KEY, newToken)
    localStorage.setItem(USUARIO_KEY, JSON.stringify(userData))
    setToken(newToken)
    setUser(userData)
  }

  const selectEmpresa = (empresaData) => {
    localStorage.setItem(EMPRESA_KEY, JSON.stringify(empresaData))
    setEmpresa(empresaData)
  }

  const loginDev = (username = 'admin', empresaNombre = 'SADE Financiera Demo') => {
    const dummyToken = 'dev.' + btoa(JSON.stringify({ sub: username, nombre: username })) + '.sig'
    const dummyEmpresa = { idEmpresa: '01', empresa: empresaNombre, rnc: '101-00000-1' }
    loginWithCredentials(dummyToken, { username, nombre: username, roles: ['admin'] })
    selectEmpresa(dummyEmpresa)
  }

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(EMPRESA_KEY)
    localStorage.removeItem(USUARIO_KEY)
    setToken(null)
    setUser(null)
    setEmpresa(null)
  }

  useEffect(() => {
    // Si estamos en la ruta de callback de SSO externo
    if (window.location.pathname === '/auth-callback') {
      setLoading(false)
      return
    }

    const storedToken = localStorage.getItem(TOKEN_KEY)
    const storedEmpresa = localStorage.getItem(EMPRESA_KEY)
    const storedUser = localStorage.getItem(USUARIO_KEY)

    if (storedToken && storedEmpresa) {
      try {
        let parsedUser = null
        if (storedUser) {
          parsedUser = JSON.parse(storedUser)
        } else {
          parsedUser = getUsuarioFromToken(storedToken)
        }
        const parsedEmpresa = JSON.parse(storedEmpresa)
        setToken(storedToken)
        setUser(parsedUser || { username: 'usuario', nombre: 'Usuario' })
        setEmpresa(parsedEmpresa)
        setLoading(false)
        return
      } catch (e) {
        console.error('Error restaurando sesión:', e)
      }
    }

    // Bypass opcional de desarrollo (?dev_auth=1)
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
        loginWithCredentials,
        selectEmpresa,
        loginDev,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
