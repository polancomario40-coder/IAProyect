import React, { createContext, useState, useEffect, useContext } from 'react';


interface User {
  username: string;
  fullName: string;
  email: string;
  nivel: number;
  companyId?: string;
  companyName?: string;
}

function parseJwt(token: string) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/, '/');
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));
    return JSON.parse(jsonPayload);
  } catch (e) {
    return null;
  }
}

interface Company {
  idEmpresa: string;
  empresa: string;
  rnc: string;
  servidor: string;
  baseDatos: string;
  trusted: boolean;
  userId: string;
  activa: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  companies: Company[];
  login: () => void;
  saveSsoData: (token: string, empresaId: string, empresaNombre: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    // Initialize session from localStorage
    const savedToken = localStorage.getItem('sade_token');
    const savedUser = localStorage.getItem('sade_user');
    
    if (savedToken && savedUser) {
      setToken(savedToken);
      setUser(JSON.parse(savedUser));
    }
    setLoading(false);
  }, []);

  const login = React.useCallback(() => {
    const currentUrl = new URL(window.location.href);
    let basePath = currentUrl.pathname;
    if (basePath.endsWith('/login')) {
      basePath = basePath.substring(0, basePath.length - '/login'.length);
    }
    if (basePath.endsWith('/')) {
      basePath = basePath.substring(0, basePath.length - 1);
    }
    const redirectUri = currentUrl.origin + basePath + '/auth-callback';
    
    // Utilizar la URL de producción si estamos en IIS (no en localhost), o una URL configurable.
    const isDev = window.location.hostname === 'localhost';
    const authUrl = isDev ? 'http://localhost:5174/' : 'https://auth.sade.com.do/';
    window.location.href = `${authUrl}?client_id=seg-sade&redirect_uri=${encodeURIComponent(redirectUri)}`;
  }, []);

  const saveSsoData = React.useCallback((receivedToken: string, empresaId: string, empresaNombre: string) => {
    localStorage.setItem('sade_token', receivedToken);
    
    // Decode token to get user info
    const payload = parseJwt(receivedToken);
    const username = payload?.sub || payload?.['http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier'] || 'Usuario';
    const fullName = payload?.['http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name'] || username;
    const nivel = parseInt(payload?.['http://schemas.microsoft.com/ws/2008/06/identity/claims/role'] || '3', 10);
    const email = payload?.['http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress'] || '';

    const loggedUser: User = { 
      username, 
      fullName, 
      email, 
      nivel,
      companyId: empresaId,
      companyName: empresaNombre
    };
    
    localStorage.setItem('sade_user', JSON.stringify(loggedUser));
    
    setToken(receivedToken);
    setUser(loggedUser);
  }, []);

  const logout = React.useCallback(() => {
    localStorage.removeItem('sade_token');
    localStorage.removeItem('sade_user');
    setToken(null);
    setUser(null);
    setCompanies([]);
  }, []);

  return (
    <AuthContext.Provider value={{
      user,
      token,
      loading,
      companies,
      login,
      saveSsoData,
      logout
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth debe ser usado dentro de un AuthProvider');
  }
  return context;
};
