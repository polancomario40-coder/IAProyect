import React, { createContext, useContext, useEffect, useState } from 'react';
import { getToken, getUsuario, clearToken } from '../services/puertaApi';

const AUTH_CENTER = import.meta.env.VITE_AUTH_CENTER_URL || 'http://localhost:5174';
const CLIENT_ID   = 'control-puerta';

interface AuthUser {
  username: string;
  nombre: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  roles: string[];
  isAuthenticated: boolean;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  token: null,
  roles: [],
  isAuthenticated: false,
  logout: () => {},
});

/**
 * AuthProvider
 * - Al montar: busca el token en localStorage (puesto por auth-center SSO).
 * - Si no hay token válido → redirige a auth-center con client_id y redirect_uri.
 */
export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser]           = useState<AuthUser | null>(null);
  const [token, setTokenState]    = useState<string | null>(null);
  const [roles, setRoles]         = useState<string[]>([]);
  const [loading, setLoading]     = useState(true);

  const redirectToLogin = () => {
    const redirectUri = encodeURIComponent(window.location.origin + '/auth-callback');
    const apiUrl = encodeURIComponent(import.meta.env.VITE_API_URL || '/api');
    window.location.href = `${AUTH_CENTER}/?client_id=${CLIENT_ID}&redirect_uri=${redirectUri}&api_url=${apiUrl}`;
  };

  useEffect(() => {
    // Saltar la verificación si estamos en la ruta /auth-callback
    if (window.location.pathname === '/auth-callback') {
      setLoading(false);
      return;
    }

    // Leer token de localStorage (guardado por AuthCallback después del SSO)
    const stored = getToken();
    if (stored) {
      const decoded = getUsuario();
      if (decoded) {
        setTokenState(stored);
        setUser(decoded);
        
        // Fetch roles using getMe
        import('../services/puertaApi').then(({ getMe }) => {
          getMe()
            .then(res => {
              if (res.data?.success && res.data.roles) {
                setRoles(res.data.roles.map((r: string) => r.toLowerCase()));
              }
            })
            .catch(err => console.error('Error fetching roles', err))
            .finally(() => setLoading(false));
        });
        return;
      }
    }

    // Sin token válido → ir al login central
    redirectToLogin();
  }, []);

  const logout = () => {
    clearToken();
    localStorage.removeItem('empresa');
    setUser(null);
    setTokenState(null);
    redirectToLogin();
  };

  if (loading) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100vh', background: '#080C14', color: '#F3F4F6',
        fontFamily: 'Outfit, sans-serif', flexDirection: 'column', gap: 16
      }}>
        <div style={{
          width: 50, height: 50, borderRadius: '50%',
          border: '4px solid #1e293b',
          borderLeftColor: '#10b981',
          animation: 'spin 0.8s linear infinite'
        }} />
        <p style={{ margin: 0, color: '#94a3b8' }}>Verificando sesión...</p>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ user, token, roles, isAuthenticated: !!user, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
