/**
 * Clientes.jsx — Página de gestión de cartera de clientes
 * Soporta ordenamiento dinámico, exportación a Excel y PDF,
 * visualización de referencias y modal de perfil integral de cliente.
 */
import { useState } from 'react'
import {
  Users,
  UserPlus,
  RefreshCw,
  AlertTriangle,
  TrendingDown,
  FileSpreadsheet,
  FileText,
  Download,
} from 'lucide-react'
import { useClientes } from '../hooks/useApi'
import KPICard from '../components/KPICard'
import FiltrosBar from '../components/FiltrosBar'
import ClientesTable from '../components/ClientesTable'
import ClientePerfilModal from '../components/ClientePerfilModal'
import { exportarClientesExcel, exportarClientesPDF, exportarTopEmpresasPDF } from '../utils/exportUtils'

const FILTROS_INICIALES = {
  pagina: 1,
  porPagina: 25,
  busqueda: '',
  tipoCliente: 'ACTIVO',
  estado: '',
  desde: '',
  hasta: '',
  empresa: '',
  oficina: '',
  creador: '',
  tipoFecha: 'PRESTAMO',
  ordenarPor: 'fecha',
  ordenDireccion: 'DESC',
}

export default function Clientes() {
  const [filtros, setFiltros] = useState(FILTROS_INICIALES)
  const [clientePerfilId, setClientePerfilId] = useState(null)
  const [exportando, setExportando] = useState(false)

  const { data, isLoading, isError, error } = useClientes(filtros)

  const clientes        = data?.clientes      ?? []
  const stats           = data?.stats         ?? {}
  const porEmpresa      = data?.porEmpresa    ?? []
  const opcionesOficina = data?.oficinas     ?? []
  const totalPaginas    = stats.totalPaginas  ?? 1
  const totalRegistros  = stats.totalFiltrados ?? stats.totalClientes ?? 0

  function handleFiltroChange(campo, valor) {
    setFiltros((prev) => {
      const resetPagina = campo !== 'pagina' ? { pagina: 1 } : {}
      return { ...prev, ...resetPagina, [campo]: valor }
    })
  }

  function handleSortChange(colId, direccion) {
    setFiltros((prev) => ({
      ...prev,
      ordenarPor: colId,
      ordenDireccion: direccion,
      pagina: 1,
    }))
  }

  // Descarga todo el universo filtrado respetando los filtros actuales (hasta 5,000 registros)
  async function fetchClientesParaExportar() {
    try {
      const params = new URLSearchParams()
      const mapped = {
        ...filtros,
        pagina: 1,
        porPagina: 5000,
        fechaDesde: filtros.fechaDesde || filtros.desde || undefined,
        fechaHasta: filtros.fechaHasta || filtros.hasta || undefined,
      }
      delete mapped.desde
      delete mapped.hasta

      Object.entries(mapped).forEach(([k, v]) => {
        if (v !== null && v !== undefined && v !== '') params.set(k, v)
      })

      const res = await fetch(`/api/clientes/?${params.toString()}`)
      if (res.ok) {
        const json = await res.json()
        if (json?.clientes && json.clientes.length > 0) {
          return json.clientes
        }
      }
    } catch (e) {
      console.warn('Fallo descarga completa para exportar, usando lista actual:', e)
    }
    return clientes || []
  }

  function construirTituloExportacion(totalItems) {
    const partes = [`Informe de Cartera (${filtros.tipoCliente || 'ACTIVO'})`]
    if (filtros.empresa && filtros.empresa.trim()) {
      partes.push(`Correspondiente a los Clientes de: ${filtros.empresa.trim().toUpperCase()}`)
    }
    if (filtros.estado && filtros.estado.trim()) {
      partes.push(`Estado: ${filtros.estado.trim()}`)
    }
    if (filtros.oficina && filtros.oficina.trim()) {
      partes.push(`Oficina: ${filtros.oficina.trim()}`)
    }
    if (filtros.creador && filtros.creador.trim()) {
      partes.push(`Creador: ${filtros.creador.trim()}`)
    }
    return `${partes.join(' — ')} (${totalItems} clientes)`
  }

  function construirNombreArchivoExportacion() {
    const base = `Cartera_${filtros.tipoCliente || 'ACTIVO'}`
    const emp = filtros.empresa && filtros.empresa.trim()
      ? `_${filtros.empresa.trim().replace(/[^a-zA-Z0-9_-]/g, '_')}`
      : ''
    const est = filtros.estado && filtros.estado.trim()
      ? `_${filtros.estado.trim().replace(/[^a-zA-Z0-9_-]/g, '_')}`
      : ''
    return `${base}${emp}${est}`
  }

  async function handleExportExcel() {
    try {
      setExportando(true)
      const dataset = await fetchClientesParaExportar()
      exportarClientesExcel(
        dataset,
        construirNombreArchivoExportacion(),
        construirTituloExportacion(dataset.length)
      )
    } catch (err) {
      alert(`Error al exportar a Excel: ${err.message}`)
    } finally {
      setExportando(false)
    }
  }

  async function handleExportPDF() {
    try {
      setExportando(true)
      const dataset = await fetchClientesParaExportar()
      exportarClientesPDF(
        dataset,
        construirTituloExportacion(dataset.length),
        construirNombreArchivoExportacion()
      )
    } catch (err) {
      alert(`Error al exportar a PDF: ${err.message}`)
    } finally {
      setExportando(false)
    }
  }

  const maxClientes = Math.max(...porEmpresa.map((e) => e.totalClientes || 0), 1)

  const labelCondicion =
    filtros.estado === 'REENGANCHADO'
      ? 'clientes reenganchados'
      : filtros.estado === 'NUEVO'
      ? 'clientes nuevos'
      : filtros.estado === 'EN MORA'
      ? 'clientes en mora'
      : filtros.estado === 'PROBLEMATICO'
      ? 'clientes problemáticos'
      : filtros.estado === 'AL DIA'
      ? 'clientes al día'
      : filtros.tipoCliente === 'CANCELADO'
      ? 'clientes cancelados / saldados'
      : filtros.tipoCliente === 'TODOS'
      ? 'clientes en total'
      : 'clientes activos en cartera'

  return (
    <div className="p-6 space-y-6 max-w-screen-2xl mx-auto">
      
      {/* ── Header con Botones de Exportación ────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Cartera de Clientes</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {isLoading
              ? 'Cargando…'
              : `${totalRegistros.toLocaleString('es-DO')} ${labelCondicion}`}
          </p>
        </div>

        {/* Acciones de Exportación */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={handleExportExcel}
            disabled={exportando || isLoading || clientes.length === 0}
            className="flex items-center gap-2 px-3.5 py-2 text-sm font-semibold bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl transition-all shadow-sm hover:shadow disabled:opacity-50 disabled:cursor-not-allowed"
            title="Exportar cartera completa filtrada a Excel"
          >
            <FileSpreadsheet size={16} />
            <span>Exportar Excel</span>
          </button>

          <button
            onClick={handleExportPDF}
            disabled={exportando || isLoading || clientes.length === 0}
            className="flex items-center gap-2 px-3.5 py-2 text-sm font-semibold bg-rose-600 hover:bg-rose-700 text-white rounded-xl transition-all shadow-sm hover:shadow disabled:opacity-50 disabled:cursor-not-allowed"
            title="Exportar cartera completa filtrada a PDF"
          >
            <FileText size={16} />
            <span>Exportar PDF</span>
          </button>
        </div>
      </div>

      {/* ── Error banner ─────────────────────────────────────────────────── */}
      {isError && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-700">
          ⚠️ {error?.message ?? 'Error al cargar los datos de clientes.'}
        </div>
      )}

      {/* ── KPI Cards ────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        <KPICard
          title="Total Clientes"
          value={isLoading ? '…' : (stats.totalClientesGlobal ?? stats.totalClientes ?? 0).toLocaleString('es-DO')}
          icon={Users}
          variant="blue"
        />
        <KPICard
          title="Nuevos"
          value={isLoading ? '…' : (stats.nuevos ?? 0).toLocaleString('es-DO')}
          icon={UserPlus}
          variant="green"
        />
        <KPICard
          title="Reenganchados"
          value={isLoading ? '…' : (stats.reenganchados ?? 0).toLocaleString('es-DO')}
          icon={RefreshCw}
          variant="blue"
        />
        <KPICard
          title="En Mora"
          value={isLoading ? '…' : (stats.enMora ?? 0).toLocaleString('es-DO')}
          icon={TrendingDown}
          variant="red"
        />
        <KPICard
          title="Problemáticos"
          value={isLoading ? '…' : (stats.problematicos ?? 0).toLocaleString('es-DO')}
          icon={AlertTriangle}
          variant="yellow"
        />
      </div>

      {/* ── Barra de Filtros y Chips ─────────────────────────────────────── */}
      <FiltrosBar
        filtros={filtros}
        onChange={handleFiltroChange}
        opcionesOficina={opcionesOficina}
      />

      {/* ── Tabla de Clientes ─────────────────────────────────────────────── */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-bold text-slate-800">
            Listado de Clientes
          </h2>
          <span className="text-xs text-slate-500">
            {exportando && 'Generando archivo de exportación...'}
          </span>
        </div>
        <ClientesTable
          clientes={clientes}
          loading={isLoading}
          pagina={filtros.pagina}
          totalPaginas={totalPaginas}
          onPaginaChange={(p) => handleFiltroChange('pagina', p)}
          ordenarPor={filtros.ordenarPor}
          ordenDireccion={filtros.ordenDireccion}
          onSortChange={handleSortChange}
          onVerPerfil={(id) => setClientePerfilId(id)}
        />
      </section>

      {/* ── Gráfico Top Empresas ─────────────────────────────────────────── */}
      {porEmpresa.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <div>
              <h2 className="text-base font-semibold text-slate-800">
                Top Empresas
              </h2>
              <p className="text-xs text-slate-400">
                Distribución de clientes y cartera por compañía
              </p>
            </div>
            <button
              onClick={() => exportarTopEmpresasPDF(porEmpresa)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-lg transition-colors shadow-2xs"
              title="Descargar distribución completa de Top Empresas en PDF formal"
            >
              <FileText size={14} />
              <span>Generar PDF</span>
            </button>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-3">
            {porEmpresa.slice(0, 10).map((emp) => {
              const porcentaje = Math.round((emp.totalClientes / maxClientes) * 100)
              return (
                <div key={emp.empresa} className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium text-slate-700 truncate max-w-xs">
                      {emp.empresa || '(Sin empresa)'}
                    </span>
                    <span className="text-slate-500 ml-3 whitespace-nowrap">
                      {emp.totalClientes} clientes
                    </span>
                  </div>
                  <div className="w-full bg-slate-100 rounded-full h-2">
                    <div
                      className="bg-blue-500 h-2 rounded-full transition-all duration-500"
                      style={{ width: `${porcentaje}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* ── Modal de Perfil e Historial Integral del Cliente ────────────── */}
      {clientePerfilId && (
        <ClientePerfilModal
          idCliente={clientePerfilId}
          onClose={() => setClientePerfilId(null)}
        />
      )}

    </div>
  )
}
