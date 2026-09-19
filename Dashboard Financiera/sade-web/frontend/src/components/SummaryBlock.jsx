import { clsx } from 'clsx'

const fmt = (n) =>
  new Intl.NumberFormat('es-DO', { style: 'currency', currency: 'DOP', minimumFractionDigits: 2 }).format(n ?? 0)

const VARIANTS = {
  blue:   { header: 'bg-blue-600',   border: 'border-blue-200' },
  green:  { header: 'bg-emerald-600', border: 'border-emerald-200' },
  amber:  { header: 'bg-amber-500',  border: 'border-amber-200' },
  red:    { header: 'bg-red-600',    border: 'border-red-200' },
}

/**
 * SummaryBlock — Los 4 bloques de resumen del préstamo
 * (Inicial / Pagado / Balance / Vencido)
 *
 * Props:
 *   title     string
 *   capital   number
 *   interes   number
 *   mora      number?
 *   total     number
 *   variant   'blue' | 'green' | 'amber' | 'red'
 *   showMora  boolean  (Inicial no tiene mora)
 */
export default function SummaryBlock({
  title,
  capital,
  interes,
  mora,
  total,
  variant = 'blue',
  showMora = true,
}) {
  const v = VARIANTS[variant] || VARIANTS.blue

  return (
    <div className={clsx('rounded-xl border overflow-hidden bg-white shadow-sm', v.border)}>
      {/* Header */}
      <div className={clsx('px-4 py-2.5', v.header)}>
        <h3 className="text-white text-sm font-semibold uppercase tracking-wider">{title}</h3>
      </div>

      {/* Filas */}
      <div className="px-4 py-3 space-y-2 text-sm">
        <Row label="Capital" value={fmt(capital)} />
        <Row label="Interés" value={fmt(interes)} />
        {showMora && <Row label="Mora" value={fmt(mora)} />}
        <div className="border-t border-slate-100 pt-2">
          <Row label="Total" value={fmt(total)} bold />
        </div>
      </div>
    </div>
  )
}

function Row({ label, value, bold }) {
  return (
    <div className="flex justify-between items-center gap-2">
      <span className={clsx('text-slate-500', bold && 'font-semibold text-slate-700')}>{label}</span>
      <span className={clsx('font-mono text-slate-800 tabular-nums', bold && 'font-bold text-slate-900')}>
        {value}
      </span>
    </div>
  )
}
