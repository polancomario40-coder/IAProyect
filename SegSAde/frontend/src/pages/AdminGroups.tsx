import React, { useEffect, useState } from 'react';
import api from '../services/api';
import { 
  Plus, 
  Edit, 
  Trash2, 
  Users, 
  X, 
  Check, 
  AlertCircle 
} from 'lucide-react';

interface Group {
  idSegUserGrp: string;
  activo: boolean;
  nivel: number;
}

interface User {
  idSegUserGrp: string;
  nombre: string;
}

const AdminGroups: React.FC = () => {
  const [groups, setGroups] = useState<Group[]>([]);
  const [allUsers, setAllUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Group Form Modal State
  const [showGroupModal, setShowGroupModal] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [groupId, setGroupId] = useState('');
  const [activo, setActivo] = useState(true);
  const [nivel, setNivel] = useState(3);

  // Members Modal State
  const [showMembersModal, setShowMembersModal] = useState(false);
  const [activeGroup, setActiveGroup] = useState<Group | null>(null);
  const [groupMembers, setGroupMembers] = useState<string[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [groupsRes, usersRes] = await Promise.all([
        api.get('/groups'),
        api.get('/users')
      ]);
      setGroups(groupsRes.data);
      setAllUsers(usersRes.data);
    } catch (err) {
      setError('Error al recuperar grupos y usuarios del servidor.');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenAdd = () => {
    setIsEditMode(false);
    setGroupId('');
    setActivo(true);
    setNivel(3);
    setShowGroupModal(true);
  };

  const handleOpenEdit = (g: Group) => {
    setIsEditMode(true);
    setGroupId(g.idSegUserGrp);
    setActivo(g.activo);
    setNivel(g.nivel);
    setShowGroupModal(true);
  };

  const handleSaveGroup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!groupId) {
      setError('El identificador del grupo es necesario.');
      return;
    }

    try {
      const payload = {
        idSegUserGrp: groupId,
        activo,
        nivel
      };

      if (isEditMode) {
        await api.put(`/groups/${groupId}`, payload);
      } else {
        await api.post('/groups', payload);
      }

      setShowGroupModal(false);
      fetchData();
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data || 'Error al guardar los cambios del grupo.');
    }
  };

  const handleDeleteGroup = async (g: Group) => {
    if (window.confirm(`¿Está seguro que desea desactivar el grupo "${g.idSegUserGrp}"?`)) {
      try {
        await api.delete(`/groups/${g.idSegUserGrp}`);
        fetchData();
      } catch (err) {
        setError('Error al eliminar el grupo.');
      }
    }
  };

  const handleOpenMembers = async (g: Group) => {
    setActiveGroup(g);
    setGroupMembers([]);
    setMembersLoading(true);
    setShowMembersModal(true);

    try {
      const membersRes = await api.get(`/groups/${g.idSegUserGrp}/members`);
      setGroupMembers(membersRes.data);
    } catch (err) {
      console.error('Error fetching group members:', err);
    } finally {
      setMembersLoading(false);
    }
  };

  const handleMemberToggle = (username: string) => {
    if (groupMembers.includes(username)) {
      setGroupMembers(groupMembers.filter(u => u !== username));
    } else {
      setGroupMembers([...groupMembers, username]);
    }
  };

  const handleSaveMembers = async () => {
    if (!activeGroup) return;

    try {
      await api.post(`/groups/${activeGroup.idSegUserGrp}/members`, groupMembers);
      setShowMembersModal(false);
      fetchData();
    } catch (err) {
      setError('Error al actualizar los miembros del grupo.');
    }
  };

  return (
    <div style={{ padding: '30px', width: '100%', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 700 }}>Grupos de Seguridad</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginTop: '4px' }}>
            Configure grupos de usuarios para asignación colectiva de permisos de acceso.
          </p>
        </div>
        <button className="sade-btn sade-btn-primary" onClick={handleOpenAdd}>
          <Plus size={16} style={{ marginRight: '8px' }} />
          Nuevo Grupo
        </button>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#EF4444', fontSize: '13px', backgroundColor: 'var(--danger-bg)', padding: '12px', borderRadius: '8px' }}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: '50px 0', color: 'var(--text-secondary)' }}>
          Cargando grupos de seguridad...
        </div>
      ) : (
        <div className="sade-table-container">
          <table className="sade-table">
            <thead>
              <tr>
                <th>Identificador Grupo</th>
                <th>Clearance Nivel</th>
                <th>Estado</th>
                <th style={{ textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {groups.map((g) => (
                <tr key={g.idSegUserGrp}>
                  <td style={{ fontWeight: 600, color: '#10B981' }}>{g.idSegUserGrp}</td>
                  <td>Nivel {g.nivel}</td>
                  <td>
                    {g.activo ? (
                      <span className="sade-badge sade-badge-success">Activo</span>
                    ) : (
                      <span className="sade-badge sade-badge-danger">Inactivo</span>
                    )}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                      <button 
                        style={{ display: 'flex', alignItems: 'center', gap: '6px', backgroundColor: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)', color: '#3B82F6', cursor: 'pointer', padding: '6px 12px', borderRadius: '6px', fontSize: '12px', fontWeight: 500 }}
                        onClick={() => handleOpenMembers(g)}
                      >
                        <Users size={14} />
                        Miembros
                      </button>
                      <button 
                        style={{ background: 'transparent', border: 'none', color: '#3B82F6', cursor: 'pointer', padding: '6px' }}
                        onClick={() => handleOpenEdit(g)}
                      >
                        <Edit size={16} />
                      </button>
                      <button 
                        style={{ background: 'transparent', border: 'none', color: '#EF4444', cursor: 'pointer', padding: '6px' }}
                        onClick={() => handleDeleteGroup(g)}
                        disabled={!g.activo}
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

      {/* Group Form Modal */}
      {showGroupModal && (
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
              maxWidth: '450px',
              border: '1px solid var(--border)',
              boxShadow: 'var(--card-shadow)',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border)', paddingBottom: '14px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 700 }}>
                {isEditMode ? `Editar Grupo: ${groupId}` : 'Registrar Nuevo Grupo'}
              </h2>
              <button 
                style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
                onClick={() => setShowGroupModal(false)}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSaveGroup} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>
                  Identificador de Grupo (ID)
                </label>
                <input 
                  type="text" 
                  className="sade-input" 
                  placeholder="ej. G_FACTURACION"
                  value={groupId}
                  onChange={(e) => setGroupId(e.target.value)}
                  disabled={isEditMode}
                  required
                />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>
                  Nivel de Clearance del Grupo (1 - 5)
                </label>
                <select 
                  className="sade-input" 
                  value={nivel}
                  onChange={(e) => setNivel(parseInt(e.target.value))}
                  style={{ appearance: 'none', cursor: 'pointer' }}
                >
                  <option value={1}>Nivel 1 (Básico)</option>
                  <option value={2}>Nivel 2</option>
                  <option value={3}>Nivel 3 (Por defecto)</option>
                  <option value={4}>Nivel 4</option>
                  <option value={5}>Nivel 5 (Supervisor)</option>
                </select>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>
                  Estado
                </label>
                <select 
                  className="sade-input" 
                  value={activo ? '1' : '0'}
                  onChange={(e) => setActivo(e.target.value === '1')}
                  style={{ appearance: 'none', cursor: 'pointer' }}
                >
                  <option value="1">Activo</option>
                  <option value="0">Inactivo</option>
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', borderTop: '1px solid var(--border)', paddingTop: '14px', marginTop: '10px' }}>
                <button 
                  type="button" 
                  className="sade-btn sade-btn-secondary"
                  onClick={() => setShowGroupModal(false)}
                >
                  Cancelar
                </button>
                <button 
                  type="submit" 
                  className="sade-btn sade-btn-primary"
                >
                  Guardar Grupo
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Members Assignment Modal */}
      {showMembersModal && (
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
              maxWidth: '500px',
              border: '1px solid var(--border)',
              boxShadow: 'var(--card-shadow)',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
              maxHeight: '85vh'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border)', paddingBottom: '14px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 700 }}>
                Asignar Miembros: <span style={{ color: '#10B981' }}>{activeGroup?.idSegUserGrp}</span>
              </h2>
              <button 
                style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
                onClick={() => setShowMembersModal(false)}
              >
                <X size={18} />
              </button>
            </div>

            {membersLoading ? (
              <div style={{ textAlign: 'center', padding: '30px 0', color: 'var(--text-secondary)' }}>
                Cargando miembros...
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', overflow: 'hidden' }}>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                  Seleccione los usuarios que pertenecerán a este grupo de seguridad.
                </p>

                <div 
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    padding: '12px',
                    overflowY: 'auto',
                    maxHeight: '300px',
                    backgroundColor: 'rgba(0,0,0,0.1)'
                  }}
                >
                  {allUsers.map((u) => {
                    const isChecked = groupMembers.includes(u.idSegUserGrp);
                    return (
                      <div 
                        key={u.idSegUserGrp}
                        onClick={() => handleMemberToggle(u.idSegUserGrp)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '12px',
                          padding: '10px 12px',
                          border: '1px solid ' + (isChecked ? 'rgba(16,185,129,0.3)' : 'transparent'),
                          backgroundColor: isChecked ? 'rgba(16,185,129,0.05)' : 'transparent',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          fontSize: '14px',
                          transition: 'all 0.2s'
                        }}
                      >
                        <div 
                          style={{
                            width: '16px',
                            height: '16px',
                            border: '1px solid ' + (isChecked ? '#10B981' : 'var(--text-muted)'),
                            borderRadius: '4px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            backgroundColor: isChecked ? '#10B981' : 'transparent',
                            color: '#FFFFFF'
                          }}
                        >
                          {isChecked && <Check size={12} strokeWidth={3} />}
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontWeight: 600 }}>{u.idSegUserGrp}</span>
                          {u.nombre && (
                            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{u.nombre}</span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', borderTop: '1px solid var(--border)', paddingTop: '14px', marginTop: '10px' }}>
                  <button 
                    type="button" 
                    className="sade-btn sade-btn-secondary"
                    onClick={() => setShowMembersModal(false)}
                  >
                    Cancelar
                  </button>
                  <button 
                    type="button" 
                    className="sade-btn sade-btn-primary"
                    onClick={handleSaveMembers}
                  >
                    Guardar Miembros
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminGroups;
