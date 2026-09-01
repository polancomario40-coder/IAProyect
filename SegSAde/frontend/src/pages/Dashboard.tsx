import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';
import { 
  Users, 
  UserSquare2, 
  Layers, 
  KeyRound,
  CheckCircle,
  AlertCircle
} from 'lucide-react';

const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState({ users: 0, groups: 0, objects: 0 });
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [pwdLoading, setPwdLoading] = useState(false);
  const [pwdError, setPwdError] = useState<string | null>(null);
  const [pwdSuccess, setPwdSuccess] = useState<string | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [usersRes, groupsRes, objectsRes] = await Promise.all([
          api.get('/users'),
          api.get('/groups'),
          api.get('/permissions/objects')
        ]);
        setStats({
          users: usersRes.data.length,
          groups: groupsRes.data.length,
          objects: objectsRes.data.length
        });
      } catch (error) {
        console.error('Error fetching statistics:', error);
      }
    };
    fetchStats();
  }, []);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwdError(null);
    setPwdSuccess(null);

    if (!oldPassword || !newPassword || !confirmPassword) {
      setPwdError('Por favor complete todos los campos.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setPwdError('La nueva contraseña y su confirmación no coinciden.');
      return;
    }

    setPwdLoading(true);
    try {
      await api.post('/auth/change-password', {
        username: user?.username,
        oldPassword,
        newPassword
      });
      setPwdSuccess('Contraseña cambiada exitosamente.');
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      console.error(err);
      if (err.response && err.response.data) {
        setPwdError(typeof err.response.data === 'string' ? err.response.data : err.response.data.message || 'Error al cambiar contraseña.');
      } else {
        setPwdError('Error de red al procesar la solicitud.');
      }
    } finally {
      setPwdLoading(false);
    }
  };

  return (
    <div style={{ padding: '30px', display: 'flex', flexDirection: 'column', gap: '30px', width: '100%' }}>
      {/* Welcome Banner */}
      <div 
        className="sade-card-glass"
        style={{
          padding: '40px',
          border: '1px solid rgba(59, 130, 246, 0.1)',
          background: 'linear-gradient(135deg, rgba(15, 22, 38, 0.9) 0%, rgba(30, 41, 59, 0.6) 100%)'
        }}
      >
        <h1 style={{ fontSize: '28px', fontWeight: 800, marginBottom: '8px' }}>
          Consola de Administración de Seguridad
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '15px', maxWidth: '600px', lineHeight: 1.6 }}>
          Bienvenido al nuevo panel web de SADE ERP. Desde este módulo puede gestionar usuarios, roles, configurar matrices de permisos y supervisar logs de auditoría en tiempo real.
        </p>
      </div>

      {/* Statistics Cards */}
      <div 
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '20px'
        }}
      >
        <div className="sade-card" style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div style={{ backgroundColor: 'rgba(59, 130, 246, 0.1)', color: '#3B82F6', padding: '14px', borderRadius: '12px' }}>
            <UserSquare2 size={24} />
          </div>
          <div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '13px', fontWeight: 500 }}>Usuarios Locales</p>
            <h3 style={{ fontSize: '24px', fontWeight: 700, marginTop: '4px' }}>{stats.users}</h3>
          </div>
        </div>

        <div className="sade-card" style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div style={{ backgroundColor: 'rgba(16, 185, 129, 0.1)', color: '#10B981', padding: '14px', borderRadius: '12px' }}>
            <Users size={24} />
          </div>
          <div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '13px', fontWeight: 500 }}>Grupos de Seguridad</p>
            <h3 style={{ fontSize: '24px', fontWeight: 700, marginTop: '4px' }}>{stats.groups}</h3>
          </div>
        </div>

        <div className="sade-card" style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div style={{ backgroundColor: 'rgba(245, 158, 11, 0.1)', color: '#F59E0B', padding: '14px', borderRadius: '12px' }}>
            <Layers size={24} />
          </div>
          <div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '13px', fontWeight: 500 }}>Objetos Registrados</p>
            <h3 style={{ fontSize: '24px', fontWeight: 700, marginTop: '4px' }}>{stats.objects}</h3>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '30px' }}>
        {/* Session Info */}
        <div className="sade-card" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <h2 style={{ fontSize: '18px', fontWeight: 700, borderBottom: '1px solid var(--border)', paddingBottom: '12px' }}>
            Información de Sesión Activa
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', fontSize: '14px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Usuario Autenticado:</span>
              <span style={{ fontWeight: 600 }}>{user?.username}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Nombre Completo:</span>
              <span style={{ fontWeight: 600 }}>{user?.fullName || 'N/D'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Correo Electrónico:</span>
              <span style={{ fontWeight: 600 }}>{user?.email || 'N/D'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Clearance Nivel:</span>
              <span style={{ fontWeight: 600, color: '#3B82F6' }}>{user?.nivel}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Empresa Conectada:</span>
              <span style={{ fontWeight: 600, color: '#10B981' }}>{user?.companyName || 'Ninguna'}</span>
            </div>
          </div>
        </div>

        {/* Change Password Form */}
        <div className="sade-card">
          <h2 style={{ fontSize: '18px', fontWeight: 700, borderBottom: '1px solid var(--border)', paddingBottom: '12px', marginBottom: '20px' }}>
            Cambiar Contraseña
          </h2>
          
          {pwdError && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#EF4444', fontSize: '13px', backgroundColor: 'var(--danger-bg)', padding: '10px', borderRadius: '6px', marginBottom: '16px' }}>
              <AlertCircle size={16} />
              <span>{pwdError}</span>
            </div>
          )}

          {pwdSuccess && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#10B981', fontSize: '13px', backgroundColor: 'var(--success-bg)', padding: '10px', borderRadius: '6px', marginBottom: '16px' }}>
              <CheckCircle size={16} />
              <span>{pwdSuccess}</span>
            </div>
          )}

          <form onSubmit={handleChangePassword} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>
                Contraseña Actual
              </label>
              <input 
                type="password" 
                className="sade-input" 
                placeholder="Introduzca clave actual"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                required 
              />
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>
                Nueva Contraseña
              </label>
              <input 
                type="password" 
                className="sade-input" 
                placeholder="Nueva clave"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required 
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>
                Confirmar Contraseña
              </label>
              <input 
                type="password" 
                className="sade-input" 
                placeholder="Repita nueva clave"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required 
              />
            </div>

            <button 
              type="submit" 
              className="sade-btn sade-btn-primary"
              style={{ width: '100%', height: '42px', marginTop: '4px' }}
              disabled={pwdLoading}
            >
              <KeyRound size={16} style={{ marginRight: '8px' }} />
              {pwdLoading ? 'Actualizando...' : 'Actualizar Contraseña'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
