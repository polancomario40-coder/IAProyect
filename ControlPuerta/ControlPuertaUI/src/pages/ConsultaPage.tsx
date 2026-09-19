import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import RecepcionDataTable from '../components/RecepcionDataTable';
import { consultarRecepciones } from '../services/puertaApi';
import { exportarExcelAgregados, exportarExcelTransporte } from '../utils/excelExport';

export const ConsultaPage: React.FC = () => {
  const hoy = new Date().toISOString().split('T')[0];
  const haceUnMes = new Date();
  haceUnMes.setDate(haceUnMes.getDate() - 30);
  const fechaHaceUnMes = haceUnMes.toISOString().split('T')[0];

  const [filtros, setFiltros] = useState({
    fechaDesde: fechaHaceUnMes,
    fechaHasta: hoy,
    conduce: '',
    placa: '',
    transportista: '',
    status: '',
    pageNumber: 1,
    pageSize: 50
  });

  const [filtrosActivos, setFiltrosActivos] = useState(filtros);
  const [exportando, setExportando] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleBuscar = () => {
    let nuevosFiltros = { ...filtros };
    // Si están buscando por un conduce o placa específica, y tienen las fechas por defecto, 
    // limpiamos las fechas para buscar en todo el historial.
    if ((nuevosFiltros.conduce.trim() !== '' || nuevosFiltros.placa.trim() !== '') && 
        nuevosFiltros.fechaDesde === fechaHaceUnMes && 
        nuevosFiltros.fechaHasta === hoy) {
      nuevosFiltros.fechaDesde = '';
      nuevosFiltros.fechaHasta = '';
    }
    setFiltrosActivos({ ...nuevosFiltros, pageNumber: 1 });
  };

  const handleExportarExcel = async (tipo: 'agregados' | 'transporte') => {
    try {
      setExportando(tipo);
      const queryFiltros = {
        ...Object.fromEntries(Object.entries(filtrosActivos).filter(([_, v]) => v !== '')),
        pageNumber: 1,
        pageSize: 5000 // Obtener todos los registros del rango
      };

      const res = await consultarRecepciones(queryFiltros);
      const items = res.data?.data?.data || [];

      if (!items.length) {
        alert('No se encontraron registros para exportar con los filtros seleccionados.');
        return;
      }

      if (tipo === 'agregados') {
        exportarExcelAgregados(items, filtrosActivos.fechaDesde, filtrosActivos.fechaHasta);
      } else {
        exportarExcelTransporte(items, filtrosActivos.fechaDesde, filtrosActivos.fechaHasta);
      }
    } catch (error) {
      console.error('Error al exportar a Excel:', error);
      alert('Ocurrió un error al generar el reporte en Excel.');
    } finally {
      setExportando(null);
    }
  };

  return (
    <div style={{ padding: 20, color: '#F3F4F6' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 15 }}>
        <h2>Consulta Histórica</h2>
        
        {/* BOTONES DE REPORTES / EXCEL */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button
            onClick={() => handleExportarExcel('agregados')}
            disabled={!!exportando}
            style={{
              padding: '9px 16px',
              background: '#059669',
              color: 'white',
              border: 'none',
              borderRadius: 6,
              cursor: exportando ? 'not-allowed' : 'pointer',
              fontWeight: 'bold',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
            }}
          >
            📊 {exportando === 'agregados' ? 'Generando...' : 'Reporte Recepción Agregados (Excel)'}
          </button>

          <button
            onClick={() => handleExportarExcel('transporte')}
            disabled={!!exportando}
            style={{
              padding: '9px 16px',
              background: '#4F46E5',
              color: 'white',
              border: 'none',
              borderRadius: 6,
              cursor: exportando ? 'not-allowed' : 'pointer',
              fontWeight: 'bold',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
            }}
          >
            🚚 {exportando === 'transporte' ? 'Generando...' : 'Reporte Transporte (Excel)'}
          </button>
        </div>
      </div>
      
      <div style={{ background: '#1F2937', padding: 15, borderRadius: 8, marginBottom: 20, display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: '11px', color: '#9CA3AF' }}>Desde:</label>
          <input type="date" value={filtros.fechaDesde} onChange={e=>setFiltros({...filtros, fechaDesde: e.target.value})} style={inputStyle} />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: '11px', color: '#9CA3AF' }}>Hasta:</label>
          <input type="date" value={filtros.fechaHasta} onChange={e=>setFiltros({...filtros, fechaHasta: e.target.value})} style={inputStyle} />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: '1 1 120px' }}>
          <label style={{ fontSize: '11px', color: '#9CA3AF' }}>Conduce:</label>
          <input placeholder="Buscar conduce..." value={filtros.conduce} onChange={e=>setFiltros({...filtros, conduce: e.target.value})} style={inputStyle} />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: '1 1 120px' }}>
          <label style={{ fontSize: '11px', color: '#9CA3AF' }}>Placa:</label>
          <input placeholder="Buscar placa..." value={filtros.placa} onChange={e=>setFiltros({...filtros, placa: e.target.value})} style={inputStyle} />
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: '1 1 140px' }}>
          <label style={{ fontSize: '11px', color: '#9CA3AF' }}>Estado:</label>
          <select value={filtros.status} onChange={e=>setFiltros({...filtros, status: e.target.value})} style={inputStyle}>
            <option value="">-- Todos --</option>
            <option value="PENDIENTE">Pendiente</option>
            <option value="RECIBIDO">Recibido</option>
            <option value="CERRADO">Cerrado</option>
            <option value="BLOQUEADO">Bloqueado</option>
          </select>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', marginTop: 'auto' }}>
          <button onClick={handleBuscar} style={{ padding: '9px 20px', background: '#3B82F6', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 'bold' }}>
            🔍 Buscar
          </button>
        </div>
      </div>

      <RecepcionDataTable 
        filtros={filtrosActivos} 
        onVerDetalle={(id) => navigate(`/recepcion/${id}?readonly=true`)}
      />
    </div>
  );
};

const inputStyle = { padding: '8px', borderRadius: 4, border: '1px solid #4B5563', background: '#374151', color: 'white' };

