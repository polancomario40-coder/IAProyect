import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const AuthCallback: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { saveSsoData } = useAuth();

  useEffect(() => {
    const token = searchParams.get('token');
    const empresaId = searchParams.get('empresaId');
    const empresaNombre = searchParams.get('empresaNombre');

    if (token && empresaId && empresaNombre) {
      saveSsoData(token, empresaId, empresaNombre);
      navigate('/');
    } else {
      navigate('/login');
    }
  }, [searchParams, navigate, saveSsoData]);

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', backgroundColor: 'var(--bg-primary)', color: 'var(--text-secondary)' }}>
      Validando credenciales...
    </div>
  );
};

export default AuthCallback;
