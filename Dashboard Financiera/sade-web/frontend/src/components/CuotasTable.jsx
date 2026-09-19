import { clsx } from 'clsx'

const fmt = (n) =>
  new Intl.NumberFormat('es-DO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n ?? 0)

const fmtDate = (d) =>
  d ? new Date(d + 'T00:00:00').toLocaleDateString('es-DO', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '—'

const STATUS_STYLES = {
  PAGADA:   'bg-emerald-100 text-emerald-700',
  VENCIDA:  'bg-red-100 text-red-700',
  PENDIENTE:'bg-slate-100 text-slate-600',
}

/**
 * CuotasTable — Tabla de cuotas del préstamo
 *
 * Props:
 *   cuotas  array    Lista de cuotas del backend
 *   loading boolean
 */
export default function CuotasTable({ cuotas = [], loading }) {
  if (loading) {
    return <TableSkeleton rows={8} cols={6} />
  }

  return (
    <div className="overflow-auto scrollbar-thin rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full text-xs">
        <thead>
          <tr className="bg-slate-50 border-b border-slate-200">
            {['#', 'Fecha', 'Balance', 'Capital', 'Interés', 'Mora', 'Estado'].map((h) => (
              <th
                key={h}
                className="px-3 py-2.5 text-left font-semibold text-slate-600 uppercase tracking-wide whitespace-nowrap"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {cuotas.map((c) => (
            <tr
              key={c.idCuota}
              className={clsx(
                'hover:bg-slate-50 transition-colors',
                c.estadoCuota === 'VENCIDA' && 'bg-red-50 hover:bg-red-100',
                c.estadoCuota === 'PAGADA'  && 'bg-emerald-50/40'
              )}
            >
              <td className="px-3 py-2 font-mono text-slate-600 font-medium">{c.numCuota}</td>
              <td className="px-3 py-2 text-slate-700 whitespace-nowrap">{fmtDate(c.fecha)}</td>
              <td className="px-3 py-2 font-mono tabular-nums text-right text-slate-800">{fmt(c.balance)}</td>
              <td className="px-3 py-2 font-mono tabular-nums text-right text-slate-800">{fmt(c.capital)}</td>
              <td className="px-3 py-2 font-mono tabular-nums text-right text-slate-800">{fmt(c.interes)}</td>
              <td className="px-3 py-2 font-mono tabular-nums text-right text-amber-700">{fmt(c.mora)}</td>
              <td className="px-3 py-2">
                <span
                  className={clsx(
                    'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium',
                    STATUS_STYLES[c.estadoCuota]
                  )}
                >
                  {c.estadoCuota}
                </span>
              </td>
            </tr>
          ))}
          {cuotas.length === 0 && (
            <tr>
              <td colSpan={7} className="px-4 py-8 text-center text-slate-400 text-sm">
                No hay cuotas registradas
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function TableSkeleton({ rows, cols }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
      <div className="bg-slate-50 border-b border-slate-200 h-10" />
      <div className="divide-y divide-slate-100">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex gap-4 px-3 py-2">
            {Array.from({ length: cols }).map((_, j) => (
              <div key={j} className="h-4 bg-slate-200 animate-pulse rounded flex-1" />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
