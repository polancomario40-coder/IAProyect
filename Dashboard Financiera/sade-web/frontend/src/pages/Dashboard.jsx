import { Wallet, TrendingUp, AlertTriangle, Percent, RefreshCw, AlertCircle } from 'lucide-react'
import KPICard from '../components/KPICard'
import CobrosChart from '../components/CobrosChart'
import { useDashboardKPIs, useCobrosporMes } from '../hooks/useApi'

const fmt = (n) =>
  new Intl.NumberFormat('es-DO', {
    style: 'currency',
    currency: 'DOP',
    minimumFractionDigits: 2,
  }).format(n ?? 0)

const fmtCompact = (n) =>
  new Intl.NumberFormat('es-DO', {
    style: 'currency',
    currency: 'DOP',
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(n ?? 0)

function ErrorBanner({ message }) {
  return (
    <div className="flex items-center gap-3 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
      <AlertCircle size={16} className="flex-shrink-0" />
      <span>{message}</span>
    </div>
  )
}

export default function Dashboard() {
  const {
    data: kpis,
    isLoading: kpisLoading,
    isError: kpisError,
    error: kpisErr,
    refetch,
    isFetching,
  } = useDashboardKPIs()

  const { data: cobros, isLoading: cobrosLoading } = useCobrosporMes(12)

  const now = new Date()
  const mesActual = now.toLocaleDateString('es-DO', { month: 'long', year: 'numeric' })

  return (
    <div className="p-4 lg:p-6 space-y-6 max-w-screen-2xl mx-auto">

      {/* ── Page header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-0.5 capitalize">Período: {mesActual}</p>
        </div>
        <button
          onClick={refetch}
          disabled={isFetching}
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={15} className={isFetching ? 'animate-spin' : ''} />
          Actualizar
        </button>
      </div>

      {/* ── Error ── */}
      {kpisError && <ErrorBanner message={kpisErr?.message || 'Error al conectar con el servidor'} />}

      {/* ── KPI Cards ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <KPICard
          title="Cartera Activa"
          value={kpisLoading ? '...' : fmtCompact(kpis?.capitalPendiente)}
          subtitle={kpisLoading ? '' : `${kpis?.totalPrestamos ?? 0} préstamos activos`}
          icon={Wallet}
          variant="blue"
        />
        <KPICard
          title="Cobrado Este Mes"
          value={kpisLoading ? '...' : fmtCompact(kpis?.totalCobradoMes)}
          subtitle={kpisLoading ? '' : `${kpis?.recibosMes ?? 0} recibos emitidos`}
          icon={TrendingUp}
          variant="green"
        />
        <KPICard
          title="Préstamos Atrasados"
          value={kpisLoading ? '...' : String(kpis?.prestamosAtrasados ?? 0)}
          subtitle={kpisLoading ? '' : `Mora pendiente: ${fmt(kpis?.morasPendientes)}`}
          icon={AlertTriangle}
          variant="red"
        />
        <KPICard
          title="Tasa de Mora"
          value={kpisLoading ? '...' : `${Number(kpis?.tasaMora ?? 0).toFixed(1)}%`}
          subtitle={kpisLoading ? '' : `Intereses pend.: ${fmtCompact(kpis?.interesesPendientes)}`}
          icon={Percent}
          variant="yellow"
        />
      </div>

      {/* ── Gráfico de Cobros por Mes ── */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-slate-900">Cobros por Mes</h2>
            <p className="text-xs text-slate-400 mt-0.5">Últimos 12 meses — Capital, Interés y Mora</p>
          </div>
        </div>
        <div className="px-2 py-4">
          <CobrosChart data={cobros} loading={cobrosLoading} />
        </div>
      </div>

      {/* ── Panel de Detalle Rápido ── */}
      {!kpisLoading && kpis && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <MetricCard label="Capital Original" value={fmt(kpis.capitalOriginal)} color="text-blue-700" />
          <MetricCard label="Capital Cobrado (mes)" value={fmt(kpis.capitalCobradoMes)} color="text-emerald-700" />
          <MetricCard label="Interés Cobrado (mes)" value={fmt(kpis.interesCobradoMes)} color="text-indigo-700" />
        </div>
      )}
    </div>
  )
}

function MetricCard({ label, value, color }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-4 flex items-center justify-between">
      <span className="text-sm text-slate-500">{label}</span>
      <span className={`font-mono font-semibold tabular-nums ${color}`}>{value}</span>
    </div>
  )
}
