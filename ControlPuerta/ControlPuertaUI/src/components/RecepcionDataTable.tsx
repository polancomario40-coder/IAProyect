import React, { useState, useEffect } from 'react';
import { consultarRecepciones, obtenerTicket } from '../services/puertaApi';
import { generarTicketPDF } from '../utils/TicketPrint';

export interface EntradaRow {
  idEntradaCamion: string;
  conduce: string;
  conduceTransporte?: string;
  placa: string;
  transportista: string;
  nombreChofer: string;
  fechaEntrada: string;
  status: string;
  ordenNumero: number | null;
  idEvidencia: string | null;
  proMov?: string;
  numRecepcionOC?: string;
  idProducto?: string;
  producto?: string;
  cantidadRecibida?: number;
  idUnidad?: string;
  idUnidadAlmacen?: string;
  cantidadAlmacen?: number;
  suplidor?: string;
}

interface Props {
  filtros: any;
  onVerDetalle: (id: string) => void;
}

const RecepcionDataTable: React.FC<Props> = ({ filtros, onVerDetalle }) => {
  const [data, setData] = useState<EntradaRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [imprimiendoId, setImprimiendoId] = useState<string | null>(null);

  const handleImprimir = async (id: string) => {
    try {
      setImprimiendoId(id);
      const res = await obtenerTicket(id);
      await generarTicketPDF(res.data.data);
    } catch (e) {
      alert('Error al generar el ticket.');
    } finally {
      setImprimiendoId(null);
    }
  };
  
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

  if (loading) return <div style={{ padding: 20, color: '#9CA3AF' }}>Cargando tabla...</div>;

  return (
    <div style={{ overflowX: 'auto', background: '#1F2937', borderRadius: 8, border: '1px solid #374151' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', color: '#F3F4F6', fontSize: '13px' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #374151', background: '#111827' }}>
            <th style={{ padding: 10, textAlign: 'left', fontWeight: 'bold' }}>Fecha</th>
            <th style={{ padding: 10, textAlign: 'left', fontWeight: 'bold' }}>Conduce</th>
            <th style={{ padding: 10, textAlign: 'left', fontWeight: 'bold' }}>Entrada Alm.</th>
            <th style={{ padding: 10, textAlign: 'left', fontWeight: 'bold' }}>Recepción OC</th>
            <th style={{ padding: 10, textAlign: 'left', fontWeight: 'bold' }}>OC</th>
            <th style={{ padding: 10, textAlign: 'left', fontWeight: 'bold' }}>Producto</th>
            <th style={{ padding: 10, textAlign: 'right', fontWeight: 'bold' }}>Cantidad</th>
            <th style={{ padding: 10, textAlign: 'left', fontWeight: 'bold' }}>Placa</th>
            <th style={{ padding: 10, textAlign: 'left', fontWeight: 'bold' }}>Transportista</th>
            <th style={{ padding: 10, textAlign: 'left', fontWeight: 'bold' }}>Status</th>
            <th style={{ padding: 10, textAlign: 'center', fontWeight: 'bold' }}>Acciones</th>
          </tr>
        </thead>
        <tbody>
          {data.map(row => (
            <tr key={row.idEntradaCamion} style={{ borderBottom: '1px solid #374151' }}>
              <td style={{ padding: 10 }}>{new Date(row.fechaEntrada).toLocaleString()}</td>
              <td style={{ padding: 10, fontWeight: 600 }}>
                {row.conduce}
                {row.conduceTransporte && (
                  <span style={{ display: 'block', fontSize: '11px', color: '#10B981', fontWeight: 'normal' }} title="Secuencia Almacén">
                    🎫 {row.conduceTransporte}
                  </span>
                )}
              </td>
              <td style={{ padding: 10, color: '#10B981', fontWeight: 600 }}>{(row as any).proMov || '-'}</td>
              <td style={{ padding: 10, color: '#3B82F6', fontWeight: 600 }}>{(row as any).numRecepcionOC || '-'}</td>
              <td style={{ padding: 10 }}>{row.ordenNumero ? `#${row.ordenNumero}` : '-'}</td>
              <td style={{ padding: 10, maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.producto || ''}>
                {row.producto ? (row.idProducto ? `[${row.idProducto}] ${row.producto}` : row.producto) : '-'}
              </td>
              <td style={{ padding: 10, textAlign: 'right', fontWeight: 600 }}>
                {row.cantidadRecibida != null ? `${row.cantidadRecibida} ${row.idUnidad || ''}` : '-'}
              </td>
              <td style={{ padding: 10 }}>{row.placa}</td>
              <td style={{ padding: 10 }}>{row.transportista}</td>
              <td style={{ padding: 10 }}>
                {row.status === 'PENDIENTE' && <span style={{color: '#F59E0B', fontWeight: 'bold'}}>{row.status}</span>}
                {row.status === 'RECIBIDO' && <span style={{color: '#3B82F6', fontWeight: 'bold'}}>{row.status}</span>}
                {row.status === 'CERRADO' && <span style={{color: '#10B981', fontWeight: 'bold'}}>{row.status}</span>}
                {row.status === 'BLOQUEADO' && <span style={{color: '#EF4444', fontWeight: 'bold'}}>{row.status}</span>}
                {row.status !== 'PENDIENTE' && row.status !== 'RECIBIDO' && row.status !== 'CERRADO' && row.status !== 'BLOQUEADO' && (
                  <span>{row.status}</span>
                )}
              </td>
              <td style={{ padding: 10, textAlign: 'center', whiteSpace: 'nowrap' }}>
                <div style={{ display: 'flex', gap: 6, justifyContent: 'center', alignItems: 'center' }}>
                  <button 
                    onClick={() => onVerDetalle(row.idEntradaCamion)}
                    style={{ padding: '4px 8px', cursor: 'pointer', background: '#374151', color: 'white', border: '1px solid #4B5563', borderRadius: 4, fontSize: '12px' }}
                    title="Ver Detalle"
                  >
                    Ver
                  </button>
                  <button 
                    onClick={() => handleImprimir(row.idEntradaCamion)}
                    disabled={imprimiendoId === row.idEntradaCamion}
                    style={{ 
                      padding: '4px 8px', 
                      cursor: imprimiendoId === row.idEntradaCamion ? 'wait' : 'pointer', 
                      background: '#059669', 
                      color: 'white', 
                      border: 'none', 
                      borderRadius: 4, 
                      fontSize: '12px', 
                      fontWeight: 'bold',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4
                    }}
                    title="Imprimir ticket completo (con todos los productos del conduce)"
                  >
                    {imprimiendoId === row.idEntradaCamion ? '...' : '🖨️ Ticket'}
                  </button>
                </div>
              </td>
            </tr>
          ))}
          {data.length === 0 && (
            <tr><td colSpan={11} style={{ padding: 25, textAlign: 'center', color: '#9CA3AF' }}>No hay registros para mostrar.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
};

export default RecepcionDataTable;
