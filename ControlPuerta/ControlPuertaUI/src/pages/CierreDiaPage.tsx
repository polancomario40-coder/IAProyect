import React, { useState, useEffect } from 'react';
import { obtenerPendientesCierre, buscarOrdenes, asignarOc, ejecutarCierre } from '../services/puertaApi';

export const CierreDiaPage: React.FC = () => {
  const [fecha, setFecha] = useState(new Date().toISOString().split('T')[0]);
  const [pendientes, setPendientes] = useState<any[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Modal State
  const [isModalOpen, setModalOpen] = useState(false);
  const [targetIds, setTargetIds] = useState<string[]>([]); // The IDs being assigned right now
  const [q, setQ] = useState('');
  const [ordenes, setOrdenes] = useState<any[]>([]);
  const [selectedOc, setSelectedOc] = useState<any>(null);
  const [evals, setEvals] = useState({ calidad: 255, tiempo: 255, servicio: 255 });

  const cargarPendientes = async () => {
    try {
      const res = await obtenerPendientesCierre(fecha);
      setPendientes(res.data.data);
      setSelectedIds([]); // Clear selection on load
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    cargarPendientes();
  }, [fecha]);

  // Handle Checkboxes
  const toggleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      const unassigned = pendientes.filter(p => !p.idOrden).map(p => p.idEntradaCamion);
      setSelectedIds(unassigned);
    } else {
      setSelectedIds([]);
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };

  // Handle Modal Actions
  const openModal = (ids: string[]) => {
    setTargetIds(ids);
    setQ('');
    setOrdenes([]);
    setSelectedOc(null);
    setEvals({ calidad: 255, tiempo: 255, servicio: 255 });
    setModalOpen(true);
  };

  const buscarOC = async () => {
    try {
      const res = await buscarOrdenes(q);
      setOrdenes(res.data.data);
    } catch (e) { console.error(e); }
  };

  const confirmarAsignacion = async () => {
    if (!selectedOc) return;
    try {
      // Lote: Apply to all targets
      await Promise.all(targetIds.map(idEntrada => 
        asignarOc({
          idEntradaCamion: idEntrada,
          idOrden: selectedOc.idOrden,
          ordenNumero: selectedOc.numero,
          evalCalidad: evals.calidad,
          evalTiempo: evals.tiempo,
          evalServicio: evals.servicio
        })
      ));
      
      alert(`OC #${selectedOc.numero} asignada correctamente a ${targetIds.length} recepción(es).`);
      setModalOpen(false);
      cargarPendientes();
    } catch (e: any) {
      alert(e.response?.data?.mensaje || 'Error asignando OC');
    }
  };

  // Cierre Final
  const handleCerrarDia = async () => {
    const sinOc = pendientes.filter(p => !p.idOrden).length;
    let msg = `¿Está seguro de cerrar el día ${fecha}?`;
    if (sinOc > 0) {
      msg += `\n\n⚠️ ATENCIÓN: Hay ${sinOc} recepciones sin OC. Estas quedarán PENDIENTES DE CIERRE y se arrastrarán para el próximo cierre, no pasarán a CxP hoy.`;
    }
    
    if (!window.confirm(msg)) return;

    try {
      const res = await ejecutarCierre({ fechaDia: fecha, asignacionesOc: [] });
      alert(res.data.mensaje);
      cargarPendientes();
    } catch (e: any) {
      alert(e.response?.data?.mensaje || 'Error en cierre de día');
    }
  };

  return (
    <div style={{ padding: 20, color: '#F3F4F6' }}>
      <h2>Cierre del Día</h2>
      
      <div style={{ display: 'flex', gap: 20, marginBottom: 20, alignItems: 'center' }}>
        <input type="date" value={fecha} onChange={e=>setFecha(e.target.value)} style={{...inputStyle, width: 'auto'}} />
        <button onClick={cargarPendientes} style={{...btnStyle, background: '#374151'}}>Actualizar</button>
        
        <button 
          onClick={() => openModal(selectedIds)} 
          disabled={selectedIds.length === 0}
          style={{
            ...btnStyle, 
            background: selectedIds.length > 0 ? '#10B981' : '#4B5563', 
            opacity: selectedIds.length > 0 ? 1 : 0.7,
            marginLeft: 20
          }}
        >
          Asignar OC a Seleccionados ({selectedIds.length})
        </button>

        <button onClick={handleCerrarDia} style={{...btnStyle, background: '#EF4444', marginLeft: 'auto'}}>
          Ejecutar Cierre Definitivo
        </button>
      </div>

      <div style={{ background: '#1F2937', padding: 20, borderRadius: 8 }}>
        <h3>Recepciones Pendientes de Cierre</h3>
        
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 10 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #4B5563', textAlign: 'left', color: '#9CA3AF' }}>
              <th style={{ width: 40, padding: '10px 0' }}>
                <input 
                  type="checkbox" 
                  onChange={toggleSelectAll} 
                  checked={selectedIds.length > 0 && pendientes.filter(p => !p.idOrden).length > 0 && selectedIds.length === pendientes.filter(p => !p.idOrden).length} 
                />
              </th>
              <th>Conduce</th>
              <th>Entrada Almacén</th>
              <th>Transportista</th>
              <th>Producto / Cantidad</th>
              <th>OC Asignada</th>
              <th style={{ textAlign: 'right' }}>Acción</th>
            </tr>
          </thead>
          <tbody>
            {pendientes.map(p => (
              <tr key={p.idEntradaCamion} style={{ borderBottom: '1px solid #374151' }}>
                <td style={{ padding: '10px 0' }}>
                  <input 
                    type="checkbox" 
                    checked={selectedIds.includes(p.idEntradaCamion)} 
                    onChange={() => toggleSelect(p.idEntradaCamion)} 
                    disabled={p.idOrden !== null} 
                  />
                </td>
                <td style={{ fontWeight: 500 }}>{p.conduce}</td>
                <td style={{ color: '#10B981', fontWeight: 600 }}>{p.proMov || 'N/A'}</td>
                <td>{p.transportista}</td>
                <td>{p.producto} <br/><small style={{color: '#9CA3AF'}}>{p.cantidadRecibida} mts</small></td>
                <td>
                  {p.idOrden ? (
                    <span style={{ color: '#10B981', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 5 }}>
                      ✓ #{p.ordenNumero}
                    </span>
                  ) : (
                    <span style={{ color: '#FCD34D' }}>Sin asignar</span>
                  )}
                </td>
                <td style={{ textAlign: 'right' }}>
                  {selectedIds.length === 0 && (
                    <button 
                      onClick={() => openModal([p.idEntradaCamion])}
                      style={{
                        ...btnStyle, 
                        background: p.idOrden ? '#374151' : '#3B82F6', 
                        padding: '6px 12px', 
                        fontSize: '12px'
                      }}
                    >
                      {p.idOrden ? 'Cambiar OC' : 'Asignar OC'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {pendientes.length === 0 && (
              <tr><td colSpan={6} style={{ padding: 30, textAlign: 'center', color: '#9CA3AF' }}>No hay pendientes para esta fecha</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* MODAL DE ASIGNACION */}
      {isModalOpen && (
        <div style={modalOverlayStyle}>
          <div style={modalContentStyle}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
              <h3 style={{ margin: 0, fontSize: 20 }}>Asignar Orden de Compra</h3>
              <button onClick={() => setModalOpen(false)} style={{ background: 'transparent', border: 'none', color: '#9CA3AF', cursor: 'pointer', fontSize: 24, lineHeight: 1 }}>×</button>
            </div>
            
            <div style={{ background: '#374151', padding: '10px 15px', borderRadius: 6, marginBottom: 20 }}>
              <p style={{ margin: 0, fontSize: 14 }}>
                Se asignará OC a <strong>{targetIds.length}</strong> recepción(es)
              </p>
            </div>

            {!selectedOc ? (
              // PANTALLA 1: BÚSQUEDA
              <>
                <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
                  <input 
                    placeholder="Buscar OC (Ej: 4473 o Suplidor)..." 
                    value={q} 
                    onChange={e=>setQ(e.target.value)} 
                    onKeyDown={e => e.key === 'Enter' && buscarOC()}
                    style={inputStyle} 
                    autoFocus
                  />
                  <button onClick={buscarOC} style={{...btnStyle, background: '#3B82F6'}}>Buscar</button>
                </div>
                
                <div style={{ maxHeight: 300, overflowY: 'auto' }}>
                  {ordenes.map(oc => (
                    <div key={oc.idOrden} style={{ background: '#374151', padding: 15, borderRadius: 6, marginBottom: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center', border: '1px solid #4B5563' }}>
                      <div>
                        <p style={{ margin: '0 0 5px 0', fontSize: 16 }}><strong>OC #{oc.numero}</strong></p>
                        <p style={{ margin: 0, fontSize: 13, color: '#D1D5DB' }}>{oc.suplidor} • Total: <strong>${oc.granTotal}</strong></p>
                      </div>
                      <button onClick={() => setSelectedOc(oc)} style={{...btnStyle, background: '#10B981', padding: '8px 16px'}}>Seleccionar</button>
                    </div>
                  ))}
                  {ordenes.length === 0 && q && (
                    <p style={{ textAlign: 'center', color: '#9CA3AF', marginTop: 20 }}>Presione Buscar para encontrar órdenes abiertas.</p>
                  )}
                </div>
              </>
            ) : (
              // PANTALLA 2: EVALUACIÓN Y CONFIRMACIÓN
              <>
                <div style={{ border: '1px solid #10B981', background: 'rgba(16, 185, 129, 0.1)', padding: 15, borderRadius: 6, marginBottom: 20 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                    <h4 style={{ margin: 0, color: '#10B981', fontSize: 16 }}>OC #{selectedOc.numero}</h4>
                    <button onClick={() => setSelectedOc(null)} style={{ background: 'transparent', border: 'none', color: '#3B82F6', cursor: 'pointer', fontSize: 13, padding: 0 }}>Modificar Selección</button>
                  </div>
                  <p style={{ margin: 0, fontSize: 14, color: '#E5E7EB' }}>{selectedOc.suplidor}</p>
                </div>
                  
                <h5 style={{ margin: '0 0 12px 0', color: '#D1D5DB', fontSize: 14 }}>Evaluación del Suplidor</h5>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 24 }}>
                  <div>
                    <label style={{ fontSize: 12, display: 'block', marginBottom: 6, color: '#9CA3AF' }}>Calidad:</label>
                    <select value={evals.calidad} onChange={e => setEvals({...evals, calidad: Number(e.target.value)})} style={inputStyle}>
                      <option value="255">NO EVALUADO</option>
                      <option value="5">Excelente</option>
                      <option value="4">Bueno</option>
                      <option value="3">Regular</option>
                      <option value="2">Malo</option>
                      <option value="1">Pésimo</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: 12, display: 'block', marginBottom: 6, color: '#9CA3AF' }}>Tiempo entrega:</label>
                    <select value={evals.tiempo} onChange={e => setEvals({...evals, tiempo: Number(e.target.value)})} style={inputStyle}>
                      <option value="255">NO EVALUADO</option>
                      <option value="5">Excelente</option>
                      <option value="4">Bueno</option>
                      <option value="3">Regular</option>
                      <option value="2">Malo</option>
                      <option value="1">Pésimo</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: 12, display: 'block', marginBottom: 6, color: '#9CA3AF' }}>Orden completa:</label>
                    <select value={evals.servicio} onChange={e => setEvals({...evals, servicio: Number(e.target.value)})} style={inputStyle}>
                      <option value="255">NO EVALUADO</option>
                      <option value="5">Excelente</option>
                      <option value="4">Bueno</option>
                      <option value="3">Regular</option>
                      <option value="2">Malo</option>
                      <option value="1">Pésimo</option>
                    </select>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 10 }}>
                  <button onClick={() => setModalOpen(false)} style={{...btnStyle, flex: 1, background: '#4B5563', padding: 12, fontSize: 15}}>Cancelar</button>
                  <button onClick={confirmarAsignacion} style={{...btnStyle, flex: 2, background: '#10B981', padding: 12, fontSize: 15}}>
                    Confirmar Asignación
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

    </div>
  );
};

const inputStyle = { padding: '10px', borderRadius: 6, border: '1px solid #4B5563', background: '#374151', color: 'white', width: '100%', fontSize: 14, outline: 'none' };
const btnStyle = { padding: '10px 16px', color: 'white', border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 500, transition: 'all 0.2s' };
const modalOverlayStyle: React.CSSProperties = {
  position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
  backgroundColor: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
};
const modalContentStyle: React.CSSProperties = {
  backgroundColor: '#1F2937', padding: 30, borderRadius: 12, width: '500px', maxWidth: '90%', 
  boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)', border: '1px solid #374151'
};
