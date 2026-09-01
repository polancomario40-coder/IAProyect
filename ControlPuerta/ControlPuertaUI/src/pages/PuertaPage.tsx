import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import CamaraCaptura from '../components/CamaraCaptura';
import { useAuth } from '../contexts/AuthContext';
import { ocrPlaca, validarTransportista, registrarEntrada, obtenerEntradasHoy, listarProductos, cancelarEntrada, buscarPlacas } from '../services/puertaApi';

export const PuertaPage: React.FC = () => {
  const { roles } = useAuth();
  const hasPuerta = roles.includes('controlpuerta') || roles.includes('controlalmacen');
  const hasRecepcion = roles.includes('controlrecepcion') || roles.includes('controlalmacen');
  const [placa, setPlaca] = useState('');
  const [placasRes, setPlacasRes] = useState<string[]>([]);
  const [mostrarPlacasList, setMostrarPlacasList] = useState(false);
  const [conduce, setConduce] = useState('');
  const [producto, setProducto] = useState('');
  const [productosLista, setProductosLista] = useState<any[]>([]);
  const [transportista, setTransportista] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [entradasHoy, setEntradasHoy] = useState<any[]>([]);
  const [busquedaPendientes, setBusquedaPendientes] = useState('');
  const navigate = useNavigate();

  const cargarDatos = async () => {
    try {
      const res = await obtenerEntradasHoy();
      // Filtrar solo las pendientes
      setEntradasHoy(res.data.data.filter((e: any) => e.status === 'PENDIENTE'));
      
      const resProd = await listarProductos();
      setProductosLista(resProd.data.data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    cargarDatos();
  }, []);

  // Debounce para autocompletar placas
  useEffect(() => {
    const timer = setTimeout(() => {
      if (placa.length >= 2 && !transportista) {
        buscarPlacas(placa).then(res => {
          setPlacasRes(res.data.data || []);
          setMostrarPlacasList(true);
        }).catch(console.error);
      } else {
        setMostrarPlacasList(false);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [placa, transportista]);

  const handleOcr = async (base64: string, mime: string) => {
    setLoading(true);
    try {
      const res = await ocrPlaca(base64, mime);
      if (res.data.success && res.data.data.exito) {
        setPlaca(res.data.data.textoDetectado);
        alert(`Placa detectada: ${res.data.data.textoDetectado}`);
      } else {
        alert(res.data.data.mensaje || 'No se pudo leer la placa');
      }
    } catch (error: any) {
      alert(error.response?.data?.mensaje || 'Error procesando OCR');
    } finally {
      setLoading(false);
    }
  };

  const handleValidar = async () => {
    if (!placa) return alert('Ingrese la placa');
    setLoading(true);
    try {
      const res = await validarTransportista(placa);
      if (res.data.success) {
        setTransportista(res.data.data);
      }
    } catch (error: any) {
      setTransportista(null);
      alert(error.response?.data?.mensaje || 'Transportista no encontrado');
    } finally {
      setLoading(false);
    }
  };

  const handleGuardar = async () => {
    if (!conduce || !producto || !transportista) return alert('Complete todos los campos');
    setLoading(true);
    try {
      const payload = {
        conduce,
        placa,
        idTransportista: transportista.idTransportista,
        transportista: transportista.nombre,
        idChofer: transportista.choferes?.[0]?.idChofer,
        nombreChofer: transportista.choferes?.[0]?.nombre,
        idProducto: productosLista.find((p: any) => p.idProductoPuerta === producto)?.idProducto || producto,
        producto: productosLista.find((p: any) => p.idProductoPuerta === producto)?.nombre || producto,
        cantidadDeclarada: transportista.capacidad || null,
        productos: [{ 
          idProducto: productosLista.find((p: any) => p.idProductoPuerta === producto)?.idProducto || producto, 
          producto: productosLista.find((p: any) => p.idProductoPuerta === producto)?.nombre || producto, 
          cantidad: 1 
        }]
      };
      
      const res = await registrarEntrada(payload);
      if (res.data.success) {
        alert('Entrada registrada');
        setPlaca(''); setConduce(''); setProducto(''); setTransportista(null);
        cargarDatos();
      }
    } catch (error: any) {
      alert(error.response?.data?.mensaje || 'Error registrando entrada');
    } finally {
      setLoading(false);
    }
  };

  const handleCancelar = async (id: string) => {
    if (!window.confirm('¿Está seguro que desea cancelar esta entrada?')) return;
    try {
      await cancelarEntrada(id);
      cargarDatos();
    } catch (error: any) {
      alert(error.response?.data?.mensaje || 'Error al cancelar la entrada');
    }
  };

  const entradasFiltradas = entradasHoy.filter(e => 
    e.placa.toLowerCase().includes(busquedaPendientes.toLowerCase()) || 
    e.conduce.toLowerCase().includes(busquedaPendientes.toLowerCase())
  );

  return (
    <div style={{ padding: 20, color: '#F3F4F6' }}>
      <h2>Inicio de Operaciones</h2>
      
      {!hasPuerta && !hasRecepcion && (
        <div style={{ background: '#374151', padding: 20, borderRadius: 8, textAlign: 'center' }}>
          <p>No tiene permisos asignados para acceder a Control de Puerta ni a Recepción.</p>
        </div>
      )}

      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
        {hasPuerta && (
          <div style={{ flex: 1, minWidth: 300, background: '#1F2937', padding: 20, borderRadius: 8 }}>
            <h3>Registrar Entrada (Control Puerta)</h3>
            
            <CamaraCaptura onCaptura={handleOcr} label="Capturar Placa (IA)" />
            
            <div style={{ marginTop: 20 }}>
              <label>Placa:</label>
              <div style={{ display: 'flex', gap: 10, position: 'relative' }}>
                <input 
                  value={placa} 
                  onChange={e => { setPlaca(e.target.value.toUpperCase()); setTransportista(null); }} 
                  style={{ ...inputStyle, textTransform: 'uppercase' }} 
                  placeholder="Ej. L123456" 
                  onFocus={() => { if(placasRes.length > 0) setMostrarPlacasList(true) }}
                  onBlur={() => setTimeout(() => setMostrarPlacasList(false), 200)}
                />
                <button onClick={handleValidar} disabled={loading} style={btnStyle}>Validar</button>

                {mostrarPlacasList && placasRes.length > 0 && (
                  <ul style={{ position: 'absolute', top: 45, left: 0, right: 90, background: 'white', color: 'black', listStyle: 'none', padding: 0, margin: 0, maxHeight: 200, overflowY: 'auto', zIndex: 10, borderRadius: 4, border: '1px solid #ccc' }}>
                    {placasRes.map((p, idx) => (
                      <li key={idx} onMouseDown={() => { setPlaca(p); setMostrarPlacasList(false); }} style={{ padding: 10, cursor: 'pointer', borderBottom: '1px solid #ccc' }}>
                        {p}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            {transportista && (
              <div style={{ marginTop: 20, background: '#111827', padding: 10, borderRadius: 4 }}>
                <p>✅ <strong>Transportista:</strong> {transportista.nombre}</p>
                <p>🚚 <strong>Equipo:</strong> {transportista.nombreEquipo}</p>
                
                <div style={{ marginTop: 15 }}>
                  <label>Número de Conduce:</label>
                  <input value={conduce} onChange={e=>setConduce(e.target.value)} style={inputStyle} />
                </div>
                
                <div style={{ marginTop: 15 }}>
                  <label>Producto a recibir:</label>
                  <select value={producto} onChange={e=>setProducto(e.target.value)} style={inputStyle}>
                    <option value="">-- Seleccione un producto --</option>
                    {productosLista.map(p => (
                      <option key={p.idProductoPuerta} value={p.idProductoPuerta}>{p.nombre}</option>
                    ))}
                  </select>
                </div>
                
                <button onClick={handleGuardar} disabled={loading} style={{...btnStyle, marginTop: 20, width: '100%', background: '#10B981'}}>
                  {loading ? 'Guardando...' : 'Registrar Entrada'}
                </button>
              </div>
            )}
          </div>
        )}

        {hasRecepcion && (
          <div style={{ flex: 1, minWidth: 300, background: '#1F2937', padding: 20, borderRadius: 8 }}>
            <h3>Entradas de Hoy (Recepción)</h3>
            
            <input 
              type="text"
              placeholder="Buscar por placa o conduce..."
              value={busquedaPendientes}
              onChange={(e) => setBusquedaPendientes(e.target.value)}
              style={{ ...inputStyle, marginBottom: 15 }}
            />

            <ul style={{ listStyle: 'none', padding: 0 }}>
              {entradasFiltradas.map((e: any) => (
                <li key={e.idEntradaCamion} style={{ padding: 10, borderBottom: '1px solid #374151', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <strong>{e.conduce}</strong> - {e.placa} <br/>
                    <small style={{ color: '#9CA3AF' }}>{new Date(e.fechaEntrada).toLocaleTimeString()} | {e.producto}</small>
                  </div>
                  <div style={{ display: 'flex', gap: 5 }}>
                    <button onClick={() => navigate(`/recepcion/${e.idEntradaCamion}`)} style={btnStyle}>Recibir</button>
                    <button onClick={() => handleCancelar(e.idEntradaCamion)} style={{...btnStyle, background: '#EF4444'}}>Cancelar</button>
                  </div>
                </li>
              ))}
              {entradasFiltradas.length === 0 && <p>No hay camiones pendientes.</p>}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

const inputStyle = { width: '100%', padding: 10, marginTop: 5, borderRadius: 4, border: '1px solid #4B5563', background: '#374151', color: 'white' };
const btnStyle = { padding: '10px 15px', background: '#3B82F6', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' };
