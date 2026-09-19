/**
 * Clientes.jsx — Página de gestión de cartera de clientes
 */
import { useState } from 'react'
import { Users, UserPlus, RefreshCw, AlertTriangle, TrendingDown } from 'lucide-react'
import { useClientes } from '../hooks/useApi'
import KPICard from '../components/KPICard'
import FiltrosBar from '../components/FiltrosBar'
import ClientesTable from '../components/ClientesTable'

const FILTROS_INICIALES = {
  pagina: 1,
  porPagina: 25,
  busqueda: '',
  estado: '',
  desde: '',
  hasta: '',
  empresa: '',
  oficina: '',
}

export default function Clientes() {
  const [filtros, setFiltros] = useState(FILTROS_INICIALES)

  const { data, isLoading, isError, error } = useClientes(filtros)

  // Datos de la respuesta del API
  // La API retorna: { stats, clientes, porEmpresa, oficinas }
  const clientes       = data?.clientes      ?? []
  const stats          = data?.stats         ?? {}
  const porEmpresa     = data?.porEmpresa    ?? []
  const opcionesOficina = data?.oficinas     ?? []
  const totalPaginas   = stats.totalPaginas  ?? 1
  const totalRegistros = stats.totalClientes ?? 0

  function handleFiltroChange(campo, valor) {
    setFiltros(prev => {
      // Resetear página al cambiar cualquier filtro que no sea pagina
      const resetPagina = campo !== 'pagina' ? { pagina: 1 } : {}
      return { ...prev, ...resetPagina, [campo]: valor }
    })
  }

  // Máximo para la barra proporcional del gráfico de empresas
  const maxClientes = Math.max(...porEmpresa.map(e => e.totalClientes || 0), 1)

  return (
    <div className="p-6 space-y-6 max-w-screen-xl mx-auto">

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Clientes</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {isLoading
              ? 'Cargando…'
              : `${totalRegistros.toLocaleString('es-DO')} clientes en cartera`}
          </p>
        </div>
        <div className="p-2.5 rounded-lg bg-blue-50 text-blue-600">
          <Users size={24} />
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
          value={isLoading ? '…' : (stats.totalClientes ?? 0).toLocaleString('es-DO')}
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

      {/* ── Filtros ──────────────────────────────────────────────────────── */}
      <FiltrosBar
        filtros={filtros}
        onChange={handleFiltroChange}
        opcionesOficina={opcionesOficina}
      />

      {/* ── Tabla de Clientes ─────────────────────────────────────────────── */}
      <section>
        <h2 className="text-base font-semibold text-slate-700 mb-3">
          Cartera de Clientes
        </h2>
        <ClientesTable
          clientes={clientes}
          loading={isLoading}
          pagina={filtros.pagina}
          totalPaginas={totalPaginas}
          onPaginaChange={p => handleFiltroChange('pagina', p)}
        />
      </section>

      {/* ── Gráfico Top Empresas ─────────────────────────────────────────── */}
      {porEmpresa.length > 0 && (
        <section>
          <h2 className="text-base font-semibold text-slate-700 mb-3">
            Top Empresas
          </h2>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 space-y-3">
            {porEmpresa.slice(0, 10).map(emp => {
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

    </div>
  )
}
