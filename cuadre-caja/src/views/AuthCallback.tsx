import { useEffect, useState } from 'react';

interface AuthCallbackProps {
  navigate: (to: string) => void;
}

export default function AuthCallback({ navigate }: AuthCallbackProps) {
  const [status, setStatus] = useState('Procesando credenciales...');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    const empresaId = params.get('empresaId');
    const empresaNombre = params.get('empresaNombre');
    const empresaRNC = params.get('empresaRNC');

    let timeoutId: any = null;

    if (token && empresaId) {
      try {
        localStorage.setItem('jwt_token', token);
        
        const empresaData = {
          idEmpresa: empresaId,
          empresa: empresaNombre || 'Empresa Seleccionada',
          rnc: empresaRNC || ''
        };
        localStorage.setItem('empresa', JSON.stringify(empresaData));
        
        setStatus('¡Sesión establecida con éxito! Redirigiendo...');
        
        // Clean URL from parameters
        window.history.replaceState({}, document.title, '/');

        timeoutId = setTimeout(() => {
          navigate('/');
        }, 800);
      } catch (e) {
        console.error('Error saving session details', e);
        setStatus('Error al guardar la sesión.');
      }
    } else {
      // Check if we already have a valid session stored (to handle React 18 StrictMode double mount)
      const existingToken = localStorage.getItem('jwt_token');
      const existingEmpresa = localStorage.getItem('empresa');
      
      if (existingToken && existingEmpresa) {
        setStatus('¡Sesión activa detectada! Redirigiendo...');
        navigate('/');
      } else {
        setStatus('Credenciales no recibidas o no válidas.');
        timeoutId = setTimeout(() => {
          window.location.href = 'http://localhost:5174/?client_id=cuadre-caja';
        }, 2000);
      }
    }

    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
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
      <div className="spinner" style={{ width: '50px', height: '50px', borderLeftColor: '#10b981' }}></div>
      <h2 style={{ fontWeight: 600, letterSpacing: '0.02em' }}>{status}</h2>
    </div>
  );
}
