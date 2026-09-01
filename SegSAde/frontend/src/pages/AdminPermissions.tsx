import React, { useEffect, useState } from 'react';
import api from '../services/api';
import { 
  Save, 
  ChevronRight, 
  AlertCircle,
  CheckCircle
} from 'lucide-react';

interface PermissionRow {
  idSegObjeto: string;
  idSegUserGrp: string;
  categoria: string;
  segObjeto: string;
  agregar: number;
  editar: number;
  borrar: number;
  imprimir: number;
  abrir: number;
  anular: number;
  aprobar: number;
}

interface TargetOption {
  id: string;
  name: string;
  isGroup: boolean;
}

const AdminPermissions: React.FC = () => {
  const [targetOptions, setTargetOptions] = useState<TargetOption[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<string>('');
  const [matrix, setMatrix] = useState<PermissionRow[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [matrixLoading, setMatrixLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    loadTargets();
  }, []);

  const loadTargets = async () => {
    setLoading(true);
    setError(null);
    try {
      const [usersRes, groupsRes] = await Promise.all([
        api.get('/users'),
        api.get('/groups')
      ]);

      const options: TargetOption[] = [];
      
      // Add groups first
      groupsRes.data.forEach((g: any) => {
        options.push({ id: g.idSegUserGrp, name: `${g.idSegUserGrp} (Grupo)`, isGroup: true });
      });

      // Add users
      usersRes.data.forEach((u: any) => {
        options.push({ id: u.idSegUserGrp, name: `${u.idSegUserGrp} (Usuario)`, isGroup: false });
      });

      setTargetOptions(options);
      
      if (options.length > 0) {
        setSelectedTarget(options[0].id);
      }
    } catch (err) {
      setError('Error al cargar la lista de usuarios y grupos.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedTarget) {
      loadMatrix(selectedTarget);
    }
  }, [selectedTarget]);

  const loadMatrix = async (targetId: string) => {
    setMatrixLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await api.get(`/permissions/matrix?userOrGroupId=${targetId}`);
      setMatrix(res.data);
    } catch (err) {
      setError('Error al cargar la matriz de permisos para el sujeto seleccionado.');
    } finally {
      setMatrixLoading(false);
    }
  };

  const handleCellChange = (rowIndex: number, column: keyof PermissionRow, value: number) => {
    const updated = [...matrix];
    // @ts-ignore
    updated[rowIndex][column] = value;
    setMatrix(updated);
  };

  const handleSave = async () => {
    setError(null);
    setSuccess(null);
    setMatrixLoading(true);
    try {
      await api.post('/permissions/matrix', matrix);
      setSuccess('Matriz de permisos guardada exitosamente.');
    } catch (err) {
      setError('Error de red al guardar la matriz de permisos.');
    } finally {
      setMatrixLoading(false);
    }
  };

  const levels = [
    { value: 0, label: 'Denegado' },
    { value: 1, label: 'Nivel 1' },
    { value: 2, label: 'Nivel 2' },
    { value: 3, label: 'Nivel 3' },
    { value: 4, label: 'Nivel 4' },
    { value: 5, label: 'Nivel 5' },
    { value: 6, label: 'Completo (6)' }
  ];

  // Group matrix by category
  const categories: { [key: string]: PermissionRow[] } = {};
  matrix.forEach((row, index) => {
    const cat = row.categoria || 'Sin Categoría';
    if (!categories[cat]) {
      categories[cat] = [];
    }
    // Store original index so we can update the correct item in the flat matrix array
    // @ts-ignore
    row.originalIndex = index;
    categories[cat].push(row);
  });

  return (
    <div style={{ padding: '30px', width: '100%', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 700 }}>Matriz de Roles y Permisos</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginTop: '4px' }}>
            Configure niveles de acceso específicos por pantalla (objeto) y acción para cada sujeto.
          </p>
        </div>
        <button 
          className="sade-btn sade-btn-primary" 
          onClick={handleSave}
          disabled={matrixLoading || matrix.length === 0}
        >
          <Save size={16} style={{ marginRight: '8px' }} />
          Guardar Permisos
        </button>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#EF4444', fontSize: '13px', backgroundColor: 'var(--danger-bg)', padding: '12px', borderRadius: '8px' }}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#10B981', fontSize: '13px', backgroundColor: 'var(--success-bg)', padding: '12px', borderRadius: '8px' }}>
          <CheckCircle size={18} />
          <span>{success}</span>
        </div>
      )}

      <div className="sade-card" style={{ display: 'flex', alignItems: 'center', gap: '16px', padding: '16px 24px' }}>
        <label style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-secondary)' }}>
          Seleccionar Sujeto:
        </label>
        {loading ? (
          <span>Cargando...</span>
        ) : (
          <select 
            className="sade-input" 
            value={selectedTarget}
            onChange={(e) => setSelectedTarget(e.target.value)}
            style={{ width: 'auto', minWidth: '280px', cursor: 'pointer' }}
          >
            {targetOptions.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {matrixLoading ? (
        <div style={{ textAlign: 'center', padding: '50px 0', color: 'var(--text-secondary)' }}>
          Cargando configuración de la matriz de permisos...
        </div>
      ) : matrix.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '50px 0', color: 'var(--text-muted)' }}>
          Seleccione un sujeto para configurar sus permisos.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {Object.keys(categories).map((catName) => (
            <div key={catName} className="sade-card" style={{ padding: '0', overflow: 'hidden' }}>
              <div 
                style={{ 
                  backgroundColor: 'var(--bg-tertiary)', 
                  padding: '12px 20px', 
                  fontSize: '14px', 
                  fontWeight: 600, 
                  color: '#3B82F6',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  borderBottom: '1px solid var(--border)'
                }}
              >
                <ChevronRight size={16} />
                Área / Categoría: {catName}
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table className="sade-table" style={{ border: 'none' }}>
                  <thead>
                    <tr>
                      <th style={{ width: '220px', backgroundColor: 'transparent' }}>Pantalla / Objeto</th>
                      <th style={{ backgroundColor: 'transparent', textAlign: 'center' }}>Abrir</th>
                      <th style={{ backgroundColor: 'transparent', textAlign: 'center' }}>Agregar</th>
                      <th style={{ backgroundColor: 'transparent', textAlign: 'center' }}>Editar</th>
                      <th style={{ backgroundColor: 'transparent', textAlign: 'center' }}>Borrar</th>
                      <th style={{ backgroundColor: 'transparent', textAlign: 'center' }}>Imprimir</th>
                      <th style={{ backgroundColor: 'transparent', textAlign: 'center' }}>Anular</th>
                      <th style={{ backgroundColor: 'transparent', textAlign: 'center' }}>Aprobar</th>
                    </tr>
                  </thead>
                  <tbody>
                    {categories[catName].map((row) => {
                      // @ts-ignore
                      const originalIdx = row.originalIndex;
                      return (
                        <tr key={row.idSegObjeto}>
                          <td style={{ fontWeight: 500 }}>
                            <div style={{ display: 'flex', flexDirection: 'column' }}>
                              <span style={{ fontSize: '14px' }}>{row.segObjeto}</span>
                              <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>{row.idSegObjeto}</span>
                            </div>
                          </td>
                          {[
                            { col: 'abrir', val: row.abrir },
                            { col: 'agregar', val: row.agregar },
                            { col: 'editar', val: row.editar },
                            { col: 'borrar', val: row.borrar },
                            { col: 'imprimir', val: row.imprimir },
                            { col: 'anular', val: row.anular },
                            { col: 'aprobar', val: row.aprobar }
                          ].map((c) => (
                            <td key={c.col} style={{ textAlign: 'center', padding: '8px' }}>
                              <select 
                                className="sade-input" 
                                value={c.val}
                                onChange={(e) => handleCellChange(originalIdx, c.col as keyof PermissionRow, parseInt(e.target.value))}
                                style={{ 
                                  fontSize: '12px', 
                                  padding: '6px 8px', 
                                  width: '100%', 
                                  maxWidth: '120px',
                                  textAlign: 'center',
                                  cursor: 'pointer',
                                  backgroundColor: c.val === 0 
                                    ? 'rgba(239, 68, 68, 0.05)' 
                                    : c.val === 6 
                                      ? 'rgba(16, 185, 129, 0.05)' 
                                      : 'var(--bg-tertiary)',
                                  borderColor: c.val === 0 
                                    ? 'rgba(239, 68, 68, 0.15)' 
                                    : c.val === 6 
                                      ? 'rgba(16, 185, 129, 0.15)' 
                                      : 'var(--border)',
                                  color: c.val === 0 
                                    ? '#EF4444' 
                                    : c.val === 6 
                                      ? '#10B981' 
                                      : 'var(--text-primary)'
                                }}
                              >
                                {levels.map((lvl) => (
                                  <option key={lvl.value} value={lvl.value}>
                                    {lvl.label}
                                  </option>
                                ))}
                              </select>
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AdminPermissions;
