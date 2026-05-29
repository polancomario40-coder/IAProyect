import { useState, useEffect } from 'react';
import api from '../services/api';

interface CuadreRecord {
  orden: number;
  usuario: string;
  idfactura: string | null;
  registro: string;
  numero: string;
  cliente: string;
  fecha: string;
  moneda: string;
  efectivo: number;
  tarjeta: number;
  cheque: number;
  otros: number;
  credito: number;
  factura: number;
  recibos: number;
  gastos: number;
}

interface SucursalDto {
  idSucursal: string;
  sucursal: string;
}

interface CajeroDto {
  usuario: string;
  nombre: string;
}

export default function DashboardView() {
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');
  const [records, setRecords] = useState<CuadreRecord[]>([]);
  const [filteredRecords, setFilteredRecords] = useState<CuadreRecord[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  
  const [sortField, setSortField] = useState<keyof CuadreRecord>('fecha');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [accessDenied, setAccessDenied] = useState(false);
  const [showMobileDetails, setShowMobileDetails] = useState(false);

  const [empresaNombre, setEmpresaNombre] = useState('Empresa');

  // Dropdown states
  const [sucursales, setSucursales] = useState<SucursalDto[]>([]);
  const [cajeros, setCajeros] = useState<CajeroDto[]>([]);
  const [selectedSucursal, setSelectedSucursal] = useState('Todos');
  const [selectedCajero, setSelectedCajero] = useState('Todos');

  // Load session info, load dropdown filters, set default dates
  useEffect(() => {
    const userRaw = localStorage.getItem('usuario');
    if (userRaw) {
      try {
        JSON.parse(userRaw);
        // User parsing kept if needed elsewhere, but state removed
      } catch (e) {}
    }

    const empRaw = localStorage.getItem('empresa');
    if (empRaw) {
      try {
        const emp = JSON.parse(empRaw);
        setEmpresaNombre(emp.empresa || 'Empresa');
      } catch (e) {}
    }

    // Default dates: today in local timezone
    const d = new Date();
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const formattedToday = `${year}-${month}-${day}`;

    setDesde(formattedToday);
    setHasta(formattedToday);

    // Fetch dropdown options on startup
    const loadFiltersData = async () => {
      try {
        const sucResponse = await api.get('/cuadre/sucursales');
        setSucursales(sucResponse.data || []);
      } catch (e) {
        console.error('Error loading sucursales from API', e);
      }

      try {
        const cajResponse = await api.get('/cuadre/cajeros');
        setCajeros(cajResponse.data || []);
      } catch (e) {
        console.error('Error loading cajeros from API', e);
      }
    };

    loadFiltersData();

    // Read stored filters if any
    const lastSuc = localStorage.getItem('last_selected_sucursal') || 'Todos';
    setSelectedSucursal(lastSuc);

    const lastCaj = localStorage.getItem('last_selected_cajero') || 'Todos';
    setSelectedCajero(lastCaj);

    const checkAccess = async () => {
      try {
        const resp = await api.post('/usuario/validar-acceso');
        if (resp.data && resp.data.success === false) {
          setAccessDenied(true);
          setErrorMsg(resp.data.mensaje || 'No tiene permisos para acceder al Cuadre de Caja.');
        }
      } catch (e) {
        console.error('Error validating access', e);
      }
    };

    checkAccess();
  }, []);

  // Filter records based on search term (real-time query box)
  useEffect(() => {
    if (!searchTerm) {
      setFilteredRecords(records);
    } else {
      const search = searchTerm.toLowerCase();
      const filtered = records.filter(
        (r) =>
          (r.cliente?.toLowerCase() || '').includes(search) ||
          (r.numero?.toLowerCase() || '').includes(search) ||
          (r.registro?.toLowerCase() || '').includes(search) ||
          (r.usuario?.toLowerCase() || '').includes(search)
      );
      setFilteredRecords(filtered);
    }
  }, [searchTerm, records]);

  const handleSearch = async (
    desdeVal = desde, 
    hastaVal = hasta, 
    cajeroVal = selectedCajero, 
    sucursalVal = selectedSucursal
  ) => {
    if (!desdeVal || !hastaVal) {
      setErrorMsg('Debe especificar ambas fechas.');
      return;
    }

    setLoading(true);
    setErrorMsg(null);
    try {
      const response = await api.get('/cuadre', {
        params: { 
          desde: desdeVal, 
          hasta: hastaVal,
          usuario: cajeroVal !== 'Todos' ? cajeroVal : undefined,
          sucursal: sucursalVal !== 'Todos' ? sucursalVal : undefined
        }
      });
      setRecords(response.data || []);
    } catch (err: any) {
      console.error('Error fetching cash reconciliation data', err);
      setRecords([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (field: keyof CuadreRecord) => {
    const isAsc = sortField === field && sortDirection === 'asc';
    setSortDirection(isAsc ? 'desc' : 'asc');
    setSortField(field);

    const sorted = [...filteredRecords].sort((a, b) => {
      let valA = a[field];
      let valB = b[field];

      if (typeof valA === 'string' && typeof valB === 'string') {
        return isAsc
          ? valB.localeCompare(valA)
          : valA.localeCompare(valB);
      } else if (valA === null || valB === null) {
        return 0;
      } else {
        return isAsc
          ? (valB as number) - (valA as number)
          : (valA as number) - (valB as number);
      }
    });
    setFilteredRecords(sorted);
  };

  const handleLogout = () => {
    localStorage.removeItem('jwt_token');
    localStorage.removeItem('empresa');
    localStorage.removeItem('usuario');
    // Redirect to Auth Center SSO
    window.location.href = `https://auth.sade.com.do/?client_id=cuadre-caja`;
  };

  // Group division for calculations
  const facturas = filteredRecords.filter(r => r.orden === 1 || r.registro?.toLowerCase() === 'factura');
  const recibos = filteredRecords.filter(r => r.orden === 2 || r.registro?.toLowerCase() === 'recibo');
  const gastos = filteredRecords.filter(r => r.orden === 3 || r.registro?.toLowerCase() === 'gastos');

  const efectivoFacturas = facturas.reduce((acc, curr) => acc + (curr.efectivo || 0), 0);
  const tarjetaFacturas = facturas.reduce((acc, curr) => acc + (curr.tarjeta || 0), 0);
  const chequeFacturas = facturas.reduce((acc, curr) => acc + (curr.cheque || 0), 0);
  const otrosFacturas = facturas.reduce((acc, curr) => acc + (curr.otros || 0), 0);
  const gastosFacturas = facturas.reduce((acc, curr) => acc + (curr.gastos || 0), 0);
  const creditoFacturas = facturas.reduce((acc, curr) => acc + (curr.credito || 0), 0);

  const efectivoRecibos = recibos.reduce((acc, curr) => acc + (curr.efectivo || 0), 0);
  const tarjetaRecibos = recibos.reduce((acc, curr) => acc + (curr.tarjeta || 0), 0);
  const chequeRecibos = recibos.reduce((acc, curr) => acc + (curr.cheque || 0), 0);
  const otrosRecibos = recibos.reduce((acc, curr) => acc + (curr.otros || 0), 0);
  const gastosRecibos = recibos.reduce((acc, curr) => acc + (curr.gastos || 0), 0);
  const creditoRecibos = recibos.reduce((acc, curr) => acc + (curr.credito || 0), 0);

  const efectivoGastos = gastos.reduce((acc, curr) => acc + (curr.efectivo || 0), 0);
  const tarjetaGastos = gastos.reduce((acc, curr) => acc + (curr.tarjeta || 0), 0);
  const chequeGastos = gastos.reduce((acc, curr) => acc + (curr.cheque || 0), 0);
  const otrosGastos = gastos.reduce((acc, curr) => acc + (curr.otros || 0), 0);
  const gastosGastos = gastos.reduce((acc, curr) => acc + (curr.gastos || 0), 0);
  const creditoGastos = gastos.reduce((acc, curr) => acc + (curr.credito || 0), 0);

  const grandEfectivo = efectivoFacturas + efectivoRecibos + efectivoGastos;
  const grandTarjeta = tarjetaFacturas + tarjetaRecibos + tarjetaGastos;
  const grandCheque = chequeFacturas + chequeRecibos + chequeGastos;
  const grandOtros = otrosFacturas + otrosRecibos + otrosGastos;
  const grandGastos = gastosFacturas + gastosRecibos + gastosGastos;
  const grandCredito = creditoFacturas + creditoRecibos + creditoGastos;

  const totalFacturado = efectivoFacturas + tarjetaFacturas + chequeFacturas + otrosFacturas + creditoFacturas;
  const abonos = efectivoRecibos + tarjetaRecibos + chequeRecibos + otrosRecibos;
  const totalDepositar = grandEfectivo - grandGastos;

  // Format currencies
  const fmt = (num: number) => {
    return new Intl.NumberFormat('es-DO', { style: 'currency', currency: 'DOP' }).format(num);
  };

  // Export CSV logic
  const exportToCSV = () => {
    if (filteredRecords.length === 0) return;
    
    const headers = ['Orden', 'Registro', 'Número/Referencia', 'Cliente', 'Fecha', 'Efectivo', 'Tarjeta', 'Cheque', 'Otros', 'Gastos', 'Crédito'];
    const rows = filteredRecords.map((r) => [
      r.orden,
      r.registro,
      r.numero,
      r.cliente,
      r.fecha?.split('T')[0] || '',
      r.efectivo,
      r.tarjeta,
      r.cheque,
      r.otros,
      r.gastos,
      r.credito
    ]);

    const csvContent =
      'data:text/csv;charset=utf-8,\uFEFF' +
      [headers.join(','), ...rows.map((row) => row.join(','))].join('\n');
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `Cuadre_Caja_${desde}_a_${hasta}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="dashboard-container">
      {/* Header Premium */}
      <header className="dashboard-header no-print">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '2.5rem', flexShrink: 0 }}>📊</div>
            <h1 className="header-title" style={{ margin: 0, overflowWrap: 'break-word', wordBreak: 'break-word' }}>
              {empresaNombre}
            </h1>
          </div>

          <button 
            onClick={handleLogout} 
            title="Volver / Cambiar de Empresa"
            style={{ 
              background: 'rgba(255,255,255,0.05)', 
              border: '1px solid rgba(255,255,255,0.1)', 
              fontSize: '1.2rem', 
              cursor: 'pointer',
              width: '36px',
              height: '36px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: '50%',
              transition: 'all 0.2s',
              padding: 0,
              flexShrink: 0,
              marginLeft: '1rem'
            }}
          >
            ⬅️
          </button>

        </div>
      </header>

      {accessDenied ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '50vh', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '16px', padding: '3rem', textAlign: 'center' }}>
          <div style={{ fontSize: '5rem', marginBottom: '1rem' }}>🚫</div>
          <h2 style={{ fontSize: '2rem', fontWeight: 800, color: '#fca5a5', marginBottom: '1rem' }}>Acceso Denegado</h2>
          <p style={{ fontSize: '1.1rem', color: '#e2e8f0', marginBottom: '2rem', maxWidth: '600px' }}>
            {errorMsg || 'Su usuario no pertenece a los grupos autorizados (Administración o Contabilidad) para consultar el Cuadre de Caja.'}
          </p>
          <button className="btn-primary" style={{ maxWidth: '250px' }} onClick={handleLogout}>
            ⬅️ Volver
          </button>
        </div>
      ) : (
        <>
          {/* Filter and KPI Grid */}
          <div className="dashboard-grid no-print">
        {/* Filters Card */}
        <div className="dashboard-card glass-card-dark" style={{ flex: '1 1 300px' }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#60a5fa' }}>
            📅 Filtros de Consulta
          </h2>

          <div style={{ display: 'flex', gap: '1rem', flexDirection: 'column' }}>
            <div style={{ display: 'flex', gap: '1rem' }}>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label" style={{ fontSize: '0.75rem' }}>Desde</label>
                <input
                  type="date"
                  className="form-input"
                  value={desde}
                  onChange={(e) => setDesde(e.target.value)}
                  disabled={loading}
                  style={{ padding: '0.65rem' }}
                />
              </div>

              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label" style={{ fontSize: '0.75rem' }}>Hasta</label>
                <input
                  type="date"
                  className="form-input"
                  value={hasta}
                  onChange={(e) => setHasta(e.target.value)}
                  disabled={loading}
                  style={{ padding: '0.65rem' }}
                />
              </div>
            </div>

            {/* Dynamic Branch/Sucursal Selector */}
            <div className="form-group">
              <label className="form-label" style={{ fontSize: '0.75rem' }}>Sucursal</label>
              <select
                className="form-input"
                value={selectedSucursal}
                onChange={(e) => {
                  const val = e.target.value;
                  setSelectedSucursal(val);
                  localStorage.setItem('last_selected_sucursal', val);
                }}
                disabled={loading}
                style={{ backgroundColor: '#1e293b', color: '#fff', border: '1px solid #475569', cursor: 'pointer' }}
              >
                <option value="Todos">🏢 Todas las Sucursales</option>
                {sucursales.map((suc) => (
                  <option key={suc.idSucursal} value={suc.idSucursal}>
                    {suc.sucursal}
                  </option>
                ))}
              </select>
            </div>

            {/* Dynamic Cashier/Usuario Selector */}
            <div className="form-group" style={{ marginBottom: '1.5rem' }}>
              <label className="form-label" style={{ fontSize: '0.75rem' }}>Cajero / Usuario</label>
              <select
                className="form-input"
                value={selectedCajero}
                onChange={(e) => {
                  const val = e.target.value;
                  setSelectedCajero(val);
                  localStorage.setItem('last_selected_cajero', val);
                }}
                disabled={loading}
                style={{ backgroundColor: '#1e293b', color: '#fff', border: '1px solid #475569', cursor: 'pointer' }}
              >
                <option value="Todos">👤 Todos los Cajeros</option>
                {cajeros.map((caj) => (
                  <option key={caj.usuario} value={caj.usuario}>
                    {caj.nombre} ({caj.usuario})
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <button
                onClick={() => handleSearch(desde, hasta, selectedCajero, selectedSucursal)}
                className="btn-primary"
                disabled={loading}
                style={{ padding: '0.85rem' }}
              >
                {loading ? <span className="spinner"></span> : '🔎 Consultar Cuadre'}
              </button>
              
              <button 
                className="btn-primary" 
                onClick={() => window.print()} 
                disabled={filteredRecords.length === 0} 
                style={{ padding: '0.85rem', background: 'linear-gradient(135deg, #4b5563 0%, #374151 100%)' }}
              >
                🖨️ Imprimir Cuadre
              </button>
            </div>
          </div>
        </div>

        {/* KPIs blocks (7 blocks layout) */}
        <div className="kpis-section" style={{ flex: '3 1 600px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.8rem' }}>
          
          <div className="kpi-card glass-card-dark" style={{ background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(37, 99, 235, 0.05) 100%)', border: '1px solid rgba(59, 130, 246, 0.2)' }}>
            <div className="kpi-value" style={{ color: '#60a5fa' }} title={fmt(totalFacturado)}>{fmt(totalFacturado)}</div>
            <div className="kpi-label" style={{ fontWeight: 800 }}>🛒 Total Ventas</div>
          </div>

          <div className="kpi-card glass-card-dark">
            <div className="kpi-value" title={fmt(grandEfectivo)}>{fmt(grandEfectivo)}</div>
            <div className="kpi-label">💵 Efectivo Bruto</div>
          </div>
          
          <div className="kpi-card glass-card-dark">
            <div className="kpi-value" style={{ color: '#60a5fa' }} title={fmt(grandTarjeta)}>{fmt(grandTarjeta)}</div>
            <div className="kpi-label">💳 Tarjetas</div>
          </div>

          <div className="kpi-card glass-card-dark">
            <div className="kpi-value" style={{ color: '#a78bfa' }} title={fmt(grandOtros)}>{fmt(grandOtros)}</div>
            <div className="kpi-label">🧩 Otros Ingresos</div>
          </div>

          <div className="kpi-card glass-card-dark">
            <div className="kpi-value" style={{ color: '#f59e0b' }} title={fmt(grandCredito)}>{fmt(grandCredito)}</div>
            <div className="kpi-label">⏳ Ventas Crédito</div>
          </div>

          <div className="kpi-card glass-card-dark">
            <div className="kpi-value" style={{ color: '#f87171' }} title={fmt(grandGastos)}>{fmt(grandGastos)}</div>
            <div className="kpi-label">💸 Gastos Menores</div>
          </div>

          <div className="kpi-card glass-card-dark" style={{ background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(5, 150, 105, 0.05) 100%)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
            <div className="kpi-value" style={{ color: '#10b981' }} title={fmt(totalDepositar)}>{fmt(totalDepositar)}</div>
            <div className="kpi-label" style={{ fontWeight: 800 }}>💰 Neto a Depositar</div>
          </div>
        </div>
      </div>

      {/* Warning/Alert if showing mock data */}
      {errorMsg && (
        <div className="alert alert-danger no-print" style={{ margin: '1.5rem 0' }}>
          ⚠️ {errorMsg}
        </div>
      )}

      {/* Mobile Toggle Details Button */}
      <div className="mobile-only-btn-wrapper no-print">
        <button 
          className="btn-primary" 
          onClick={() => setShowMobileDetails(!showMobileDetails)}
          style={{ width: '100%', padding: '1rem', marginTop: '1.5rem', background: 'linear-gradient(135deg, #4f46e5 0%, #3b82f6 100%)' }}
        >
          {showMobileDetails ? '🙈 Ocultar Detalle de Ventas' : '📋 Ver Detalle de Ventas'}
        </button>
      </div>

      {/* Main Interactive Table section */}
      <div className={`dashboard-card glass-card-dark no-print ${!showMobileDetails ? 'hide-on-mobile' : ''}`} style={{ marginTop: '2rem', padding: '2rem' }}>
        <div className="table-actions no-print">
          <h2 style={{ fontSize: '1.35rem', fontWeight: 700 }}>📋 Detalle General de Ventas</h2>
          
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
            {/* Realtime filter input */}
            <input
              type="text"
              className="form-input search-input"
              placeholder="🔍 Buscar por Cliente, Factura, Cajero..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />

            <button className="btn-secondary" onClick={exportToCSV} disabled={filteredRecords.length === 0} style={{ width: 'auto', margin: 0, padding: '0.75rem 1.25rem' }}>
              📥 Exportar Excel
            </button>
          </div>
        </div>

        {/* Responsive Table Wrapper */}
        <div className="table-container">
          <table className="interactive-table">
            <thead>
              <tr style={{ background: 'rgba(15, 23, 42, 0.4)' }}>
                <th onClick={() => handleSort('registro')}>Registro {sortField === 'registro' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
                <th onClick={() => handleSort('cliente')}>Cliente {sortField === 'cliente' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
                <th onClick={() => handleSort('fecha')}>Fecha {sortField === 'fecha' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
                <th onClick={() => handleSort('efectivo')} style={{ textAlign: 'right' }}>Efectivo</th>
                <th onClick={() => handleSort('tarjeta')} style={{ textAlign: 'right' }}>Tarjeta</th>
                <th onClick={() => handleSort('cheque')} style={{ textAlign: 'right' }}>Cheque</th>
                <th onClick={() => handleSort('otros')} style={{ textAlign: 'right' }}>Otros</th>
                <th onClick={() => handleSort('gastos')} style={{ textAlign: 'right' }}>Gastos</th>
                <th onClick={() => handleSort('credito')} style={{ textAlign: 'right' }}>Crédito</th>
              </tr>
            </thead>
            <tbody>
              {/* === GRUPO 1: FACTURAS === */}
              {facturas.length > 0 && (
                <>
                  <tr className="group-title-row">
                    <td colSpan={9} style={{ background: 'rgba(59, 130, 246, 0.15)', fontWeight: 800, color: '#60a5fa', fontSize: '1rem', textAlign: 'left', padding: '0.75rem 1rem', borderLeft: '4px solid #3b82f6' }}>
                      🧾 Facturas
                    </td>
                  </tr>
                  {facturas.map((r, i) => (
                    <tr key={`fac-${i}`}>
                      <td data-label="Registro" style={{ fontWeight: 600 }}>{r.registro} &nbsp;&nbsp;&nbsp; {r.numero}</td>
                      <td data-label="Cliente" style={{ maxWidth: '240px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.cliente}</td>
                      <td data-label="Fecha">{r.fecha ? new Date(r.fecha).toLocaleDateString('es-DO') : ''}</td>
                      <td data-label="Efectivo" style={{ textAlign: 'right' }}>{fmt(r.efectivo || 0)}</td>
                      <td data-label="Tarjeta" style={{ textAlign: 'right', color: '#93c5fd' }}>{fmt(r.tarjeta || 0)}</td>
                      <td data-label="Cheque" style={{ textAlign: 'right' }}>{fmt(r.cheque || 0)}</td>
                      <td data-label="Otros" style={{ textAlign: 'right' }}>{fmt(r.otros || 0)}</td>
                      <td data-label="Gastos" style={{ textAlign: 'right' }}>{fmt(r.gastos || 0)}</td>
                      <td data-label="Crédito" style={{ textAlign: 'right', color: '#fcd34d' }}>{fmt(r.credito || 0)}</td>
                    </tr>
                  ))}
                  <tr className="group-subtotal-row" style={{ background: 'rgba(255, 255, 255, 0.02)', fontWeight: 700 }}>
                    <td colSpan={3} style={{ textAlign: 'right', color: '#94a3b8', fontStyle: 'italic' }}>Subtotal Facturas</td>
                    <td style={{ textAlign: 'right' }}>{fmt(efectivoFacturas)}</td>
                    <td style={{ textAlign: 'right', color: '#93c5fd' }}>{fmt(tarjetaFacturas)}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(chequeFacturas)}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(otrosFacturas)}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(gastosFacturas)}</td>
                    <td style={{ textAlign: 'right', color: '#fcd34d' }}>{fmt(creditoFacturas)}</td>
                  </tr>
                </>
              )}

              {/* === GRUPO 2: RECIBOS === */}
              {recibos.length > 0 && (
                <>
                  <tr className="group-title-row" style={{ marginTop: '1rem' }}>
                    <td colSpan={9} style={{ background: 'rgba(16, 185, 129, 0.15)', fontWeight: 800, color: '#34d399', fontSize: '1rem', textAlign: 'left', padding: '0.75rem 1rem', borderLeft: '4px solid #10b981' }}>
                      📝 Recibos / Abonos
                    </td>
                  </tr>
                  {recibos.map((r, i) => (
                    <tr key={`rec-${i}`}>
                      <td data-label="Registro" style={{ fontWeight: 600 }}>{r.registro} &nbsp;&nbsp;&nbsp; {r.numero}</td>
                      <td data-label="Cliente" style={{ maxWidth: '240px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.cliente}</td>
                      <td data-label="Fecha">{r.fecha ? new Date(r.fecha).toLocaleDateString('es-DO') : ''}</td>
                      <td data-label="Efectivo" style={{ textAlign: 'right' }}>{fmt(r.efectivo || 0)}</td>
                      <td data-label="Tarjeta" style={{ textAlign: 'right', color: '#93c5fd' }}>{fmt(r.tarjeta || 0)}</td>
                      <td data-label="Cheque" style={{ textAlign: 'right' }}>{fmt(r.cheque || 0)}</td>
                      <td data-label="Otros" style={{ textAlign: 'right' }}>{fmt(r.otros || 0)}</td>
                      <td data-label="Gastos" style={{ textAlign: 'right' }}>{fmt(r.gastos || 0)}</td>
                      <td data-label="Crédito" style={{ textAlign: 'right', color: '#fcd34d' }}>{fmt(r.credito || 0)}</td>
                    </tr>
                  ))}
                  <tr className="group-subtotal-row" style={{ background: 'rgba(255, 255, 255, 0.02)', fontWeight: 700 }}>
                    <td colSpan={3} style={{ textAlign: 'right', color: '#94a3b8', fontStyle: 'italic' }}>Subtotal Recibos</td>
                    <td style={{ textAlign: 'right' }}>{fmt(efectivoRecibos)}</td>
                    <td style={{ textAlign: 'right', color: '#93c5fd' }}>{fmt(tarjetaRecibos)}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(chequeRecibos)}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(otrosRecibos)}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(gastosRecibos)}</td>
                    <td style={{ textAlign: 'right', color: '#fcd34d' }}>{fmt(creditoRecibos)}</td>
                  </tr>
                </>
              )}

              {/* === GRUPO 3: GASTOS === */}
              {gastos.length > 0 && (
                <>
                  <tr className="group-title-row" style={{ marginTop: '1rem' }}>
                    <td colSpan={9} style={{ background: 'rgba(239, 68, 68, 0.15)', fontWeight: 800, color: '#f87171', fontSize: '1rem', textAlign: 'left', padding: '0.75rem 1rem', borderLeft: '4px solid #ef4444' }}>
                      💸 Gastos Menores
                    </td>
                  </tr>
                  {gastos.map((r, i) => (
                    <tr key={`gas-${i}`}>
                      <td data-label="Registro" style={{ fontWeight: 600 }}>{r.registro}</td>
                      <td data-label="Cliente" style={{ maxWidth: '240px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.numero ? `${r.numero} ` : ''}{r.cliente}</td>
                      <td data-label="Fecha">{r.fecha ? new Date(r.fecha).toLocaleDateString('es-DO') : ''}</td>
                      <td data-label="Efectivo" style={{ textAlign: 'right' }}>{fmt(r.efectivo || 0)}</td>
                      <td data-label="Tarjeta" style={{ textAlign: 'right', color: '#93c5fd' }}>{fmt(r.tarjeta || 0)}</td>
                      <td data-label="Cheque" style={{ textAlign: 'right' }}>{fmt(r.cheque || 0)}</td>
                      <td data-label="Otros" style={{ textAlign: 'right' }}>{fmt(r.otros || 0)}</td>
                      <td data-label="Gastos" style={{ textAlign: 'right', color: '#f87171' }}>{fmt(r.gastos || 0)}</td>
                      <td data-label="Crédito" style={{ textAlign: 'right', color: '#fcd34d' }}>{fmt(r.credito || 0)}</td>
                    </tr>
                  ))}
                  <tr className="group-subtotal-row" style={{ background: 'rgba(255, 255, 255, 0.02)', fontWeight: 700 }}>
                    <td colSpan={3} style={{ textAlign: 'right', color: '#94a3b8', fontStyle: 'italic' }}>Subtotal Gastos</td>
                    <td style={{ textAlign: 'right' }}>{fmt(efectivoGastos)}</td>
                    <td style={{ textAlign: 'right', color: '#93c5fd' }}>{fmt(tarjetaGastos)}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(chequeGastos)}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(otrosGastos)}</td>
                    <td style={{ textAlign: 'right', color: '#f87171' }}>{fmt(gastosGastos)}</td>
                    <td style={{ textAlign: 'right', color: '#fcd34d' }}>{fmt(creditoGastos)}</td>
                  </tr>
                </>
              )}

              {filteredRecords.length === 0 && (
                <tr>
                  <td colSpan={9} style={{ textAlign: 'center', padding: '3rem', color: '#94a3b8' }}>
                    No se encontraron registros de cuadre para el rango y filtro seleccionados.
                  </td>
                </tr>
              )}
            </tbody>
            {filteredRecords.length > 0 && (
              <tfoot>
                <tr style={{ background: 'rgba(255,255,255,0.06)', fontWeight: 800, borderTop: '2px solid rgba(255,255,255,0.2)' }}>
                  <td colSpan={3} data-label="Concepto" style={{ fontSize: '1rem', letterSpacing: '0.05em' }}>TOTALES GENERALES (RD$)</td>
                  <td data-label="Total Efectivo" style={{ textAlign: 'right' }}>{fmt(grandEfectivo)}</td>
                  <td data-label="Total Tarjeta" style={{ textAlign: 'right', color: '#60a5fa' }}>{fmt(grandTarjeta)}</td>
                  <td data-label="Total Cheque" style={{ textAlign: 'right' }}>{fmt(grandCheque)}</td>
                  <td data-label="Total Otros" style={{ textAlign: 'right' }}>{fmt(grandOtros)}</td>
                  <td data-label="Total Gastos" style={{ textAlign: 'right', color: '#f87171' }}>{fmt(grandGastos)}</td>
                  <td data-label="Total Crédito" style={{ textAlign: 'right', color: '#f59e0b' }}>{fmt(grandCredito)}</td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>

        {/* Dashboard visual summary block */}
        {filteredRecords.length > 0 && (
          <div style={{ display: 'flex', gap: '2rem', marginTop: '2rem', flexWrap: 'wrap', justifyContent: 'flex-start' }}>
            <div className="glass-card-dark" style={{ flex: '1 1 380px', padding: '1.75rem', borderRadius: '16px', border: '1px solid rgba(255,255,255,0.08)', boxShadow: '0 8px 32px rgba(0,0,0,0.3)' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 800, marginBottom: '1.25rem', color: '#60a5fa', textTransform: 'uppercase', letterSpacing: '0.06em', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '0.5rem' }}>
                Resumen del Proceso de Cuadre
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', fontSize: '0.95rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: '0.5rem' }}>
                  <span style={{ fontWeight: 600, color: '#94a3b8' }}>Total Facturado:</span>
                  <span style={{ fontWeight: 700 }}>{fmt(totalFacturado)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: '0.5rem' }}>
                  <span style={{ fontWeight: 600, color: '#94a3b8' }}>Abonos (Recibos):</span>
                  <span style={{ fontWeight: 700 }}>{fmt(abonos)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: '0.5rem' }}>
                  <span style={{ fontWeight: 500, color: '#94a3b8' }}>Tarjeta:</span>
                  <span style={{ fontWeight: 600, color: '#60a5fa' }}>{fmt(grandTarjeta)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: '0.5rem' }}>
                  <span style={{ fontWeight: 500, color: '#94a3b8' }}>Otros:</span>
                  <span style={{ fontWeight: 600 }}>{fmt(grandOtros)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: '0.5rem' }}>
                  <span style={{ fontWeight: 500, color: '#94a3b8' }}>Créditos Otorgados:</span>
                  <span style={{ fontWeight: 600, color: '#fcd34d' }}>{fmt(grandCredito)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.04)', paddingBottom: '0.5rem' }}>
                  <span style={{ fontWeight: 500, color: '#94a3b8' }}>Gastos Menores:</span>
                  <span style={{ fontWeight: 600, color: '#f87171' }}>{fmt(grandGastos)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', background: 'rgba(16, 185, 129, 0.08)', padding: '0.85rem', borderRadius: '10px', border: '1.5px solid rgba(16, 185, 129, 0.3)', marginTop: '0.5rem' }}>
                  <span style={{ fontWeight: 800, color: '#10b981' }}>Total Neto a Depositar:</span>
                  <span style={{ fontWeight: 800, color: '#10b981', fontSize: '1.15rem' }}>{fmt(totalDepositar)}</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
      </>
      )}

      {/* Printed version elements: Styled to EXACTLY match the uploaded image report */}
      <div className="print-only" style={{ color: '#000', fontFamily: 'system-ui, -apple-system, sans-serif', width: '100%', padding: '10px 0' }}>
        
        {/* Header Section */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', width: '100%' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '2.4rem', fontWeight: 800, color: '#1e3a8a' }}>
              {empresaNombre || 'Higüey'}
            </h1>
            <p style={{ margin: '3px 0 0 0', fontSize: '1.4rem', fontStyle: 'italic', fontWeight: 600, color: '#1e3a8a' }}>
              Cuadre de caja
            </p>
          </div>
          <div style={{ textAlign: 'right', fontSize: '12px', color: '#000', fontWeight: 500 }}>
            <div>{new Date().toLocaleDateString('es-DO')} {new Date().toLocaleTimeString('es-DO', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true })}</div>
            <div style={{ marginTop: '4px' }}>Page 1 of 1</div>
          </div>
        </div>

        {/* Thick blue horizontal separator rule */}
        <div style={{ borderBottom: '2.5px solid #1e3a8a', marginTop: '10px', marginBottom: '15px', width: '100%' }}></div>
        
        <div style={{ fontSize: '12px', fontWeight: 700, marginBottom: '8px' }}>RD$</div>

        {/* 1. FACTURAS PRINT TABLE */}
        {facturas.length > 0 && (
          <div style={{ marginBottom: '20px' }}>
            <h3 style={{ margin: '0 0 4px 0', fontSize: '13px', fontWeight: 800, color: '#1e3a8a' }}>Factura</h3>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '10.5px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #1e3a8a', borderTop: '1px solid #1e3a8a', textAlign: 'left', fontWeight: 'bold' }}>
                  <th style={{ padding: '4px 0', width: '18%' }}>Registro</th>
                  <th style={{ width: '34%' }}>Cliente</th>
                  <th style={{ width: '12%' }}>Fecha</th>
                  <th style={{ textAlign: 'right', width: '9%' }}>Efectivo</th>
                  <th style={{ textAlign: 'right', width: '9%' }}>Tarjeta</th>
                  <th style={{ textAlign: 'right', width: '9%' }}>Cheque</th>
                  <th style={{ textAlign: 'right', width: '9%' }}>Otros</th>
                  <th style={{ textAlign: 'right', width: '9%' }}>Gastos</th>
                  <th style={{ textAlign: 'right', width: '9%' }}>Credito</th>
                </tr>
              </thead>
              <tbody>
                {facturas.map((r, i) => (
                  <tr key={`print-fac-${i}`} style={{ borderBottom: '0.5px solid #cbd5e1' }}>
                    <td style={{ padding: '4px 0' }}>{r.registro} &nbsp;&nbsp;&nbsp; {r.numero}</td>
                    <td>{r.cliente}</td>
                    <td>{r.fecha ? new Date(r.fecha).toLocaleDateString('es-DO') : ''}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(r.efectivo || 0).replace('RD$', '').trim()}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(r.tarjeta || 0).replace('RD$', '').trim()}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(r.cheque || 0).replace('RD$', '').trim()}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(r.otros || 0).replace('RD$', '').trim()}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(r.gastos || 0).replace('RD$', '').trim()}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(r.credito || 0).replace('RD$', '').trim()}</td>
                  </tr>
                ))}
                <tr style={{ fontWeight: 'bold', borderTop: '1px solid #000', borderBottom: '1px solid #000', background: '#f1f5f9' }}>
                  <td colSpan={3} style={{ padding: '5px 0', textAlign: 'right', paddingRight: '15px' }}>Subtotal Factura:</td>
                  <td style={{ textAlign: 'right' }}>{fmt(efectivoFacturas).replace('RD$', '').trim()}</td>
                  <td style={{ textAlign: 'right' }}>{fmt(tarjetaFacturas).replace('RD$', '').trim()}</td>
                  <td style={{ textAlign: 'right' }}>{fmt(chequeFacturas).replace('RD$', '').trim()}</td>
                  <td style={{ textAlign: 'right' }}>{fmt(otrosFacturas).replace('RD$', '').trim()}</td>
                  <td style={{ textAlign: 'right' }}>{fmt(gastosFacturas).replace('RD$', '').trim()}</td>
                  <td style={{ textAlign: 'right' }}>{fmt(creditoFacturas).replace('RD$', '').trim()}</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}

        {/* 2. RECIBOS PRINT TABLE */}
        {recibos.length > 0 && (
          <div style={{ marginBottom: '20px' }}>
            <h3 style={{ margin: '0 0 4px 0', fontSize: '13px', fontWeight: 800, color: '#1e3a8a' }}>Recibo</h3>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '10.5px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #1e3a8a', borderTop: '1px solid #1e3a8a', textAlign: 'left', fontWeight: 'bold' }}>
                  <th style={{ padding: '4px 0', width: '18%' }}>Registro</th>
                  <th style={{ width: '34%' }}>Cliente</th>
                  <th style={{ width: '12%' }}>Fecha</th>
                  <th style={{ textAlign: 'right', width: '9%' }}>Efectivo</th>
                  <th style={{ textAlign: 'right', width: '9%' }}>Tarjeta</th>
                  <th style={{ textAlign: 'right', width: '9%' }}>Cheque</th>
                  <th style={{ textAlign: 'right', width: '9%' }}>Otros</th>
                  <th style={{ textAlign: 'right', width: '9%' }}>Gastos</th>
                  <th style={{ textAlign: 'right', width: '9%' }}>Credito</th>
                </tr>
              </thead>
              <tbody>
                {recibos.map((r, i) => (
                  <tr key={`print-rec-${i}`} style={{ borderBottom: '0.5px solid #cbd5e1' }}>
                    <td style={{ padding: '4px 0' }}>{r.registro} &nbsp;&nbsp;&nbsp; {r.numero}</td>
                    <td>{r.cliente}</td>
                    <td>{r.fecha ? new Date(r.fecha).toLocaleDateString('es-DO') : ''}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(r.efectivo || 0).replace('RD$', '').trim()}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(r.tarjeta || 0).replace('RD$', '').trim()}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(r.cheque || 0).replace('RD$', '').trim()}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(r.otros || 0).replace('RD$', '').trim()}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(r.gastos || 0).replace('RD$', '').trim()}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(r.credito || 0).replace('RD$', '').trim()}</td>
                  </tr>
                ))}
                <tr style={{ fontWeight: 'bold', borderTop: '1px solid #000', borderBottom: '1px solid #000', background: '#f1f5f9' }}>
                  <td colSpan={3} style={{ padding: '5px 0', textAlign: 'right', paddingRight: '15px' }}>Subtotal Recibo:</td>
                  <td style={{ textAlign: 'right' }}>{fmt(efectivoRecibos).replace('RD$', '').trim()}</td>
                  <td style={{ textAlign: 'right' }}>{fmt(tarjetaRecibos).replace('RD$', '').trim()}</td>
                  <td style={{ textAlign: 'right' }}>{fmt(chequeRecibos).replace('RD$', '').trim()}</td>
                  <td style={{ textAlign: 'right' }}>{fmt(otrosRecibos).replace('RD$', '').trim()}</td>
                  <td style={{ textAlign: 'right' }}>{fmt(gastosRecibos).replace('RD$', '').trim()}</td>
                  <td style={{ textAlign: 'right' }}>{fmt(creditoRecibos).replace('RD$', '').trim()}</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}

        {/* 3. GASTOS PRINT TABLE */}
        {gastos.length > 0 && (
          <div style={{ marginBottom: '20px' }}>
            <h3 style={{ margin: '0 0 4px 0', fontSize: '13px', fontWeight: 800, color: '#1e3a8a' }}>Gastos</h3>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '10.5px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #1e3a8a', borderTop: '1px solid #1e3a8a', textAlign: 'left', fontWeight: 'bold' }}>
                  <th style={{ padding: '4px 0', width: '18%' }}>Registro</th>
                  <th style={{ width: '34%' }}>Cliente</th>
                  <th style={{ width: '12%' }}>Fecha</th>
                  <th style={{ textAlign: 'right', width: '9%' }}>Efectivo</th>
                  <th style={{ textAlign: 'right', width: '9%' }}>Tarjeta</th>
                  <th style={{ textAlign: 'right', width: '9%' }}>Cheque</th>
                  <th style={{ textAlign: 'right', width: '9%' }}>Otros</th>
                  <th style={{ textAlign: 'right', width: '9%' }}>Gastos</th>
                  <th style={{ textAlign: 'right', width: '9%' }}>Credito</th>
                </tr>
              </thead>
              <tbody>
                {gastos.map((r, i) => (
                  <tr key={`print-gas-${i}`} style={{ borderBottom: '0.5px solid #cbd5e1' }}>
                    <td style={{ padding: '4px 0' }}>{r.registro}</td>
                    <td>{r.numero ? `${r.numero} ` : ''}{r.cliente}</td>
                    <td>{r.fecha ? new Date(r.fecha).toLocaleDateString('es-DO') : ''}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(r.efectivo || 0).replace('RD$', '').trim()}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(r.tarjeta || 0).replace('RD$', '').trim()}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(r.cheque || 0).replace('RD$', '').trim()}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(r.otros || 0).replace('RD$', '').trim()}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(r.gastos || 0).replace('RD$', '').trim()}</td>
                    <td style={{ textAlign: 'right' }}>{fmt(r.credito || 0).replace('RD$', '').trim()}</td>
                  </tr>
                ))}
                <tr style={{ fontWeight: 'bold', borderTop: '1px solid #000', borderBottom: '1px solid #000', background: '#f1f5f9' }}>
                  <td colSpan={3} style={{ padding: '5px 0', textAlign: 'right', paddingRight: '15px' }}>Subtotal Gastos:</td>
                  <td style={{ textAlign: 'right' }}>{fmt(efectivoGastos).replace('RD$', '').trim()}</td>
                  <td style={{ textAlign: 'right' }}>{fmt(tarjetaGastos).replace('RD$', '').trim()}</td>
                  <td style={{ textAlign: 'right' }}>{fmt(chequeGastos).replace('RD$', '').trim()}</td>
                  <td style={{ textAlign: 'right' }}>{fmt(otrosGastos).replace('RD$', '').trim()}</td>
                  <td style={{ textAlign: 'right' }}>{fmt(gastosGastos).replace('RD$', '').trim()}</td>
                  <td style={{ textAlign: 'right' }}>{fmt(creditoGastos).replace('RD$', '').trim()}</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}

        {/* Grand Totals Rule & Detailed Summary Box exactly as image */}
        <div style={{ marginTop: '15px', width: '100%' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px', fontWeight: 'bold', marginBottom: '15px' }}>
            <tbody>
              <tr style={{ borderTop: '1.5px solid #000', borderBottom: '2.5px double #000' }}>
                <td style={{ padding: '6px 0', width: '64%' }}>TOTALES</td>
                <td style={{ textAlign: 'right', width: '9%' }}>{fmt(grandEfectivo).replace('RD$', '').trim()}</td>
                <td style={{ textAlign: 'right', width: '9%' }}>{fmt(grandTarjeta).replace('RD$', '').trim()}</td>
                <td style={{ textAlign: 'right', width: '9%' }}>{fmt(grandCheque).replace('RD$', '').trim()}</td>
                <td style={{ textAlign: 'right', width: '9%' }}>{fmt(grandOtros).replace('RD$', '').trim()}</td>
                <td style={{ textAlign: 'right', width: '9%' }}>{fmt(grandGastos).replace('RD$', '').trim()}</td>
                <td style={{ textAlign: 'right', width: '9%' }}>{fmt(grandCredito).replace('RD$', '').trim()}</td>
              </tr>
            </tbody>
          </table>

          {/* Left Summary Box exact reproduction */}
          <div style={{ width: '360px', marginTop: '10px', fontSize: '11.5px', color: '#000' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
              <span style={{ fontWeight: 800 }}>Total Facturado:</span>
              <span style={{ fontWeight: 800, width: '120px', textAlign: 'right' }}>{fmt(totalFacturado).replace('RD$', '').trim()}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
              <span style={{ fontWeight: 800 }}>Abonos:</span>
              <span style={{ fontWeight: 800, width: '120px', textAlign: 'right' }}>{fmt(abonos).replace('RD$', '').trim()}</span>
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', marginTop: '5px' }}>
              <span style={{ fontWeight: 700 }}>Tarjeta :</span>
              <span style={{ fontWeight: 700, width: '120px', textAlign: 'right' }}>{fmt(grandTarjeta).replace('RD$', '').trim()}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
              <span style={{ fontWeight: 700 }}>Otros :</span>
              <span style={{ fontWeight: 700, width: '120px', textAlign: 'right' }}>{fmt(grandOtros).replace('RD$', '').trim()}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
              <span style={{ fontWeight: 700 }}>Creditos:</span>
              <span style={{ fontWeight: 700, width: '120px', textAlign: 'right' }}>{fmt(grandCredito).replace('RD$', '').trim()}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
              <span style={{ fontWeight: 700 }}>Gastos Menores:</span>
              <span style={{ fontWeight: 700, width: '120px', textAlign: 'right' }}>{fmt(grandGastos).replace('RD$', '').trim()}</span>
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderTop: '1.5px solid #000', marginTop: '4px' }}>
              <span style={{ fontWeight: 800 }}>Total a depositar:</span>
              <span style={{ fontWeight: 800, width: '120px', textAlign: 'right' }}>{fmt(totalDepositar).replace('RD$', '').trim()}</span>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
