import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import RecepcionDataTable from '../components/RecepcionDataTable';

export const ConsultaPage: React.FC = () => {
  const hoy = new Date().toISOString().split('T')[0];
  const [filtros, setFiltros] = useState({
    fechaDesde: hoy,
    fechaHasta: hoy,
    conduce: '',
    placa: '',
    transportista: '',
    status: '',
    pageNumber: 1,
    pageSize: 50
  });

  const [filtrosActivos, setFiltrosActivos] = useState(filtros);
  const navigate = useNavigate();

  const handleBuscar = () => {
    setFiltrosActivos({ ...filtros, pageNumber: 1 });
  };

  return (
    <div style={{ padding: 20, color: '#F3F4F6' }}>
      <h2>Consulta Histórica</h2>
      
      <div style={{ background: '#1F2937', padding: 15, borderRadius: 8, marginBottom: 20, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <input type="date" value={filtros.fechaDesde} onChange={e=>setFiltros({...filtros, fechaDesde: e.target.value})} style={inputStyle} title="Desde" />
        <input type="date" value={filtros.fechaHasta} onChange={e=>setFiltros({...filtros, fechaHasta: e.target.value})} style={inputStyle} title="Hasta" />
        <input placeholder="Conduce..." value={filtros.conduce} onChange={e=>setFiltros({...filtros, conduce: e.target.value})} style={inputStyle} />
        <input placeholder="Placa..." value={filtros.placa} onChange={e=>setFiltros({...filtros, placa: e.target.value})} style={inputStyle} />
        
        <select value={filtros.status} onChange={e=>setFiltros({...filtros, status: e.target.value})} style={inputStyle}>
          <option value="">-- Todos los estados --</option>
          <option value="PENDIENTE">Pendiente</option>
          <option value="RECIBIDO">Recibido</option>
          <option value="CERRADO">Cerrado</option>
          <option value="BLOQUEADO">Bloqueado</option>
        </select>
        
        <button onClick={handleBuscar} style={{ padding: '8px 16px', background: '#3B82F6', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
          Buscar
        </button>
      </div>

      <RecepcionDataTable 
        filtros={filtrosActivos} 
        onVerDetalle={(id) => navigate(`/recepcion/${id}?readonly=true`)}
      />
    </div>
  );
};

const inputStyle = { padding: '8px', borderRadius: 4, border: '1px solid #4B5563', background: '#374151', color: 'white', flex: '1 1 150px' };
