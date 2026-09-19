/**
 * useApi.js — TanStack Query hooks para todos los endpoints SADE
 */
import { useQuery } from '@tanstack/react-query'

const API_BASE = '/api'

async function fetchJson(url) {
  const res = await fetch(url)
  if (!res.ok) {
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
  const params = new URLSearchParams();
  const mapped = {
    ...filtros,
    fechaDesde: filtros.fechaDesde || filtros.desde || undefined,
    fechaHasta: filtros.fechaHasta || filtros.hasta || undefined,
  };
  delete mapped.desde;
  delete mapped.hasta;

  Object.entries(mapped).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== '') params.set(k, v);
  });
  const queryString = params.toString();
  return useQuery({
    queryKey: ['clientes', filtros],
    queryFn: () => fetch(`/api/clientes/${queryString ? '?' + queryString : ''}`).then(r => {
      if (!r.ok) throw new Error('Error al cargar clientes');
      return r.json();
    }),
    staleTime: 2 * 60 * 1000,
    retry: 1,
  });
}
