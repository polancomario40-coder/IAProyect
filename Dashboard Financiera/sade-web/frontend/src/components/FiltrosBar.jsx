/**
 * FiltrosBar.jsx — Barra de filtros horizontal para la página de Clientes
 *
 * Props:
 *   filtros         object   Estado actual de los filtros
 *   onChange        fn       (campo, valor) => void
 *   opcionesOficina array    [{ value, label }] para el select de Oficina
 */
import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

const ESTADOS = [
  { value: '', label: 'Todos' },
  { value: 'NUEVO', label: 'Nuevo' },
  { value: 'REENGANCHADO', label: 'Reenganchado' },
  { value: 'EN MORA', label: 'En Mora' },
  { value: 'PROBLEMATICO', label: 'Problemático' },
  { value: 'AL DIA', label: 'Al Día' },
]

const inputClass =
  'border border-slate-200 rounded-lg py-1.5 px-3 text-sm text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent w-full'
const labelClass = 'block text-xs font-medium text-slate-500 mb-1'

export default function FiltrosBar({ filtros = {}, onChange, opcionesOficina = [] }) {
  // Debounce refs for text inputs
  const busquedaTimer = useRef(null)
  const empresaTimer = useRef(null)

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      clearTimeout(busquedaTimer.current)
      clearTimeout(empresaTimer.current)
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

  function handleLimpiar() {
    // Reset all filters except pagina/porPagina
    ;['busqueda', 'estado', 'desde', 'hasta', 'empresa', 'oficina'].forEach(campo =>
      onChange(campo, '')
    )
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
      <div className="flex flex-wrap gap-3 items-end">

        {/* Búsqueda libre */}
        <div className="flex-1 min-w-[160px]">
          <label className={labelClass}>Buscar</label>
          <input
            type="text"
            placeholder="Nombre, cédula, teléfono…"
            defaultValue={filtros.busqueda || ''}
            onChange={handleBusqueda}
            className={inputClass}
          />
        </div>

        {/* Estado */}
        <div className="min-w-[150px]">
          <label className={labelClass}>Estado</label>
          <select
            value={filtros.estado || ''}
            onChange={e => onChange('estado', e.target.value)}
            className={inputClass}
          >
            {ESTADOS.map(op => (
              <option key={op.value} value={op.value}>{op.label}</option>
            ))}
          </select>
        </div>

        {/* Desde */}
        <div className="min-w-[130px]">
          <label className={labelClass}>Desde</label>
          <input
            type="date"
            value={filtros.desde || ''}
            onChange={e => onChange('desde', e.target.value)}
            className={inputClass}
          />
        </div>

        {/* Hasta */}
        <div className="min-w-[130px]">
          <label className={labelClass}>Hasta</label>
          <input
            type="date"
            value={filtros.hasta || ''}
            onChange={e => onChange('hasta', e.target.value)}
            className={inputClass}
          />
        </div>

        {/* Empresa */}
        <div className="min-w-[150px]">
          <label className={labelClass}>Empresa</label>
          <input
            type="text"
            placeholder="Empresa…"
            defaultValue={filtros.empresa || ''}
            onChange={handleEmpresa}
            className={inputClass}
          />
        </div>

        {/* Oficina */}
        {opcionesOficina.length > 0 && (
          <div className="min-w-[150px]">
            <label className={labelClass}>Oficina</label>
            <select
              value={filtros.oficina || ''}
              onChange={e => onChange('oficina', e.target.value)}
              className={inputClass}
            >
              <option value="">Todas</option>
              {opcionesOficina.map(op => {
                const val = typeof op === 'string' ? op : (op.value ?? op.label)
                const lbl = typeof op === 'string' ? op : (op.label ?? op.value)
                return <option key={val} value={val}>{lbl}</option>
              })}
            </select>
          </div>
        )}

        {/* Botón Limpiar */}
        <div className="flex-shrink-0">
          <label className={labelClass}>&nbsp;</label>
          <button
            onClick={handleLimpiar}
            className="flex items-center gap-1.5 py-1.5 px-3 text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 border border-slate-200 rounded-lg transition-colors"
          >
            <X size={14} />
            Limpiar
          </button>
        </div>

      </div>
    </div>
  )
}
