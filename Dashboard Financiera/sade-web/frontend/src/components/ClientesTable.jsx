/**
 * ClientesTable.jsx — Tabla de clientes con ordenamiento multi-columna,
 * referencias expandibles, monto para saldar hoy y acceso al perfil integral.
 */
import React, { useState, useMemo } from 'react'
import { clsx } from 'clsx'
import {
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  User,
  Users,
  Phone,
  MapPin,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Info,
} from 'lucide-react'
import { Link } from 'react-router-dom'

const fmt = (n) =>
  new Intl.NumberFormat('es-DO', {
    style: 'currency',
    currency: 'DOP',
    minimumFractionDigits: 2,
  }).format(n ?? 0)

const BADGE = {
  'NUEVO':        'bg-emerald-100 text-emerald-700 border border-emerald-200',
  'REENGANCHADO': 'bg-blue-100 text-blue-700 border border-blue-200',
  'EN MORA':      'bg-red-100 text-red-700 border border-red-200',
  'PROBLEMATICO': 'bg-amber-100 text-amber-700 border border-amber-200',
  'AL DIA':       'bg-slate-100 text-slate-600 border border-slate-200',
  'CANCELADO':    'bg-zinc-100 text-zinc-600 border border-zinc-200',
  'SALDADO':      'bg-zinc-100 text-zinc-600 border border-zinc-200',
}

const ROW_BG = {
  'EN MORA':      'bg-red-50/40',
  'PROBLEMATICO': 'bg-amber-50/40',
  'CANCELADO':    'bg-slate-50/40 opacity-85',
}

const SORTABLE_COLUMNS = [
  { id: 'cliente',       label: 'Cliente / Nombre' },
  { id: 'cedula',        label: 'Cédula' },
  { id: 'empresa',       label: 'Empresa' },
  { id: 'prestamo',      label: 'Préstamo #' },
  { id: 'balance',       label: 'Balance Total' },
  { id: 'montosaldar',   label: 'Saldar Hoy' },
  { id: 'creador',       label: 'Creador' },
  { id: 'fecha',         label: 'Fecha' },
]

function SkeletonRow() {
  return (
    <tr className="border-b border-slate-100">
      <td className="w-10 px-3 py-3" />
      {Array.from({ length: 8 }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 bg-slate-200 rounded animate-pulse" style={{ width: i === 0 ? '80%' : '60%' }} />
          {i === 0 && <div className="h-3 bg-slate-100 rounded animate-pulse mt-1.5 w-2/5" />}
        </td>
      ))}
      <td className="w-16 px-3 py-3" />
    </tr>
  )
}

export default function ClientesTable({
  clientes = [],
  loading = false,
  pagina = 1,
  totalPaginas = 1,
  onPaginaChange,
  ordenarPor = 'fechaRegistro',
  ordenDireccion = 'DESC',
  onSortChange,
  onVerPerfil,
}) {
  const [expandedRows, setExpandedRows] = useState({})

  function toggleRow(id) {
    setExpandedRows((prev) => ({
      ...prev,
      [id]: !prev[id],
    }))
  }

  function handleHeaderClick(colId) {
    if (!onSortChange) return
    const current = (ordenarPor || 'fecha').toLowerCase()
    const target = colId.toLowerCase()
    if (current === target || (target === 'fecha' && current === 'fecharegistro')) {
      onSortChange(colId, ordenDireccion === 'ASC' ? 'DESC' : 'ASC')
    } else {
      onSortChange(colId, colId === 'fecha' ? 'DESC' : 'ASC')
    }
  }

  // Ordenamiento client-side inmediato para máxima fluidez
  const sortedClientes = useMemo(() => {
    if (!clientes || clientes.length === 0) return []
    const copy = [...clientes]
    const dir = ordenDireccion === 'DESC' ? -1 : 1
    const col = (ordenarPor || 'fecha').toLowerCase()

    return copy.sort((a, b) => {
      let valA, valB
      switch (col) {
        case 'cliente':
          valA = (a.nombreCompleto || '').toLowerCase()
          valB = (b.nombreCompleto || '').toLowerCase()
          return valA.localeCompare(valB) * dir
        case 'cedula':
          valA = a.cedula || ''
          valB = b.cedula || ''
          return valA.localeCompare(valB) * dir
        case 'empresa':
          valA = (a.empresa || '').toLowerCase()
          valB = (b.empresa || '').toLowerCase()
          return valA.localeCompare(valB) * dir
        case 'prestamo':
          valA = Number(a.numeroPrestamo) || 0
          valB = Number(b.numeroPrestamo) || 0
          return (valA - valB) * dir
        case 'balance':
          valA = Number(a.balanceActual) || 0
          valB = Number(b.balanceActual) || 0
          return (valA - valB) * dir
        case 'montosaldar':
          valA = Number(a.montoSaldarHoy) || 0
          valB = Number(b.montoSaldarHoy) || 0
          return (valA - valB) * dir
        case 'creador':
          valA = (a.creador || '').toLowerCase()
          valB = (b.creador || '').toLowerCase()
          return valA.localeCompare(valB) * dir
        case 'fecha':
        case 'fecharegistro':
        default:
          valA = a.fechaRegistro ? new Date(a.fechaRegistro).getTime() : 0
          valB = b.fechaRegistro ? new Date(b.fechaRegistro).getTime() : 0
          return (valA - valB) * dir
      }
    })
  }, [clientes, ordenarPor, ordenDireccion])

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200 select-none">
              <th className="w-8 px-2 py-3 text-center" />
              {SORTABLE_COLUMNS.map((col) => {
                const isSorted = ordenarPor.toLowerCase() === col.id.toLowerCase()
                return (
                  <th
                    key={col.id}
                    onClick={() => handleHeaderClick(col.id)}
                    className="px-4 py-3 text-left text-xs font-semibold text-slate-600 uppercase tracking-wide whitespace-nowrap cursor-pointer hover:bg-slate-100 transition-colors"
                  >
                    <div className="flex items-center gap-1.5">
                      <span>{col.label}</span>
                      <span className="text-slate-400">
                        {isSorted ? (
                          ordenDireccion === 'ASC' ? (
                            <ArrowUp size={14} className="text-blue-600 stroke-[2.5]" />
                          ) : (
                            <ArrowDown size={14} className="text-blue-600 stroke-[2.5]" />
                          )
                        ) : (
                          <ArrowUpDown size={12} className="opacity-40" />
                        )}
                      </span>
                    </div>
                  </th>
                )
              })}
              <th className="px-3 py-3 text-center text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Ficha
              </th>
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-100">
            {loading ? (
              Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} />)
            ) : sortedClientes.length === 0 ? (
              <tr>
                <td colSpan={10} className="px-4 py-12 text-center text-slate-400 text-sm">
                  No se encontraron clientes con los filtros aplicados.
                </td>
              </tr>
            ) : (
              sortedClientes.map((c) => {
                const clasificacion = (c.clasificacion || '').toUpperCase()
                const rowBg = ROW_BG[clasificacion] || ''
                const isExpanded = !!expandedRows[c.idCliente]
                const tieneReferencias = !!(c.nombreRef1 || c.nombreRef2)
                const esReenganchado = (c.totalPrestamos ?? 0) > 1 || clasificacion === 'REENGANCHADO'
                const esMora = clasificacion === 'EN MORA'

                return (
                  <React.Fragment key={c.idCliente ?? c.cedula}>
                    <tr
                      className={clsx(
                        'hover:bg-slate-50/80 transition-colors group',
                        rowBg,
                        isExpanded && 'bg-blue-50/30'
                      )}
                    >
                      {/* Botón Expandir Referencias */}
                      <td className="px-2 py-3 text-center">
                        {tieneReferencias ? (
                          <button
                            onClick={() => toggleRow(c.idCliente)}
                            className="p-1 rounded text-slate-400 hover:text-blue-600 hover:bg-slate-100 transition-colors"
                            title={isExpanded ? 'Ocultar referencias' : 'Ver referencias personales'}
                          >
                            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                          </button>
                        ) : (
                          <span className="inline-block w-4" />
                        )}
                      </td>

                      {/* Cliente */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="font-semibold text-slate-800 flex items-center gap-1.5">
                          <button
                            onClick={() => onVerPerfil?.(c.idCliente)}
                            className="text-left hover:text-blue-600 hover:underline"
                            title="Ver perfil integral del cliente"
                          >
                            {c.nombreCompleto || 'Sin nombre'}
                          </button>
                        </div>
                        <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                          {/* Badge de Historial */}
                          <span
                            className={clsx(
                              'px-1.5 py-0.2 rounded text-[10px] font-bold leading-tight',
                              esReenganchado
                                ? 'bg-blue-100 text-blue-700 border border-blue-200'
                                : 'bg-emerald-100 text-emerald-700 border border-emerald-200'
                            )}
                          >
                            {esReenganchado ? 'REENGANCHADO' : 'NUEVO'}
                          </span>

                          {/* Badge Financiero / Cartera */}
                          {c.esProblematico ? (
                            <span className="px-1.5 py-0.2 rounded text-[10px] font-bold leading-tight bg-amber-100 text-amber-800 border border-amber-200">
                              PROBLEMÁTICO
                            </span>
                          ) : c.estadoCartera === 'CANCELADO' ? (
                            <span className="px-1.5 py-0.2 rounded text-[10px] font-bold leading-tight bg-slate-100 text-slate-600 border border-slate-200">
                              SALDADO
                            </span>
                          ) : esMora ? (
                            <span className="px-1.5 py-0.2 rounded text-[10px] font-bold leading-tight bg-red-100 text-red-700 border border-red-200">
                              EN MORA
                            </span>
                          ) : (
                            <span className="px-1.5 py-0.2 rounded text-[10px] font-bold leading-tight bg-emerald-50 text-emerald-800 border border-emerald-200">
                              AL DÍA
                            </span>
                          )}

                          <span className="text-[11px] text-slate-400 font-mono">
                            ID #{c.idCliente}
                          </span>
                        </div>
                      </td>

                      {/* Cédula */}
                      <td className="px-4 py-3 text-slate-600 whitespace-nowrap font-mono text-xs">
                        {c.cedula ?? '—'}
                      </td>

                      {/* Empresa */}
                      <td className="px-4 py-3">
                        {c.empresa ? (
                          <div className="max-w-[220px]">
                            <div className="font-medium text-slate-800 truncate" title={c.empresa}>
                              {c.empresa}
                            </div>
                            {c.cargoEmpresa && (
                              <div className="text-xs text-slate-500 truncate" title={c.cargoEmpresa}>
                                {c.cargoEmpresa}
                              </div>
                            )}
                          </div>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>

                      {/* Préstamo # */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        {c.numeroPrestamo ? (
                          <Link
                            to={`/prestamos/${c.numeroPrestamo}`}
                            className="inline-flex items-center gap-1 font-mono font-bold text-blue-600 hover:text-blue-800 bg-blue-50/80 px-2.5 py-1 rounded-md hover:underline"
                            title="Ir al detalle del préstamo"
                          >
                            #{c.numeroPrestamo}
                            <ExternalLink size={11} />
                          </Link>
                        ) : (
                          <span className="text-slate-400 font-mono">—</span>
                        )}
                      </td>

                      {/* Balance Total */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="font-semibold text-slate-900">{fmt(c.balanceActual)}</div>
                        <div className="text-[11px] text-slate-400">
                          {fmt(c.capitalPagado)} / {fmt(c.montoActual)}
                        </div>
                      </td>

                      {/* Monto para Saldar Hoy */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        {c.estadoCartera === 'ACTIVO' && c.balanceActual > 0 ? (
                          <div className="bg-amber-50/80 border border-amber-200/60 px-2 py-1 rounded-md inline-block">
                            <div className="font-bold text-amber-900 font-mono text-xs">
                              {fmt(c.montoSaldarHoy)}
                            </div>
                            <div className="text-[10px] text-amber-700">
                              Cap: {fmt(c.balanceCapital)}
                            </div>
                          </div>
                        ) : (
                          <span className="text-slate-400 font-mono text-xs">Saldado</span>
                        )}
                      </td>

                      {/* Creador (reemplaza Gestor vacío) */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium text-slate-700 bg-slate-100">
                          <User size={11} className="text-slate-400" />
                          {c.creador && c.creador !== 'SADE' ? c.creador : '—'}
                        </span>
                      </td>

                      {/* Fecha */}
                      <td className="px-4 py-3 text-slate-500 whitespace-nowrap text-xs">
                        {c.fechaRegistro
                          ? new Date(c.fechaRegistro).toLocaleDateString('es-DO')
                          : (c.fechaPrestamo
                          ? new Date(c.fechaPrestamo).toLocaleDateString('es-DO')
                          : '—')}
                      </td>

                      {/* Acción Ficha */}
                      <td className="px-3 py-3 text-center whitespace-nowrap">
                        <button
                          onClick={() => onVerPerfil?.(c.idCliente)}
                          className="px-2 py-1 text-xs font-semibold text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors"
                          title="Abrir expediente completo"
                        >
                          Expediente
                        </button>
                      </td>
                    </tr>

                    {/* Fila Expandible: Referencias Personales */}
                    {isExpanded && (
                      <tr className="bg-blue-50/40 border-b border-blue-100">
                        <td colSpan={10} className="px-6 py-3.5">
                          <div className="space-y-2">
                            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                              <Users size={13} className="text-blue-600" />
                              Referencias Personales Registradas
                            </span>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                              {/* Referencia 1 */}
                              <div className="bg-white p-3 rounded-xl border border-blue-200/80 shadow-xs flex items-start gap-2.5">
                                <div className="w-5 h-5 rounded-full bg-blue-600 text-white text-[11px] font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                                  1
                                </div>
                                <div className="text-xs space-y-0.5 min-w-0">
                                  <div className="font-bold text-slate-800">
                                    {c.nombreRef1 || 'Sin nombre registrado'}
                                  </div>
                                  <div className="text-slate-600 flex items-center gap-1">
                                    <Phone size={11} className="text-slate-400" />
                                    <span>{c.telRef1 || 'Sin teléfono'}</span>
                                  </div>
                                  {c.dirRef1 && (
                                    <div className="text-slate-500 text-[11px] flex items-start gap-1">
                                      <MapPin size={11} className="text-slate-400 mt-0.5 flex-shrink-0" />
                                      <span className="truncate">{c.dirRef1}</span>
                                    </div>
                                  )}
                                </div>
                              </div>

                              {/* Referencia 2 */}
                              <div className="bg-white p-3 rounded-xl border border-blue-200/80 shadow-xs flex items-start gap-2.5">
                                <div className="w-5 h-5 rounded-full bg-blue-600 text-white text-[11px] font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                                  2
                                </div>
                                <div className="text-xs space-y-0.5 min-w-0">
                                  <div className="font-bold text-slate-800">
                                    {c.nombreRef2 || 'Sin nombre registrado'}
                                  </div>
                                  <div className="text-slate-600 flex items-center gap-1">
                                    <Phone size={11} className="text-slate-400" />
                                    <span>{c.telRef2 || 'Sin teléfono'}</span>
                                  </div>
                                  {c.dirRef2 && (
                                    <div className="text-slate-500 text-[11px] flex items-start gap-1">
                                      <MapPin size={11} className="text-slate-400 mt-0.5 flex-shrink-0" />
                                      <span className="truncate">{c.dirRef2}</span>
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Paginación */}
      {!loading && totalPaginas > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100">
          <span className="text-xs text-slate-500">
            Página <span className="font-semibold text-slate-700">{pagina}</span> de{' '}
            <span className="font-semibold text-slate-700">{totalPaginas}</span>
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onPaginaChange?.(pagina - 1)}
              disabled={pagina <= 1}
              className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft size={14} />
              Anterior
            </button>
            <button
              onClick={() => onPaginaChange?.(pagina + 1)}
              disabled={pagina >= totalPaginas}
              className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Siguiente
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
