import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { obtenerRecepcion, confirmarRecepcion, notificarRecepcion, obtenerTicket, buscarSuplidores, listarAlmacenes, extraerTextoPlaca, descargarEvidencia } from '../services/puertaApi';
import CamaraCaptura from '../components/CamaraCaptura';
import FirmaCanvas from '../components/FirmaCanvas';
import { generarTicketPDF } from '../utils/TicketPrint';

export const RecepcionPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const queryParams = new URLSearchParams(location.search);
  const isReadonly = queryParams.get('readonly') === 'true';
  
  const [entrada, setEntrada] = useState<any>(null);
  const [fotoConduce, setFotoConduce] = useState<string>('');
  const [fotoMime, setFotoMime] = useState<string>('image/jpeg');
  const [firma, setFirma] = useState<string>('');
  const [metros, setMetros] = useState<string>('');
  const [loading, setLoading] = useState(false);

  // Nuevos campos
  const [conduceAgregado, setConduceAgregado] = useState<string>('');
  const [conduceTransporte, setConduceTransporte] = useState<string>('');
  
  // OCR conduce agregado
  const [ocrConduceLoading, setOcrConduceLoading] = useState(false);

  // Evidencias (solo lectura)
  const [urlFoto, setUrlFoto] = useState<string | null>(null);
  const [urlFirma, setUrlFirma] = useState<string | null>(null);
  const [cargandoEvidencia, setCargandoEvidencia] = useState(false);

  // Almacenes
  const [almacenes, setAlmacenes] = useState<any[]>([]);
  const [idAlmacen, setIdAlmacen] = useState<string>('');

  // Autocomplete Suplidor
  const [qSuplidor, setQSuplidor] = useState('');
  const [suplidoresRes, setSuplidoresRes] = useState<any[]>([]);
  const [suplidorSel, setSuplidorSel] = useState<any>(null);
  const [mostrarSupList, setMostrarSupList] = useState(false);
  const [isSupFocused, setIsSupFocused] = useState(false);

  // Autocomplete Producto Real (Materia Prima ERP)
  const [qProductoReal, setQProductoReal] = useState('');
  const [productosRealesRes, setProductosRealesRes] = useState<any[]>([]);
  const [productoRealSel, setProductoRealSel] = useState<any>(null);
  const [mostrarProdList, setMostrarProdList] = useState(false);
  const [isProdFocused, setIsProdFocused] = useState(false);

  useEffect(() => {
    if (id) {
      obtenerRecepcion(id).then(res => {
        setEntrada(res.data.data);
        setConduceAgregado(res.data.data.conduce || '');
        setQProductoReal(''); // Dejar vacio para obligar a buscar el producto real
      }).catch(console.error);
    }
    listarAlmacenes().then(res => {
      const lista = res.data.data;
      setAlmacenes(lista);
      // Auto-seleccionar si el usuario solo tiene permiso a un almacén
      if (lista.length === 1) setIdAlmacen(lista[0].idAlmacen);
    }).catch(console.error);
  }, [id]);

  // Debounce para buscar suplidores
  useEffect(() => {
    const timer = setTimeout(() => {
      if (qSuplidor && !suplidorSel) {
        buscarSuplidores(qSuplidor).then(res => {
          setSuplidoresRes(res.data.data);
          if (isSupFocused) setMostrarSupList(true);
        }).catch(console.error);
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [qSuplidor, isSupFocused, suplidorSel]);

  // Debounce para buscar productos reales
  useEffect(() => {
    const timer = setTimeout(() => {
      import('../services/puertaApi').then(({ buscarProductosReales }) => {
        if (qProductoReal && !productoRealSel) {
          buscarProductosReales(qProductoReal).then(res => {
            setProductosRealesRes(res.data.data);
            if (isProdFocused) setMostrarProdList(true);
          }).catch(console.error);
        }
      });
    }, 500);
    return () => clearTimeout(timer);
  }, [qProductoReal, isProdFocused, productoRealSel]);

  const seleccionarSuplidor = (sup: any) => {
    setSuplidorSel(sup);
    setQSuplidor(sup.nombre);
    setMostrarSupList(false);
  };

  const seleccionarProductoReal = (prod: any) => {
    setProductoRealSel(prod);
    setQProductoReal(prod.nombre);
    setMostrarProdList(false);
  };

  // OCR para capturar el número de conduce desde una foto
  const handleOcrConduce = async (b64: string, mime: string) => {
    try {
      setOcrConduceLoading(true);
      const res = await extraerTextoPlaca(b64, mime);
      const texto = res.data?.data?.textoDetectado || '';
      if (texto) {
        // Limpiar el texto: solo números y letras, eliminar espacios
        const limpio = texto.replace(/[^A-Za-z0-9\-]/g, '').trim();
        setConduceAgregado(limpio || texto.trim());
        alert(`Texto detectado: ${limpio || texto.trim()}`);
      } else {
        alert('No se detectó texto en la imagen. Ingrese el número manualmente.');
      }
    } catch (e) {
      console.error(e);
      alert('Error al leer el conduce. Ingrese el número manualmente.');
    } finally {
      setOcrConduceLoading(false);
    }
  };

  const handleCargarEvidencias = async () => {
    if (!id) return;
    setCargandoEvidencia(true);
    try {
      const resFoto = await descargarEvidencia(id, 'foto').catch(() => null);
      if (resFoto?.data) setUrlFoto(URL.createObjectURL(resFoto.data));

      const resFirma = await descargarEvidencia(id, 'firmada').catch(() => null);
      if (resFirma?.data) setUrlFirma(URL.createObjectURL(resFirma.data));
    } catch (error) {
      console.error(error);
    } finally {
      setCargandoEvidencia(false);
    }
  };

  const handleGuardar = async () => {
    if (!id) return;
    if (!conduceAgregado || conduceAgregado.length < 4) return alert('El Número de Conduce del Agregado es obligatorio y debe tener al menos 4 caracteres.');
    if (!conduceTransporte || conduceTransporte.length < 4) return alert('El Número de Conduce del Transporte es obligatorio y debe tener al menos 4 caracteres.');
    if (!suplidorSel?.idSuplidor) return alert('Debe seleccionar el Suplidor del Agregado.');
    if (!productoRealSel?.idProducto) return alert('Debe buscar y seleccionar el Producto Físico de Materia Prima en el ERP.');
    if (!idAlmacen) return alert('Debe seleccionar el Almacén de destino.');

    if (conduceAgregado === conduceTransporte) {
      if (!window.confirm('¡ATENCIÓN! Los números de conduce de Agregado y Transporte son iguales. ¿Está seguro de que desea continuar?')) {
        return;
      }
    }

    const qty = Number(metros);
    const declared = Number(entrada.cantidadDeclarada || 0);
    if (Math.abs(qty - declared) > 2) {
      if (!window.confirm(`La cantidad recibida (${qty} Mts) difiere en más de 2 metros de la capacidad declarada (${declared} Mts). ¿Desea continuar?`)) {
        return;
      }
    }

    setLoading(true);
    try {
      // Unir firma y foto conduces en un array (Fase 3 pedía combinarlos en Canvas, pero temporalmente los enviamos separados)
      const evidencias = [];
      if (fotoConduce) evidencias.push(`data:${fotoMime};base64,${fotoConduce}`);
      if (firma) evidencias.push(firma);

      await confirmarRecepcion(id, {
        idEntradaCamion: id,
        conduce: conduceAgregado,
        conduceTransporte: conduceTransporte,
        cantidadRecibida: qty,
        idSuplidor: suplidorSel.idSuplidor,
        nombreSuplidor: suplidorSel.nombre,
        idProductoReal: productoRealSel.idProducto,
        nombreProductoReal: productoRealSel.nombre,
        idAlmacen: idAlmacen,
        notas: 'Recibido vía web',
        evidenciasBase64: evidencias
      });
      
      const notifRes = await notificarRecepcion(id, { emailDestinatario: 'proveedor@test.com' });
      if (notifRes.data.success) {
        alert('Recepción confirmada y correo enviado');
      }

      const ticketRes = await obtenerTicket(id);
      await generarTicketPDF(ticketRes.data.data);

      navigate('/');
    } catch (error: any) {
      alert(error.response?.data?.mensaje || 'Error al procesar recepción');
    } finally {
      setLoading(false);
    }
  };

  if (!entrada) return <div style={{ color: 'white', padding: 20 }}>Cargando...</div>;

  if (isReadonly && entrada.status === 'PENDIENTE') {
    return (
      <div style={{ padding: 20, color: '#F3F4F6', maxWidth: 800, margin: '0 auto' }}>
        <h2>Detalle de la Recepción</h2>
        <div style={{ background: '#1F2937', padding: 20, borderRadius: 8 }}>
          <p style={{ fontSize: 16 }}>Esta entrada de <strong>{entrada.producto}</strong> del transportista <strong>{entrada.transportista}</strong> (Placa: {entrada.placa}) se encuentra en estado <strong>PENDIENTE</strong> de ser recibida en almacén.</p>
          <button onClick={() => navigate('/consulta')} style={{ marginTop: 20, padding: '8px 16px', background: '#3B82F6', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
            Volver a Consulta
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: 20, color: '#F3F4F6', maxWidth: 800, margin: '0 auto' }}>
      <h2>Recepción de Conduce</h2>
      
      {entrada.status === 'PENDIENTE' ? (
        <div style={{ background: '#1F2937', padding: 20, borderRadius: 8 }}>
          
          <div style={{ display: 'flex', gap: 15, marginBottom: 15 }}>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>Fecha de Llegada</label>
              <input type="text" value={new Date(entrada.fechaEntrada).toLocaleString()} readOnly style={{...inputStyle, background: '#4B5563'}} />
            </div>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>Conduce Agregado</label>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input 
                  type="text" 
                  value={conduceAgregado} 
                  onChange={e => setConduceAgregado(e.target.value)} 
                  style={{...inputStyle, flex: 1, marginBottom: 0}} 
                  placeholder="Mínimo 4 caracteres" 
                />
                <CamaraCaptura
                  label=""
                  soloBoton
                  onCaptura={handleOcrConduce}
                  ocr
                />
                {ocrConduceLoading && <span style={{ color: '#60A5FA', fontSize: 12 }}>Leyendo...</span>}
              </div>
            </div>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>Conduce Transporte</label>
              <input type="text" value={conduceTransporte} onChange={e=>setConduceTransporte(e.target.value)} style={inputStyle} placeholder="Mínimo 4 caracteres" />
            </div>
          </div>

          {conduceAgregado && conduceTransporte && conduceAgregado === conduceTransporte && (
            <div style={{ marginBottom: 15, padding: 10, background: 'rgba(239, 68, 68, 0.2)', border: '1px solid #EF4444', borderRadius: 4, color: '#FCA5A5', fontSize: 14 }}>
              <strong>¡Aviso!</strong> Los números de conduce son iguales. Verifique que no sea un error antes de continuar.
            </div>
          )}

          <div style={{ display: 'flex', gap: 15, marginBottom: 15 }}>
            <div style={{ flex: 2, position: 'relative' }}>
              <label style={labelStyle}>Suplidor (Buscar)</label>
              <input 
                type="text" 
                value={qSuplidor}
                onChange={e => { setQSuplidor(e.target.value); setSuplidorSel(null); }}
                onBlur={() => { setIsSupFocused(false); setTimeout(() => setMostrarSupList(false), 200); }}
                onFocus={() => { setIsSupFocused(true); if(suplidoresRes.length > 0) setMostrarSupList(true); }}
                style={inputStyle}
                placeholder="Escriba para buscar..."
              />
              {mostrarSupList && suplidoresRes.length > 0 && (
                <ul style={{ position: 'absolute', top: 65, left: 0, right: 0, background: 'white', color: 'black', listStyle: 'none', padding: 0, margin: 0, maxHeight: 200, overflowY: 'auto', zIndex: 10, borderRadius: 4, boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}>
                  {suplidoresRes.map(s => (
                    <li key={s.idSuplidor} onMouseDown={() => seleccionarSuplidor(s)} style={{ padding: 10, cursor: 'pointer', borderBottom: '1px solid #ccc' }}>
                      {s.nombre}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>Almacén</label>
              <select value={idAlmacen} onChange={e=>setIdAlmacen(e.target.value)} style={inputStyle}>
                <option value="">[Por Defecto]</option>
                {almacenes.map(a => (
                  <option key={a.idAlmacen} value={a.idAlmacen}>{a.nombre}</option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ marginBottom: 20 }}>
            <label style={labelStyle}>Transportista (Llegada)</label>
            <input type="text" value={`${entrada.transportista} - Placa: ${entrada.placa}`} readOnly style={{...inputStyle, background: '#4B5563'}} />
          </div>

          <div style={{ marginBottom: 20 }}>
            <h4 style={{ borderBottom: '1px solid #4B5563', paddingBottom: 5 }}>Productos a Recibir</h4>
            <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 10 }}>
              <thead>
                <tr style={{ background: '#374151', textAlign: 'left' }}>
                  <th style={{ padding: 10 }}>Producto</th>
                  <th style={{ padding: 10, width: 120, textAlign: 'center' }}>Capacidad (Declarada)</th>
                  <th style={{ padding: 10, width: 120 }}>Recibido (Mts)</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style={{ padding: 10, borderBottom: '1px solid #4B5563', position: 'relative' }}>
                    <span style={{ fontSize: 11, color: '#9CA3AF', display: 'block', marginBottom: 4 }}>Categoría de Puerta: {entrada.producto}</span>
                    <input 
                      type="text" 
                      value={qProductoReal}
                      onChange={e => { setQProductoReal(e.target.value); setProductoRealSel(null); }}
                      onBlur={() => { setIsProdFocused(false); setTimeout(() => setMostrarProdList(false), 200); }}
                      onFocus={() => { setIsProdFocused(true); if(productosRealesRes.length > 0) setMostrarProdList(true); }}
                      style={inputStyle}
                      placeholder="Buscar producto en ERP (Ej. Gasoil, Arena)..."
                    />
                    {mostrarProdList && productosRealesRes.length > 0 && (
                      <ul style={{ position: 'absolute', top: 60, left: 10, right: 10, background: 'white', color: 'black', listStyle: 'none', padding: 0, margin: 0, maxHeight: 200, overflowY: 'auto', zIndex: 10, borderRadius: 4, boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}>
                        {productosRealesRes.map(p => (
                          <li key={p.idProducto} onMouseDown={() => seleccionarProductoReal(p)} style={{ padding: 10, cursor: 'pointer', borderBottom: '1px solid #ccc' }}>
                            {p.nombre}
                          </li>
                        ))}
                      </ul>
                    )}
                  </td>
                  <td style={{ padding: 10, borderBottom: '1px solid #4B5563', textAlign: 'center' }}>
                    <span style={{ fontSize: 16, fontWeight: 'bold' }}>{entrada.cantidadDeclarada ?? '0.00'}</span>
                  </td>
                  <td style={{ padding: 10, borderBottom: '1px solid #4B5563' }}>
                    <input 
                      type="number" 
                      step="0.01" 
                      value={metros} 
                      onChange={(e) => setMetros(e.target.value)} 
                      placeholder="Ej. 8.5"
                      style={{...inputStyle, marginTop: 0}} 
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div style={{ marginBottom: 20 }}>
            <CamaraCaptura 
              label="Foto del Conduce Físico" 
              onCaptura={(b64, mime) => { setFotoConduce(b64); setFotoMime(mime); }} 
            />
          </div>

          <div style={{ marginBottom: 20 }}>
            <FirmaCanvas onFirma={(b64) => setFirma(b64)} />
          </div>

          <button 
            onClick={handleGuardar} 
            disabled={loading} 
            style={{ width: '100%', padding: 12, background: '#10B981', color: 'white', border: 'none', borderRadius: 4, fontWeight: 'bold', cursor: 'pointer', fontSize: 16 }}
          >
            {loading ? 'Procesando...' : 'Guardar y Generar Entrada de Almacén'}
          </button>
        </div>
      ) : (
        <div style={{ background: '#374151', padding: 20, borderRadius: 8 }}>
          <h3 style={{ borderBottom: '1px solid #4B5563', paddingBottom: 10, marginTop: 0 }}>Detalle de la Recepción</h3>
          <p>Esta entrada se encuentra en estado <strong>{entrada.status}</strong>.</p>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 15, marginTop: 20, background: '#1F2937', padding: 15, borderRadius: 8 }}>
            <div>
              <span style={{ color: '#9CA3AF', fontSize: 14 }}>Número de ProMov (ERP)</span>
              <div style={{ fontSize: 18, fontWeight: 'bold', color: '#10B981' }}>{entrada.proMov || 'N/A'}</div>
            </div>
            <div>
              <span style={{ color: '#9CA3AF', fontSize: 14 }}>Fecha de Recepción</span>
              <div style={{ fontSize: 16 }}>{entrada.fechaRecepcion ? new Date(entrada.fechaRecepcion).toLocaleString() : 'N/A'}</div>
            </div>
            <div>
              <span style={{ color: '#9CA3AF', fontSize: 14 }}>Conduce / Referencia</span>
              <div style={{ fontSize: 16 }}>{entrada.conduce}</div>
            </div>
            <div>
              <span style={{ color: '#9CA3AF', fontSize: 14 }}>Placa del Camión</span>
              <div style={{ fontSize: 16 }}>{entrada.placa}</div>
            </div>
            <div>
              <span style={{ color: '#9CA3AF', fontSize: 14 }}>Producto Recibido</span>
              <div style={{ fontSize: 16 }}>{entrada.producto}</div>
            </div>
            <div>
              <span style={{ color: '#9CA3AF', fontSize: 14 }}>Cantidad (Metros)</span>
              <div style={{ fontSize: 16 }}>{entrada.cantidadRecibida ?? 'N/A'}</div>
            </div>
            <div>
              <span style={{ color: '#9CA3AF', fontSize: 14 }}>Transportista</span>
              <div style={{ fontSize: 16 }}>{entrada.transportista}</div>
            </div>
            <div>
              <span style={{ color: '#9CA3AF', fontSize: 14 }}>Usuario que recibió</span>
              <div style={{ fontSize: 16 }}>{entrada.usuarioRecepcion}</div>
            </div>
          </div>
          
          <button onClick={() => navigate(isReadonly ? '/consulta' : '/')} style={{ marginTop: 20, padding: '8px 16px', background: '#3B82F6', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
            {isReadonly ? 'Volver a Consulta' : 'Volver'}
          </button>

          <div style={{ marginTop: 30, paddingTop: 20, borderTop: '1px solid #4B5563' }}>
            <h4>Evidencias Fotográficas</h4>
            {!urlFoto && !urlFirma && !cargandoEvidencia && (
              <button onClick={handleCargarEvidencias} style={{ padding: '8px 16px', background: '#4B5563', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
                Cargar Fotos y Firma
              </button>
            )}
            {cargandoEvidencia && <p>Cargando evidencias...</p>}
            
            <div style={{ display: 'flex', gap: 20, marginTop: 15, flexWrap: 'wrap' }}>
              {urlFoto && (
                <div style={{ border: '1px solid #4B5563', padding: 10, borderRadius: 8, background: '#1F2937' }}>
                  <p style={{ margin: '0 0 10px 0', fontSize: 14, color: '#9CA3AF' }}>Conduce Físico</p>
                  <img src={urlFoto} alt="Conduce" style={{ maxWidth: 300, maxHeight: 300, objectFit: 'contain' }} />
                </div>
              )}
              {urlFirma && (
                <div style={{ border: '1px solid #4B5563', padding: 10, borderRadius: 8, background: '#1F2937' }}>
                  <p style={{ margin: '0 0 10px 0', fontSize: 14, color: '#9CA3AF' }}>Firma + Foto</p>
                  <img src={urlFirma} alt="Firma" style={{ maxWidth: 300, maxHeight: 300, objectFit: 'contain' }} />
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const labelStyle = { fontWeight: 'bold', display: 'block', marginBottom: 5 };
const inputStyle = { width: '100%', padding: 10, borderRadius: 4, border: '1px solid #4B5563', background: '#374151', color: 'white', boxSizing: 'border-box' as const };
