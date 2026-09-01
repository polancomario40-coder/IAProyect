import React, { useState, useEffect } from 'react';
import { consultarRecepciones } from '../services/puertaApi';

export interface EntradaRow {
  idEntradaCamion: string;
  conduce: string;
  placa: string;
  transportista: string;
  nombreChofer: string;
  fechaEntrada: string;
  status: string;
  ordenNumero: number | null;
  idEvidencia: string | null;
}

interface Props {
  filtros: any;
  onVerDetalle: (id: string) => void;
}

const RecepcionDataTable: React.FC<Props> = ({ filtros, onVerDetalle }) => {
  const [data, setData] = useState<EntradaRow[]>([]);
  const [loading, setLoading] = useState(false);
  
  const cargar = async () => {
    setLoading(true);
    try {
      const queryFiltros = Object.fromEntries(Object.entries(filtros).filter(([_, v]) => v !== ''));
      const res = await consultarRecepciones(queryFiltros);
      setData(res.data.data.data || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    cargar();
  }, [filtros]);

  if (loading) return <div>Cargando tabla...</div>;

  return (
    <div style={{ overflowX: 'auto', background: '#1F2937', borderRadius: 8, border: '1px solid #374151' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', color: '#F3F4F6' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #374151', background: '#111827' }}>
            <th style={{ padding: 12, textAlign: 'left', fontWeight: 'bold' }}>Fecha</th>
            <th style={{ padding: 12, textAlign: 'left', fontWeight: 'bold' }}>Conduce</th>
            <th style={{ padding: 12, textAlign: 'left', fontWeight: 'bold' }}>Entrada Almacén</th>
            <th style={{ padding: 12, textAlign: 'left', fontWeight: 'bold' }}>Recepción OC</th>
            <th style={{ padding: 12, textAlign: 'left', fontWeight: 'bold' }}>Placa</th>
            <th style={{ padding: 12, textAlign: 'left', fontWeight: 'bold' }}>Transportista</th>
            <th style={{ padding: 12, textAlign: 'left', fontWeight: 'bold' }}>Status</th>
            <th style={{ padding: 12, textAlign: 'left', fontWeight: 'bold' }}>OC</th>
            <th style={{ padding: 12, textAlign: 'left', fontWeight: 'bold' }}>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {data.map(row => (
            <tr key={row.idEntradaCamion} style={{ borderBottom: '1px solid #374151' }}>
              <td style={{ padding: 12 }}>{new Date(row.fechaEntrada).toLocaleString()}</td>
              <td style={{ padding: 12 }}>{row.conduce}</td>
              <td style={{ padding: 12, color: '#10B981', fontWeight: 600 }}>{(row as any).proMov || '-'}</td>
              <td style={{ padding: 12, color: '#3B82F6', fontWeight: 600 }}>{(row as any).numRecepcionOC || '-'}</td>
              <td style={{ padding: 12 }}>{row.placa}</td>
              <td style={{ padding: 12 }}>{row.transportista}</td>
              <td style={{ padding: 12 }}>
                {row.status === 'PENDIENTE' && <span style={{color: '#F59E0B', fontWeight: 'bold'}}>{row.status}</span>}
                {row.status === 'RECIBIDO' && <span style={{color: '#3B82F6', fontWeight: 'bold'}}>{row.status}</span>}
                {row.status === 'CERRADO' && <span style={{color: '#10B981', fontWeight: 'bold'}}>{row.status}</span>}
                {row.status === 'BLOQUEADO' && <span style={{color: '#EF4444', fontWeight: 'bold'}}>{row.status}</span>}
              </td>
              <td style={{ padding: 12 }}>{row.ordenNumero || '-'}</td>
              <td style={{ padding: 12 }}>
                <button 
                  onClick={() => onVerDetalle(row.idEntradaCamion)}
                  style={{ padding: '4px 8px', cursor: 'pointer', background: '#374151', color: 'white', border: 'none', borderRadius: 4 }}
                >
                  Ver Detalle
                </button>
              </td>
            </tr>
          ))}
          {data.length === 0 && (
            <tr><td colSpan={7} style={{ padding: 20, textAlign: 'center' }}>No hay registros para mostrar.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
};

export default RecepcionDataTable;
