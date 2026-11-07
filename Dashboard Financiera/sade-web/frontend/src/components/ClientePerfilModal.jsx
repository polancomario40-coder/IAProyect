import { useState } from 'react'
import {
  X,
  User,
  Building,
  CreditCard,
  FileSpreadsheet,
  FileText,
  ExternalLink,
  Phone,
  MapPin,
  Calendar,
  AlertCircle,
  CheckCircle2,
  Clock,
  Sparkles,
  History,
} from 'lucide-react'
import { clsx } from 'clsx'
import { useHistorialCliente } from '../hooks/useApi'
import { exportarHistorialClienteExcel, exportarHistorialClientePDF } from '../utils/exportUtils'
import { Link } from 'react-router-dom'

const fmtMoney = (n) =>
  new Intl.NumberFormat('es-DO', {
    style: 'currency',
    currency: 'DOP',
    minimumFractionDigits: 2,
  }).format(n ?? 0)

const fmtDate = (d) =>
  d
    ? new Date(d).toLocaleDateString('es-DO', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
      })
    : '—'

export default function ClientePerfilModal({ idCliente, onClose }) {
  const { data, isLoading, isError, error } = useHistorialCliente(idCliente)
  const cliente = data?.cliente
  const prestamos = data?.prestamos ?? []

  if (!idCliente) return null

  const esReenganchado = (cliente?.totalPrestamos ?? 0) > 1 || cliente?.clasificacionGlobal === 'REENGANCHADO'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-4xl max-h-[92vh] flex flex-col overflow-hidden">
        
        {/* Header Modal */}
        <div className="px-6 py-4 bg-gradient-to-r from-[#1e3a5f] to-blue-900 text-white flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white/10 rounded-xl">
              <User size={24} className="text-blue-300" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-lg font-bold">
                  {cliente?.nombreCompleto || (isError ? `Expediente del Cliente` : 'Cargando perfil...')}
                </h2>
                {cliente && (
                  <span
                    className={clsx(
                      'px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider',
                      esReenganchado
                        ? 'bg-blue-500/30 text-blue-200 border border-blue-400/40'
                        : 'bg-emerald-500/30 text-emerald-200 border border-emerald-400/40'
                    )}
                  >
                    {esReenganchado ? '🔄 Reenganchado' : '✨ Nuevo'}
                  </span>
                )}
              </div>
              <p className="text-xs text-blue-200 mt-0.5">
                Cédula: {cliente?.cedula || '—'} | ID: #{cliente?.idCliente ?? idCliente}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {cliente && (
              <>
                <button
                  onClick={() => exportarHistorialClienteExcel(cliente, prestamos)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors shadow-sm"
                  title="Descargar historial en Excel"
                >
                  <FileSpreadsheet size={14} />
                  Excel
                </button>
                <button
                  onClick={() => exportarHistorialClientePDF(cliente, prestamos)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-rose-600 hover:bg-rose-700 text-white rounded-lg transition-colors shadow-sm"
                  title="Descargar estado de cuenta en PDF"
                >
                  <FileText size={14} />
                  PDF
                </button>
              </>
            )}
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-white/70 hover:text-white hover:bg-white/10 transition-colors ml-2"
            >
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Contenido Modal */}
        <div className="p-6 overflow-y-auto space-y-6 divide-y divide-slate-100 flex-1">
          {isLoading ? (
            <div className="py-16 text-center space-y-3">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-blue-600 border-t-transparent" />
              <p className="text-sm text-slate-500 font-medium">Cargando expediente integral del cliente...</p>
            </div>
          ) : isError ? (
            <div className="p-5 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-start gap-3">
              <AlertCircle size={22} className="text-red-500 flex-shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="font-semibold text-red-900">
                  No se pudo cargar el expediente del cliente (ID #{idCliente})
                </p>
                <p className="text-xs text-red-700">
                  {error?.message?.toLowerCase().includes('not found')
                    ? 'El backend de FastAPI en el servidor necesita ser reiniciado para cargar la nueva ruta de historial (/api/clientes/{id}/historial) o actualizar los archivos del backend.'
                    : error?.message || 'Error al consultar la base de datos.'}
                </p>
              </div>
            </div>
          ) : cliente ? (
            <>
              {/* Sección 1: Datos Personales, Laborales y Creador */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Columna 1: Contacto y Ubicación */}
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200/60 space-y-2">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-1">
                    Contacto & Ubicación
                  </span>
                  <div className="text-sm flex items-center gap-2 text-slate-700">
                    <Phone size={14} className="text-slate-400" />
                    <span>{cliente.telefono || 'Sin teléfono'}</span>
                  </div>
                  <div className="text-sm flex items-start gap-2 text-slate-700">
                    <MapPin size={14} className="text-slate-400 mt-0.5 flex-shrink-0" />
                    <span className="text-xs leading-relaxed">{cliente.direccion || 'Sin dirección registrada'}</span>
                  </div>
                  <div className="text-xs text-slate-500 pt-1">
                    Oficina: <span className="font-medium text-slate-700">{cliente.oficina || '—'}</span>
                  </div>
                </div>

                {/* Columna 2: Empresa & Empleo */}
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200/60 space-y-2">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-1">
                    Laboral & Ingresos
                  </span>
                  <div className="text-sm font-semibold text-slate-800 flex items-center gap-1.5">
                    <Building size={14} className="text-blue-500" />
                    <span className="truncate">{cliente.empresa || 'Sin empresa asignada'}</span>
                  </div>
                  <div className="text-xs text-slate-600">
                    Puesto: <span className="font-medium text-slate-800">{cliente.cargoEmpresa || '—'}</span>
                  </div>
                  <div className="text-xs text-slate-600">
                    Salario: <span className="font-medium text-emerald-700">{fmtMoney(cliente.salario)}</span>
                  </div>
                </div>

                {/* Columna 3: Registro & Creador */}
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200/60 space-y-2">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-1">
                    Ficha & Operador
                  </span>
                  <div className="text-xs text-slate-600 flex items-center gap-1.5">
                    <Calendar size={13} className="text-slate-400" />
                    Registro: <span className="font-medium text-slate-700">{fmtDate(cliente.fechaRegistro)}</span>
                  </div>
                  <div className="text-xs text-slate-600">
                    Creador / Operador: <span className="font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded">{cliente.creador && cliente.creador !== 'SADE' ? cliente.creador : '—'}</span>
                  </div>
                  <div className="text-xs text-slate-600">
                    Banco: <span className="font-medium text-slate-700">{cliente.banco || '—'}</span> {cliente.cuentaBancaria && `(${cliente.cuentaBancaria})`}
                  </div>
                </div>
              </div>

              {/* Sección 2: Referencias Personales */}
              <div className="pt-4 space-y-2">
                <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                  Referencias Personales
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {/* Ref 1 */}
                  <div className="p-3 bg-blue-50/50 rounded-xl border border-blue-100 flex items-start gap-2.5">
                    <div className="w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center flex-shrink-0">
                      1
                    </div>
                    <div className="text-xs space-y-0.5">
                      <div className="font-semibold text-slate-800">{cliente.nombreRef1 || 'Sin Referencia 1'}</div>
                      <div className="text-slate-600">Tel: <span className="font-medium text-slate-800">{cliente.telRef1 || '—'}</span></div>
                      <div className="text-slate-500">{cliente.dirRef1 || ''}</div>
                    </div>
                  </div>

                  {/* Ref 2 */}
                  <div className="p-3 bg-blue-50/50 rounded-xl border border-blue-100 flex items-start gap-2.5">
                    <div className="w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center flex-shrink-0">
                      2
                    </div>
                    <div className="text-xs space-y-0.5">
                      <div className="font-semibold text-slate-800">{cliente.nombreRef2 || 'Sin Referencia 2'}</div>
                      <div className="text-slate-600">Tel: <span className="font-medium text-slate-800">{cliente.telRef2 || '—'}</span></div>
                      <div className="text-slate-500">{cliente.dirRef2 || ''}</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Sección 3: Historial de Préstamos */}
              <div className="pt-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
                    <History size={16} className="text-blue-600" />
                    Historial de Préstamos ({prestamos.length})
                  </h3>
                  <span className="text-xs text-slate-500">
                    Haz clic en un préstamo para ver sus cuotas y recibos
                  </span>
                </div>

                <div className="border border-slate-200 rounded-xl overflow-hidden shadow-sm">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-slate-50 text-slate-500 font-semibold border-b border-slate-200">
                      <tr>
                        <th className="px-3 py-2.5">Préstamo #</th>
                        <th className="px-3 py-2.5">Fecha</th>
                        <th className="px-3 py-2.5">Monto Original</th>
                        <th className="px-3 py-2.5">Tasa</th>
                        <th className="px-3 py-2.5">Total Pagado</th>
                        <th className="px-3 py-2.5">Balance Total</th>
                        <th className="px-3 py-2.5">Monto Saldar Hoy</th>
                        <th className="px-3 py-2.5">Estado</th>
                        <th className="px-3 py-2.5 text-center">Acción</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {prestamos.length === 0 ? (
                        <tr>
                          <td colSpan={9} className="px-4 py-8 text-center text-slate-400">
                            No hay préstamos registrados para este cliente.
                          </td>
                        </tr>
                      ) : (
                        prestamos.map((p) => {
                          const esActivo = p.estado === 'ACTIVO'
                          return (
                            <tr key={p.numeroPrestamo} className="hover:bg-slate-50 transition-colors">
                              <td className="px-3 py-2.5 font-bold font-mono text-blue-700">
                                #{p.numeroPrestamo}
                              </td>
                              <td className="px-3 py-2.5 text-slate-600">{fmtDate(p.fechaPrestamo)}</td>
                              <td className="px-3 py-2.5 font-medium text-slate-800">{fmtMoney(p.montoOriginal)}</td>
                              <td className="px-3 py-2.5 text-slate-600">{p.tasa}%</td>
                              <td className="px-3 py-2.5 text-emerald-700 font-medium">{fmtMoney(p.totalPagado)}</td>
                              <td className="px-3 py-2.5 font-semibold text-slate-800">{fmtMoney(p.balanceTotal)}</td>
                              <td className="px-3 py-2.5 font-bold text-amber-700">
                                {esActivo ? fmtMoney(p.montoSaldarHoy) : '—'}
                              </td>
                              <td className="px-3 py-2.5">
                                <span
                                  className={clsx(
                                    'px-2 py-0.5 rounded text-[10px] font-semibold tracking-wider',
                                    esActivo
                                      ? 'bg-blue-100 text-blue-700 border border-blue-200'
                                      : 'bg-zinc-100 text-zinc-600 border border-zinc-200'
                                  )}
                                >
                                  {p.estado}
                                </span>
                              </td>
                              <td className="px-3 py-2.5 text-center">
                                <Link
                                  to={`/prestamos/${p.numeroPrestamo}`}
                                  onClick={onClose}
                                  className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors"
                                  title="Ver detalle del préstamo"
                                >
                                  Ver Estado
                                  <ExternalLink size={11} />
                                </Link>
                              </td>
                            </tr>
                          )
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 bg-slate-50 border-t border-slate-200 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-200 hover:bg-slate-100 rounded-lg transition-colors"
          >
            Cerrar
          </button>
        </div>

      </div>
    </div>
  )
}
