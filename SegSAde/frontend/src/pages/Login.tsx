import React, { useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

const Login: React.FC = () => {
  const { login } = useAuth();

  useEffect(() => {
    login();
  }, [login]);

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', backgroundColor: 'var(--bg-primary)', color: 'var(--text-secondary)' }}>
      Redirigiendo al Centro de Seguridad...
    </div>
  );
};

export default Login;

