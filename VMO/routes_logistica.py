"""
Rutas del modulo de Logistica — el historial de dias.

El modulo nacio 100% cliente y en lo esencial lo sigue siendo: **el calculo
del cumplimiento no esta aca ni en ninguna parte de Python**. Vive entero en
`static/logistica.logic.js`, corre en el navegador, y lo cubren las pruebas de
`tests/logistica/`. Estas rutas son un deposito: guardan lo que no es
derivable y lo devuelven.

Eso es deliberado y es lo que evita el problema clasico de tener el mismo
calculo en dos idiomas. Ver el comentario del bloque de Logistica en
`core.py`, que explica que se guarda y que no.
"""
import re
from datetime import datetime
import sqlite3
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

import core
from core import verificar_token

router = APIRouter()

RE_FECHA = r"^\d{4}-\d{2}-\d{2}$"

# Los motivos de la lista desplegable (2026-10-06). La misma lista vive en
# static/logistica.logic.js (MOTIVOS); un test compara las dos.
LOG_MOTIVOS = (
    "PROBLEMAS CLIMATICOS", "RETRASOS EN OBRA", "SIN COLOCACION", "ELEMENTO NO LISTO",
    "INCONVENIENTES EN OBRA", "AVERIA DE BOMBA", "AVERIA DE PLANTA", "DISPONIBILIDAD DE CAMIONES",
    "TARDANZA DE BOMBA", "REVISION CALIDAD", "RETRASO EN LA SALIDA DE PLANTA",
    # 2026-10-08, de la version 13 de la companera
    "LLEGADA TARDE PERSONAL", "ACCIDENTE", "DIFICIL ACCESO EN OBRA",
    "OBSTRUCCION ESTACIONAMIENTO DE LA BOMBA", "DISPONIBILIDAD DE MANGUERAS", "PRIORIDAD OTRO ELEMENTO",
    "PERMISOS DE OBRA",
    # 2026-10-09, pedido del usuario. CLIENTE PIDIO ANTES estuvo aca y se saco
    # el 2026-10-12: llegar antes ya cuenta como cumplido.
    "MISMO HORARIO ELEMENTOS", "PASE DE INGRESO A OBRA", "DESPACHO VMO", "INICIO DE CARGA VMO",
    "HORARIO PROGRAMADO",
    # 2026-10-12, pedido del usuario
    "CAMBIO DE PEDIDO",
    # 2026-10-21, pedido del usuario
    "SIN SISTEMA", "OPERACIONES",
    # 2026-10-23, pedido del usuario
    "PRIORIDAD OTRO SERVICIO",
)


class LogFilaProgramacion(BaseModel):
    cliente: str | None = None
    obra: str | None = None
    horaMin: float | None = None
    pedido: str | int | float | None = None
    cantidad: float = 0
    elemento: str | int | float | None = None
    producto: str | int | float | None = None
    prioridad: str | int | float | None = None
    zonaSheet: str | None = None
    # Bomba, vendedor y zona de la planilla (2026-10-06). Declarados aca por
    # lo mismo que despachado/pendiente: pydantic tira en silencio lo que no
    # declara.
    bomba: str | int | float | None = None
    vendedor: str | int | float | None = None
    zonaProg: str | None = None
    # Despachado y Pendiente vienen de la propia programacion y no son
    # derivables de nada mas que este guardado: `pendiente` es lo unico que
    # dice que un renglon quedo sin despachar sin deducirlo del cruce, y
    # `despachado` es la cuota con la que repartirCamiones() parte los
    # camiones entre las horas de una misma obra. Faltaban en este modelo, y
    # pydantic descarta lo que no declara: el navegador los mandaba y se
    # perdian aca, antes de llegar al SQL. Reabrir un dia guardado mostraba el
    # panel de no despachado VACIO — el 29-09 se tragaba 42 m3 en 2 renglones,
    # medido contra su Excel original.
    #
    # None y 0 son distintos y por eso el default es None: None es "la
    # planilla no trae la columna" —y ahi repartirCamiones() cae a la cantidad
    # programada a proposito— y 0 es "no se despacho nada".
    despachado: float | None = None
    pendiente: float | None = None


class LogFilaCargue(BaseModel):
    ficha: str | None = None
    horaMin: float | None = None
    cliente: str | None = None
    conduce: str | int | float | None = None
    elemento: str | int | float | None = None
    planta: str | None = None
    obra: str | None = None
    cantidad: float = 0


class LogPlanta(BaseModel):
    planta: str
    trayecto: float | None = None
    zona: str | None = None


class LogGuardarRequest(BaseModel):
    fecha: str = Field(pattern=RE_FECHA)
    cargue: float
    calidad: float
    tolerancia: float
    # Cuanto adelanto deja de ser cumplimiento (2026-10-02). Va declarado
    # EXPLICITAMENTE y no se deduce de `tolerancia`: pydantic descarta en
    # silencio lo que no declara, y asi ya se perdieron `despachado` y
    # `pendiente` entre el navegador y el SQL sin que fallara nada.
    #
    # El default es None y no 60 a proposito: None significa "este dia se
    # guardo sin ese supuesto" y deja que la pantalla aplique el suyo, mientras
    # que un 60 escrito aca le inventaria al dia una decision que nadie tomo.
    toleranciaAdelanto: float | None = None
    # Espaciamiento maximo entre camiones (2026-10-06): None por lo mismo.
    espaciamiento: float | None = None
    plantas: list[LogPlanta] = []
    programacion: list[LogFilaProgramacion]
    cargue_rows: list[LogFilaCargue]
    trayectoOverrides: dict[str, float] = {}
    observaciones: dict[str, str] = {}
    # Responsable por fila (2026-10-06). Literal: un valor fuera de la lista
    # es un 422 aca y no un CHECK que revienta a mitad del guardado.
    responsables: dict[str, Literal["VMO", "Cliente", "Externo"]] = {}
    motivos: dict[str, str] = {}
    # Las incumplidas pasadas a cumplido a mano (2026-10-26), por clave de fila.
    cumplidosManuales: list[str] = []
    # Mismo criterio que /api/estimaciones/cerrar: el aviso no bloquea, pero
    # sin confirmar_aviso la ruta responde 409 y NO escribe nada.
    confirmar_aviso: bool = False


def _texto(v):
    """Lo que solo se muestra se guarda como texto: en el Excel la misma
    columna viene numero un dia y texto al otro, y para mostrarla da igual."""
    return None if v is None else str(v)


@router.post("/api/logistica/dias")
async def logistica_guardar_dia(req: LogGuardarRequest, authorization: str = Header(None)):
    """Guarda el dia. Explicito a proposito: lo aprieta una persona cuando ya
    ajusto los trayectos, reviso los cruces marcados y escribio las
    observaciones. Guardar solo al subir los archivos dejaria en el historial
    el primer borrador en vez del trabajo terminado.
    """
    verificar_token(authorization)
    malos = sorted({v for v in req.motivos.values() if v not in LOG_MOTIVOS})
    if malos:
        raise HTTPException(status_code=422, detail={"error": "motivo_desconocido", "detalle": malos})
    if not req.programacion and not req.cargue_rows:
        raise HTTPException(status_code=400, detail="dia_vacio")
    for nombre, filas in (("programacion", req.programacion), ("cargue", req.cargue_rows)):
        if len(filas) > core.LOG_MAX_FILAS:
            raise HTTPException(status_code=400, detail={
                "error": "demasiadas_filas",
                "detalle": f"{nombre}: {len(filas)} filas, el tope es {core.LOG_MAX_FILAS}",
            })

    core.setup_logistica_db()
    conn = core._log_conn()
    try:
        avisos = core._log_avisos_guardar(conn, req.fecha)
        if avisos and not req.confirmar_aviso:
            # 409 y sin escribir: la decision de pisar un dia ya guardado se
            # toma viendo que hay adentro, no de memoria.
            return JSONResponse(status_code=409, content={"avisos": avisos})

        dia = req.model_dump()
        for fila in dia["programacion"]:
            for campo in ("pedido", "elemento", "producto", "prioridad"):
                fila[campo] = _texto(fila[campo])
        for fila in dia["cargue_rows"]:
            for campo in ("conduce", "elemento"):
                fila[campo] = _texto(fila[campo])

        resumen = core._log_guardar_dia(conn, dia)
    finally:
        conn.close()
    return {**resumen, "reemplazado": bool(avisos)}


@router.get("/api/logistica/dias")
async def logistica_listar_dias(authorization: str = Header(None)):
    """El indice del historial. Devuelve cuentas directas sobre lo guardado,
    nunca el porcentaje de cumplimiento: ese es derivado y lo calcula el
    navegador al abrir el dia, con la misma funcion de siempre."""
    verificar_token(authorization)
    core.setup_logistica_db()
    conn = core._log_conn()
    try:
        return {"dias": core._log_listar_dias(conn)}
    finally:
        conn.close()


@router.get("/api/logistica/dias/{fecha}")
async def logistica_leer_dia(fecha: str, authorization: str = Header(None)):
    """Un dia completo, listo para volver a cargar en el dashboard.

    Viene con los supuestos de ESE dia —incluido el trayecto y la zona de cada
    planta— y por eso reabrirlo reproduce lo que se vio ese dia, en vez de
    recalcularlo con los supuestos de hoy."""
    verificar_token(authorization)
    core.setup_logistica_db()
    conn = core._log_conn()
    try:
        dia = core._log_leer_dia(conn, fecha)
    finally:
        conn.close()
    if dia is None:
        raise HTTPException(status_code=404, detail="dia_no_encontrado")
    return dia


@router.delete("/api/logistica/dias/{fecha}")
async def logistica_borrar_dia(fecha: str, authorization: str = Header(None)):
    """Borra un dia del historial. La confirmacion la pide el Historial
    (escribir la fecha); aca se deja una copia del dia antes de borrarlo."""
    verificar_token(authorization)
    if not re.fullmatch(RE_FECHA, fecha):
        raise HTTPException(status_code=422, detail="fecha_invalida")
    core.setup_logistica_db()
    conn = core._log_conn()
    try:
        borrado = core._log_borrar_dia(conn, fecha)
    finally:
        conn.close()
    if borrado is None:
        raise HTTPException(status_code=404, detail="dia_no_encontrado")
    return borrado


# ================= INDICADORES (2026-10-28) =================
# Los dos reportes del sistema (CBSListas) que alimentan la pagina
# Indicadores. El navegador lee el Excel con SheetJS y manda las filas; aca se
# validan y se guardan por rango. El calculo, como todo en Logistica, esta en
# logistica.logic.js (indicadoresDelPeriodo).

class LogFilaBombeo(BaseModel):
    fecha: str = Field(pattern=RE_FECHA)
    equipo: str = Field(min_length=1, max_length=40)
    nombre: str | None = Field(default=None, max_length=80)
    m3: float = Field(ge=0)


class LogFilaTiempo(BaseModel):
    fecha: str = Field(pattern=RE_FECHA)
    ordComp: str | None = Field(default=None, max_length=40)
    planta: str | None = Field(default=None, max_length=60)
    cliente: str | None = Field(default=None, max_length=200)
    horaIni: float | None = Field(default=None, ge=0, lt=1440)
    horaFin: float | None = Field(default=None, ge=0, lt=1440)
    cantidad: float = Field(ge=0)
    totalIn: float = Field(ge=0)
    logro: str | None = Field(default=None, max_length=10)
    totalDespachado: float = Field(ge=0)
    viajesProgramados: float | None = Field(default=None, ge=0)
    viajesEfectuados: float = Field(ge=0)
    bomba: str | None = Field(default=None, max_length=40)


class LogBombeoRequest(BaseModel):
    desde: str = Field(pattern=RE_FECHA)
    hasta: str = Field(pattern=RE_FECHA)
    filas: list[LogFilaBombeo] = Field(max_length=core.LOG_MAX_FILAS)


class LogTiemposRequest(BaseModel):
    desde: str = Field(pattern=RE_FECHA)
    hasta: str = Field(pattern=RE_FECHA)
    filas: list[LogFilaTiempo] = Field(max_length=core.LOG_MAX_FILAS)


def _ind_validar_rango(desde: str, hasta: str, fechas: list[str]):
    """El rango tiene que venir derecho y cubrir todas las filas: lo que se
    borra es el rango, y una fila de afuera quedaria pisando otra fecha."""
    if desde > hasta:
        raise HTTPException(status_code=422, detail="rango_invertido")
    fuera = sorted({f for f in fechas if not (desde <= f <= hasta)})
    if fuera:
        raise HTTPException(status_code=422, detail={"error": "fila_fuera_del_rango", "detalle": fuera[:5]})


def _ind_guardar(tabla: str, desde: str, hasta: str, filas: list[tuple]):
    core.setup_logistica_db()
    conn = core._log_conn()
    try:
        return core._log_ind_reemplazar(conn, tabla, desde, hasta, filas)
    finally:
        conn.close()


@router.post("/api/logistica/indicadores/bombeo")
async def logistica_subir_bombeo(req: LogBombeoRequest, authorization: str = Header(None)):
    """"Metros bombeados por equipo": reemplaza las fechas del rango."""
    verificar_token(authorization)
    _ind_validar_rango(req.desde, req.hasta, [f.fecha for f in req.filas])
    claves = [(f.fecha, f.equipo) for f in req.filas]
    if len(set(claves)) != len(claves):
        raise HTTPException(status_code=422, detail="equipo_repetido_en_un_dia")
    return _ind_guardar("logistica_bombeo", req.desde, req.hasta,
                        [(f.fecha, f.equipo, f.nombre, f.m3) for f in req.filas])


@router.post("/api/logistica/indicadores/tiempos")
async def logistica_subir_tiempos(req: LogTiemposRequest, authorization: str = Header(None)):
    """"Cumplimiento de tiempos de despacho": reemplaza las fechas del rango."""
    verificar_token(authorization)
    _ind_validar_rango(req.desde, req.hasta, [f.fecha for f in req.filas])
    return _ind_guardar("logistica_tiempo_pedido", req.desde, req.hasta, [
        (f.fecha, i, f.ordComp, f.planta, f.cliente, f.horaIni, f.horaFin, f.cantidad, f.totalIn,
         f.logro, f.totalDespachado, f.viajesProgramados, f.viajesEfectuados, f.bomba)
        for i, f in enumerate(req.filas)])


@router.get("/api/logistica/indicadores")
async def logistica_leer_indicadores(desde: str, hasta: str, authorization: str = Header(None)):
    verificar_token(authorization)
    if not (re.fullmatch(RE_FECHA, desde) and re.fullmatch(RE_FECHA, hasta)):
        raise HTTPException(status_code=422, detail="fecha_invalida")
    core.setup_logistica_db()
    conn = core._log_conn()
    try:
        return core._log_ind_leer(conn, desde, hasta)
    finally:
        conn.close()


# ================= REPORTE DE CANCELADOS (2026-10-12) =================
# Las filas y el resumen llegan hechos por reporteCancelados(), en
# logistica.logic.js: la ruta solo los vuelve un Excel con formato.

class LogFilaCancelado(BaseModel):
    fecha: str = Field(pattern=RE_FECHA)
    semana: str = ""
    horaFraccion: float | None = Field(default=None, ge=0, lt=1)
    cliente: str = ""
    obra: str = ""
    vendedor: str = ""
    zona: str = ""
    elemento: str = ""
    servicio: str = ""
    producto: str = ""
    volumen: float = 0
    razon: str = ""
    responsable: str = ""
    motivo: str = ""


class LogGrupoCancelados(BaseModel):
    nombre: str
    entregas: int
    m3Cancelado: float
    pct: float


class LogDiaCancelados(BaseModel):
    fecha: str = Field(pattern=RE_FECHA)
    entregas: int
    m3Cancelado: float


class LogResumenCancelados(BaseModel):
    diasRevisados: int
    diasConCancelados: int
    entregas: int
    m3Cancelado: float
    porDia: list[LogDiaCancelados]
    porMotivo: list[LogGrupoCancelados]
    porResponsable: list[LogGrupoCancelados]


class LogReporteCanceladosRequest(BaseModel):
    desde: str = Field(pattern=RE_FECHA)
    hasta: str = Field(pattern=RE_FECHA)
    encabezado: list[str] = Field(min_length=14, max_length=14)
    filas: list[LogFilaCancelado]
    resumen: LogResumenCancelados


@router.post("/api/logistica/reporte-cancelados")
async def logistica_reporte_cancelados(req: LogReporteCanceladosRequest,
                                       authorization: str = Header(None)):
    """Devuelve el .xlsx del Reporte de cancelados. No lee la base: el
    navegador ya tiene los dias y el calculo, y aca solo se da formato."""
    verificar_token(authorization)
    if req.desde > req.hasta:
        raise HTTPException(status_code=400, detail="rango_invertido")
    if len(req.filas) > core.LOG_MAX_FILAS:
        raise HTTPException(status_code=400, detail={
            "error": "demasiadas_filas",
            "detalle": f"{len(req.filas)} filas, el tope es {core.LOG_MAX_FILAS}"})
    contenido = core.log_reporte_cancelados_xlsx(
        req.desde, req.hasta, req.encabezado,
        [f.model_dump() for f in req.filas], req.resumen.model_dump())
    nombre = f"Cancelados_VMO_{req.desde}_al_{req.hasta}.xlsx"
    return Response(
        content=contenido,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


# ── Reporte del dia en PDF (2026-10-15) ──────────────────────────────────
# Los numeros llegan hechos por reporteDelDia(), en logistica.logic.js — la
# misma cuenta que la pantalla del dia y Estadisticas. Aca solo se dibujan.

class LogBloqueDia(BaseModel):
    nombre: str = Field(max_length=40)
    pct: int | None = Field(default=None, ge=0, le=100)
    pctPedidos: int | None = Field(default=None, ge=0, le=100)
    pedidos: int = Field(ge=0)
    pedidosCumplidos: int = Field(ge=0)
    m3: float = Field(ge=0)
    m3Cumplidos: float = Field(ge=0)
    incumplidos: int = Field(ge=0)
    m3Despachado: float = Field(ge=0)
    cargues: int = Field(ge=0)
    camiones: float = Field(ge=0)   # en un rango, promedio por dia


class LogNoEvaluableDia(BaseModel):
    estado: str = Field(max_length=40)
    entregas: int = Field(ge=0)


class LogGrupoDia(BaseModel):
    nombre: str = Field(max_length=120)
    entregas: int = Field(ge=0)
    m3: float = Field(ge=0)
    pct: int = Field(ge=0, le=100)
    pctAcumulado: int = Field(ge=0, le=100)
    detalle: str = Field(default="", max_length=600)   # "Cliente 2, VMO 1" o los motivos


class LogIncumplidasServicio(BaseModel):
    servicio: str = Field(max_length=20)
    entregas: int = Field(ge=0)
    m3: float = Field(ge=0)
    companias: list[LogGrupoDia] = Field(default_factory=list, max_length=1000)


class LogIncumplidasResponsable(BaseModel):
    responsable: Literal["Cliente", "VMO"]
    entregas: int = Field(ge=0)
    servicios: list[LogIncumplidasServicio] = Field(default_factory=list, max_length=2)


class LogCoberturaDia(BaseModel):
    incumplidos: int = Field(ge=0)
    sinMotivo: int = Field(ge=0)
    sinResponsable: int = Field(ge=0)


class LogEntregaDia(BaseModel):
    fecha: str = Field(default="", pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    cliente: str = Field(default="", max_length=300)
    obra: str = Field(default="", max_length=300)
    elemento: str = Field(default="", max_length=120)
    servicio: str = Field(default="", max_length=20)
    horaProg: float | None = None
    cantProg: float = 0
    cantReal: float = 0
    cargues: int = Field(default=0, ge=0)
    primerCargue: float | None = None
    planta: str = Field(default="", max_length=80)
    zona: str = Field(default="", max_length=40)
    llegada: float | None = None
    diff: float | None = None
    estado: str = Field(max_length=40)
    responsable: str = Field(default="", max_length=20)
    motivo: str = Field(default="", max_length=120)
    observacion: str = Field(default="", max_length=1000)


class LogSupuestosDia(BaseModel):
    cargue: float | None = None
    calidad: float | None = None
    tolerancia: float | None = None
    ajusteHora: float | None = None
    # En un rango, los supuestos que cambiaron entre dias (van en null).
    varian: list[Literal["cargue", "calidad", "tolerancia"]] = Field(default_factory=list)


class LogNombresDia(BaseModel):
    pct: str = Field(max_length=60)
    pctPedidos: str = Field(max_length=60)


class LogReporteDiaRequest(BaseModel):
    # Un dia es desde == hasta (2026-10-21: antes era un solo `fecha`).
    desde: str = Field(pattern=RE_FECHA)
    hasta: str = Field(pattern=RE_FECHA)
    supuestos: LogSupuestosDia
    nombres: LogNombresDia
    bloques: list[LogBloqueDia] = Field(min_length=1, max_length=10)
    porDia: list[LogBloqueDia] = Field(default_factory=list, max_length=400)
    noEvaluables: list[LogNoEvaluableDia] = Field(default_factory=list, max_length=10)
    porResponsable: list[LogGrupoDia] = Field(default_factory=list, max_length=10)
    porMotivo: list[LogGrupoDia] = Field(default_factory=list, max_length=100)
    # Cliente y VMO, cada uno en Con bomba / Directo y por compania (2026-10-22).
    incumplidasPorResponsable: list[LogIncumplidasResponsable] = Field(default_factory=list, max_length=2)
    cobertura: LogCoberturaDia
    entregas: list[LogEntregaDia]


@router.post("/api/logistica/reporte-dia")
async def logistica_reporte_dia(req: LogReporteDiaRequest, authorization: str = Header(None)):
    """Devuelve el PDF del Reporte del dia, o de un rango de dias. No lee la
    base: el navegador ya tiene los dias y el calculo, y aca solo se dibuja."""
    verificar_token(authorization)
    try:
        datetime.strptime(req.desde, "%Y-%m-%d")
        datetime.strptime(req.hasta, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="fecha_invalida")
    if req.desde > req.hasta:
        raise HTTPException(status_code=400, detail="rango_invertido")
    if len(req.entregas) > core.LOG_MAX_FILAS:
        raise HTTPException(status_code=400, detail={
            "error": "demasiadas_filas",
            "detalle": f"{len(req.entregas)} entregas, el tope es {core.LOG_MAX_FILAS}"})
    contenido = core.log_reporte_dia_pdf(req.model_dump())
    nombre = core.log_nombre_reporte_dia(req.desde, req.hasta)
    return Response(
        content=contenido, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
