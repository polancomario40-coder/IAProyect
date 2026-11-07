import { useParams, Link, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  User,
  Calendar,
  Percent,
  Tag,
  CreditCard,
  Receipt,
  RefreshCw,
  Search,
  Sparkles,
  Clock,
  ShieldCheck,
  Calculator,
  FileSpreadsheet,
  FileText,
} from 'lucide-react'
import { clsx } from 'clsx'
import { useState } from 'react'
import { useEstadoPrestamo } from '../hooks/useApi'
import SummaryBlock from '../components/SummaryBlock'
import CuotasTable from '../components/CuotasTable'
import RecibosTable from '../components/RecibosTable'
import ClientePerfilModal from '../components/ClientePerfilModal'
import {
  exportarCuotasExcel,
  exportarCuotasPDF,
  exportarHistorialPagosExcel,
  exportarHistorialPagosPDF,
} from '../utils/exportUtils'

const fmt = (n) =>
  new Intl.NumberFormat('es-DO', {
    style: 'currency',
    currency: 'DOP',
    minimumFractionDigits: 2,
  }).format(n ?? 0)

const fmtDate = (d) =>
  d
    ? new Date(d).toLocaleDateString('es-DO', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      })
    : '—'

function StatusBadge({ estado }) {
  const isOk = estado === 'AL DIA'
  const isSaldado = estado === 'SALDADO'
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-semibold',
        isSaldado
          ? 'bg-zinc-100 text-zinc-700 border border-zinc-300'
          : isOk
          ? 'bg-emerald-100 text-emerald-700 border border-emerald-200'
          : 'bg-red-100 text-red-700 border border-red-200'
      )}
    >
      {isSaldado ? <CheckCircle2 size={14} /> : isOk ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
      {estado}
    </span>
  )
}

function InfoPill({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-600">
      <Icon size={14} className="text-slate-400 flex-shrink-0" />
      <span className="text-slate-400">{label}:</span>
      <span className="font-medium text-slate-700">{value}</span>
    </div>
  )
}

function ErrorState({ message }) {
  return (
    <div className="p-8 flex flex-col items-center gap-3 text-center">
      <AlertCircle size={40} className="text-red-400" />
      <p className="text-slate-700 font-medium">Error al cargar el préstamo</p>
      <p className="text-sm text-slate-500">{message}</p>
    </div>
  )
}

export default function LoanDetail() {
  const { idCxc } = useParams()
  const navigate = useNavigate()
  const [searchId, setSearchId] = useState('')
  const [perfilModalClienteId, setPerfilModalClienteId] = useState(null)
  const { data, isLoading, isError, error, refetch, isFetching } = useEstadoPrestamo(idCxc)

  const enc     = data?.encabezado
  const cuotas  = data?.cuotas  ?? []
  const recibos = data?.recibos ?? []
  const conteos = data?.conteos

  function handleSearch(e) {
    e.preventDefault()
    const trimmed = searchId.trim()
    if (trimmed) {
      navigate(`/prestamos/${trimmed}`)
      setSearchId('')
    }
  }

  const enGracia = enc ? (enc.diasDesdeVencimiento ?? 99) <= 5 : false

  return (
    <div className="p-4 lg:p-6 space-y-5 max-w-screen-2xl mx-auto">

      {/* ── Topbar ── */}
      <div className="flex items-center gap-3 flex-wrap justify-between">
        <div className="flex items-center gap-3 min-w-0">
          <Link
            to="/clientes"
            className="text-slate-500 hover:text-slate-800 p-1.5 rounded-lg hover:bg-slate-100 transition-colors"
            title="Volver a Cartera de Clientes"
          >
            <ArrowLeft size={18} />
          </Link>
          <div className="min-w-0">
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2 flex-wrap">
              Préstamo
              <span className="font-mono text-blue-700">#{idCxc}</span>
              {enc && <StatusBadge estado={enc.estado} />}
            </h1>
            {enc && (
              <p className="text-sm text-slate-500 mt-0.5 flex items-center gap-2">
                <User size={13} />
                {enc.idCliente ? (
                  <button
                    onClick={() => setPerfilModalClienteId(enc.idCliente)}
                    className="font-medium text-slate-700 hover:text-blue-600 hover:underline text-left"
                    title="Ver perfil e historial completo de préstamos"
                  >
                    {enc.nombreCliente} (Ver Expediente)
                  </button>
                ) : (
                  <span>{enc.nombreCliente}</span>
                )}
              </p>
            )}
          </div>
        </div>

        {/* Buscador de otros préstamos */}
        <div className="flex items-center gap-3 flex-wrap">
          <form onSubmit={handleSearch} className="flex items-center gap-2">
            <div className="relative">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Buscar préstamo # (ej. 17481)..."
                value={searchId}
                onChange={(e) => setSearchId(e.target.value)}
                className="pl-9 pr-3 py-1.5 text-sm bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 w-52 sm:w-64"
              />
            </div>
            <button
              type="submit"
              className="px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
            >
              Consultar
            </button>
          </form>

          <button
            onClick={refetch}
            disabled={isFetching}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} />
            Actualizar
          </button>
        </div>
      </div>

      {/* ── Error ── */}
      {isError && !isLoading && (
        <div className="bg-white rounded-xl border border-red-200 shadow-sm">
          <ErrorState message={error?.message} />
        </div>
      )}

      {/* ── Meta del préstamo ── */}
      {(isLoading || enc) && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm px-5 py-4">
          {isLoading ? (
            <div className="flex gap-6">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-4 bg-slate-200 animate-pulse rounded w-28" />
              ))}
            </div>
          ) : (
            <div className="flex flex-wrap gap-x-8 gap-y-2">
              <InfoPill icon={Calendar} label="Fecha"    value={fmtDate(enc.fechaPrestamo)} />
              <InfoPill icon={Percent}  label="Tasa"     value={enc.tasaInteres ? `${enc.tasaInteres}%` : '—'} />
              <InfoPill icon={Tag}      label="Tipo"     value={enc.tipoPrestamo || '—'} />
              <InfoPill icon={User}     label="Creador"  value={enc.creador || '—'} />
            </div>
          )}
        </div>
      )}

      {/* ── BANNER DESTACADO: PROYECCIÓN DE CANCELACIÓN (MONTO PARA SALDAR HOY) ── */}
      {enc && enc.estado !== 'SALDADO' && (
        <div className="bg-gradient-to-r from-amber-500 via-amber-600 to-amber-700 rounded-2xl p-5 text-white shadow-md flex items-center justify-between flex-wrap gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Calculator size={20} className="text-amber-200" />
              <span className="text-xs font-bold uppercase tracking-wider text-amber-100">
                Proyección de Cancelación Inmediata
              </span>
            </div>
            <h2 className="text-3xl font-extrabold tracking-tight font-mono">
              {fmt(enc.montoSaldarHoy)}
            </h2>
            <p className="text-xs text-amber-100 flex items-center gap-1.5 pt-0.5">
              {enGracia ? (
                <>
                  <ShieldCheck size={14} className="text-emerald-300" />
                  <span>
                    Dentro de los 5 días de gracia (Día {enc.diasDesdeVencimiento} de 5). Monto a saldar = 100% Capital Pendiente sin intereses del período.
                  </span>
                </>
              ) : (
                <>
                  <Clock size={14} className="text-amber-200" />
                  <span>
                    Han transcurrido {enc.diasDesdeVencimiento} días desde el corte (supera 5 días de gracia). Aplica tasa del {enc.tasaInteres}% sobre capital pendiente ({fmt(enc.capitalBalance)}).
                  </span>
                </>
              )}
            </p>
          </div>

          <div className="bg-white/10 backdrop-blur-sm rounded-xl px-4 py-2.5 text-right border border-white/20">
            <div className="text-[11px] text-amber-100 uppercase">Capital Pendiente Base</div>
            <div className="text-lg font-bold font-mono">{fmt(enc.capitalBalance)}</div>
            <div className="text-[10px] text-amber-200">
              {enc.ultimoVencimiento ? `Último corte: ${fmtDate(enc.ultimoVencimiento)}` : ''}
            </div>
          </div>
        </div>
      )}

      {/* ── 4 Bloques de Resumen ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-slate-200 h-36 animate-pulse" />
          ))
        ) : enc ? (
          <>
            <SummaryBlock
              title="Inicial"
              capital={enc.capitalInicial}
              interes={enc.interesInicial}
              total={enc.totalInicial}
              variant="blue"
              showMora={false}
            />
            <SummaryBlock
              title="Pagado"
              capital={enc.capitalPagado}
              interes={enc.interesPagado}
              mora={enc.moraPagada}
              total={enc.totalPagado}
              variant="green"
            />
            <SummaryBlock
              title="Balance"
              capital={enc.capitalBalance}
              interes={enc.interesBalance}
              mora={enc.moraBalance}
              total={enc.totalBalance}
              variant="amber"
            />
            <SummaryBlock
              title="Vencido"
              capital={enc.capitalVencido}
              interes={enc.interesVencido}
              mora={enc.moraVencida}
              total={enc.totalVencido}
              variant="red"
            />
          </>
        ) : null}
      </div>

      {/* ── Tablas: Cuotas + Recibos ── */}
      <div className="grid grid-cols-1 xl:grid-cols-5 gap-5">

        {/* Cuotas — más ancho (3/5) */}
        <div className="xl:col-span-3 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <CreditCard size={16} className="text-blue-500" />
                <h2 className="font-semibold text-slate-800 text-sm">Tabla de Cuotas</h2>
              </div>
              {conteos && (
                <span className="text-xs text-slate-400 font-mono">
                  {conteos.totalCuotas} cuotas
                  {enc?.cuotasVencidas > 0 && (
                    <span className="ml-1.5 text-red-500 font-semibold">
                      ({enc.cuotasVencidas} vencidas)
                    </span>
                  )}
                </span>
              )}
            </div>

            {/* Botones de Exportación Cuotas */}
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => exportarCuotasExcel(cuotas, enc)}
                disabled={!cuotas || cuotas.length === 0}
                className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 rounded-lg transition-colors disabled:opacity-40"
                title="Descargar tabla de cuotas en formato Excel (.xlsx)"
              >
                <FileSpreadsheet size={13} />
                <span>Excel</span>
              </button>
              <button
                onClick={() => exportarCuotasPDF(cuotas, enc)}
                disabled={!cuotas || cuotas.length === 0}
                className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-lg transition-colors disabled:opacity-40"
                title="Descargar tabla de cuotas en PDF formal listo para imprimir"
              >
                <FileText size={13} />
                <span>PDF</span>
              </button>
            </div>
          </div>
          <div className="p-3 overflow-auto max-h-[520px] scrollbar-thin">
            <CuotasTable cuotas={cuotas} loading={isLoading} />
          </div>
        </div>

        {/* Recibos — 2/5 */}
        <div className="xl:col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <Receipt size={16} className="text-emerald-500" />
                <h2 className="font-semibold text-slate-800 text-sm">Historial de Pagos</h2>
              </div>
              {conteos && (
                <span className="text-xs text-slate-400 font-mono">{conteos.totalRecibos} recibos</span>
              )}
            </div>

            {/* Botones de Exportación Recibos */}
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => exportarHistorialPagosExcel(recibos, enc)}
                disabled={!recibos || recibos.length === 0}
                className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 rounded-lg transition-colors disabled:opacity-40"
                title="Descargar historial de recibos en formato Excel (.xlsx)"
              >
                <FileSpreadsheet size={13} />
                <span>Excel</span>
              </button>
              <button
                onClick={() => exportarHistorialPagosPDF(recibos, enc)}
                disabled={!recibos || recibos.length === 0}
                className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-lg transition-colors disabled:opacity-40"
                title="Descargar historial de recibos en PDF formal listo para imprimir"
              >
                <FileText size={13} />
                <span>PDF</span>
              </button>
            </div>
          </div>
          <div className="p-3 overflow-auto max-h-[520px] scrollbar-thin">
            <RecibosTable recibos={recibos} loading={isLoading} />
          </div>
        </div>
      </div>

      {/* ── Footer ── */}
      {enc && (
        <p className="text-xs text-slate-400 pb-2">
          Consulta generada el {fmtDate(enc.fechaConsulta)}
        </p>
      )}

      {/* ── Modal de Historial del Cliente ── */}
      {perfilModalClienteId && (
        <ClientePerfilModal
          idCliente={perfilModalClienteId}
          onClose={() => setPerfilModalClienteId(null)}
        />
      )}
    </div>
  )
}
