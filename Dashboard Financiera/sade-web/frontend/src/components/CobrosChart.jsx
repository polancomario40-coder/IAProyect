import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

const fmt = (n) =>
  new Intl.NumberFormat('es-DO', {
    style: 'currency',
    currency: 'DOP',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(n ?? 0)

const fmtFull = (n) =>
  new Intl.NumberFormat('es-DO', { style: 'currency', currency: 'DOP', minimumFractionDigits: 2 }).format(n ?? 0)

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-slate-200 shadow-lg rounded-lg p-3 text-xs min-w-36">
      <p className="font-semibold text-slate-700 mb-2">{label}</p>
      {payload.map((p) => (
        <div key={p.dataKey} className="flex justify-between gap-4 items-center">
          <span style={{ color: p.color }} className="font-medium">{p.name}</span>
          <span className="font-mono tabular-nums text-slate-800">{fmtFull(p.value)}</span>
        </div>
      ))}
      <div className="border-t border-slate-100 mt-1.5 pt-1.5 flex justify-between">
        <span className="text-slate-500">Total</span>
        <span className="font-mono font-semibold">
          {fmtFull(payload.reduce((s, p) => s + (p.value || 0), 0))}
        </span>
      </div>
    </div>
  )
}

/**
 * CobrosChart — Gráfico de barras apiladas de cobros por mes
 *
 * Props:
 *   data     array   Lista de { mesEtiqueta, capitalCobrado, interesCobrado, moraCobrada }
 *   loading  boolean
 */
export default function CobrosChart({ data = [], loading }) {
  if (loading) {
    return (
      <div className="h-72 flex items-end gap-2 px-4 pb-4">
        {Array.from({ length: 12 }).map((_, i) => (
          <div
            key={i}
            className="flex-1 bg-slate-200 animate-pulse rounded-t"
            style={{ height: `${Math.random() * 60 + 20}%` }}
          />
        ))}
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart
        data={data}
        margin={{ top: 4, right: 8, left: 8, bottom: 0 }}
        barCategoryGap="30%"
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
        <XAxis
          dataKey="mesEtiqueta"
          tick={{ fontSize: 11, fill: '#64748b' }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tickFormatter={fmt}
          tick={{ fontSize: 11, fill: '#64748b' }}
          axisLine={false}
          tickLine={false}
          width={70}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ fill: '#f1f5f9' }} />
        <Legend
          iconType="circle"
          iconSize={8}
          wrapperStyle={{ fontSize: 12, paddingTop: 12 }}
        />
        <Bar dataKey="capitalCobrado" name="Capital"  stackId="a" fill="#3b82f6" radius={[0, 0, 0, 0]} />
        <Bar dataKey="interesCobrado" name="Interés"  stackId="a" fill="#6366f1" radius={[0, 0, 0, 0]} />
        <Bar dataKey="moraCobrada"    name="Mora"     stackId="a" fill="#f59e0b" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
