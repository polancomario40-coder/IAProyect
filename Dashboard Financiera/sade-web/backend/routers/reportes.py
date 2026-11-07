"""
reportes.py — Router FastAPI para Reportes Analíticos Oficiales
Endpoints:
    GET /api/reportes/detalle-clientes     → Detalle Individual de Clientes (con subtipos Nuevos, Reenganchados, etc.)
    GET /api/reportes/consolidado-cartera  → Resumen Consolidado por Cartera
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from database import execute_sp_multi
from models.schemas import (
    ReporteDetalleClientesResponse,
    ReporteDetalleClientesTotales,
    ReporteDetalleClienteItem,
    ReporteConsolidadoCarteraResponse,
    ReporteConsolidadoCarteraTotales,
    ReporteConsolidadoCarteraItem,
)

router = APIRouter(prefix="/api/reportes", tags=["Reportes"])


@router.get(
    "/detalle-clientes",
    response_model=ReporteDetalleClientesResponse,
    summary="Informe 1: Detalle Individual de Clientes con Quincena y Totales en pesos ($)",
)
def get_reporte_detalle_clientes(
    fechaDesde:  Optional[date] = Query(None, description="Fecha de inicio del período consultado"),
    fechaHasta:  Optional[date] = Query(None, description="Fecha de corte / fin del período consultado"),
    empresa:     Optional[str]  = Query(None, description="Filtrar por Cartera / Empresa específica"),
    tipoReporte: Optional[str]  = Query("TODOS", description="Tipo de reporte: TODOS, NUEVOS, REENGANCHADOS, EN MORA, AL DIA"),
):
    try:
        empresa_param = empresa.strip() if empresa and empresa.strip() else None
        tipo_param = (tipoReporte or "TODOS").strip().upper()

        result_sets = execute_sp_multi(
            "cxcReporteDetalleClientes",
            fechaDesde,
            fechaHasta,
            empresa_param,
            tipo_param,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al ejecutar cxcReporteDetalleClientes: {exc}") from exc

    if len(result_sets) < 2:
        raise HTTPException(
            status_code=500,
            detail=f"El procedimiento devolvió {len(result_sets)} result sets; se esperaban 2.",
        )

    rs_filas, rs_totales = result_sets[0], result_sets[1]
    
    # Garantizar que capitalActualAdeudado nunca venga en 0 si montoPrestamo > capitalPagado
    processed_filas = []
    total_cap_adeudado = Decimal('0.00')
    for r in rs_filas:
        row_dict = dict(r)
        monto = Decimal(str(row_dict.get("montoPrestamo") or 0))
        pagado = Decimal(str(row_dict.get("capitalPagado") or 0))
        adeudado_val = row_dict.get("capitalActualAdeudado")
        if adeudado_val is None or Decimal(str(adeudado_val)) == Decimal('0.00'):
            # Fórmula oficial: Capital Actual Adeudado = Monto Préstamo Inicial - Capital Pagado
            adeudado_calc = max(Decimal('0.00'), monto - pagado)
            row_dict["capitalActualAdeudado"] = adeudado_calc
        else:
            row_dict["capitalActualAdeudado"] = Decimal(str(adeudado_val))
        
        total_cap_adeudado += row_dict["capitalActualAdeudado"]
        processed_filas.append(row_dict)

    totales_dict = dict(rs_totales[0]) if rs_totales else {
        "totalRegistros": 0,
        "totalMontoPrestamo": 0,
        "totalCapitalPagado": 0,
        "totalBalanceAntesCobro": 0,
        "totalCapitalCobradoQuincena": 0,
        "totalInteresCobradoQuincena": 0,
        "totalCapitalActualAdeudado": 0,
        "totalCobradoQuincena": 0,
        "totalBalanceActual": 0,
        "tasaPromedio": 0.0,
        "periodoDesde": fechaDesde,
        "periodoHasta": fechaHasta,
        "quincenaDesde": None,
        "quincenaHasta": None,
    }

    if not totales_dict.get("totalCapitalActualAdeudado") or Decimal(str(totales_dict.get("totalCapitalActualAdeudado"))) == Decimal('0.00'):
        totales_dict["totalCapitalActualAdeudado"] = total_cap_adeudado

    filas = [ReporteDetalleClienteItem(**r) for r in processed_filas]
    totales = ReporteDetalleClientesTotales(**totales_dict)

    return ReporteDetalleClientesResponse(totales=totales, filas=filas)


@router.get(
    "/consolidado-cartera",
    response_model=ReporteConsolidadoCarteraResponse,
    summary="Informe 2: Resumen Consolidado por Cartera con Quincena y Totales en pesos ($)",
)
def get_reporte_consolidado_cartera(
    fechaCorte: Optional[date] = Query(None, description="Fecha de corte consultada"),
    fechaDesde: Optional[date] = Query(None, description="Fecha de inicio de la quincena/período"),
    fechaHasta: Optional[date] = Query(None, description="Fecha de fin de la quincena/período"),
    empresa:    Optional[str]  = Query(None, description="Filtrar por Cartera / Empresa específica"),
):
    try:
        empresa_param = empresa.strip() if empresa and empresa.strip() else None
        corte_eff = fechaHasta or fechaCorte

        result_sets = execute_sp_multi(
            "cxcReporteConsolidadoCartera",
            corte_eff,
            empresa_param,
            fechaDesde,
            corte_eff,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al ejecutar cxcReporteConsolidadoCartera: {exc}") from exc

    if len(result_sets) < 2:
        raise HTTPException(
            status_code=500,
            detail=f"El procedimiento devolvió {len(result_sets)} result sets; se esperaban 2.",
        )

    rs_filas, rs_totales = result_sets[0], result_sets[1]

    totales_dict = rs_totales[0] if rs_totales else {
        "totalCarteras": 0,
        "totalBalanceCapitalColocado": 0,
        "totalCapitalInactivosCancelados": 0,
        "totalCapitalActivo": 0,
        "totalClientesActivos": 0,
        "totalClientesInactivos": 0,
        "totalCapitalCobradoQuincena": 0,
        "totalInteresCobradoQuincena": 0,
        "tasaPromedioPonderada": 0.0,
        "fechaCorte": fechaCorte,
        "quincenaDesde": None,
        "quincenaHasta": None,
    }

    filas = [ReporteConsolidadoCarteraItem(**r) for r in rs_filas]
    totales = ReporteConsolidadoCarteraTotales(**totales_dict)

    return ReporteConsolidadoCarteraResponse(totales=totales, filas=filas)
