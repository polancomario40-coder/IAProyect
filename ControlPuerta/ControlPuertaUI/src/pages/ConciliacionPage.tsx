import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import * as XLSX from 'xlsx';
import { useAuth } from '../contexts/AuthContext';
import { 
  buscarSuplidores, 
  extraerConducesDocumento,
  compararConciliacion, 
  guardarConciliacion, 
  listarLotesConciliacion, 
  obtenerLoteConciliacion, 
  actualizarEstadoPagoLote 
} from '../services/puertaApi';
import { 
  descargarPlantillaSuplidorExcel, 
  exportarResultadoConciliacionExcel 
} from '../utils/excelExport';

export const ConciliacionPage: React.FC = () => {
  const { roles, user } = useAuth();

  // Validación de Permisos: Exclusivo para Contabilidad o Administrador
  const tienePermiso = roles.length === 0 || roles.some(r => 
    r.includes('contabilidad') || 
    r.includes('admin') || 
    r.includes('administrator') || 
    r.includes('administracion')
  );

  // Pestaña principal: 'NUEVA' o 'HISTORIAL'
  const [vista, setVista] = useState<'NUEVA' | 'HISTORIAL'>('NUEVA');

  // Suplidor State
  const [qSuplidor, setQSuplidor] = useState('');
  const [suplidores, setSuplidores] = useState<any[]>([]);
  const [mostrarSuplidores, setMostrarSuplidores] = useState(false);
  const [suplidorSel, setSuplidorSel] = useState<{ idSuplidor?: string; nombre: string } | null>(null);

  // Archivo y Carga
  const [archivoNombre, setArchivoNombre] = useState('');
  const [filasLeidas, setFilasLeidas] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [escaneandoOcr, setEscaneandoOcr] = useState(false);
  const [tipoArchivo, setTipoArchivo] = useState<'EXCEL' | 'PDF_SCAN' | null>(null);
  const [ocrMensaje, setOcrMensaje] = useState<string | null>(null);

  // Resultado de Conciliación
  const [resultado, setResultado] = useState<any | null>(null);
  const [filtroTab, setFiltroTab] = useState<'TODOS' | 'CALIFICAN' | 'RECHAZADOS' | 'PENDIENTES'>('TODOS');
  const [busquedaTabla, setBusquedaTabla] = useState('');
  const [guardadoExitoso, setGuardadoExitoso] = useState<string | null>(null);

  // Historial de Lotes
  const [lotes, setLotes] = useState<any[]>([]);
  const [cargandoLotes, setCargandoLotes] = useState(false);
  const [loteActivoId, setLoteActivoId] = useState<string | null>(null);

  // Modal Pago
  const [modalPagoOpen, setModalPagoOpen] = useState(false);
  const [referenciaPago, setReferenciaPago] = useState('');
  const [notaPago, setNotaPago] = useState('');

  // Autocomplete Suplidores
  useEffect(() => {
    if (qSuplidor.trim().length >= 2 && !suplidorSel) {
      const timer = setTimeout(() => {
        buscarSuplidores(qSuplidor.trim()).then(res => {
          setSuplidores(res.data?.data || []);
          setMostrarSuplidores(true);
        }).catch(() => setSuplidores([]));
      }, 300);
      return () => clearTimeout(timer);
    } else {
      setSuplidores([]);
      setMostrarSuplidores(false);
    }
  }, [qSuplidor, suplidorSel]);

  // Cargar Historial de Lotes
  const cargarHistorial = async () => {
    setCargandoLotes(true);
    try {
      const res = await listarLotesConciliacion();
      setLotes(res.data?.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setCargandoLotes(false);
    }
  };

  useEffect(() => {
    if (vista === 'HISTORIAL') {
      cargarHistorial();
    }
  }, [vista]);

  // Manejo de lectura de Excel o Documento Escaneado (PDF/Imagen)
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setArchivoNombre(file.name);
    setResultado(null);
    setGuardadoExitoso(null);
    setOcrMensaje(null);

    const isExcel = /\.(xlsx|xls)$/i.test(file.name);
    const isScanDoc = /\.(pdf|png|jpe?g)$/i.test(file.name);

    if (!isExcel && !isScanDoc) {
      alert('Formato no soportado. Por favor suba un archivo Excel (.xlsx, .xls) o un documento escaneado (.pdf, .png, .jpg).');
      return;
    }

    if (isScanDoc) {
      setTipoArchivo('PDF_SCAN');
      setEscaneandoOcr(true);
      setOcrMensaje('📄 Procesando documento escaneado con OCR inteligente... Reconociendo conduces...');

      try {
        const resp = await extraerConducesDocumento(file);
        const data = resp.data?.data || [];
        if (!data.length) {
          alert('No se detectaron conduces en el documento escaneado. Asegúrese de que la imagen sea legible o utilice la plantilla Excel.');
          setFilasLeidas([]);
          setOcrMensaje(null);
        } else {
          setFilasLeidas(data);
          setOcrMensaje(`✅ Se extrajeron exitosamente ${data.length} conduces del documento escaneado.`);
        }
      } catch (err: any) {
        console.error('Error al escanear documento OCR:', err);
        const msg = err.response?.data?.message || err.message || 'Error al comunicarse con el servicio de OCR.';
        alert(`Error al procesar documento con OCR: ${msg}`);
        setOcrMensaje(null);
      } finally {
        setEscaneandoOcr(false);
      }
      return;
    }

    setTipoArchivo('EXCEL');
    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const bstr = evt.target?.result;
        const wb = XLSX.read(bstr, { type: 'binary' });
        const wsName = wb.SheetNames[0];
        const ws = wb.Sheets[wsName];
        
        // Leer hoja como matriz de filas [fila][columna]
        const rows: any[][] = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });

        if (!rows.length) {
          alert('El archivo Excel está vacío o no contiene filas.');
          return;
        }

        // 1. Detección dinámica de la fila de encabezados
        let headerRowIdx = -1;
        let colFecha = -1;
        let colConduce = -1;
        let colProducto = -1;
        let colMina = -1;
        let colPlanta = -1;
        let colCantidad = -1;
        let colPrecio = -1;
        let colTotal = -1;

        for (let r = 0; r < Math.min(rows.length, 20); r++) {
          const row = rows[r];
          if (!Array.isArray(row)) continue;

          const strRow = row.map(cell => String(cell || '').trim().toLowerCase());
          
          const cIdx = strRow.findIndex(c => 
            c === 'no. conduce' || c === 'conduce' || c === 'no conduce' || c === 'ticket' || 
            (c.startsWith('no.') && !c.includes('orden')) || c === 'numero conduce'
          );
          const fIdx = strRow.findIndex(c => c.includes('fecha'));
          const pIdx = strRow.findIndex(c => c.includes('producto') || c.includes('material') || c.includes('descripcion'));
          const cantIdx = strRow.findIndex(c => c.includes('cantidad') || c.includes('cant') || c.includes('m3') || c.includes('ton'));

          // La fila de encabezados debe contener al menos Conduce y alguna otra columna representativa
          if (cIdx !== -1 && (fIdx !== -1 || pIdx !== -1 || cantIdx !== -1)) {
            headerRowIdx = r;
            colConduce = cIdx;
            colFecha = fIdx;
            colProducto = pIdx;
            colMina = strRow.findIndex(c => c.includes('mina') || c.includes('origen') || c.includes('cantera'));
            colPlanta = strRow.findIndex(c => c.includes('planta') || c.includes('destino') || c.includes('almacen'));
            colCantidad = cantIdx;
            colPrecio = strRow.findIndex(c => c.includes('precio') || c.includes('costo'));
            colTotal = strRow.findIndex(c => c.includes('total') || c.includes('monto') || c.includes('importe'));
            break;
          }
        }

        // Si no se detectó fila con encabezados específicos, usar mapeo por posición estándar (0..7)
        if (headerRowIdx === -1) {
          headerRowIdx = 0;
          colFecha = 0;
          colConduce = 1;
          colProducto = 2;
          colMina = 3;
          colPlanta = 4;
          colCantidad = 5;
          colPrecio = 6;
          colTotal = 7;
        }

        // 2. Extraer filas de datos posteriores al encabezado
        const items: any[] = [];
        const parseNum = (val: any): number => {
          if (val === null || val === undefined || val === '') return 0;
          if (typeof val === 'number') return isNaN(val) ? 0 : val;
          const clean = String(val).replace(/[^0-9.-]/g, '');
          const res = parseFloat(clean);
          return isNaN(res) ? 0 : res;
        };

        for (let i = headerRowIdx + 1; i < rows.length; i++) {
          const row = rows[i];
          if (!row || !Array.isArray(row) || row.length === 0) continue;

          let rawConduce = colConduce >= 0 && row[colConduce] !== undefined ? String(row[colConduce]).trim() : '';

          // Si viene con formato flotante como "672867.0", dejarlo entero
          if (/^\d+\.0+$/.test(rawConduce)) {
            rawConduce = rawConduce.split('.')[0];
          }

          if (!rawConduce) continue;

          const lowerC = rawConduce.toLowerCase();
          // Descartar encabezados repetidos, títulos, o notas explicativas
          if (
            lowerC === 'conduce' ||
            lowerC === 'no. conduce' ||
            lowerC === 'no conduce' ||
            lowerC === 'no.' ||
            lowerC === 'fecha' ||
            lowerC.includes('complete las columnas') ||
            lowerC.includes('plantilla oficial') ||
            lowerC.includes('instruccion') ||
            lowerC.includes('total') ||
            (rawConduce.length > 35 && !/\d/.test(rawConduce))
          ) {
            continue;
          }

          // Fecha
          const fechaRaw = colFecha >= 0 ? row[colFecha] : '';
          let fechaParsed: string | null = null;
          if (fechaRaw) {
            if (typeof fechaRaw === 'number') {
              // Serial Excel
              const d = new Date((fechaRaw - (25567 + 2)) * 86400 * 1000);
              fechaParsed = !isNaN(d.getTime()) ? d.toISOString() : null;
            } else {
              const d = new Date(fechaRaw);
              fechaParsed = !isNaN(d.getTime()) ? d.toISOString() : null;
            }
          }

          const productoRaw = colProducto >= 0 && row[colProducto] !== undefined ? String(row[colProducto]).trim() : '';
          const minaRaw     = colMina >= 0 && row[colMina] !== undefined ? String(row[colMina]).trim() : '';
          const plantaRaw   = colPlanta >= 0 && row[colPlanta] !== undefined ? String(row[colPlanta]).trim() : '';
          const cantRaw     = colCantidad >= 0 ? parseNum(row[colCantidad]) : 0;
          const precioRaw   = colPrecio >= 0 ? parseNum(row[colPrecio]) : 0;
          const totalRaw    = colTotal >= 0 ? parseNum(row[colTotal]) : 0;

          items.push({
            fecha: fechaParsed,
            noConduce: rawConduce,
            producto: productoRaw,
            mina: minaRaw,
            planta: plantaRaw,
            cantidad: cantRaw,
            precio: precioRaw,
            total: totalRaw > 0 ? totalRaw : Math.round(cantRaw * precioRaw * 100) / 100
          });
        }

        if (!items.length) {
          alert('No se encontraron filas con conduces válidos en el archivo Excel. Asegúrese de que la columna "No. conduce" contenga los números de conduce.');
          return;
        }

        setFilasLeidas(items);
      } catch (error) {
        console.error('Error al procesar Excel:', error);
        alert('Ocurrió un error al leer el archivo Excel. Asegúrese de que sea un formato válido (.xlsx o .xls).');
      }
    };
    reader.readAsBinaryString(file);
  };

  // Ejecutar Conciliación (Llamada al Backend)
  const handleEjecutarConciliacion = async () => {
    if (!suplidorSel?.nombre && !qSuplidor.trim()) {
      return alert('Debe seleccionar o escribir el nombre del Suplidor antes de conciliar.');
    }
    if (!filasLeidas.length) {
      return alert('Debe cargar un archivo Excel con los conduces del suplidor.');
    }

    setLoading(true);
    setResultado(null);
    setGuardadoExitoso(null);
    try {
      const payload = {
        idSuplidor: suplidorSel?.idSuplidor || null,
        suplidor: suplidorSel?.nombre || qSuplidor.trim(),
        nombreArchivo: archivoNombre,
        items: filasLeidas
      };

      const res = await compararConciliacion(payload);
      if (res.data?.success) {
        setResultado(res.data.data);
      } else {
        alert(res.data?.mensaje || 'Error al ejecutar conciliación');
      }
    } catch (error: any) {
      console.error(error);
      alert(error.response?.data?.mensaje || 'Error en el servidor al conciliar los datos.');
    } finally {
      setLoading(false);
    }
  };

  // Guardar Lote en BD
  const handleGuardarLote = async () => {
    if (!resultado || !resultado.items?.length) return;
    setLoading(true);
    try {
      const payload = {
        idSuplidor: resultado.idSuplidor,
        suplidor: resultado.suplidor,
        nombreArchivo: resultado.nombreArchivo,
        notas: `Lote procesado con ${resultado.totalConduces} conduces`,
        items: resultado.items
      };

      const res = await guardarConciliacion(payload);
      if (res.data?.success) {
        const idConciliacion = res.data.data.idConciliacion;
        setLoteActivoId(idConciliacion);
        setGuardadoExitoso(`Lote guardado con éxito. ID: ${idConciliacion}`);
        alert('¡Lote de conciliación guardado exitosamente en base de datos!');
      }
    } catch (e: any) {
      alert(e.response?.data?.mensaje || 'Error al guardar el lote');
    } finally {
      setLoading(false);
    }
  };

  // Cargar Lote desde Historial
  const handleVerLoteHistorial = async (id: string) => {
    setLoading(true);
    try {
      const res = await obtenerLoteConciliacion(id);
      if (res.data?.success) {
        setResultado(res.data.data);
        setLoteActivoId(id);
        setVista('NUEVA');
      }
    } catch (e: any) {
      alert('Error al cargar detalle del lote: ' + e.message);
    } finally {
      setLoading(false);
    }
  };

  // Actualizar Estado de Pago (Flujo CXP)
  const handleCambiarEstadoPago = async (nuevoEstado: string) => {
    const targetId = loteActivoId || resultado?.idConciliacion;
    if (!targetId) {
      return alert('Debe guardar el lote primero en la base de datos antes de cambiar su estado de pago.');
    }

    setLoading(true);
    try {
      const payload = {
        nuevoEstadoPago: nuevoEstado,
        referenciaPago: referenciaPago || null,
        notas: notaPago || null
      };

      const res = await actualizarEstadoPagoLote(targetId, payload);
      if (res.data?.success) {
        alert(`Estado actualizado a ${nuevoEstado} con éxito.`);
        setModalPagoOpen(false);
        setReferenciaPago('');
        setNotaPago('');
        // Recargar detalle
        const updated = await obtenerLoteConciliacion(targetId);
        if (updated.data?.success) setResultado(updated.data.data);
      }
    } catch (e: any) {
      alert(e.response?.data?.mensaje || 'Error actualizando estado de pago');
    } finally {
      setLoading(false);
    }
  };

  // Filtrado de items para la tabla
  const itemsFiltrados = (resultado?.items || []).filter((item: any) => {
    // Filtro Tab
    if (filtroTab === 'CALIFICAN' && item.estadoCuadre !== 'CALIFICA_PAGO') return false;
    if (filtroTab === 'RECHAZADOS' && item.estadoCuadre !== 'NO_CALIFICA') return false;
    if (filtroTab === 'PENDIENTES' && item.estadoCuadre !== 'PENDIENTE_RECEPCION') return false;

    // Filtro Búsqueda
    if (busquedaTabla.trim() !== '') {
      const q = busquedaTabla.toLowerCase();
      const matchConduce = item.noConduce?.toLowerCase().includes(q);
      const matchProd = (item.producto || '').toLowerCase().includes(q) || (item.productoEncontrado || '').toLowerCase().includes(q);
      const matchPlanta = (item.planta || '').toLowerCase().includes(q) || (item.plantaEncontrada || '').toLowerCase().includes(q);
      const matchMotivo = (item.motivoRechazo || '').toLowerCase().includes(q);
      if (!matchConduce && !matchProd && !matchPlanta && !matchMotivo) return false;
    }

    return true;
  });

  if (!tienePermiso) {
    return (
      <div style={{ padding: '60px 20px', maxWidth: '600px', margin: '40px auto', textAlign: 'center', background: '#1F2937', borderRadius: 12, border: '1px solid #374151', color: '#F3F4F6' }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>🔒</div>
        <h2 style={{ fontSize: 22, fontWeight: 'bold', margin: '0 0 10px 0', color: '#EF4444' }}>
          Acceso Restringido
        </h2>
        <p style={{ color: '#9CA3AF', fontSize: 14, lineHeight: 1.6, marginBottom: 20 }}>
          Este módulo de <strong>Conciliación de Suplidores y Flujo de Pagos (CXP)</strong> es exclusivo para los usuarios pertenecientes a los grupos de <strong>Contabilidad</strong> o <strong>Administrador</strong>.
        </p>
        <div style={{ background: '#111827', padding: '12px 16px', borderRadius: 8, border: '1px solid #374151', display: 'inline-block', textAlign: 'left', marginBottom: 24, fontSize: 12 }}>
          <div><span style={{ color: '#9CA3AF' }}>Usuario actual:</span> <strong style={{ color: '#F3F4F6' }}>{user?.nombre || user?.username || 'No identificado'}</strong></div>
          <div style={{ marginTop: 4 }}><span style={{ color: '#9CA3AF' }}>Grupos asignados:</span> <strong style={{ color: '#F87171' }}>{roles.length > 0 ? roles.join(', ') : 'Ninguno'}</strong></div>
        </div>
        <div>
          <Link
            to="/"
            style={{
              display: 'inline-block',
              background: '#2563EB',
              color: 'white',
              padding: '10px 20px',
              borderRadius: 6,
              textDecoration: 'none',
              fontWeight: 'bold',
              fontSize: 13
            }}
          >
            ← Volver al Inicio
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '24px', color: '#F3F4F6', maxWidth: '1400px', margin: '0 auto' }}>
      
      {/* ENCABEZADO PRINCIPAL */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16, marginBottom: 20 }}>
        <div>
          <h2 style={{ margin: '0 0 6px 0', fontSize: 24, fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 10 }}>
            <span>📑</span> Conciliación de Conduces y Flujo de Pagos (CXP)
          </h2>
          <p style={{ margin: 0, color: '#9CA3AF', fontSize: 14 }}>
            Cruce automático de conduces enviados por suplidores vs recepciones en planta para aprobación de pagos.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button
            onClick={descargarPlantillaSuplidorExcel}
            style={{ ...btnSecundario, background: '#047857' }}
            title="Descarga el formato Excel oficial para que los suplidores completen sus conduces"
          >
            📥 Descargar Plantilla Suplidor (Excel)
          </button>

          <button
            onClick={() => setVista(vista === 'NUEVA' ? 'HISTORIAL' : 'NUEVA')}
            style={{ ...btnSecundario, background: vista === 'NUEVA' ? '#4F46E5' : '#374151' }}
          >
            {vista === 'NUEVA' ? '📋 Ver Historial de Lotes' : '➕ Nueva Conciliación'}
          </button>
        </div>
      </div>

      {vista === 'HISTORIAL' ? (
        /* VISTA DE HISTORIAL DE LOTES */
        <div style={{ background: '#1F2937', padding: 20, borderRadius: 8, border: '1px solid #374151' }}>
          <h3 style={{ marginTop: 0, marginBottom: 15 }}>Historial de Lotes Conciliados</h3>
          {cargandoLotes ? (
            <p style={{ color: '#9CA3AF' }}>Cargando lotes...</p>
          ) : lotes.length === 0 ? (
            <p style={{ color: '#9CA3AF' }}>No se han registrado lotes de conciliación aún.</p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#111827', borderBottom: '1px solid #374151', textAlign: 'left', color: '#9CA3AF' }}>
                  <th style={{ padding: 10 }}>No. Conciliación</th>
                  <th style={{ padding: 10 }}>Fecha Carga</th>
                  <th style={{ padding: 10 }}>Suplidor</th>
                  <th style={{ padding: 10, textAlign: 'center' }}>Total Conduces</th>
                  <th style={{ padding: 10, textAlign: 'center' }}>Califican</th>
                  <th style={{ padding: 10, textAlign: 'center' }}>Rechazados</th>
                  <th style={{ padding: 10, textAlign: 'right' }}>Monto Aprobado</th>
                  <th style={{ padding: 10, textAlign: 'center' }}>Estado</th>
                  <th style={{ padding: 10, textAlign: 'center' }}>Acción</th>
                </tr>
              </thead>
              <tbody>
                {lotes.map(l => (
                  <tr key={l.idConciliacion} style={{ borderBottom: '1px solid #374151' }}>
                    <td style={{ padding: 10, fontWeight: 'bold', color: '#60A5FA' }}>{l.numeroConciliacion}</td>
                    <td style={{ padding: 10 }}>{new Date(l.fechaCarga).toLocaleString()}</td>
                    <td style={{ padding: 10 }}>{l.suplidor}</td>
                    <td style={{ padding: 10, textAlign: 'center' }}>{l.totalConduces}</td>
                    <td style={{ padding: 10, textAlign: 'center', color: '#10B981', fontWeight: 'bold' }}>{l.totalCalifican}</td>
                    <td style={{ padding: 10, textAlign: 'center', color: '#EF4444', fontWeight: 'bold' }}>{l.totalRechazados}</td>
                    <td style={{ padding: 10, textAlign: 'right', fontWeight: 'bold' }}>RD$ {Number(l.montoTotalCalifica).toLocaleString('es-DO', { minimumFractionDigits: 2 })}</td>
                    <td style={{ padding: 10, textAlign: 'center' }}>
                      <span style={{ 
                        padding: '3px 8px', borderRadius: 4, fontSize: 11, fontWeight: 'bold',
                        background: l.status === 'PAGADO' ? '#065F46' : (l.status === 'APROBADO_PAGO' ? '#1E40AF' : '#374151'),
                        color: 'white'
                      }}>
                        {l.status}
                      </span>
                    </td>
                    <td style={{ padding: 10, textAlign: 'center' }}>
                      <button
                        onClick={() => handleVerLoteHistorial(l.idConciliacion)}
                        style={{ ...btnPequeno, background: '#3B82F6' }}
                      >
                        Abrir Detalle
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : (
        /* VISTA NUEVA CONCILIACIÓN */
        <>
          {/* PANEL DE CONFIGURACIÓN Y SUBIDA DE EXCEL */}
          <div style={{ background: '#1F2937', padding: 20, borderRadius: 8, marginBottom: 20, border: '1px solid #374151' }}>
            <h3 style={{ margin: '0 0 15px 0', fontSize: 16, color: '#E5E7EB' }}>1. Seleccionar Suplidor y Cargar Plantilla</h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 15, alignItems: 'flex-start' }}>
              
              {/* Selector Suplidor */}
              <div style={{ position: 'relative' }}>
                <label style={{ display: 'block', fontSize: 12, color: '#9CA3AF', marginBottom: 5 }}>
                  Suplidor de Agregados / Materiales:
                </label>
                <input
                  type="text"
                  placeholder="Escriba el nombre del suplidor..."
                  value={suplidorSel ? suplidorSel.nombre : qSuplidor}
                  onChange={(e) => {
                    setQSuplidor(e.target.value);
                    setSuplidorSel(null);
                  }}
                  onFocus={() => { if (suplidores.length > 0) setMostrarSuplidores(true); }}
                  onBlur={() => setTimeout(() => setMostrarSuplidores(false), 200)}
                  style={{ ...inputStyle, width: '100%', boxSizing: 'border-box' as any, borderColor: suplidorSel ? '#10B981' : '#4B5563' }}
                />

                {mostrarSuplidores && suplidores.length > 0 && (
                  <ul style={{ position: 'absolute', top: 62, left: 0, right: 0, background: 'white', color: 'black', listStyle: 'none', padding: 0, margin: 0, maxHeight: 200, overflowY: 'auto', zIndex: 20, borderRadius: 4, border: '1px solid #ccc', boxShadow: '0 4px 10px rgba(0,0,0,0.3)' }}>
                    {suplidores.map((s: any) => (
                      <li
                        key={s.idSuplidor}
                        onMouseDown={() => {
                          setSuplidorSel({ idSuplidor: s.idSuplidor, nombre: s.nombre });
                          setQSuplidor(s.nombre);
                          setMostrarSuplidores(false);
                        }}
                        style={{ padding: '8px 12px', cursor: 'pointer', borderBottom: '1px solid #eee' }}
                      >
                        <strong>{s.nombre}</strong>
                        {s.idSuplidor && <span style={{ color: '#888', fontSize: 11, marginLeft: 8 }}>[{s.idSuplidor}]</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Selector Archivo Excel o Hoja Escaneada */}
              <div>
                <label style={{ display: 'block', fontSize: 12, color: '#9CA3AF', marginBottom: 5 }}>
                  Plantilla Excel o Hoja Escaneada (.xlsx, .pdf, .png, .jpg):
                </label>
                <input
                  type="file"
                  accept=".xlsx, .xls, .pdf, .png, .jpg, .jpeg"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  style={{ display: 'none' }}
                />
                <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={escaneandoOcr}
                    style={{ 
                      ...btnSecundario, 
                      background: escaneandoOcr ? '#1F2937' : '#374151', 
                      border: '1px dashed #6B7280', 
                      flex: 1, 
                      justifyContent: 'center',
                      opacity: escaneandoOcr ? 0.7 : 1
                    }}
                  >
                    {escaneandoOcr 
                      ? '⏳ Escaneando con OCR...' 
                      : (archivoNombre ? `📄 ${archivoNombre}` : '📂 Cargar Excel o PDF / Foto Escaneada')}
                  </button>
                  {filasLeidas.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
                      <span style={{ color: '#10B981', fontSize: 12, fontWeight: 'bold' }}>
                        ✓ {filasLeidas.length} conduces
                      </span>
                      <span style={{ fontSize: 10, color: '#9CA3AF' }}>
                        {tipoArchivo === 'PDF_SCAN' ? '🔍 OCR Escáner' : '📊 Excel'}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Botón Ejecutar Conciliación */}
              <div style={{ display: 'flex', alignItems: 'flex-end', height: '100%' }}>
                <button
                  type="button"
                  onClick={handleEjecutarConciliacion}
                  disabled={loading || escaneandoOcr || !filasLeidas.length}
                  style={{
                    ...btnPrincipal,
                    width: '100%',
                    padding: '11px',
                    fontSize: 14,
                    background: (!filasLeidas.length || loading || escaneandoOcr) ? '#4B5563' : '#2563EB',
                    cursor: (!filasLeidas.length || loading || escaneandoOcr) ? 'not-allowed' : 'pointer'
                  }}
                >
                  {loading ? 'Analizando Conduces...' : '⚡ Ejecutar Conciliación'}
                </button>
              </div>

            </div>

            {/* Mensaje de estado OCR */}
            {ocrMensaje && (
              <div style={{ marginTop: 15, padding: '10px 14px', borderRadius: 6, background: '#1E3A8A', border: '1px solid #3B82F6', fontSize: 13, color: '#DBEAFE', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>ℹ️</span> {ocrMensaje}
              </div>
            )}
          </div>

          {/* PREVIEW DE CONDUCES EXTRAÍDOS ANTES DE CONCILIAR */}
          {filasLeidas.length > 0 && !resultado && (
            <div style={{ background: '#1F2937', padding: 15, borderRadius: 8, marginBottom: 20, border: '1px solid #374151' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
                <span style={{ fontSize: 14, fontWeight: 'bold', color: '#60A5FA' }}>
                  📋 Vista Previa de Conduces Extraídos ({filasLeidas.length} filas detectadas)
                </span>
                <span style={{ fontSize: 12, color: '#9CA3AF' }}>
                  Origen: {tipoArchivo === 'PDF_SCAN' ? '🔍 Documento Escaneado (OCR)' : '📊 Plantilla Excel'}
                </span>
              </div>
              <div style={{ maxHeight: 220, overflowY: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: '#111827', color: '#9CA3AF', textAlign: 'left', borderBottom: '1px solid #374151' }}>
                      <th style={{ padding: '6px 10px' }}>Fecha</th>
                      <th style={{ padding: '6px 10px' }}>No. Conduce</th>
                      <th style={{ padding: '6px 10px' }}>Producto</th>
                      <th style={{ padding: '6px 10px' }}>Mina</th>
                      <th style={{ padding: '6px 10px' }}>Planta</th>
                      <th style={{ padding: '6px 10px', textAlign: 'right' }}>Cantidad</th>
                      <th style={{ padding: '6px 10px', textAlign: 'right' }}>Precio</th>
                      <th style={{ padding: '6px 10px', textAlign: 'right' }}>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filasLeidas.slice(0, 50).map((f: any, idx: number) => (
                      <tr key={idx} style={{ borderBottom: '1px solid #2D3748' }}>
                        <td style={{ padding: '6px 10px' }}>{f.fecha ? new Date(f.fecha).toLocaleDateString() : '-'}</td>
                        <td style={{ padding: '6px 10px', fontWeight: 'bold', color: '#F3F4F6' }}>{f.noConduce}</td>
                        <td style={{ padding: '6px 10px' }}>{f.producto || '-'}</td>
                        <td style={{ padding: '6px 10px' }}>{f.mina || '-'}</td>
                        <td style={{ padding: '6px 10px' }}>{f.planta || '-'}</td>
                        <td style={{ padding: '6px 10px', textAlign: 'right' }}>{Number(f.cantidad || 0).toLocaleString()}</td>
                        <td style={{ padding: '6px 10px', textAlign: 'right' }}>RD$ {Number(f.precio || 0).toFixed(2)}</td>
                        <td style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 'bold', color: '#34D399' }}>RD$ {Number(f.total || 0).toLocaleString('es-DO', { minimumFractionDigits: 2 })}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {filasLeidas.length > 50 && (
                <div style={{ textAlign: 'center', marginTop: 8, fontSize: 11, color: '#9CA3AF' }}>
                  ... y {filasLeidas.length - 50} conduces más. Presione "⚡ Ejecutar Conciliación" para iniciar el cruce con el sistema.
                </div>
              )}
            </div>
          )}

          {/* DASHBOARD DE MÉTRICAS / KPIS */}
          {resultado && (
            <div style={{ marginBottom: 20 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 15, marginBottom: 15 }}>
                
                {/* Total Reclamados */}
                <div style={{ background: '#1F2937', padding: 15, borderRadius: 8, border: '1px solid #374151' }}>
                  <div style={{ fontSize: 11, color: '#9CA3AF', textTransform: 'uppercase', fontWeight: 'bold' }}>Total Conduces en Archivo</div>
                  <div style={{ fontSize: 24, fontWeight: 'bold', marginTop: 4 }}>{resultado.totalConduces}</div>
                  <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 2 }}>
                    Reclamado: RD$ {Number(resultado.montoTotalReclamado).toLocaleString('es-DO', { minimumFractionDigits: 2 })}
                  </div>
                </div>

                {/* Califican para Pago */}
                <div style={{ background: '#064E3B', padding: 15, borderRadius: 8, border: '1px solid #059669' }}>
                  <div style={{ fontSize: 11, color: '#A7F3D0', textTransform: 'uppercase', fontWeight: 'bold' }}>✅ Califican para Pago</div>
                  <div style={{ fontSize: 24, fontWeight: 'bold', marginTop: 4, color: '#34D399' }}>{resultado.totalCalifican}</div>
                  <div style={{ fontSize: 12, color: '#D1FAE5', marginTop: 2 }}>
                    Monto: RD$ {Number(resultado.montoTotalCalifica).toLocaleString('es-DO', { minimumFractionDigits: 2 })}
                  </div>
                </div>

                {/* Discrepancias / No Califican */}
                <div style={{ background: '#450A0A', padding: 15, borderRadius: 8, border: '1px solid #DC2626' }}>
                  <div style={{ fontSize: 11, color: '#FECACA', textTransform: 'uppercase', fontWeight: 'bold' }}>❌ Con Discrepancias / Rechazo</div>
                  <div style={{ fontSize: 24, fontWeight: 'bold', marginTop: 4, color: '#F87171' }}>{resultado.totalRechazados}</div>
                  <div style={{ fontSize: 12, color: '#FEE2E2', marginTop: 2 }}>No cuadran con recepción de planta</div>
                </div>

                {/* Pendientes en Planta */}
                <div style={{ background: '#451A03', padding: 15, borderRadius: 8, border: '1px solid #D97706' }}>
                  <div style={{ fontSize: 11, color: '#FDE68A', textTransform: 'uppercase', fontWeight: 'bold' }}>⏳ Pendientes de Recepción</div>
                  <div style={{ fontSize: 24, fontWeight: 'bold', marginTop: 4, color: '#FBBF24' }}>{resultado.totalPendientes}</div>
                  <div style={{ fontSize: 12, color: '#FEF3C7', marginTop: 2 }}>En puerta pero no recibidos aún</div>
                </div>

              </div>

              {/* BARRA DE HERRAMIENTAS Y ACCIONES DEL LOTE */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, background: '#111827', padding: '12px 16px', borderRadius: 8, border: '1px solid #374151' }}>
                {/* Tabs de Filtro */}
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <button
                    onClick={() => setFiltroTab('TODOS')}
                    style={tabStyle(filtroTab === 'TODOS')}
                  >
                    Todos ({resultado.totalConduces})
                  </button>
                  <button
                    onClick={() => setFiltroTab('CALIFICAN')}
                    style={tabStyle(filtroTab === 'CALIFICAN', '#10B981')}
                  >
                    ✅ Califican ({resultado.totalCalifican})
                  </button>
                  <button
                    onClick={() => setFiltroTab('RECHAZADOS')}
                    style={tabStyle(filtroTab === 'RECHAZADOS', '#EF4444')}
                  >
                    ❌ Rechazados ({resultado.totalRechazados})
                  </button>
                  <button
                    onClick={() => setFiltroTab('PENDIENTES')}
                    style={tabStyle(filtroTab === 'PENDIENTES', '#F59E0B')}
                  >
                    ⏳ Pendientes ({resultado.totalPendientes})
                  </button>
                </div>

                {/* Botones de Acción */}
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  <button
                    onClick={() => exportarResultadoConciliacionExcel(resultado, resultado.items)}
                    style={{ ...btnSecundario, background: '#059669' }}
                    title="Exporta el reporte detallado con motivos de rechazo a Excel"
                  >
                    📊 Exportar Auditoría (Excel)
                  </button>

                  <button
                    onClick={handleGuardarLote}
                    disabled={loading}
                    style={{ ...btnSecundario, background: '#2563EB' }}
                  >
                    💾 Guardar Lote
                  </button>

                  <button
                    onClick={() => setModalPagoOpen(true)}
                    style={{ ...btnPrincipal, background: '#10B981' }}
                    title="Aprobar para pago los conduces que cuadraron exitosamente"
                  >
                    💳 Aprobar para Pago
                  </button>
                </div>
              </div>

              {guardadoExitoso && (
                <div style={{ marginTop: 10, padding: 10, background: '#065F46', color: '#D1FAE5', borderRadius: 6, fontSize: 13, fontWeight: 'bold' }}>
                  ✓ {guardadoExitoso}
                </div>
              )}
            </div>
          )}

          {/* TABLA DETALLADA DE CONDUCES CONCILIADOS */}
          {resultado && (
            <div style={{ background: '#1F2937', borderRadius: 8, border: '1px solid #374151', overflow: 'hidden' }}>
              
              {/* Buscador dentro de la tabla */}
              <div style={{ padding: '12px 16px', background: '#111827', borderBottom: '1px solid #374151', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 13, color: '#9CA3AF' }}>
                  Mostrando <strong>{itemsFiltrados.length}</strong> de <strong>{resultado.totalConduces}</strong> conduces
                </span>
                <input
                  type="text"
                  placeholder="Filtrar por conduce, producto, planta o motivo..."
                  value={busquedaTabla}
                  onChange={e => setBusquedaTabla(e.target.value)}
                  style={{ ...inputStyle, width: '320px', fontSize: 12 }}
                />
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: '#0B0F19', borderBottom: '1px solid #374151', textAlign: 'left', color: '#9CA3AF' }}>
                      <th style={{ padding: 10 }}>Fecha</th>
                      <th style={{ padding: 10 }}>No. Conduce</th>
                      <th style={{ padding: 10 }}>Producto (Excel / Sistema)</th>
                      <th style={{ padding: 10 }}>Planta (Excel / Sistema)</th>
                      <th style={{ padding: 10, textAlign: 'right' }}>Cant. Declarada</th>
                      <th style={{ padding: 10, textAlign: 'right' }}>Cant. Planta</th>
                      <th style={{ padding: 10, textAlign: 'right' }}>Precio</th>
                      <th style={{ padding: 10, textAlign: 'right' }}>Total Reclamado</th>
                      <th style={{ padding: 10, textAlign: 'right' }}>Total Aprobado</th>
                      <th style={{ padding: 10, textAlign: 'center' }}>Estado Cuadre</th>
                      <th style={{ padding: 10 }}>Diagnóstico / Motivo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {itemsFiltrados.map((item: any, idx: number) => {
                      const esCalifica = item.estadoCuadre === 'CALIFICA_PAGO';
                      const esPendiente = item.estadoCuadre === 'PENDIENTE_RECEPCION';
                      const esRechazado = item.estadoCuadre === 'NO_CALIFICA';

                      const rowBg = esCalifica ? 'rgba(16, 185, 129, 0.05)' : (esPendiente ? 'rgba(245, 158, 11, 0.05)' : 'rgba(239, 68, 68, 0.05)');

                      return (
                        <tr key={idx} style={{ borderBottom: '1px solid #374151', background: rowBg }}>
                          <td style={{ padding: 10, whiteSpace: 'nowrap' }}>
                            {item.fechaConduce ? new Date(item.fechaConduce).toLocaleDateString() : '-'}
                          </td>
                          <td style={{ padding: 10, fontWeight: 'bold', color: '#F3F4F6', whiteSpace: 'nowrap' }}>
                            {item.noConduce}
                            {item.proMov && (
                              <span style={{ display: 'block', fontSize: 10, color: '#38BDF8', fontWeight: 'normal' }}>
                                Alm: {item.proMov}
                              </span>
                            )}
                          </td>
                          <td style={{ padding: 10 }}>
                            <div style={{ fontWeight: 500 }}>{item.producto || '-'}</div>
                            {item.productoEncontrado && item.productoEncontrado !== item.producto && (
                              <div style={{ fontSize: 11, color: '#9CA3AF' }}>Recibido: {item.productoEncontrado}</div>
                            )}
                          </td>
                          <td style={{ padding: 10 }}>
                            <div style={{ color: '#E5E7EB' }}>{item.planta || '-'}</div>
                            {item.plantaEncontrada && (
                              <div style={{ fontSize: 11, color: '#38BDF8' }}>Planta: {item.plantaEncontrada}</div>
                            )}
                          </td>
                          <td style={{ padding: 10, textAlign: 'right', fontWeight: 'bold' }}>
                            {Number(item.cantidadDeclarada).toFixed(2)}
                          </td>
                          <td style={{ padding: 10, textAlign: 'right', fontWeight: 'bold', color: esCalifica ? '#34D399' : (item.cantidadSistema != null ? '#F87171' : '#9CA3AF') }}>
                            {item.cantidadSistema != null ? `${Number(item.cantidadSistema).toFixed(2)} ${item.unidadSistema || ''}` : '-'}
                          </td>
                          <td style={{ padding: 10, textAlign: 'right' }}>
                            RD$ {Number(item.precioUnitario).toFixed(2)}
                          </td>
                          <td style={{ padding: 10, textAlign: 'right', fontWeight: 'bold' }}>
                            RD$ {Number(item.totalReclamado).toLocaleString('es-DO', { minimumFractionDigits: 2 })}
                          </td>
                          <td style={{ padding: 10, textAlign: 'right', fontWeight: 'bold', color: esCalifica ? '#10B981' : '#9CA3AF' }}>
                            RD$ {Number(item.totalAprobado || 0).toLocaleString('es-DO', { minimumFractionDigits: 2 })}
                          </td>
                          <td style={{ padding: 10, textAlign: 'center', whiteSpace: 'nowrap' }}>
                            {esCalifica && (
                              <span style={{ padding: '3px 8px', borderRadius: 4, fontSize: 11, fontWeight: 'bold', background: '#065F46', color: '#34D399' }}>
                                ✓ CALIFICA
                              </span>
                            )}
                            {esPendiente && (
                              <span style={{ padding: '3px 8px', borderRadius: 4, fontSize: 11, fontWeight: 'bold', background: '#78350F', color: '#FCD34D' }}>
                                ⏳ PENDIENTE
                              </span>
                            )}
                            {esRechazado && (
                              <span style={{ padding: '3px 8px', borderRadius: 4, fontSize: 11, fontWeight: 'bold', background: '#7F1D1D', color: '#F87171' }}>
                                ✕ NO CALIFICA
                              </span>
                            )}
                          </td>
                          <td style={{ padding: 10, color: esCalifica ? '#10B981' : (esPendiente ? '#FBBF24' : '#F87171'), fontSize: 11 }}>
                            {item.motivoRechazo}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {/* MODAL GESTIÓN DE PAGO (FLUJO CXP) */}
      {modalPagoOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div style={{ background: '#1F2937', padding: 24, borderRadius: 8, width: 450, maxWidth: '90%', border: '1px solid #374151', color: 'white' }}>
            <h3 style={{ margin: '0 0 15px 0' }}>Aprobación y Flujo de Pagos (CXP)</h3>
            <p style={{ fontSize: 13, color: '#9CA3AF', marginBottom: 15 }}>
              Seleccione la acción para los conduces calificados del lote. Al aprobarlos quedarán autorizados para el enlace con Cuentas por Pagar.
            </p>

            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', fontSize: 12, color: '#9CA3AF', marginBottom: 4 }}>No. de Referencia / Transferencia / Cheque:</label>
              <input
                type="text"
                placeholder="Ej. TRANSF-98234 o FACT-2026-01"
                value={referenciaPago}
                onChange={e => setReferenciaPago(e.target.value)}
                style={{ ...inputStyle, width: '100%', boxSizing: 'border-box' as any }}
              />
            </div>

            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 12, color: '#9CA3AF', marginBottom: 4 }}>Notas / Comentarios:</label>
              <textarea
                placeholder="Observaciones de tesorería o cuentas por pagar..."
                value={notaPago}
                onChange={e => setNotaPago(e.target.value)}
                style={{ ...inputStyle, width: '100%', boxSizing: 'border-box' as any, height: 60 }}
              />
            </div>

            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => setModalPagoOpen(false)}
                style={{ ...btnSecundario, background: '#4B5563' }}
              >
                Cancelar
              </button>

              <button
                type="button"
                onClick={() => handleCambiarEstadoPago('APROBADO')}
                style={{ ...btnPrincipal, background: '#2563EB' }}
              >
                Autorizar para Pago
              </button>

              <button
                type="button"
                onClick={() => handleCambiarEstadoPago('PAGADO')}
                style={{ ...btnPrincipal, background: '#059669' }}
              >
                Marcar como Pagado
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

const inputStyle = {
  padding: '9px 12px',
  borderRadius: 6,
  border: '1px solid #4B5563',
  background: '#374151',
  color: 'white',
  fontSize: '13px'
};

const btnPrincipal = {
  padding: '8px 16px',
  background: '#2563EB',
  color: 'white',
  border: 'none',
  borderRadius: 6,
  fontWeight: 'bold' as const,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  fontSize: '13px'
};

const btnSecundario = {
  padding: '8px 14px',
  background: '#374151',
  color: 'white',
  border: 'none',
  borderRadius: 6,
  fontWeight: 'bold' as const,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  fontSize: '12px'
};

const btnPequeno = {
  padding: '5px 10px',
  color: 'white',
  border: 'none',
  borderRadius: 4,
  fontWeight: 'bold' as const,
  cursor: 'pointer',
  fontSize: '11px'
};

const tabStyle = (active: boolean, color?: string) => ({
  padding: '6px 12px',
  background: active ? (color || '#2563EB') : '#1F2937',
  color: active ? 'white' : '#9CA3AF',
  border: active ? '1px solid transparent' : '1px solid #374151',
  borderRadius: 6,
  cursor: 'pointer',
  fontSize: '12px',
  fontWeight: active ? ('bold' as const) : ('normal' as const)
});
