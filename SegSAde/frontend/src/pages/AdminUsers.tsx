import React, { useEffect, useState } from 'react';
import api from '../services/api';
import { 
  Plus, 
  Edit, 
  Trash2, 
  Check, 
  X, 
  Building2, 
  AlertCircle,
  Eye,
  EyeOff,
  Search
} from 'lucide-react';

interface User {
  idSegUserGrp: string;
  nombre: string;
  email: string;
  telefono: string;
  activo: boolean;
  nivel: number;
  objetoDefault: string;
}

interface Company {
  idEmpresa: string;
  empresa: string;
}

const AdminUsers: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  // Form State
  const [showModal, setShowModal] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [nombre, setNombre] = useState('');
  const [email, setEmail] = useState('');
  const [telefono, setTelefono] = useState('');
  const [nivel, setNivel] = useState(3);
  const [objetoDefault, setObjetoDefault] = useState('');
  const [activo, setActivo] = useState(true);
  const [selectedCompanies, setSelectedCompanies] = useState<string[]>([]);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [usersRes, companiesRes] = await Promise.all([
        api.get('/users'),
        api.get('/auth/companies')
      ]);
      setUsers(usersRes.data);
      setCompanies(companiesRes.data);
    } catch (err) {
      setError('Error al recuperar datos del servidor.');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenAdd = () => {
    setIsEditMode(false);
    setUsername('');
    setPassword('');
    setNombre('');
    setEmail('');
    setTelefono('');
    setNivel(3);
    setObjetoDefault('');
    setActivo(true);
    setSelectedCompanies([]);
    setShowModal(true);
  };

  const handleOpenEdit = async (u: User) => {
    setIsEditMode(true);
    setUsername(u.idSegUserGrp);
    setPassword(''); // Leave password blank on edit unless changing it
    setNombre(u.nombre);
    setEmail(u.email);
    setTelefono(u.telefono);
    setNivel(u.nivel);
    setObjetoDefault(u.objetoDefault);
    setActivo(u.activo);
    setShowModal(true);

    try {
      const mappedCiasRes = await api.get(`/users/${u.idSegUserGrp}/companies`);
      setSelectedCompanies(mappedCiasRes.data);
    } catch (err) {
      console.error('Error fetching mapped companies:', err);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || (!isEditMode && !password)) {
      setError('El usuario y contraseña son campos mandatorios.');
      return;
    }

    try {
      const payload = {
        idSegUserGrp: username,
        clave: password,
        nombre,
        email,
        telefono,
        nivel,
        objetoDefault,
        activo
      };

      if (isEditMode) {
        await api.put(`/users/${username}`, payload);
      } else {
        await api.post('/users', payload);
      }

      // Save company mappings
      await api.post(`/users/${username}/companies`, selectedCompanies);

      setShowModal(false);
      fetchData();
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data || 'Error al guardar los cambios del usuario.');
    }
  };

  const handleDelete = async (u: User) => {
    if (window.confirm(`¿Está seguro que desea desactivar al usuario "${u.idSegUserGrp}"?`)) {
      try {
        await api.delete(`/users/${u.idSegUserGrp}`);
        fetchData();
      } catch (err) {
        setError('Error al desactivar el usuario.');
      }
    }
  };

  const handleCompanyToggle = (companyId: string) => {
    if (selectedCompanies.includes(companyId)) {
      setSelectedCompanies(selectedCompanies.filter(id => id !== companyId));
    } else {
      setSelectedCompanies([...selectedCompanies, companyId]);
    }
  };

  return (
    <div style={{ padding: '30px', width: '100%', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 700 }}>Administración de Usuarios</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginTop: '4px' }}>
            Cree, edite y restrinja accesos de usuarios locales y globales.
          </p>
        </div>
        <button className="sade-btn sade-btn-primary" onClick={handleOpenAdd}>
          <Plus size={16} style={{ marginRight: '8px' }} />
          Agregar Usuario
        </button>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#EF4444', fontSize: '13px', backgroundColor: 'var(--danger-bg)', padding: '12px', borderRadius: '8px' }}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* Search Bar */}
      <div 
        className="sade-card" 
        style={{ 
          padding: '16px 20px', 
          display: 'flex', 
          gap: '16px', 
          alignItems: 'center'
        }}
      >
        <div style={{ position: 'relative', flexGrow: 1 }}>
          <Search 
            size={16} 
            style={{ 
              position: 'absolute', 
              left: '14px', 
              top: '50%', 
              transform: 'translateY(-50%)', 
              color: 'var(--text-muted)' 
            }} 
          />
          <input 
            type="text" 
            className="sade-input" 
            placeholder="Buscar por usuario (ID), nombre o correo..." 
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ paddingLeft: '40px' }}
          />
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '50px 0', color: 'var(--text-secondary)' }}>
          Cargando usuarios de la base de datos...
        </div>
      ) : (
        <div className="sade-table-container">
          <table className="sade-table">
            <thead>
              <tr>
                <th>Usuario</th>
                <th>Nombre Completo</th>
                <th>Correo Electrónico</th>
                <th>Teléfono</th>
                <th>Clearance Nivel</th>
                <th>Estado</th>
                <th style={{ textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {users.filter(u => 
                u.idSegUserGrp.toLowerCase().includes(searchTerm.toLowerCase()) ||
                (u.nombre && u.nombre.toLowerCase().includes(searchTerm.toLowerCase())) ||
                (u.email && u.email.toLowerCase().includes(searchTerm.toLowerCase()))
              ).map((u) => (
                <tr key={u.idSegUserGrp}>
                  <td style={{ fontWeight: 600, color: '#3B82F6' }}>{u.idSegUserGrp}</td>
                  <td>{u.nombre || '-'}</td>
                  <td>{u.email || '-'}</td>
                  <td>{u.telefono || '-'}</td>
                  <td>
                    <span style={{ fontWeight: 600 }}>Nivel {u.nivel}</span>
                  </td>
                  <td>
                    {u.activo ? (
                      <span className="sade-badge sade-badge-success">Activo</span>
                    ) : (
                      <span className="sade-badge sade-badge-danger">Inactivo</span>
                    )}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                      <button 
                        style={{ background: 'transparent', border: 'none', color: '#3B82F6', cursor: 'pointer', padding: '4px' }}
                        onClick={() => handleOpenEdit(u)}
                      >
                        <Edit size={16} />
                      </button>
                      <button 
                        style={{ background: 'transparent', border: 'none', color: '#EF4444', cursor: 'pointer', padding: '4px' }}
                        onClick={() => handleDelete(u)}
                        disabled={!u.activo}
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Modal Form */}
      {showModal && (
        <div 
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            backgroundColor: 'rgba(0,0,0,0.6)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000
          }}
        >
          <div 
            className="sade-card"
            style={{
              width: '100%',
              maxWidth: '650px',
              maxHeight: '90vh',
              overflowY: 'auto',
              border: '1px solid var(--border)',
              boxShadow: 'var(--card-shadow)',
              animation: 'modalFadeIn 0.3s ease-out',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border)', paddingBottom: '14px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 700 }}>
                {isEditMode ? `Editar Usuario: ${username}` : 'Registrar Nuevo Usuario'}
              </h2>
              <button 
                style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
                onClick={() => setShowModal(false)}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>
                    Identificador (Usuario ID)
                  </label>
                  <input 
                    type="text" 
                    className="sade-input" 
                    placeholder="ej. admin_ventas"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    disabled={isEditMode}
                    required
                  />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>
                    {isEditMode ? 'Contraseña (Dejar en blanco para conservar)' : 'Contraseña'}
                  </label>
                  <div style={{ position: 'relative' }}>
                    <input 
                      type={showPassword ? 'text' : 'password'} 
                      className="sade-input" 
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required={!isEditMode}
                    />
                    <button 
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)', background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>
                    Nombre Completo
                  </label>
                  <input 
                    type="text" 
                    className="sade-input" 
                    placeholder="ej. Juan Pérez"
                    value={nombre}
                    onChange={(e) => setNombre(e.target.value)}
                  />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>
                    Correo Electrónico
                  </label>
                  <input 
                    type="email" 
                    className="sade-input" 
                    placeholder="ej. juan@sade.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>
                    Teléfono
                  </label>
                  <input 
                    type="text" 
                    className="sade-input" 
                    placeholder="ej. 809-555-0199"
                    value={telefono}
                    onChange={(e) => setTelefono(e.target.value)}
                  />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>
                    Clearance Nivel (1 - 5)
                  </label>
                  <select 
                    className="sade-input" 
                    value={nivel}
                    onChange={(e) => setNivel(parseInt(e.target.value))}
                    style={{ appearance: 'none', cursor: 'pointer' }}
                  >
                    <option value={1}>Nivel 1 (Bajo)</option>
                    <option value={2}>Nivel 2</option>
                    <option value={3}>Nivel 3 (Predeterminado)</option>
                    <option value={4}>Nivel 4</option>
                    <option value={5}>Nivel 5 (Supervisor)</option>
                  </select>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>
                    Estado del Usuario
                  </label>
                  <select 
                    className="sade-input" 
                    value={activo ? '1' : '0'}
                    onChange={(e) => setActivo(e.target.value === '1')}
                    style={{ appearance: 'none', cursor: 'pointer' }}
                  >
                    <option value="1">Activo / Operativo</option>
                    <option value="0">Desactivado / Bloqueado</option>
                  </select>
                </div>
              </div>

              {/* Companies selector */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', borderTop: '1px solid var(--border)', paddingTop: '14px' }}>
                <label style={{ fontSize: '13px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Building2 size={16} style={{ color: '#3B82F6' }} />
                  Empresas Asignadas (Acceso Autorizado)
                </label>
                <div 
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: '10px',
                    backgroundColor: 'rgba(255,255,255,0.01)',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    padding: '12px',
                    maxHeight: '140px',
                    overflowY: 'auto'
                  }}
                >
                  {companies.map((c) => {
                    const isChecked = selectedCompanies.includes(c.idEmpresa);
                    return (
                      <div 
                        key={c.idEmpresa}
                        onClick={() => handleCompanyToggle(c.idEmpresa)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '10px',
                          padding: '8px 10px',
                          border: '1px solid ' + (isChecked ? 'rgba(59,130,246,0.3)' : 'transparent'),
                          backgroundColor: isChecked ? 'rgba(59,130,246,0.05)' : 'transparent',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          fontSize: '13px',
                          transition: 'all 0.2s'
                        }}
                      >
                        <div 
                          style={{
                            width: '16px',
                            height: '16px',
                            border: '1px solid ' + (isChecked ? '#3B82F6' : 'var(--text-muted)'),
                            borderRadius: '4px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            backgroundColor: isChecked ? '#3B82F6' : 'transparent',
                            color: '#FFFFFF'
                          }}
                        >
                          {isChecked && <Check size={12} strokeWidth={3} />}
                        </div>
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {c.empresa}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', borderTop: '1px solid var(--border)', paddingTop: '14px', marginTop: '10px' }}>
                <button 
                  type="button" 
                  className="sade-btn sade-btn-secondary"
                  onClick={() => setShowModal(false)}
                >
                  Cancelar
                </button>
                <button 
                  type="submit" 
                  className="sade-btn sade-btn-primary"
                >
                  Guardar Cambios
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      
      <style>{`
        @keyframes modalFadeIn {
          from { opacity: 0; transform: scale(0.95); }
          to { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  );
};

export default AdminUsers;
