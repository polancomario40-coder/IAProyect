const fmt = (n) =>
  new Intl.NumberFormat('es-DO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n ?? 0)

const fmtDate = (d) =>
  d ? new Date(d + 'T00:00:00').toLocaleDateString('es-DO', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '—'

/**
 * RecibosTable — Tabla del historial de pagos (Recibos)
 *
 * Props:
 *   recibos  array    Lista de recibos del backend
 *   loading  boolean
 */
export default function RecibosTable({ recibos = [], loading }) {
  if (loading) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
        <div className="bg-slate-50 border-b border-slate-200 h-10" />
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex gap-4 px-3 py-2 border-b border-slate-100">
            {Array.from({ length: 5 }).map((_, j) => (
              <div key={j} className="h-4 bg-slate-200 animate-pulse rounded flex-1" />
            ))}
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="overflow-auto scrollbar-thin rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full text-xs">
        <thead>
          <tr className="bg-slate-50 border-b border-slate-200">
            {['Recibo #', 'Fecha', 'Total Pagado', 'Capital', 'Interés', 'Mora'].map((h) => (
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
          {recibos.map((r) => (
            <tr key={r.numeroPago} className="hover:bg-blue-50/50 transition-colors">
              <td className="px-3 py-2 font-mono font-semibold text-blue-700">{r.numeroPago}</td>
              <td className="px-3 py-2 text-slate-700 whitespace-nowrap">{fmtDate(r.fecha)}</td>
              <td className="px-3 py-2 font-mono tabular-nums text-right font-semibold text-slate-900">
                {fmt(r.totalPagado)}
              </td>
              <td className="px-3 py-2 font-mono tabular-nums text-right text-slate-700">{fmt(r.capital)}</td>
              <td className="px-3 py-2 font-mono tabular-nums text-right text-blue-700">{fmt(r.interes)}</td>
              <td className="px-3 py-2 font-mono tabular-nums text-right text-amber-700">{fmt(r.mora)}</td>
            </tr>
          ))}
          {recibos.length === 0 && (
            <tr>
              <td colSpan={6} className="px-4 py-8 text-center text-slate-400 text-sm">
                No hay recibos registrados
              </td>
            </tr>
          )}
        </tbody>
        {/* Totales */}
        {recibos.length > 0 && (
          <tfoot>
            <tr className="bg-slate-50 border-t-2 border-slate-300 font-semibold">
              <td colSpan={2} className="px-3 py-2 text-slate-600 text-xs uppercase">
                TOTALES ({recibos.length})
              </td>
              <td className="px-3 py-2 font-mono tabular-nums text-right text-slate-900">
                {fmt(recibos.reduce((s, r) => s + parseFloat(r.totalPagado || 0), 0))}
              </td>
              <td className="px-3 py-2 font-mono tabular-nums text-right text-slate-700">
                {fmt(recibos.reduce((s, r) => s + parseFloat(r.capital || 0), 0))}
              </td>
              <td className="px-3 py-2 font-mono tabular-nums text-right text-blue-700">
                {fmt(recibos.reduce((s, r) => s + parseFloat(r.interes || 0), 0))}
              </td>
              <td className="px-3 py-2 font-mono tabular-nums text-right text-amber-700">
                {fmt(recibos.reduce((s, r) => s + parseFloat(r.mora || 0), 0))}
              </td>
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  )
}
