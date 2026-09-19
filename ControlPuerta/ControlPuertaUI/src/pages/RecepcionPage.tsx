import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { obtenerRecepcion, confirmarRecepcion, notificarRecepcion, obtenerTicket, buscarSuplidores, listarAlmacenes, listarUnidades, extraerTextoPlaca, descargarEvidencia } from '../services/puertaApi';
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
  const [cantidadRecibida, setCantidadRecibida] = useState<string>('');
  const [unidadRecepcion, setUnidadRecepcion] = useState<string>('Mts3');
  const [unidadAlmacen, setUnidadAlmacen] = useState<string>('Mts3');
  const [cantidadAlmacen, setCantidadAlmacen] = useState<string>('');
  const [unidadesDisponibles, setUnidadesDisponibles] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  // Nuevos campos
  const [conduceAgregado, setConduceAgregado] = useState<string>('');
  const [notas, setNotas] = useState<string>('');
  
  // OCR conduce agregado
  const [ocrConduceLoading, setOcrConduceLoading] = useState(false);

  // Evidencias (solo lectura)
  const [urlFoto, setUrlFoto] = useState<string | null>(null);
  const [urlFirma, setUrlFirma] = useState<string | null>(null);
  const [urlCamion, setUrlCamion] = useState<string | null>(null);
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

  const [productosRecepcion, setProductosRecepcion] = useState<any[]>([]);
  
  const handleAgregarProducto = () => {
    if (!productoRealSel) return alert('Seleccione un producto ERP.');
    if (!cantidadRecibida || isNaN(parseFloat(cantidadRecibida)) || parseFloat(cantidadRecibida) <= 0) return alert('Digite una cantidad v�lida mayor a 0.');
    
    const prod = {
      idProductoReal: productoRealSel.idProducto,
      nombreProductoReal: productoRealSel.nombre || productoRealSel.producto,
      cantidadRecibida: parseFloat(cantidadRecibida),
      idUnidad: unidadRecepcion,
      idUnidadAlmacen: unidadAlmacen,
      cantidadAlmacen: parseFloat(cantidadAlmacen) || parseFloat(cantidadRecibida)
    };
    
    setProductosRecepcion([...productosRecepcion, prod]);
    setProductoRealSel(null);
    setQProductoReal('');
    setCantidadRecibida('');
    setCantidadAlmacen('');
  };
  
  const handleQuitarProducto = (idx: number) => {
    setProductosRecepcion(productosRecepcion.filter((_, i) => i !== idx));
  };

  const [isProdFocused, setIsProdFocused] = useState(false);

  const normalizarUnidad = (u: string): string => {
    if (!u) return '';
    const s = u.trim().toLowerCase();
    if (s === 'to' || s === 'ton' || s === 'tn' || s === 't' || s.includes('tonelad')) return 'Toneladas';
    if (s.includes('funda') || s.includes('saco') || s === 'fnd' || s === 'sc') return 'Fundas';
    if (s.includes('mt3') || s.includes('m3') || s.includes('metro') || s === 'mts3' || s === 'mts') return 'Mts3';
    if (s.includes('gal') || s === 'gl') return 'Galones';
    if (s.includes('kilo') || s === 'kg' || s === 'kgs') return 'Kgs';
    if (s.includes('libra') || s === 'lb' || s === 'lbs') return 'Libras';
    if (s.includes('und') || s.includes('unidad')) return 'Unidad';
    return u.trim();
  };

  const calcularConversion = (cantidad: number, deUnidad: string, aUnidad: string): number | null => {
    if (!cantidad || isNaN(cantidad) || cantidad <= 0) return null;
    const de = (deUnidad || '').trim().toLowerCase();
    const a = (aUnidad || '').trim().toLowerCase();
    if (!de || !a || de === a) return cantidad;

    const isTon = (u: string) => u.includes('ton') || u === 'to' || u === 'tn' || u === 't';
    const isFunda = (u: string) => u.includes('funda') || u.includes('saco') || u === 'fnd' || u === 'sc';
    const isLb = (u: string) => u.includes('libra') || u === 'lb' || u === 'lbs';
    const isKg = (u: string) => u.includes('kg') || u.includes('kilo');
    const isGalon = (u: string) => u.includes('gal') || u === 'gl';
    const isLitro = (u: string) => u.includes('litro') || u === 'lt' || u === 'l';

    // 1 Tonelada = 1,000 kg.
    // 1 Funda / Saco estándar = 42.5 kg.
    // 1 Tonelada = 1000 / 42.5 = 23.52941176 fundas.
    const FACTOR_TON_A_FUNDAS = 1000.0 / 42.5; // 23.52941176 fundas por tonelada

    // Toneladas <-> Fundas
    if (isTon(de) && isFunda(a)) return cantidad * FACTOR_TON_A_FUNDAS;
    if (isFunda(de) && isTon(a)) return cantidad / FACTOR_TON_A_FUNDAS;

    // Toneladas <-> Libras (1 Tonelada métrica = 2204.62 lbs; 1 Tonelada corta = 2000 lbs)
    if (isTon(de) && isLb(a)) return cantidad * 2204.62;
    if (isLb(de) && isTon(a)) return cantidad / 2204.62;

    // Toneladas <-> Kgs (1 Ton = 1000 kg)
    if (isTon(de) && isKg(a)) return cantidad * 1000.0;
    if (isKg(de) && isTon(a)) return cantidad / 1000.0;

    // Kgs <-> Fundas (1 funda = 42.5 kg)
    if (isKg(de) && isFunda(a)) return cantidad / 42.5;
    if (isFunda(de) && isKg(a)) return cantidad * 42.5;

    // Kgs <-> Libras (1 kg = 2.20462 lbs)
    if (isKg(de) && isLb(a)) return cantidad * 2.20462;
    if (isLb(de) && isKg(a)) return cantidad / 2.20462;

    // Galones <-> Libras (1 Galón de aditivo / líquido = ~8.345 lbs)
    if (isGalon(de) && isLb(a)) return cantidad * 8.345;
    if (isLb(de) && isGalon(a)) return cantidad / 8.345;

    // Galones <-> Litros (1 Galón = 3.78541 L)
    if (isGalon(de) && isLitro(a)) return cantidad * 3.78541;
    if (isLitro(de) && isGalon(a)) return cantidad / 3.78541;

    // Fundas <-> Libras (1 funda = 42.5 kg ≈ 93.696 lbs)
    if (isFunda(de) && isLb(a)) return cantidad * (42.5 * 2.20462);
    if (isLb(de) && isFunda(a)) return cantidad / (42.5 * 2.20462);

    return cantidad;
  };

  useEffect(() => {
    if (id) {
      obtenerRecepcion(id).then(res => {
        const d = res.data.data;
        setEntrada(d);
        setConduceAgregado(d.conduce || '');
        setQProductoReal('');
        
        const esCemento = (d.producto || '').toLowerCase().includes('cemento');
        const uNorm = normalizarUnidad(d.idUnidad || '');
        const u = uNorm || (esCemento ? 'Toneladas' : 'Mts3');
        setUnidadRecepcion(u);
        const almUnit = normalizarUnidad(d.idUnidadAlmacen || '') || (esCemento ? 'Fundas' : u);
        setUnidadAlmacen(almUnit);

        if (d.cantidadRecibida) {
          setCantidadRecibida(String(d.cantidadRecibida));
          setCantidadAlmacen(String(d.cantidadAlmacen || d.cantidadRecibida));
        } else if (d.cantidadDeclarada) {
          setCantidadRecibida(String(d.cantidadDeclarada));
          const valDec = parseFloat(String(d.cantidadDeclarada));
          if (!isNaN(valDec) && valDec > 0) {
            const conv = calcularConversion(valDec, u, almUnit);
            setCantidadAlmacen(conv !== null ? conv.toFixed(2) : String(d.cantidadDeclarada));
          } else {
            setCantidadAlmacen(String(d.cantidadDeclarada));
          }
        }
      }).catch(console.error);
    }
    listarAlmacenes().then(res => {
      const lista = res.data.data;
      setAlmacenes(lista);
      if (lista.length === 1) setIdAlmacen(lista[0].idAlmacen);
    }).catch(console.error);

    listarUnidades().then(res => {
      if (res.data?.data && res.data.data.length > 0) {
        const uList = res.data.data.map((u: string) => normalizarUnidad(u));
        const defaultUnits = ['Toneladas', 'Fundas', 'Mts3', 'Galones', 'Kgs', 'Libras', 'Unidad'];
        const merged = Array.from(new Set([...uList, ...defaultUnits])).filter(Boolean);
        setUnidadesDisponibles(merged);
      } else {
        setUnidadesDisponibles(['Toneladas', 'Fundas', 'Mts3', 'Galones', 'Kgs', 'Libras', 'Unidad']);
      }
    }).catch(() => {
      setUnidadesDisponibles(['Toneladas', 'Fundas', 'Mts3', 'Galones', 'Kgs', 'Libras', 'Unidad']);
    });
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
      if (qProductoReal.length >= 2 && !productoRealSel) {
        import('../services/puertaApi').then(({ buscarProductosReales }) => {
          if (buscarProductosReales) {
            buscarProductosReales(qProductoReal).then(res => {
              setProductosRealesRes(res.data.data);
              if (isProdFocused) setMostrarProdList(true);
            }).catch(console.error);
          }
        });
      } else {
        setMostrarProdList(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [qProductoReal, isProdFocused, productoRealSel]);

  const seleccionarSuplidor = (sup: any) => {
    setSuplidorSel(sup);
    setQSuplidor(sup.nombre);
    setMostrarSupList(false);
  };

  const seleccionarProductoReal = (prod: any) => {
    setProductoRealSel(prod);
    setQProductoReal(`[${prod.idProducto}] ${prod.nombre}`);
    setMostrarProdList(false);

    // Priorizar la unidad del producto ERP real
    const uProd = normalizarUnidad(prod.idUnidad || '');
    const uEntrada = normalizarUnidad(entrada?.idUnidad || '');
    const esCemento = (prod.nombre || '').toLowerCase().includes('cemento') || 
                      (entrada?.producto || '').toLowerCase().includes('cemento') ||
                      uProd === 'Toneladas';

    const uRec = uProd || (esCemento ? 'Toneladas' : (uEntrada || 'Mts3'));
    setUnidadRecepcion(uRec);

    // Si es cemento o la unidad es Toneladas, la unidad de almacén pasa por defecto a Fundas
    let targetUAlmacen = uRec;
    if (esCemento || uRec === 'Toneladas') {
      targetUAlmacen = 'Fundas';
    }
    setUnidadAlmacen(targetUAlmacen);

    const val = parseFloat(cantidadRecibida);
    if (!isNaN(val) && val > 0) {
      const conv = calcularConversion(val, uRec, targetUAlmacen);
      if (conv !== null) {
        setCantidadAlmacen(conv.toFixed(2));
      } else {
        setCantidadAlmacen(cantidadRecibida);
      }
    } else {
      setCantidadAlmacen(cantidadRecibida);
    }
  };

  const handleUnidadRecepcionChange = (nuevaUnidad: string) => {
    setUnidadRecepcion(nuevaUnidad);
    let targetAlm = unidadAlmacen;
    const isTon = (u: string) => {
      const s = (u || '').trim().toLowerCase();
      return s.includes('ton') || s === 'to' || s === 'tn';
    };
    if (isTon(nuevaUnidad) && !targetAlm.toLowerCase().includes('funda')) {
      targetAlm = 'Fundas';
      setUnidadAlmacen('Fundas');
    }
    const val = parseFloat(cantidadRecibida);
    if (!isNaN(val) && val > 0) {
      const conv = calcularConversion(val, nuevaUnidad, targetAlm);
      if (conv !== null) {
        setCantidadAlmacen(conv.toFixed(2));
      }
    }
  };

  const handleCantidadRecibidaChange = (valStr: string) => {
    setCantidadRecibida(valStr);
    const val = parseFloat(valStr);
    if (isNaN(val) || val <= 0) {
      setCantidadAlmacen('');
      return;
    }

    const conv = calcularConversion(val, unidadRecepcion, unidadAlmacen);
    if (conv !== null) {
      setCantidadAlmacen(conv.toFixed(2));
    } else {
      setCantidadAlmacen(valStr);
    }
  };

  const handleUnidadAlmacenChange = (nuevaUnidad: string) => {
    setUnidadAlmacen(nuevaUnidad);
    const val = parseFloat(cantidadRecibida);
    if (isNaN(val) || val <= 0) return;

    const conv = calcularConversion(val, unidadRecepcion, nuevaUnidad);
    if (conv !== null) {
      setCantidadAlmacen(conv.toFixed(2));
    }
  };

  // OCR para capturar el número de conduce desde una foto
  const handleOcrConduce = async (b64: string, mime: string) => {
    // 1. Guardar como evidencia
    setFotoConduce(b64);
    setFotoMime(mime);
    
    // 2. Extraer OCR
    try {
      setOcrConduceLoading(true);
      const res = await extraerTextoPlaca(b64, mime);
      const texto = res.data?.data?.textoDetectado || '';
      if (texto) {
        // Limpiar el texto: solo números y letras, eliminar espacios
        const limpio = texto.replace(/[^A-Za-z0-9\-]/g, '').trim();
        if (limpio || texto.trim()) {
          setConduceAgregado(limpio || texto.trim());
        }
      }
    } catch (e) {
      console.warn('OCR de conduce no disponible:', e);
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

      let resFirma = await descargarEvidencia(id, 'firma').catch(() => null);
      if (!resFirma?.data) {
        resFirma = await descargarEvidencia(id, 'firmada').catch(() => null);
      }
      if (resFirma?.data) setUrlFirma(URL.createObjectURL(resFirma.data));

      const resCamion = await descargarEvidencia(id, 'camion').catch(() => null);
      if (resCamion?.data) setUrlCamion(URL.createObjectURL(resCamion.data));

      if (!resFoto?.data && !resFirma?.data && !resCamion?.data) {
        alert('No se encontraron archivos de evidencia para esta recepción.');
      }
    } catch (error) {
      console.error(error);
    } finally {
      setCargandoEvidencia(false);
    }
  };

  const handleGuardar = async () => {
    if (!id) return;
    if (!fotoConduce) return alert('Es obligatorio tomar la foto del conduce físico antes de confirmar la recepción.');
    if (!conduceAgregado || conduceAgregado.length < 4) return alert('El Número de Conduce del Proveedor es obligatorio y debe tener al menos 4 caracteres.');
    if (!suplidorSel?.idSuplidor) return alert('Debe seleccionar el Suplidor del Agregado.');
    let currentProds = [...productosRecepcion];
      if (productoRealSel && cantidadRecibida && parseFloat(cantidadRecibida) > 0) {
        currentProds.push({
          idProductoReal: productoRealSel.idProducto,
          nombreProductoReal: productoRealSel.nombre || productoRealSel.producto,
          cantidadRecibida: parseFloat(cantidadRecibida),
          idUnidad: unidadRecepcion,
          idUnidadAlmacen: unidadAlmacen,
          cantidadAlmacen: cantidadAlmacen ? parseFloat(cantidadAlmacen) : parseFloat(cantidadRecibida)
        });
      }
      if (currentProds.length === 0) {
        setLoading(false);
        return alert('Debe agregar al menos un producto con cantidad v�lida.');
      }

      setLoading(true);
      try {
        const fotoLimpia = fotoConduce ? (fotoConduce.includes(',') ? fotoConduce.split(',')[1] : fotoConduce) : undefined;
        const firmaLimpia = firma ? (firma.includes(',') ? firma.split(',')[1] : firma) : undefined;
  
        await confirmarRecepcion(id, {
          idEntradaCamion: id,
          conduce: conduceAgregado,
          idSuplidor: suplidorSel.idSuplidor,
          nombreSuplidor: suplidorSel.nombre,
          idAlmacen: idAlmacen,
          productos: currentProds,
          notas: notas.trim() || 'Recibido v�a web',
          fotoConduceBase64: fotoLimpia,
          fotoConduceMime: fotoMime || 'image/jpeg',
          firmaDigitalBase64: firmaLimpia
        } as any);
      
      const notifRes = await notificarRecepcion(id, { emailDestinatario: 'proveedor@test.com' }).catch(() => null);
      if (notifRes?.data?.success) {
        alert('Recepción confirmada y correo enviado');
      }

      const ticketRes = await obtenerTicket(id);
      const ticketData = ticketRes.data.data;
      if (!ticketData.firmaDigitalBase64 && firmaLimpia) {
        ticketData.firmaDigitalBase64 = firmaLimpia;
      }
      await generarTicketPDF(ticketData);

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
          <div style={{ display: 'flex', gap: '15px' }}>
            <button onClick={() => navigate('/consulta')} style={{ marginTop: 20, padding: '8px 16px', background: '#3B82F6', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
              Volver a Consulta
            </button>
            <button onClick={async () => {
              try {
                if (id) {
                  const ticketRes = await obtenerTicket(id);
                  await generarTicketPDF(ticketRes.data.data);
                }
              } catch (e) {
                alert('Error al imprimir el ticket.');
              }
            }} style={{ marginTop: 20, padding: '8px 16px', background: '#10B981', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
              Imprimir Ticket
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (isReadonly) {
    return (
      <div style={{ padding: 20, color: '#F3F4F6', maxWidth: 800, margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2>Detalle de la Recepción (Solo Lectura)</h2>
          <button onClick={() => navigate('/consulta')} style={{ padding: '8px 16px', background: '#3B82F6', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
            Volver a Consulta
          </button>
        </div>

        <div style={{ background: '#1F2937', padding: 20, borderRadius: 8, marginTop: 15 }}>
          <p><strong>Status:</strong> <span style={{ color: entrada.status === 'CERRADO' ? '#10B981' : '#F59E0B' }}>{entrada.status}</span></p>
          <p><strong>Fecha Entrada:</strong> {new Date(entrada.fechaEntrada).toLocaleString()}</p>
          <p><strong>Fecha Recepción:</strong> {entrada.fechaRecepcion ? new Date(entrada.fechaRecepcion).toLocaleString() : 'N/A'}</p>
          <p><strong>Transportista:</strong> {entrada.transportista}</p>
          <p><strong>Chofer:</strong> {entrada.nombreChofer}</p>
          <p><strong>Placa:</strong> {entrada.placa}</p>
          <p><strong>Id (conduce):</strong> {entrada.conduceTransporte || entrada.conduce}</p>
          {entrada.conduceTransporte && entrada.conduce && <p><strong>Conduce Proveedor:</strong> {entrada.conduce}</p>}
          <p><strong>Producto ERP:</strong> {entrada.nombreProductoReal || entrada.producto}</p>
          <p><strong>Cantidad Declarada:</strong> {entrada.cantidadDeclarada} {entrada.idUnidad || 'Mts3'}</p>
          <p><strong>Cantidad Recibida:</strong> {entrada.cantidadRecibida} {entrada.idUnidad || 'Mts3'}</p>
          {entrada.idUnidadAlmacen && entrada.idUnidadAlmacen !== entrada.idUnidad && (
            <p><strong>Entrada a Almacén:</strong> {entrada.cantidadAlmacen ?? entrada.cantidadRecibida} {entrada.idUnidadAlmacen}</p>
          )}
          <p><strong>Notas:</strong> {entrada.notas}</p>

          <div style={{ marginTop: 15 }}>
            <button onClick={async () => {
              try {
                if (id) {
                  const ticketRes = await obtenerTicket(id);
                  await generarTicketPDF(ticketRes.data.data);
                }
              } catch(e) {
                alert('No se pudo imprimir el ticket');
              }
            }} style={{ padding: '8px 16px', background: '#10B981', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
              Imprimir Ticket
            </button>
          </div>

          <div style={{ marginTop: 30, paddingTop: 20, borderTop: '1px solid #4B5563' }}>
            <h4>Evidencias Fotográficas</h4>
            {!urlFoto && !urlFirma && !urlCamion && !cargandoEvidencia && (
              <button onClick={handleCargarEvidencias} style={{ padding: '8px 16px', background: '#4B5563', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
                Cargar Fotos y Firma
              </button>
            )}
            {cargandoEvidencia && <p>Cargando evidencias...</p>}
            
            <div style={{ display: 'flex', gap: 20, marginTop: 15, flexWrap: 'wrap' }}>
              {urlCamion && (
                <div style={{ border: '1px solid #4B5563', padding: 10, borderRadius: 8, background: '#111827' }}>
                  <p style={{ margin: '0 0 10px 0', fontSize: 14, color: '#9CA3AF' }}>Placa de Camión</p>
                  <img src={urlCamion} alt="Placa Camión" style={{ maxWidth: 300, maxHeight: 300, objectFit: 'contain' }} />
                </div>
              )}
              {urlFoto && (
                <div style={{ border: '1px solid #4B5563', padding: 10, borderRadius: 8, background: '#1F2937' }}>
                  <p style={{ margin: '0 0 10px 0', fontSize: 14, color: '#9CA3AF' }}>Conduce Físico</p>
                  <img src={urlFoto} alt="Conduce" style={{ maxWidth: 300, maxHeight: 300, objectFit: 'contain' }} />
                </div>
              )}
              {urlFirma && (
                <div style={{ border: '1px solid #4B5563', padding: 10, borderRadius: 8, background: '#1F2937' }}>
                  <p style={{ margin: '0 0 10px 0', fontSize: 14, color: '#9CA3AF' }}>Firma del Chofer</p>
                  <img src={urlFirma} alt="Firma" style={{ maxWidth: 300, maxHeight: 300, objectFit: 'contain' }} />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px 24px', color: '#F3F4F6', maxWidth: 1050, margin: '0 auto', width: '100%', boxSizing: 'border-box' }}>
      <h2>Recepción de Conduce</h2>
      
      {entrada.status === 'PENDIENTE' ? (
        <div style={{ background: '#1F2937', padding: 20, borderRadius: 8 }}>
          
          <div style={{ marginBottom: 20, background: '#374151', padding: 15, borderRadius: 8 }}>
            <h4 style={{ margin: '0 0 10px 0', color: '#60A5FA' }}>1. Foto del Conduce Físico (Obligatorio)</h4>
            <p style={{ margin: '0 0 15px 0', fontSize: 13, color: '#9CA3AF' }}>Al tomar la foto se guardará como evidencia y se intentará extraer el número de conduce automáticamente para llenar los datos.</p>
            <CamaraCaptura 
              label="" 
              onCaptura={handleOcrConduce} 
            />
            {fotoConduce ? (
              <span style={{ color: '#10B981', fontSize: 13, display: 'block', marginTop: 6, fontWeight: 'bold' }}>
                ✓ Foto del conduce físico tomada con éxito
              </span>
            ) : (
              <span style={{ color: '#F87171', fontSize: 13, display: 'block', marginTop: 6, fontWeight: 'bold' }}>
                ⚠️ Foto obligatoria: Debe tomar la foto del conduce con la cámara antes de confirmar.
              </span>
            )}
            {ocrConduceLoading && <span style={{ color: '#60A5FA', fontSize: 14, display: 'block', marginTop: 10 }}>Leyendo documento con IA...</span>}
          </div>

          <div style={{ display: 'flex', gap: 15, marginBottom: 15 }}>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>Fecha de Llegada</label>
              <input type="text" value={new Date(entrada.fechaEntrada).toLocaleString()} readOnly style={{...inputStyle, background: '#4B5563'}} />
            </div>
            <div style={{ flex: 1 }}>
              <label style={labelStyle}>Conduce Proveedor</label>
              <input 
                type="text" 
                value={conduceAgregado} 
                onChange={e=>setConduceAgregado(e.target.value)} 
                style={inputStyle} 
                placeholder="Mínimo 4 caracteres" 
              />
            </div>
          </div>

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
                <ul style={{ position: 'absolute', top: 60, left: 0, right: 0, background: 'white', color: 'black', listStyle: 'none', padding: 0, margin: 0, maxHeight: 150, overflowY: 'auto', zIndex: 10, borderRadius: 4, boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}>
                  {suplidoresRes.map(s => (
                    <li key={s.idSuplidor} onMouseDown={() => seleccionarSuplidor(s)} style={{ padding: '8px 10px', cursor: 'pointer', borderBottom: '1px solid #eee' }}>
                      {s.nombre}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div style={{ flex: 1 }}>
              <label style={labelStyle}>Almacén Destino</label>
              <select value={idAlmacen} onChange={e=>setIdAlmacen(e.target.value)} style={inputStyle}>
                <option value="">-- Seleccionar --</option>
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
            <div style={{ borderBottom: '1px solid #4B5563', paddingBottom: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h4 style={{ margin: 0 }}>Productos a Recibir</h4>
              <span style={{ fontSize: 13, color: '#9CA3AF' }}>
                Categoría de Puerta: <strong style={{ color: '#60A5FA' }}>{entrada.producto}</strong>
              </span>
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 10 }}>
              <thead>
                <tr style={{ background: '#374151', textAlign: 'left' }}>
                  <th style={{ padding: '8px 10px' }}>Producto ERP (Materia Prima)</th>
                  <th style={{ padding: '8px 4px', width: 75, textAlign: 'center' }}>Declarada</th>
                  <th style={{ padding: '8px 4px', width: 175, textAlign: 'center' }}>Cant. Recibida</th>
                  <th style={{ padding: '8px 6px', width: 175, textAlign: 'center' }}>Entrada Almacén</th>
                </tr>
              </thead>
              <tbody>
                  {productosRecepcion.map((p, idx) => (
                    <tr key={idx} style={{ background: '#374151' }}>
                      <td style={{ padding: '8px 10px', borderBottom: '1px solid #4B5563' }}>{p.nombreProductoReal}</td>
                      <td style={{ padding: '8px 4px', textAlign: 'center', borderBottom: '1px solid #4B5563' }}>-</td>
                      <td style={{ padding: '8px 4px', textAlign: 'center', borderBottom: '1px solid #4B5563' }}>{p.cantidadRecibida} {p.idUnidad}</td>
                      <td style={{ padding: '8px 6px', textAlign: 'center', borderBottom: '1px solid #4B5563' }}>{p.cantidadAlmacen} {p.idUnidadAlmacen}
                        <button type="button" onClick={() => handleQuitarProducto(idx)} style={{ marginLeft: 10, background: 'red', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer', padding: '2px 6px' }}>X</button>
                      </td>
                    </tr>
                  ))}
                  <tr>
                    <td style={{ padding: '8px 10px', borderBottom: '1px solid #4B5563', verticalAlign: 'top' }}>
                    <div style={{ position: 'relative', width: '100%' }}>
                      <input 
                        type="text" 
                        value={qProductoReal}
                        onChange={e => { setQProductoReal(e.target.value); setProductoRealSel(null); }}
                        onBlur={() => { setIsProdFocused(false); setTimeout(() => setMostrarProdList(false), 200); }}
                        onFocus={() => { setIsProdFocused(true); if(productosRealesRes.length > 0) setMostrarProdList(true); }}
                        style={{ ...inputStyle, width: '100%', height: 38, fontSize: 13, margin: 0, padding: '8px 10px' }}
                        placeholder="Buscar por ID o Nombre (Ej. 0209025, Arena)..."
                      />
                      {mostrarProdList && productosRealesRes.length > 0 && (
                        <ul style={{ 
                          position: 'absolute', 
                          top: 'calc(100% + 4px)', 
                          left: 0, 
                          right: 0, 
                          background: '#1F2937', 
                          color: 'white', 
                          border: '1px solid #4B5563',
                          listStyle: 'none', 
                          padding: 0, 
                          margin: 0, 
                          maxHeight: 220, 
                          overflowY: 'auto', 
                          zIndex: 9999, 
                          borderRadius: 6, 
                          boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 4px 6px -2px rgba(0, 0, 0, 0.4)' 
                        }}>
                          {productosRealesRes.map(p => (
                            <li 
                              key={p.idProducto} 
                              onMouseDown={() => seleccionarProductoReal(p)} 
                              style={{ 
                                padding: '8px 12px', 
                                cursor: 'pointer', 
                                borderBottom: '1px solid #374151', 
                                display: 'flex', 
                                justifyContent: 'space-between', 
                                alignItems: 'center' 
                              }}
                              onMouseEnter={e => (e.currentTarget.style.background = '#374151')}
                              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                            >
                              <div>
                                <div style={{ fontWeight: 600, color: '#F3F4F6', fontSize: 13 }}>{p.nombre}</div>
                                {p.idUnidad && <div style={{ fontSize: 11, color: '#9CA3AF' }}>Unidad ERP: {p.idUnidad}</div>}
                              </div>
                              <span style={{ color: '#60A5FA', fontWeight: 'bold', fontSize: 12, background: '#1E3A8A', padding: '2px 8px', borderRadius: 4, marginLeft: 8, whiteSpace: 'nowrap' }}>
                                {p.idProducto}
                              </span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </td>
                  <td style={{ padding: '8px 4px', borderBottom: '1px solid #4B5563', textAlign: 'center', width: 75, verticalAlign: 'top' }}>
                    <div style={{ height: 38, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
                      <span style={{ fontSize: 15, fontWeight: 'bold', lineHeight: '1.1' }}>{entrada.cantidadDeclarada ?? '0.00'}</span>
                      <span style={{ fontSize: 11, color: '#9CA3AF', lineHeight: '1.1' }}>{unidadRecepcion}</span>
                    </div>
                  </td>
                  <td style={{ padding: '8px 4px', borderBottom: '1px solid #4B5563', width: 175, verticalAlign: 'top' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4, height: 38 }}>
                      <input 
                        type="number" 
                        step="0.01" 
                        value={cantidadRecibida} 
                        onChange={(e) => handleCantidadRecibidaChange(e.target.value)} 
                        placeholder="0.00"
                        style={{ ...inputStyle, margin: 0, height: 38, flex: 1, minWidth: 0, padding: '8px 4px', textAlign: 'right' }} 
                      />
                      <select 
                        value={unidadRecepcion} 
                        onChange={(e) => handleUnidadRecepcionChange(e.target.value)}
                        style={{ ...inputStyle, margin: 0, height: 38, width: '85px', padding: '8px 2px', fontSize: 11, color: '#10B981', fontWeight: 'bold' }}
                        title="Unidad del Conduce / Recepción"
                      >
                        {(unidadesDisponibles.length > 0 ? unidadesDisponibles : ['Toneladas', 'Fundas', 'Mts3', 'Galones', 'Kgs', 'Libras', 'LBs', 'Unidad']).map(u => (
                          <option key={u} value={u}>{u}</option>
                        ))}
                      </select>
                    </div>
                  </td>
                  <td style={{ padding: '8px 6px', borderBottom: '1px solid #4B5563', width: 175, verticalAlign: 'top' }}>
                    <div style={{ display: 'flex', gap: 4, alignItems: 'center', height: 38 }}>
                      <input 
                        type="number" 
                        step="0.01" 
                        value={cantidadAlmacen} 
                        onChange={(e) => setCantidadAlmacen(e.target.value)} 
                        placeholder="0.00"
                        style={{ ...inputStyle, margin: 0, height: 38, flex: 1, minWidth: 0, padding: '8px 4px', textAlign: 'right' }} 
                        title="Cantidad que se registrará en el inventario del almacén (editable si desea ajustar al conduce/báscula)"
                      />
                      <select 
                        value={unidadAlmacen} 
                        onChange={(e) => handleUnidadAlmacenChange(e.target.value)} 
                        style={{ ...inputStyle, margin: 0, height: 38, width: '85px', padding: '8px 2px', fontSize: 11 }}
                        title="Unidad en que se dará entrada al almacén"
                      >
                        {(unidadesDisponibles.length > 0 ? unidadesDisponibles : ['Mts3', 'Fundas', 'Toneladas', 'Galones', 'Kgs', 'Libras', 'LBs', 'Unidad']).map(u => (
                          <option key={u} value={u}>{u}</option>
                        ))}
                      </select>
                    </div>
                    {unidadAlmacen !== unidadRecepcion && (
                      <span style={{ fontSize: 10, color: '#38BDF8', display: 'block', marginTop: 4, textAlign: 'center' }}>
                        ⇄ {unidadRecepcion} a {unidadAlmacen}
                      </span>
                    )}
                  </td>
                </tr>
              </tbody>
            
              <div style={{ textAlign: 'right', padding: '10px 0' }}>
                <button type="button" onClick={handleAgregarProducto} style={{ padding: '6px 12px', background: '#3B82F6', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>+ Agregar Producto</button>
              </div>
</table>
          </div>

          <div style={{ marginBottom: 20 }}>
            <label style={labelStyle}>Observaciones / Notas (Opcional):</label>
            <textarea 
              value={notas}
              onChange={e => setNotas(e.target.value)}
              placeholder="Cualquier imprevisto o nota relevante..."
              style={{ ...inputStyle, minHeight: '60px', resize: 'vertical' }}
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
              <span style={{ color: '#9CA3AF', fontSize: 14 }}>Id (conduce)</span>
              <div style={{ fontSize: 16, fontWeight: 'bold', color: '#10B981' }}>{entrada.conduceTransporte || entrada.conduce}</div>
            </div>
            {entrada.conduceTransporte && (
              <div>
                <span style={{ color: '#9CA3AF', fontSize: 14 }}>Conduce Proveedor</span>
                <div style={{ fontSize: 16 }}>{entrada.conduce}</div>
              </div>
            )}
            <div>
              <span style={{ color: '#9CA3AF', fontSize: 14 }}>Placa del Camión</span>
              <div style={{ fontSize: 16 }}>{entrada.placa}</div>
            </div>
            <div>
              <span style={{ color: '#9CA3AF', fontSize: 14 }}>Producto Recibido</span>
              <div style={{ fontSize: 16 }}>{entrada.producto}</div>
            </div>
            <div>
              <span style={{ color: '#9CA3AF', fontSize: 14 }}>Cantidad Recibida</span>
              <div style={{ fontSize: 16 }}>{entrada.cantidadRecibida ? `${entrada.cantidadRecibida} ${entrada.idUnidad || ''}` : 'N/A'}</div>
            </div>
            {entrada.idUnidadAlmacen && entrada.idUnidadAlmacen !== entrada.idUnidad && (
              <div>
                <span style={{ color: '#9CA3AF', fontSize: 14 }}>Entrada Almacén</span>
                <div style={{ fontSize: 16, color: '#38BDF8', fontWeight: 600 }}>{entrada.cantidadAlmacen ?? entrada.cantidadRecibida} {entrada.idUnidadAlmacen}</div>
              </div>
            )}
            <div>
              <span style={{ color: '#9CA3AF', fontSize: 14 }}>Transportista</span>
              <div style={{ fontSize: 16 }}>{entrada.transportista}</div>
            </div>
            <div>
              <span style={{ color: '#9CA3AF', fontSize: 14 }}>Usuario que recibió</span>
              <div style={{ fontSize: 16 }}>{entrada.usuarioRecepcion}</div>
            </div>
          </div>
          
          <div style={{ display: 'flex', gap: '15px' }}>
            <button onClick={() => navigate(isReadonly ? '/consulta' : '/')} style={{ marginTop: 20, padding: '8px 16px', background: '#3B82F6', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
              {isReadonly ? 'Volver a Consulta' : 'Volver'}
            </button>

            <button onClick={async () => {
              try {
                if (id) {
                  const ticketRes = await obtenerTicket(id);
                  await generarTicketPDF(ticketRes.data.data);
                }
              } catch (e) {
                alert('Error al imprimir el ticket.');
              }
            }} style={{ marginTop: 20, padding: '8px 16px', background: '#10B981', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
              Imprimir Ticket
            </button>
          </div>

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


