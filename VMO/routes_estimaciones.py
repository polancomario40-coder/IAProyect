# by a_oller
"""
routes_estimaciones.py — las rutas HTTP de Estimaciones (issue #4, Fase 2;
issue #17 agrego cerrar/reabrir/cerradas).

Referencia config/estado mutable compartido (EST_DB_PATH, EST_DATA_DIR,
EST_REPORTES_DIR, EST_ZIP_MAX_BYTES, EST_ZIP_MAX_PDFS, est_sessions,
VISION_MODEL_STD, PUENTE_*, EST_RGO_SANITY_MAX) via `core.NOMBRE` en vez de
`from core import NOMBRE` — ver el docstring de core.py para el porque.
Funciones puras de negocio si se importan directo, son seguras.
"""
import asyncio
import io
import json
import os
import re
import shutil
import sqlite3
import traceback
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import core
from core import (
    verificar_token,
    setup_est_db,
    _procesar_pdfs,
    generar_excel_validacion,
    _confirmar_registros,
    actualizar_excel_main,
    _reprocesar_en_background,
    _nombre_archivo_seguro,
    _est_vista_previa,
    _est_catalogo_fase,
    _est_plantilla_de_fase,
    _est_normalizar,
    _est_generar_workbook,
    _est_clasificar_series,
    _est_avisos_cierre,
    _est_cerrar_estimacion,
    _est_corte_de_conteo,
    _est_aprobar_pendiente,
    _est_revertir_aprobacion,
    _est_motivo_no_reversible,
    _est_descartar_pendiente,
    _est_reponer_descartado,
    EST_MOTIVOS_APROBABLES,
    cargar_lookup_excel,
    ExcelFormatoError,
    ExcelIlegibleError,
    _est_filtrar_conflictos_excel,
)

router = APIRouter()


def _lista_errores_vision(errores):
    """Cada error con `reprocesable`: si Opus lo puede volver a leer. Solo los
    que fallaron AL LEERSE guardan los bytes del PDF; un nombre de archivo
    invalido (un "Scan_19-09-2026....pdf" del escaner), un PDF de mas de una
    pagina o uno demasiado grande no se arreglan reintentando Vision. Hasta el
    2026-10-15 la pantalla los contaba en "reprocesar con Opus (4)", Opus leia
    1, y el segundo clic, sin nada que reintentar, daba el lote por terminado
    y volvia al inicio escondiendo los 3 que seguian en error."""
    return [{"nombre": e["nombre"], "motivo": e["motivo"],
             "reprocesable": bool(e.get("_pdf_bytes"))} for e in errores]


def _hacer_lugar_para_una_sesion():
    """Antes de abrir un lote nuevo: libera las sesiones vencidas y, si igual
    quedan EST_MAX_SESIONES, la mas vieja sin reproceso en curso. Cada sesion
    retiene en memoria los PDFs de su lote (auditoria 2026-10-07)."""
    core._est_purgar_sesiones()
    libres = sorted(
        (sid for sid, s in core.est_sessions.items()
         if not (s.get("reprocess_progress") or {}).get("activo")),
        key=lambda sid: core.est_sessions[sid].get("creada", datetime.min))
    while len(core.est_sessions) >= core.EST_MAX_SESIONES and libres:
        core.est_sessions.pop(libres.pop(0), None)


@router.post("/api/estimaciones/procesar-zip")
async def procesar_zip(archivo: UploadFile = File(...), excel: UploadFile = File(...),
                        authorization: str = Header(None)):
    """Issue #15: el Excel de conduces es obligatorio, junto con el ZIP —
    sin el es un 422 automatico de FastAPI (campo requerido faltante), antes
    de que este handler corra una sola linea. El Excel se lee y valida ANTES
    de abrir el ZIP y antes de cualquier llamada a Vision — es la fuente de
    verdad de la descripcion y, via el Cliente, de la fase."""
    verificar_token(authorization)
    setup_est_db()
    _hacer_lugar_para_una_sesion()

    excel_buf = bytearray()
    while True:
        chunk = await excel.read(1024 * 1024)
        if not chunk:
            break
        excel_buf.extend(chunk)
        if len(excel_buf) > core.EST_EXCEL_MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"El Excel excede el tope de {core.EST_EXCEL_MAX_BYTES // (1024 * 1024)}MB"
            )
    excel_bytes = bytes(excel_buf)

    try:
        # En un hilo: openpyxl recorriendo miles de filas congelaba el
        # servidor entero para todos los usuarios mientras tanto.
        lookup = await asyncio.to_thread(cargar_lookup_excel, excel_bytes)
    except ExcelFormatoError as e:
        raise HTTPException(status_code=400, detail={"error": "excel_formato_invalido", "detalle": str(e)})
    except ExcelIlegibleError as e:
        raise HTTPException(status_code=400, detail={"error": "excel_ilegible", "detalle": str(e)})

    zip_buf = bytearray()
    while True:
        chunk = await archivo.read(1024 * 1024)
        if not chunk:
            break
        zip_buf.extend(chunk)
        if len(zip_buf) > core.EST_ZIP_MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"El ZIP excede el tope de {core.EST_ZIP_MAX_BYTES // (1024 * 1024)}MB"
            )
    zip_bytes = bytes(zip_buf)

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="El archivo no es un ZIP válido")

    pdfs = [n for n in zf.namelist() if n.lower().endswith(".pdf") and os.path.basename(n)]
    if len(pdfs) > core.EST_ZIP_MAX_PDFS:
        raise HTTPException(
            status_code=413,
            detail=f"El ZIP tiene {len(pdfs)} PDFs, excede el tope de {core.EST_ZIP_MAX_PDFS} por lote"
        )

    conn = sqlite3.connect(core.EST_DB_PATH)
    importadas, errores_vision, pendientes, duplicadas, corregidas = await _procesar_pdfs(
        zf, pdfs, conn, core.VISION_MODEL_STD, lookup
    )
    conn.commit()
    conn.close()
    zf.close()

    session_id     = str(uuid.uuid4())
    core.est_sessions[session_id] = {
        "importadas": importadas, "errores_vision": errores_vision, "lookup": lookup,
        "creada": datetime.now(),
    }
    excel_filename = f"validacion_{session_id[:8]}.xlsx"
    excel_path     = os.path.join(core.EST_DATA_DIR, excel_filename)
    await asyncio.to_thread(generar_excel_validacion, importadas, excel_path)

    # importadas_lista/importadas_sin_firma_lista son solo un split de
    # presentacion — el conteo real de importadas (usado al incorporar) sigue
    # siendo la lista completa, sello obligatorio + firma opcional juntos.
    importadas_validas    = [d for d in importadas if not d.get("sin_firma")]
    importadas_sin_firma  = [d for d in importadas if d.get("sin_firma")]

    # conflictos_excel solo lista conflictos de filas que corresponden a PDFs
    # de ESTE ZIP — el Excel tiene miles de filas, solo importan las del lote.
    conflictos_excel = _est_filtrar_conflictos_excel(lookup, pdfs)

    return JSONResponse(content={
        "importadas":        len(importadas),
        "importadas_lista":  [d["archivo_pdf"] for d in importadas_validas],
        "importadas_sin_firma_lista": [d["archivo_pdf"] for d in importadas_sin_firma],
        "errores_vision":    len(errores_vision),
        "errores_vision_lista": _lista_errores_vision(errores_vision),
        "pendientes":        len(pendientes),
        "pendientes_lista":  pendientes,
        "duplicadas":        duplicadas,
        "corregidas_lista":  corregidas,
        "conflictos_excel":  conflictos_excel,
        "session_id":        session_id,
        "excel_url":         f"/api/estimaciones/excel/{excel_filename}"
    }, media_type="application/json; charset=utf-8")

@router.post("/api/estimaciones/incorporar-y-reprocesar")
async def incorporar_y_reprocesar(req: dict, authorization: str = Header(None)):
    """Un solo paso: (1) incorpora a la BD lo que ya esta validado, (2) reintenta
    con Opus (mas capaz) solo los PDFs que dieron error de lectura con Haiku,
    en segundo plano (ver /reprocesar-progreso para la barra en vivo). Nunca
    toca los que estan en pendientes_revision por falta de sello/firma — eso
    no es un problema de lectura, no se resuelve reintentando Vision.
    Si despues de reprocesar quedan errores, el frontend puede llamar de nuevo
    a este mismo endpoint para repetir la ronda."""
    verificar_token(authorization)
    session_id = req.get("session_id")
    if session_id not in core.est_sessions:
        raise HTTPException(status_code=404, detail="Sesión no encontrada o expirada")

    sesion = core.est_sessions[session_id]
    if (sesion.get("reprocess_progress") or {}).get("activo"):
        # Sin esto, un doble clic (o un script) lanzaba un segundo reproceso
        # con Opus sobre los MISMOS PDFs mientras el primero seguia: el doble
        # de llamadas, y las dos tareas escribiendo la misma sesion.
        raise HTTPException(status_code=409, detail="Ya hay un reproceso en curso para este lote")
    conn = sqlite3.connect(core.EST_DB_PATH)

    # Incorporar lo ya valido (rapido, sincrono)
    confirmados = _confirmar_registros(conn, sesion["importadas"])
    conn.commit()
    conn.close()
    if confirmados:
        await asyncio.to_thread(actualizar_excel_main, confirmados)
    sesion["importadas"] = []
    sesion["incorporados_total"] = len(confirmados)

    total_reprocesar = len([e for e in sesion["errores_vision"] if e.get("_pdf_bytes")])

    # Split de presentacion (mismo criterio que /procesar-zip) sobre lo que
    # realmente se confirmo en este paso — no cambia el conteo de incorporados.
    confirmados_sin_firma = [r for r in confirmados if r.get("sin_firma")]

    if total_reprocesar == 0:
        return JSONResponse(content={
            "incorporados_ahora": len(confirmados),
            "importadas_sin_firma_lista": [r["archivo_pdf"] for r in confirmados_sin_firma],
            "reprocesando":       False,
            "errores_vision":     len(sesion["errores_vision"]),
            "errores_vision_lista": _lista_errores_vision(sesion["errores_vision"]),
            "pendientes_nuevos":  [],
            "session_id":         session_id,
        }, media_type="application/json; charset=utf-8")

    sesion["reprocess_progress"] = {
        "activo": True, "actual": 0, "total": total_reprocesar,
        "modelo": "opus", "pendientes_nuevos": [],
    }
    asyncio.create_task(_reprocesar_en_background(session_id))

    return JSONResponse(content={
        "incorporados_ahora": len(confirmados),
        "reprocesando":       True,
        "total_reprocesar":   total_reprocesar,
        "session_id":         session_id,
    }, media_type="application/json; charset=utf-8")


@router.get("/api/estimaciones/reprocesar-progreso/{session_id}")
async def reprocesar_progreso(session_id: str, authorization: str = Header(None)):
    verificar_token(authorization)
    if session_id not in core.est_sessions:
        raise HTTPException(status_code=404, detail="Sesión no encontrada o expirada")
    sesion = core.est_sessions[session_id]
    prog = sesion.get("reprocess_progress")
    if not prog:
        raise HTTPException(status_code=404, detail="No hay un reproceso en curso para esta sesión")

    resultado = {
        "activo": prog["activo"], "actual": prog["actual"],
        "total": prog["total"], "modelo": prog["modelo"],
    }
    if not prog["activo"]:
        resultado["errores_vision"]      = len(sesion["errores_vision"])
        resultado["errores_vision_lista"] = _lista_errores_vision(sesion["errores_vision"])
        resultado["pendientes_nuevos"]   = prog["pendientes_nuevos"]
        resultado["incorporados_total"]  = sesion.get("incorporados_total", 0)
        # Split de presentacion — documentos reprocesados con Opus que se
        # importaron con sello pero sin firma, mismo criterio que las otras
        # 2 respuestas JSON del pipeline.
        resultado["importadas_sin_firma_lista"] = prog.get("importadas_sin_firma_lista", [])
        # Issue #15: corregidas_lista del reproceso con Opus SOLO sale por
        # aca — /incorporar-y-reprocesar responde antes de que el trabajo
        # exista, no puede devolverla en su propia respuesta.
        resultado["corregidas_lista"] = prog.get("corregidas_lista", [])

    return JSONResponse(content=resultado, media_type="application/json; charset=utf-8")


def _cuenta_para_estimaciones(fecha, corte):
    """Issue #20 — la definicion unica de si un conduce va a sumar a alguna
    estimacion: False si su fecha es NULL (sin fecha no se puede afirmar que
    cuente — lado conservador) o si hay corte y fecha <= corte. La misma que
    aplica core._est_aprobar_pendiente() al aprobar."""
    return not (fecha is None or (corte is not None and fecha <= corte))


@router.get("/api/estimaciones/pendientes-revision")
async def listar_pendientes_revision(authorization: str = Header(None)):
    """Separa la lista en 2 grupos segun la regla fase-condicional del issue
    #8: MACAO 2 (motivo siempre "falta sello") vs cualquier otra fase
    (motivo siempre "falta firma") — evita que el usuario tenga que adivinar
    por que motivo esta cada fila mezclada en una sola tabla.

    Issue #20: cada fila suma `aprobable` (bool, segun el motivo),
    `cuenta_para_estimaciones` y `corte` — lo que el panel necesita para
    mostrar el boton Aprobar y la franja de aviso del corte de conteo.

    Issue #67: y `obra_papel`, la linea `OBRA:` del papel. Va JUNTO a `obra`
    y no en su lugar: son datos distintos (`obra` vale la fase por el import
    masivo) y el operador que decide si aprueba un pendiente es justo quien
    necesita saber a que obra fue el conduce sin abrir el escaneo. El SELECT
    es de columnas explicitas, asi que una columna nueva NO llega sola —
    misma trampa que se comio el issue #31 en routes_conduces.py.

    Issue #72: y `obra_familia`, la forma normalizada/agrupada de obra_papel
    (core.normalizar_obra_papel()) — solo para auditar/agrupar."""
    verificar_token(authorization)
    setup_est_db()
    conn = sqlite3.connect(core.EST_DB_PATH)
    cur = conn.execute(
        """SELECT archivo_pdf, id_documento, fecha, cliente, obra, obra_papel,
                  obra_familia,
                  empresa, fase, descripcion, cantidad, motivo, fecha_pendiente
           FROM pendientes_revision ORDER BY fecha_pendiente DESC"""
    )
    cols = [c[0] for c in cur.description]
    filas = [dict(zip(cols, row)) for row in cur.fetchall()]
    cortes: dict = {}  # (empresa, fase) -> corte, una consulta por fase y no por fila
    for f in filas:
        f["aprobable"] = f.get("motivo") in EST_MOTIVOS_APROBABLES
        clave_fase = (f.get("empresa"), f.get("fase"))
        if clave_fase not in cortes:
            cortes[clave_fase] = _est_corte_de_conteo(conn, *clave_fase)
        f["corte"] = cortes[clave_fase]
        f["cuenta_para_estimaciones"] = _cuenta_para_estimaciones(f.get("fecha"), f["corte"])
    conn.close()
    macao2 = [f for f in filas if f.get("fase") == "MACAO 2"]
    otras_fases = [f for f in filas if f.get("fase") != "MACAO 2"]
    return JSONResponse(
        content={"total": len(filas), "macao2": macao2, "otras_fases": otras_fases},
        media_type="application/json; charset=utf-8"
    )


# ── Issue #20 — aprobacion manual de pendientes (falta sello / falta firma) ──

class EstAprobarPendienteRequest(BaseModel):
    archivo_pdf: str
    aprobado_por: str
    motivo: str


class EstRevertirAprobacionRequest(BaseModel):
    id_documento: str


def _mover_pdf_con_transaccion(conn, primitiva, origen: str, destino: str):
    """Issue #20 — la secuencia compartida de aprobar y revertir, en este
    orden y no otro: BEGIN IMMEDIATE → primitiva de core (toda la BD) →
    copiar el PDF al destino → COMMIT → recien ahi borrar el origen. Una
    transaccion de SQLite no revierte un archivo movido: copiando antes del
    COMMIT y borrando despues, cualquier fallo previo al COMMIT se deshace
    entero (ROLLBACK + borrar la copia si llego a crearse) y un fallo del
    borrado final solo deja un PDF huerfano en el directorio de origen —
    detectable y registrado en el log, nunca una fila sin su documento de
    respaldo (criterio 13, mismo criterio que _est_resolver_pendiente).

    BEGIN IMMEDIATE serializa dos clicks simultaneos sobre el mismo
    documento: el segundo espera, encuentra la fila ya movida por el primero
    y falla con 400 sin haber copiado nada — las guardas corren DENTRO de la
    transaccion, no antes.

    Codigos HTTP sin ambiguedad (mismo criterio aceptado en el issue #15):
    ValueError de core → 400 con el detalle tal cual (entrada o estado que
    el operador puede corregir); OSError de la copia → 500 generico con el
    detalle al log (no es culpa del operador ni se arregla reintentando el
    mismo click)."""
    conn.execute("BEGIN IMMEDIATE")
    copiado = False
    try:
        resultado = primitiva(conn)
        shutil.copy2(origen, destino)
        copiado = True
        conn.execute("COMMIT")
    except Exception as e:
        conn.execute("ROLLBACK")
        if copiado and os.path.exists(destino):
            try:
                os.remove(destino)
            except OSError:
                print(f"[estimaciones] no se pudo limpiar la copia {destino} tras el rollback")
                traceback.print_exc()
        if isinstance(e, ValueError):
            raise HTTPException(status_code=400, detail=str(e))
        if isinstance(e, HTTPException):
            raise
        print(f"[estimaciones] fallo moviendo {origen} -> {destino}:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="error del servidor, revisar el log")
    # Despues del COMMIT no hay vuelta atras por diseño: lo unico que queda
    # es borrar el origen, y su fallo deja un huerfano detectable, no un
    # estado inconsistente.
    try:
        os.remove(origen)
    except OSError:
        print(f"[estimaciones] PDF huérfano: no se pudo borrar {origen} "
              f"(la BD ya quedó consistente, borrarlo a mano)")
        traceback.print_exc()
    return resultado


@router.post("/api/estimaciones/pendientes-revision/aprobar")
async def aprobar_pendiente_revision(req: EstAprobarPendienteRequest,
                                     authorization: str = Header(None)):
    verificar_token(authorization)
    # Limites de entrada — se validan aca y no con max_length de pydantic
    # para responder 400 (entrada que el operador puede corregir), no el 422
    # generico de validacion de FastAPI.
    aprobado_por = req.aprobado_por.strip()
    motivo = req.motivo.strip()
    if len(aprobado_por) > 120:
        raise HTTPException(status_code=400, detail="quién aprueba: máximo 120 caracteres")
    if len(motivo) > 500:
        raise HTTPException(status_code=400, detail="motivo: máximo 500 caracteres")
    setup_est_db()
    archivo_pdf = _nombre_archivo_seguro(req.archivo_pdf)
    origen  = os.path.join(core.EST_PENDIENTES, archivo_pdf)
    destino = os.path.join(core.EST_PROCESADAS, archivo_pdf)
    # isolation_level=None (autocommit): el BEGIN IMMEDIATE explicito de
    # _mover_pdf_con_transaccion controla la transaccion completa, igual que
    # en /cerrar (issue #17)
    conn = sqlite3.connect(core.EST_DB_PATH, isolation_level=None)
    try:
        resultado = _mover_pdf_con_transaccion(
            conn,
            lambda c: _est_aprobar_pendiente(c, archivo_pdf, aprobado_por, motivo),
            origen, destino,
        )
    finally:
        conn.close()
    return JSONResponse(content={"ok": True, **resultado},
                        media_type="application/json; charset=utf-8")


@router.post("/api/estimaciones/pendientes-revision/revertir")
async def revertir_aprobacion_manual(req: EstRevertirAprobacionRequest,
                                     authorization: str = Header(None)):
    verificar_token(authorization)
    setup_est_db()
    conn = sqlite3.connect(core.EST_DB_PATH, isolation_level=None)
    try:
        # el archivo_pdf sale de la BD dentro de la primitiva; para armar las
        # rutas de origen/destino hay que leerlo primero (fuera de la
        # transaccion — la primitiva lo revalida adentro con sus guardas)
        fila = conn.execute(
            "SELECT archivo_pdf FROM facturas WHERE id_documento = ? AND aprobado_manual = 1",
            (req.id_documento,),
        ).fetchone()
        if fila is None:
            raise HTTPException(status_code=400,
                                detail="no existe una factura aprobada a mano con ese id_documento")
        archivo_pdf = _nombre_archivo_seguro(fila[0])
        origen  = os.path.join(core.EST_PROCESADAS, archivo_pdf)
        destino = os.path.join(core.EST_PENDIENTES, archivo_pdf)
        resultado = _mover_pdf_con_transaccion(
            conn,
            lambda c: _est_revertir_aprobacion(c, req.id_documento),
            origen, destino,
        )
    finally:
        conn.close()
    return JSONResponse(content={"ok": True, **resultado},
                        media_type="application/json; charset=utf-8")


# ── Issue #38 — descartar / reponer un pendiente que no corresponde facturar ──

class EstDescartarPendienteRequest(BaseModel):
    archivo_pdf: str
    descartado_por: str
    motivo: str


class EstReponerDescartadoRequest(BaseModel):
    archivo_pdf: str


@router.post("/api/estimaciones/pendientes-revision/descartar")
async def descartar_pendiente_revision(req: EstDescartarPendienteRequest,
                                       authorization: str = Header(None)):
    """Issue #38 — la salida legitima del bloqueo del cierre: un conduce del
    periodo que genuinamente no debe cobrarse se saca de pendientes_revision
    sin pasar por facturas. Espeja /aprobar en todo (mismos limites de
    entrada validados aca para responder 400 y no el 422 de pydantic, misma
    conexion en autocommit, misma secuencia copiar → COMMIT → borrar
    origen), pero contra descartadas/ en vez de procesadas/."""
    verificar_token(authorization)
    descartado_por = req.descartado_por.strip()
    motivo = req.motivo.strip()
    if len(descartado_por) > 120:
        raise HTTPException(status_code=400, detail="quién descarta: máximo 120 caracteres")
    if len(motivo) > 500:
        raise HTTPException(status_code=400, detail="motivo: máximo 500 caracteres")
    setup_est_db()
    archivo_pdf = _nombre_archivo_seguro(req.archivo_pdf)
    os.makedirs(core.EST_DESCARTADOS, exist_ok=True)
    origen  = os.path.join(core.EST_PENDIENTES, archivo_pdf)
    destino = os.path.join(core.EST_DESCARTADOS, archivo_pdf)
    conn = sqlite3.connect(core.EST_DB_PATH, isolation_level=None)
    try:
        resultado = _mover_pdf_con_transaccion(
            conn,
            lambda c: _est_descartar_pendiente(c, archivo_pdf, descartado_por, motivo),
            origen, destino,
        )
    finally:
        conn.close()
    return JSONResponse(content={"ok": True, **resultado},
                        media_type="application/json; charset=utf-8")


@router.post("/api/estimaciones/pendientes-revision/reponer")
async def reponer_pendiente_descartado(req: EstReponerDescartadoRequest,
                                       authorization: str = Header(None)):
    """Issue #38 — deshace un descarte. Sin esto descartar seria una puerta
    de una sola direccion y un clic equivocado borraria un conduce real."""
    verificar_token(authorization)
    setup_est_db()
    archivo_pdf = _nombre_archivo_seguro(req.archivo_pdf)
    os.makedirs(core.EST_DESCARTADOS, exist_ok=True)
    origen  = os.path.join(core.EST_DESCARTADOS, archivo_pdf)
    destino = os.path.join(core.EST_PENDIENTES, archivo_pdf)
    conn = sqlite3.connect(core.EST_DB_PATH, isolation_level=None)
    try:
        resultado = _mover_pdf_con_transaccion(
            conn,
            lambda c: _est_reponer_descartado(c, archivo_pdf),
            origen, destino,
        )
    finally:
        conn.close()
    return JSONResponse(content={"ok": True, **resultado},
                        media_type="application/json; charset=utf-8")


@router.get("/api/estimaciones/descartados")
async def listar_pendientes_descartados(authorization: str = Header(None)):
    """Issue #38 — el rastro permanente de los descartes, y la unica forma de
    llegar al boton Reponer desde el panel: sin este listado los conduces
    descartados desaparecen de la pantalla y la vuelta atras existiria solo
    por API. Mismo rol que /aprobados-manualmente para las aprobaciones."""
    verificar_token(authorization)
    setup_est_db()
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        cur = conn.execute(
            """SELECT archivo_pdf, id_documento, fecha, cliente, empresa, fase,
                      descripcion, cantidad, motivo_bloqueo, descartado_por,
                      descartado_motivo, descartado_fecha
               FROM pendiente_descartado ORDER BY descartado_fecha DESC, archivo_pdf"""
        )
        cols = [c[0] for c in cur.description]
        filas = [dict(zip(cols, row)) for row in cur.fetchall()]
        return JSONResponse(content={"total": len(filas), "filas": filas},
                            media_type="application/json; charset=utf-8")
    finally:
        conn.close()


@router.get("/api/estimaciones/aprobados-manualmente")
async def listar_aprobados_manualmente(authorization: str = Header(None)):
    """Issue #20 — el rastro permanente de las aprobaciones manuales, con la
    elegibilidad de la reversa precalculada por fila (la misma guarda que
    /revertir revalida al escribir — el listado puede quedar viejo).
    `motivo_no_reversible` esta siempre presente y vale null cuando
    `reversible` es true."""
    verificar_token(authorization)
    setup_est_db()
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        cur = conn.execute(
            """SELECT id_documento, archivo_pdf, fecha, cliente, empresa, fase,
                      descripcion, cantidad, motivo_bloqueo, aprobado_por,
                      aprobado_motivo, aprobado_fecha, aprobado_manual
               FROM facturas WHERE aprobado_manual = 1
               ORDER BY aprobado_fecha DESC"""
        )
        cols = [c[0] for c in cur.description]
        cortes: dict = {}
        filas = []
        for row in cur.fetchall():
            fila = dict(zip(cols, row))
            clave_fase = (fila.get("empresa"), fila.get("fase"))
            if clave_fase not in cortes:
                cortes[clave_fase] = _est_corte_de_conteo(conn, *clave_fase)
            motivo_nr = _est_motivo_no_reversible(conn, fila)
            fila.pop("aprobado_manual")  # implicita en el listado, no va en el esquema
            fila["cuenta_para_estimaciones"] = _cuenta_para_estimaciones(
                fila.get("fecha"), cortes[clave_fase])
            fila["corte"] = cortes[clave_fase]
            fila["reversible"] = motivo_nr is None
            fila["motivo_no_reversible"] = motivo_nr
            filas.append(fila)
        return JSONResponse(content={"total": len(filas), "filas": filas},
                            media_type="application/json; charset=utf-8")
    finally:
        conn.close()


# ── Issue #25 — aviso pasivo de resoluciones manuales desactualizadas ──

@router.get("/api/estimaciones/claves-resueltas")
async def listar_claves_resueltas(empresa: str = None, fase: str = None,
                                  authorization: str = Header(None)):
    """Issue #25 — revisa cada `clave_resuelta` guardada contra lo que el
    catalogo y los alias vigentes dirian hoy, y devuelve los tres desenlaces
    separados (`discrepan` / `sin_auto_match` / `coinciden`) mas un `resumen`.

    Avisa, no corrige: la conexion se abre en modo SOLO LECTURA (`mode=ro`) a
    proposito, asi ni un bug futuro en este camino puede tocar la BD. Por eso
    tampoco llama a `setup_est_db()` como los demas endpoints — crear la BD
    seria una escritura, y este endpoint no escribe.
    """
    verificar_token(authorization)
    try:
        conn = sqlite3.connect(Path(core.EST_DB_PATH).absolute().as_uri() + "?mode=ro", uri=True)
    except sqlite3.OperationalError:
        raise HTTPException(status_code=503, detail="estimaciones_db_no_disponible")
    try:
        datos = core._est_revisar_claves_resueltas(conn, empresa, fase)
    finally:
        conn.close()
    return JSONResponse(content=datos, media_type="application/json; charset=utf-8")


class ConfirmarRequest(BaseModel):
    session_id: str

@router.post("/api/estimaciones/confirmar")
async def confirmar_importacion(req: ConfirmarRequest, authorization: str = Header(None)):
    verificar_token(authorization)

    if req.session_id not in core.est_sessions:
        raise HTTPException(status_code=404, detail="Sesión no encontrada o expirada")

    sesion    = core.est_sessions.pop(req.session_id)
    registros = sesion["importadas"]
    setup_est_db()

    conn  = sqlite3.connect(core.EST_DB_PATH)
    confirmados = _confirmar_registros(conn, registros)
    conn.commit()
    conn.close()

    if confirmados:
        actualizar_excel_main(confirmados)

    return {"total": len(confirmados)}


@router.get("/api/estimaciones/excel/{filename}")
async def download_excel_est(filename: str, authorization: str = Header(None)):
    verificar_token(authorization)
    # Solo los Excel de validacion que genera /procesar-zip. Antes servia
    # cualquier archivo de estimaciones/data: la base, la lista de precios,
    # las plantillas (auditoria de seguridad 2026-10-07).
    if not re.fullmatch(r"validacion_[0-9a-f]{8}\.xlsx", filename or ""):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    filename = _nombre_archivo_seguro(filename)
    filepath = os.path.join(core.EST_DATA_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename
    )


@router.get("/api/estimaciones/progreso-macao2")
async def progreso_macao2(authorization: str = Header(None)):
    verificar_token(authorization)

    if not os.path.exists(core.PUENTE_PROGRESO_TXT):
        return {"activo": False}

    mtime = os.path.getmtime(core.PUENTE_PROGRESO_TXT)
    ahora = datetime.now().timestamp()
    if ahora - mtime > 60:
        return {"activo": False}

    with open(core.PUENTE_PROGRESO_TXT, "r", encoding="utf-8") as f:
        procesados = sum(1 for _ in f)

    if procesados >= core.PUENTE_TOTAL_MACAO2:
        return {"activo": False}

    errores = 0
    if os.path.exists(core.PUENTE_ERRORES_TXT):
        with open(core.PUENTE_ERRORES_TXT, "r", encoding="utf-8") as f:
            errores = sum(1 for _ in f)

    return {
        "activo": True,
        "procesados": procesados,
        "total": core.PUENTE_TOTAL_MACAO2,
        "porcentaje": round(procesados / core.PUENTE_TOTAL_MACAO2 * 100, 1),
        "errores": errores,
    }

@router.get("/api/estimaciones/vista-previa")
async def estimaciones_vista_previa(empresa: str, fase: str,
                                     fecha_desde: str = Query(pattern=core.RE_FECHA_ISO),
                                     fecha_hasta: str = Query(pattern=core.RE_FECHA_ISO),
                                     authorization: str = Header(None)):
    verificar_token(authorization)
    if fecha_desde > fecha_hasta:
        raise HTTPException(status_code=400, detail="rango_fechas_invalido")
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        resultado = _est_vista_previa(conn, empresa, fase, fecha_desde, fecha_hasta)
        return JSONResponse(content=resultado, media_type="application/json; charset=utf-8")
    finally:
        conn.close()

class EstProductoRequest(BaseModel):
    clave: str
    cantidad_proyecto: float
    acumulado_anterior_cantidad: float


class EstGenerarRequest(BaseModel):
    empresa: str
    fase: str
    fecha_desde: core.FechaISO
    fecha_hasta: core.FechaISO
    numero_estimacion: str
    fecha_estimacion: str
    semana: int
    productos: list[EstProductoRequest]
    reasignaciones: dict[str, str] = {}
    # Issue #12 — contratos paralelos (principal vs PPACT). Obligatorio (sin
    # default): Pydantic devuelve 422 automatico si falta o viene otro valor.
    # El frontend siempre manda "principal" cuando genera desde el formulario
    # unico de una fase sin PPACT — el resultado es identico al de antes de
    # este issue, solo cambia que el request ahora incluye este campo.
    serie: Literal["principal", "ppact"]
    # Claves del catalogo a excluir de ESTA estimacion (destildadas en la
    # pantalla de revision). El renglon igual sale completo en REO-01 con su
    # clave, concepto, U.M., Cant. Proyecto, P.U. y Acumulado Anterior — lo
    # unico que se omite es la columna "Esta Estimacion" (K) y su hoja de
    # generadores. No toca el catalogo ni la BD: aplica solo a esta generacion.
    excluidos: list[str] = []

@router.post("/api/estimaciones/generar")
async def estimaciones_generar(req: EstGenerarRequest, authorization: str = Header(None)):
    verificar_token(authorization)

    if req.fecha_desde > req.fecha_hasta:
        raise HTTPException(status_code=400, detail="rango_fechas_invalido")

    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        catalogo = _est_catalogo_fase(conn, req.empresa, req.fase)
        if not catalogo:
            raise HTTPException(status_code=404, detail="catalogo_no_definido")

        ruta_plantilla = _est_plantilla_de_fase(req.empresa, req.fase, catalogo)

        productos_por_clave = {p.clave: p for p in req.productos}
        faltantes = [c["clave"] for c in catalogo if c["clave"] not in productos_por_clave]
        if faltantes:
            raise HTTPException(status_code=400, detail={"error": "campos_faltantes", "detalle": faltantes})

        claves_catalogo_todas = {c["clave"] for c in catalogo}
        excluidos = set(req.excluidos)
        desconocidos = sorted(excluidos - claves_catalogo_todas)
        if desconocidos:
            # excluir una clave que no existe en esta fase casi seguro es un bug
            # del frontend o un request armado a mano — mejor fallar claro que
            # ignorarlo en silencio y generar un documento oficial distinto al
            # que el usuario creyo pedir
            raise HTTPException(status_code=400, detail={
                "error": "excluidos_desconocidos", "detalle": desconocidos})

        grupos = conn.execute(
            "SELECT descripcion, id_documento, fecha, cantidad, precio_unitario, clave_resuelta FROM facturas "
            "WHERE empresa = ? AND fase = ? AND fecha BETWEEN ? AND ?",
            (req.empresa, req.fase, req.fecha_desde, req.fecha_hasta)
        ).fetchall()

        if not grupos:
            raise HTTPException(status_code=422, detail={
                "error": "sin_facturas_en_periodo",
                "detalle": f"no hay facturas para {req.empresa}/{req.fase} entre {req.fecha_desde} y {req.fecha_hasta}",
            })

        catalogo_norm_a_clave = core._est_catalogo_norm_a_clave(catalogo, req.empresa, req.fase)
        claves_validas = {c["clave"] for c in catalogo}
        pu_catalogo = {c["clave"]: c["precio_unitario"] for c in catalogo}

        facturas_por_clave: dict[str, list] = {c["clave"]: [] for c in catalogo}
        resoluciones_a_persistir = []  # [(id_documento, clave)] — solo las que vinieron de reasignaciones esta vez
        sin_resolver = []
        for descripcion, id_documento, fecha, cantidad, precio_unitario, clave_resuelta in grupos:
            # Issue #36 — la prioridad clave_resuelta > auto-match se mantiene,
            # pero solo cuando la guardada sirve. Antes esto era un `or`, y el
            # cortocircuito hacia que una clave_resuelta obsoleta (apunta a una
            # clave que ya no existe en el catalogo) impidiera que el auto-match
            # se consultara siquiera: una factura cuya descripcion matchea
            # perfecto el catalogo de hoy caia igual en sin_resolver y
            # bloqueaba la generacion con facturas_sin_resolver.
            auto_match = catalogo_norm_a_clave.get(_est_normalizar(descripcion))
            clave = clave_resuelta if clave_resuelta in claves_validas else auto_match
            if clave not in claves_validas:
                # ni la guardada ni el auto-match sirven — se trata como no
                # resuelta, dandole a reasignaciones la oportunidad de
                # corregirla en esta misma generacion en vez de bloquear
                clave = None
            vino_de_reasignacion = False
            if not clave:
                clave = req.reasignaciones.get(descripcion)
                vino_de_reasignacion = clave is not None
            if not clave or clave not in claves_validas:
                sin_resolver.append(descripcion)
                continue
            if vino_de_reasignacion:
                resoluciones_a_persistir.append((id_documento, clave))
            # Una factura asignada a mano a otro producto (la descripcion no
            # esta en la lista de precios, p. ej. rev. 7" contra un producto
            # de rev. 6") se cobra al P.U. de ESE producto: la asignacion es
            # justamente para darle precio. Sin esto quedaba con precio NULL
            # y el chequeo de abajo bloqueaba con precios_faltantes aunque el
            # producto elegido si tiene precio. Las que matchean solas no
            # cambian: si les falta precio, sigue bloqueando.
            if precio_unitario is None and clave != auto_match:
                precio_unitario = pu_catalogo.get(clave)
            facturas_por_clave[clave].append({
                "id_documento": id_documento, "fecha": fecha,
                "cantidad": cantidad, "precio_unitario": precio_unitario
            })

        if sin_resolver:
            raise HTTPException(status_code=400, detail={"error": "facturas_sin_resolver", "detalle": sin_resolver})

        for id_documento, clave in resoluciones_a_persistir:
            conn.execute("UPDATE facturas SET clave_resuelta = ? WHERE id_documento = ?", (clave, id_documento))
        if resoluciones_a_persistir:
            conn.commit()

        # Issue #12 — contratos paralelos (principal vs PPACT): clasifica cada
        # factura del periodo en su serie con la misma funcion que usa
        # vista-previa (_est_clasificar_series) y se queda solo con las de
        # req.serie — nunca reemplaza el matching/reasignaciones de arriba
        # (out of scope del issue #12, se reusa tal cual), solo filtra el
        # resultado ya matcheado. Se recalcula DESPUES de persistir
        # resoluciones_a_persistir para que la clasificacion ya vea el
        # clave_resuelta actualizado (misma prioridad clave_resuelta >
        # auto-match que ya usa el matching de este endpoint, asi que toda
        # factura que llego hasta aqui matcheada deberia aparecer clasificada
        # — el default "principal" de abajo es solo un resguardo, no se
        # espera que se use nunca en la practica).
        clasificacion = _est_clasificar_series(conn, req.empresa, req.fase, catalogo, req.fecha_desde, req.fecha_hasta)
        id_a_serie = {f[0]: f[2] for f in clasificacion["facturas_periodo"]}
        for clave in facturas_por_clave:
            facturas_por_clave[clave] = [
                f for f in facturas_por_clave[clave]
                if id_a_serie.get(f["id_documento"], "principal") == req.serie
            ]

        # Productos destildados en la pantalla de revision: se les vacian las
        # facturas de ESTA generacion. Con eso alcanza para lo pedido, sin
        # tocar core.py: _est_generar_workbook() escribe clave, concepto, U.M.,
        # Cant. Proyecto, P.U. y Acumulado Anterior ANTES del `if facturas:`, y
        # deja adentro de ese `if` tanto la hoja de generadores como la columna
        # "Esta Estimacion" (K). O sea que el renglon sale completo igual y solo
        # se omite lo de este periodo, que es exactamente la regla acordada.
        # Ojo: esto NO borra nada de la BD — las facturas excluidas siguen
        # contando para el Acumulado de la proxima estimacion.
        for clave in excluidos:
            facturas_por_clave[clave] = []

        if not any(facturas_por_clave.values()):
            detalle = (
                f"no hay facturas de la serie '{req.serie}' para {req.empresa}/{req.fase} "
                f"entre {req.fecha_desde} y {req.fecha_hasta}"
            )
            if excluidos:
                detalle += " (o quedaron todas excluidas)"
            raise HTTPException(status_code=422, detail={
                "error": "sin_facturas_en_periodo", "detalle": detalle,
            })

        precios_faltantes = []
        excede_capacidad = []
        for clave, facturas in facturas_por_clave.items():
            if not facturas:
                continue
            if any(f["precio_unitario"] is None for f in facturas):
                precios_faltantes.append(clave)
            if len(facturas) > core.EST_RGO_SANITY_MAX:
                excede_capacidad.append({"clave": clave, "count": len(facturas)})

        if precios_faltantes:
            raise HTTPException(status_code=422, detail={"error": "precios_faltantes", "detalle": precios_faltantes})
        if excede_capacidad:
            # la capacidad de la hoja RGO es dinamica (se ajusta sola a la
            # cantidad real de facturas) — esto solo salta ante un rango de
            # fechas claramente mal elegido (miles de facturas), no un
            # volumen real de negocio
            raise HTTPException(status_code=422, detail={"error": "excede_capacidad_rgo", "detalle": excede_capacidad})

        # generar el archivo — trabajo de CPU/disco sincrono (openpyxl no es
        # async), se corre en un thread aparte para no congelar el event loop
        # del proceso entero (login, chat, etc.) mientras se arma una
        # estimacion grande — hallazgo real de la revision adversarial de
        # /ship, confirmado con MACAO 2 (900+ filas en una sola hoja RGO)
        # El nombre del escaneo de cada conduce, para anexar su foto al PDF. Va
        # en una consulta APARTE y tolerante a proposito: es un dato que solo
        # necesita el anexado, no la generacion, y meterlo en el SELECT de
        # arriba obligaba a que toda BD que genere una estimacion tenga la
        # columna. Si no esta, se avisa por el parte de escaneos y el resto
        # del documento sale igual.
        archivo_por_id = {}
        try:
            archivo_por_id = {
                fila[0]: fila[1] for fila in conn.execute(
                    "SELECT id_documento, archivo_pdf FROM facturas "
                    "WHERE empresa = ? AND fase = ? AND fecha BETWEEN ? AND ?",
                    (req.empresa, req.fase, req.fecha_desde, req.fecha_hasta)
                )
            }
        except sqlite3.OperationalError:
            print("[estimaciones] escaneos: la tabla facturas no tiene archivo_pdf, "
                  "el PDF sale sin los conduces anexados")
        for _clave, _facturas in facturas_por_clave.items():
            for _f in _facturas:
                _f["archivo_pdf"] = archivo_por_id.get(_f["id_documento"])

        total_facturas, productos_con_entregas, nombre, nombre_pdf, escaneos = await asyncio.to_thread(
            _est_generar_workbook, ruta_plantilla, req, catalogo, productos_por_clave, facturas_por_clave
        )

        return JSONResponse(content={
            "total_facturas": total_facturas,
            "productos_con_entregas": productos_con_entregas,
            "download_url": f"/api/estimaciones/descargar/{nombre}",
            "download_url_pdf": f"/api/estimaciones/descargar/{nombre_pdf}" if nombre_pdf else None,
            # parte del anexado de conduces escaneados: cuantos entraron y
            # cuales quedaron sin imagen. Va POR LA RUTA a proposito — la
            # leccion del #31 es que un campo que solo existe en core no le
            # llega a nadie.
            "escaneos": escaneos,
            # issue #16 AC #6 — mismo aviso que vista-previa: el acumulado
            # anterior incluye facturas del hueco fecha_base..fecha_desde
            # calculadas una por una, no con la regla de lote. No bloquea
            # la generacion, solo avisa.
            "aviso_acumulado_por_factura": clasificacion["aviso_acumulado_por_factura"],
        }, media_type="application/json; charset=utf-8")
    finally:
        conn.close()

# ── Issue #17 — cerrar / reabrir / consultar estimaciones cerradas ──
# Generar NO cierra (se genera varias veces mientras se revisa); cerrar es el
# paso explicito que escribe en el libro mayor estimacion_cerrada. El seed
# (estimacion_acumulado_base) no se toca en ningun caso.

class EstCerrarRequest(BaseModel):
    empresa: str
    fase: str
    numero_estimacion: str
    fecha_desde: core.FechaISO
    fecha_hasta: core.FechaISO
    # los avisos (re_cierre, hueco) no bloquean, pero exigen confirmacion
    # explicita: con avisos y confirmar_aviso=False la ruta responde 409 y no
    # escribe nada (criterio 13)
    confirmar_aviso: bool = False


class EstReabrirRequest(BaseModel):
    empresa: str
    fase: str
    numero_estimacion: str


@router.post("/api/estimaciones/cerrar")
async def estimaciones_cerrar(req: EstCerrarRequest, authorization: str = Header(None)):
    verificar_token(authorization)
    if req.fecha_desde > req.fecha_hasta:
        raise HTTPException(status_code=400, detail="rango_fechas_invalido")
    # garantiza que estimacion_cerrada exista antes de escribir (migracion
    # idempotente) — mismo patron que las demas rutas que escriben en la BD
    setup_est_db()
    # isolation_level=None (autocommit): _est_cerrar_estimacion() maneja su
    # propia transaccion con BEGIN IMMEDIATE explicito — DELETE + INSERT
    # atomicos, ver su docstring para el porque no es INSERT OR REPLACE
    conn = sqlite3.connect(core.EST_DB_PATH, isolation_level=None)
    try:
        catalogo = _est_catalogo_fase(conn, req.empresa, req.fase)
        if not catalogo:
            raise HTTPException(status_code=404, detail="catalogo_no_definido")
        # issue #96: el solapamiento se chequea ANTES de los avisos — si no,
        # el operador confirma un aviso de hueco y recien despues se entera de
        # que el cierre no se puede hacer. Se vuelve a chequear bajo el lock
        # dentro de _est_cerrar_estimacion().
        core._est_bloquear_si_solapa(conn, req.empresa, req.fase, req.numero_estimacion,
                                     req.fecha_desde, req.fecha_hasta)
        avisos = _est_avisos_cierre(conn, req.empresa, req.fase, req.numero_estimacion,
                                    req.fecha_desde, req.fecha_hasta)
        if avisos and not req.confirmar_aviso:
            raise HTTPException(status_code=409, detail={
                "error": "cierre_requiere_confirmacion", "avisos": avisos})
        cerradas = _est_cerrar_estimacion(conn, req.empresa, req.fase, catalogo,
                                          req.numero_estimacion, req.fecha_desde, req.fecha_hasta)
        return JSONResponse(content={"cerradas": cerradas, "avisos": avisos},
                            media_type="application/json; charset=utf-8")
    finally:
        conn.close()


@router.post("/api/estimaciones/reabrir")
async def estimaciones_reabrir(req: EstReabrirRequest, authorization: str = Header(None)):
    verificar_token(authorization)
    setup_est_db()
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        # reabrir borra TODAS las filas de (empresa, fase, numero_estimacion)
        # — es por estimacion completa de una fase, nunca por clave suelta
        cur = conn.execute(
            "DELETE FROM estimacion_cerrada WHERE empresa = ? AND fase = ? AND numero_estimacion = ?",
            (req.empresa, req.fase, req.numero_estimacion)
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="estimacion_no_cerrada")
        return JSONResponse(content={"borradas": cur.rowcount},
                            media_type="application/json; charset=utf-8")
    finally:
        conn.close()


@router.get("/api/estimaciones/cerradas")
async def estimaciones_cerradas(empresa: str, fase: str, authorization: str = Header(None)):
    verificar_token(authorization)
    setup_est_db()
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        filas = conn.execute(
            "SELECT numero_estimacion, fecha_desde, fecha_hasta, cerrada_en, clave, serie, cantidad "
            "FROM estimacion_cerrada WHERE empresa = ? AND fase = ? "
            "ORDER BY fecha_desde, numero_estimacion, serie, clave",
            (empresa, fase)
        ).fetchall()
        cierres: dict[str, dict] = {}
        for numero, desde, hasta, cerrada_en, clave, serie, cantidad in filas:
            c = cierres.setdefault(numero, {
                "numero_estimacion": numero, "fecha_desde": desde, "fecha_hasta": hasta,
                "cerrada_en": cerrada_en, "total_principal": 0.0, "total_ppact": 0.0,
                "filas": [],
            })
            c["filas"].append({"clave": clave, "serie": serie, "cantidad": cantidad})
            c[f"total_{serie}"] += cantidad
        return JSONResponse(content={"cerradas": list(cierres.values())},
                            media_type="application/json; charset=utf-8")
    finally:
        conn.close()


EST_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@router.get("/api/estimaciones/descargar/{nombre}")
async def estimaciones_descargar(nombre: str, authorization: str = Header(None)):
    verificar_token(authorization)
    nombre = _nombre_archivo_seguro(nombre)
    ruta = os.path.join(core.EST_REPORTES_DIR, nombre)
    if not os.path.exists(ruta):
        raise HTTPException(status_code=404, detail="archivo_no_encontrado")
    _, ext = os.path.splitext(nombre)
    media_type = EST_MEDIA_TYPES.get(ext.lower(), "application/octet-stream")
    return FileResponse(
        ruta,
        media_type=media_type,
        filename=nombre
    )
