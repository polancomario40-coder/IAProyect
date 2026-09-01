import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, PieChart, Pie, Cell, LineChart, Line, AreaChart, Area } from 'recharts'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

// Función helper para formatear números de forma bonita (con comas y decimales)
const formatNumber = (value) => {
  if (typeof value === 'number') {
    return new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(value);
  }
  return value;
};

const DynamicRenderer = ({ metadata, data, overrideTipoVista, columnFilters, onColumnFilterChange }) => {

  if (!metadata || !data || data.length === 0) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', padding: '2rem' }}>
        No hay datos para el rango seleccionado o los criterios de búsqueda.
      </div>
    )
  }

  const tipoVista = overrideTipoVista || metadata.tipoVista
  const { ejeX, ejeY, configuracionUI } = metadata

  // Custom Tooltip premium
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="glass-panel" style={{ padding: '1rem', border: '1px solid rgba(255,255,255,0.1)' }}>
          <p style={{ color: 'var(--text-light)', fontWeight: 'bold', marginBottom: '0.5rem' }}>{label}</p>
          {payload.map((entry, index) => (
            <p key={index} style={{ color: entry.color, fontSize: '0.9rem' }}>
              {entry.name}: <span style={{ fontWeight: 'bold' }}>{formatNumber(entry.value)}</span>
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  if (tipoVista === 'BarChart') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--glass-border)" vertical={false} />
          <XAxis dataKey={ejeX} stroke="var(--text-muted)" tick={{ fill: 'var(--text-muted)' }} />
          <YAxis stroke="var(--text-muted)" tick={{ fill: 'var(--text-muted)' }} tickFormatter={formatNumber} />
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ paddingTop: '20px' }} />
          <Bar 
            dataKey={ejeY} 
            name={ejeY} 
            fill="url(#colorUv)" 
            radius={[6, 6, 0, 0]} 
            animationDuration={800}
          />
          <defs>
            <linearGradient id="colorUv" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.9}/>
              <stop offset="95%" stopColor="var(--primary)" stopOpacity={0.2}/>
            </linearGradient>
          </defs>
        </BarChart>
      </ResponsiveContainer>
    )
  }

  if (tipoVista === 'HorizontalBarChart') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <BarChart layout="vertical" data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--glass-border)" horizontal={false} />
          <XAxis type="number" stroke="var(--text-muted)" tick={{ fill: 'var(--text-muted)' }} tickFormatter={formatNumber} />
          <YAxis dataKey={ejeX} type="category" stroke="var(--text-muted)" tick={{ fill: 'var(--text-muted)' }} width={100} />
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ paddingTop: '20px' }} />
          <Bar 
            dataKey={ejeY} 
            name={ejeY} 
            fill="url(#colorUv)" 
            radius={[0, 6, 6, 0]} 
            animationDuration={800}
          />
          <defs>
            <linearGradient id="colorUv" x1="0" y1="0" x2="1" y2="0">
              <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.9}/>
              <stop offset="95%" stopColor="var(--primary)" stopOpacity={0.2}/>
            </linearGradient>
          </defs>
        </BarChart>
      </ResponsiveContainer>
    )
  }

  if (tipoVista === 'StackedBarChart') {
    // Assuming multiple Y axes properties might exist, but we stick to ejeY if it's dynamic
    // Usually Stacked requires multiple dataKeys. We'll map ejeY.
    return (
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--glass-border)" vertical={false} />
          <XAxis dataKey={ejeX} stroke="var(--text-muted)" tick={{ fill: 'var(--text-muted)' }} />
          <YAxis stroke="var(--text-muted)" tick={{ fill: 'var(--text-muted)' }} tickFormatter={formatNumber} />
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ paddingTop: '20px' }} />
          <Bar 
            dataKey={ejeY} 
            stackId="a"
            name={ejeY} 
            fill="url(#colorUv)" 
            animationDuration={800}
          />
          <defs>
            <linearGradient id="colorUv" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.9}/>
              <stop offset="95%" stopColor="var(--primary)" stopOpacity={0.2}/>
            </linearGradient>
          </defs>
        </BarChart>
      </ResponsiveContainer>
    )
  }

  if (tipoVista === 'LineChart') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--glass-border)" vertical={false} />
          <XAxis dataKey={ejeX} stroke="var(--text-muted)" tick={{ fill: 'var(--text-muted)' }} />
          <YAxis stroke="var(--text-muted)" tick={{ fill: 'var(--text-muted)' }} tickFormatter={formatNumber} />
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ paddingTop: '20px' }} />
          <Line 
            type="monotone" 
            dataKey={ejeY} 
            name={ejeY} 
            stroke="var(--primary)" 
            strokeWidth={3}
            dot={{ r: 4, fill: 'var(--bg-dark)', strokeWidth: 2 }}
            activeDot={{ r: 6 }}
            animationDuration={800}
          />
        </LineChart>
      </ResponsiveContainer>
    )
  }

  if (tipoVista === 'AreaChart') {
    return (
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--glass-border)" vertical={false} />
          <XAxis dataKey={ejeX} stroke="var(--text-muted)" tick={{ fill: 'var(--text-muted)' }} />
          <YAxis stroke="var(--text-muted)" tick={{ fill: 'var(--text-muted)' }} tickFormatter={formatNumber} />
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ paddingTop: '20px' }} />
          <Area 
            type="monotone" 
            dataKey={ejeY} 
            name={ejeY} 
            stroke="var(--primary)" 
            fill="url(#colorArea)" 
            strokeWidth={2}
            animationDuration={800}
          />
          <defs>
            <linearGradient id="colorArea" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.6}/>
              <stop offset="95%" stopColor="var(--primary)" stopOpacity={0.0}/>
            </linearGradient>
          </defs>
        </AreaChart>
      </ResponsiveContainer>
    )
  }

  if (tipoVista === 'PieChart' || tipoVista === 'DonutChart') {
    const isDonut = tipoVista === 'DonutChart';
    return (
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={isDonut ? 100 : 0}
            outerRadius={140}
            paddingAngle={isDonut ? 5 : 0}
            dataKey={ejeY}
            nameKey={ejeX}
            animationDuration={800}
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    )
  }

  if (tipoVista === 'Table') {
    const columns = configuracionUI?.grid?.columns || Object.keys(data[0]).map(k => ({ field: k, title: k }))
    
    // Calculate totals for numeric columns
    const columnTotals = {};
    columns.forEach(col => {
      // Check if this column is mostly numeric
      const isNumeric = data.some(row => typeof row[col.field] === 'number');
      if (isNumeric) {
        columnTotals[col.field] = data.reduce((sum, row) => sum + (Number(row[col.field]) || 0), 0);
      } else {
        columnTotals[col.field] = null; // Not numeric
      }
    });

    return (
      <div className="table-container" style={{ overflowX: 'auto', borderRadius: '8px', border: '1px solid var(--border-color)', maxHeight: '500px' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '600px' }}>
          <thead style={{ position: 'sticky', top: 0, zIndex: 1, backgroundColor: 'rgba(15, 23, 42, 0.95)', backdropFilter: 'blur(8px)' }}>
            <tr>
              {columns.map((col, idx) => (
                <th key={idx} style={{ padding: '1rem', borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)', fontWeight: '600', fontSize: '0.85rem', textTransform: 'uppercase', verticalAlign: 'top' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    <span>{col.title || col.field}</span>
                    {onColumnFilterChange && (
                      <input 
                        type="text" 
                        placeholder="Filtrar..."
                        className="hide-on-print"
                        value={columnFilters?.[col.field] || ''}
                        onChange={(e) => onColumnFilterChange(col.field, e.target.value)}
                        style={{ 
                          background: 'rgba(0,0,0,0.2)', 
                          border: '1px solid var(--glass-border)', 
                          color: 'var(--text-light)', 
                          padding: '0.4rem 0.6rem', 
                          borderRadius: '6px',
                          fontSize: '0.8rem',
                          outline: 'none',
                          width: '100%',
                          fontWeight: 'normal',
                          transition: 'border-color 0.2s'
                        }}
                        onFocus={(e) => e.target.style.borderColor = 'var(--primary)'}
                        onBlur={(e) => e.target.style.borderColor = 'var(--glass-border)'}
                      />
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, rowIdx) => (
              <tr key={rowIdx} style={{ borderBottom: '1px solid var(--border-color)', transition: 'background 0.2s', ':hover': { backgroundColor: 'rgba(255,255,255,0.02)' } }}>
                {columns.map((col, colIdx) => (
                  <td key={colIdx} style={{ padding: '1rem', color: 'var(--text-light)', fontSize: '0.9rem' }}>
                    {typeof row[col.field] === 'number' ? formatNumber(row[col.field]) : row[col.field]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
          <tfoot style={{ position: 'sticky', bottom: 0, zIndex: 1, backgroundColor: 'rgba(15, 23, 42, 0.95)', backdropFilter: 'blur(8px)' }}>
            <tr>
              {columns.map((col, colIdx) => {
                const total = columnTotals[col.field];
                return (
                  <td key={`total-${colIdx}`} style={{ padding: '1rem', borderTop: '2px solid var(--primary)', color: 'var(--primary)', fontWeight: 'bold', fontSize: '0.95rem' }}>
                    {total !== null ? formatNumber(total) : (colIdx === 0 ? 'TOTALES' : '')}
                  </td>
                )
              })}
            </tr>
          </tfoot>
        </table>
      </div>
    )
  }

  return (
    <div style={{ padding: '2rem', color: '#fca5a5', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '8px' }}>
      Tipo de vista <strong>"{tipoVista}"</strong> no soportada por el motor dinámico.
    </div>
  )
}

export default DynamicRenderer
