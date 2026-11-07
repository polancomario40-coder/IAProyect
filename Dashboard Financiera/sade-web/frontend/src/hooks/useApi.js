/**
 * useApi.js — TanStack Query hooks para todos los endpoints SADE
 */
import { useQuery } from '@tanstack/react-query'

const API_BASE = '/api'

function getAuthHeaders() {
  const headers = {}
  const token = localStorage.getItem('jwt_token')
  if (token) headers['Authorization'] = `Bearer ${token}`
  const empresaStr = localStorage.getItem('empresa')
  if (empresaStr) {
    try {
      const emp = JSON.parse(empresaStr)
      if (emp.idEmpresa) headers['X-Selected-Company'] = emp.idEmpresa
    } catch {}
  }
  return headers
}

async function fetchJson(url, options = {}) {
  const headers = { ...getAuthHeaders(), ...(options.headers || {}) }
  const res = await fetch(url, { ...options, headers })
  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem('jwt_token')
      localStorage.removeItem('empresa')
      if (window.location.pathname !== '/auth-callback') {
        const callbackUrl = encodeURIComponent(window.location.origin + '/auth-callback')
        const authUrl = import.meta.env.VITE_AUTH_CENTER_URL || 'https://auth.sade.com.do'
        window.location.href = `${authUrl}/?client_id=sade-financiera&redirect_uri=${callbackUrl}`
      }
    }
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `Error ${res.status}`)
  }
  return res.json()
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

export function useDashboardKPIs() {
  return useQuery({
    queryKey: ['dashboard', 'kpis'],
    queryFn: () => fetchJson(`${API_BASE}/dashboard/kpis`),
  })
}

export function useCobrosporMes(meses = 12) {
  return useQuery({
    queryKey: ['dashboard', 'cobros-por-mes', meses],
    queryFn: () => fetchJson(`${API_BASE}/dashboard/cobros-por-mes?meses=${meses}`),
  })
}

// ─── Préstamos ────────────────────────────────────────────────────────────────

export function useEstadoPrestamo(idCxc) {
  return useQuery({
    queryKey: ['prestamos', idCxc],
    queryFn: () => fetchJson(`${API_BASE}/prestamos/${idCxc}`),
    enabled: !!idCxc,
  })
}

// ─── Clientes ─────────────────────────────────────────────────────────────────

export function useClientes(filtros = {}) {
  const params = new URLSearchParams()
  const mapped = {
    ...filtros,
    fechaDesde: filtros.fechaDesde || filtros.desde || undefined,
    fechaHasta: filtros.fechaHasta || filtros.hasta || undefined,
  }
  delete mapped.desde
  delete mapped.hasta

  Object.entries(mapped).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== '') params.set(k, v)
  })
  const queryString = params.toString()
  return useQuery({
    queryKey: ['clientes', filtros],
    queryFn: () => fetchJson(`${API_BASE}/clientes/${queryString ? '?' + queryString : ''}`),
    staleTime: 2 * 60 * 1000,
    retry: 1,
  })
}

// ─── Historial del Cliente ───────────────────────────────────────────────────

export function useHistorialCliente(idCliente) {
  return useQuery({
    queryKey: ['cliente', 'historial', idCliente],
    queryFn: () => fetchJson(`${API_BASE}/clientes/${idCliente}/historial`),
    enabled: !!idCliente,
    staleTime: 2 * 60 * 1000,
  })
}

// ─── Reportes Analíticos Oficiales ──────────────────────────────────────────

export function useReporteDetalleClientes(filtros = {}, options = {}) {
  const params = new URLSearchParams()
  Object.entries(filtros).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== '') params.set(k, v)
  })
  const queryString = params.toString()
  return useQuery({
    queryKey: ['reportes', 'detalle-clientes', filtros],
    queryFn: () => fetchJson(`${API_BASE}/reportes/detalle-clientes${queryString ? '?' + queryString : ''}`),
    staleTime: 60 * 1000,
    ...options,
  })
}

export function useReporteConsolidadoCartera(filtros = {}, options = {}) {
  const params = new URLSearchParams()
  Object.entries(filtros).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== '') params.set(k, v)
  })
  const queryString = params.toString()
  return useQuery({
    queryKey: ['reportes', 'consolidado-cartera', filtros],
    queryFn: () => fetchJson(`${API_BASE}/reportes/consolidado-cartera${queryString ? '?' + queryString : ''}`),
    staleTime: 60 * 1000,
    ...options,
  })
}

export function useReporteClientesAtrasados(filtros = {}, options = {}) {
  const params = new URLSearchParams()
  Object.entries(filtros).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== '') params.set(k, v)
  })
  const queryString = params.toString()
  return useQuery({
    queryKey: ['reportes', 'clientes-atrasados', filtros],
    queryFn: () => fetchJson(`${API_BASE}/reportes/clientes-atrasados${queryString ? '?' + queryString : ''}`),
    staleTime: 60 * 1000,
    ...options,
  })
}


