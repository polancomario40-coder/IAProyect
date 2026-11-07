"""
clientes.py — Router para inteligencia de cartera e historial de clientes
"""
from datetime import date
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from database import execute_sp_multi
from models.schemas import (
    ClientesResponse,
    ClientesStats,
    ClienteResumen,
    EmpresaDistribucion,
    ClienteHistorialResponse,
    ClienteDetalle,
    PrestamoHistoricoItem,
)

router = APIRouter(prefix="/api/clientes", tags=["Clientes"])


@router.get(
    "/",
    response_model=ClientesResponse,
    summary="Listado inteligente y filtrado de cartera de clientes",
)
async def get_clientes(
    fechaDesde: Optional[date] = Query(default=None),
    fechaHasta: Optional[date] = Query(default=None),
    empresa: Optional[str] = Query(default=None),
    estado: Optional[str] = Query(default=None),
    busqueda: Optional[str] = Query(default=None),
    oficina: Optional[str] = Query(default=None),
    creador: Optional[str] = Query(default=None),
    pagina: int = Query(default=1, ge=1),
    porPagina: int = Query(default=25, ge=1, le=10000),
    tipoCliente: Optional[str] = Query(default="ACTIVO"),
    ordenarPor: Optional[str] = Query(default="fecha"),
    ordenDireccion: Optional[str] = Query(default="DESC"),
    tipoFecha: Optional[str] = Query(default="PRESTAMO"),
):
    try:
        sets = execute_sp_multi(
            "cxcClientesIntelligence",
            fechaDesde,
            fechaHasta,
            empresa or None,
            estado or None,
            busqueda or None,
            oficina or None,
            creador or None,
            pagina,
            porPagina,
            tipoCliente or "ACTIVO",
            ordenarPor or "fecha",
            ordenDireccion or "DESC",
            tipoFecha or "PRESTAMO",
        )

        stats_raw = sets[0][0] if sets and sets[0] else {
            "totalClientes": 0,
            "totalClientesGlobal": 0,
            "totalFiltrados": 0,
            "nuevos": 0,
            "reenganchados": 0,
            "enMora": 0,
            "problematicos": 0,
            "alDia": 0,
            "cancelados": 0,
            "montoTotalCartera": 0,
            "balanceTotalPendiente": 0,
            "paginaActual": pagina,
            "porPagina": porPagina,
            "totalPaginas": 0,
        }
        clientes_raw = sets[1] if len(sets) > 1 else []
        empresas_raw = sets[2] if len(sets) > 2 else []
        oficinas_raw = [r.get("oficina") for r in (sets[3] if len(sets) > 3 else []) if r.get("oficina")]

        return ClientesResponse(
            stats=ClientesStats(**stats_raw),
            clientes=[ClienteResumen(**c) for c in clientes_raw],
            porEmpresa=[EmpresaDistribucion(**e) for e in empresas_raw],
            oficinas=oficinas_raw,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{id_cliente}/historial",
    response_model=ClienteHistorialResponse,
    summary="Perfil integral e historial de préstamos de un cliente",
)
async def get_historial_cliente(id_cliente: int):
    try:
        sets = execute_sp_multi("cxcHistorialPrestamosCliente", id_cliente)
        if not sets or not sets[0]:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontró el cliente con ID {id_cliente}",
            )

        cliente_raw = sets[0][0]
        prestamos_raw = sets[1] if len(sets) > 1 else []

        return ClienteHistorialResponse(
            cliente=ClienteDetalle(**cliente_raw),
            prestamos=[PrestamoHistoricoItem(**p) for p in prestamos_raw],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))