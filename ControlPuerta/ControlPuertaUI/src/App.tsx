import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { PuertaPage } from './pages/PuertaPage';
import { RecepcionPage } from './pages/RecepcionPage';
import { ConsultaPage } from './pages/ConsultaPage';
import { CierreDiaPage } from './pages/CierreDiaPage';
import AuthCallback from './pages/AuthCallback';
import { puertaApi } from './services/puertaApi';

const NavBar = () => {
  const { user, roles, logout } = useAuth();
  const [compania, setCompania] = useState('SADE');
  
  useEffect(() => {
    puertaApi.get('/puerta/configuracion')
      .then(res => {
        if (res.data && res.data.data && res.data.data.companiaCorto) {
          setCompania(res.data.data.companiaCorto);
        }
      })
      .catch(console.error);
  }, []);

  // Asumiremos que consulta y cierre son para administradores o almacén
  const hasAdmin = roles.includes('controlalmacen');

  return (
    <nav style={{ background: '#111827', padding: '15px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #374151' }}>
      <div style={{ display: 'flex', gap: 20, alignItems: 'center' }}>
        <h1 style={{ color: 'white', margin: 0, fontSize: 20 }}>{compania} | Puerta</h1>
        <Link to="/" style={linkStyle}>Inicio</Link>
        {hasAdmin && <Link to="/consulta" style={linkStyle}>Consulta</Link>}
        {hasAdmin && <Link to="/cierre" style={linkStyle}>Cierre Diario</Link>}
      </div>
      <div style={{ color: 'white', display: 'flex', alignItems: 'center', gap: 15 }}>
        <span>👤 {user?.nombre}</span>
        <button onClick={logout} style={{ background: 'transparent', border: '1px solid #4B5563', color: 'white', padding: '5px 10px', borderRadius: 4, cursor: 'pointer' }}>
          Salir
        </button>
      </div>
    </nav>
  );
};

const linkStyle = { color: '#9CA3AF', textDecoration: 'none', fontWeight: '500' };

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <div style={{ minHeight: '100vh', background: '#0B0F19', fontFamily: 'sans-serif' }}>
          <NavBar />
          <Routes>
            <Route path="/auth-callback" element={<AuthCallback />} />
            <Route path="/" element={<PuertaPage />} />
            <Route path="/recepcion/:id" element={<RecepcionPage />} />
            <Route path="/consulta" element={<ConsultaPage />} />
            <Route path="/cierre" element={<CierreDiaPage />} />
          </Routes>
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
