"""
prestamos.py — Router para endpoints de Préstamos
"""
from fastapi import APIRouter, HTTPException, Path, Query
from database import execute_sp_multi
from models.schemas import (
    EstadoPrestamoResponse,
    EncabezadoPrestamo,
    Cuota,
    Recibo,
    ConteosPrestamo,
)

router = APIRouter(prefix="/api/prestamos", tags=["Préstamos"])


@router.get(
    "/{idCxc}",
    response_model=EstadoPrestamoResponse,
    summary="Estado completo de un préstamo",
)
async def get_estado_prestamo(
    idCxc: str = Path(
        ...,
        description="Número del préstamo (campo Cxc en dbo.Cxc)",
        examples=["17481"],
    )
):
    """
    Retorna el estado completo de un préstamo en 4 secciones:
    1. **Encabezado** — Datos generales + los 4 bloques de resumen
       (Inicial, Pagado, Balance, Vencido)
    2. **Cuotas** — Tabla de cuotas con estado (PAGADA / VENCIDA / PENDIENTE)
    3. **Recibos** — Historial de pagos con distribución
    4. **Conteos** — Total de cuotas y recibos
    """
    try:
        result_sets = execute_sp_multi("cxcEstadoPrestamo", idCxc)

        # Verificar que el SP retornó los 4 result sets esperados
        if len(result_sets) < 4:
            raise HTTPException(
                status_code=500,
                detail=f"El SP retornó {len(result_sets)} result sets, se esperaban 4",
            )

        # RS 0 → Encabezado y bloques resumen
        if not result_sets[0]:
            raise HTTPException(
                status_code=404,
                detail=f"Préstamo {idCxc} no encontrado",
            )

        encabezado = EncabezadoPrestamo(**result_sets[0][0])

        # RS 1 → Cuotas
        cuotas = [Cuota(**row) for row in result_sets[1]]

        # RS 2 → Recibos
        recibos = [Recibo(**row) for row in result_sets[2]]

        # RS 3 → Conteos
        conteos = ConteosPrestamo(**result_sets[3][0]) if result_sets[3] else ConteosPrestamo(
            totalCuotas=len(cuotas), totalRecibos=len(recibos)
        )

        return EstadoPrestamoResponse(
            encabezado=encabezado,
            cuotas=cuotas,
            recibos=recibos,
            conteos=conteos,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
