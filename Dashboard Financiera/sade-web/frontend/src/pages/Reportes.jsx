/**
 * Reportes.jsx — Informes Analíticos Oficiales SADE
 * Implementa las plantillas exactas requeridas por el cliente:
 *  1. Informe General Consolidado por Cartera (Imagen 2)
 *  2. Detalle Individual de Clientes por Quincena (Imagen 1)
 *  3. Clientes Nuevos del Período
 *  4. Clientes Reenganchados del Período
 * Incluye fila de Totales Generales en pesos ($) y descargas a Excel y PDF.
 */
import { useState, useMemo } from 'react'
import {
  FileSpreadsheet,
  FileText,
  Calendar,
  Building2,
  Users,
  UserPlus,
  RefreshCw,
  Ban,
  FolderDown,
  Layers,
  ChevronRight,
  Filter,
  AlertTriangle,
  Clock,
  ExternalLink,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Link } from 'react-router-dom'
import {
  useReporteDetalleClientes,
  useReporteConsolidadoCartera,
  useReporteClientesAtrasados,
} from '../hooks/useApi'
import {
  exportarReporteDetalleExcel,
  exportarReporteDetallePDF,
  exportarReporteCarteraExcel,
  exportarReporteCarteraPDF,
  exportarReporteCompletoLibroExcel,
  exportarReporteClientesAtrasadosExcel,
  exportarReporteClientesAtrasadosPDF,
} from '../utils/exportUtils'

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

const BADGES = {
  'NUEVO': 'bg-amber-300 text-amber-950 font-bold border border-amber-400',
  'REENGANCHADO': 'bg-blue-100 text-blue-800 font-bold border border-blue-200',
  'SITUACION ATRASO (15 DIAS)': 'bg-amber-100 text-amber-900 font-bold border border-amber-300',
  'SITUACION ATRASO (30 DIAS)': 'bg-orange-100 text-orange-900 font-bold border border-orange-300',
  'SITUACION ATRASO (45 DIAS)': 'bg-rose-100 text-rose-900 font-bold border border-rose-300',
  'SITUACION ATRASO (60+ DIAS)': 'bg-red-100 text-red-950 font-bold border border-red-300',
  'SITUACION ATRASO': 'bg-amber-300 text-amber-950 font-bold border border-amber-400',
  'EN MORA': 'bg-red-100 text-red-700 font-bold border border-red-200',
  'AL DIA': 'bg-emerald-50 text-emerald-800 font-bold border border-emerald-200',
  'CANCELADO': 'bg-zinc-100 text-zinc-600 border border-zinc-200',
}

const PESTANAS = [
  { id: 'CONSOLIDADO', label: '1. Consolidado por Cartera', icon: Layers, desc: 'Resumen gerencial de capital y cobros' },
  { id: 'DETALLE',     label: '2. Detalle de Clientes',      icon: Users,  desc: 'Plantilla quincenal con balances' },
  { id: 'NUEVOS',      label: '3. Clientes Nuevos',          icon: UserPlus, desc: 'Préstamos nuevos del período' },
  { id: 'REENGANCHES', label: '4. Reenganchados',            icon: RefreshCw, desc: 'Préstamos reenganchados del período' },
  { id: 'CANCELADOS',  label: '5. Cancelados',               icon: Ban, desc: 'Préstamos cancelados / saldados del período' },
  { id: 'ATRASADOS',   label: '6. Clientes Atrasados (Mora)', icon: AlertTriangle, desc: 'Mora por compañía y tramos (30d, Legal 60d, 90+d)' },
]

export default function Reportes() {
  const [pestañaActiva, setPestañaActiva] = useState('CONSOLIDADO')
  const [exportando, setExportando] = useState(false)

  // Configuración de período / quincena
  const hoy = new Date()
  const añoActual = hoy.getFullYear()
  const mesActual = hoy.getMonth() + 1
  const diaActual = hoy.getDate()

  const [periodoTipo, setPeriodoTipo] = useState(diaActual <= 15 ? 'Q1' : 'Q2') // 'Q1' | 'Q2' | 'MES' | 'CUSTOM'
  const [mesSeleccionado, setMesSeleccionado] = useState(mesActual)
  const [añoSeleccionado, setAñoSeleccionado] = useState(añoActual)
  const [filtroEmpresa, setFiltroEmpresa] = useState('')
  const [fechaDesdeCustom, setFechaDesdeCustom] = useState('')
  const [fechaHastaCustom, setFechaHastaCustom] = useState('')
  const [filtroClasificacion, setFiltroClasificacion] = useState('TODOS')
  const [subtabAtrasados, setSubtabAtrasados] = useState('RESUMEN') // 'RESUMEN' | 'DETALLE'

  // Fechas computadas
  const { fechaDesde, fechaHasta } = useMemo(() => {
    if (periodoTipo === 'CUSTOM') {
      return {
        fechaDesde: fechaDesdeCustom || undefined,
        fechaHasta: fechaHastaCustom || undefined,
      }
    }

    const y = añoSeleccionado
    const m = mesSeleccionado
    const pad = (n) => String(n).padStart(2, '0')
    const ultDiaMes = new Date(y, m, 0).getDate()

    if (periodoTipo === 'Q1') {
      return {
        fechaDesde: `${y}-${pad(m)}-01`,
        fechaHasta: `${y}-${pad(m)}-15`,
      }
    } else if (periodoTipo === 'Q2') {
      return {
        fechaDesde: `${y}-${pad(m)}-16`,
        fechaHasta: `${y}-${pad(m)}-${pad(ultDiaMes)}`,
      }
    } else {
      // MES COMPLETO
      return {
        fechaDesde: `${y}-${pad(m)}-01`,
        fechaHasta: `${y}-${pad(m)}-${pad(ultDiaMes)}`,
      }
    }
  }, [periodoTipo, mesSeleccionado, añoSeleccionado, fechaDesdeCustom, fechaHastaCustom])

  // Parámetros de consulta
  const filtrosDetalle = useMemo(() => ({
    fechaDesde,
    fechaHasta,
    empresa: filtroEmpresa || undefined,
    tipoReporte: pestañaActiva === 'NUEVOS' 
      ? 'NUEVOS' 
      : pestañaActiva === 'REENGANCHES' 
      ? 'REENGANCHADOS' 
      : pestañaActiva === 'CANCELADOS'
      ? 'CANCELADOS'
      : 'TODOS',
  }), [fechaDesde, fechaHasta, filtroEmpresa, pestañaActiva])

  const filtrosCartera = useMemo(() => ({
    fechaDesde,
    fechaHasta,
    fechaCorte: fechaHasta,
    empresa: filtroEmpresa || undefined,
  }), [fechaDesde, fechaHasta, filtroEmpresa])

  // Queries TanStack (Carga bajo demanda según pestaña activa para máxima velocidad)
  const esConsolidado = pestañaActiva === 'CONSOLIDADO'
  const esAtrasados = pestañaActiva === 'ATRASADOS'

  const { data: dataCartera, isLoading: loadingCartera } = useReporteConsolidadoCartera(filtrosCartera, {
    enabled: esConsolidado,
  })
  const { data: dataDetalle, isLoading: loadingDetalle } = useReporteDetalleClientes(filtrosDetalle, {
    enabled: !esConsolidado && !esAtrasados,
  })
  const { data: dataAtrasados, isLoading: loadingAtrasados } = useReporteClientesAtrasados({
    fechaCorte: fechaHasta,
    empresa: filtroEmpresa || undefined,
  }, {
    enabled: esAtrasados,
  })

  const filasCartera = dataCartera?.filas ?? []
  const totalesCartera = dataCartera?.totales ?? {}

  const filasDetalle = dataDetalle?.filas ?? []
  const totalesDetalle = dataDetalle?.totales ?? {}

  const carterasMora = dataAtrasados?.carteras ?? []
  const clientesMora = dataAtrasados?.clientes ?? []
  const totalesMora = dataAtrasados?.totales ?? {}

  // Filtrado interactivo de Clasificación para la Pestaña Detalle
  const filasDetalleFiltradas = useMemo(() => {
    if (!filasDetalle || filasDetalle.length === 0) return []
    if (pestañaActiva !== 'DETALLE' || filtroClasificacion === 'TODOS') return filasDetalle

    if (filtroClasificacion === 'AL_DIA') {
      return filasDetalle.filter(r => r.clasificacion === 'AL DIA')
    }
    if (filtroClasificacion === 'ATRASO_15') {
      return filasDetalle.filter(r => r.clasificacion?.includes('15') || (r.diasAtraso > 0 && r.diasAtraso <= 15))
    }
    if (filtroClasificacion === 'ATRASO_30') {
      return filasDetalle.filter(r => r.clasificacion?.includes('30') || (r.diasAtraso > 15 && r.diasAtraso <= 30))
    }
    if (filtroClasificacion === 'ATRASO_45') {
      return filasDetalle.filter(r => r.clasificacion?.includes('45') || (r.diasAtraso > 30 && r.diasAtraso <= 45))
    }
    if (filtroClasificacion === 'ATRASO_60') {
      return filasDetalle.filter(r => r.clasificacion?.includes('60') || r.diasAtraso > 45)
    }
    if (filtroClasificacion === 'ATRASO_TODOS') {
      return filasDetalle.filter(r => r.clasificacion?.startsWith('SITUACION ATRASO') || r.clasificacion === 'EN MORA')
    }
    return filasDetalle.filter(r => r.clasificacion === filtroClasificacion)
  }, [filasDetalle, filtroClasificacion, pestañaActiva])

  const totalesDetalleCalculados = useMemo(() => {
    if (pestañaActiva !== 'DETALLE' || filtroClasificacion === 'TODOS') return totalesDetalle
    return {
      ...totalesDetalle,
      totalRegistros: filasDetalleFiltradas.length,
      totalMontoPrestamo: filasDetalleFiltradas.reduce((s, r) => s + (Number(r.montoPrestamo) || 0), 0),
      totalCapitalPagado: filasDetalleFiltradas.reduce((s, r) => s + (Number(r.capitalPagado) || 0), 0),
      totalBalanceAntesCobro: filasDetalleFiltradas.reduce((s, r) => s + (Number(r.balanceAntesCobro) || 0), 0),
      totalCapitalCobradoQuincena: filasDetalleFiltradas.reduce((s, r) => s + (Number(r.capitalCobradoQuincena) || 0), 0),
      totalInteresCobradoQuincena: filasDetalleFiltradas.reduce((s, r) => s + (Number(r.interesCobradoQuincena) || 0), 0),
      totalCapitalActualAdeudado: filasDetalleFiltradas.reduce((s, r) => s + (Number(r.capitalActualAdeudado) || 0), 0),
      totalCobradoQuincena: filasDetalleFiltradas.reduce((s, r) => s + (Number(r.totalCobradoQuincena) || 0), 0),
      totalBalanceActual: filasDetalleFiltradas.reduce((s, r) => s + (Number(r.balanceActual) || 0), 0),
    }
  }, [filasDetalleFiltradas, totalesDetalle, filtroClasificacion, pestañaActiva])

  // Sufijos dinámicos según filtro de cartera / empresa (ej. Clientes del Bravo)
  const empresaLimpia = (filtroEmpresa || '').trim()
  const sufijoTituloEmpresa = empresaLimpia
    ? ` — Correspondiente a los Clientes de: ${empresaLimpia.toUpperCase()}`
    : ''
  const sufijoArchivoEmpresa = empresaLimpia
    ? `_${empresaLimpia.replace(/[^a-zA-Z0-9_-]/g, '_')}`
    : ''

  // Descargas individuales
  async function handleDescargarExcel() {
    try {
      setExportando(true)
      if (pestañaActiva === 'CONSOLIDADO') {
        exportarReporteCarteraExcel(
          filasCartera,
          totalesCartera,
          `Consolidado_Cartera${sufijoArchivoEmpresa}_${fechaHasta}`,
          `Informe General Consolidado por Cartera${sufijoTituloEmpresa}`
        )
      } else if (pestañaActiva === 'ATRASADOS') {
        exportarReporteClientesAtrasadosExcel({
          carteras: carterasMora,
          clientes: clientesMora,
          totales: totalesMora,
          nombreArchivo: `Cartera_En_Mora${sufijoArchivoEmpresa}_${fechaHasta}`,
          titulo: `Informe Oficial de Cartera en Mora por Tramos y Compañía${sufijoTituloEmpresa}`,
          fechaCorte: fechaHasta,
        })
      } else {
        const titulos = {
          DETALLE: `Informe Detalle de Préstamos${sufijoTituloEmpresa}`,
          NUEVOS: `Informe de Préstamos Nuevos${sufijoTituloEmpresa}`,
          REENGANCHES: `Informe de Préstamos Reenganchados${sufijoTituloEmpresa}`,
          CANCELADOS: `Informe de Préstamos Cancelados / Saldados${sufijoTituloEmpresa}`,
        }
        const sufijoFiltro = (pestañaActiva === 'DETALLE' && filtroClasificacion !== 'TODOS')
          ? `_${filtroClasificacion}`
          : ''
        exportarReporteDetalleExcel(
          filasDetalleFiltradas,
          totalesDetalleCalculados,
          `${pestañaActiva}${sufijoFiltro}${sufijoArchivoEmpresa}_${fechaHasta}`,
          titulos[pestañaActiva] || `Informe Detalle${sufijoTituloEmpresa}`
        )
      }
    } catch (err) {
      alert(`Error al generar Excel: ${err.message}`)
    } finally {
      setExportando(false)
    }
  }

  async function handleDescargarPDF() {
    try {
      setExportando(true)
      if (pestañaActiva === 'CONSOLIDADO') {
        exportarReporteCarteraPDF(
          filasCartera,
          totalesCartera,
          `Informe General Consolidado por Cartera${sufijoTituloEmpresa}`,
          `Consolidado_Cartera${sufijoArchivoEmpresa}_${fechaHasta}`
        )
      } else if (pestañaActiva === 'ATRASADOS') {
        exportarReporteClientesAtrasadosPDF({
          carteras: carterasMora,
          clientes: clientesMora,
          totales: totalesMora,
          titulo: `Informe Oficial de Cartera en Mora por Tramos y Compañía${sufijoTituloEmpresa}`,
          nombreArchivo: `Cartera_En_Mora${sufijoArchivoEmpresa}_${fechaHasta}`,
          fechaCorte: fechaHasta,
        })
      } else {
        const titulos = {
          DETALLE: `Informe Detalle Individual de Préstamos${sufijoTituloEmpresa}`,
          NUEVOS: `Informe de Préstamos Nuevos del Período${sufijoTituloEmpresa}`,
          REENGANCHES: `Informe de Préstamos Reenganchados del Período${sufijoTituloEmpresa}`,
          CANCELADOS: `Informe de Préstamos Cancelados / Saldados del Período${sufijoTituloEmpresa}`,
        }
        const sufijoFiltro = (pestañaActiva === 'DETALLE' && filtroClasificacion !== 'TODOS')
          ? `_${filtroClasificacion}`
          : ''
        exportarReporteDetallePDF(
          filasDetalleFiltradas,
          totalesDetalleCalculados,
          titulos[pestañaActiva] || `Informe Detalle${sufijoTituloEmpresa}`,
          `${pestañaActiva}${sufijoFiltro}${sufijoArchivoEmpresa}_${fechaHasta}`
        )
      }
    } catch (err) {
      alert(`Error al generar PDF: ${err.message}`)
    } finally {
      setExportando(false)
    }
  }

  // Descargar Libro Completo con todas las pestañas (Como en Excel del cliente)
  async function handleDescargarLibroCompleto() {
    try {
      setExportando(true)
      const qEmpresa = empresaLimpia ? `&empresa=${encodeURIComponent(empresaLimpia)}` : ''
      // Buscar todos los datos necesarios respetando el filtro de empresa si existe
      const [resTodos, resNuevos, resReeng, resCanc, resMora] = await Promise.all([
        fetch(`/api/reportes/detalle-clientes?fechaDesde=${fechaDesde || ''}&fechaHasta=${fechaHasta || ''}${qEmpresa}&tipoReporte=TODOS`).then(r => r.json()),
        fetch(`/api/reportes/detalle-clientes?fechaDesde=${fechaDesde || ''}&fechaHasta=${fechaHasta || ''}${qEmpresa}&tipoReporte=NUEVOS`).then(r => r.json()),
        fetch(`/api/reportes/detalle-clientes?fechaDesde=${fechaDesde || ''}&fechaHasta=${fechaHasta || ''}${qEmpresa}&tipoReporte=REENGANCHADOS`).then(r => r.json()),
        fetch(`/api/reportes/detalle-clientes?fechaDesde=${fechaDesde || ''}&fechaHasta=${fechaHasta || ''}${qEmpresa}&tipoReporte=CANCELADOS`).then(r => r.json()),
        fetch(`/api/reportes/clientes-atrasados?fechaCorte=${fechaHasta || ''}${qEmpresa}`).then(r => r.json()),
      ])

      exportarReporteCompletoLibroExcel({
        carteras: filasCartera,
        totalesCartera,
        detalleTodos: resTodos?.filas || [],
        totalesDetalleTodos: resTodos?.totales || {},
        nuevos: resNuevos?.filas || [],
        totalesNuevos: resNuevos?.totales || {},
        reenganches: resReeng?.filas || [],
        totalesReenganches: resReeng?.totales || {},
        cancelados: resCanc?.filas || [],
        totalesCancelados: resCanc?.totales || {},
        carteraMora: resMora?.carteras || [],
        totalesMora: resMora?.totales || {},
        nombreArchivo: `Libro_Informes_Financieros${sufijoArchivoEmpresa}_${fechaHasta}`,
        empresa: empresaLimpia,
        fechaDesde,
        fechaHasta,
      })
    } catch (err) {
      alert(`Error al generar libro completo: ${err.message}`)
    } finally {
      setExportando(false)
    }
  }

  const isLoading = pestañaActiva === 'CONSOLIDADO' 
    ? loadingCartera 
    : pestañaActiva === 'ATRASADOS'
    ? loadingAtrasados
    : loadingDetalle

  return (
    <div className="p-4 lg:p-6 space-y-6 max-w-screen-2xl mx-auto">
      
      {/* ── Encabezado y Botones de Acción ── */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Informes Financieros</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Generación y descarga de informes quincenales, consolidados y detalle con totales en pesos ($).
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={handleDescargarExcel}
            disabled={exportando || isLoading}
            className="flex items-center gap-2 px-3.5 py-2 text-sm font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl transition-all shadow-sm hover:shadow disabled:opacity-50"
            title="Descargar informe actual en Excel (.xlsx) con totales"
          >
            <FileSpreadsheet size={16} />
            <span>Excel</span>
          </button>

          <button
            onClick={handleDescargarPDF}
            disabled={exportando || isLoading}
            className="flex items-center gap-2 px-3.5 py-2 text-sm font-semibold bg-rose-600 hover:bg-rose-700 text-white rounded-xl transition-all shadow-sm hover:shadow disabled:opacity-50"
            title="Descargar informe actual en PDF formal listo para imprimir"
          >
            <FileText size={16} />
            <span>PDF</span>
          </button>

          <button
            onClick={handleDescargarLibroCompleto}
            disabled={exportando || isLoading}
            className="flex items-center gap-2 px-3.5 py-2 text-sm font-semibold bg-blue-700 hover:bg-blue-800 text-white rounded-xl transition-all shadow-sm hover:shadow disabled:opacity-50"
            title="Descargar libro Excel completo con todas las pestañas (General, Nuevos, Reenganches, Detalle)"
          >
            <FolderDown size={16} />
            <span>Libro Completo (Multi-Hoja)</span>
          </button>
        </div>
      </div>

      {/* ── Barra de Selección de Período y Filtros ── */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3 pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <Calendar size={18} className="text-blue-600" />
            <span className="text-sm font-bold text-slate-800">Período de Evaluación / Quincena:</span>
          </div>

          <div className="flex items-center gap-1.5 bg-slate-100 p-1 rounded-xl">
            <button
              onClick={() => setPeriodoTipo('Q1')}
              className={clsx(
                'px-3 py-1 text-xs font-semibold rounded-lg transition-all',
                periodoTipo === 'Q1' ? 'bg-white text-blue-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
              )}
            >
              1ra Quincena (1 - 15)
            </button>
            <button
              onClick={() => setPeriodoTipo('Q2')}
              className={clsx(
                'px-3 py-1 text-xs font-semibold rounded-lg transition-all',
                periodoTipo === 'Q2' ? 'bg-white text-blue-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
              )}
            >
              2da Quincena (16 - Fin)
            </button>
            <button
              onClick={() => setPeriodoTipo('MES')}
              className={clsx(
                'px-3 py-1 text-xs font-semibold rounded-lg transition-all',
                periodoTipo === 'MES' ? 'bg-white text-blue-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
              )}
            >
              Mes Completo
            </button>
            <button
              onClick={() => setPeriodoTipo('CUSTOM')}
              className={clsx(
                'px-3 py-1 text-xs font-semibold rounded-lg transition-all',
                periodoTipo === 'CUSTOM' ? 'bg-white text-blue-700 shadow-xs' : 'text-slate-600 hover:text-slate-900'
              )}
            >
              Personalizado
            </button>
          </div>
        </div>

        {/* Parámetros de Fechas y Empresa */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 items-end">
          {periodoTipo !== 'CUSTOM' ? (
            <>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Mes</label>
                <select
                  value={mesSeleccionado}
                  onChange={(e) => setMesSeleccionado(Number(e.target.value))}
                  className="w-full border border-slate-200 rounded-lg py-1.5 px-3 text-sm text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
                >
                  <option value={1}>Enero</option>
                  <option value={2}>Febrero</option>
                  <option value={3}>Marzo</option>
                  <option value={4}>Abril</option>
                  <option value={5}>Mayo</option>
                  <option value={6}>Junio</option>
                  <option value={7}>Julio</option>
                  <option value={8}>Agosto</option>
                  <option value={9}>Septiembre</option>
                  <option value={10}>Octubre</option>
                  <option value={11}>Noviembre</option>
                  <option value={12}>Diciembre</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Año</label>
                <select
                  value={añoSeleccionado}
                  onChange={(e) => setAñoSeleccionado(Number(e.target.value))}
                  className="w-full border border-slate-200 rounded-lg py-1.5 px-3 text-sm text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
                >
                  <option value={2024}>2024</option>
                  <option value={2025}>2025</option>
                  <option value={2026}>2026</option>
                  <option value={2027}>2027</option>
                </select>
              </div>
            </>
          ) : (
            <>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Fecha Desde</label>
                <input
                  type="date"
                  value={fechaDesdeCustom}
                  onChange={(e) => setFechaDesdeCustom(e.target.value)}
                  className="w-full border border-slate-200 rounded-lg py-1.5 px-3 text-sm text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1">Fecha Hasta</label>
                <input
                  type="date"
                  value={fechaHastaCustom}
                  onChange={(e) => setFechaHastaCustom(e.target.value)}
                  className="w-full border border-slate-200 rounded-lg py-1.5 px-3 text-sm text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
                />
              </div>
            </>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-600 mb-1">Filtrar por Cartera / Empresa</label>
            <div className="relative">
              <input
                type="text"
                placeholder="Ej. Bravo, Olé, Sirena..."
                value={filtroEmpresa}
                onChange={(e) => setFiltroEmpresa(e.target.value)}
                className="w-full border border-slate-200 rounded-lg py-1.5 px-3 text-sm text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
              <Building2 size={15} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            </div>
          </div>

          <div className="bg-slate-50 border border-slate-200/80 rounded-lg px-3 py-1.5 text-xs text-slate-600">
            <span className="font-semibold text-slate-800 block">Rango Activo:</span>
            <span>{fechaDesde || '—'} al {fechaHasta || '—'}</span>
          </div>
        </div>
      </div>

      {/* ── Pestañas de Navegación de Informes ── */}
      <div className="flex border-b border-slate-200 gap-2 overflow-x-auto">
        {PESTANAS.map((tab) => {
          const Icon = tab.icon
          const isActive = pestañaActiva === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setPestañaActiva(tab.id)}
              className={clsx(
                'flex items-center gap-2.5 px-4 py-3 text-sm font-semibold border-b-2 transition-all whitespace-nowrap',
                isActive
                  ? 'border-blue-600 text-blue-600 bg-blue-50/50 rounded-t-lg'
                  : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
              )}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
            </button>
          )
        })}
      </div>

      {/* ── CONTENIDO: INFORME GENERAL CONSOLIDADO POR CARTERA (Plantilla Imagen 2) ── */}
      {pestañaActiva === 'CONSOLIDADO' && (
        <section className="space-y-4">
          <div className="bg-amber-100/90 border border-amber-300/80 rounded-xl p-3.5 flex items-center justify-between text-xs text-amber-950 font-medium">
            <div>
              <span className="font-bold uppercase tracking-wide">Plantilla Oficial:</span> Informe General Consolidado por Cartera{sufijoTituloEmpresa} (Período: {fechaDesde || '—'} al {fechaHasta || '—'}).
            </div>
            <div className="font-bold text-amber-900">
              Total Carteras: {filasCartera.length}
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-amber-300 border-b border-amber-400 text-slate-900 select-none">
                    <th className="px-3.5 py-3 text-left font-bold uppercase tracking-wider">Cartera (Empresa)</th>
                    <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Balance Capital Colocado</th>
                    <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Cap. Inactivos/Cancelados</th>
                    <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Capital Activo</th>
                    <th className="px-2.5 py-3 text-center font-bold uppercase tracking-wider">Cli. Act.</th>
                    <th className="px-2.5 py-3 text-center font-bold uppercase tracking-wider">Cli. Inact.</th>
                    <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Cap. Cobrado Quincena</th>
                    <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Int. Cobrado Quincena</th>
                    <th className="px-2.5 py-3 text-center font-bold uppercase tracking-wider">Tasa</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100">
                  {loadingCartera ? (
                    <tr>
                      <td colSpan={9} className="px-4 py-12 text-center text-slate-400">
                        Cargando consolidado de carteras...
                      </td>
                    </tr>
                  ) : filasCartera.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="px-4 py-12 text-center text-slate-400">
                        No se encontraron registros de carteras para los filtros seleccionados.
                      </td>
                    </tr>
                  ) : (
                    filasCartera.map((r, i) => (
                      <tr key={i} className="hover:bg-amber-50/30 transition-colors font-medium text-slate-800">
                        <td className="px-3.5 py-2.5 font-bold text-slate-900">{r.cartera}</td>
                        <td className="px-3 py-2.5 text-right font-mono">{fmt(r.balanceCapitalColocado)}</td>
                        <td className="px-3 py-2.5 text-right font-mono text-slate-500">{fmt(r.capitalClientesInactivosCancelados)}</td>
                        <td className="px-3 py-2.5 text-right font-mono font-semibold text-blue-700">{fmt(r.capitalActivo)}</td>
                        <td className="px-2.5 py-2.5 text-center font-bold text-emerald-700">{r.clientesActivos}</td>
                        <td className="px-2.5 py-2.5 text-center text-slate-400">{r.clientesInactivos}</td>
                        <td className="px-3 py-2.5 text-right font-mono font-semibold text-emerald-700">{fmt(r.capitalCobradoQuincena)}</td>
                        <td className="px-3 py-2.5 text-right font-mono font-semibold text-indigo-700">{fmt(r.interesCobradoQuincena)}</td>
                        <td className="px-2.5 py-2.5 text-center font-mono">{r.tasa}%</td>
                      </tr>
                    ))
                  )}
                </tbody>

                {/* ── FILA FINAL DE TOTALES EN PESOS ($) ── */}
                {!loadingCartera && filasCartera.length > 0 && (
                  <tfoot>
                    <tr className="bg-slate-900 text-white font-bold border-t-2 border-slate-950 text-xs">
                      <td className="px-3.5 py-3 uppercase tracking-wider">TOTAL GENERAL</td>
                      <td className="px-3 py-3 text-right font-mono">{fmt(totalesCartera.totalBalanceCapitalColocado)}</td>
                      <td className="px-3 py-3 text-right font-mono text-slate-300">{fmt(totalesCartera.totalCapitalInactivosCancelados)}</td>
                      <td className="px-3 py-3 text-right font-mono text-blue-300">{fmt(totalesCartera.totalCapitalActivo)}</td>
                      <td className="px-2.5 py-3 text-center text-emerald-300">{totalesCartera.totalClientesActivos}</td>
                      <td className="px-2.5 py-3 text-center text-slate-400">{totalesCartera.totalClientesInactivos}</td>
                      <td className="px-3 py-3 text-right font-mono text-emerald-300">{fmt(totalesCartera.totalCapitalCobradoQuincena)}</td>
                      <td className="px-3 py-3 text-right font-mono text-indigo-300">{fmt(totalesCartera.totalInteresCobradoQuincena)}</td>
                      <td className="px-2.5 py-3 text-center font-mono">{totalesCartera.tasaPromedioPonderada}%</td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </div>
        </section>
      )}

      {/* ── CONTENIDO: DETALLE DE CLIENTES / NUEVOS / REENGANCHADOS / CANCELADOS (Plantilla Imagen 1) ── */}
      {pestañaActiva !== 'CONSOLIDADO' && pestañaActiva !== 'ATRASADOS' && (
        <section className="space-y-4">
          <div className="bg-amber-100/90 border border-amber-300/80 rounded-xl p-3.5 flex items-center justify-between text-xs text-amber-950 font-medium">
            <div>
              <span className="font-bold uppercase tracking-wide">
                {pestañaActiva === 'NUEVOS' 
                  ? 'INFORME EXCLUSIVO: CLIENTES / PRÉSTAMOS NUEVOS DEL PERÍODO' 
                  : pestañaActiva === 'REENGANCHES' 
                  ? 'INFORME EXCLUSIVO: PRÉSTAMOS REENGANCHADOS DEL PERÍODO' 
                  : pestañaActiva === 'CANCELADOS'
                  ? 'INFORME EXCLUSIVO: PRÉSTAMOS CANCELADOS / SALDADOS DEL PERÍODO'
                  : 'INFORME DETALLE DE PRÉSTAMOS CON BALANCE Y COBROS'}
                {sufijoTituloEmpresa}
              </span>
              <span className="ml-2 text-amber-800">
                (Período: {fechaDesde} al {fechaHasta})
              </span>
            </div>
            <div className="font-bold text-amber-900">
              Total Registros: {filasDetalleFiltradas.length}
              {filtroClasificacion !== 'TODOS' && pestañaActiva === 'DETALLE' && (
                <span className="ml-1 text-[11px] text-amber-700 font-normal">
                  (de {filasDetalle.length})
                </span>
              )}
            </div>
          </div>

          {/* ── BARRA INTERACTIVA DE FILTRO DE CLASIFICACIÓN (Solo en Detalle de Clientes) ── */}
          {pestañaActiva === 'DETALLE' && (
            <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs flex items-center justify-between flex-wrap gap-2.5">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-700">
                <Filter size={15} className="text-blue-600" />
                <span>Filtrar por Clasificación / Antigüedad:</span>
              </div>
              <div className="flex items-center gap-1.5 flex-wrap text-xs">
                {[
                  { id: 'TODOS', label: 'Todos' },
                  { id: 'AL_DIA', label: 'Clientes al Día', color: 'bg-emerald-50 text-emerald-800 border-emerald-200 hover:bg-emerald-100' },
                  { id: 'ATRASO_15', label: 'Atraso 15 días', color: 'bg-amber-50 text-amber-900 border-amber-200 hover:bg-amber-100' },
                  { id: 'ATRASO_30', label: 'Atraso 30 días', color: 'bg-orange-50 text-orange-900 border-orange-200 hover:bg-orange-100' },
                  { id: 'ATRASO_45', label: 'Atraso 45 días', color: 'bg-rose-50 text-rose-900 border-rose-200 hover:bg-rose-100' },
                  { id: 'ATRASO_60', label: 'Atraso 60 días', color: 'bg-red-50 text-red-950 border-red-200 hover:bg-red-100' },
                  { id: 'ATRASO_TODOS', label: 'Todos en Atraso', color: 'bg-yellow-50 text-yellow-900 border-yellow-200 hover:bg-yellow-100' },
                  { id: 'NUEVO', label: 'Nuevos', color: 'bg-amber-50 text-amber-900 border-amber-200 hover:bg-amber-100' },
                  { id: 'REENGANCHADO', label: 'Reenganchados', color: 'bg-blue-50 text-blue-900 border-blue-200 hover:bg-blue-100' },
                  { id: 'CANCELADO', label: 'Cancelados', color: 'bg-slate-100 text-slate-700 border-slate-200 hover:bg-slate-200' },
                ].map((b) => {
                  const active = filtroClasificacion === b.id
                  return (
                    <button
                      key={b.id}
                      onClick={() => setFiltroClasificacion(b.id)}
                      className={clsx(
                        'px-2.5 py-1 rounded-lg border font-medium transition-all shadow-2xs',
                        active
                          ? 'bg-blue-600 text-white border-blue-600 font-bold shadow-xs'
                          : b.color || 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                      )}
                    >
                      {b.label}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-amber-300 border-b border-amber-400 text-slate-900 select-none">
                    <th className="px-3 py-3 text-left font-bold uppercase tracking-wider">
                      <div className="flex items-center gap-1">
                        <span>Clasificación</span>
                        {filtroClasificacion !== 'TODOS' && pestañaActiva === 'DETALLE' && (
                          <span className="w-2 h-2 rounded-full bg-blue-700 animate-pulse" title="Filtro de clasificación activo" />
                        )}
                      </div>
                    </th>
                    <th className="px-3.5 py-3 text-left font-bold uppercase tracking-wider">Nombre del Cliente</th>
                    <th className="px-3 py-3 text-left font-bold uppercase tracking-wider">Empresa</th>
                    <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Monto Préstamo</th>
                    <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Capital Pagado</th>
                    <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Balance Antes Cobro</th>
                    <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Capital Cobrado</th>
                    <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Interés Cobrado</th>
                    <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Capital Actual Adeudado</th>
                    <th className="px-2.5 py-3 text-center font-bold uppercase tracking-wider">Tasa</th>
                    <th className="px-3 py-3 text-left font-bold uppercase tracking-wider">Comentario</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100">
                  {loadingDetalle ? (
                    <tr>
                      <td colSpan={11} className="px-4 py-12 text-center text-slate-400">
                        Cargando detalle individual de clientes...
                      </td>
                    </tr>
                  ) : filasDetalleFiltradas.length === 0 ? (
                    <tr>
                      <td colSpan={11} className="px-4 py-12 text-center text-slate-400">
                        No se encontraron registros para los filtros seleccionados.
                      </td>
                    </tr>
                  ) : (
                    filasDetalleFiltradas.map((r) => {
                      const badgeClass = BADGES[r.clasificacion] || 'bg-slate-100 text-slate-700'
                      const isRowYellow = r.clasificacion === 'NUEVO' || r.clasificacion?.startsWith('SITUACION ATRASO')
                      return (
                        <tr
                          key={r.numeroPrestamo || r.idCliente}
                          className={clsx(
                            'transition-colors font-medium text-slate-800',
                            isRowYellow ? 'bg-amber-50/50 hover:bg-amber-100/60' : 'hover:bg-slate-50/80'
                          )}
                        >
                          <td className="px-3 py-2.5 whitespace-nowrap">
                            <span className={clsx('px-2 py-0.5 rounded text-[10px] tracking-wide inline-block', badgeClass)}>
                              {r.clasificacion}
                            </span>
                          </td>
                          <td className="px-3.5 py-2.5 font-bold text-slate-900 whitespace-nowrap">
                            <Link
                              to={r.numeroPrestamo ? `/prestamos/${r.numeroPrestamo}` : '#'}
                              className="hover:text-blue-600 transition-colors"
                              title="Consultar cliente / préstamo"
                            >
                              {r.nombreCliente}
                            </Link>
                          </td>
                          <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">
                            {r.empresa || '—'}
                          </td>
                          <td className="px-3 py-2.5 text-right font-mono font-semibold text-slate-900 whitespace-nowrap">
                            {fmt(r.montoPrestamo)}
                          </td>
                          <td className="px-3 py-2.5 text-right font-mono font-medium text-slate-700 whitespace-nowrap">
                            {fmt(r.capitalPagado)}
                          </td>
                          <td className="px-3 py-2.5 text-right font-mono font-medium text-slate-700 whitespace-nowrap">
                            {fmt(r.balanceAntesCobro)}
                          </td>
                          <td className="px-3 py-2.5 text-right font-mono font-semibold text-emerald-700 whitespace-nowrap">
                            {fmt(r.capitalCobradoQuincena)}
                          </td>
                          <td className="px-3 py-2.5 text-right font-mono font-semibold text-indigo-700 whitespace-nowrap">
                            {fmt(r.interesCobradoQuincena)}
                          </td>
                          <td className="px-3 py-2.5 text-right font-mono font-semibold text-blue-700 whitespace-nowrap">
                            {fmt(
                              (r.capitalActualAdeudado && Number(r.capitalActualAdeudado) !== 0)
                                ? r.capitalActualAdeudado
                                : Math.max(0, Number(r.montoPrestamo || 0) - Number(r.capitalPagado || 0))
                            )}
                          </td>
                          <td className="px-2.5 py-2.5 text-center font-mono whitespace-nowrap">
                            {r.tasa}%
                          </td>
                          <td className="px-3 py-2.5 text-slate-500 italic text-[11px] whitespace-nowrap">
                            {r.comentario || '—'}
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>

                {/* ── FILA FINAL DE TOTALES EN PESOS ($) ── */}
                {!loadingDetalle && filasDetalleFiltradas.length > 0 && (
                  <tfoot>
                    <tr className="bg-slate-900 text-white font-bold border-t-2 border-slate-950 text-xs">
                      <td colSpan={3} className="px-3.5 py-3 uppercase tracking-wider">
                        TOTAL ({totalesDetalleCalculados.totalRegistros ?? filasDetalleFiltradas.length} Registros)
                      </td>
                      <td className="px-3 py-3 text-right font-mono text-amber-300">
                        {fmt(totalesDetalleCalculados.totalMontoPrestamo)}
                      </td>
                      <td className="px-3 py-3 text-right font-mono text-slate-300">
                        {fmt(totalesDetalleCalculados.totalCapitalPagado)}
                      </td>
                      <td className="px-3 py-3 text-right font-mono text-slate-300">
                        {fmt(totalesDetalleCalculados.totalBalanceAntesCobro)}
                      </td>
                      <td className="px-3 py-3 text-right font-mono text-emerald-300">
                        {fmt(totalesDetalleCalculados.totalCapitalCobradoQuincena)}
                      </td>
                      <td className="px-3 py-3 text-right font-mono text-indigo-300">
                        {fmt(totalesDetalleCalculados.totalInteresCobradoQuincena)}
                      </td>
                      <td className="px-3 py-3 text-right font-mono text-blue-300">
                        {fmt(
                          (totalesDetalleCalculados.totalCapitalActualAdeudado && Number(totalesDetalleCalculados.totalCapitalActualAdeudado) !== 0)
                            ? totalesDetalleCalculados.totalCapitalActualAdeudado
                            : Math.max(0, Number(totalesDetalleCalculados.totalMontoPrestamo || 0) - Number(totalesDetalleCalculados.totalCapitalPagado || 0))
                        )}
                      </td>
                      <td className="px-2.5 py-3 text-center font-mono">
                        {totalesDetalleCalculados.tasaPromedio}%
                      </td>
                      <td className="px-3 py-3 text-slate-400 text-[11px]">
                        Quincena {fechaHasta}
                      </td>
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </div>
        </section>
      )}

      {/* ── CONTENIDO: NUEVO REPORTE DE CLIENTES ATRASADOS / MORA POR TRAMOS Y COMPAÑÍA ── */}
      {pestañaActiva === 'ATRASADOS' && (
        <section className="space-y-4">
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center justify-between text-xs text-red-950 font-medium flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <AlertTriangle size={18} className="text-red-600 flex-shrink-0" />
              <div>
                <span className="font-bold uppercase tracking-wide">
                  Reporte Especializado de Cartera en Mora por Tramos Oficiales
                </span>
                <span className="ml-2 text-red-700">
                  (Corte: {fechaHasta || 'Fecha Actual'} — Tramos: 30 Días, Legal 60 Días y 90 Días o más)
                </span>
                {sufijoTituloEmpresa && (
                  <span className="block text-red-800 font-semibold pt-0.5">{sufijoTituloEmpresa}</span>
                )}
              </div>
            </div>
            <div className="font-bold text-red-900 bg-red-100 px-3 py-1.5 rounded-lg border border-red-200">
              Total Clientes Atrasados: {totalesMora.totalClientesMora ?? 0}
            </div>
          </div>

          {/* ── TARJETAS KPI DE MORA POR TRAMOS ── */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            <div className="bg-white rounded-xl border border-red-200 p-3.5 shadow-xs">
              <span className="text-[11px] font-bold text-red-600 uppercase tracking-wider block">
                Total Cartera en Mora
              </span>
              <div className="text-xl font-extrabold font-mono text-red-700 mt-1">
                {fmt(totalesMora.totalCapitalMora)}
              </div>
              <span className="text-[11px] text-slate-500 mt-0.5 block">
                {totalesMora.totalPrestamosMora ?? 0} préstamos en atraso
              </span>
            </div>

            <div className="bg-white rounded-xl border border-amber-200 p-3.5 shadow-xs">
              <span className="text-[11px] font-bold text-amber-700 uppercase tracking-wider block">
                Mora 30 Días (1 a 30d)
              </span>
              <div className="text-xl font-extrabold font-mono text-amber-800 mt-1">
                {fmt(totalesMora.totalCapitalMora30Dias)}
              </div>
              <span className="text-[11px] text-slate-500 mt-0.5 block">
                Atraso reciente
              </span>
            </div>

            <div className="bg-white rounded-xl border border-orange-200 p-3.5 shadow-xs">
              <span className="text-[11px] font-bold text-orange-700 uppercase tracking-wider block">
                Legal 60 Días (31 a 60d)
              </span>
              <div className="text-xl font-extrabold font-mono text-orange-800 mt-1">
                {fmt(totalesMora.totalCapitalMora60DiasLegal)}
              </div>
              <span className="text-[11px] text-slate-500 mt-0.5 block">
                Fase cobranza legal
              </span>
            </div>

            <div className="bg-white rounded-xl border border-rose-200 p-3.5 shadow-xs">
              <span className="text-[11px] font-bold text-rose-700 uppercase tracking-wider block">
                90 Días o más (&gt; 60d)
              </span>
              <div className="text-xl font-extrabold font-mono text-rose-800 mt-1">
                {fmt(totalesMora.totalCapitalMora90MasDias)}
              </div>
              <span className="text-[11px] text-slate-500 mt-0.5 block">
                Mora crítica / alta
              </span>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-3.5 shadow-xs">
              <span className="text-[11px] font-bold text-slate-700 uppercase tracking-wider block">
                Total Deuda en Mora
              </span>
              <div className="text-xl font-extrabold font-mono text-slate-900 mt-1">
                {fmt(totalesMora.totalDeudaMora)}
              </div>
              <span className="text-[11px] text-slate-500 mt-0.5 block">
                Capital + Int + Moras
              </span>
            </div>
          </div>

          {/* ── SELECTOR DE VISTA: RESUMEN POR COMPAÑÍA VS DETALLE INDIVIDUAL ── */}
          <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
            <button
              onClick={() => setSubtabAtrasados('RESUMEN')}
              className={clsx(
                'px-3.5 py-1.5 text-xs font-bold rounded-lg transition-all',
                subtabAtrasados === 'RESUMEN'
                  ? 'bg-red-600 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              )}
            >
              1. Resumen por Compañía / Cartera ({carterasMora.length})
            </button>
            <button
              onClick={() => setSubtabAtrasados('DETALLE')}
              className={clsx(
                'px-3.5 py-1.5 text-xs font-bold rounded-lg transition-all',
                subtabAtrasados === 'DETALLE'
                  ? 'bg-red-600 text-white shadow-xs'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              )}
            >
              2. Detalle Individual de Clientes en Mora ({clientesMora.length})
            </button>
          </div>

          {/* ── TABLA 1: RESUMEN POR COMPAÑÍA / CARTERA ── */}
          {subtabAtrasados === 'RESUMEN' && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-red-600 border-b border-red-700 text-white select-none">
                      <th className="px-3.5 py-3 text-left font-bold uppercase tracking-wider">Cartera / Empresa</th>
                      <th className="px-2.5 py-3 text-center font-bold uppercase tracking-wider">Clientes</th>
                      <th className="px-2.5 py-3 text-center font-bold uppercase tracking-wider">Préstamos</th>
                      <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Mora 30 Días</th>
                      <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Legal 60 Días</th>
                      <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Mora 90+ Días</th>
                      <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Total Capital en Mora</th>
                      <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Otros Cargos</th>
                      <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Total Deuda en Mora</th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-slate-100">
                    {loadingAtrasados ? (
                      <tr>
                        <td colSpan={9} className="px-4 py-12 text-center text-slate-400">
                          Analizando cartera y calculando tramos de mora...
                        </td>
                      </tr>
                    ) : carterasMora.length === 0 ? (
                      <tr>
                        <td colSpan={9} className="px-4 py-12 text-center text-slate-400">
                          ¡Excelente! No se registran préstamos en mora para los filtros seleccionados.
                        </td>
                      </tr>
                    ) : (
                      carterasMora.map((c, idx) => (
                        <tr key={idx} className="hover:bg-red-50/40 transition-colors font-medium text-slate-800">
                          <td className="px-3.5 py-2.5 font-bold text-slate-900">{c.cartera}</td>
                          <td className="px-2.5 py-2.5 text-center font-bold text-red-700">{c.totalClientesMora}</td>
                          <td className="px-2.5 py-2.5 text-center text-slate-600">{c.totalPrestamosMora}</td>
                          <td className="px-3 py-2.5 text-right font-mono font-medium text-amber-800">
                            {fmt(c.capitalMora30Dias)}
                          </td>
                          <td className="px-3 py-2.5 text-right font-mono font-semibold text-orange-800">
                            {fmt(c.capitalMora60DiasLegal)}
                          </td>
                          <td className="px-3 py-2.5 text-right font-mono font-bold text-rose-800">
                            {fmt(c.capitalMora90MasDias)}
                          </td>
                          <td className="px-3 py-2.5 text-right font-mono font-bold text-red-700">
                            {fmt(c.totalCapitalMora)}
                          </td>
                          <td className="px-3 py-2.5 text-right font-mono text-slate-600">
                            {fmt(c.otrosCargosMora)}
                          </td>
                          <td className="px-3 py-2.5 text-right font-mono font-bold text-slate-900">
                            {fmt(c.totalDeudaMora)}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>

                  {!loadingAtrasados && carterasMora.length > 0 && (
                    <tfoot>
                      <tr className="bg-slate-900 text-white font-bold border-t-2 border-slate-950 text-xs">
                        <td className="px-3.5 py-3 uppercase tracking-wider">
                          TOTAL GENERAL ({totalesMora.totalCarteras ?? carterasMora.length} Compañías)
                        </td>
                        <td className="px-2.5 py-3 text-center text-red-300">
                          {totalesMora.totalClientesMora}
                        </td>
                        <td className="px-2.5 py-3 text-center text-slate-300">
                          {totalesMora.totalPrestamosMora}
                        </td>
                        <td className="px-3 py-3 text-right font-mono text-amber-300">
                          {fmt(totalesMora.totalCapitalMora30Dias)}
                        </td>
                        <td className="px-3 py-3 text-right font-mono text-orange-300">
                          {fmt(totalesMora.totalCapitalMora60DiasLegal)}
                        </td>
                        <td className="px-3 py-3 text-right font-mono text-rose-300">
                          {fmt(totalesMora.totalCapitalMora90MasDias)}
                        </td>
                        <td className="px-3 py-3 text-right font-mono text-red-300">
                          {fmt(totalesMora.totalCapitalMora)}
                        </td>
                        <td className="px-3 py-3 text-right font-mono text-slate-300">
                          {fmt((Number(totalesMora.totalInteresVencido) || 0) + (Number(totalesMora.totalMoraPendiente) || 0))}
                        </td>
                        <td className="px-3 py-3 text-right font-mono text-emerald-300">
                          {fmt(totalesMora.totalDeudaMora)}
                        </td>
                      </tr>
                    </tfoot>
                  )}
                </table>
              </div>
            </div>
          )}

          {/* ── TABLA 2: DETALLE INDIVIDUAL DE CLIENTES EN MORA ── */}
          {subtabAtrasados === 'DETALLE' && (
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-red-600 border-b border-red-700 text-white select-none">
                      <th className="px-3.5 py-3 text-left font-bold uppercase tracking-wider">Cliente</th>
                      <th className="px-3 py-3 text-left font-bold uppercase tracking-wider">Cédula</th>
                      <th className="px-3 py-3 text-left font-bold uppercase tracking-wider">Teléfono</th>
                      <th className="px-3 py-3 text-left font-bold uppercase tracking-wider">Empresa</th>
                      <th className="px-2.5 py-3 text-center font-bold uppercase tracking-wider">Préstamo</th>
                      <th className="px-2.5 py-3 text-center font-bold uppercase tracking-wider">Días Atraso</th>
                      <th className="px-3 py-3 text-center font-bold uppercase tracking-wider">Tramo de Mora</th>
                      <th className="px-2 py-3 text-center font-bold uppercase tracking-wider">Cuotas</th>
                      <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Capital Vencido</th>
                      <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Interés Vencido</th>
                      <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Total Vencido</th>
                      <th className="px-3 py-3 text-right font-bold uppercase tracking-wider">Saldo Capital</th>
                      <th className="px-2.5 py-3 text-center font-bold uppercase tracking-wider">Acción</th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-slate-100">
                    {loadingAtrasados ? (
                      <tr>
                        <td colSpan={13} className="px-4 py-12 text-center text-slate-400">
                          Cargando detalle de clientes en mora...
                        </td>
                      </tr>
                    ) : clientesMora.length === 0 ? (
                      <tr>
                        <td colSpan={13} className="px-4 py-12 text-center text-slate-400">
                          No se encontraron clientes con mora registrada.
                        </td>
                      </tr>
                    ) : (
                      clientesMora.map((cl) => {
                        const tramoColor = cl.tramoMora === '30 DIAS'
                          ? 'bg-amber-100 text-amber-900 border-amber-300'
                          : cl.tramoMora === 'LEGAL 60 DIAS'
                          ? 'bg-orange-100 text-orange-900 border-orange-300'
                          : 'bg-red-100 text-red-950 font-bold border-red-300'
                        return (
                          <tr key={cl.numeroPrestamo} className="hover:bg-red-50/30 transition-colors font-medium text-slate-800">
                            <td className="px-3.5 py-2.5 font-bold text-slate-900 whitespace-nowrap">
                              {cl.nombreCliente}
                            </td>
                            <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">{cl.cedula || '—'}</td>
                            <td className="px-3 py-2.5 text-slate-600 whitespace-nowrap">{cl.telefono || '—'}</td>
                            <td className="px-3 py-2.5 text-slate-700 whitespace-nowrap">{cl.empresa || '—'}</td>
                            <td className="px-2.5 py-2.5 text-center font-mono font-bold text-blue-700 whitespace-nowrap">
                              #{cl.numeroPrestamo}
                            </td>
                            <td className="px-2.5 py-2.5 text-center font-bold font-mono text-red-600 whitespace-nowrap">
                              {cl.diasAtraso} d
                            </td>
                            <td className="px-3 py-2.5 text-center whitespace-nowrap">
                              <span className={clsx('px-2 py-0.5 rounded text-[10px] font-bold border inline-block', tramoColor)}>
                                {cl.tramoMora}
                              </span>
                            </td>
                            <td className="px-2 py-2.5 text-center font-mono text-slate-700 whitespace-nowrap">
                              {cl.cuotasVencidas}
                            </td>
                            <td className="px-3 py-2.5 text-right font-mono font-bold text-red-700 whitespace-nowrap">
                              {fmt(cl.capitalVencido)}
                            </td>
                            <td className="px-3 py-2.5 text-right font-mono text-indigo-700 whitespace-nowrap">
                              {fmt(cl.interesVencido)}
                            </td>
                            <td className="px-3 py-2.5 text-right font-mono font-bold text-slate-900 whitespace-nowrap">
                              {fmt(cl.totalVencido)}
                            </td>
                            <td className="px-3 py-2.5 text-right font-mono text-slate-600 whitespace-nowrap">
                              {fmt(cl.saldoCapital)}
                            </td>
                            <td className="px-2.5 py-2.5 text-center whitespace-nowrap">
                              <Link
                                to={`/prestamos/${cl.numeroPrestamo}`}
                                className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-semibold text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-md transition-colors"
                                title="Ver consulta integral del préstamo y cuotas"
                              >
                                Ver
                                <ExternalLink size={10} />
                              </Link>
                            </td>
                          </tr>
                        )
                      })
                    )}
                  </tbody>

                  {!loadingAtrasados && clientesMora.length > 0 && (
                    <tfoot>
                      <tr className="bg-slate-900 text-white font-bold border-t-2 border-slate-950 text-xs">
                        <td colSpan={4} className="px-3.5 py-3 uppercase tracking-wider">
                          TOTAL ({clientesMora.length} Clientes)
                        </td>
                        <td colSpan={4} className="px-2 py-3 text-center font-mono text-slate-300">
                          {totalesMora.totalPrestamosMora} préstamos
                        </td>
                        <td className="px-3 py-3 text-right font-mono text-red-300">
                          {fmt(totalesMora.totalCapitalMora)}
                        </td>
                        <td className="px-3 py-3 text-right font-mono text-indigo-300">
                          {fmt(totalesMora.totalInteresVencido)}
                        </td>
                        <td className="px-3 py-3 text-right font-mono text-emerald-300">
                          {fmt(totalesMora.totalDeudaMora)}
                        </td>
                        <td colSpan={2} className="px-3 py-3 text-slate-400 text-center text-[11px]">
                          Corte al {fechaHasta}
                        </td>
                      </tr>
                    </tfoot>
                  )}
                </table>
              </div>
            </div>
          )}
        </section>
      )}

    </div>
  )
}
