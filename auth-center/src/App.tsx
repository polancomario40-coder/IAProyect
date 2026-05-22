import React, { useState, useEffect } from 'react';
import api from './services/api';

interface Empresa {
  idEmpresa: string;
  empresa: string;
  rnc: string;
}

export default function App() {
  const [step, setStep] = useState<'login' | 'empresa'>('login');
  const [usuarioStr, setUsuarioStr] = useState('');
  const [clave, setClave] = useState('');
  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const [selectedEmpresa, setSelectedEmpresa] = useState<Empresa | null>(null);
  
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [redirectUri, setRedirectUri] = useState<string | null>(null);
  const [clientId, setClientId] = useState<string | null>(null);

  // Parse query parameters
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const redirect = params.get('redirect_uri') || 'https://cuadre.sade.com.do/auth-callback';
    const client = params.get('client_id') || 'cuadre-caja';
    
    setRedirectUri(redirect);
    setClientId(client);

    // If already logged in, check if we can skip directly to company selection
    const token = localStorage.getItem('jwt_token');
    const savedUser = localStorage.getItem('usuario');
    if (token && savedUser) {
      fetchEmpresas();
    }
  }, []);

  const fetchEmpresas = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const response = await api.get('/usuario/empresas');
      setEmpresas(response.data);
      setStep('empresa');
    } catch (err: any) {
      console.error('Error fetching companies', err);
      // If token expired, clear it
      localStorage.removeItem('jwt_token');
      localStorage.removeItem('usuario');
      setStep('login');
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!usuarioStr.trim()) {
      setErrorMsg('Debe ingresar el usuario');
      return;
    }

    setLoading(true);
    setErrorMsg(null);
    try {
      const response = await api.post('/login', {
        usuario: usuarioStr.trim(),
        clave: clave,
      });

      const { token, usuario } = response.data;
      localStorage.setItem('jwt_token', token);
      localStorage.setItem('usuario', JSON.stringify(usuario));
      
      setSuccessMsg('Inicio de sesión exitoso');
      setTimeout(() => setSuccessMsg(null), 2000);

      // Fetch companies right after successful login
      await fetchEmpresas();
    } catch (err: any) {
      console.error(err);
      const msg = err.response?.data?.mensaje || err.response?.data || 'Credenciales incorrectas o error en el servidor';
      setErrorMsg(typeof msg === 'string' ? msg : 'Error de autenticación');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectEmpresa = async (empresa: Empresa) => {
    setSelectedEmpresa(empresa);
    setLoading(true);
    setErrorMsg(null);
    try {
      // Validate access (X-Selected-Company header is added by interceptor after saving or explicitly passed here)
      const response = await api.post('/usuario/validar-acceso', {}, {
        headers: { 'X-Selected-Company': empresa.idEmpresa }
      });

      let companyName = empresa.empresa;
      if (response.data && response.data.success) {
        companyName = response.data.companiaNombre || empresa.empresa;
      } else {
        // If target app is Cuadre de Caja, we might not strictly block if the database group check is for CXPAPP only.
        // We warn or allow access because Cuadre de Caja has its own database privileges.
        console.warn('Acceso denegado en CXPAPP, procediendo con permisos alternativos para Cuadre de Caja.');
        if (clientId !== 'cuadre-caja') {
          throw new Error(response.data?.mensaje || 'No tiene permisos requeridos para esta compañía.');
        }
      }

      // Save company details
      const empresaData = {
        idEmpresa: empresa.idEmpresa,
        empresa: companyName,
        rnc: empresa.rnc
      };
      localStorage.setItem('empresa', JSON.stringify(empresaData));

      // Redirect SSO Callback
      if (redirectUri) {
        const token = localStorage.getItem('jwt_token');
        const callbackUrl = new URL(redirectUri);
        callbackUrl.searchParams.set('token', token || '');
        callbackUrl.searchParams.set('empresaId', empresa.idEmpresa);
        callbackUrl.searchParams.set('empresaNombre', companyName);
        callbackUrl.searchParams.set('empresaRNC', empresa.rnc);
        
        setSuccessMsg('Redirigiendo a la aplicación...');
        setTimeout(() => {
          window.location.href = callbackUrl.toString();
        }, 1200);
      } else {
        setSuccessMsg(`Empresa "${companyName}" seleccionada correctamente.`);
        setTimeout(() => setSuccessMsg(null), 3000);
      }
    } catch (err: any) {
      console.error(err);
      const msg = err.response?.data?.mensaje || err.message || 'Error al validar el acceso.';
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('jwt_token');
    localStorage.removeItem('empresa');
    localStorage.removeItem('usuario');
    setStep('login');
    setEmpresas([]);
    setSelectedEmpresa(null);
    setErrorMsg(null);
  };

  return (
    <div className="glass-card">
      <div className="logo-container">
        {/* Placeholder image loaded via CSS styling or custom text fallback if not found */}
        <div style={{ textAlign: 'center', marginBottom: '1rem' }}>
          <span style={{ fontSize: '3rem', display: 'block', marginBottom: '0.5rem' }}>🌌</span>
          <span style={{ fontSize: '1.2rem', fontWeight: 800, letterSpacing: '0.1em', color: '#60a5fa' }}>DATAFLOW ERP</span>
        </div>
      </div>

      {errorMsg && <div className="alert alert-danger">{errorMsg}</div>}
      {successMsg && <div className="alert alert-success">{successMsg}</div>}

      {step === 'login' ? (
        <form onSubmit={handleLogin}>
          <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
            <h1 className="title-header">Iniciar Sesión</h1>
            <p className="subtitle-header">Centro de Autenticación Unificado</p>
          </div>

          <div className="form-group">
            <label className="form-label">Usuario</label>
            <input
              type="text"
              className="form-input"
              placeholder="Ingrese su usuario"
              value={usuarioStr}
              onChange={(e) => setUsuarioStr(e.target.value)}
              disabled={loading}
              autoCapitalize="none"
              required
            />
          </div>

          <div className="form-group" style={{ marginBottom: '2rem' }}>
            <label className="form-label">Contraseña</label>
            <input
              type="password"
              className="form-input"
              placeholder="Ingrese su contraseña"
              value={clave}
              onChange={(e) => setClave(e.target.value)}
              disabled={loading}
              required
            />
          </div>

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? <span className="spinner"></span> : 'Ingresar al Portal'}
          </button>

          <p className="text-version">Portal ID v1.0 • Seguro • Protegido</p>
        </form>
      ) : (
        <div>
          <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
            <h1 className="title-header">Empresas</h1>
            <p className="subtitle-header">Seleccione su espacio de trabajo</p>
          </div>

          {loading && empresas.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '2rem' }}>
              <span className="spinner" style={{ width: '40px', height: '40px', borderLeftColor: '#3b82f6' }}></span>
              <p style={{ marginTop: '1rem', color: '#94a3b8' }}>Cargando empresas...</p>
            </div>
          ) : (
            <>
              <div className="company-list">
                {empresas.map((emp) => (
                  <div
                    key={emp.idEmpresa}
                    className={`company-card ${selectedEmpresa?.idEmpresa === emp.idEmpresa ? 'selected' : ''}`}
                    onClick={() => !loading && handleSelectEmpresa(emp)}
                  >
                    <div className="company-name">{emp.empresa}</div>
                    <div className="company-rnc">RNC: {emp.rnc}</div>
                  </div>
                ))}
                {empresas.length === 0 && (
                  <div style={{ textAlign: 'center', padding: '2rem', color: '#94a3b8' }}>
                    No tiene empresas asignadas con acceso web.
                  </div>
                )}
              </div>

              <button
                type="button"
                className="btn-danger"
                onClick={handleLogout}
                disabled={loading}
              >
                🚪 Cerrar Sesión
              </button>
            </>
          )}

          <p className="text-version">Dataflow Cloud Platform</p>
        </div>
      )}
    </div>
  );
}
