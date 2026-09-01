import React, { useEffect, useState } from 'react';
import api from '../services/api';
import { 
  Search, 
  RefreshCw, 
  AlertCircle,
  Filter
} from 'lucide-react';

interface AuditLog {
  idLog: string;
  fechaHora: string;
  usuario: string;
  estacion: string;
  evento: string;
  objeto: string;
  referencia: string;
  descripcion: string;
  datosAdicionales: string;
}

const AuditLogs: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [eventFilter, setEventFilter] = useState('');

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get('/auditlogs');
      setLogs(res.data);
    } catch (err) {
      setError('Error al recuperar los logs de auditoría del servidor central.');
    } finally {
      setLoading(false);
    }
  };

  const getEventBadgeClass = (eventName: string) => {
    const ev = eventName.toUpperCase();
    if (ev.includes('FAIL') || ev.includes('BLOCKED')) {
      return 'sade-badge-danger';
    }
    if (ev.includes('OK') || ev.includes('CHANGED') || ev.includes('SUCCESS')) {
      return 'sade-badge-success';
    }
    return 'sade-badge-warning';
  };

  const formatEventName = (eventName: string) => {
    return eventName
      .replace('EVENT_', '')
      .replace('_', ' ')
      .toLowerCase()
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  // Filter logs based on search term and event dropdown filter
  const filteredLogs = logs.filter(log => {
    const matchesSearch = 
      log.usuario.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.descripcion.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.objeto.toLowerCase().includes(searchTerm.toLowerCase()) ||
      log.referencia.toLowerCase().includes(searchTerm.toLowerCase());
      
    const matchesEvent = eventFilter === '' || log.evento === eventFilter;
    
    return matchesSearch && matchesEvent;
  });

  // Extract unique events for the filter dropdown
  const uniqueEvents = Array.from(new Set(logs.map(log => log.evento)));

  return (
    <div style={{ padding: '30px', width: '100%', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 700 }}>Bitácora de Auditoría (Audit Logs)</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginTop: '4px' }}>
            Registro cronológico de los eventos de inicio de sesión, cambios de contraseña y validación de permisos.
          </p>
        </div>
        <button className="sade-btn sade-btn-secondary" onClick={fetchLogs} disabled={loading}>
          <RefreshCw size={16} style={{ marginRight: '8px' }} className={loading ? 'animate-spin' : ''} />
          Refrescar
        </button>
      </div>

      {error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#EF4444', fontSize: '13px', backgroundColor: 'var(--danger-bg)', padding: '12px', borderRadius: '8px' }}>
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* Filters Toolbar */}
      <div 
        className="sade-card" 
        style={{ 
          padding: '16px 20px', 
          display: 'flex', 
          flexWrap: 'wrap', 
          gap: '16px', 
          alignItems: 'center',
          justifyContent: 'space-between'
        }}
      >
        <div style={{ display: 'flex', gap: '16px', flexGrow: 1, maxWidth: '600px' }}>
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
              placeholder="Buscar por usuario, objeto o descripción..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ paddingLeft: '40px' }}
            />
          </div>

          <div style={{ position: 'relative', minWidth: '200px' }}>
            <Filter 
              size={16} 
              style={{ 
                position: 'absolute', 
                left: '14px', 
                top: '50%', 
                transform: 'translateY(-50%)', 
                color: 'var(--text-muted)' 
              }} 
            />
            <select 
              className="sade-input" 
              value={eventFilter}
              onChange={(e) => setEventFilter(e.target.value)}
              style={{ paddingLeft: '40px', appearance: 'none', cursor: 'pointer' }}
            >
              <option value="">Todos los eventos</option>
              {uniqueEvents.map(ev => (
                <option key={ev} value={ev}>{formatEventName(ev)}</option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
          Mostrando <span style={{ fontWeight: 600, color: '#3B82F6' }}>{filteredLogs.length}</span> registros de {logs.length}
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '50px 0', color: 'var(--text-secondary)' }}>
          Cargando registros de auditoría...
        </div>
      ) : filteredLogs.length === 0 ? (
        <div className="sade-card" style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
          No se encontraron registros de auditoría que coincidan con la búsqueda.
        </div>
      ) : (
        <div className="sade-table-container">
          <table className="sade-table">
            <thead>
              <tr>
                <th style={{ width: '180px' }}>Fecha y Hora</th>
                <th>Usuario</th>
                <th>Evento</th>
                <th>Objeto / Referencia</th>
                <th>Descripción</th>
                <th>Origen / IP</th>
              </tr>
            </thead>
            <tbody>
              {filteredLogs.map((log) => (
                <tr key={log.idLog}>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>
                    {new Date(log.fechaHora).toLocaleString('es-DO', {
                      year: 'numeric',
                      month: '2-digit',
                      day: '2-digit',
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit'
                    })}
                  </td>
                  <td style={{ fontWeight: 600 }}>{log.usuario}</td>
                  <td>
                    <span className={`sade-badge ${getEventBadgeClass(log.evento)}`}>
                      {formatEventName(log.evento)}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontWeight: 500 }}>{log.objeto || '-'}</span>
                      {log.referencia && (
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                          Ref: {log.referencia}
                        </span>
                      )}
                    </div>
                  </td>
                  <td>{log.descripcion}</td>
                  <td style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    {log.datosAdicionales ? log.datosAdicionales.replace('IP: ', '') : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default AuditLogs;
