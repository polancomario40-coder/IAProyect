import { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

const AuthCallback = () => {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const token = params.get('token');
    const empresaId = params.get('empresaId');
    const empresaNombre = params.get('empresaNombre');
    const empresaRNC = params.get('empresaRNC');

    if (token) {
      localStorage.setItem('jwt_token', token);
      // Dummy user info just to keep the interceptor happy if needed
      localStorage.setItem('usuario', JSON.stringify({ validado: true }));
      
      if (empresaId) {
        localStorage.setItem('empresa', JSON.stringify({
          idEmpresa: empresaId,
          empresa: empresaNombre || 'Empresa',
          rnc: empresaRNC || ''
        }));
      }
      
      // Redirect to main dashboard
      navigate('/');
    } else {
      // Failed to get token, back to login
      const redirectUri = window.location.origin + '/auth-callback';
      window.location.href = `https://auth.sade.com.do/?client_id=sade-dashboard&redirect_uri=${encodeURIComponent(redirectUri)}`;
    }
  }, [navigate, location]);

  return (
    <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', background: '#0f172a', color: 'white' }}>
      <div style={{ textAlign: 'center' }}>
        <h2 style={{ marginBottom: '1rem' }}>Autenticando...</h2>
        <p style={{ color: '#94a3b8' }}>Validando su sesión segura en SADE</p>
      </div>
    </div>
  );
};

export default AuthCallback;
