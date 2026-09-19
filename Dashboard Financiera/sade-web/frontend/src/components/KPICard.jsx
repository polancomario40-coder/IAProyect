import { clsx } from 'clsx'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

const VARIANTS = {
  blue:   { card: 'border-l-4 border-blue-500',  icon: 'bg-blue-50 text-blue-600',   title: 'text-blue-600'  },
  green:  { card: 'border-l-4 border-emerald-500', icon: 'bg-emerald-50 text-emerald-600', title: 'text-emerald-600' },
  red:    { card: 'border-l-4 border-red-500',   icon: 'bg-red-50 text-red-600',     title: 'text-red-600'   },
  yellow: { card: 'border-l-4 border-amber-500', icon: 'bg-amber-50 text-amber-600', title: 'text-amber-600' },
}

/**
 * KPICard — Tarjeta de indicador clave de negocio
 *
 * Props:
 *   title     string   Etiqueta del KPI
 *   value     string   Valor formateado
 *   subtitle  string?  Texto secundario
 *   icon      React    Icono (lucide)
 *   variant   string   'blue' | 'green' | 'red' | 'yellow'
 *   trend     number?  % de cambio respecto al período anterior
 */
export default function KPICard({ title, value, subtitle, icon: Icon, variant = 'blue', trend }) {
  const v = VARIANTS[variant] || VARIANTS.blue
  const TrendIcon = trend > 0 ? TrendingUp : trend < 0 ? TrendingDown : Minus
  const trendColor = trend > 0 ? 'text-emerald-600' : trend < 0 ? 'text-red-500' : 'text-slate-400'

  return (
    <div className={clsx('bg-white rounded-xl shadow-sm p-5', v.card)}>
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className={clsx('text-xs font-semibold uppercase tracking-wide', v.title)}>{title}</p>
          <p className="mt-1 text-2xl font-bold text-slate-900 truncate">{value}</p>
          {subtitle && <p className="mt-1 text-xs text-slate-500">{subtitle}</p>}
          {trend !== undefined && (
            <div className={clsx('flex items-center gap-1 mt-2 text-xs font-medium', trendColor)}>
              <TrendIcon size={12} />
              <span>{Math.abs(trend).toFixed(1)}% vs. mes anterior</span>
            </div>
          )}
        </div>
        {Icon && (
          <div className={clsx('ml-3 p-2.5 rounded-lg flex-shrink-0', v.icon)}>
            <Icon size={22} />
          </div>
        )}
      </div>
    </div>
  )
}
