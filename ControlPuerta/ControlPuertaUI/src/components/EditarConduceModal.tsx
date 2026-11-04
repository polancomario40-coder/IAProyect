import React, { useState, useEffect } from 'react';
import { editarEntradaConduce, listarAlmacenes, listarUnidades } from '../services/puertaApi';

export interface EditarConduceModalProps {
  entrada: any;
  isOpen: boolean;
  onClose: () => void;
  onSaved: () => void;
}

export const EditarConduceModal: React.FC<EditarConduceModalProps> = ({
  entrada,
  isOpen,
  onClose,
  onSaved,
}) => {
  if (!isOpen || !entrada) return null;

  const [codigoAutorizacion, setCodigoAutorizacion] = useState('');
  const [conduce, setConduce] = useState(entrada.conduce || '');
  const [conduceTransporte, setConduceTransporte] = useState(entrada.conduceTransporte || '');
  const [placa, setPlaca] = useState(entrada.placa || '');
  const [transportista, setTransportista] = useState(entrada.transportista || '');
  const [idTransportista, setIdTransportista] = useState(entrada.idTransportista || '');
  const [nombreChofer, setNombreChofer] = useState(entrada.nombreChofer || '');
  const [idChofer, setIdChofer] = useState(entrada.idChofer || null);
  const [suplidor, setSuplidor] = useState(entrada.suplidor || '');
  const [idSuplidor, setIdSuplidor] = useState(entrada.idSuplidor || '');
  const [producto, setProducto] = useState(entrada.producto || '');
  const [idProducto, setIdProducto] = useState(entrada.idProducto || '');
  const [idAlmacen, setIdAlmacen] = useState(entrada.idAlmacen || '');
  const [cantidadDeclarada, setCantidadDeclarada] = useState<string>(
    entrada.cantidadDeclarada != null ? String(entrada.cantidadDeclarada) : ''
  );
  const [cantidadRecibida, setCantidadRecibida] = useState<string>(
    entrada.cantidadRecibida != null ? String(entrada.cantidadRecibida) : ''
  );
  const [idUnidad, setIdUnidad] = useState(entrada.idUnidad || 'Mts3');
  const [ordenNumero, setOrdenNumero] = useState<string>(
    entrada.ordenNumero != null ? String(entrada.ordenNumero) : ''
  );
  const [fechaEntrada, setFechaEntrada] = useState<string>(() => {
    if (entrada.fechaEntrada) {
      try {
        const d = new Date(entrada.fechaEntrada);
        return d.toISOString().slice(0, 16);
      } catch {
        return '';
      }
    }
    return '';
  });
  const [notas, setNotas] = useState(entrada.notas || '');

  const [almacenes, setAlmacenes] = useState<any[]>([]);
  const [unidades, setUnidades] = useState<string[]>(['Mts3', 'Fundas', 'Qqs', 'Lbs', 'Kgs', 'Unid']);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listarAlmacenes()
      .then(res => setAlmacenes(res.data?.data || []))
      .catch(() => {});
    listarUnidades()
      .then(res => {
        if (res.data?.data && res.data.data.length > 0) {
          setUnidades(res.data.data);
        }
      })
      .catch(() => {});
  }, []);

  const handleGuardar = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!codigoAutorizacion.trim()) {
      setError('El Código de Autorización ERP es OBLIGATORIO.');
      return;
    }

    if (!conduce.trim()) {
      setError('El número de conduce no puede estar vacío.');
      return;
    }

    setGuardando(true);
    try {
      const payload = {
        codigoAutorizacion: codigoAutorizacion.trim().toUpperCase(),
        conduce: conduce.trim(),
        conduceTransporte: conduceTransporte.trim() || null,
        placa: placa.trim().toUpperCase(),
        idTransportista: idTransportista || null,
        transportista: transportista.trim(),
        idChofer: idChofer || null,
        nombreChofer: nombreChofer.trim(),
        idSuplidor: idSuplidor || null,
        suplidor: suplidor.trim(),
        idProducto: idProducto || null,
        producto: producto.trim(),
        idAlmacen: idAlmacen || null,
        cantidadDeclarada: cantidadDeclarada !== '' ? parseFloat(cantidadDeclarada) : null,
        cantidadRecibida: cantidadRecibida !== '' ? parseFloat(cantidadRecibida) : null,
        idUnidad: idUnidad || null,
        ordenNumero: ordenNumero.trim() !== '' ? parseInt(ordenNumero, 10) : null,
        fechaEntrada: fechaEntrada ? new Date(fechaEntrada).toISOString() : null,
        notas: notas.trim() || null,
      };

      await editarEntradaConduce(entrada.idEntradaCamion, payload);
      alert('✅ Conduce modificado exitosamente. La auditoría ha sido registrada en el sistema.');
      onSaved();
      onClose();
    } catch (err: any) {
      console.error('Error al editar conduce:', err);
      const msg = err.response?.data?.mensaje || err.message || 'Error al guardar los cambios.';
      setError(msg);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: 16,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#1F2937',
          color: '#F9FAFB',
          borderRadius: 10,
          border: '1px solid #374151',
          width: '100%',
          maxWidth: '750px',
          maxHeight: '92vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid #374151',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            backgroundColor: '#111827',
            borderTopLeftRadius: 10,
            borderTopRightRadius: 10,
          }}
        >
          <div>
            <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 600, color: '#38BDF8', display: 'flex', alignItems: 'center', gap: 8 }}>
              ✏️ Modificar Información de Conduce
            </h3>
            <span style={{ fontSize: '12px', color: '#9CA3AF' }}>
              Entrada ID: {entrada.idEntradaCamion} | Estado: <b style={{ color: '#FCD34D' }}>{entrada.status}</b>
            </span>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#9CA3AF',
              fontSize: '22px',
              cursor: 'pointer',
              lineHeight: 1,
            }}
          >
            &times;
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleGuardar} style={{ display: 'flex', flexDirection: 'column', overflowY: 'auto', flex: 1, padding: 20, gap: 16 }}>
          {/* Alerta de Código de Autorización ERP */}
          <div
            style={{
              background: 'rgba(217, 119, 6, 0.15)',
              border: '2px solid #F59E0B',
              borderRadius: 8,
              padding: '14px 16px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <span style={{ fontSize: '20px' }}>🔐</span>
              <strong style={{ color: '#FBBF24', fontSize: '15px' }}>
                Autorización ERP Requerida
              </strong>
            </div>
            <p style={{ margin: '0 0 10px 0', fontSize: '12.5px', color: '#D1D5DB' }}>
              Para modificar este registro debe proporcionar un código de autorización generado en el ERP (módulo <i>Autorizaciones</i> de Transporte Almánzar / SADE). Cada código es de un solo uso y la edición quedará registrada en la tabla de auditoría <b>Loging</b>.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={{ fontSize: '12px', fontWeight: 700, color: '#FCD34D', textTransform: 'uppercase' }}>
                Código de Autorización *
              </label>
              <input
                type="text"
                required
                value={codigoAutorizacion}
                onChange={(e) => setCodigoAutorizacion(e.target.value.toUpperCase())}
                placeholder="EJ: VJPB@SUNRA"
                style={{
                  background: '#111827',
                  border: '2px solid #F59E0B',
                  borderRadius: 6,
                  padding: '10px 14px',
                  color: '#FCD34D',
                  fontSize: '16px',
                  fontWeight: 700,
                  letterSpacing: '1.5px',
                  fontFamily: 'monospace',
                }}
              />
            </div>
          </div>

          {error && (
            <div
              style={{
                background: 'rgba(239, 68, 68, 0.2)',
                border: '1px solid #EF4444',
                color: '#FCA5A5',
                padding: '10px 14px',
                borderRadius: 6,
                fontSize: '13px',
              }}
            >
              ⚠️ {error}
            </div>
          )}

          {/* Grid de campos editables */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: 14,
            }}
          >
            {/* Conduce */}
            <div>
              <label style={labelStyle}>No. Conduce *</label>
              <input
                type="text"
                required
                value={conduce}
                onChange={(e) => setConduce(e.target.value)}
                style={inputStyle}
              />
            </div>

            {/* Conduce Transporte / Secuencia Almacén */}
            <div>
              <label style={labelStyle}>Secuencia Alm. / Conduce Transp.</label>
              <input
                type="text"
                value={conduceTransporte}
                onChange={(e) => setConduceTransporte(e.target.value)}
                placeholder="Ej: Metaldom-00142"
                style={inputStyle}
              />
            </div>

            {/* Placa */}
            <div>
              <label style={labelStyle}>Placa *</label>
              <input
                type="text"
                required
                value={placa}
                onChange={(e) => setPlaca(e.target.value.toUpperCase())}
                style={inputStyle}
              />
            </div>

            {/* Transportista */}
            <div>
              <label style={labelStyle}>Transportista</label>
              <input
                type="text"
                value={transportista}
                onChange={(e) => setTransportista(e.target.value)}
                style={inputStyle}
              />
            </div>

            {/* Chofer */}
            <div>
              <label style={labelStyle}>Nombre Chofer</label>
              <input
                type="text"
                value={nombreChofer}
                onChange={(e) => setNombreChofer(e.target.value)}
                style={inputStyle}
              />
            </div>

            {/* Suplidor */}
            <div>
              <label style={labelStyle}>Suplidor</label>
              <input
                type="text"
                value={suplidor}
                onChange={(e) => setSuplidor(e.target.value)}
                style={inputStyle}
              />
            </div>

            {/* Producto */}
            <div>
              <label style={labelStyle}>Producto</label>
              <input
                type="text"
                value={producto}
                onChange={(e) => setProducto(e.target.value)}
                style={inputStyle}
              />
            </div>

            {/* Planta / Almacén */}
            <div>
              <label style={labelStyle}>Planta / Almacén</label>
              <select
                value={idAlmacen}
                onChange={(e) => setIdAlmacen(e.target.value)}
                style={inputStyle}
              >
                <option value="">-- Seleccionar Planta --</option>
                {almacenes.map((alm) => (
                  <option key={alm.idAlmacen} value={alm.idAlmacen}>
                    {alm.nombre || alm.idAlmacen}
                  </option>
                ))}
              </select>
            </div>

            {/* Cantidad Declarada */}
            <div>
              <label style={labelStyle}>Cantidad Declarada</label>
              <input
                type="number"
                step="any"
                value={cantidadDeclarada}
                onChange={(e) => setCantidadDeclarada(e.target.value)}
                style={inputStyle}
              />
            </div>

            {/* Cantidad Recibida */}
            <div>
              <label style={labelStyle}>Cantidad Recibida</label>
              <input
                type="number"
                step="any"
                value={cantidadRecibida}
                onChange={(e) => setCantidadRecibida(e.target.value)}
                style={inputStyle}
              />
            </div>

            {/* Unidad */}
            <div>
              <label style={labelStyle}>Unidad de Medida</label>
              <select
                value={idUnidad}
                onChange={(e) => setIdUnidad(e.target.value)}
                style={inputStyle}
              >
                {unidades.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </select>
            </div>

            {/* Orden de Compra */}
            <div>
              <label style={labelStyle}>No. Orden de Compra (OC)</label>
              <input
                type="number"
                value={ordenNumero}
                onChange={(e) => setOrdenNumero(e.target.value)}
                placeholder="Ej: 67162"
                style={inputStyle}
              />
            </div>

            {/* Fecha Entrada */}
            <div>
              <label style={labelStyle}>Fecha / Hora Entrada</label>
              <input
                type="datetime-local"
                value={fechaEntrada}
                onChange={(e) => setFechaEntrada(e.target.value)}
                style={inputStyle}
              />
            </div>
          </div>

          {/* Notas */}
          <div>
            <label style={labelStyle}>Notas / Observaciones</label>
            <textarea
              rows={2}
              value={notas}
              onChange={(e) => setNotas(e.target.value)}
              placeholder="Notas aclaratorias o motivo de la edición..."
              style={{ ...inputStyle, resize: 'vertical' }}
            />
          </div>

          {/* Footer Buttons */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: 12,
              marginTop: 10,
              paddingTop: 16,
              borderTop: '1px solid #374151',
            }}
          >
            <button
              type="button"
              onClick={onClose}
              disabled={guardando}
              style={{
                padding: '9px 18px',
                background: '#4B5563',
                color: 'white',
                border: 'none',
                borderRadius: 6,
                cursor: 'pointer',
                fontWeight: 600,
                fontSize: '13px',
              }}
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={guardando}
              style={{
                padding: '9px 22px',
                background: guardando ? '#9CA3AF' : '#2563EB',
                color: 'white',
                border: 'none',
                borderRadius: 6,
                cursor: guardando ? 'wait' : 'pointer',
                fontWeight: 700,
                fontSize: '14px',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
              }}
            >
              {guardando ? '⏳ Guardando...' : '💾 Guardar Cambios (Validar Código)'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: '12px',
  fontWeight: 600,
  color: '#D1D5DB',
  marginBottom: 4,
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  background: '#111827',
  border: '1px solid #4B5563',
  borderRadius: 6,
  padding: '8px 10px',
  color: '#F9FAFB',
  fontSize: '13px',
  boxSizing: 'border-box',
};

export default EditarConduceModal;
