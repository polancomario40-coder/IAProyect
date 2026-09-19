"""
clientes.py — Router FastAPI para el módulo de Clientes (CXC)

Endpoint:
    GET /api/clientes/  → Listado paginado + estadísticas + distribución por empresa
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from database import execute_sp_multi
from models.schemas import ClientesResponse

router = APIRouter(prefix="/api/clientes", tags=["Clientes"])


@router.get("/", response_model=ClientesResponse, summary="Listado de clientes con estadísticas")
def get_clientes(
    fechaDesde:  Optional[date] = Query(None, description="Fecha inicio del filtro"),
    fechaHasta:  Optional[date] = Query(None, description="Fecha fin del filtro"),
    empresa:     Optional[str]  = Query(None, description="Nombre de la empresa"),
    estado:      Optional[str]  = Query(
        None,
        description="Estado del cliente",
        pattern="^(NUEVO|REENGANCHADO|EN MORA|PROBLEMATICO|AL DIA)$",
    ),
    busqueda:    Optional[str]  = Query(None, description="Texto libre (nombre, cedula, telefono...)"),
    oficina:     Optional[str]  = Query(None, description="Nombre de la oficina"),
    gestor:      Optional[str]  = Query(None, description="Nombre del gestor"),
    pagina:      int            = Query(1,    ge=1,       description="Pagina actual"),
    porPagina:   int            = Query(25,   ge=1, le=200, description="Registros por pagina"),
):
    """
    Consulta el SP cxcClientesIntelligence y devuelve:
    - stats: KPIs/totales del universo filtrado (RS 0)
    - clientes: Lista paginada de clientes (RS 1)
    - porEmpresa: Top 15 empresas por cartera (RS 2)
    - oficinas: Catalogo de oficinas disponibles (RS 3)
    """
    try:
        # execute_sp_multi usa *args — pasamos los 9 parámetros desempaquetados
        result_sets = execute_sp_multi(
            "cxcClientesIntelligence",
            fechaDesde,
            fechaHasta,
            empresa,
            estado,
            busqueda,
            oficina,
            gestor,
            pagina,
            porPagina,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al ejecutar SP: {exc}") from exc

    # Validar que el SP devolvio los 4 result sets esperados
    if len(result_sets) < 4:
        raise HTTPException(
            status_code=500,
            detail=f"El SP devolvio {len(result_sets)} result sets; se esperaban 4.",
        )

    rs_stats, rs_clientes, rs_empresas, rs_oficinas = (
        result_sets[0],
        result_sets[1],
        result_sets[2],
        result_sets[3],
    )

    # RS 0: fila unica de estadisticas
    if not rs_stats:
        raise HTTPException(status_code=500, detail="RS 0 (stats) vacio.")
    stats = rs_stats[0]

    # RS 3: extraer solo el nombre de la oficina (primer valor de cada fila)
    oficinas_list: list[str] = []
    for row in rs_oficinas:
        valores = list(row.values())
        if valores:
            oficinas_list.append(str(valores[0]))

    return {
        "stats":      stats,
        "clientes":   rs_clientes,
        "porEmpresa": rs_empresas,
        "oficinas":   oficinas_list,
    }
