/**
 * ClientesTable.jsx — Tabla de clientes con paginación, badges y skeleton loader
 *
 * Props:
 *   clientes        array    Lista de objetos cliente
 *   loading         bool     Muestra skeleton si true
 *   pagina          number   Página actual (1-based)
 *   totalPaginas    number   Total de páginas
 *   onPaginaChange  fn       (nuevaPagina) => void
 */
import { clsx } from 'clsx'
import { ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react'
import { Link } from 'react-router-dom'

const fmt = n =>
  new Intl.NumberFormat('es-DO', {
    style: 'currency',
    currency: 'DOP',
    minimumFractionDigits: 2,
  }).format(n ?? 0)

const BADGE = {
  'NUEVO':        'bg-emerald-100 text-emerald-700',
  'REENGANCHADO': 'bg-blue-100 text-blue-700',
  'EN MORA':      'bg-red-100 text-red-700',
  'PROBLEMATICO': 'bg-amber-100 text-amber-700',
  'AL DIA':       'bg-slate-100 text-slate-600',
}

const ROW_BG = {
  'EN MORA':      'bg-red-50/40',
  'PROBLEMATICO': 'bg-amber-50/40',
}

const HEADERS = [
  'Cliente', 'Cédula', 'Teléfono', 'Empresa',
  'Préstamo #', 'Balance', 'Gestor', 'Fecha',
]

// ── Skeleton ──────────────────────────────────────────────────────────────────

function SkeletonRow() {
  return (
    <tr className="border-b border-slate-100">
      {HEADERS.map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 bg-slate-200 rounded animate-pulse" style={{ width: i === 0 ? '80%' : '60%' }} />
          {i === 0 && <div className="h-3 bg-slate-100 rounded animate-pulse mt-1.5 w-2/5" />}
        </td>
      ))}
    </tr>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function ClientesTable({
  clientes = [],
  loading = false,
  pagina = 1,
  totalPaginas = 1,
  onPaginaChange,
}) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200">
              {HEADERS.map(h => (
                <th
                  key={h}
                  className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide whitespace-nowrap"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-100">
            {loading ? (
              Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} />)
            ) : clientes.length === 0 ? (
              <tr>
                <td colSpan={HEADERS.length} className="px-4 py-12 text-center text-slate-400 text-sm">
                  No se encontraron clientes con los filtros aplicados.
                </td>
              </tr>
            ) : (
              clientes.map(c => {
                const clasificacion = (c.clasificacion || '').toUpperCase()
                const rowBg = ROW_BG[clasificacion] || ''
                const badgeClass = BADGE[clasificacion] || 'bg-slate-100 text-slate-500'

                return (
                  <tr key={c.idCliente ?? c.cedula} className={clsx('hover:bg-slate-50 transition-colors', rowBg)}>
                    {/* Cliente */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="font-medium text-slate-800 flex items-center gap-1.5">
                        {c.numeroPrestamo ? (
                          <Link
                            to={`/prestamos/${c.numeroPrestamo}`}
                            className="hover:text-blue-600 hover:underline flex items-center gap-1"
                            title="Ver Estado de Préstamo"
                          >
                            {c.nombreCompleto || c.nombreCliente || 'Sin nombre'}
                            <ExternalLink size={12} className="text-slate-400" />
                          </Link>
                        ) : (
                          <span>{c.nombreCompleto || c.nombreCliente || 'Sin nombre'}</span>
                        )}
                      </div>
                      {clasificacion && (
                        <span className={clsx('inline-block mt-0.5 px-1.5 py-0.5 rounded text-[10px] font-semibold leading-tight', badgeClass)}>
                          {clasificacion}
                        </span>
                      )}
                    </td>

                    {/* Cédula */}
                    <td className="px-4 py-3 text-slate-600 whitespace-nowrap">{c.cedula ?? '—'}</td>

                    {/* Teléfono */}
                    <td className="px-4 py-3 text-slate-600 whitespace-nowrap">{c.telefono ?? '—'}</td>

                    {/* Empresa */}
                    <td className="px-4 py-3">
                      {c.empresa ? (
                        <>
                          <div className="font-semibold text-slate-800 whitespace-nowrap">{c.empresa}</div>
                          {c.cargoEmpresa && (
                            <div className="text-xs text-slate-500 whitespace-nowrap">{c.cargoEmpresa}</div>
                          )}
                        </>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>

                    {/* Préstamo # */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      {c.numeroPrestamo ? (
                        <Link
                          to={`/prestamos/${c.numeroPrestamo}`}
                          className="inline-flex items-center gap-1 font-mono font-bold text-blue-600 hover:text-blue-800 bg-blue-50 px-2 py-0.5 rounded hover:underline"
                          title="Ir al detalle del préstamo"
                        >
                          #{c.numeroPrestamo}
                          <ExternalLink size={12} />
                        </Link>
                      ) : (
                        <span className="text-slate-400 font-mono">—</span>
                      )}
                    </td>

                    {/* Balance */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="font-semibold text-slate-800">{fmt(c.balanceActual)}</div>
                      <div className="text-xs text-slate-400">
                        {fmt(c.capitalPagado)} / {fmt(c.montoActual)}
                      </div>
                    </td>

                    {/* Gestor */}
                    <td className="px-4 py-3 text-slate-600 whitespace-nowrap">{c.gestor ?? '—'}</td>

                    {/* Fecha */}
                    <td className="px-4 py-3 text-slate-500 whitespace-nowrap">
                      {c.fechaRegistro ? new Date(c.fechaRegistro).toLocaleDateString('es-DO') : (c.fechaPrestamo ? new Date(c.fechaPrestamo).toLocaleDateString('es-DO') : '—')}
                    </td>
                  </tr>
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
