import { useState, useEffect } from 'react';
import DashboardView from './views/DashboardView';
import AuthCallback from './views/AuthCallback';

export default function App() {
  const [path, setPath] = useState(window.location.pathname);

  useEffect(() => {
    const handleLocationChange = () => {
      setPath(window.location.pathname);
    };
    window.addEventListener('popstate', handleLocationChange);
    return () => window.removeEventListener('popstate', handleLocationChange);
  }, []);

  const navigate = (to: string) => {
    window.history.pushState({}, '', to);
    setPath(to);
  };

  // Route Guards
  const token = localStorage.getItem('jwt_token');
  const empresa = localStorage.getItem('empresa');

  if (path === '/auth-callback') {
    return <AuthCallback navigate={navigate} />;
  }

  if (!token || !empresa) {
    // Redirect to Auth Center SSO
    const callbackUrl = window.location.origin + '/auth-callback';
    window.location.href = `https://auth.sade.com.do/?client_id=cuadre-caja&redirect_uri=${encodeURIComponent(callbackUrl)}`;
    
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', flexDirection: 'column', gap: '1rem', color: '#94a3b8' }}>
        <div className="spinner" style={{ width: '45px', height: '45px', borderLeftColor: '#60a5fa' }}></div>
        <p style={{ fontFamily: 'Outfit, sans-serif', fontWeight: 500, letterSpacing: '0.05em' }}>
          Redirigiendo al Portal de Autenticación Central...
        </p>
      </div>
    );
  }

  return <DashboardView />;
}
