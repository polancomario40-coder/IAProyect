"""
prestamos.py — Router para consulta de estado de préstamo individual
"""
from fastapi import APIRouter, HTTPException
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
    "/{numero_cxc}",
    response_model=EstadoPrestamoResponse,
    summary="Consulta el estado completo de un préstamo por su número",
)
async def get_estado_prestamo(numero_cxc: str):
    try:
        sets = execute_sp_multi("cxcEstadoPrestamo", numero_cxc)
        if not sets or not sets[0]:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontró el préstamo '{numero_cxc}'",
            )

        encabezado_raw = sets[0][0]
        cuotas_raw = sets[1] if len(sets) > 1 else []
        recibos_raw = sets[2] if len(sets) > 2 else []
        conteos_raw = (
            sets[3][0]
            if len(sets) > 3 and sets[3]
            else {"totalCuotas": len(cuotas_raw), "totalRecibos": len(recibos_raw)}
        )

        return EstadoPrestamoResponse(
            encabezado=EncabezadoPrestamo(**encabezado_raw),
            cuotas=[Cuota(**c) for c in cuotas_raw],
            recibos=[Recibo(**r) for r in recibos_raw],
            conteos=ConteosPrestamo(**conteos_raw),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))