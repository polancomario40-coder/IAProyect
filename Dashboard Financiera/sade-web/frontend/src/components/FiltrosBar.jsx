/**
 * FiltrosBar.jsx — Barra de filtros con selector rápido de condición,
 * chips/botones de acceso rápido para clasificación (Nuevos, Reenganchados, En Mora, etc.)
 * y filtros dinámicos.
 */
import { useEffect, useRef } from 'react'
import { X, UserPlus, RefreshCw, AlertTriangle, AlertCircle, CheckCircle2, ListFilter } from 'lucide-react'
import { clsx } from 'clsx'

const CONDICIONES = [
  { value: 'ACTIVO',    label: '🟢 Solo Activos (con deuda)' },
  { value: 'CANCELADO', label: '⚪ Cancelados / Saldados' },
  { value: 'TODOS',     label: '📋 Todos los Clientes' },
]

const CHIPS_ESTADO = [
  { value: '',             label: 'Todos',          icon: ListFilter },
  { value: 'NUEVO',        label: 'Nuevos',         icon: UserPlus,       activeClass: 'bg-emerald-600 text-white' },
  { value: 'REENGANCHADO', label: 'Reenganchados',  icon: RefreshCw,      activeClass: 'bg-blue-600 text-white' },
  { value: 'EN MORA',      label: 'En Mora',        icon: AlertTriangle,  activeClass: 'bg-red-600 text-white' },
  { value: 'PROBLEMATICO', label: 'Problemáticos',  icon: AlertCircle,    activeClass: 'bg-amber-600 text-white' },
  { value: 'AL DIA',       label: 'Al Día',         icon: CheckCircle2,   activeClass: 'bg-slate-700 text-white' },
]

const inputClass =
  'border border-slate-200 rounded-lg py-1.5 px-3 text-sm text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent w-full'
const labelClass = 'block text-xs font-semibold text-slate-600 mb-1'

export default function FiltrosBar({
  filtros = {},
  onChange,
  opcionesOficina = [],
}) {
  const busquedaTimer = useRef(null)
  const empresaTimer = useRef(null)
  const creadorTimer = useRef(null)

  useEffect(() => {
    return () => {
      clearTimeout(busquedaTimer.current)
      clearTimeout(empresaTimer.current)
      clearTimeout(creadorTimer.current)
    }
  }, [])

  function handleBusqueda(e) {
    const val = e.target.value
    clearTimeout(busquedaTimer.current)
    busquedaTimer.current = setTimeout(() => onChange('busqueda', val), 400)
  }

  function handleEmpresa(e) {
    const val = e.target.value
    clearTimeout(empresaTimer.current)
    empresaTimer.current = setTimeout(() => onChange('empresa', val), 400)
  }

  function handleCreador(e) {
    const val = e.target.value
    clearTimeout(creadorTimer.current)
    creadorTimer.current = setTimeout(() => onChange('creador', val), 400)
  }

  function handleLimpiar() {
    onChange('busqueda', '')
    onChange('estado', '')
    onChange('desde', '')
    onChange('hasta', '')
    onChange('empresa', '')
    onChange('oficina', '')
    onChange('creador', '')
    onChange('tipoCliente', 'ACTIVO')
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 space-y-3.5">
      
      {/* ── Fila de Chips Rápidos (Nuevos, Reenganchados, En Mora, etc.) ── */}
      <div className="flex items-center justify-between flex-wrap gap-2 pb-2 border-b border-slate-100">
        <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
          Filtro Rápido por Perfil:
        </span>
        <div className="flex flex-wrap items-center gap-1.5">
          {CHIPS_ESTADO.map((chip) => {
            const isSelected = (filtros.estado || '') === chip.value
            const Icon = chip.icon
            return (
              <button
                key={chip.value}
                onClick={() => onChange('estado', chip.value)}
                className={clsx(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all shadow-xs',
                  isSelected
                    ? chip.activeClass || 'bg-slate-900 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200 hover:text-slate-900'
                )}
              >
                <Icon size={13} />
                <span>{chip.label}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* ── Filtros Detallados ── */}
      <div className="flex flex-wrap gap-3 items-end">
        {/* Búsqueda libre */}
        <div className="flex-1 min-w-[180px]">
          <label className={labelClass}>Buscar Cliente</label>
          <input
            type="text"
            placeholder="Nombre, cédula, teléfono…"
            defaultValue={filtros.busqueda || ''}
            onChange={handleBusqueda}
            className={inputClass}
          />
        </div>

        {/* Condición de Cartera */}
        <div className="min-w-[185px]">
          <label className={labelClass}>Condición de Cartera</label>
          <select
            value={filtros.tipoCliente || 'ACTIVO'}
            onChange={(e) => onChange('tipoCliente', e.target.value)}
            className="border border-blue-300 bg-blue-50/50 text-blue-900 font-semibold rounded-lg py-1.5 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 w-full"
          >
            {CONDICIONES.map((op) => (
              <option key={op.value} value={op.value}>
                {op.label}
              </option>
            ))}
          </select>
        </div>

        {/* Empresa */}
        <div className="min-w-[150px]">
          <label className={labelClass}>Empresa</label>
          <input
            type="text"
            placeholder="Filtrar por empresa…"
            defaultValue={filtros.empresa || ''}
            onChange={handleEmpresa}
            className={inputClass}
          />
        </div>

        {/* Creador / Operador */}
        <div className="min-w-[140px]">
          <label className={labelClass}>Creador / Operador</label>
          <input
            type="text"
            placeholder="Creado por…"
            defaultValue={filtros.creador || ''}
            onChange={handleCreador}
            className={inputClass}
          />
        </div>

        {/* Desde */}
        <div className="min-w-[130px]">
          <label className={labelClass}>Desde</label>
          <input
            type="date"
            value={filtros.desde || ''}
            onChange={(e) => onChange('desde', e.target.value)}
            className={inputClass}
          />
        </div>

        {/* Hasta */}
        <div className="min-w-[130px]">
          <label className={labelClass}>Hasta</label>
          <input
            type="date"
            value={filtros.hasta || ''}
            onChange={(e) => onChange('hasta', e.target.value)}
            className={inputClass}
          />
        </div>

        {/* Oficina */}
        {opcionesOficina.length > 0 && (
          <div className="min-w-[140px]">
            <label className={labelClass}>Oficina</label>
            <select
              value={filtros.oficina || ''}
              onChange={(e) => onChange('oficina', e.target.value)}
              className={inputClass}
            >
              <option value="">Todas</option>
              {opcionesOficina.map((op) => {
                const val = typeof op === 'string' ? op : op.value ?? op.label
                const lbl = typeof op === 'string' ? op : op.label ?? op.value
                return (
                  <option key={val} value={val}>
                    {lbl}
                  </option>
                )
              })}
            </select>
          </div>
        )}

        {/* Botón Limpiar */}
        <div className="flex-shrink-0">
          <label className={labelClass}>&nbsp;</label>
          <button
            onClick={handleLimpiar}
            className="flex items-center gap-1.5 py-1.5 px-3.5 text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 border border-slate-200 rounded-lg transition-colors shadow-xs"
          >
            <X size={14} />
            Limpiar
          </button>
        </div>
      </div>
    </div>
  )
}
