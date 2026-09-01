import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const AUTH_CENTER = import.meta.env.VITE_AUTH_CENTER_URL || 'http://localhost:5174';

export default function AuthCallback() {
  const [status, setStatus] = useState('Procesando credenciales...');
  const navigate = useNavigate();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token       = params.get('token');
    const empresaId   = params.get('empresaId');
    const empresaNombre = params.get('empresaNombre');
    const empresaRNC  = params.get('empresaRNC');

    let timeoutId: any = null;

    if (token && empresaId) {
      try {
        localStorage.setItem('jwt_token', token);
        localStorage.setItem('empresa', JSON.stringify({
          idEmpresa: empresaId,
          empresa: empresaNombre || 'Empresa',
          rnc: empresaRNC || ''
        }));

        setStatus('¡Sesión establecida! Redirigiendo...');
        
        timeoutId = setTimeout(() => {
          window.location.href = '/';
        }, 800);
      } catch (e) {
        console.error('Error guardando sesión', e);
        setStatus('Error al guardar la sesión.');
      }
    } else {
      // Verificar si ya hay sesión activa
      const existingToken   = localStorage.getItem('jwt_token');
      const existingEmpresa = localStorage.getItem('empresa');

      if (existingToken && existingEmpresa) {
        setStatus('¡Sesión activa! Redirigiendo...');
        window.location.href = '/';
      } else {
        setStatus('Credenciales no recibidas. Volviendo al login...');
        timeoutId = setTimeout(() => {
          const redirectUri = encodeURIComponent(window.location.origin + '/auth-callback');
          window.location.href = `${AUTH_CENTER}/?client_id=control-puerta&redirect_uri=${redirectUri}`;
        }, 2000);
      }
    }

    return () => { if (timeoutId) clearTimeout(timeoutId); };
  }, [navigate]);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'center',
      height: '100vh',
      gap: '1.5rem',
      backgroundColor: '#0f172a',
      color: '#fff',
      fontFamily: 'Outfit, sans-serif'
    }}>
      <div style={{
        width: 50, height: 50, borderRadius: '50%',
        border: '4px solid #1e293b',
        borderLeftColor: '#10b981',
        animation: 'spin 0.8s linear infinite'
      }} />
      <h2 style={{ fontWeight: 600, letterSpacing: '0.02em', margin: 0 }}>{status}</h2>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
