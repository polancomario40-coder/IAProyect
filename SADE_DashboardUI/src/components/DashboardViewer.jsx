import { useState, useEffect } from 'react'
import { Calendar, Filter, Loader2, RefreshCcw, Search, Printer, LayoutDashboard, AlertTriangle } from 'lucide-react'
import { format, subMonths } from 'date-fns'
import DynamicRenderer from './DynamicRenderer'
import api from '../services/api'

const DashboardViewer = ({ idIndicador }) => {
  const [fechaDesde, setFechaDesde] = useState(format(subMonths(new Date(), 6), 'yyyy-MM-dd'))
  const [fechaHasta, setFechaHasta] = useState(format(new Date(), 'yyyy-MM-dd'))
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  
  // Nuevos estados para Cross-Filtering y Dual Layout
  const [filteredData, setFilteredData] = useState([])
  const [searchTerm, setSearchTerm] = useState('')
  const [columnFilters, setColumnFilters] = useState({})
  const [viewOverride, setViewOverride] = useState(null)

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.get(`/dashboard/${idIndicador}?fechaDesde=${fechaDesde}&fechaHasta=${fechaHasta}`)
      setData(response.data)
      setFilteredData(response.data?.data || [])
      setSearchTerm('') // reset search on new fetch
      setColumnFilters({}) // reset column filters
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // Cargar datos cuando cambie el indicador
  useEffect(() => {
    fetchData()
  }, [idIndicador])

  // Manejador para cambiar filtros de columna
  const handleColumnFilterChange = (colName, value) => {
    setColumnFilters(prev => ({
      ...prev,
      [colName]: value
    }))
  }

  // Lógica de Cross-Filtering (Global + Multicolumn AND)
  useEffect(() => {
    if (!data?.data) {
      setFilteredData([])
      return
    }
    
    const activeColFilters = Object.entries(columnFilters).filter(([k, v]) => v && v.trim() !== '')

    if (!searchTerm && activeColFilters.length === 0) {
      setFilteredData(data.data)
      return
    }
    
    const lowerSearch = searchTerm.toLowerCase()
    
    const filtered = data.data.filter(row => {
      // 1. Check Global Search
      let passesGlobal = true;
      if (lowerSearch) {
        passesGlobal = Object.values(row).some(val => 
          val !== null && val !== undefined && val.toString().toLowerCase().includes(lowerSearch)
        )
      }
      
      if (!passesGlobal) return false;
      
      // 2. Check Column Filters (AND logic)
      for (const [col, filterVal] of activeColFilters) {
        const rowVal = row[col];
        if (rowVal === null || rowVal === undefined) return false;
        
        if (!rowVal.toString().toLowerCase().includes(filterVal.toLowerCase().trim())) {
          return false;
        }
      }
      
      return true;
    })
    
    setFilteredData(filtered)
  }, [searchTerm, columnFilters, data])

  const currentView = viewOverride || data?.metadata?.tipoVista || 'Table'
  const isChart = currentView !== 'Table'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', height: '100%' }}>
      {/* Top Filter Bar */}
      <div className="glass-panel hide-on-print" style={{ padding: '1rem 1.5rem', display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'flex-end', justifyContent: 'space-between', background: 'rgba(15, 23, 42, 0.4)', border: '1px solid var(--border-color)' }}>
        
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Calendar size={14} /> Fecha Desde
            </label>
            <input 
              type="date" 
              className="premium-input"
              value={fechaDesde} 
              onChange={(e) => setFechaDesde(e.target.value)} 
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Calendar size={14} /> Fecha Hasta
            </label>
            <input 
              type="date" 
              className="premium-input"
              value={fechaHasta} 
              onChange={(e) => setFechaHasta(e.target.value)} 
            />
          </div>

          <button className="premium-btn" onClick={fetchData} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', height: '40px' }}>
            <Filter size={16} /> Mostrar
          </button>
        </div>

        {/* View Overrides & Print */}
        {data && (
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(0,0,0,0.3)', padding: '0.25rem 0.5rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <LayoutDashboard size={16} style={{ color: 'var(--text-muted)' }} />
              <select 
                value={viewOverride || ''} 
                onChange={(e) => setViewOverride(e.target.value || null)}
                style={{ background: 'transparent', color: 'var(--text-light)', border: 'none', outline: 'none', padding: '0.25rem', fontSize: '0.9rem', cursor: 'pointer' }}
              >
                <option value="" style={{ background: 'var(--sidebar-bg)' }}>-- Vista Original --</option>
                <option value="Table" style={{ background: 'var(--sidebar-bg)' }}>📋 Tabla de Datos</option>
                <option value="BarChart" style={{ background: 'var(--sidebar-bg)' }}>📊 Barra Vertical</option>
                <option value="HorizontalBarChart" style={{ background: 'var(--sidebar-bg)' }}>🗃️ Barra Horizontal</option>
                <option value="StackedBarChart" style={{ background: 'var(--sidebar-bg)' }}>🥞 Barra Apilada</option>
                <option value="LineChart" style={{ background: 'var(--sidebar-bg)' }}>📈 Línea de Tendencia</option>
                <option value="AreaChart" style={{ background: 'var(--sidebar-bg)' }}>🌊 Gráfico de Área</option>
                <option value="PieChart" style={{ background: 'var(--sidebar-bg)' }}>🥧 Pastel Clásico</option>
                <option value="DonutChart" style={{ background: 'var(--sidebar-bg)' }}>🍩 Gráfico de Dona</option>
              </select>
            </div>
            
            <button onClick={() => window.print()} className="premium-btn" style={{ background: 'transparent', border: '1px solid var(--primary)', color: 'var(--primary)', padding: '0.5rem 1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }} title="Imprimir Reporte">
              <Printer size={16} /> Imprimir
            </button>
          </div>
        )}
      </div>

      {/* Cross Filtering Search Bar */}
      {data && data.data?.length > 0 && (
        <div className="hide-on-print" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'rgba(15, 23, 42, 0.6)', padding: '0.75rem 1.5rem', borderRadius: '8px', border: '1px solid var(--glass-border)' }}>
          <Search size={18} style={{ color: 'var(--primary)' }} />
          <input 
            type="text" 
            placeholder="Escribe para buscar y filtrar los datos en tiempo real..." 
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ flex: 1, background: 'transparent', border: 'none', color: 'var(--text-light)', fontSize: '0.95rem', outline: 'none' }}
          />
          {searchTerm && (
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', background: 'rgba(0,0,0,0.3)', padding: '0.25rem 0.5rem', borderRadius: '4px' }}>
              {filteredData.length} resultados
            </span>
          )}
        </div>
      )}

      {/* Content Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {loading ? (
          <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '1rem', color: 'var(--primary)' }}>
            <Loader2 size={48} className="animate-spin" style={{ animation: 'spin 1s linear infinite' }} />
            <span style={{ color: 'var(--text-muted)' }}>Cargando indicador...</span>
            <style>{`@keyframes spin { 100% { transform: rotate(360deg); } }`}</style>
          </div>
        ) : error ? (
          <div style={{ padding: '2rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '8px', color: '#fca5a5' }}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>⚠️ Ocurrió un error</h3>
            <p style={{ marginTop: '0.5rem' }}>{error}</p>
            <button onClick={fetchData} style={{ marginTop: '1rem', background: 'transparent', border: '1px solid #fca5a5', color: '#fca5a5', padding: '0.5rem 1rem', borderRadius: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <RefreshCcw size={14} /> Reintentar
            </button>
          </div>
        ) : data ? (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div style={{ marginBottom: '1.5rem' }}>
              <h2 style={{ fontSize: '1.5rem', fontWeight: '600' }}>{data.metadata?.nombre || 'Indicador sin nombre'}</h2>
              <span style={{ display: 'inline-block', padding: '0.25rem 0.75rem', background: 'rgba(59, 130, 246, 0.2)', color: '#93c5fd', borderRadius: '9999px', fontSize: '0.75rem', marginTop: '0.5rem' }}>
                Módulo: {data.metadata?.modulo}
              </span>
            </div>
            
            {/* Dual Layout Engine */}
            <div style={{ flex: 1, width: '100%', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
              {isChart ? (
                <>
                  <div className="chart-container" style={{ height: '350px', background: 'rgba(15, 23, 42, 0.3)', borderRadius: '8px', padding: '1rem', border: '1px solid var(--glass-border)', display: 'flex', flexDirection: 'column' }}>
                    {(currentView === 'PieChart' || currentView === 'DonutChart') && filteredData.length > 15 ? (
                      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#fbbf24', textAlign: 'center', gap: '1rem', padding: '2rem' }}>
                        <AlertTriangle size={48} />
                        <div>
                          <h3 style={{ fontSize: '1.2rem', fontWeight: 'bold', marginBottom: '0.5rem' }}>Visualización no óptima</h3>
                          <p style={{ color: 'var(--text-muted)' }}>Hay demasiados datos ({filteredData.length} registros) para un gráfico de pastel. Por favor, aplique un filtro en la tabla para reducir los resultados, o cambie a un gráfico de Barras/Tabla.</p>
                        </div>
                      </div>
                    ) : (
                      <DynamicRenderer metadata={data.metadata} data={filteredData} overrideTipoVista={currentView} />
                    )}
                  </div>
                  <div style={{ flex: 1 }}>
                    <DynamicRenderer metadata={data.metadata} data={filteredData} overrideTipoVista="Table" columnFilters={columnFilters} onColumnFilterChange={handleColumnFilterChange} />
                  </div>
                </>
              ) : (
                <div style={{ flex: 1 }}>
                  <DynamicRenderer metadata={data.metadata} data={filteredData} overrideTipoVista="Table" columnFilters={columnFilters} onColumnFilterChange={handleColumnFilterChange} />
                </div>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}

export default DashboardViewer
