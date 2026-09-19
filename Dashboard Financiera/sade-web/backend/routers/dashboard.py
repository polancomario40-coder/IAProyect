"""
dashboard.py — Router para endpoints del Dashboard
"""
from fastapi import APIRouter, HTTPException, Query
from database import execute_sp, execute_sp_multi
from models.schemas import DashboardKPIs, CobrosporMes, DashboardResponse

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/kpis", response_model=DashboardKPIs, summary="KPIs del Dashboard")
async def get_kpis():
    """
    Retorna los indicadores clave del panel de control:
    - Cartera activa (capital pendiente)
    - Cobros del mes actual
    - Préstamos en atraso y tasa de mora
    - Moras e intereses pendientes
    """
    try:
        rows = execute_sp("cxcDashboardKPIs")
        if not rows:
            raise HTTPException(status_code=404, detail="No se encontraron datos")
        return DashboardKPIs(**rows[0])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/cobros-por-mes",
    response_model=list[CobrosporMes],
    summary="Cobros de los últimos N meses",
)
async def get_cobros_por_mes(
    meses: int = Query(default=12, ge=1, le=60, description="Número de meses a mostrar"),
):
    """
    Retorna los cobros (RC) agrupados por mes para el gráfico de barras.
    Los meses sin cobros aparecen con valores en 0.
    """
    try:
        rows = execute_sp("cxcCobrosporMes", meses)
        return [CobrosporMes(**r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/",
    response_model=DashboardResponse,
    summary="Dashboard completo (KPIs + Gráfico)",
)
async def get_dashboard_completo(
    meses: int = Query(default=12, ge=1, le=60),
):
    """Combina KPIs y cobros por mes en una sola llamada."""
    try:
        kpis_rows = execute_sp("cxcDashboardKPIs")
        cobros_rows = execute_sp("cxcCobrosporMes", meses)

        if not kpis_rows:
            raise HTTPException(status_code=404, detail="No se encontraron datos")

        return DashboardResponse(
            kpis=DashboardKPIs(**kpis_rows[0]),
            cobrosporMes=[CobrosporMes(**r) for r in cobros_rows],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
