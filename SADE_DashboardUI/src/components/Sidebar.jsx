import { useState, useEffect } from 'react'
import { LayoutDashboard, Monitor, ChevronRight, Activity, FolderOpen } from 'lucide-react'
import api from '../services/api'

const Sidebar = ({ onSelectDashboard, activeId }) => {
  const [menuItems, setMenuItems] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchMenu = async () => {
      try {
        const response = await api.get('/dashboard/menu')
        const data = response.data
          
          // Agrupar por Modulo (soportando camelCase y PascalCase)
          const grouped = data.reduce((acc, item) => {
            const mod = item.modulo || item.Modulo || 'General'
            if (!acc[mod]) acc[mod] = []
            acc[mod].push({
              id: item.id !== undefined ? item.id : item.Id,
              nombre: item.nombre || item.Nombre
            })
            return acc
          }, {})
          
          setMenuItems(grouped)
      } catch (error) {
        console.error("Error fetching menu:", error)
      } finally {
        setLoading(false)
      }
    }

    fetchMenu()
  }, [])

  return (
    <aside className="hide-on-print" style={{ width: '280px', backgroundColor: 'var(--sidebar-bg)', borderRight: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '2rem 1.5rem', borderBottom: '1px solid var(--border-color)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', color: 'white', fontWeight: 'bold', fontSize: '1.5rem' }}>
          <Activity size={28} color="var(--primary)" />
          SADE Web
        </div>
      </div>

      <div style={{ padding: '1.5rem 1rem', flex: 1, overflowY: 'auto' }}>
        <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 'bold', letterSpacing: '0.05em', marginBottom: '1rem', paddingLeft: '0.5rem' }}>
          Módulos Dinámicos
        </div>

        {loading ? (
          <div style={{ color: 'var(--text-muted)', paddingLeft: '0.5rem', fontSize: '0.9rem' }}>Cargando menú...</div>
        ) : Object.keys(menuItems).length === 0 ? (
          <div style={{ color: 'var(--text-muted)', paddingLeft: '0.5rem', fontSize: '0.9rem' }}>No hay indicadores configurados.</div>
        ) : (
          Object.entries(menuItems).map(([modulo, items], index) => (
            <div key={`mod-${index}-${modulo}`} style={{ marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.75rem 0.5rem', color: 'var(--text-light)', cursor: 'default' }}>
                <FolderOpen size={20} color="#a78bfa" />
                <span style={{ fontWeight: '500' }}>{modulo}</span>
              </div>

              <div style={{ marginLeft: '1.5rem', paddingLeft: '0.5rem', borderLeft: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: '0.25rem', marginTop: '0.25rem' }}>
                {items.map((item, itemIdx) => (
                  <button 
                    key={`btn-${item.id}-${itemIdx}`}
                    onClick={() => onSelectDashboard(item.id)}
                    style={{ 
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      width: '100%', padding: '0.5rem 0.75rem', 
                      backgroundColor: activeId === item.id ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                      color: activeId === item.id ? 'var(--primary)' : 'var(--text-muted)',
                      border: 'none', borderRadius: '6px', cursor: 'pointer', textAlign: 'left',
                      transition: 'all 0.2s', fontSize: '0.9rem'
                    }}
                    onMouseOver={(e) => { if(activeId !== item.id) { e.currentTarget.style.color = 'var(--text-light)'; e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.05)' } }}
                    onMouseOut={(e) => { if(activeId !== item.id) { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.backgroundColor = 'transparent' } }}
                  >
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.nombre}</span>
                    {activeId === item.id && <ChevronRight size={16} style={{ flexShrink: 0 }} />}
                  </button>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </aside>
  )
}

export default Sidebar
