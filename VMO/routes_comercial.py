"""
Rutas del modulo Comercial (2026-10-19) — el dashboard comercial que antes
era un Excel con tablas dinamicas.

Como Logistica, estas rutas son un deposito: reciben los Excel, guardan las
filas y las devuelven. Las cuentas del dashboard (totales, graficos, filtros,
cumplimiento) viven en `static/comercial.logic.js` y corren en el navegador.

Ambiente separado: todo lo de aca usa `comercial/db/comercial.db` y nada mas.

Subir un archivo es en dos pasos con el MISMO archivo: primero sin
`confirmar` (lee, valida y devuelve el resumen de lo que va a reemplazar) y
despues con `confirmar=true` (guarda). Se manda dos veces en vez de guardar el
archivo en memoria del servidor entre un paso y otro: son unos MB y leerlo
tarda segundos, y asi no queda nada a medias si nadie confirma.
"""
import asyncio

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

import core
from core import verificar_token

router = APIRouter()


async def _leer_subida(archivo: UploadFile) -> bytes:
    buf = bytearray()
    while True:
        chunk = await archivo.read(1024 * 1024)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > core.COM_EXCEL_MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"El archivo supera el máximo de {core.COM_EXCEL_MAX_BYTES // (1024 * 1024)} MB.")
    return bytes(buf)


def _nombre(archivo: UploadFile) -> str:
    return (archivo.filename or "archivo").replace("\\", "/").split("/")[-1][:200]


@router.post("/api/comercial/despachos")
async def comercial_subir_despachos(archivo: UploadFile = File(...), confirmar: bool = Form(False),
                                    authorization: str = Header(None)):
    verificar_token(authorization)
    contenido = await _leer_subida(archivo)
    nombre = _nombre(archivo)
    try:
        # En un hilo: openpyxl leyendo 38.000 filas tarda unos segundos y
        # congelaria el servidor para todos mientras tanto.
        filas = await asyncio.to_thread(core.com_leer_despachos, contenido, nombre)
    except core.ComercialArchivoInvalido as e:
        raise HTTPException(status_code=400, detail=str(e))
    core.setup_comercial_db()
    conn = core._com_conn()
    try:
        resumen = core.com_resumen_despachos(filas, conn)
        if confirmar:
            core.com_guardar_despachos(filas, nombre, conn)
        return {"archivo": nombre, "guardado": bool(confirmar), "meses": resumen,
                "filas": len(filas), "m3": sum(f["cantidad"] or 0 for f in filas),
                "rd": sum(f["line_total"] or 0 for f in filas),
                # Lo que el dashboard no puede agrupar bien: una fila sin
                # vendedor, zona o rango cae en "(vacío)" en ese grafico.
                "sin_vendedor": sum(1 for f in filas if not f["vendedor"]),
                "sin_zona": sum(1 for f in filas if not f["zona"]),
                "sin_rango": sum(1 for f in filas if not f["rango_fc"])}
    finally:
        conn.close()


@router.post("/api/comercial/plan")
async def comercial_subir_plan(archivo: UploadFile = File(...), confirmar: bool = Form(False),
                               authorization: str = Header(None)):
    verificar_token(authorization)
    contenido = await _leer_subida(archivo)
    nombre = _nombre(archivo)
    try:
        plan = await asyncio.to_thread(core.com_leer_plan, contenido, nombre)
        precios = await asyncio.to_thread(core.com_leer_precio_plan, contenido, nombre)
    except core.ComercialArchivoInvalido as e:
        raise HTTPException(status_code=400, detail=str(e))
    core.setup_comercial_db()
    conn = core._com_conn()
    try:
        actuales = {m: (m3, precio) for m, m3, precio in conn.execute("SELECT mes, m3, precio FROM comercial_plan")}
        if confirmar:
            core.com_guardar_plan(plan, nombre, conn, precios)
        return {"archivo": nombre, "guardado": bool(confirmar),
                "meses": [{"mes": m, "m3": plan[m], "m3_actual": actuales.get(m, (None, None))[0],
                           "precio": precios.get(m), "precio_actual": actuales.get(m, (None, None))[1]}
                          for m in sorted(plan)]}
    finally:
        conn.close()


@router.get("/api/comercial/datos")
async def comercial_datos(anio: int | None = None, authorization: str = Header(None)):
    """Los despachos de un ano y su plan, para que el navegador arme el
    dashboard. Sin `anio`, el ultimo ano con despachos."""
    verificar_token(authorization)
    core.setup_comercial_db()
    conn = core._com_conn()
    try:
        if anio is None:
            ultimo = conn.execute("SELECT MAX(substr(mes, 1, 4)) FROM comercial_despacho").fetchone()[0]
            anio = int(ultimo) if ultimo else core.datetime.now().year
        if not 2000 <= anio <= 2100:
            raise HTTPException(status_code=400, detail="Año inválido.")
        return core.com_datos_dashboard(conn, anio)
    finally:
        conn.close()


@router.get("/api/comercial/cargas")
async def comercial_cargas(authorization: str = Header(None)):
    verificar_token(authorization)
    core.setup_comercial_db()
    conn = core._com_conn()
    try:
        return {"cargas": core.com_cargas(conn)}
    finally:
        conn.close()
