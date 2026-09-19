import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import CamaraCaptura from '../components/CamaraCaptura';
import { useAuth } from '../contexts/AuthContext';
import { ocrPlaca, validarTransportista, registrarEntrada, obtenerEntradasHoy, listarProductos, cancelarEntrada, buscarPlacas, buscarChoferes } from '../services/puertaApi';

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
  const [idChoferSel, setIdChoferSel] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [entradasHoy, setEntradasHoy] = useState<any[]>([]);
  const [busquedaPendientes, setBusquedaPendientes] = useState('');
  const [fotoPlacaBase64, setFotoPlacaBase64] = useState<string>('');
  const [fotoPlacaMime, setFotoPlacaMime] = useState<string>('');
  const [busquedaChofer, setBusquedaChofer] = useState('');
  const [mostrarChoferes, setMostrarChoferes] = useState(false);
  const [choferesEncontrados, setChoferesEncontrados] = useState<any[]>([]);
  const [buscandoChofer, setBuscandoChofer] = useState(false);
  
  const navigate = useNavigate();

  const cargarDatos = async () => {
    try {
      setLoading(true);
      const res = await obtenerEntradasHoy();
      setEntradasHoy(res.data.data.filter((e: any) => e.status === 'PENDIENTE') || []);
      const prodRes = await listarProductos();
      setProductosLista(prodRes.data.data || []);
    } catch (error: any) {
      console.error('Error cargando datos');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { cargarDatos(); }, []);

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

  useEffect(() => {
    if (busquedaChofer.trim().length < 2) {
      setChoferesEncontrados([]);
      setMostrarChoferes(false);
      return;
    }
    const timer = setTimeout(async () => {
      setBuscandoChofer(true);
      try {
        const res = await buscarChoferes(busquedaChofer.trim());
        setChoferesEncontrados(res.data?.data || []);
        setMostrarChoferes(true);
      } catch {
        setChoferesEncontrados([]);
      } finally {
        setBuscandoChofer(false);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [busquedaChofer]);

  const handleOcr = async (base64: string, mime: string) => {
    setLoading(true);
    setFotoPlacaBase64(base64);
    setFotoPlacaMime(mime);
    try {
      const resOcr = await ocrPlaca(base64, mime);
      if (resOcr.data.success && resOcr.data.data?.textoDetectado) {
        const detected = resOcr.data.data.textoDetectado;
        setPlaca(detected);
        try {
          const res = await validarTransportista(detected);
          if (res.data.success) { setTransportista(res.data.data); setIdChoferSel(''); setBusquedaChofer(''); }
        } catch { setTransportista(null); setIdChoferSel(''); setBusquedaChofer(''); }
      }
    } catch (error) { console.warn('OCR no disponible:', error); }
    finally { setLoading(false); }
  };

  const handleValidar = async () => {
    if (!placa) return alert('Ingrese la placa');
    setLoading(true);
    try {
      const res = await validarTransportista(placa);
      if (res.data.success) { setTransportista(res.data.data); setIdChoferSel(''); setBusquedaChofer(''); }
    } catch (error: any) {
      setTransportista(null); setIdChoferSel(''); setBusquedaChofer('');
      alert(error.response?.data?.mensaje || 'Transportista no encontrado');
    } finally { setLoading(false); }
  };

  const handleGuardar = async () => {
    if (!fotoPlacaBase64) return alert('Es obligatorio tomar la foto de la placa/camion antes de registrar la entrada.');
    if (!conduce || !producto || !transportista) return alert('Complete todos los campos');
    setLoading(true);
    try {
      const payload = {
        conduce, placa,
        fotoPlacaBase64: fotoPlacaBase64 || null,
        fotoPlacaMime: fotoPlacaMime || null,
        idTransportista: transportista.idTransportista,
        transportista: transportista.nombre,
        idChofer: idChoferSel || null,
        nombreChofer: busquedaChofer || '',
        idProducto: productosLista.find((p: any) => p.idProductoPuerta === producto)?.idProducto || producto,
        producto: productosLista.find((p: any) => p.idProductoPuerta === producto)?.nombre || producto,
        cantidadDeclarada: transportista.capacidad || null,
        productos: [{ 
          idProducto: productosLista.find((p: any) => p.idProductoPuerta === producto)?.idProducto || producto, 
          producto: productosLista.find((p: any) => p.idProductoPuerta === producto)?.nombre || producto, cantidad: 1 
        }]
      };
      const res = await registrarEntrada(payload);
      if (res.data.success) {
        alert('Entrada registrada');
        setPlaca(''); setConduce(''); setProducto(''); setTransportista(null);
        setIdChoferSel(''); setBusquedaChofer(''); setFotoPlacaBase64(''); setFotoPlacaMime('');
        cargarDatos();
      }
    } catch (error: any) { alert(error.response?.data?.mensaje || 'Error registrando entrada'); }
    finally { setLoading(false); }
  };

  const handleCancelar = async (id: string) => {
    if (!window.confirm('Esta seguro que desea cancelar esta entrada?')) return;
    try { await cancelarEntrada(id); cargarDatos(); }
    catch (error: any) { alert(error.response?.data?.mensaje || 'Error al cancelar la entrada'); }
  };

  const entradasFiltradas = entradasHoy.filter((e: any) => 
    e.placa.toLowerCase().includes(busquedaPendientes.toLowerCase()) || 
    e.conduce.toLowerCase().includes(busquedaPendientes.toLowerCase())
  );

  return (
    <div style={{ padding: 20, color: '#F3F4F6' }}>
      <h2>Inicio de Operaciones</h2>
      {!hasPuerta && !hasRecepcion && (
        <div style={{ background: '#374151', padding: 20, borderRadius: 8, textAlign: 'center' }}>
          <p>No tiene permisos asignados para acceder a Control de Puerta ni a Recepcion.</p>
        </div>
      )}
      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
        {hasPuerta && (
          <div style={{ flex: 1, minWidth: 300, background: '#1F2937', padding: 20, borderRadius: 8 }}>
            <h3>Registrar Entrada (Control Puerta)</h3>
            <CamaraCaptura onCaptura={handleOcr} label="Capturar Placa (IA)" />
            {fotoPlacaBase64 ? (
              <span style={{ color: '#10B981', fontSize: 13, display: 'block', marginTop: 6, fontWeight: 'bold' }}>Foto de la placa tomada con exito</span>
            ) : (
              <span style={{ color: '#F87171', fontSize: 13, display: 'block', marginTop: 6, fontWeight: 'bold' }}>Foto obligatoria: Debe tomar la foto con la camara antes de guardar.</span>
            )}
            <div style={{ marginTop: 20 }}>
              <label>Placa:</label>
              <div style={{ display: 'flex', gap: 10, position: 'relative' }}>
                <input value={placa} onChange={e => { setPlaca(e.target.value.toUpperCase()); setTransportista(null); }} 
                  style={{ ...inputStyle, textTransform: 'uppercase' }} placeholder="Ej. L123456" 
                  onFocus={() => { if(placasRes.length > 0) setMostrarPlacasList(true) }}
                  onBlur={() => setTimeout(() => setMostrarPlacasList(false), 200)} />
                <button onClick={handleValidar} disabled={loading} style={btnStyle}>Validar</button>
                {mostrarPlacasList && placasRes.length > 0 && (
                  <ul style={{ position: 'absolute', top: 45, left: 0, right: 90, background: 'white', color: 'black', listStyle: 'none', padding: 0, margin: 0, maxHeight: 200, overflowY: 'auto', zIndex: 10, borderRadius: 4, border: '1px solid #ccc' }}>
                    {placasRes.map((p, idx) => (
                      <li key={idx} onMouseDown={() => { setPlaca(p); setMostrarPlacasList(false); }} style={{ padding: 10, cursor: 'pointer', borderBottom: '1px solid #ccc' }}>{p}</li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            {transportista && (
              <div style={{ marginTop: 20, background: '#111827', padding: 15, borderRadius: 8, border: '1px solid #374151' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 5, borderBottom: '1px solid #374151', paddingBottom: 10, marginBottom: 15 }}>
                  <p style={{margin: 0}}>Transportista: <strong>{transportista.nombre}</strong></p>
                  <p style={{margin: 0}}>Equipo: <strong>{transportista.nombreEquipo}</strong></p>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                  <div style={{ gridColumn: '1 / -1', position: 'relative' }}>
                    <label style={{ display: 'block', marginBottom: 5 }}>
                      Chofer del Camion (Todos):
                      {idChoferSel && <span style={{ color: '#10B981', marginLeft: 8, fontSize: 12 }}>Seleccionado</span>}
                    </label>
                    <input type="text" value={busquedaChofer}
                      onChange={(e) => { setBusquedaChofer(e.target.value); setIdChoferSel(''); }}
                      onFocus={() => { if (choferesEncontrados.length > 0) setMostrarChoferes(true); }}
                      onBlur={() => setTimeout(() => setMostrarChoferes(false), 200)}
                      placeholder="Escriba al menos 2 letras del nombre del chofer..."
                      style={{ ...inputStyle, width: '100%', boxSizing: 'border-box' as any,
                        borderColor: idChoferSel ? '#10B981' : '#4B5563' }} />
                    {buscandoChofer && <span style={{ position: 'absolute', right: 10, top: 38, color: '#9CA3AF', fontSize: 12 }}>Buscando...</span>}
                    {mostrarChoferes && choferesEncontrados.length > 0 && (
                      <ul style={{ position: 'absolute', top: 65, left: 0, right: 0, background: 'white', color: 'black', listStyle: 'none', padding: 0, margin: 0, maxHeight: 220, overflowY: 'auto', zIndex: 10, borderRadius: 4, border: '1px solid #ccc', boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}>
                        {choferesEncontrados.map((c: any) => (
                          <li key={c.idChofer} onMouseDown={() => { setIdChoferSel(c.idChofer); setBusquedaChofer(c.nombre); setMostrarChoferes(false); }} 
                              style={{ padding: '8px 12px', cursor: 'pointer', borderBottom: '1px solid #eee' }}>
                            <strong style={{ display: 'block' }}>{c.nombre}</strong>
                            {c.transportistaNombre && <span style={{ color: '#555', fontSize: 12 }}>Transportista: {c.transportistaNombre}</span>}
                            {c.licenciaNo && <span style={{ color: '#888', fontSize: 11, marginLeft: 8 }}>Lic: {c.licenciaNo}</span>}
                          </li>
                        ))}
                      </ul>
                    )}
                    {mostrarChoferes && choferesEncontrados.length === 0 && !buscandoChofer && busquedaChofer.trim().length >= 2 && (
                      <div style={{ position: 'absolute', top: 65, left: 0, right: 0, background: 'white', color: '#666', padding: 12, border: '1px solid #ccc', borderRadius: 4, fontSize: 13, zIndex: 10 }}>
                        No se encontraron choferes. Puede escribir el nombre manualmente.
                      </div>
                    )}
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: 5 }}>Numero de Conduce:</label>
                    <input value={conduce} onChange={e=>setConduce(e.target.value)} style={{ ...inputStyle, marginTop: 0 }} />
                  </div>
                  <div>
                    <label style={{ display: 'block', marginBottom: 5 }}>Producto a recibir:</label>
                    <select value={producto} onChange={e=>setProducto(e.target.value)} style={{ ...inputStyle, marginTop: 0 }}>
                      <option value="">-- Seleccione --</option>
                      {productosLista.map(p => (<option key={p.idProductoPuerta} value={p.idProductoPuerta}>{p.nombre}</option>))}
                    </select>
                  </div>
                </div>
                <button onClick={handleGuardar} disabled={loading} style={{...btnStyle, marginTop: 20, width: '100%', background: '#10B981', fontSize: 16, padding: 15}}>
                  {loading ? 'Guardando...' : 'Registrar Entrada'}
                </button>
              </div>
            )}
          </div>
        )}
        {hasRecepcion && (
          <div style={{ flex: 1, minWidth: 300, background: '#1F2937', padding: 20, borderRadius: 8 }}>
            <h3>Camiones Pendientes de Recepción</h3>
            <input type="text" placeholder="Buscar por placa o conduce..." value={busquedaPendientes}
              onChange={(e) => setBusquedaPendientes(e.target.value)} style={{ ...inputStyle, marginBottom: 15 }} />
            <ul style={{ listStyle: 'none', padding: 0 }}>
              {entradasFiltradas.map((e: any) => (
                <li key={e.idEntradaCamion} style={{ padding: 10, borderBottom: '1px solid #374151', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <strong>{e.conduce}</strong> - {e.placa} <br/>
                    <small style={{ color: '#9CA3AF' }}>
                      {new Date(e.fechaEntrada).toLocaleDateString()} {new Date(e.fechaEntrada).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} | {e.producto}
                    </small>
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
