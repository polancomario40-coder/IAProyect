# by a_oller
"""
core.py — config, auth, estado global, helpers y TODA la logica de negocio
compartida entre routes_conduces.py y routes_estimaciones.py.

Nace del split de main.py (issue #4, Fase 2) para evitar imports circulares:
si routes_conduces.py hiciera `from main import generar_reporte` y main.py
hiciera `from routes_conduces import router`, Python fallaria con
ImportError (circular import) — main.py no termina de ejecutarse antes de
que routes_conduces.py intente importar de el. Al mover todo lo que no es
un handler de ruta aca, ambos routers importan de un solo lugar sin ciclo.

Los routers NUNCA hacen `from core import DB_PATH` (ni de ningun otro
config mutable — REPORTES_DIR, FACTURAS_DIR, EST_DB_PATH, EST_DATA_DIR,
active_tokens, login_attempts, est_sessions, LOGIN_USER/PASS, client,
etc.) para no copiar el VALOR al importar: los tests monkeypatchean estos
nombres como `core.DB_PATH = ...`, y una copia importada por valor no ve
ese cambio (el bug de "parcheaste la copia equivocada" que motivo este
diseño). En su lugar los routers hacen `import core` y referencian
`core.DB_PATH` etc. en el cuerpo de cada ruta. Funciones (generar_reporte,
verificar_token, ...) si son seguras de importar con `from core import x`
— una funcion siempre resuelve sus globals contra el modulo donde fue
DEFINIDA (este archivo), sin importar desde donde se la llame.
"""
import os
import re
import io
import json
import base64
import hashlib
import shutil
import sqlite3
import subprocess
import traceback
import unicodedata
import asyncio
import zipfile
import fitz  # pymupdf — anexar los conduces escaneados al PDF
from copy import copy as _copiar_estilo
from html import escape as _esc_html
from datetime import datetime, date, timedelta, timezone
from typing import Annotated, Optional

import anthropic
import openpyxl
import xlrd
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.formula import ArrayFormula
from openpyxl.worksheet.pagebreak import Break
from dotenv import load_dotenv
from fastapi import Header, HTTPException
from pydantic import Field

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
REPORTES_DIR = os.path.join(BASE_DIR, "conduces", "reportes")
FACTURAS_DIR = os.path.join(BASE_DIR, "conduces", "facturas")
DB_PATH      = os.path.join(BASE_DIR, "conduces", "db", "conduces.db")
os.makedirs(FACTURAS_DIR, exist_ok=True)

# Estimaciones
EST_DB_PATH      = os.path.join(BASE_DIR, "estimaciones", "db", "estimaciones.db")
EST_PROCESADAS   = os.path.join(BASE_DIR, "estimaciones", "facturas", "procesadas")
EST_PENDIENTES   = os.path.join(BASE_DIR, "estimaciones", "facturas", "pendientes_revision")
# Issue #38 — el PDF de un pendiente descartado a mano (no corresponde
# facturarlo: sin sello, invalido, duplicado). Directorio propio, hermano de
# pendientes_revision/ y procesadas/: un descartado NO es una factura y no
# puede terminar en procesadas/, ni quedar suelto donde /aprobar lo vuelva a
# encontrar.
EST_DESCARTADOS  = os.path.join(BASE_DIR, "estimaciones", "facturas", "descartadas")
EST_DATA_DIR     = os.path.join(BASE_DIR, "estimaciones", "data")
EST_REPORTES_DIR = os.path.join(BASE_DIR, "estimaciones", "reportes")
EST_EXCEL_MAIN   = os.path.join(BASE_DIR, "estimaciones", "data", "estimaciones_main.xlsx")
# Logistica — la base del historial del dia (2026-09-30). El modulo nacio 100%
# cliente y sin BD; esto NO cambia eso: el calculo del cumplimiento sigue
# viviendo entero en static/logistica.logic.js y corriendo en el navegador. La
# base es un deposito, no calcula nada.
#
# Por que existe: el dashboard leia dos Excel, mostraba el dia y se olvidaba de
# todo con un F5, asi que no habia manera de preguntar como venia el mes.
LOG_DB_PATH = os.path.join(BASE_DIR, "logistica", "db", "logistica.db")
# Tope de cordura por archivo del dia. El mayor lote real medido hasta hoy
# ronda las 2.000 filas de cargue, asi que 20.000 es holgado y al mismo tiempo
# impide que un POST equivocado llene la base.
LOG_MAX_FILAS = 20000

VISION_MODEL_STD = "claude-haiku-4-5-20251001"
VISION_MODEL_PRO = "claude-opus-5"
VISION_MODEL_VERIFICACION = "claude-sonnet-5"
EST_ZIP_MAX_BYTES = 50 * 1024 * 1024
EST_ZIP_MAX_PDFS = 1000
# Issue #15 — el Excel de conduces se sube junto con el ZIP en /procesar-zip,
# obligatorio, con su propio tope (no comparte EST_ZIP_MAX_BYTES: es un
# archivo distinto, con un formato y un tamano tipico muy distintos).
EST_EXCEL_MAX_BYTES = 25 * 1024 * 1024
EST_PDF_MAX_BYTES_DESCOMPRIMIDO = 20 * 1024 * 1024  # por PDF individual, no por el ZIP
# Tope agregado sobre TODOS los PDFs descomprimidos de un mismo lote — el tope
# por-PDF de arriba no alcanza solo: con EST_ZIP_MAX_PDFS=1000 PDFs de hasta
# 20MB cada uno, un ZIP malicioso podia retener ~20GB en memoria (cada PDF
# valido se guarda con sus bytes en sesion, para reintento/importacion) aunque
# el ZIP comprimido pesara menos de 50MB. 1GB alcanza de sobra para 1000 PDFs
# reales (documentos escaneados de una pagina, tipicamente unos pocos cientos
# de KB cada uno) y bloquea el caso agregado malicioso.
EST_ZIP_TOTAL_DESCOMPRIMIDO_MAX_BYTES = 1024 * 1024 * 1024
# Topes de gasto y de memoria (auditoria de seguridad 2026-10-07), pensados
# para la app publicada:
# - Paginas por PDF: Vision cobra por pagina, y un conduce es de UNA (medido el
#   2026-10-07: 1854 de 1854 en procesadas/). Un PDF de 100 paginas costaba
#   100 veces mas y no es un conduce.
# - Filas del Excel: openpyxl las recorre todas y cada una queda en memoria
#   dentro de la sesion. El Excel real tiene unos miles.
# - Sesiones: cada /procesar-zip deja en memoria los PDFs del lote hasta que
#   se incorpora, y antes no se liberaban nunca — dos o tres lotes grandes
#   abandonados tumbaban el servidor.
EST_PDF_MAX_PAGINAS = 3
EST_EXCEL_MAX_FILAS = 200_000
EST_SESION_TTL_MIN = 120
EST_MAX_SESIONES = 5
os.makedirs(EST_DATA_DIR,   exist_ok=True)
os.makedirs(EST_PROCESADAS, exist_ok=True)
os.makedirs(EST_PENDIENTES, exist_ok=True)
os.makedirs(EST_DESCARTADOS, exist_ok=True)
os.makedirs(EST_REPORTES_DIR, exist_ok=True)


def _encontrar_soffice():
    """Ubica el binario de LibreOffice headless — mismo helper que ya usaban
    (duplicado) tests/test_calculo_estimacion.py y
    tests/test_rgo_capacidad_dinamica.py para forzar el recalculo real de
    las plantillas. Se centraliza aca (issue #6) para reutilizarlo tambien
    en la conversion a PDF del generador de Estimaciones."""
    encontrado = shutil.which("soffice") or shutil.which("soffice.exe")
    if encontrado:
        return encontrado
    candidatos = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for c in candidatos:
        if os.path.exists(c):
            return c
    return None


EST_SOFFICE = _encontrar_soffice()

est_sessions: dict = {}


def _est_purgar_sesiones(ahora: datetime | None = None):
    """Libera las sesiones de /procesar-zip vencidas (EST_SESION_TTL_MIN desde
    que se crearon). Una con reproceso en curso no se toca: la tarea de fondo
    la esta usando."""
    ahora = ahora or datetime.now()
    limite = ahora - timedelta(minutes=EST_SESION_TTL_MIN)
    for sid in list(est_sessions):
        sesion = est_sessions[sid]
        if (sesion.get("reprocess_progress") or {}).get("activo"):
            continue
        if sesion.get("creada", ahora) < limite:
            est_sessions.pop(sid, None)

# Progreso Vision MACAO 2 (importar_puente.py)
PUENTE_PROGRESO_TXT = os.path.join(BASE_DIR, "conduces", "data", "puente_progreso.txt")
PUENTE_ERRORES_TXT  = os.path.join(BASE_DIR, "conduces", "data", "puente_errores_sello.txt")
PUENTE_TOTAL_MACAO2 = 2752

# Fechas que llegan de afuera (formularios, query string, herramientas del
# chat). Van pegadas al NOMBRE de los archivos que se generan
# (`reporte_general_{desde}_{hasta}.html`, la factura, el entregable de la
# estimacion), asi que una "fecha" como `x/../../static/pwn` escribia fuera de
# la carpeta: en Windows dejaba un .html servido por la propia app. Auditoria
# de seguridad 2026-10-07.
RE_FECHA_ISO = r"^\d{4}-\d{2}-\d{2}$"
FechaISO = Annotated[str, Field(pattern=RE_FECHA_ISO)]


def _exigir_fechas_iso(*fechas):
    """Segunda barrera, en las funciones que arman nombres de archivo: el chat
    las llama con lo que devuelve el modelo, que no pasa por pydantic."""
    for f in fechas:
        if f and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(f)):
            raise ValueError(f"Fecha inválida: {f!r} (se espera AAAA-MM-DD)")


LOGIN_USER = os.getenv("LOGIN_USER")
LOGIN_PASS = os.getenv("LOGIN_PASS")
active_tokens: dict[str, datetime] = {}  # token -> fecha de creacion
TOKEN_TTL_HORAS = 24

login_attempts: dict[str, dict] = {}  # ip -> {"fallos": int, "bloqueado_hasta": datetime|None}
LOGIN_MAX_INTENTOS = 5
LOGIN_BLOQUEO_MINUTOS = 15

def verificar_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autorizado")
    token = authorization.split(" ", 1)[1]
    creado = active_tokens.get(token)
    if creado is None:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    if (datetime.now() - creado).total_seconds() > TOKEN_TTL_HORAS * 3600:
        del active_tokens[token]
        raise HTTPException(status_code=401, detail="Token inválido o expirado")


def _nombre_archivo_seguro(nombre: str) -> str:
    """Evita path traversal en endpoints de descarga — solo se permite un
    nombre de archivo simple, sin componentes de ruta."""
    if not nombre or ".." in nombre or "/" in nombre or "\\" in nombre or nombre != os.path.basename(nombre):
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido")
    return nombre


def _slug_archivo(texto: str, largo_max: int = 40) -> str:
    """Componente seguro de nombre de archivo — solo alfanumerico, sin
    limite de caracteres original del texto (los IDs de conduce ya no
    tienen tope de longitud desde la unificacion de la regla de validacion,
    ver CLAUDE.md 2026-08-21), asi que se trunca aca para no producir un
    nombre de archivo invalido en Windows o un "File name too long"."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", (texto or "").strip()).strip("_")
    return (slug or "x")[:largo_max]


def _slug_compania(compania: str) -> str:
    """Convierte un nombre de compañía en un componente seguro de nombre de
    archivo — evita que comas, comillas, barras u otros caracteres rompan la
    generación/descarga del reporte. Sufijo de hash corto para que dos
    compañías distintas que solo se diferencian por puntuación (ej.
    "ACME, SRL" vs "ACME SRL") nunca colisionen en el mismo nombre de
    archivo — la caché de reportes serviría el reporte de una compañía a
    la otra si eso pasara."""
    sufijo = hashlib.sha1((compania or "").encode("utf-8")).hexdigest()[:6]
    return f"{_slug_archivo(compania, largo_max=60)}_{sufijo}"

SYSTEM_PROMPT = """Eres un asistente para validar conduces de una hormigonera.

Cuando el usuario te dé IDs de conduces, usa la herramienta consultar_conduces para verificar su estado. Pasa los IDs exactamente como el usuario los escribió, sin modificarlos ni partirlos.
Después de consultar, responde solo con un resumen breve en texto plano, sin emojis ni símbolos especiales.

Cuando el usuario pida un reporte general, usa la herramienta generar_reporte.
Cuando el usuario pida un reporte de una compañía específica, usa la herramienta generar_reporte_compania con el nombre exacto de esa compañía.
Después de generar cualquier reporte, informa al usuario que está listo para descargar.

Nunca uses emojis ni caracteres especiales. Siempre responde en español."""

TOOLS = [
    {
        "name": "consultar_conduces",
        "description": "Consulta el estado de uno o varios conduces en la base de datos por su ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de IDs de conduces a consultar"
                }
            },
            "required": ["ids"]
        }
    },
    {
        "name": "generar_reporte",
        "description": "Genera un reporte general de todos los conduces. Acepta rango de fechas opcional.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fecha_desde": {
                    "type": "string",
                    "description": "Fecha inicial del rango en formato YYYY-MM-DD (opcional)"
                },
                "fecha_hasta": {
                    "type": "string",
                    "description": "Fecha final del rango en formato YYYY-MM-DD (opcional)"
                }
            }
        }
    },
    {
        "name": "generar_reporte_compania",
        "description": "Genera un reporte de conduces filtrado por una compañía específica. Acepta rango de fechas opcional.",
        "input_schema": {
            "type": "object",
            "properties": {
                "compania": {
                    "type": "string",
                    "description": "Nombre exacto de la compañía"
                },
                "fecha_desde": {
                    "type": "string",
                    "description": "Fecha inicial del rango en formato YYYY-MM-DD (opcional)"
                },
                "fecha_hasta": {
                    "type": "string",
                    "description": "Fecha final del rango en formato YYYY-MM-DD (opcional)"
                }
            },
            "required": ["compania"]
        }
    }
]

def consultar_conduces(ids: list[str]) -> str:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    resultados = []

    for id_conduce in ids:
        id_conduce = id_conduce.strip()
        if len(id_conduce) < 4:
            resultados.append({"id_conduce": id_conduce, "estado": "INVALIDO", "error": "ID demasiado corto"})
            continue
        cursor.execute(
            "SELECT id_conduce, fecha, producto, compania, precio, cantidad, estado, id_transporte FROM conduces WHERE id_conduce = ?",
            (id_conduce,)
        )
        row = cursor.fetchone()
        if row is None:
            resultados.append({"id_conduce": id_conduce, "estado": "NO ENCONTRADO"})
        else:
            resultado = {
                "id_conduce": row[0],
                "fecha": row[1],
                "producto": row[2],
                "compania": row[3],
                "precio": row[4],
                "cantidad": row[5],
                "estado": row[6].upper()
            }
            if row[7]:
                resultado["id_transporte"] = row[7]
            resultados.append(resultado)

    conn.close()
    return json.dumps(resultados, ensure_ascii=False)


def _monto_y_sin_precio(rows, filtro=None):
    """Suma precio x cantidad sobre filas de `conduces`, y devuelve ademas
    cuantas de esas filas entraron SIN precio.

    Issue #31: la formula `(precio or 0) * (cantidad or 0)` estaba repetida
    seis veces inline en tres funciones distintas, y ninguna avisaba que un
    precio NULL suma $0. Un conduce sin precio no vale cero — vale un numero
    que no sabemos. Medido el 2026-08-31: 1.632 de 3.523 conduces (46,3%)
    tienen precio NULL, todos de julio 2026, porque la columna XCosto del
    Excel de origen vino vacia; el Monto Pendiente los contaba como $0 y
    quedaba ~38% corto sin decirlo.

    El conteo viaja JUNTO al monto a proposito: quien lo muestra tiene que
    poder decir sobre cuantas filas esta calculado. Devolver solo el monto es
    lo que dejo pasar el problema durante meses.

    rows: filas de `conduces` con precio en r[4] y cantidad en r[5].
    filtro: predicado opcional sobre la fila (ej. solo las no pagadas).
    """
    monto = 0.0
    sin_precio = 0
    for r in rows:
        if filtro is not None and not filtro(r):
            continue
        if r[4] is None:
            sin_precio += 1
        monto += (r[4] or 0) * (r[5] or 0)
    return monto, sin_precio


def _nota_sin_precio(sin_precio, total, singular="conduce"):
    """Texto del aviso para las tarjetas de monto. Cadena vacia si no falta
    ninguno, para que el HTML no muestre un aviso vacio."""
    if not sin_precio:
        return ""
    # el plural concuerda con el TOTAL, no con el faltante: se lee "1 de 2
    # conduces", no "1 de 2 conduce".
    plural = singular if total == 1 else singular + "s"
    contados = "contado" if sin_precio == 1 else "contados"
    return (f'<div class="nota-sin-precio">incompleto: {sin_precio} de {total} '
            f'{plural} sin precio, {contados} como $0</div>')


def generar_reporte(fecha_desde: str = None, fecha_hasta: str = None) -> str:
    _exigir_fechas_iso(fecha_desde, fecha_hasta)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if fecha_desde and fecha_hasta:
        cursor.execute(
            "SELECT id_conduce, fecha, producto, compania, precio, cantidad, estado, id_transporte FROM conduces WHERE fecha BETWEEN ? AND ? ORDER BY compania, fecha",
            (fecha_desde, fecha_hasta)
        )
    else:
        cursor.execute("SELECT id_conduce, fecha, producto, compania, precio, cantidad, estado, id_transporte FROM conduces ORDER BY compania, fecha")
    rows = cursor.fetchall()

    total = len(rows)
    pagados = sum(1 for r in rows if r[6].lower() == "pagado")
    pendientes = total - pagados
    monto_pendiente, sin_precio_pendiente = _monto_y_sin_precio(
        rows, lambda r: r[6].lower() == "no_pagado")
    # monto_pagado se calculaba aca y no lo usaba ninguna plantilla — codigo
    # muerto desde siempre, retirado con el issue #31.

    # Resumen por compañía
    # Issue #31: se agrupa primero y el monto sale de _monto_y_sin_precio(),
    # la misma primitiva que la tarjeta de arriba. Antes la formula y el
    # criterio de "sin precio" estaban repetidos aca, que es como se
    # desincronizan: el total de la tarjeta y la suma de la tabla tienen que
    # salir del mismo lugar o tarde o temprano dicen cosas distintas.
    filas_por_compania = {}
    for r in rows:
        filas_por_compania.setdefault(r[3], []).append(r)

    por_compania = {}
    for comp, filas in filas_por_compania.items():
        pagados_comp = sum(1 for r in filas if r[6].lower() == "pagado")
        monto_comp, sin_precio_comp = _monto_y_sin_precio(
            filas, lambda r: r[6].lower() != "pagado")
        por_compania[comp] = {
            "total": len(filas),
            "pagados": pagados_comp,
            "pendientes": len(filas) - pagados_comp,
            "monto_pendiente": monto_comp,
            "sin_precio": sin_precio_comp,
        }

    conn.close()

    fecha_reporte = datetime.now().strftime("%d/%m/%Y %H:%M")
    rango = f"{fecha_desde} al {fecha_hasta}" if fecha_desde and fecha_hasta else "Todos los registros"
    filename = f"reporte_general_{fecha_desde}_{fecha_hasta}.html" if fecha_desde and fecha_hasta else f"reporte_general_todos.html"
    filepath = os.path.join(REPORTES_DIR, filename)

    if os.path.exists(filepath):
        return json.dumps({"filename": filename, "cached": True})

    filas_compania = ""
    for comp, data in por_compania.items():
        filas_compania += f"""
        <tr>
            <td>{_esc_html(str(comp))}</td>
            <td class="center">{data['total']}</td>
            <td class="center pagado">{data['pagados']}</td>
            <td class="center pendiente">{data['pendientes']}</td>
            <td class="right">${data['monto_pendiente']:,.2f}{
                f" <span class='sin-precio'>({data['sin_precio']} sin precio)</span>"
                if data['sin_precio'] else ""}</td>
        </tr>"""

    filas_detalle = ""
    for r in rows:
        estado_class = "pagado" if r[6].lower() == "pagado" else "pendiente"
        estado_label = "PAGADO" if r[6].lower() == "pagado" else "PENDIENTE"
        precio_str = f"${r[4]:,.2f}" if r[4] is not None else "N/A"
        id_transporte_str = r[7] if r[7] else ""
        filas_detalle += f"""
        <tr>
            <td><strong>{_esc_html(str(r[0]))}</strong></td>
            <td>{_esc_html(str(id_transporte_str))}</td>
            <td>{_esc_html(str(r[1]))}</td>
            <td>{_esc_html(str(r[2]))}</td>
            <td>{_esc_html(str(r[3]))}</td>
            <td class="right">{r[5]}</td>
            <td class="right">{precio_str}</td>
            <td class="center"><span class="badge {estado_class}">{estado_label}</span></td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <title>Reporte de Conduces</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, sans-serif; background: #f5f5f5; color: #1A3A5C; padding: 40px; }}

    .header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 40px; }}
    .header h1 {{ font-size: 36px; font-weight: 800; color: #1A3A5C; }}
    .header .empresa {{ font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }}
    .header .fecha-box {{ text-align: right; }}
    .header .fecha {{ font-size: 22px; font-weight: 700; color: #D32F2F; }}
    .header .generado {{ font-size: 12px; color: #666; margin-top: 4px; }}

    .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 40px; }}
    .card {{ background: white; border-radius: 12px; padding: 20px 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.07); }}
    .card .label {{ font-size: 12px; color: #666; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }}
    .card .value {{ font-size: 28px; font-weight: 800; color: #1A3A5C; }}
    /* issue #31: un monto calculado sobre filas sin precio no es el monto */
    .card .nota-sin-precio {{ margin-top: 6px; font-size: 11px; font-weight: 600; color: #B00020; }}
    .sin-precio {{ font-size: 11px; font-weight: 600; color: #B00020; white-space: nowrap; }}
    .card.orange .value {{ color: #D32F2F; }}
    .card.green .value {{ color: #2d6a4f; }}
    .card.red .value {{ color: #c1121f; }}

    h2 {{ font-size: 18px; font-weight: 700; margin-bottom: 16px; color: #1A3A5C; }}

    .section {{ background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.07); margin-bottom: 24px; }}

    table {{ width: 100%; border-collapse: collapse; }}
    th {{ text-align: left; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #666; padding: 8px 12px; border-bottom: 2px solid #f0f0f0; }}
    td {{ padding: 10px 12px; border-bottom: 1px solid #f5f5f5; font-size: 14px; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #fafafa; }}

    .center {{ text-align: center; }}
    .right {{ text-align: right; }}

    .badge {{ display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; }}
    .badge.pagado {{ background: #d8f3dc; color: #2d6a4f; }}
    .badge.pendiente {{ background: #ffe5d0; color: #c1121f; }}
    .pagado {{ color: #2d6a4f; }}
    .pendiente {{ color: #c1121f; }}

    .footer {{ text-align: center; font-size: 12px; color: #aaa; margin-top: 40px; }}
  </style>
</head>
<body>

  <div class="header">
    <div>
      <div class="empresa">VMO</div>
      <h1>Reporte de Conduces</h1>
      <div style="font-size:13px;color:#666;margin-top:6px;">Período: {_esc_html(str(rango))}</div>
    </div>
    <div class="fecha-box">
      <div class="fecha">{fecha_reporte}</div>
      <div class="generado">Generado automáticamente</div>
    </div>
  </div>

  <div class="cards">
    <div class="card orange">
      <div class="label">Total Conduces</div>
      <div class="value">{total}</div>
    </div>
    <div class="card green">
      <div class="label">Pagados</div>
      <div class="value">{pagados}</div>
    </div>
    <div class="card red">
      <div class="label">Pendientes</div>
      <div class="value">{pendientes}</div>
    </div>
    <div class="card red">
      <div class="label">Monto Pendiente</div>
      <div class="value">${monto_pendiente:,.2f}</div>
      {_nota_sin_precio(sin_precio_pendiente, pendientes)}
    </div>
  </div>

  <div class="section">
    <h2>Resumen por Compañía</h2>
    <table>
      <thead>
        <tr>
          <th>Compañía</th>
          <th class="center">Total</th>
          <th class="center">Pagados</th>
          <th class="center">Pendientes</th>
          <th class="right">Monto Pendiente</th>
        </tr>
      </thead>
      <tbody>{filas_compania}</tbody>
    </table>
  </div>

  <div class="section">
    <h2>Detalle de Conduces</h2>
    <table>
      <thead>
        <tr>
          <th>ID Conduce</th>
          <th>ID Transporte</th>
          <th>Fecha</th>
          <th>Producto</th>
          <th>Compañía</th>
          <th class="right">Cantidad</th>
          <th class="right">Precio</th>
          <th class="center">Estado</th>
        </tr>
      </thead>
      <tbody>{filas_detalle}</tbody>
    </table>
  </div>

  <div class="footer">Reporte generado el {fecha_reporte}</div>

</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    return json.dumps({"filename": filename, "total": total, "pagados": pagados,
                       "pendientes": pendientes, "sin_precio": sin_precio_pendiente})


def generar_reporte_compania(compania: str, fecha_desde: str = None, fecha_hasta: str = None) -> str:
    _exigir_fechas_iso(fecha_desde, fecha_hasta)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if fecha_desde and fecha_hasta:
        cursor.execute(
            "SELECT id_conduce, fecha, producto, compania, precio, cantidad, estado, id_transporte FROM conduces WHERE compania = ? AND fecha BETWEEN ? AND ? ORDER BY fecha",
            (compania, fecha_desde, fecha_hasta)
        )
    else:
        cursor.execute(
            "SELECT id_conduce, fecha, producto, compania, precio, cantidad, estado, id_transporte FROM conduces WHERE compania = ? ORDER BY fecha",
            (compania,)
        )
    rows = cursor.fetchall()
    conn.close()

    total = len(rows)
    pagados = sum(1 for r in rows if r[6].lower() == "pagado")
    pendientes = total - pagados
    monto_pendiente, sin_precio_pendiente = _monto_y_sin_precio(
        rows, lambda r: r[6].lower() == "no_pagado")

    fecha_reporte = datetime.now().strftime("%d/%m/%Y %H:%M")
    rango = f"{fecha_desde} al {fecha_hasta}" if fecha_desde and fecha_hasta else "Todos los registros"
    comp_slug = _slug_compania(compania)
    filename = f"reporte_{comp_slug}_{fecha_desde}_{fecha_hasta}.html" if fecha_desde and fecha_hasta else f"reporte_{comp_slug}_todos.html"
    filepath = os.path.join(REPORTES_DIR, filename)

    if os.path.exists(filepath):
        return json.dumps({"filename": filename, "cached": True})

    filas_detalle = ""
    for r in rows:
        estado_class = "pagado" if r[6].lower() == "pagado" else "pendiente"
        estado_label = "PAGADO" if r[6].lower() == "pagado" else "PENDIENTE"
        precio_str = f"${r[4]:,.2f}" if r[4] is not None else "N/A"
        id_transporte_str = r[7] if r[7] else ""
        filas_detalle += f"""
        <tr>
            <td><strong>{_esc_html(str(r[0]))}</strong></td>
            <td>{_esc_html(str(id_transporte_str))}</td>
            <td>{_esc_html(str(r[1]))}</td>
            <td>{_esc_html(str(r[2]))}</td>
            <td class="right">{r[5]}</td>
            <td class="right">{precio_str}</td>
            <td class="center"><span class="badge {estado_class}">{estado_label}</span></td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <title>Reporte — {_esc_html(str(compania))}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, sans-serif; background: #f5f5f5; color: #1A3A5C; padding: 40px; }}

    .header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 40px; }}
    .header h1 {{ font-size: 36px; font-weight: 800; color: #1A3A5C; }}
    .header .empresa {{ font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }}
    .header .compania-nombre {{ font-size: 18px; font-weight: 600; color: #D32F2F; margin-top: 4px; }}
    .header .fecha-box {{ text-align: right; }}
    .header .fecha {{ font-size: 22px; font-weight: 700; color: #D32F2F; }}
    .header .generado {{ font-size: 12px; color: #666; margin-top: 4px; }}

    .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 40px; }}
    .card {{ background: white; border-radius: 12px; padding: 20px 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.07); }}
    .card .label {{ font-size: 12px; color: #666; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }}
    .card .value {{ font-size: 28px; font-weight: 800; color: #1A3A5C; }}
    /* issue #31: un monto calculado sobre filas sin precio no es el monto */
    .card .nota-sin-precio {{ margin-top: 6px; font-size: 11px; font-weight: 600; color: #B00020; }}
    .sin-precio {{ font-size: 11px; font-weight: 600; color: #B00020; white-space: nowrap; }}
    .card.orange .value {{ color: #D32F2F; }}
    .card.green .value {{ color: #2d6a4f; }}
    .card.red .value {{ color: #c1121f; }}

    h2 {{ font-size: 18px; font-weight: 700; margin-bottom: 16px; color: #1A3A5C; }}
    .section {{ background: white; border-radius: 12px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.07); margin-bottom: 24px; }}

    table {{ width: 100%; border-collapse: collapse; }}
    th {{ text-align: left; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #666; padding: 8px 12px; border-bottom: 2px solid #f0f0f0; }}
    td {{ padding: 10px 12px; border-bottom: 1px solid #f5f5f5; font-size: 14px; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #fafafa; }}

    .center {{ text-align: center; }}
    .right {{ text-align: right; }}

    .badge {{ display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; }}
    .badge.pagado {{ background: #d8f3dc; color: #2d6a4f; }}
    .badge.pendiente {{ background: #ffe5d0; color: #c1121f; }}
    .pagado {{ color: #2d6a4f; }}
    .pendiente {{ color: #c1121f; }}

    .footer {{ text-align: center; font-size: 12px; color: #aaa; margin-top: 40px; }}
  </style>
</head>
<body>

  <div class="header">
    <div>
      <div class="empresa">VMO</div>
      <h1>Reporte de Conduces</h1>
      <div class="compania-nombre">{_esc_html(str(compania))}</div>
      <div style="font-size:13px;color:#666;margin-top:6px;">Período: {_esc_html(str(rango))}</div>
    </div>
    <div class="fecha-box">
      <div class="fecha">{fecha_reporte}</div>
      <div class="generado">Generado automáticamente</div>
    </div>
  </div>

  <div class="cards">
    <div class="card orange">
      <div class="label">Total Conduces</div>
      <div class="value">{total}</div>
    </div>
    <div class="card green">
      <div class="label">Pagados</div>
      <div class="value">{pagados}</div>
    </div>
    <div class="card red">
      <div class="label">Pendientes</div>
      <div class="value">{pendientes}</div>
    </div>
    <div class="card red">
      <div class="label">Monto Pendiente</div>
      <div class="value">${monto_pendiente:,.2f}</div>
      {_nota_sin_precio(sin_precio_pendiente, pendientes)}
    </div>
  </div>

  <div class="section">
    <h2>Detalle de Conduces</h2>
    <table>
      <thead>
        <tr>
          <th>ID Conduce</th>
          <th>ID Transporte</th>
          <th>Fecha</th>
          <th>Producto</th>
          <th class="right">Cantidad</th>
          <th class="right">Precio</th>
          <th class="center">Estado</th>
        </tr>
      </thead>
      <tbody>{filas_detalle}</tbody>
    </table>
  </div>

  <div class="footer">Reporte generado el {fecha_reporte}</div>

</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    return json.dumps({"filename": filename, "total": total, "pagados": pagados,
                       "pendientes": pendientes, "sin_precio": sin_precio_pendiente})


def generar_factura(compania: str, fecha_desde: str = None, fecha_hasta: str = None, conduces: list = None) -> str:
    _exigir_fechas_iso(fecha_desde, fecha_hasta)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if conduces:
        placeholders = ','.join('?' * len(conduces))
        cursor.execute(
            f"SELECT id_conduce, fecha, producto, compania, precio, cantidad, estado, id_transporte, almacen FROM conduces WHERE compania = ? AND id_conduce IN ({placeholders}) ORDER BY fecha",
            [compania] + conduces
        )
    elif fecha_desde and fecha_hasta:
        cursor.execute(
            "SELECT id_conduce, fecha, producto, compania, precio, cantidad, estado, id_transporte, almacen FROM conduces WHERE compania = ? AND fecha BETWEEN ? AND ? ORDER BY fecha",
            (compania, fecha_desde, fecha_hasta)
        )
    else:
        cursor.execute(
            "SELECT id_conduce, fecha, producto, compania, precio, cantidad, estado, id_transporte, almacen FROM conduces WHERE compania = ? ORDER BY fecha",
            (compania,)
        )

    rows = cursor.fetchall()
    conn.close()

    total = len(rows)
    monto_total, sin_precio_total = _monto_y_sin_precio(rows)

    fecha_reporte = datetime.now().strftime("%d/%m/%Y %H:%M")
    comp_slug = _slug_compania(compania)

    if conduces:
        ids_slug = "_".join(_slug_archivo(c) for c in conduces[:3]) + \
            (f"_y{len(conduces)-3}mas" if len(conduces) > 3 else "")
        filename = f"factura_{comp_slug}_{ids_slug}.html"
        descripcion_filtro = f"Conduces específicos: {', '.join(conduces)}"
    elif fecha_desde and fecha_hasta:
        filename = f"factura_{comp_slug}_{fecha_desde}_{fecha_hasta}.html"
        descripcion_filtro = f"Período: {fecha_desde} al {fecha_hasta}"
    else:
        filename = f"factura_{comp_slug}_todos.html"
        descripcion_filtro = "Todos los registros"

    filepath = os.path.join(FACTURAS_DIR, filename)

    if os.path.exists(filepath):
        return json.dumps({"filename": filename, "cached": True})

    filas_detalle = ""
    for r in rows:
        estado_class = "pagado" if r[6].lower() == "pagado" else "pendiente"
        estado_label = "PAGADO" if r[6].lower() == "pagado" else "PENDIENTE"
        precio_str = f"${r[4]:,.2f}" if r[4] is not None else "N/A"
        subtotal = (r[4] or 0) * (r[5] or 0)
        subtotal_str = f"${subtotal:,.2f}" if r[4] is not None else "N/A"
        id_transporte_str = r[7] if r[7] else ""
        almacen_str = r[8] if r[8] else ""
        filas_detalle += f"""
        <tr>
            <td><strong>{_esc_html(str(r[0]))}</strong></td>
            <td>{_esc_html(str(id_transporte_str))}</td>
            <td>{_esc_html(str(r[1]))}</td>
            <td>{_esc_html(str(r[2]))}</td>
            <td>{_esc_html(str(almacen_str))}</td>
            <td class="right">{r[5]}</td>
            <td class="right">{precio_str}</td>
            <td class="right">{subtotal_str}</td>
            <td class="center"><span class="badge {estado_class}">{estado_label}</span></td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <title>Factura — {_esc_html(str(compania))}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, sans-serif; background: #f5f5f5; color: #222; padding: 40px; }}

    .header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 32px; padding-bottom: 24px; border-bottom: 3px solid #1A3A5C; }}
    .header-left .empresa {{ font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #888; }}
    .header-left h1 {{ font-size: 34px; font-weight: 800; color: #1A3A5C; margin: 6px 0 4px; }}
    .header-left .proveedor {{ font-size: 17px; font-weight: 600; color: #D32F2F; }}
    .header-right {{ text-align: right; }}
    .header-right .meta-label {{ font-size: 10px; color: #aaa; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px; }}
    .header-right .meta-value {{ font-size: 14px; font-weight: 600; color: #333; margin-bottom: 12px; }}

    .periodo {{ font-size: 13px; color: #555; background: white; padding: 10px 16px; border-radius: 8px; border-left: 3px solid #D32F2F; margin-bottom: 28px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}

    table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.07); }}
    th {{ text-align: left; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #888; padding: 12px 14px; background: #f8f8f8; border-bottom: 2px solid #eee; }}
    td {{ padding: 10px 14px; border-bottom: 1px solid #f0f0f0; font-size: 14px; color: #333; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #fafafa; }}
    .right {{ text-align: right; }}
    .center {{ text-align: center; }}

    .badge {{ display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; }}
    .badge.pagado {{ background: #d8f3dc; color: #2d6a4f; }}
    .badge.pendiente {{ background: #ffe5d0; color: #c1121f; }}

    .total-row td {{ background: #1A3A5C; color: white; font-weight: 700; font-size: 14px; padding: 13px 14px; border: none; }}
    .total-row td.right {{ font-size: 16px; }}

    .footer {{ text-align: center; font-size: 11px; color: #bbb; margin-top: 36px; }}
  </style>
</head>
<body>

  <div class="header">
    <div class="header-left">
      <div class="empresa">VMO — Sistema de Conduces</div>
      <h1>Factura</h1>
      <div class="proveedor">{_esc_html(str(compania))}</div>
    </div>
    <div class="header-right">
      <div class="meta-label">Generado</div>
      <div class="meta-value">{fecha_reporte}</div>
      <div class="meta-label">Total conduces</div>
      <div class="meta-value">{total}</div>
    </div>
  </div>

  <div class="periodo">{_esc_html(str(descripcion_filtro))}</div>

  <table>
    <thead>
      <tr>
        <th>ID Conduce</th>
        <th>ID Transporte</th>
        <th>Fecha</th>
        <th>Producto</th>
        <th>Almacén</th>
        <th class="right">Cantidad</th>
        <th class="right">Precio Unit.</th>
        <th class="right">Total</th>
        <th class="center">Estado</th>
      </tr>
    </thead>
    <tbody>
      {filas_detalle}
      <tr class="total-row">
        <td colspan="7">Total General</td>
        <td class="right">${monto_total:,.2f}</td>
        <td></td>
      </tr>
    </tbody>
  </table>

  <div class="footer">Generado automáticamente por VMO el {fecha_reporte}</div>

</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    return json.dumps({"filename": filename, "total": total,
                       "sin_precio": sin_precio_total})

# ─────────────────────────────────────────────
# ESTIMACIONES — helpers
# ─────────────────────────────────────────────

def _est_crear_tabla_pendientes(conn):
    """Crea pendientes_revision si no existe (idempotente). Primitiva
    compartida (issue #19): antes vivia duplicada como
    asegurar_tabla_pendientes() en scripts/importar_puente.py — ahora la
    llaman setup_est_db() y el script, sobre la conexion (o cursor) que le
    pasen. No abre ni cierra transaccion: el llamador decide.

    Issue #38: crea tambien pendiente_descartado, el archivo permanente de
    los pendientes que se decidio NO facturar. Va aca y no en setup_est_db()
    porque las dos tablas son las dos caras del mismo dato y ningun llamador
    puede quedarse con una sola: la fila se MUEVE de una a la otra."""
    conn.execute("""CREATE TABLE IF NOT EXISTS pendientes_revision (
        archivo_pdf       TEXT PRIMARY KEY,
        id_documento      TEXT,
        fecha             DATE,
        planta            TEXT,
        orden_compra      TEXT,
        referencia        TEXT,
        distancia         TEXT,
        cliente           TEXT,
        obra              TEXT,
        obra_papel        TEXT,
        obra_familia      TEXT,
        bomba             TEXT,
        id_producto       TEXT,
        descripcion       TEXT,
        cantidad          REAL,
        precio_unitario   REAL,
        total             REAL,
        ficha             TEXT,
        chofer            TEXT,
        hora_salida       TEXT,
        observaciones     TEXT,
        empresa           TEXT,
        fase              TEXT,
        motivo            TEXT,
        fecha_pendiente   DATETIME
    )""")
    # Issue #38 — el descarte no borra: mueve. Mismas 21 columnas compartidas
    # (misma PK: archivo_pdf) + fecha_pendiente y el motivo original, para que
    # /reponer reconstruya el pendiente EXACTO que habia, no una aproximacion.
    # La PK da gratis la guarda de colision: descartar dos veces el mismo
    # archivo choca en vez de duplicar.
    conn.execute("""CREATE TABLE IF NOT EXISTS pendiente_descartado (
        archivo_pdf       TEXT PRIMARY KEY,
        id_documento      TEXT,
        fecha             DATE,
        planta            TEXT,
        orden_compra      TEXT,
        referencia        TEXT,
        distancia         TEXT,
        cliente           TEXT,
        obra              TEXT,
        obra_papel        TEXT,
        obra_familia      TEXT,
        bomba             TEXT,
        id_producto       TEXT,
        descripcion       TEXT,
        cantidad          REAL,
        precio_unitario   REAL,
        total             REAL,
        ficha             TEXT,
        chofer            TEXT,
        hora_salida       TEXT,
        observaciones     TEXT,
        empresa           TEXT,
        fase              TEXT,
        fecha_pendiente   DATETIME,
        motivo_bloqueo    TEXT,
        descartado_por    TEXT NOT NULL,
        descartado_motivo TEXT NOT NULL,
        descartado_fecha  TEXT NOT NULL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pendiente_descartado_id "
                 "ON pendiente_descartado (id_documento)")
    # Issue #67 — obra_papel: la linea `OBRA:` impresa en el conduce (DIMECA,
    # CONCAVA, LIDOMI), que hasta ahora no se guardaba en ninguna columna. Es
    # un dato DISTINTO de `obra`, que no se toca: por el import masivo `obra`
    # vale la fase y por el camino individual lo que devuelva Vision. La
    # migracion va ACA y no en setup_est_db() por el mismo motivo que el
    # CREATE: scripts/importar_puente.py llama a esta primitiva directo y
    # tiene que encontrar las dos tablas con la columna. ADD COLUMN simple —
    # no hace falta recrear la tabla (a diferencia de la de `serie`, que
    # cambiaba la PRIMARY KEY). Idempotente via PRAGMA table_info.
    #
    # Issue #72 — obra_familia entra por el mismo camino: la forma normalizada
    # y agrupada de obra_papel segun EQUIVALENCIAS_OBRA (ver
    # normalizar_obra_papel()). obra_papel NO se toca: es la evidencia cruda.
    for tabla in ("pendientes_revision", "pendiente_descartado"):
        cols = [c[1] for c in conn.execute(f"PRAGMA table_info({tabla})").fetchall()]
        for columna in ("obra_papel", "obra_familia"):
            if cols and columna not in cols:
                conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} TEXT")


def setup_est_db():
    os.makedirs(os.path.dirname(EST_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(EST_DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS facturas (
        id_documento      TEXT PRIMARY KEY,
        fecha             DATE,
        planta            TEXT,
        orden_compra      TEXT,
        referencia        TEXT,
        distancia         TEXT,
        cliente           TEXT,
        obra              TEXT,
        obra_papel        TEXT,
        obra_familia      TEXT,
        bomba             TEXT,
        id_producto       TEXT,
        descripcion       TEXT,
        cantidad          REAL,
        precio_unitario   REAL,
        total             REAL,
        ficha             TEXT,
        chofer            TEXT,
        hora_salida       TEXT,
        observaciones     TEXT,
        archivo_pdf       TEXT,
        empresa           TEXT,
        fase              TEXT,
        fecha_importacion DATETIME
    )""")
    _est_crear_tabla_pendientes(conn)
    conn.execute("""CREATE TABLE IF NOT EXISTS catalogo_estimacion (
        empresa TEXT,
        fase TEXT,
        orden INTEGER,
        clave TEXT,
        descripcion TEXT,
        precio_unitario REAL,
        PRIMARY KEY (empresa, fase, orden)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS precios_vmo (
        codigo TEXT,
        fase TEXT,
        descripcion TEXT,
        precio_unitario REAL,
        PRIMARY KEY (codigo, fase)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS precios_domicem (
        fase TEXT,
        codigo TEXT,
        descripcion TEXT,
        precio_unitario REAL,
        PRIMARY KEY (fase, codigo)
    )""")
    # Issue #11: base fija de "acumulado anterior" por producto, dada una sola
    # vez por el usuario — el calculo automatico suma facturas reales por
    # encima de esta base (ver _est_clasificar_series()). Issue #12 extendio
    # el esquema para soportar 2 series (contrato principal / PPACT) por
    # producto — ver la migracion justo abajo.
    conn.execute("""CREATE TABLE IF NOT EXISTS estimacion_acumulado_base (
        empresa        TEXT,
        fase           TEXT,
        clave          TEXT,
        fecha_base     DATE,
        cantidad_base  REAL,
        PRIMARY KEY (empresa, fase, clave)
    )""")
    # Issue #12: contratos paralelos (principal vs PPACT) — SQLite no permite
    # cambiar la PRIMARY KEY de una tabla existente con ALTER TABLE, asi que
    # hay que recrearla. Migracion idempotente (revisa si "serie" ya existe
    # antes de tocar nada) y transaccional (si cualquier paso falla, rollback
    # completo — nunca deja la tabla a medio migrar).
    columnas_acum_base = [c[1] for c in conn.execute("PRAGMA table_info(estimacion_acumulado_base)").fetchall()]
    if columnas_acum_base and "serie" not in columnas_acum_base:
        conn.execute("BEGIN")
        try:
            conn.execute("ALTER TABLE estimacion_acumulado_base RENAME TO estimacion_acumulado_base_old")
            conn.execute("""CREATE TABLE estimacion_acumulado_base (
                empresa TEXT, fase TEXT, clave TEXT,
                serie TEXT NOT NULL CHECK (serie IN ('principal','ppact')),
                fecha_base DATE, cantidad_base REAL,
                cantidad_proyecto_principal REAL,
                PRIMARY KEY (empresa, fase, clave, serie)
            )""")
            conn.execute("""INSERT INTO estimacion_acumulado_base
                (empresa, fase, clave, serie, fecha_base, cantidad_base, cantidad_proyecto_principal)
                SELECT empresa, fase, clave, 'principal', fecha_base, cantidad_base, NULL
                FROM estimacion_acumulado_base_old""")
            conn.execute("DROP TABLE estimacion_acumulado_base_old")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    # Issue #17: libro mayor de estimaciones cerradas. Cada cierre guarda, por
    # (clave, serie), cuanto quedo registrado en esa estimacion y su periodo —
    # asi el acumulado anterior de la proxima pasa a ser seed + cerradas, sin
    # reprocesar las facturas del medio. El seed (estimacion_acumulado_base)
    # queda inmutable: es la copia del documento de la empresa. Migracion
    # idempotente: CREATE TABLE IF NOT EXISTS no toca una tabla existente ni
    # sus filas (criterio 9).
    conn.execute("""CREATE TABLE IF NOT EXISTS estimacion_cerrada (
        empresa            TEXT NOT NULL,
        fase               TEXT NOT NULL,
        clave              TEXT NOT NULL,
        serie              TEXT NOT NULL CHECK (serie IN ('principal','ppact')),
        numero_estimacion  TEXT NOT NULL,
        fecha_desde        DATE NOT NULL,
        fecha_hasta        DATE NOT NULL,
        cantidad           REAL NOT NULL CHECK (cantidad > 0),
        cerrada_en         TEXT NOT NULL,
        PRIMARY KEY (empresa, fase, clave, serie, numero_estimacion)
    )""")
    # Migracion idempotente — agrega sin_firma si la BD todavia no la tiene
    # (tablas existentes se crean con CREATE TABLE IF NOT EXISTS, que no
    # agrega columnas nuevas a una tabla que ya existe). Mismo patron que
    # fecha_pago en pagar.py. Issue #7: sello obligatorio, firma ya no
    # bloquea el import — sin_firma=1 marca los documentos importados sin
    # firma para poder mostrarlos aparte en el resumen.
    columnas_facturas = [c[1] for c in conn.execute("PRAGMA table_info(facturas)").fetchall()]
    if "sin_firma" not in columnas_facturas:
        conn.execute("ALTER TABLE facturas ADD COLUMN sin_firma INTEGER DEFAULT 0")
    # Issue #11: cuando una factura se resuelve a mano (colision o sin match)
    # la resolucion queda guardada para siempre, keyeada por id_documento
    # (PK de facturas) — nunca por descripcion, que puede repetirse en
    # facturas de otras fechas que necesiten resolverse distinto.
    if "clave_resuelta" not in columnas_facturas:
        conn.execute("ALTER TABLE facturas ADD COLUMN clave_resuelta TEXT")
    # Issue #20: aprobacion manual de pendientes bloqueados por falta de
    # sello/firma. La marca es solo interna (nunca sale en el documento del
    # cliente): quien aprobo, por que y cuando, mas el motivo original del
    # bloqueo — motivo_bloqueo es lo que permite devolver la fila a
    # pendientes_revision con su motivo intacto al revertir. Mismo patron
    # idempotente que sin_firma: solo se agregan las columnas que falten.
    # ALTER TABLE ... DEFAULT 0 en SQLite tambien aplica el default a las
    # filas existentes, asi que una BD vieja queda con aprobado_manual=0 y
    # el resto en NULL (criterio 15) sin UPDATE aparte.
    #
    # Issue #67: obra_papel entra por el mismo camino — la linea `OBRA:` del
    # papel, que `obra` nunca guardo (ver _est_crear_tabla_pendientes()). Las
    # 4.185 filas viejas quedan en NULL hasta que las rellene
    # scripts/backfill_obra_papel.py; `obra` no se toca.
    #
    # Issue #72: obra_familia — la forma normalizada/agrupada de obra_papel
    # (normalizar_obra_papel()). Las filas viejas quedan en NULL hasta que
    # las derive scripts/backfill_obra_familia.py (gratis y deterministico,
    # sin Vision); obra_papel no se toca.
    for columna, tipo in (
        ("aprobado_manual", "INTEGER DEFAULT 0"),
        ("aprobado_por",    "TEXT"),
        ("aprobado_motivo", "TEXT"),
        ("aprobado_fecha",  "TEXT"),
        ("motivo_bloqueo",  "TEXT"),
        ("obra_papel",      "TEXT"),
        ("obra_familia",    "TEXT"),
    ):
        if columna not in columnas_facturas:
            conn.execute(f"ALTER TABLE facturas ADD COLUMN {columna} {tipo}")
    conn.commit()
    conn.close()


def parsear_nombre_pdf(nombre: str):
    """MM-DD-M#-XXXXX.pdf → {fecha, planta, id_documento}"""
    # fullmatch y no match con `$`: `$` tambien acepta un salto de linea al
    # final, y un nombre terminado en salto de linea pasaba el filtro.
    m = re.fullmatch(r'(\d{2})-(\d{2})-(M\d+)-(\d+)\.pdf', nombre, re.IGNORECASE)
    if not m:
        return None
    mes, dia, planta, id_num = m.groups()
    try:
        fecha = date(datetime.now().year, int(mes), int(dia))
    except ValueError:
        return None
    planta_up = planta.upper()
    id_documento = f"{planta_up}{id_num.zfill(8)}"  # M3 + 00048807 → M300048807
    return {"fecha": fecha.isoformat(), "planta": planta_up, "id_documento": id_documento}


# Issue #67 — la instruccion que apunta al dato del papel, en un solo lugar
# porque la usan dos prompts distintos: el de scripts/importar_puente.py
# (camino masivo) y el de _extraer_obra_papel() (backfill). El paréntesis del
# campo `Cliente:` dice siempre lo mismo ("MACAO ALTO RESORT SRL (CIUDAD
# PALACE - CAVERNAS Y EXT)") y es justo el distractor que hay que descartar:
# la obra real —DIMECA, CONCAVA, LIDOMI— solo esta en la linea `OBRA:`.
# _procesar_pdf_sync() NO la lleva a proposito: su prompt ya lee bien esa
# linea (medido 2026-09-07 sobre los 10 fixtures) y tocarlo cambiaria lo que
# se guarda en la columna `obra`, que este issue no toca.
EST_OBRA_PAPEL_PROMPT = (
    'El campo "obra" es el texto que sigue a la etiqueta OBRA: impresa en el '
    'documento (por ejemplo DIMECA, CONCAVA o LIDOMI). NO uses el campo '
    'Cliente: ni lo que va entre parentesis dentro de el. Si la etiqueta '
    'OBRA: no se lee, devuelve null.'
)


# Issue #69 — cuantos intentos se le dan a una respuesta que no parsea. El
# fallo es ALEATORIO POR LLAMADA, no una propiedad del documento: medido el
# 2026-09-07, 4 de 32 llamadas (~12%) sobre conduces con comilla de pulgada en
# la descripcion, y el mismo PDF que fallo dos veces paso otras seis. Por eso
# reintentar sirve: 3 intentos bajan el ~12% a ~0,2%.
EST_VISION_INTENTOS = 3

_MARCA_JSON = "```"


def _json_de_respuesta(texto: str) -> dict:
    """Parsea la respuesta de Vision, con o sin cerca de markdown.

    Issue #69 — existe aparte por lo que hace al FALLAR. La version anterior
    probaba las partes de la cerca dentro de un `except: pass` y, si ninguna
    parseaba, terminaba en un `json.loads(texto)` sobre el texto CON la cerca.
    Eso levantaba `Expecting value: line 1 column 1 (char 0)` —el error de
    toparse con el backtick— y **tapaba el error real**, que estaba en medio
    del JSON: una comilla de pulgada sin escapar en la descripcion
    (`Agg 3/8", Temp. 32C`) corta el string y rompe el objeto. El mensaje
    mandaba a investigar el lugar equivocado.

    Ahora el error que se levanta es el de la ultima parte CON CONTENIDO, que
    es la que de verdad traia el JSON. Un diagnostico que apunta al carbon
    equivocado cuesta mas que no tener diagnostico."""
    texto = (texto or "").strip()
    candidatos = []
    if _MARCA_JSON in texto:
        for parte in texto.split(_MARCA_JSON):
            parte = parte.strip()
            # Quitar el marcador de lenguaje por PREFIJO. El `lstrip("json")`
            # anterior borraba cualquier caracter inicial del conjunto
            # {j,o,s,n}, que no es lo mismo. Es defensivo, no un arreglo: con
            # JSON valido las dos formas dan igual siempre (despues de `json`
            # viene un salto de linea o una llave, que cortan el lstrip), asi
            # que NO lleva test propio: uno que pase con y sin el cambio no
            # guardaria nada.
            if parte.startswith("json"):
                parte = parte[4:].strip()
            if parte:
                candidatos.append(parte)
    error_interno = None
    for candidato in candidatos:
        try:
            return json.loads(candidato)
        except ValueError as e:
            error_interno = e

    # El texto crudo va al final como ultimo recurso, pero su error NO pisa al
    # de adentro: si hubo cerca, el `json.loads(texto)` falla siempre en el
    # backtick y ese es justo el mensaje enganoso que este issue saca de encima.
    try:
        return json.loads(texto)
    except ValueError as e:
        raise error_interno if error_interno is not None else e


def _rotar_pdf(pdf_bytes: bytes, grados: int = 180) -> bytes:
    """Devuelve el mismo PDF con la pagina rotada. Issue #73.

    Se rota a nivel PAGINA (`set_rotation`) en vez de re-renderizar la imagen:
    es barato, no pierde calidad, y el documento sigue siendo un PDF, asi que
    la llamada a Vision no cambia de forma.

    El motivo por el que hace falta: en los escaneos dados vuelta
    `page.rotation` vale 0 —la vuelta esta en la IMAGEN, no en el metadato— y
    estos PDFs no tienen capa de texto. Asi que la orientacion NO se puede
    deducir del archivo, y por eso se le pregunta al modelo (campo
    `al_reves` del prompt) en vez de detectarla aca."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for pagina in doc:
            pagina.set_rotation((pagina.rotation + grados) % 360)
        return doc.tobytes()
    finally:
        doc.close()


EST_MOTIVO_PAGINA_VERTICAL = "escaneo vertical"


def _pagina_vertical(pdf_bytes: bytes) -> bool:
    """True si alguna pagina del PDF se VE vertical (mas alta que ancha).

    El conduce es un papel apaisado, asi que un escaneo con el contenido
    girado 90 o 270 grados se ve vertical. A diferencia de la vuelta de 180
    (issue #73, que no se puede ver desde el archivo), esta si se puede: es
    geometria, no hace falta Vision.

    Se mira `page.rect`, que YA aplica el /Rotate de la pagina, y no la
    imagen embebida: medido el 2026-10-05 sobre los ~6.100 conduces de los
    cuatro zips y procesadas/, 118 traen /Rotate 90/180/270 con la imagen
    vertical adentro, y los 118 se ven derechos y apaisados — el escaner ya
    los enderezo, y Vision los lee bien (los 118 tienen obra_papel
    correcto). Mirar la imagen los marcaria a todos. Con page.rect se ve
    vertical uno solo: M800015683, un escaneo atascado pero derecho.

    Un PDF que no abre devuelve False: no es un problema de orientacion y
    la llamada a Vision ya lo va a hacer fallar por su lado."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return False
    try:
        return any(p.rect.height > p.rect.width for p in doc)
    finally:
        doc.close()


# Lo que se acepta de la respuesta de Vision (auditoria de seguridad
# 2026-10-07). Antes el dict del modelo pasaba entero: un PDF con texto
# armado para engañar al modelo (prompt injection) podia hacerle devolver
# `"aprobado_manual": 1, "aprobado_por": "..."` y la factura entraba como
# aprobada a mano, porque la insercion lee esas claves del mismo dict. O una
# `cantidad` de texto, que tumbaba el lote entero al multiplicar por el precio
# —despues de haber pagado las llamadas—. Ahora pasan solo los campos del
# prompt, con su tipo; lo demas se descarta.
VISION_CAMPOS_TEXTO = ("id_documento", "orden_compra", "referencia", "distancia", "cliente", "obra",
                       "bomba", "id_producto", "descripcion", "ficha", "chofer", "hora_salida",
                       "observaciones")
VISION_CAMPOS_SI_NO = ("al_reves", "tiene_sello", "tiene_firma")
VISION_TEXTO_MAX = 500
# m3 por conduce: el mayor medido es 16 (2026-10-07). Fuera de rango es una
# lectura mala, y se trata como tal: error y reintento, no un numero inventado.
VISION_CANTIDAD_MAX = 50


def _sanear_datos_vision(datos) -> dict:
    if not isinstance(datos, dict):
        raise ValueError("la respuesta de Vision no es un objeto JSON")
    limpio = {}
    for campo in VISION_CAMPOS_SI_NO:
        v = datos.get(campo)
        limpio[campo] = v is True or (isinstance(v, str) and v.strip().lower() == "true")
    for campo in VISION_CAMPOS_TEXTO:
        v = datos.get(campo)
        limpio[campo] = None if v is None else str(v)[:VISION_TEXTO_MAX]
    cantidad = datos.get("cantidad")
    if cantidad is not None:
        try:
            cantidad = float(cantidad)
        except (TypeError, ValueError):
            raise ValueError(f"cantidad ilegible: {cantidad!r}")
        if not (0 < cantidad <= VISION_CANTIDAD_MAX):
            raise ValueError(f"cantidad fuera de rango: {cantidad}")
    limpio["cantidad"] = cantidad
    return limpio


def _procesar_pdf_sync(pdf_bytes: bytes, model: str = VISION_MODEL_STD) -> dict:
    """Envía PDF a Claude Vision y extrae campos + valida sello y firma."""
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    prompt = (
        "Analiza este documento de entrega de hormigón. "
        "Responde ÚNICAMENTE con un JSON (sin texto extra, sin bloques de código) con esta estructura:\n"
        "{\n"
        '  "al_reves": true o false,\n'
        '  "tiene_sello": true o false,\n'
        '  "tiene_firma": true o false,\n'
        '  "id_documento": "string o null",\n'
        '  "orden_compra": "string o null",\n'
        '  "referencia": "string o null",\n'
        '  "distancia": "string o null",\n'
        '  "cliente": "string o null",\n'
        '  "obra": "string o null",\n'
        '  "bomba": "string o null",\n'
        '  "id_producto": "string o null",\n'
        '  "descripcion": "string o null",\n'
        '  "cantidad": numero o null,\n'
        '  "ficha": "string o null",\n'
        '  "chofer": "string o null",\n'
        '  "hora_salida": "string o null",\n'
        '  "observaciones": "string o null"\n'
        "}\n"
        "tiene_sello: true si hay cualquier sello, stamp o timbre. "
        "tiene_firma: true si hay una firma o rúbrica visible. "
        "al_reves: true SOLO si el documento esta rotado 180 grados, o sea si "
        "el texto se lee de cabeza. Si se lee normal, false. "
        "Si un campo no es legible usa null."
    )
    # Issue #69 — se reintenta la LLAMADA, no el parseo: el JSON malformado no
    # se puede arreglar desde aca (la comilla sin escapar ya destruyo el
    # string), pero la siguiente respuesta suele venir bien porque el fallo es
    # aleatorio por llamada. Solo se reintenta lo que puede cambiar de una
    # llamada a otra; un error de red o de la API sube tal cual, que es lo que
    # hacia antes.
    def _leer(b64):
        """Los EST_VISION_INTENTOS sobre UN pdf ya codificado (issue #69)."""
        ultimo_error = None
        for _ in range(EST_VISION_INTENTOS):
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}},
                        {"type": "text", "text": prompt}
                    ]
                }]
            )
            text_block = next((b for b in response.content if b.type == "text"), None)
            if text_block is None:
                ultimo_error = ValueError("Respuesta sin bloque de texto (solo thinking/otros)")
                continue
            try:
                return _sanear_datos_vision(_json_de_respuesta(text_block.text))
            except ValueError as e:
                ultimo_error = e
        raise ultimo_error

    datos = _leer(pdf_b64)

    # Issue #73 — un escaneo rotado 180 grados NO entra vacio: entra MAL, y
    # con cara de estar bien. Medido el 2026-09-07 sobre 06-17-M7-18862.pdf:
    # sin rotar devolvia id_documento "M7018882" (el real es M700018862),
    # cantidad 11.0 donde el papel dice 7.00, una descripcion inventada, y
    # tiene_sello/tiene_firma en true — o sea que tampoco caia en
    # pendientes_revision. Rotado, los cuatro campos salen bien.
    #
    # No se puede detectar desde el archivo (`page.rotation` vale 0 y no hay
    # capa de texto) ni comparando el id contra el nombre del PDF: medido, 6
    # de 11 documentos SANOS ya traen el id distinto por confusiones de OCR
    # (`MS00012229` por `M800012229`), asi que ese criterio daria mas falsos
    # positivos que aciertos.
    #
    # Por eso se le pregunta al modelo, en el MISMO prompt: no cuesta ninguna
    # llamada extra en el caso normal, y solo se paga una segunda cuando el
    # documento realmente esta dado vuelta. Medido 8/8 (4 rotados, 4 sanos).
    #
    # Se rota UNA sola vez a proposito: si la segunda lectura tambien dice
    # al_reves, algo mas esta pasando y volver a girar solo gasta plata.
    if datos.get("al_reves"):
        datos = _leer(base64.standard_b64encode(_rotar_pdf(pdf_bytes)).decode("utf-8"))
        # Para que el doble-chequeo de sello/firma mire el PDF enderezado.
        datos["_rotado"] = True
    # 90/270 grados no se le pregunta al modelo: se ve en el archivo. Lo
    # decide _motivo_sello_firma(), aca solo se anota.
    datos["_pagina_vertical"] = _pagina_vertical(pdf_bytes)
    return datos


def _extraer_obra_papel(pdf_bytes: bytes, model: str = VISION_MODEL_STD):
    """Issue #67 — lee SOLO la linea `OBRA:` del conduce. Devuelve el string
    o None. Es lo que usa scripts/backfill_obra_papel.py sobre los PDFs ya
    guardados, y es un prompt propio en vez de reusar _procesar_pdf_sync()
    por dos motivos medidos el 2026-09-07:

    1. Un rellenado no necesita los otros 15 campos — pedir uno solo es mas
       barato y no puede pisar nada de lo que ya esta en la fila.
    2. _procesar_pdf_sync() revienta con este documento real: en
       `06-24-M5-19951.pdf` el modelo devuelve la descripcion
       `Hormigón 280 kg/cm2, Ag 3/4", T 35C, rev. 6" +/- 1", imp.` con las
       comillas de pulgada SIN escapar, y el JSON entero queda invalido
       (2 de 2 intentos). El bug es viejo y ajeno a este issue —se reporta,
       no se arregla aca— pero un backfill que arrastre esa fragilidad
       fallaria en todos los hormigones con revenimiento en pulgadas.

    Un JSON ilegible o una respuesta rara levanta excepcion; el llamador
    decide (el backfill la cuenta como error y sigue con la fila siguiente)."""
    prompt = (
        "Mira este conduce de entrega de hormigon. Responde UNICAMENTE con JSON:\n"
        '{"al_reves": true o false, "obra": "string o null"}\n'
        "al_reves: true SOLO si el documento esta rotado 180 grados, o sea si "
        "el texto se lee de cabeza. Si se lee normal, false.\n"
        + EST_OBRA_PAPEL_PROMPT
    )

    def _leer(datos_pdf):
        b64 = base64.standard_b64encode(datos_pdf).decode("utf-8")
        response = client.messages.create(
            model=model,
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}},
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        text_block = next((b for b in response.content if b.type == "text"), None)
        if text_block is None:
            raise ValueError("Respuesta sin bloque de texto (solo thinking/otros)")
        # _json_de_respuesta() en vez de un parseo propio (issue #69): levanta
        # el error de adentro en vez del de la cerca de markdown.
        return _json_de_respuesta(text_block.text)

    leido = _leer(pdf_bytes)
    # Issue #73 — mismo tratamiento que _procesar_pdf_sync(). Aca fue donde
    # aparecio: las 4 filas que el backfill no pudo rellenar de 4.185 eran
    # escaneos dados vuelta, y rotados salieron 4 de 4 (EXTERIORES1111,
    # EXTERIORES 1141, LIDOMI, CONCAVA). Una sola vuelta, por lo mismo.
    if leido.get("al_reves"):
        leido = _leer(_rotar_pdf(pdf_bytes))

    valor = leido.get("obra")
    if valor is None:
        return None
    valor = str(valor).strip()
    return valor or None


def _verificar_sello_firma_opus(pdf_bytes: bytes) -> dict:
    """Doble-chequeo barato: Haiku a veces dice tiene_sello=true en documentos
    donde el sello fue borrado/no esta (falso positivo confirmado en pruebas
    reales). Solo se llama cuando Haiku ya dijo que el documento estaba
    completo, para confirmar antes de darlo por valido. Usa Sonnet — validado
    contra Opus (25/25 aciertos en auditoria real de 2,742 documentos) y
    contra verdad visual, mismo tiempo de respuesta pero ~60% mas barato."""
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    prompt = (
        "Mira este documento con mucho cuidado. Responde UNICAMENTE con JSON:\n"
        '{"tiene_sello": true o false, "tiene_firma": true o false}\n'
        "tiene_sello: true SOLO si hay un sello, timbre o stamp fisico realmente visible "
        "(no cuentan cajas de texto impresas ni recuadros con datos). "
        "tiene_firma: true SOLO si hay una firma o rubrica a mano realmente visible."
    )
    response = client.messages.create(
        model=VISION_MODEL_VERIFICACION,
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": [
                {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64}},
                {"type": "text", "text": prompt}
            ]
        }]
    )
    text_block = next((b for b in response.content if b.type == "text"), None)
    if text_block is None:
        raise ValueError("Respuesta sin bloque de texto (solo thinking/otros)")
    texto = text_block.text.strip()
    if "```" in texto:
        partes = texto.split("```")
        for p in partes:
            p = p.strip().lstrip("json").strip()
            try:
                return json.loads(p)
            except Exception:
                pass
    return json.loads(texto)


def _sin_formula(celda):
    """openpyxl convierte en formula cualquier texto que empiece con "=". En
    estos Excel entra texto que no controlamos —lo que leyo Vision de un PDF,
    el numero y la fecha de estimacion que manda el navegador—, y una
    `=WEBSERVICE(...)` o `=HYPERLINK(...)` se evaluaba al abrirlo, o al
    convertirlo con LibreOffice en el servidor. Se fuerza a texto (auditoria
    de seguridad 2026-10-07)."""
    if isinstance(celda.value, str) and celda.value.startswith("="):
        celda.data_type = "s"
    return celda


def generar_excel_validacion(registros: list, filepath: str):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Validación"
    headers = ["ID_DOCUMENTO", "FECHA", "PLANTA", "ORDEN_COMPRA", "REFERENCIA", "DISTANCIA",
               "CLIENTE", "OBRA", "BOMBA", "ID_PRODUCTO", "DESCRIPCION", "CANTIDAD",
               "FICHA", "CHOFER", "HORA_SALIDA", "OBSERVACIONES", "ARCHIVO", "SELLO", "FIRMA"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1A3A5C")
        cell.alignment = Alignment(horizontal="center")
    for row_i, r in enumerate(registros, 2):
        vals = [
            r.get("id_documento"), r.get("fecha"), r.get("planta"),
            r.get("orden_compra"), r.get("referencia"), r.get("distancia"),
            r.get("cliente"), r.get("obra"), r.get("bomba"),
            r.get("id_producto"), r.get("descripcion"), r.get("cantidad"),
            r.get("ficha"), r.get("chofer"), r.get("hora_salida"),
            r.get("observaciones"), r.get("archivo_pdf"),
            "SÍ" if r.get("tiene_sello") else "NO",
            "SÍ" if r.get("tiene_firma") else "NO",
        ]
        for col, v in enumerate(vals, 1):
            _sin_formula(ws.cell(row=row_i, column=col, value=v))
    wb.save(filepath)


def actualizar_excel_main(registros: list):
    headers = ["ID_DOCUMENTO", "FECHA", "PLANTA", "ORDEN_COMPRA", "REFERENCIA", "DISTANCIA",
               "CLIENTE", "OBRA", "BOMBA", "ID_PRODUCTO", "DESCRIPCION", "CANTIDAD",
               "PRECIO_UNITARIO", "TOTAL", "FICHA", "CHOFER", "HORA_SALIDA",
               "OBSERVACIONES", "ARCHIVO_PDF", "FECHA_IMPORTACION"]
    if os.path.exists(EST_EXCEL_MAIN):
        wb = openpyxl.load_workbook(EST_EXCEL_MAIN)
        ws = wb.active
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Estimaciones"
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1A3A5C")
            cell.alignment = Alignment(horizontal="center")
    next_row = ws.max_row + 1
    ahora = datetime.now().isoformat()
    for r in registros:
        vals = [
            r.get("id_documento"), r.get("fecha"), r.get("planta"),
            r.get("orden_compra"), r.get("referencia"), r.get("distancia"),
            r.get("cliente"), r.get("obra"), r.get("bomba"),
            r.get("id_producto"), r.get("descripcion"), r.get("cantidad"),
            r.get("precio_unitario"), r.get("total"),
            r.get("ficha"), r.get("chofer"), r.get("hora_salida"),
            r.get("observaciones"), r.get("archivo_pdf"), ahora
        ]
        for col, v in enumerate(vals, 1):
            _sin_formula(ws.cell(row=next_row, column=col, value=v))
        next_row += 1
    wb.save(EST_EXCEL_MAIN)

# ─────────────────────────────────────────────
# ESTIMACIONES — Excel de conduces como fuente de verdad (issue #15)
# ─────────────────────────────────────────────

class ExcelFormatoError(ValueError):
    """Los encabezados del Excel de conduces no coinciden con lo esperado."""


class ExcelIlegibleError(ValueError):
    """El .xlsx no se pudo abrir o leer (corrupto, formato inesperado,
    excepcion propia de openpyxl, etc.) — nunca se deja escapar la
    excepcion cruda de openpyxl hacia el endpoint."""


_EXCEL_LOOKUP_HEADERS = ["Conduce", "Fecha", "Cliente", "Producto", "Cant.", "Planta", "Codigo"]


def _excel_norm_archivo(nombre) -> str:
    """Normaliza el nombre de archivo PDF (columna Codigo) para usarlo como
    llave del indice por_archivo — insensible a mayusculas/espacios, agrega
    .pdf si falta (mismo criterio que scripts/importar_puente.py:95-97)."""
    base = os.path.basename(str(nombre)).strip().lower()
    if base and not base.endswith(".pdf"):
        base += ".pdf"
    return base


def _excel_norm_id(valor) -> str:
    """Normaliza el Conduce para usarlo como llave del indice por_id."""
    return str(valor).strip().upper()


def _mismas_filas(a: dict, b: dict) -> bool:
    """Dos filas del Excel son 'la misma fila' cuando coinciden Conduce,
    Producto, Cliente y Cant. — nunca se compara el numero de fila del Excel.
    La cantidad entra desde 2026-10-20: ahora corrige la que lee Vision, y dos
    filas del mismo conduce con distinta Cant. no dicen cual es la buena."""
    return (
        a.get("id_documento") == b.get("id_documento")
        and a.get("descripcion") == b.get("descripcion")
        and a.get("cliente") == b.get("cliente")
        and a.get("cantidad") == b.get("cantidad")
    )


def _excel_cantidad(valor):
    """La columna Cant. del Excel como float, o None si no es un numero."""
    if valor in (None, ""):
        return None
    try:
        return float(str(valor).strip().replace(",", "."))
    except ValueError:
        return None


def cargar_lookup_excel(excel_bytes: bytes) -> dict:
    """Indexa el Excel de conduces (hoja activa, `wb.active` — mismo criterio
    que scripts/importar_puente.py:84) por nombre de archivo PDF (Codigo) y
    por Conduce. Es la fuente de verdad de la descripcion y (via el Cliente)
    de la fase para el pipeline del sitio web — ver issue #15.

    Devuelve {"por_archivo": {...}, "por_id": {...}, "conflictos": {...},
    "filas": N}, donde cada fila indexada es
    {"id_documento": str, "descripcion": str, "cliente": str}.

    Reglas de saltado/conflicto (issue #15):
    - Fila sin Conduce, sin Producto o sin Cliente -> se salta.
    - Misma llave (Codigo o Conduce) repetida con Producto/Cliente
      identicos -> duplicado ignorado, sin conflicto.
    - Misma llave repetida con Producto o Cliente distintos -> conflicto:
      se anota el Conduce en un set de bloqueadas y, al terminar de indexar,
      se purga de AMBOS indices cualquier entrada que apunte a un Conduce
      bloqueado (invalidacion cruzada y total — un conflicto detectado por
      Codigo tambien invalida el indice por Conduce, y viceversa).
    """
    try:
        wb = openpyxl.load_workbook(io.BytesIO(excel_bytes), read_only=True, data_only=True)
        ws = wb.active
        filas_iter = ws.iter_rows(values_only=True)
        header = next(filas_iter, None)
    except Exception as e:
        raise ExcelIlegibleError(f"no se pudo leer el Excel: {e}") from e

    header_norm = [(str(h).strip() if h is not None else "") for h in (header or [])]
    for i, esperado in enumerate(_EXCEL_LOOKUP_HEADERS):
        real = header_norm[i] if i < len(header_norm) else ""
        if real.lower() != esperado.lower():
            raise ExcelFormatoError(
                f"columna {i + 1}: se esperaba '{esperado}', se encontro '{real or '(vacia)'}'"
            )

    por_archivo: dict = {}
    por_id: dict = {}
    conflictos: dict = {}
    bloqueadas: set = set()
    total_filas = 0

    try:
        for row in filas_iter:
            total_filas += 1
            if total_filas > EST_EXCEL_MAX_FILAS:
                raise ExcelFormatoError(
                    f"el Excel tiene mas de {EST_EXCEL_MAX_FILAS} filas — no es el Excel de conduces"
                )
            if not row:
                continue
            conduce  = row[0] if len(row) > 0 else None
            cliente  = row[2] if len(row) > 2 else None
            producto = row[3] if len(row) > 3 else None
            cantidad = row[4] if len(row) > 4 else None
            codigo   = row[6] if len(row) > 6 else None

            if conduce in (None, "") or producto in (None, "") or cliente in (None, ""):
                continue

            fila = {
                "id_documento": str(conduce).strip(),
                "descripcion":  str(producto).strip(),
                "cliente":      str(cliente).strip(),
                "cantidad":     _excel_cantidad(cantidad),
            }
            id_norm = _excel_norm_id(conduce)
            if id_norm in bloqueadas:
                # este Conduce ya quedo invalidado por un conflicto anterior —
                # no se reinstala en ningun indice sin importar cuantas filas
                # mas aparezcan con el mismo Conduce.
                continue

            existente_id = por_id.get(id_norm)
            if existente_id is None:
                por_id[id_norm] = fila
            elif not _mismas_filas(existente_id, fila):
                conflictos[id_norm] = "descripcion, cliente o cantidad distinta en 2 filas con el mismo Conduce"
                bloqueadas.add(id_norm)
                del por_id[id_norm]

            if codigo not in (None, ""):
                archivo_norm = _excel_norm_archivo(codigo)
                existente_arch = por_archivo.get(archivo_norm)
                if existente_arch is None:
                    por_archivo[archivo_norm] = fila
                elif not _mismas_filas(existente_arch, fila):
                    conflictos[archivo_norm] = "descripcion, cliente o cantidad distinta en 2 filas con el mismo Codigo"
                    bloqueadas.add(id_norm)
                    bloqueadas.add(_excel_norm_id(existente_arch["id_documento"]))
                    del por_archivo[archivo_norm]
    except (ExcelFormatoError, ExcelIlegibleError):
        raise
    except Exception as e:
        raise ExcelIlegibleError(f"error leyendo filas del Excel: {e}") from e

    # Barrido final — cierra el hueco que un simple `del` puntual no cubre:
    # sin esto, un conflicto detectado por Codigo todavia podria sobrevivir
    # via el indice de Conduce (o al reves) si esa entrada se inserto antes o
    # despues del conflicto en la iteracion.
    for clave in list(por_archivo.keys()):
        if _excel_norm_id(por_archivo[clave]["id_documento"]) in bloqueadas:
            del por_archivo[clave]
    for clave in list(por_id.keys()):
        if clave in bloqueadas:
            del por_id[clave]

    return {"por_archivo": por_archivo, "por_id": por_id, "conflictos": conflictos, "filas": total_filas}


def _resolver_fila_excel(lookup: dict, nombre_base: str, id_documento: str):
    """Busca la fila del Excel que corresponde a este documento, por nombre
    de archivo (Codigo) y por id_documento (Conduce) — el nombre del PDF se
    normaliza igual que al indexar. Devuelve (fila, motivo): si no hay fila
    resoluble sin contradicciones, fila es None y motivo describe por que
    ('sin fila en el Excel' o 'el Excel se contradice para este documento')."""
    fila_archivo = lookup["por_archivo"].get(_excel_norm_archivo(nombre_base))
    fila_id = lookup["por_id"].get(_excel_norm_id(id_documento))
    if fila_archivo and fila_id and not _mismas_filas(fila_archivo, fila_id):
        return None, "el Excel se contradice para este documento"
    fila = fila_archivo or fila_id
    if fila is None:
        return None, "sin fila en el Excel"
    return fila, None


def _est_filtrar_conflictos_excel(lookup: dict, pdfs: list) -> list:
    """conflictos_excel solo lista conflictos de filas que corresponden a
    PDFs del ZIP subido — el Excel tiene miles de filas, solo importan las
    del lote actual."""
    archivos_norm = {_excel_norm_archivo(os.path.basename(p)) for p in pdfs}
    ids_norm = set()
    for p in pdfs:
        info = parsear_nombre_pdf(os.path.basename(p))
        if info:
            ids_norm.add(_excel_norm_id(info["id_documento"]))
    resultado = []
    for llave, motivo in lookup.get("conflictos", {}).items():
        if llave in archivos_norm or llave in ids_norm:
            resultado.append({"llave": llave, "motivo": motivo})
    return resultado


# ─────────────────────────────────────────────
# ESTIMACIONES — endpoints
# ─────────────────────────────────────────────

FASES_DOMICEM = {"CAVERNAS", "MACAO 2", "VIVIENDAS", "PATIO DE MANIOBRAS-TRB"}
FASES_VMO     = {"CANCHAS", "CEDIS", "EXTERIORES", "PATIO DE MANIOBRAS-TRA", "PODIUM-1-2-3",
                  "CAMPO DE GOLF", "PUENTES DE MANGLAR", "BALLROOM"}

def _normalizar_fase(texto: str) -> str | None:
    """Devuelve la fase normalizada, o None si el texto no matchea ninguna fase
    conocida — None es una señal explicita para que el llamador mande el
    documento a pendientes_revision, en vez de asumir una empresa a ciegas."""
    texto_up = (texto or "").upper()
    if "CAVERNAS"            in texto_up: return "CAVERNAS"
    # "MACAO 11" es un error de lectura real de Vision, no una fase: confunde
    # los numeros romanos "II" con dos unos (visto 2026-08-26 en M800012439,
    # cliente "(MACAO 11, ESTRUCTURA)" y obra "MALESPIN MACAO 11"). No existe
    # ninguna fase con ese nombre, asi que mapearlo aca no puede colisionar.
    if ("CIMENTACIONES" in texto_up or "MACAO II" in texto_up
            or "MACAO 2" in texto_up or "MACAO 11" in texto_up): return "MACAO 2"
    if "VIVIENDAS"           in texto_up: return "VIVIENDAS"
    if "PATIO" in texto_up and "TRB" in texto_up: return "PATIO DE MANIOBRAS-TRB"
    if "CANCHAS"             in texto_up: return "CANCHAS"
    if "CEDIS"               in texto_up: return "CEDIS"
    if "EXTERIORES"          in texto_up: return "EXTERIORES"
    if "PATIO" in texto_up and "TRA" in texto_up: return "PATIO DE MANIOBRAS-TRA"
    if "PODIUM"              in texto_up: return "PODIUM-1-2-3"
    if "CAMPO DE GOLF"       in texto_up: return "CAMPO DE GOLF"
    if "PUENTES DE MANGLAR"  in texto_up: return "PUENTES DE MANGLAR"
    if "BALLROOM"            in texto_up: return "BALLROOM"
    return None


# Issue #72 — obra_familia: el mapa de equivalencias que agrupa las variantes
# de facturas.obra_papel (el texto crudo de la linea `OBRA:` NO se toca: es la
# evidencia). Sobre 4.449 filas habia 146 valores crudos / 117 normalizados
# que en realidad son ~20 obras: el campo se llena a mano en la planta y el
# OCR mete variantes encima. El mapeo automatico por similitud se prototipo y
# se DESCARTO: BAHUWER/BAHUUER difieren en una letra y son la misma obra;
# GOBA LADO A/GOBA LADO B difieren en una letra y son obras DISTINTAS. Este
# mapa se confirmo A MANO el 2026-09-14, decision por decision, con la fase de
# las filas como evidencia — esta cerrado. Las claves son formas YA
# normalizadas por el paso mecanico de normalizar_obra_papel().
#
# Separaciones que son DECISION CONFIRMADA, no olvidos:
#   - DIMAX != DIMECA (contratistas distintos, evidencia de fase y fechas)
#   - EXTERIORES != EXTERIORES1111 (fase PODIUM-1-2-3 vs fase EXTERIORES)
#   - GOBA LADO A != GOBA LADO B (el LADO se respeta SIEMPRE)
#   - CAMPAMENTO, MG, PATIO TRA y RATHNER quedan como familias propias.
EQUIVALENCIAS_OBRA = {
    # -> MALESPIN MACAO II
    "MALESPIN": "MALESPIN MACAO II",
    "MALESPIN MALAO II": "MALESPIN MACAO II",
    "HALESPIN MACAO II": "MALESPIN MACAO II",
    "MACAO II ES TRI": "MALESPIN MACAO II",
    "MALOSPIN MACAO II": "MALESPIN MACAO II",
    "MALBSPIN MACAO II": "MALESPIN MACAO II",
    "MALESPIN MACAU II": "MALESPIN MACAO II",
    "MALESPIN MACAD II": "MALESPIN MACAO II",
    "MALESPIN MACAIO II": "MALESPIN MACAO II",
    "MALOSPIN": "MALESPIN MACAO II",
    "HALFESPIN MACAO II": "MALESPIN MACAO II",
    "MACAU II ES TRI": "MALESPIN MACAO II",
    "MAL ESPIN MACAO II": "MALESPIN MACAO II",
    "MALASPIN MACAO II": "MALESPIN MACAO II",
    "MALDSPIN MACAO II": "MALESPIN MACAO II",
    "MALEPSIN MACAO II": "MALESPIN MACAO II",
    "MALESFIN MACAO II": "MALESPIN MACAO II",
    "MALESPIN MACAC II": "MALESPIN MACAO II",
    "MALESPIN MACAO 1": "MALESPIN MACAO II",
    "MALESPIN MACAO I": "MALESPIN MACAO II",
    "MALESPIN MACAO JJ": "MALESPIN MACAO II",
    "MALESPIN MACAQ II": "MALESPIN MACAO II",
    "MALFESPIN MACAO II": "MALESPIN MACAO II",
    "MALGOSPIN MACAO II": "MALESPIN MACAO II",
    "MALOSPIN MALAO II": "MALESPIN MACAO II",
    "MALSPIN MACAO II": "MALESPIN MACAO II",
    "MALESPINI": "MALESPIN MACAO II",
    "WALESPIN MACAO II": "MALESPIN MACAO II",
    # -> PARMOL
    "PARHOL": "PARMOL",
    "BARMOL": "PARMOL",
    "MARMOL": "PARMOL",
    "HARMOL": "PARMOL",
    "PARMOI": "PARMOL",
    # -> EXTERIORES1111 (OJO: "EXTERIORES" a secas NO va aca — es otra obra)
    "EXTERIORES111": "EXTERIORES1111",
    "EXTERIORES11": "EXTERIORES1111",
    "EXTERIORES1141": "EXTERIORES1111",
    "EXTERIORES 1111": "EXTERIORES1111",
    "EXTERIORES1": "EXTERIORES1111",
    "EXTERIORES11111": "EXTERIORES1111",
    "EXTERIORES1113": "EXTERIORES1111",
    "EXTERIOR51111": "EXTERIORES1111",
    "EXTERIOR5311": "EXTERIORES1111",
    "EXTERIORE1111": "EXTERIORES1111",
    "EXTERIORES 111": "EXTERIORES1111",
    "EXTERIORES1131": "EXTERIORES1111",
    # -> BAHUWER (BAHUUER y BAHLUWER confirmadas como la misma obra)
    "BAHUUER": "BAHUWER",
    "BAHLUWER": "BAHUWER",
    "BAHLWER": "BAHUWER",
    "BAHUNER": "BAHUWER",
    "BAHLUMER": "BAHUWER",
    "BAHLINER": "BAHUWER",
    "BAHLUWER PODIUM 4 LADO B": "BAHUWER",
    "BAHUWER CANCHAS": "BAHUWER",
    "BAHLNER": "BAHUWER",
    "BAHUIWER": "BAHUWER",
    "BAHUMNER": "BAHUWER",
    "BAHUUWER": "BAHUWER",
    "BABLUMER": "BAHUWER",
    "BAHJUNER": "BAHUWER",
    "BAHLWNER": "BAHUWER",
    "BAHUIWER CANCHAS": "BAHUWER",
    "BAHUJWER": "BAHUWER",
    "BAHULER": "BAHUWER",
    "BAHUMER": "BAHUWER",
    "BAHUMUER": "BAHUWER",
    "BAHUMWER": "BAHUWER",
    "BAHUUEK": "BAHUWER",
    "BAHUUER CANCHAS": "BAHUWER",
    "BAHUUMER": "BAHUWER",
    "BARILUWER": "BAHUWER",
    "RAHLWER": "BAHUWER",
    "RAHUNNER": "BAHUWER",
    "RAHUWER": "BAHUWER",
    "SAHLUWER": "BAHUWER",
    # -> MOON PALACE GOBAMEX
    "MOON PALACE GORAMEX": "MOON PALACE GOBAMEX",
    "MOON PALACE GOBAMEK": "MOON PALACE GOBAMEX",
    "GOBAMEX": "MOON PALACE GOBAMEX",
    "MOON D ALACE GOBAMEX": "MOON PALACE GOBAMEX",
    "MOON PALACE COBAMEX": "MOON PALACE GOBAMEX",
    "MOON PALACE CORAMEX": "MOON PALACE GOBAMEX",
    "MOON PALACE GDGAMEX": "MOON PALACE GOBAMEX",
    "MOON PALACE GOBANEX": "MOON PALACE GOBAMEX",
    # -> PATIO MANIOBRA MALESPIN (fases PATIO DE MANIOBRAS; NO van con MACAO II)
    "MALESPIN PATIO MANIOBRA": "PATIO MANIOBRA MALESPIN",
    "PATIO MALESPIN": "PATIO MANIOBRA MALESPIN",
    "MALESPIN PATIO HANIOBRA": "PATIO MANIOBRA MALESPIN",
    "MALESPIN PATIO MANJOBRA": "PATIO MANIOBRA MALESPIN",
    "MALESPIN PATIO MANTOBRA": "PATIO MANIOBRA MALESPIN",
    "PATIO MANIOBRA": "PATIO MANIOBRA MALESPIN",
    "PATIO TRA MALESPIN": "PATIO MANIOBRA MALESPIN",
    "HALESPIN PATIO MANTOBRA": "PATIO MANIOBRA MALESPIN",
    "PATIO MANJOBRA MALESPIN": "PATIO MANIOBRA MALESPIN",
    # -> GOBA (el LADO se respeta SIEMPRE: A y B son obras distintas)
    "GORA LADO B": "GOBA LADO B",
    "GOEA LADO A": "GOBA LADO A",
    # -> RABELCA CANCHAS
    "CANCHAS DEPORTIVAS RABELCA": "RABELCA CANCHAS",
    "CANCHAS DEPORTIVAS RABELA": "RABELCA CANCHAS",
    "ZONA DEPORTIVA CANCHA": "RABELCA CANCHAS",
    "CANCHAS DEPORTIVAS RARELA": "RABELCA CANCHAS",
}


def normalizar_obra_papel(texto):
    """None -> None. Si no, normaliza mecanicamente (NFKD sin combinantes —
    saca las tildes—, upper, todo lo que no sea [\\w\\s] a espacio, espacios
    colapsados y strip; cadena vacia despues de eso -> None) y aplica el mapa
    confirmado del issue #72. Un valor desconocido devuelve su forma mecanica
    (familia propia): NUNCA se fusiona por parecido — ver EQUIVALENCIAS_OBRA
    por el porque. obra_familia es SOLO para auditar/agrupar: no entra en
    ninguna clasificacion, matcheo de precios ni generacion de documentos."""
    if texto is None:
        return None
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c)).upper()
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    if not texto:
        return None
    return EQUIVALENCIAS_OBRA.get(texto, texto)


def _est_buscar_precio(conn, empresa, fase, descripcion):
    """Matchea precio por descripcion (nunca por id_producto/codigo — Vision
    no lee ese codigo de forma confiable: en MACAO 2, que es la unica fase a la
    que historicamente se le pidio, el 31% de los codigos guardados no existe en
    la lista de precios de su fase, y 158 no son ni codigos (146 son el numero
    de conduce del propio documento, 6 el RNC de Domicem, 5 el identificador del
    formulario). OJO: este comentario decia "sobre todo en VMO" y eso era falso
    — corregido 2026-09-02, issue #48. Hasta esa fecha la Fase 1 del importador
    usaba verificar_firma(), que solo pide tiene_sello/tiene_firma, asi que a las
    901 facturas de las otras 8 fases nunca se les pidio el codigo. No habia un
    solo intento fallido de VMO: no habia ningun intento. Esa frase indujo la
    premisa equivocada del issue #40). Primitiva
    compartida (issue #19) entre _enriquecer_y_matchear() y
    scripts/importar_puente.py, con la semantica que ambos ya tenian:
    DOMICEM filtra por fase exacta; cualquier otra empresa (incluida None,
    camino real del script para filas de fase no reconocida) consulta
    precios_vmo prefiriendo la fila de fase exacta y cayendo a fase NULL.
    Devuelve el precio_unitario o None si no hay match."""
    desc = (descripcion or "").strip()
    if not desc:
        return None
    if empresa == "DOMICEM":
        row = conn.execute(
            "SELECT precio_unitario FROM precios_domicem WHERE TRIM(descripcion) = ? AND fase = ?",
            (desc, fase)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT precio_unitario FROM precios_vmo WHERE TRIM(descripcion) = ? AND (fase = ? OR fase IS NULL) ORDER BY fase IS NULL",
            (desc, fase)
        ).fetchone()
    return row[0] if row else None


def _enriquecer_y_matchear(conn, datos: dict, info: dict, nombre_base: str, lookup: dict) -> dict:
    """Combina datos del nombre de archivo con lo extraido por Vision, determina
    empresa/fase, y matchea precio por descripcion (no por id_producto/codigo —
    Vision no lee ese codigo de forma confiable; ver el detalle medido en el
    docstring de _est_buscar_precio(). La version vieja de esta linea decia
    "sobre todo en VMO" y era falso: corregido 2026-09-02, issue #48).

    Issue #15 — el Excel de conduces (`lookup`) es la fuente de verdad de la
    descripcion y de la fase cuando hay una fila que resuelve este documento
    sin contradicciones: la descripcion de Vision se reemplaza siempre por la
    del Excel (se guarda la correccion en datos["_correccion_excel"] si
    diferian), y la fase se deriva EXCLUSIVAMENTE del Cliente del Excel — sin
    respaldo al cliente/obra que leyo Vision, que es justo la puerta por la
    que entro el bug de "MACAO 11". Sin fila resoluble, fase queda en None
    (el documento ya esta marcado para pendientes_revision via
    datos["_sin_fila_excel"], _motivo_sello_firma lo bloquea antes que nada)."""
    datos["fecha"]        = info["fecha"]
    datos["planta"]       = info["planta"]
    datos["id_documento"] = info["id_documento"]
    datos["archivo_pdf"]  = nombre_base
    # Issue #67 — la linea `OBRA:` del papel, que _procesar_pdf_sync() ya
    # venia leyendo bien (medido el 2026-09-07: 10/10 sobre los fixtures de
    # DIMECA/CONCAVA/LIDOMI) y que hasta ahora solo sobrevivia mezclada en
    # `obra`. Se copia en su propia columna en vez de mover el dato: `obra`
    # tiene DOS semanticas segun el camino (por importar_puente.py vale la
    # fase; por aca, lo que devuelva Vision) y unificarlas no es este issue.
    # En este camino las dos columnas coinciden a proposito; por el masivo no.
    datos["obra_papel"]   = datos.get("obra")
    # Issue #72 — obra_familia: la forma normalizada/agrupada de esa misma
    # lectura (mapa confirmado en EQUIVALENCIAS_OBRA). Solo para
    # auditar/agrupar: no entra en clasificacion, precios ni documentos.
    datos["obra_familia"] = normalizar_obra_papel(datos.get("obra"))

    fila, motivo_excel = _resolver_fila_excel(lookup, nombre_base, info["id_documento"])
    if motivo_excel:
        datos["_sin_fila_excel"] = True
        datos["_motivo_excel"] = motivo_excel
        fase_norm = None
    else:
        desc_vision = (datos.get("descripcion") or "").strip()
        if desc_vision != fila["descripcion"]:
            datos["_correccion_excel"] = {
                "campo": "descripcion", "vision": desc_vision, "excel": fila["descripcion"],
            }
        datos["descripcion"] = fila["descripcion"]
        # La cantidad tambien manda el Excel (2026-10-20): una firma o una
        # anotacion encima del numero hace que Vision lea 9 donde dice 7, o
        # 1 donde dice 7 (M800016570, M800016621 y 42 de MACAO 2 en el
        # periodo 17/09-16/10). Sin Cant. en la fila se queda lo de Vision.
        cant_excel = fila.get("cantidad")
        if cant_excel is not None:
            cant_vision = datos.get("cantidad")
            if not isinstance(cant_vision, (int, float)) or abs(cant_vision - cant_excel) > 0.001:
                datos["_correccion_excel_cantidad"] = {
                    "campo": "cantidad", "vision": cant_vision, "excel": cant_excel,
                }
            datos["cantidad"] = cant_excel
        datos["_cliente_excel"] = fila["cliente"]
        fase_norm = _normalizar_fase(fila["cliente"])

    empresa = None if fase_norm is None else ("DOMICEM" if fase_norm in FASES_DOMICEM else "VMO")
    datos["empresa"] = empresa
    datos["fase"] = fase_norm

    descripcion_prod = (datos.get("descripcion") or "").strip()
    cantidad = datos.get("cantidad") or 0
    # Issue #19: las consultas viven en _est_buscar_precio() (compartida con
    # scripts/importar_puente.py). El guard de empresa None se queda ACA y no
    # en la primitiva: en este camino un documento sin fase reconocida ya va
    # a pendientes_revision sin precio, mientras que el script consulta
    # precios_vmo tambien con empresa None — comportamiento que conserva.
    if empresa is None:
        precio = None
    else:
        precio = _est_buscar_precio(conn, empresa, fase_norm, descripcion_prod)

    if precio is not None:
        datos["precio_unitario"] = precio
        datos["total"] = round(precio * cantidad, 2)
    else:
        datos["precio_unitario"] = None
        datos["total"] = None

    return datos


def _motivo_sello_firma(datos: dict):
    """None si el documento se puede importar. Regla fase-condicional
    (issue #8, 2026-08-24): el jefe confirmo que la regla de MACAO 2
    (sello obligatorio, firma no bloquea — issue #7) es especifica de esa
    fase, no general. Cualquier otra fase exige lo contrario: firma
    obligatoria, sello no bloquea. Fase no reconocida se chequea PRIMERO —
    es mas facil de resolver reenviando el documento correcto que buscar el
    sello/firma fisico, asi que es el motivo mas util de mostrar si aplican
    varios problemas a la vez.

    Issue #15: sin fila en el Excel (o el Excel contradiciendose para este
    documento) se chequea ANTES que fase no reconocida — mismo criterio,
    es un motivo mas accionable y ya implica fase=None de todas formas."""
    if datos.get("_sin_fila_excel"):
        return datos.get("_motivo_excel") or "sin fila en el Excel"
    if datos.get("fase") is None:
        return "fase no reconocida"
    if datos.get("fase") == "MACAO 2":
        if not datos.get("tiene_sello"):
            return "falta sello"
    elif not datos.get("tiene_firma"):
        return "falta firma"
    # Va ULTIMO a proposito: solo cambia algo cuando el documento iba a
    # entrar, que es justo el caso peligroso — una lectura girada no falla,
    # entra completa y equivocada (ver la trampa del HANDOFF).
    if datos.get("_pagina_vertical"):
        return EST_MOTIVO_PAGINA_VERTICAL
    return None


def _guardar_pendiente_revision(conn, datos: dict, motivo: str, pdf_bytes: bytes, ahora: str | None = None):
    """Guarda el PDF + los datos que Vision alcanzo a leer en la zona de
    pendientes por revision (falta sello/firma). No se le vuelve a aplicar
    Vision a esto nunca — solo aparece en el resumen hasta que alguien
    resuba el documento corregido.

    Issue #19 — tambien la llama scripts/importar_puente.py, que antes tenia
    su propia copia. De ahi los dos ajustes compatibles hacia atras: `ahora`
    opcional (el script fecha todo el lote con un mismo timestamp; sin
    argumento se conserva el datetime.now() de siempre) y el guard del PDF
    (el script contemplaba pdf_bytes/archivo_pdf ausentes; los llamadores de
    core siempre los traen, para ellos nada cambia)."""
    if ahora is None:
        ahora = datetime.now().isoformat()
    conn.execute(
        """INSERT OR REPLACE INTO pendientes_revision
           (archivo_pdf, id_documento, fecha, planta, orden_compra, referencia,
            distancia, cliente, obra, obra_papel, obra_familia, bomba,
            id_producto, descripcion,
            cantidad, precio_unitario, total, ficha, chofer, hora_salida,
            observaciones, empresa, fase, motivo, fecha_pendiente)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            datos.get("archivo_pdf"), datos.get("id_documento"), datos.get("fecha"),
            datos.get("planta"), datos.get("orden_compra"), datos.get("referencia"),
            datos.get("distancia"), datos.get("cliente"), datos.get("obra"),
            datos.get("obra_papel"), datos.get("obra_familia"),
            datos.get("bomba"), datos.get("id_producto"), datos.get("descripcion"),
            datos.get("cantidad"), datos.get("precio_unitario"), datos.get("total"),
            datos.get("ficha"), datos.get("chofer"), datos.get("hora_salida"),
            datos.get("observaciones"), datos.get("empresa"), datos.get("fase"),
            motivo, ahora
        )
    )
    if datos.get("archivo_pdf") and pdf_bytes is not None:
        with open(os.path.join(EST_PENDIENTES, datos["archivo_pdf"]), "wb") as f:
            f.write(pdf_bytes)


def _est_resolver_pendiente(conn, id_documento) -> int:
    """Si este id_documento ya estaba en pendientes_revision (version anterior
    sin sello/firma) y ahora llega una version valida, se saca de pendientes
    automaticamente — el sistema detecta que ya se resolvio. Devuelve cuantas
    filas de pendientes_revision borro (0 o 1). Primitiva compartida (issue
    #19, antes _resolver_pendiente_si_existe + copia en importar_puente.py):
    no maneja transaccion propia ni atrapa el OSError del borrado del PDF —
    el llamador decide (el SAVEPOINT de _confirmar_registros revierte el
    registro entero; el script lo traga y deja el PDF huerfano detectable)."""
    if not id_documento:
        return 0
    row = conn.execute(
        "SELECT archivo_pdf FROM pendientes_revision WHERE id_documento = ?", (id_documento,)
    ).fetchone()
    if not row:
        return 0
    archivo_pdf_pendiente = row[0]
    borradas = conn.execute(
        "DELETE FROM pendientes_revision WHERE id_documento = ?", (id_documento,)
    ).rowcount
    # El nombre sale de la BD, pero igual se valida antes de borrar.
    pdf_path = os.path.join(EST_PENDIENTES, _nombre_archivo_seguro(archivo_pdf_pendiente))
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
    return borradas


def _est_insertar_factura(conn, registro: dict) -> int:
    """INSERT OR IGNORE de UNA fila en facturas. Primitiva compartida (issue
    #19) entre _confirmar_registros() (que la envuelve en su SAVEPOINT) y
    scripts/importar_puente.py (que corre dentro de su propia transaccion):
    no abre ni cierra transaccion — el llamador decide. Devuelve el rowcount
    del INSERT: 0 si el id_documento ya existia, 1 si entro.

    Escribe 30 de las 31 columnas de la tabla (obra_papel entro con el issue
    #67, obra_familia con el #72); clave_resuelta queda fuera A PROPOSITO — la escribe despues la
    resolucion manual (issue #11) y la importacion nunca debe tocarla.

    Issue #20: las 5 columnas de aprobacion manual (aprobado_manual,
    aprobado_por, aprobado_motivo, aprobado_fecha, motivo_bloqueo) solo las
    puebla _est_aprobar_pendiente() — los llamadores de importacion no las
    pasan y quedan como siempre: aprobado_manual=0 y el resto en NULL,
    comportamiento identico al anterior a ese issue."""
    cursor = conn.execute(
        """INSERT OR IGNORE INTO facturas
           (id_documento, fecha, planta, orden_compra, referencia, distancia,
            cliente, obra, obra_papel, obra_familia, bomba, id_producto,
            descripcion, cantidad,
            precio_unitario, total, ficha, chofer, hora_salida,
            observaciones, archivo_pdf, empresa, fase, fecha_importacion, sin_firma,
            aprobado_manual, aprobado_por, aprobado_motivo, aprobado_fecha, motivo_bloqueo)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            registro.get("id_documento"), registro.get("fecha"), registro.get("planta"),
            registro.get("orden_compra"), registro.get("referencia"), registro.get("distancia"),
            registro.get("cliente"), registro.get("obra"), registro.get("obra_papel"),
            registro.get("obra_familia"), registro.get("bomba"),
            registro.get("id_producto"), registro.get("descripcion"), registro.get("cantidad"),
            registro.get("precio_unitario"), registro.get("total"),
            registro.get("ficha"), registro.get("chofer"), registro.get("hora_salida"),
            registro.get("observaciones"), registro.get("archivo_pdf"),
            registro.get("empresa"), registro.get("fase"),
            registro.get("fecha_importacion"), 1 if registro.get("sin_firma") else 0,
            1 if registro.get("aprobado_manual") else 0, registro.get("aprobado_por"),
            registro.get("aprobado_motivo"), registro.get("aprobado_fecha"),
            registro.get("motivo_bloqueo")
        )
    )
    return cursor.rowcount


# Issue #20 — la restriccion central de la aprobacion manual: solo estos
# motivos son aprobables. "sin fila en el Excel" y "fase no reconocida"
# quedan fuera A PROPOSITO: sin fase el sistema no sabe a que clave del
# catalogo va el conduce, y aprobarlo mete m3 que despues hay que adivinar
# donde poner — exactamente el mecanismo que produjo el error de los 370 m3
# de CAVERNAS. Esos se arreglan con el documento o con el Excel, no aca.
#
# EST_MOTIVO_PAGINA_VERTICAL si es aprobable: la fase se conoce, y el unico
# vertical que existe hoy (M800015683) es un escaneo atascado pero derecho,
# que no tiene otro camino de entrada. Quien lo apruebe tiene que comparar
# la cantidad contra el papel — por el camino individual sale de Vision.
EST_MOTIVOS_APROBABLES = ("falta sello", "falta firma", EST_MOTIVO_PAGINA_VERTICAL)

# Las 23 columnas que facturas y pendientes_revision comparten con el mismo
# nombre — lo que hace completa (no parcial) la reconstruccion del pendiente
# al revertir una aprobacion, y el registro al aprobarla. pendientes_revision
# suma motivo + fecha_pendiente; facturas suma archivo/importacion/aprobacion.
# Issue #67: obra_papel entra aca el mismo dia que la columna. Olvidarla
# habria hecho que aprobar un pendiente perdiera el dato EN SILENCIO — los
# INSERT de _est_revertir_aprobacion(), _est_descartar_pendiente() y
# _est_reponer_descartado() se arman con esta tupla, y _est_aprobar_pendiente()
# arma su registro con ella. Issue #72: obra_familia, por el mismo motivo.
_EST_COLUMNAS_COMPARTIDAS = (
    "archivo_pdf", "id_documento", "fecha", "planta", "orden_compra",
    "referencia", "distancia", "cliente", "obra", "obra_papel", "obra_familia",
    "bomba",
    "id_producto", "descripcion", "cantidad", "precio_unitario", "total",
    "ficha", "chofer", "hora_salida", "observaciones", "empresa", "fase",
)


def _est_corte_de_conteo(conn, empresa: str, fase: str):
    """Issue #20 — el corte vigente de (empresa, fase): la fecha hasta la
    cual los m3 ya estan contados en el acumulado (seed + estimaciones
    cerradas). Es la misma nocion de corte que _est_calcular_acumulados()
    aplica por producto (`if fecha <= corte: continue`); aca se expone
    agregada por fase (el MAX entre todos los productos) para poder avisar
    ANTES de aprobar un pendiente cuya fecha cae debajo — sin este aviso el
    boton Aprobar pareceria funcionar sin mover un solo numero (las 41
    pendientes reales de MACAO 2 estan todas debajo del corte 2026-08-16).

    Devuelve el mayor entre MAX(fecha_base) del seed y MAX(fecha_hasta) de
    las cerradas, o None si la fase no tiene ni seed ni cierres. Tolera que
    las tablas no existan (BD minima de tests, o anterior a las migraciones)
    con el mismo criterio documentado en _est_cerradas_previas(): equivale a
    'no hay nada contado'."""
    corte = None
    for consulta in (
        "SELECT MAX(fecha_base) FROM estimacion_acumulado_base WHERE empresa = ? AND fase = ?",
        "SELECT MAX(fecha_hasta) FROM estimacion_cerrada WHERE empresa = ? AND fase = ?",
    ):
        try:
            valor = conn.execute(consulta, (empresa, fase)).fetchone()[0]
        except sqlite3.OperationalError:
            valor = None
        if valor is not None and (corte is None or valor > corte):
            corte = valor
    return corte


def _est_aprobar_pendiente(conn, archivo_pdf: str, aprobado_por: str, motivo: str,
                           ahora: str | None = None) -> dict:
    """Issue #20 — aprueba a mano UN pendiente bloqueado por falta de
    sello/firma: lo mueve de pendientes_revision a facturas dejando rastro
    permanente de quien, por que y cuando. Primitiva compartida al estilo de
    _est_resolver_pendiente() y _est_insertar_factura(): sin transaccion
    propia (el llamador decide) y SOLO BD — valida que los archivos esten
    donde deben (origen presente, destino libre) pero nunca copia ni borra
    un PDF; el endpoint orquesta el disco con la secuencia copiar → COMMIT →
    borrar origen, porque una transaccion de SQLite no revierte un archivo
    movido.

    Todas las entradas invalidas levantan ValueError (→ 400 en la ruta,
    mismo criterio que el issue #15: es estado o entrada que el operador
    puede corregir). El archivo_pdf llega del cliente y arma rutas, asi que
    pasa primero por _nombre_archivo_seguro() — sin eso, un `../` deja
    escribir y borrar fuera de EST_PENDIENTES/EST_PROCESADAS.

    `ahora` por defecto es datetime.now().isoformat() — hora local sin zona,
    el mismo formato y reloj que fecha_pendiente y fecha_importacion. OJO:
    cerrada_en (issue #17) se escribe en UTC con sufijo 'Z'
    (core._est_cerrar_estimacion), NO en este formato — ver el docstring de
    _est_motivo_no_reversible() por lo que implica para la guarda de la
    reversa.

    Devuelve {"id_documento", "cuenta_para_estimaciones", "corte"}.
    cuenta_para_estimaciones se define exactamente asi, sin otro criterio:
    False si la fecha del pendiente es NULL (sin fecha no se puede afirmar
    que vaya a contar — lado conservador), o si hay corte y fecha <= corte;
    True en cualquier otro caso. Aprobar debajo del corte se permite igual,
    con aviso: el libro mayor de estimaciones cerradas NO se toca."""
    archivo_pdf = _nombre_archivo_seguro(archivo_pdf)
    if ahora is None:
        ahora = datetime.now().isoformat()

    cur = conn.execute("SELECT * FROM pendientes_revision WHERE archivo_pdf = ?", (archivo_pdf,))
    row = cur.fetchone()
    if row is None:
        raise ValueError("no existe ese pendiente")
    fila = dict(zip([c[0] for c in cur.description], row))

    # La restriccion central del issue: solo falta sello / falta firma.
    if fila.get("motivo") not in EST_MOTIVOS_APROBABLES:
        raise ValueError(
            f"solo se puede aprobar {', '.join(repr(m) for m in EST_MOTIVOS_APROBABLES)} — este pendiente "
            f"está bloqueado por '{fila.get('motivo')}' y se resuelve corrigiendo "
            f"el documento o el Excel, no aprobando"
        )

    # El motivo del operador es obligatorio, no opcional — igual que quien.
    aprobado_por = (aprobado_por or "").strip()
    motivo = (motivo or "").strip()
    if not aprobado_por:
        raise ValueError("falta indicar quién aprueba")
    if not motivo:
        raise ValueError("falta el motivo de la aprobación")

    # Sin id_documento no hay PK para facturas ni forma de revertir despues.
    # No deberia pasar (el id sale del nombre del archivo o del Excel antes
    # de llegar a pendientes), pero id_documento es nullable en la tabla y
    # un TEXT PRIMARY KEY de SQLite acepta NULL — mejor fallar ruidoso que
    # insertar una factura inencontrable.
    if not fila.get("id_documento"):
        raise ValueError("el pendiente no tiene id_documento legible — se resuelve "
                         "resubiendo el documento corregido, no aprobando")

    # Guardas de archivo ANTES de tocar la BD: nunca se aprueba un conduce
    # cuyo PDF no existe, ni se sobrescribe un PDF ya procesado.
    origen  = os.path.join(EST_PENDIENTES, archivo_pdf)
    destino = os.path.join(EST_PROCESADAS, archivo_pdf)
    if not os.path.exists(origen):
        raise ValueError("el PDF del pendiente no está en pendientes_revision/")
    if os.path.exists(destino):
        raise ValueError("ya existe un PDF con ese nombre en procesadas/")

    registro = {col: fila.get(col) for col in _EST_COLUMNAS_COMPARTIDAS}
    registro.update({
        "fecha_importacion": ahora,
        # sin_firma=1 cuando el bloqueo fue por firma, para quedar
        # consistente con lo que ya marca el import (issue #7/#8).
        "sin_firma": fila.get("motivo") == "falta firma",
        "aprobado_manual": 1,
        "aprobado_por": aprobado_por,
        "aprobado_motivo": motivo,
        "aprobado_fecha": ahora,
        "motivo_bloqueo": fila.get("motivo"),
    })
    if _est_insertar_factura(conn, registro) == 0:
        # el id_documento ya estaba en facturas — no se aprueba encima de
        # una factura existente, y no se borra nada
        raise ValueError(f"ya existe una factura con el id {fila['id_documento']} — "
                         f"no se puede aprobar encima")

    conn.execute("DELETE FROM pendientes_revision WHERE archivo_pdf = ?", (archivo_pdf,))

    corte = _est_corte_de_conteo(conn, fila.get("empresa"), fila.get("fase"))
    fecha = fila.get("fecha")
    cuenta = not (fecha is None or (corte is not None and fecha <= corte))
    return {"id_documento": fila["id_documento"],
            "cuenta_para_estimaciones": cuenta, "corte": corte}


def _est_parsear_cerrada_en(texto):
    """Issue #20 — cerrada_en como instante: _est_cerrar_estimacion() la
    escribe SIEMPRE en UTC con sufijo 'Z' y precision de segundos (issue
    #17), asi que se parsea exactamente ese formato y se le adjunta
    timezone.utc. Devuelve None si no parsea — filas anteriores al issue #17
    o editadas a mano podrian traer otro formato, y el llamador decide que
    hacer con eso (la guarda de la reversa las trata como bloqueantes, el
    lado seguro, en vez de reventar con una excepcion)."""
    try:
        return datetime.strptime(texto, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _est_parsear_aprobado_fecha(texto):
    """Issue #20 — aprobado_fecha como instante: _est_aprobar_pendiente() la
    escribe como isoformat() local sin zona, asi que a un valor naive se le
    adjunta la zona local del sistema (.astimezone() sobre el naive). Un
    valor que ya trae offset explicito se respeta tal cual — los tests lo
    usan para no depender del huso de la maquina donde corren. None si no
    parsea o es NULL."""
    try:
        dt = datetime.fromisoformat(texto)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt


def _est_motivo_no_reversible(conn, fila: dict):
    """Issue #20 — evalua la guarda de la reversa sobre una fila de facturas
    (dict por nombre de columna) y devuelve el motivo (str) por el que NO se
    puede revertir, o None si se puede. Una sola definicion, dos usos: el
    listado /aprobados-manualmente la precalcula por fila (para deshabilitar
    el boton con el motivo en el title en vez de fallar recien al apretarlo)
    y _est_revertir_aprobacion() la revalida antes de escribir (el listado
    puede haber quedado viejo si alguien cerro una estimacion con la
    pantalla abierta).

    La guarda del libro mayor: se niega si existe una estimacion cerrada de
    esa (empresa, fase) que cubra la fecha del conduce y cuyo cerrada_en sea
    posterior (`>` ESTRICTO) al aprobado_fecha — si se cerro DESPUES de la
    aprobacion el conduce pudo haber entrado en ese numero y sacarlo
    desincronizaria el libro mayor; si se cerro ANTES, nunca formo parte de
    ese cierre y revertir no cambia ningun numero. Con `>=` las 41
    pendientes reales quedarian irreversibles sin motivo real. NO filtra por
    clave ni serie, intencionalmente: saber a que clave/serie habria ido
    exige correr el clasificador completo, cuyo resultado puede diferir del
    que corria al cerrar — bloquear de mas es el lado seguro. Con fecha NULL
    la guarda nunca matchea (NULL BETWEEN ... es NULL en SQL) y la reversa
    procede: un conduce sin fecha tampoco pudo entrar en ningun cierre.

    La comparacion cerrada_en/aprobado_fecha se hace en Python como
    INSTANTES reales, no en SQL como texto. El spec del issue #20 pedia la
    comparacion de texto asumiendo que ambas marcas compartian formato y
    reloj, pero no es asi (verificado contra la BD real): cerrada_en es UTC
    con sufijo 'Z' y precision de segundos (issue #17), aprobado_fecha es
    isoformat() local con microsegundos. Comparadas como texto, el orden
    lexicografico NO era el cronologico: con el huso local detras de UTC un
    cierre hecho hasta |offset| horas ANTES de la aprobacion todavia
    comparaba como posterior y bloqueaba reversas legitimas; con un huso
    adelantado dejaria pasar reversas de conduces que SI entraron en un
    cierre — desincronizando el libro mayor. Por eso cada marca se parsea
    con su formato y zona reales (_est_parsear_cerrada_en /
    _est_parsear_aprobado_fecha) y se comparan como datetimes aware. Una
    marca NULL o que no parsea (fila vieja o editada a mano) hace
    bloqueante al cierre en cuestion — lado seguro, nunca una excepcion.

    Un motivo_bloqueo NULL en una fila aprobado_manual=1 solo es posible por
    migracion incompleta o edicion manual, nunca por este codigo: se niega
    en vez de reinsertar un pendiente sin motivo (romperia la guarda de
    motivo de _est_aprobar_pendiente). Las guardas de archivo son las mismas
    dos del aprobar, espejadas: el PDF tiene que estar en procesadas/ y su
    lugar en pendientes_revision/ tiene que estar libre."""
    if fila.get("aprobado_manual") != 1:
        return "esa factura no fue aprobada a mano — no hay nada que revertir"
    if fila.get("motivo_bloqueo") is None:
        return ("la fila no tiene motivo_bloqueo (migración incompleta o edición "
                "manual) — revertirla dejaría un pendiente sin motivo, revisar a mano")
    try:
        archivo_pdf = _nombre_archivo_seguro(fila.get("archivo_pdf"))
    except HTTPException:
        return "el archivo_pdf de la factura no es un nombre de archivo válido"
    try:
        cierres = conn.execute(
            """SELECT cerrada_en FROM estimacion_cerrada e
                WHERE e.empresa = ? AND e.fase = ?
                  AND ? BETWEEN e.fecha_desde AND e.fecha_hasta""",
            (fila.get("empresa"), fila.get("fase"), fila.get("fecha")),
        ).fetchall()
    except sqlite3.OperationalError:
        cierres = []  # sin tabla de cerradas no hay cierre que proteger
    if cierres:
        aprobado_dt = _est_parsear_aprobado_fecha(fila.get("aprobado_fecha"))
        if aprobado_dt is None:
            return ("hay un cierre que cubre la fecha del conduce y la aprobación "
                    "no se puede ubicar en el tiempo (aprobado_fecha ausente o "
                    "ilegible) — se bloquea por el lado seguro, revisar a mano")
        for (cerrada_en,) in cierres:
            cerrada_dt = _est_parsear_cerrada_en(cerrada_en)
            if cerrada_dt is None:
                return (f"un cierre que cubre la fecha del conduce tiene cerrada_en "
                        f"ilegible ('{cerrada_en}') — se bloquea por el lado seguro, "
                        f"revisar a mano")
            if cerrada_dt > aprobado_dt:
                return ("el conduce entró en una estimación cerrada después de su "
                        "aprobación — revertirlo desincronizaría el libro mayor")
    if conn.execute("SELECT 1 FROM pendientes_revision WHERE archivo_pdf = ?",
                    (archivo_pdf,)).fetchone() is not None:
        # no se usa INSERT OR REPLACE: pisar un pendiente vivo con el que
        # vuelve perderia el motivo y la fecha del que ya estaba
        return "ya hay un pendiente de revisión con ese mismo archivo_pdf"
    if not os.path.exists(os.path.join(EST_PROCESADAS, archivo_pdf)):
        return "el PDF de la factura no está en procesadas/"
    if os.path.exists(os.path.join(EST_PENDIENTES, archivo_pdf)):
        return "ya existe un PDF con ese nombre en pendientes_revision/"
    return None


def _est_revertir_aprobacion(conn, id_documento: str, ahora: str | None = None) -> dict:
    """Issue #20 — deshace una aprobacion manual que todavia no entro en una
    estimacion cerrada: borra la fila de facturas y reconstruye el pendiente
    COMPLETO (las 21 columnas compartidas, no un subconjunto) con su motivo
    original (motivo_bloqueo) y fecha_pendiente = ahora. Mismo contrato que
    _est_aprobar_pendiente(): sin transaccion propia, solo BD — el endpoint
    mueve el PDF de procesadas/ a pendientes_revision/ con la misma
    secuencia copiar → COMMIT → borrar origen.

    Toda la logica de elegibilidad vive en _est_motivo_no_reversible() (ver
    su docstring por la guarda del libro mayor y el `>` estricto); aca solo
    se aplica y se ejecuta. ValueError ante cualquier motivo (→ 400)."""
    if ahora is None:
        ahora = datetime.now().isoformat()
    cur = conn.execute("SELECT * FROM facturas WHERE id_documento = ?", (id_documento,))
    row = cur.fetchone()
    if row is None:
        raise ValueError("no existe una factura con ese id_documento")
    fila = dict(zip([c[0] for c in cur.description], row))

    motivo_bloqueado = _est_motivo_no_reversible(conn, fila)
    if motivo_bloqueado is not None:
        raise ValueError(motivo_bloqueado)

    columnas = ", ".join(_EST_COLUMNAS_COMPARTIDAS)
    marcadores = ",".join("?" for _ in _EST_COLUMNAS_COMPARTIDAS)
    conn.execute(
        f"INSERT INTO pendientes_revision ({columnas}, motivo, fecha_pendiente) "
        f"VALUES ({marcadores},?,?)",
        tuple(fila.get(col) for col in _EST_COLUMNAS_COMPARTIDAS)
        + (fila["motivo_bloqueo"], ahora),
    )
    conn.execute("DELETE FROM facturas WHERE id_documento = ?", (id_documento,))
    return {"archivo_pdf": fila["archivo_pdf"]}


# ── Issue #38 — descartar / reponer un pendiente que no corresponde facturar ──
#
# El bloqueo del cierre (_est_pendientes_del_periodo) se niega a cerrar con
# pendientes del periodo. Sin una salida legitima, un conduce que genuinamente
# no debe cobrarse (sin sello, invalido, duplicado) solo podria destrabarse
# APROBANDOLO — metiendo plata en un documento que va al cliente. Descartar es
# esa salida, y reponer es su vuelta atras: un clic equivocado no puede borrar
# un conduce real.

def _est_descartar_pendiente(conn, archivo_pdf: str, descartado_por: str, motivo: str,
                             ahora: str | None = None) -> dict:
    """Issue #38 — saca UN pendiente de pendientes_revision y lo archiva en
    pendiente_descartado dejando rastro de quien, por que y cuando. NUNCA
    escribe en facturas: descartar es lo contrario de aprobar, el conduce no
    se cobra.

    Mismo contrato que _est_aprobar_pendiente(): sin transaccion propia (el
    llamador decide), SOLO BD — valida que los archivos esten donde deben
    (origen presente en pendientes_revision/, destino libre en descartadas/)
    pero nunca copia ni borra un PDF; el endpoint orquesta el disco con
    _mover_pdf_con_transaccion() (copiar → COMMIT → borrar origen). Toda
    entrada o estado invalido levanta ValueError (→ 400 en la ruta).

    A diferencia de aprobar, NO se restringe por motivo: aprobar mete m3 en el
    documento del cliente y por eso solo admite 'falta sello'/'falta firma';
    descartar no mete nada, y un pendiente bloqueado por fase no reconocida o
    por conflicto en el Excel tambien puede no corresponder facturarlo.

    Se archiva ademas fecha_pendiente (cuando entro a pendientes) para que
    /reponer devuelva el pendiente EXACTO — no una copia con la fecha del
    momento en que se deshizo el error."""
    archivo_pdf = _nombre_archivo_seguro(archivo_pdf)
    if ahora is None:
        ahora = datetime.now().isoformat()

    cur = conn.execute("SELECT * FROM pendientes_revision WHERE archivo_pdf = ?", (archivo_pdf,))
    row = cur.fetchone()
    if row is None:
        raise ValueError("no existe ese pendiente")
    fila = dict(zip([c[0] for c in cur.description], row))

    descartado_por = (descartado_por or "").strip()
    motivo = (motivo or "").strip()
    if not descartado_por:
        raise ValueError("falta indicar quién descarta")
    if not motivo:
        raise ValueError("falta el motivo del descarte")

    # Guardas de archivo ANTES de tocar la BD, las mismas dos de aprobar
    # espejadas contra descartadas/.
    origen  = os.path.join(EST_PENDIENTES, archivo_pdf)
    destino = os.path.join(EST_DESCARTADOS, archivo_pdf)
    if not os.path.exists(origen):
        raise ValueError("el PDF del pendiente no está en pendientes_revision/")
    if os.path.exists(destino):
        raise ValueError("ya existe un PDF con ese nombre en descartadas/")

    # La PK de pendiente_descartado ya lo impediria, pero un IntegrityError
    # llega a la ruta como 500 generico; el mensaje explicito le dice al
    # operador que el camino es reponer primero.
    if conn.execute("SELECT 1 FROM pendiente_descartado WHERE archivo_pdf = ?",
                    (archivo_pdf,)).fetchone() is not None:
        raise ValueError("ya hay un descarte registrado con ese archivo_pdf — "
                         "reponerlo antes de volver a descartarlo")

    columnas = ", ".join(_EST_COLUMNAS_COMPARTIDAS)
    marcadores = ",".join("?" for _ in _EST_COLUMNAS_COMPARTIDAS)
    conn.execute(
        f"INSERT INTO pendiente_descartado ({columnas}, fecha_pendiente, motivo_bloqueo, "
        f"descartado_por, descartado_motivo, descartado_fecha) "
        f"VALUES ({marcadores},?,?,?,?,?)",
        tuple(fila.get(col) for col in _EST_COLUMNAS_COMPARTIDAS)
        + (fila.get("fecha_pendiente"), fila.get("motivo"),
           descartado_por, motivo, ahora),
    )
    conn.execute("DELETE FROM pendientes_revision WHERE archivo_pdf = ?", (archivo_pdf,))
    return {"archivo_pdf": archivo_pdf, "id_documento": fila.get("id_documento")}


def _est_reponer_descartado(conn, archivo_pdf: str, ahora: str | None = None) -> dict:
    """Issue #38 — deshace un descarte: devuelve la fila a
    pendientes_revision con su motivo original (motivo_bloqueo) y su
    fecha_pendiente original, y borra el archivo del descarte. Sin body extra
    a proposito: reponer no es un juicio, es deshacer.

    Mismo contrato que _est_descartar_pendiente() (sin transaccion propia,
    solo BD, ValueError → 400) con las guardas espejadas: el PDF tiene que
    estar en descartadas/ y su lugar en pendientes_revision/ tiene que estar
    libre — fila Y archivo, porque pisar un pendiente vivo perderia su motivo
    y su fecha (mismo criterio que la reversa del issue #20)."""
    archivo_pdf = _nombre_archivo_seguro(archivo_pdf)
    if ahora is None:
        ahora = datetime.now().isoformat()

    cur = conn.execute("SELECT * FROM pendiente_descartado WHERE archivo_pdf = ?", (archivo_pdf,))
    row = cur.fetchone()
    if row is None:
        raise ValueError("no hay ningún descarte registrado con ese archivo_pdf")
    fila = dict(zip([c[0] for c in cur.description], row))

    if conn.execute("SELECT 1 FROM pendientes_revision WHERE archivo_pdf = ?",
                    (archivo_pdf,)).fetchone() is not None:
        raise ValueError("ya hay un pendiente de revisión con ese mismo archivo_pdf")

    origen  = os.path.join(EST_DESCARTADOS, archivo_pdf)
    destino = os.path.join(EST_PENDIENTES, archivo_pdf)
    if not os.path.exists(origen):
        raise ValueError("el PDF del descarte no está en descartadas/")
    if os.path.exists(destino):
        raise ValueError("ya existe un PDF con ese nombre en pendientes_revision/")

    columnas = ", ".join(_EST_COLUMNAS_COMPARTIDAS)
    marcadores = ",".join("?" for _ in _EST_COLUMNAS_COMPARTIDAS)
    conn.execute(
        f"INSERT INTO pendientes_revision ({columnas}, motivo, fecha_pendiente) "
        f"VALUES ({marcadores},?,?)",
        tuple(fila.get(col) for col in _EST_COLUMNAS_COMPARTIDAS)
        + (fila.get("motivo_bloqueo"), fila.get("fecha_pendiente") or ahora),
    )
    conn.execute("DELETE FROM pendiente_descartado WHERE archivo_pdf = ?", (archivo_pdf,))
    return {"archivo_pdf": archivo_pdf, "id_documento": fila.get("id_documento")}


def _confirmar_registros(conn, registros: list) -> list:
    """Inserta los registros validos en facturas y mueve sus PDFs a procesadas.
    Cada registro corre dentro de su propio SAVEPOINT — si cualquier paso
    falla (INSERT, escritura del PDF, o resolver un pendiente asociado), se
    hace ROLLBACK TO SAVEPOINT (primitiva real de SQLite, no un DELETE a
    mano) y se borra el PDF si alcanzo a escribirse parcialmente, asi nunca
    queda una fila en facturas sin su documento de respaldo, ni un archivo
    huerfano sin fila que lo referencie — incluso si el propio intento de
    deshacer algo fallara a mitad de camino.

    Devuelve la lista de registros REALMENTE confirmados (no la lista
    original completa) — los 3 llamadores pasan este resultado, no
    `registros`, a actualizar_excel_main(), para que el Excel maestro nunca
    reciba un duplicado ni un registro cuya confirmacion en SQLite fallo."""
    confirmados = []
    ahora = datetime.now().isoformat()
    for r in registros:
        id_documento = r.get("id_documento")
        dest = None
        conn.execute("SAVEPOINT confirmar_registro")
        try:
            # Issue #19: el INSERT vive en _est_insertar_factura() (primitiva
            # compartida con scripts/importar_puente.py); este SAVEPOINT lo
            # envuelve igual que antes. fecha_importacion se fuerza al `ahora`
            # del lote, como siempre.
            insertadas = _est_insertar_factura(conn, {**r, "fecha_importacion": ahora})
            if insertadas == 0:
                conn.execute("RELEASE SAVEPOINT confirmar_registro")
                continue  # duplicado (mismo id_documento ya en facturas) — no tocar el PDF

            if r.get("_pdf_bytes") and r.get("archivo_pdf"):
                dest = os.path.join(EST_PROCESADAS, r["archivo_pdf"])
                with open(dest, "wb") as f:
                    f.write(r["_pdf_bytes"])

            # Resolver el pendiente (si existia una version anterior sin
            # sello/firma con este mismo id_documento) SOLO ahora que la
            # version corregida quedo realmente confirmada — antes se
            # resolvia en cuanto Vision aprobaba el documento, no cuando el
            # usuario de verdad lo incorporaba. Si el usuario apretaba
            # "Cancelar" en vez de "Incorporar", el pendiente original ya se
            # habia borrado sin que la version corregida quedara guardada en
            # ningun lado — perdida silenciosa real.
            _est_resolver_pendiente(conn, id_documento)

            conn.execute("RELEASE SAVEPOINT confirmar_registro")
            confirmados.append(r)
        except Exception:
            print(f"Error confirmando registro {id_documento}:")
            traceback.print_exc()
            # ROLLBACK TO SAVEPOINT (deshace los cambios de datos) y RELEASE
            # SAVEPOINT (libera el marcador del savepoint) son dos pasos
            # separados a proposito — un ROLLBACK TO exitoso ya deja la fila
            # revertida en la conexion, sin importar si el RELEASE posterior
            # falla (Codex confirmo esto contra SQLite real: RELEASE solo es
            # bookkeeping del stack de savepoints, no vuelve a aplicar los
            # cambios). Tratarlos como un solo paso hacia atras dejaba el PDF
            # huerfano sin necesidad cuando solo el RELEASE fallaba.
            rollback_ok = False
            try:
                conn.execute("ROLLBACK TO SAVEPOINT confirmar_registro")
                rollback_ok = True
            except Exception:
                print(f"No se pudo revertir el savepoint de {id_documento} — la fila podria quedar "
                      f"en facturas de todas formas, revisar a mano")
                traceback.print_exc()
            try:
                conn.execute("RELEASE SAVEPOINT confirmar_registro")
            except Exception:
                print(f"No se pudo liberar el savepoint de {id_documento} "
                      f"(datos ya revertidos si rollback_ok=True: {rollback_ok})")
                traceback.print_exc()
            # Solo borrar el PDF si el ROLLBACK TO SI funciono — si el propio
            # rollback fallo, la fila podria sobrevivir y comitearse igual
            # cuando el llamador haga conn.commit() mas adelante (SQLite no
            # exige savepoints cerrados para commitear). Borrar el PDF en ese
            # caso dejaria exactamente el problema que este SAVEPOINT existe
            # para evitar: una fila en facturas sin su documento de respaldo.
            if rollback_ok and dest and os.path.exists(dest):
                try:
                    os.remove(dest)
                except OSError:
                    pass
    return confirmados


def _paginas_pdf(pdf_bytes: bytes) -> int | None:
    """Cuantas paginas tiene el PDF, o None si fitz no lo puede abrir (ese
    caso lo sigue resolviendo Vision, como antes)."""
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            return doc.page_count
    except Exception:
        return None


async def _procesar_pdfs(zf, pdfs, conn, model: str, lookup: dict):
    """Procesa una lista de PDFs (de un ZIP abierto) con el modelo indicado.
    Devuelve (importadas, errores_vision, pendientes, duplicadas, corregidas).

    Issue #15: `lookup` (de cargar_lookup_excel) es obligatorio — un PDF sin
    fila resoluble en el Excel se manda a pendientes_revision ANTES de llamar
    a Vision (ahorra el costo de la llamada), con lo poco que se puede
    derivar del nombre del archivo. Orden de evaluacion fijo, el primero que
    aplica gana: 1) nombre invalido, 2) duplicado, 3) sin fila en el Excel /
    4) conflicto del Excel, 5) tope de tamano descomprimido, 6) recien aca se
    llama a Vision, 7) fase no reconocida, 8) sello/firma."""
    importadas     = []
    errores_vision = []
    pendientes     = []
    duplicadas     = []
    corregidas     = []
    total_descomprimido = 0

    for nombre_completo in pdfs:
        nombre_base = os.path.basename(nombre_completo)
        if not nombre_base or nombre_base.startswith("."):
            continue

        info = parsear_nombre_pdf(nombre_base)
        if not info:
            errores_vision.append({"nombre": nombre_base, "motivo": "nombre de archivo inválido", "_pdf_bytes": None})
            continue

        if conn.execute("SELECT 1 FROM facturas WHERE id_documento = ?", (info["id_documento"],)).fetchone():
            duplicadas.append(nombre_base)
            continue

        # Chequeo de fila en el Excel — antes de leer el PDF/llamar a Vision,
        # usa solo el nombre de archivo + id_documento (ya derivados del
        # nombre). Si no hay fila resoluble, el documento se manda a
        # pendientes_revision mas abajo (necesita los bytes del PDF para
        # guardar el archivo fisico, pero nunca se gasta una llamada a
        # Vision en el).
        _fila_excel, motivo_excel = _resolver_fila_excel(lookup, nombre_base, info["id_documento"])

        # Tamano DESCOMPRIMIDO de este archivo puntual, leido en streaming con
        # tope real — NUNCA confiar en zf.getinfo().file_size: es metadata del
        # ZIP que arma quien lo sube, no se verifica contra el contenido real
        # hasta que termina de descomprimir (confirmado con un ZIP crafteado a
        # mano: declara un tamano chico en el central directory pero al leerlo
        # igual descomprime el contenido real completo antes de fallar el
        # CRC-32 — el gasto de memoria ya paso quieras o no).
        buf = bytearray()
        excede = False
        with zf.open(nombre_completo) as entrada:
            while True:
                chunk = entrada.read(1024 * 1024)
                if not chunk:
                    break
                buf.extend(chunk)
                if len(buf) > EST_PDF_MAX_BYTES_DESCOMPRIMIDO:
                    excede = True
                    break
        if excede:
            errores_vision.append({
                "nombre": nombre_base,
                "motivo": f"el PDF descomprimido excede {EST_PDF_MAX_BYTES_DESCOMPRIMIDO // (1024 * 1024)}MB",
                "_pdf_bytes": None,
            })
            continue

        # Tope agregado: cada PDF que pasa el chequeo individual queda
        # retenido en memoria (importadas/errores_vision cargan _pdf_bytes
        # para el reintento con Opus o la importacion real) — sin este
        # chequeo, un lote de PDFs grandes-pero-validos-individualmente
        # segui pasando el limite por-PDF hasta agotar la memoria del
        # proceso completo.
        total_descomprimido += len(buf)
        if total_descomprimido > EST_ZIP_TOTAL_DESCOMPRIMIDO_MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"El lote descomprimido excede el tope agregado de "
                       f"{EST_ZIP_TOTAL_DESCOMPRIMIDO_MAX_BYTES // (1024 * 1024)}MB "
                       f"(detectado en '{nombre_base}')"
            )

        pdf_bytes_data = bytes(buf)

        if motivo_excel:
            # Issue #15: sin fila resoluble en el Excel — nunca se llama a
            # Vision para este documento (ahorra el costo de la llamada). Se
            # guarda en pendientes_revision con lo poco que se puede derivar
            # del nombre del archivo, el resto queda en NULL.
            datos_sin_fila = {
                "id_documento": info["id_documento"], "fecha": info["fecha"],
                "planta": info["planta"], "archivo_pdf": nombre_base,
            }
            _guardar_pendiente_revision(conn, datos_sin_fila, motivo_excel, pdf_bytes_data)
            pendientes.append({"nombre": nombre_base, "motivo": motivo_excel})
            continue

        paginas = _paginas_pdf(pdf_bytes_data)
        if paginas is not None and paginas > EST_PDF_MAX_PAGINAS:
            # Antes de Vision: un PDF largo no es un conduce y cobra por pagina.
            errores_vision.append({
                "nombre": nombre_base,
                "motivo": f"el PDF tiene {paginas} páginas y un conduce tiene 1 (tope {EST_PDF_MAX_PAGINAS})",
                "_pdf_bytes": None,
            })
            continue

        try:
            datos = await asyncio.to_thread(_procesar_pdf_sync, pdf_bytes_data, model)
        except Exception as e:
            errores_vision.append({
                "nombre": nombre_base, "motivo": f"error al leer el documento ({e})",
                "_pdf_bytes": pdf_bytes_data, "_info": info,
            })
            continue

        datos = _enriquecer_y_matchear(conn, datos, info, nombre_base, lookup)
        datos["_pdf_bytes"] = pdf_bytes_data

        if datos.get("_correccion_excel"):
            corregidas.append({
                "nombre": nombre_base, "campo": "descripcion",
                "vision": datos["_correccion_excel"]["vision"],
                "excel": datos["_correccion_excel"]["excel"],
            })
        if datos.get("_correccion_excel_cantidad"):
            corregidas.append({"nombre": nombre_base, **datos["_correccion_excel_cantidad"]})

        motivo = _motivo_sello_firma(datos)
        if not motivo and model != VISION_MODEL_PRO:
            # Doble-chequeo: Haiku puede dar falso positivo en sello/firma
            # (confirmado con pruebas reales). Solo se re-verifica cuando
            # Haiku ya dijo que estaba completo — barato y evita colar
            # documentos sin sello/firma como validos.
            try:
                pdf_derecho = _rotar_pdf(pdf_bytes_data) if datos.get("_rotado") else pdf_bytes_data
                verif = await asyncio.to_thread(_verificar_sello_firma_opus, pdf_derecho)
                datos["tiene_sello"] = verif.get("tiene_sello", datos.get("tiene_sello"))
                datos["tiene_firma"] = verif.get("tiene_firma", datos.get("tiene_firma"))
                motivo = _motivo_sello_firma(datos)
            except Exception as e:
                # Si falla el doble-chequeo no se confia en Haiku (ya dio
                # falsos positivos de sello/firma documentados en produccion)
                # — el documento queda pendiente de revision manual.
                print(f"Doble-chequeo de sello/firma fallo para {nombre_base}: {e}")
                motivo = "verificación de sello/firma falló"

        if motivo:
            _guardar_pendiente_revision(conn, datos, motivo, pdf_bytes_data)
            pendientes.append({"nombre": nombre_base, "motivo": motivo})
            continue

        datos["sin_firma"] = not datos.get("tiene_firma")
        importadas.append(datos)

    return importadas, errores_vision, pendientes, duplicadas, corregidas

async def _reprocesar_en_background(session_id: str):
    """Corre en segundo plano — actualiza sesion['reprocess_progress'] despues
    de cada PDF para que el frontend pueda mostrar una barra en vivo.

    Issue #15: usa el lookup del Excel guardado en la sesion (`sesion["lookup"]`,
    poblado por /procesar-zip) — todo PDF que llega aca ya paso el chequeo de
    fila en el Excel en la primera pasada (si no hubiera tenido fila, nunca
    habria llegado a errores_vision), asi que _enriquecer_y_matchear siempre
    deberia resolver una fila aca. corregidas_lista sale por
    /reprocesar-progreso — este endpoint responde antes de que el trabajo
    exista, no puede devolverla en su propia respuesta."""
    sesion = est_sessions[session_id]
    prog = sesion["reprocess_progress"]
    lookup = sesion["lookup"]

    pendientes_reintento = [e for e in sesion["errores_vision"] if e.get("_pdf_bytes")]
    siguen_con_error = [e for e in sesion["errores_vision"] if not e.get("_pdf_bytes")]
    nuevos_importados = []
    nuevos_pendientes  = []
    corregidas         = []

    conn = sqlite3.connect(EST_DB_PATH)

    for i, item in enumerate(pendientes_reintento, 1):
        prog["actual"] = i
        nombre_base = item["nombre"]
        info        = item["_info"]
        try:
            datos = await asyncio.to_thread(_procesar_pdf_sync, item["_pdf_bytes"], VISION_MODEL_PRO)
        except Exception as e:
            siguen_con_error.append({
                "nombre": nombre_base, "motivo": f"error al leer el documento ({e})",
                "_pdf_bytes": item["_pdf_bytes"], "_info": info,
            })
            continue

        datos = _enriquecer_y_matchear(conn, datos, info, nombre_base, lookup)
        datos["_pdf_bytes"] = item["_pdf_bytes"]

        if datos.get("_correccion_excel"):
            corregidas.append({
                "nombre": nombre_base, "campo": "descripcion",
                "vision": datos["_correccion_excel"]["vision"],
                "excel": datos["_correccion_excel"]["excel"],
            })
        if datos.get("_correccion_excel_cantidad"):
            corregidas.append({"nombre": nombre_base, **datos["_correccion_excel_cantidad"]})

        motivo = _motivo_sello_firma(datos)
        if motivo:
            _guardar_pendiente_revision(conn, datos, motivo, item["_pdf_bytes"])
            nuevos_pendientes.append({"nombre": nombre_base, "motivo": motivo})
            continue

        datos["sin_firma"] = not datos.get("tiene_firma")
        nuevos_importados.append(datos)

    confirmados = _confirmar_registros(conn, nuevos_importados)
    conn.commit()
    conn.close()
    if confirmados:
        actualizar_excel_main(confirmados)

    sesion["errores_vision"] = siguen_con_error
    sesion["incorporados_total"] = sesion.get("incorporados_total", 0) + len(confirmados)
    prog["pendientes_nuevos"] = nuevos_pendientes
    # Split de presentacion (mismo criterio que /procesar-zip) — documentos
    # reprocesados con Opus que quedaron con sello pero sin firma.
    prog["importadas_sin_firma_lista"] = [r["archivo_pdf"] for r in confirmados if r.get("sin_firma")]
    prog["corregidas_lista"] = corregidas
    prog["activo"] = False

# ─────────────────────────────────────────────
# ESTIMACIONES — generador (REO-01 / RGO-XX)
# ─────────────────────────────────────────────

EST_CLIENTE = "MACAO ALTO RESORT S.R.L"
EST_CONTRATISTA = {"DOMICEM": "DOMICEM S.A", "VMO": "VMO CONCRETOS S.A"}
EST_OBRA_TEXTO = {
    ("DOMICEM", "CAVERNAS"): "SUMINISTRO DE HORMIGON PARA CIUDAD PALACE - CAVERNAS/EXTERIORES",
    ("DOMICEM", "VIVIENDAS"): "SUMINISTRO DE HORMIGON PARA CIUDAD PALACE - VIVIENDAS",
    ("DOMICEM", "MACAO 2"): "SUMINISTRO DE HORMIGON PARA CIMENTACION Y ESTRUCTURA MACAO II",
    ("DOMICEM", "PATIO DE MANIOBRAS-TRB"): "SUMINISTRO DE HORMIGON PARA PATIO DE MANIOBRAS",
    ("VMO", "CANCHAS"): "SUMINISTRO DE HORMIGON PARA CANCHAS",
    ("VMO", "CEDIS"): "SUMINISTRO DE HORMIGON PARA CEDIS",
    ("VMO", "EXTERIORES"): "SUMINISTRO DE HORMIGON PARA AREA EXTERIORES",
    ("VMO", "PATIO DE MANIOBRAS-TRA"): "SUMINISTRO DE HORMIGON PARA PATIO DE MANIOBRAS",
    ("VMO", "PODIUM-1-2-3"): "SUMINISTRO DE HORMIGON PARA PODIUM 1,2,3",
}
EST_OC_CONTRATO = {
    ("DOMICEM", "CAVERNAS"): "4800029676",
    ("DOMICEM", "MACAO 2"): "4800029677",
    ("DOMICEM", "PATIO DE MANIOBRAS-TRB"): "4800032854",
    ("DOMICEM", "VIVIENDAS"): "PPACT",
    ("VMO", "CANCHAS"): "4800037426",
    ("VMO", "CEDIS"): "4800036588",
    ("VMO", "PATIO DE MANIOBRAS-TRA"): "4800025583",
    ("VMO", "PODIUM-1-2-3"): "PPACT",
    ("VMO", "EXTERIORES"): "PPACT",
}

def _est_oc_contrato(empresa: str, fase: str) -> str:
    valor = EST_OC_CONTRATO.get((empresa, fase))
    if valor is None:
        raise HTTPException(status_code=500, detail={
            "error": "oc_contrato_no_definido",
            "detalle": f"no hay OC/Contrato registrado para {empresa}/{fase}",
        })
    return valor


def _est_oc_contrato_por_serie(empresa: str, fase: str, serie: str) -> str:
    """Issue #12 — contratos paralelos. Para serie='principal' devuelve el
    valor existente de EST_OC_CONTRATO tal cual (sin cambios respecto al
    issue #9). Para serie='ppact' devuelve siempre el string literal
    "PPACT" — no necesita tabla nueva, el texto nunca varia por fase (ya
    confirmado por las 3 fases 100% PPACT que hoy usan exactamente ese
    valor en EST_OC_CONTRATO)."""
    if serie == "ppact":
        return "PPACT"
    return _est_oc_contrato(empresa, fase)


def _est_fecha_excel(valor):
    """Convierte YYYY-MM-DD a fecha real de Excel sin bloquear el documento.

    Los valores vacios o con formatos inesperados se conservan tal cual para
    que una fecha imperfecta nunca haga fallar la generacion completa.
    """
    if not isinstance(valor, str):
        return valor
    try:
        return date.fromisoformat(valor)
    except ValueError:
        return valor


def _est_etiquetas_rango(numero_estimacion: str) -> tuple[str, str, str]:
    match = re.fullmatch(r"N(\d+)", numero_estimacion or "")
    if not match:
        return "", "", ""

    numero = int(match.group(1))
    # "N0"/"N00" no es una estimacion real — sin esto devolvia el sinsentido
    # ("", "N00", "N01-N00") y lo escribia en un documento oficial.
    if numero < 1:
        return "", "", ""

    ancho = max(2, len(match.group(1)))
    actual = f"N{numero:0{ancho}d}"
    # El numero ANTERIOR se rellena a su propio ancho natural (minimo 2), no al
    # del actual: la estimacion anterior a N100 es N99, no N099.
    ancho_anterior = max(2, len(str(numero - 1)))
    # N01 es la primera estimacion: no existe un rango anterior que rotular.
    anterior = "" if numero == 1 else f"N01-N{numero - 1:0{ancho_anterior}d}"
    return anterior, actual, f"N01-{actual}"


def _est_nombre_hoja(clave, nombres_usados: set[str], prefijo: str) -> str:
    """Nombre de hoja para una clave de producto — issue #27, decision D3.

    Nacio como _est_nombre_rgo con el prefijo "CD-COAF-RGO-" cableado; ahora
    las tres familias (RGO, RCO, RFO) comparten este unico lugar donde vive
    la logica de nombres: relleno de claves numericas a 2 digitos, saneo de
    los caracteres que Excel prohibe en nombres de hoja, truncado al limite
    fisico de 31 caracteres y resolucion de colisiones con sufijo
    consecutivo. El comportamiento para las RGO esta capturado caso por caso
    en tests/test_nombre_hoja.py (escritos en verde ANTES del refactor)."""
    clave_texto = str(clave).strip()
    identificador = f"{int(clave_texto):02d}" if clave_texto.isdigit() else clave_texto
    identificador = re.sub(r"[\\/*?:\[\]]", "-", identificador) or "SIN-CLAVE"
    base = (prefijo + identificador)[:31]
    nombre = base
    consecutivo = 2
    while nombre in nombres_usados:
        sufijo = f"-{consecutivo}"
        nombre = base[:31 - len(sufijo)] + sufijo
        consecutivo += 1
    nombres_usados.add(nombre)
    return nombre

EST_REO_FIRST_ROW = 17
EST_RGO_FIRST_ROW = 18
EST_RGO_LAST_ROW = 57          # capacidad nativa de CD-COAF-RGO-PLANTILLA en disco
EST_RGO_TOTAL_ROW = 58         # fila de TOTAL nativa (antes de redimensionar)
EST_RGO_SIG_ROWS = (60, 61)    # filas de firma nativas (fila 59 es el espacio en blanco)
EST_RGO_CAPACIDAD_NATIVA = EST_RGO_LAST_ROW - EST_RGO_FIRST_ROW + 1  # 40 — desde issue #18 tambien es el tamano de bloque por pagina
EST_RGO_SANITY_MAX = 5000      # tope de cordura, no de diseno — protege contra un rango de fechas mal elegido

# Issue #18 — paginacion en bloques de 40 folios por pagina (exigencia del
# cliente, 2026-08-27). El encabezado repetible son las filas 14-17 de la
# plantilla (etiquetas PARTIDA/CLAVE/CONCEPTO/U.M., fila de valores, blanco,
# titulos de columna) y el pie son las 4 filas 58-61 (TOTAL, blanco, firma1,
# firma2). El periodo de una pagina se DERIVA de la plantilla, no es un
# numero magico: 40 datos + 4 de pie + 4 de encabezado de la pagina
# siguiente = 48 (bloque 1 en 18-57, pie 58-61, encabezado 62-65, bloque 2
# arranca en 66; 66 - 18 = 48 — coincide con la primera pagina de los
# documentos reales del cliente).
EST_RGO_ENC_ROWS = (14, 15, 16, 17)
EST_RGO_PIE_FILAS = 4
EST_RGO_PERIODO = EST_RGO_CAPACIDAD_NATIVA + EST_RGO_PIE_FILAS + len(EST_RGO_ENC_ROWS)  # 48

# Issue #33 — bloque de firma de la hoja RGO.
#
# La plantilla trae el bloque cableado a la fila 37/38 de REO-01
# (D60 ='CD-COAF-REO-01'!E37, D61 =...!$E$38, H60 formula matricial
# =...!K37:N37, H61 =...!$K$38), pero el bloque de firma de REO-01 NO esta
# en 37/38 en 7 de las 9 fases: cada plantilla tiene distinta cantidad de
# renglones de producto, asi que la firma quedo a distinta altura (TRB y
# TRA en 29/30, CANCHAS y PODIUM en 28/29, VIVIENDAS en 34/35, CAVERNAS en
# 38/39, EXTERIORES en 40/41). Medido celda por celda sobre las 10
# plantillas y confirmado end-to-end recalculando con LibreOffice: en 6 de
# esas 7 fases la firma sale con un "0" donde va el nombre y con " $   - "
# donde va el cargo (las celdas de cargo llevan formato contable, asi que
# una referencia a celda vacia no sale en blanco sino como monto cero), y
# en la septima (CAVERNAS) sale cruzada — el nombre cae en el renglon del
# cargo. Afecta por igual a las dos firmas: la del analista (columna D) y
# la de gerencia de obra (columna H, formula matricial).
#
# La fila se DETECTA leyendo la plantilla, no se cablea en un diccionario
# fase->fila: un diccionario se desincroniza en silencio la proxima vez que
# alguien reconstruya una plantilla, que es exactamente como nacio este bug.
# El ancla es el rotulo "CONTRATISTA" de la columna B, unico en la hoja en
# las 10 plantillas (el "CONTRATISTA:" del encabezado esta en A9 — otra
# columna y con dos puntos).
EST_REO_FIRMA_ANCLA = "CONTRATISTA"   # rotulo en la columna B de la fila del cargo
EST_REO_FIRMA_ANCLA_COL = 2           # columna B
# columnas del bloque de firma: (columna en REO-01, columna en la RGO) para
# el analista de estimaciones (E -> D) y para gerencia de obra (K -> H)
EST_FIRMA_COLS = ((5, 4), (11, 8))
# la formula matricial nativa de la RGO ocupa H60:K60 (4 columnas); al
# reemplazarla por un valor escalar hay que limpiar las 3 celdas sobrantes,
# que se quedan con el 0 cacheado del rango K37:N37
EST_RGO_FIRMA_ARRAY_SPAN = 4

# Issue #35 — celda del contratista de la RGO: A60 (fusionada A60:B60), justo
# encima del rotulo fijo "CONTRATISTA" de A61, que no se toca. A diferencia de
# las otras dos firmas, el contratista tiene solo fila de nombre, no de cargo.
#
# Las 10 plantillas la traen con el literal cableado "VMO CONCRETOS", tambien
# las 4 de DOMICEM, asi que toda estimacion de DOMICEM salia nombrando a la
# empresa equivocada como contratista en cada una de sus hojas RGO, mientras el
# resumen de esa misma estimacion decia DOMICEM S.A. Verificado contra los
# documentos reales del cliente: ninguna de sus estimaciones DOMICEM dice
# "VMO CONCRETOS" ahi, dicen "DOMICEM S.A" — era error nuestro, no una
# convencion suya.
#
# El texto sale de EST_CONTRATISTA y NO de la columna B del bloque de firma de
# REO-01, por dos razones: en 8 de las 10 plantillas esa celda es la formula
# "=B9" (que la guarda de abajo rechaza por empezar con "="), y EST_CONTRATISTA
# es la misma fuente que el generador ya escribe en B9, asi que el contratista
# de la RGO y el del resumen no pueden divergir nunca.
EST_RGO_FIRMA_COL_CONTRATISTA = 1   # columna A

# ═══ Issue #27 — hojas RCO (croquis de ubicacion) y RFO (reporte fotografico) ═══
#
# Una RCO y una RFO por clave con entregas del periodo, en paralelo a las RGO
# (el "6 y 6" del issue original era falso — medido: entre 2 y 13 RCO por
# documento). No tienen tabla ni formulas de calculo: cuerpo de marco
# fusionado + imagenes flotantes, largo fijo, sin paginacion.

EST_CROQUIS_DIR = os.path.join(BASE_DIR, "estimaciones", "data", "croquis")
EST_LOGOS_DIR = os.path.join(EST_CROQUIS_DIR, "logos")

EST_RCO_PREFIJO = "CD-COAF-RCO-"
EST_RFO_PREFIJO = "CD-COAF-RFO-"
EST_RCO_PLANTILLA = "CD-COAF-RCO-PLANTILLA"
EST_RFO_PLANTILLA = "CD-COAF-RFO-PLANTILLA"

# Geometria — medida sobre las 156 hojas RCO/RFO de los 15 documentos reales
# del cliente (print_area, 2026-09-01): domina A1:J46 (RCO 59/78, RFO 33/78);
# MACAO 2 es perfectamente uniforme con RCO A1:J46 y RFO A1:J52 en sus 20+20
# hojas. La decision 4 del spec conserva la RFO de MACAO 2 a 52 filas por
# continuidad visual con el historico entregado; el resto de variantes
# (41/45/48/54/57/58 y las que llegan a la columna K) son deriva del armado a
# mano del cliente y NO se replican.
EST_RCO_RFO_ULTIMA_FILA = 46
EST_RFO_ULTIMA_FILA_MACAO2 = 52
EST_FASE_MACAO2 = ("DOMICEM", "MACAO 2")

# Escala de impresion — OJO: el spec (criterio 6) decia "landscape, scale 76"
# parejo, pero el cliente usa 70 en TODAS sus 25 hojas RFO de A1:J52 (medido
# 2026-09-01, hoja por hoja). A escala 76 las 52 filas no caben en una pagina
# y el PDF saldria partido, que es exactamente lo que el criterio 8 prohibe.
EST_RCO_RFO_ESCALA = 76
EST_RFO_ESCALA_MACAO2 = 70

EST_RCO_RFO_PRIMERA_FILA_MARCO = 18
# pie de la hoja, contado desde la ultima fila: {ultima-3} cierra el marco,
# {ultima-2} queda en blanco, {ultima-1} lleva los nombres de firma y
# {ultima} los cargos (con el rotulo fijo CONTRATISTA en B)
EST_RCO_RFO_FILAS_PIE = 3

# Titulos de la celda A5 — EXACTOS a los documentos del cliente, con las
# letras espaciadas una por una (asi los escribe el en las 156 hojas; un test
# que afirme el string plano "REPORTE FOTOGRAFICO" falla siempre). El de la
# RCO trae ademas un doble espacio irregular en "D E    U B I C A C I O N"
# (4 espacios tras la E) que tambien se conserva tal cual: es el titulo con
# el que salieron sus 78 RCO. La RFO va con el titulo CORRECTO de su tipo
# (decision 5): 6 de los 15 documentos del cliente la titulan "CROQUIS DE
# UBICACION" por descuido y eso NO se replica.
EST_RCO_TITULO_A5 = (
    "R E S U M E N   D E   G E N E R A D O R E S "
    "( C R O Q U I S   D E    U B I C A C I Ó N )"
)
EST_RFO_TITULO_A5 = (
    "R E S U M E N   D E   G E N E R A D O R E S "
    "( R E P O R T E   F O T O G R Á F I C O )"
)
# Rotulos de A17 (el espacio final de la RCO tambien es del cliente)
EST_RCO_ROTULO_A17 = "CROQUIS DE UBICACIÓN "
EST_RFO_ROTULO_A17 = "REPORTE FOTOGRÁFICO"

# Logos de las hojas DOMICEM (decision D4): el banner de cabecera y el sello
# se re-estampan al generar porque copy_worksheet los perderia igual que el
# croquis. Las hojas VMO no llevan logo-imagen (los documentos VMO del
# cliente que si traen alguno — TRA, y 2 hojas de CEDIS PPACT — son deriva
# del armado a mano y no se replican; misma linea del #18). Anclas medidas
# en EST_DOMICEM_MACAO_II_N33 :: CD-COAF-RCO-02; el ancho de display
# reproduce el del cliente (~375 px la cabecera) pero el alto se deriva de la
# proporcion nativa de cada imagen, para no estamparlas deformadas.
# (archivo en EST_LOGOS_DIR, (col, fila, colOff_emu, rowOff_emu), ancho_px)
EST_LOGOS_DOMICEM = (
    ("DOMICEM_cabecera.png", (0, 1, 76200, 285750), 375),
    ("DOMICEM_sello.png", (9, 0, 238125, 114300), 61),
)

# 2026-09-25 (pedido de Axel) — la hoja RGO lleva el logo en la esquina
# derecha del encabezado EN CADA BLOQUE de 40 folios, no solo en la primera
# pagina. La geometria se CALCULA de los anchos de columna de la hoja
# (medido con sondas sobre el PDF real: cada caracter de ancho de columna
# son 7.41 px, exacto en F, G y H de la plantilla MACAO 2), y la imagen se
# ancla en la columna que contiene la X objetivo con el offset ADENTRO de
# esa columna: LibreOffice recorta un offset de ancla mas grande que su
# celda (misma trampa que el croquis, HANDOFF), asi que un offset absoluto
# desde la columna A no sirve, y el ancla absoluta en EMU tampoco (ignora
# los saltos de pagina explicitos: una sonda partio el logo entre dos
# paginas). En la pagina 1 el logo va en la zona del titulo, terminando
# ANTES de la banda azul RESUMEN DE GENERADORES (el primer intento, de 150
# px de alto, la pisaba); en los bloques siguientes (que arrancan directo
# con la banda PARTIDA/CLAVE) va una version compacta.
EST_RGO_PX_POR_CHAR = 7.41
# 10 px: 2 de respiro + 8 que la sonda v3 midio de deriva acumulada del
# factor px-por-char en el ancho completo de la tabla
EST_RGO_LOGO_MARGEN_PX = 10
EST_RGO_LOGO_RESPIRO_PX = 12       # aire entre el logo y la banda azul
EST_RGO_LOGO_ANCHO_MAX_PX = 250
EST_RGO_LOGO_ALTO_BLOQUE_PX = 42   # compacto: cubre solo las celdas U.M./m3
# empresa -> archivo en EST_LOGOS_DIR. Son versiones RECORTADAS a la marca
# sola (generadas el 2026-09-25 con PIL desde DOMICEM_sello.png 200x200,
# cuya marca real ocupa una franja de 200x82 — mostrada entera en un
# cuadrado quedaba chica y serruchada): con el recorte, la marca entra
# entre el margen superior y la banda azul de la RGO, que solo deja ~37 pt
# libres (el logo del CEO mide 65 pt de alto y por eso no cabe tal cual).
EST_LOGO_RGO_POR_EMPRESA = {
    "DOMICEM": "DOMICEM_marca.png",
    "VMO": "VMO_marca.png",
}

# 2026-09-25 — logo VMO CONCRETOS: extraido del documento del cliente
# EST_VMO_PPACT_AREA_EXTERIORES_N17 (CEO-01, col 17) a
# croquis/logos/VMO_logo.png (229x112 nativo). El cliente lo estampa en
# TODAS sus hojas y estas anclas son las suyas, medidas hoja por hoja en ese
# mismo documento (RFO usa el ancla de RCO: el cliente alterna col 9/10 y
# nuestra area de impresion A:J termina en col 9).
EST_LOGOS_VMO_R = (("VMO_logo.png", (9, 0, 323850, 95250), 229),)
EST_LOGOS_VMO_CEO = (("VMO_logo.png", (17, 0, 246062, 39687), 229),)
EST_LOGOS_VMO_REO = (("VMO_logo.png", (16, 0, 416718, 130970), 229),)

# juego de logos por empresa segun la familia de hoja. CEO/REO de DOMICEM no
# aparecen: sus logos viajan nativos en la plantilla (no se clonan).
EST_LOGOS_R_POR_EMPRESA = {"DOMICEM": EST_LOGOS_DOMICEM, "VMO": EST_LOGOS_VMO_R}
EST_LOGOS_CEO_POR_EMPRESA = {"VMO": EST_LOGOS_VMO_CEO}
EST_LOGOS_REO_POR_EMPRESA = {"VMO": EST_LOGOS_VMO_REO}

EST_EMU_POR_PX = 9525
# margen de respiro del croquis dentro del marco (97% del hueco disponible)
EST_CROQUIS_MARGEN = 0.97


def _est_geometria_rco_rfo(familia: str, empresa: str, fase: str) -> tuple[int, int]:
    """(ultima_fila, escala_de_impresion) de una hoja RCO/RFO segun la
    decision 4: RCO A1:J46 siempre (MACAO 2 incluida); RFO A1:J46 salvo
    MACAO 2, que va A1:J52 (y a escala 70, como sus 25 hojas reales)."""
    if familia == "RFO" and (empresa, fase) == EST_FASE_MACAO2:
        return EST_RFO_ULTIMA_FILA_MACAO2, EST_RFO_ESCALA_MACAO2
    return EST_RCO_RFO_ULTIMA_FILA, EST_RCO_RFO_ESCALA


def _est_id_clave(clave) -> str:
    """Identificador de una clave para nombres de archivo de croquis: misma
    normalizacion que usa _est_nombre_hoja para los nombres de hoja (2
    digitos si es numerica), para que CD-COAF-RCO-07 busque el archivo
    *_07.png y no *_7.png."""
    clave_texto = str(clave).strip()
    if clave_texto.isdigit():
        return f"{int(clave_texto):02d}"
    return re.sub(r"[^A-Za-z0-9]+", "-", clave_texto) or "SIN-CLAVE"


def _est_buscar_croquis(empresa: str, fase: str, clave) -> Optional[str]:
    """Ruta del croquis archivado para esta clave, o None si no hay.

    Patron: {EMPRESA}_{FASE}_{clave}.png pisa a {EMPRESA}_{FASE}.png
    (necesario para EXTERIORES, que usa 6 croquis distintos entre sus RCO).
    El slug es el mismo _est_slug del resto del modulo — con PODIUM-1-2-3 o
    PATIO DE MANIOBRAS-TRB un nombre sin normalizar rompe por los espacios,
    comas y guiones. Se aceptan .png y .jpg: el sembrado guarda JPEG cuando
    el PNG recomprimido sigue pasando el tope de peso (D2)."""
    base = f"{_est_slug(empresa)}_{_est_slug(fase)}"
    candidatos = [f"{base}_{_est_id_clave(clave)}", base]
    for nombre in candidatos:
        for ext in (".png", ".jpg", ".jpeg"):
            ruta = os.path.join(EST_CROQUIS_DIR, nombre + ext)
            if os.path.exists(ruta):
                return ruta
    return None


def _est_col_px(ws, col_idx: int) -> int:
    """Ancho visible de una columna en pixeles (aprox. estandar de Excel:
    ancho_en_caracteres * 7 + 5). Suficiente para centrar una imagen."""
    from openpyxl.utils import get_column_letter
    dim = ws.column_dimensions.get(get_column_letter(col_idx))
    ancho = dim.width if dim is not None and dim.width is not None else None
    if ancho is None:
        ancho = ws.sheet_format.defaultColWidth or 8.43
    return int(round(ancho * 7 + 5))


def _est_fila_px(ws, fila: int) -> int:
    """Alto visible de una fila en pixeles (puntos * 96/72)."""
    dim = ws.row_dimensions.get(fila)
    alto = dim.height if dim is not None and dim.height is not None else None
    if alto is None:
        alto = ws.sheet_format.defaultRowHeight or 15.0
    return int(round(alto * 4.0 / 3.0))


def _est_estampar_imagen(ws, ruta, col, fila, col_off, row_off, cx, cy) -> None:
    """Inserta una imagen con ancla de una celda y TAMANO EXPLICITO en EMU
    (OneCellAnchor + ext): la imagen queda anclada a la celda pero con su
    caja definida por nosotros, que es lo que permite conservar la
    proporcion — anclar sin definir escala puede cumplir un test y salir
    deformado igual."""
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, OneCellAnchor
    from openpyxl.drawing.xdr import XDRPositiveSize2D

    img = XLImage(ruta)
    img.anchor = OneCellAnchor(
        _from=AnchorMarker(col=col, row=fila, colOff=col_off, rowOff=row_off),
        ext=XDRPositiveSize2D(cx=cx, cy=cy),
    )
    ws.add_image(img)


def _est_marcador_ancla(ws, col_ini: int, fila_ini: int,
                        offset_x_emu: int, offset_y_emu: int) -> tuple[int, int, int, int]:
    """Normaliza un offset absoluto (EMU medidos desde la esquina superior
    izquierda de una celda, indices 0-based) al marcador (col, fila, colOff,
    rowOff) cuyo offset cae DENTRO de su propia celda ancla — que es como
    Excel guarda los anclajes de imagen.

    No es cosmetica: LibreOffice RECORTA al renderizar un colOff/rowOff mas
    grande que la celda ancla (verificado 2026-09-01 sobre el PDF real de
    EXTERIORES: el croquis centrado con colOff de ~347 px sobre la columna A
    de ~126 px salia pegado a la izquierda del marco, aunque el centrado en
    EMU fuera exacto). Con el marcador normalizado, Excel y LibreOffice
    renderizan lo mismo."""
    col = col_ini
    while offset_x_emu >= (ancho := _est_col_px(ws, col + 1) * EST_EMU_POR_PX):
        offset_x_emu -= ancho
        col += 1
    fila = fila_ini
    while offset_y_emu >= (alto := _est_fila_px(ws, fila + 1) * EST_EMU_POR_PX):
        offset_y_emu -= alto
        fila += 1
    return col, fila, int(offset_x_emu), int(offset_y_emu)


def _est_insertar_croquis(ws, ruta_croquis: str, ultima_fila: int) -> None:
    """Ancla el croquis DENTRO del marco A18:J{ultima-3}, con proporcion
    conservada y centrado (criterio 4). Deja que las excepciones suban: el
    caller decide la politica (croquis ilegible => se omite y se loguea, la
    generacion no se aborta)."""
    from openpyxl.drawing.image import Image as XLImage

    img = XLImage(ruta_croquis)   # abre y valida el archivo (requiere Pillow)
    nativo_w, nativo_h = int(img.width), int(img.height)
    if nativo_w <= 0 or nativo_h <= 0:
        raise ValueError(f"imagen sin dimensiones: {ruta_croquis}")

    fila_ini = EST_RCO_RFO_PRIMERA_FILA_MARCO
    fila_fin = ultima_fila - EST_RCO_RFO_FILAS_PIE
    marco_w = sum(_est_col_px(ws, c) for c in range(1, 11)) * EST_EMU_POR_PX
    marco_h = sum(_est_fila_px(ws, f) for f in range(fila_ini, fila_fin + 1)) * EST_EMU_POR_PX

    escala = EST_CROQUIS_MARGEN * min(
        marco_w / (nativo_w * EST_EMU_POR_PX),
        marco_h / (nativo_h * EST_EMU_POR_PX),
    )
    cx = int(nativo_w * EST_EMU_POR_PX * escala)
    cy = int(nativo_h * EST_EMU_POR_PX * escala)
    col, fila, col_off, row_off = _est_marcador_ancla(
        ws, 0, fila_ini - 1, (marco_w - cx) // 2, (marco_h - cy) // 2,
    )
    _est_estampar_imagen(
        ws, ruta_croquis,
        col=col, fila=fila, col_off=col_off, row_off=row_off,
        cx=cx, cy=cy,
    )


def _est_estampar_logos(ws, empresa: str, contexto: str,
                        juego=EST_LOGOS_R_POR_EMPRESA) -> None:
    """Decision D4 (ampliada 2026-09-25) — re-estampa los logos en las hojas
    generadas (copy_worksheet los pierde igual que el croquis). `juego` es el
    dict empresa -> tuplas de anclas para la familia de hoja; una empresa sin
    entrada no estampa nada (los CEO/REO de DOMICEM traen su logo nativo en
    la plantilla). Un logo ausente o ilegible se loguea y se omite: no aborta
    un documento oficial por una imagen decorativa."""
    logos = juego.get(empresa)
    if not logos:
        return
    for archivo, (col, fila, col_off, row_off), ancho_px in logos:
        ruta = os.path.join(EST_LOGOS_DIR, archivo)
        if not os.path.exists(ruta):
            print(f"[estimaciones] {contexto}: falta el logo {archivo} en "
                  f"{EST_LOGOS_DIR} — la hoja sale sin ese logo")
            continue
        try:
            from openpyxl.drawing.image import Image as XLImage
            img = XLImage(ruta)
            alto_px = max(1, int(round(ancho_px * img.height / img.width)))
            _est_estampar_imagen(
                ws, ruta, col=col, fila=fila, col_off=col_off, row_off=row_off,
                cx=ancho_px * EST_EMU_POR_PX, cy=alto_px * EST_EMU_POR_PX,
            )
        except Exception as e:
            print(f"[estimaciones] {contexto}: logo ilegible {archivo} ({e}) — "
                  f"la hoja sale sin ese logo")


def _est_ancla_por_x_rgo(ws, x_px: float) -> tuple[int, int]:
    """(col 0-indexada, colOff en EMU) para una X en px desde el borde
    izquierdo de la hoja, caminando los anchos reales de columna A..I. El
    offset queda siempre ADENTRO de su columna (LibreOffice recorta los que
    la exceden)."""
    from openpyxl.utils import get_column_letter
    inicio = 0.0
    for c in range(1, 10):  # A..I, el area de impresion de la RGO
        dim = ws.column_dimensions.get(get_column_letter(c))
        ancho_chars = dim.width if dim is not None and dim.width else 8.43
        ancho_px = ancho_chars * EST_RGO_PX_POR_CHAR
        if x_px < inicio + ancho_px or c == 9:
            return c - 1, max(0, int(round((x_px - inicio) * EST_EMU_POR_PX)))
        inicio += ancho_px
    return 8, 0


def _est_estampar_logos_rgo(ws, empresa: str, contexto: str, n_filas: int) -> None:
    """2026-09-25 — logo en la esquina derecha de CADA bloque de 40 folios
    de la hoja RGO, al ras del borde derecho de la tabla. Pagina 1: logo en
    la zona del titulo, terminando antes de la banda azul. Bloques
    siguientes: version compacta sobre la banda PARTIDA/CLAVE. Mismo
    criterio de fallo que _est_estampar_logos: se loguea y se omite, nunca
    aborta un documento por una imagen."""
    archivo = EST_LOGO_RGO_POR_EMPRESA.get(empresa)
    if not archivo:
        return
    ruta = os.path.join(EST_LOGOS_DIR, archivo)
    if not os.path.exists(ruta):
        print(f"[estimaciones] {contexto}: falta el logo {archivo} en "
              f"{EST_LOGOS_DIR} — la hoja sale sin logo")
        return
    try:
        from openpyxl.utils import get_column_letter
        from openpyxl.drawing.image import Image as XLImage
        img = XLImage(ruta)
    except Exception as e:
        print(f"[estimaciones] {contexto}: logo ilegible {archivo} ({e}) — "
              f"la hoja sale sin logo")
        return
    tabla_der_px = sum(
        (ws.column_dimensions.get(get_column_letter(c)).width
         if ws.column_dimensions.get(get_column_letter(c)) is not None
         and ws.column_dimensions.get(get_column_letter(c)).width else 8.43)
        for c in range(1, 10)
    ) * EST_RGO_PX_POR_CHAR
    # alto disponible en la pagina 1: del borde superior a la banda azul
    # (la fila cuyo A trae el titulo R E S U M E N...), medido con los altos
    # reales de fila de ESTA hoja — varian entre plantillas
    fila_banda = next(
        (r for r in range(1, 14)
         if isinstance(ws.cell(r, 1).value, str)
         and "GENERADORES" in ws.cell(r, 1).value.replace(" ", "").upper()),
        5,
    )
    def _alto_fila_pt(r):
        dim = ws.row_dimensions.get(r)
        if dim is not None and dim.height:
            return dim.height
        return ws.sheet_format.defaultRowHeight or 15.0
    libre_px = sum(_alto_fila_pt(r) for r in range(1, fila_banda)) / 0.75
    # Solo la pagina 1 se estampa aca (unica con franja libre en la hoja).
    # Los bloques 2+ arrancan directo con la banda PARTIDA/CLAVE y no
    # tienen espacio de celda: su logo va en el margen del papel y se
    # estampa DIRECTO sobre el PDF en _est_anexar_escaneos.
    alto = max(20, int(libre_px - EST_RGO_LOGO_RESPIRO_PX))
    ancho = max(1, int(round(alto * img.width / img.height)))
    if ancho > EST_RGO_LOGO_ANCHO_MAX_PX:
        ancho = EST_RGO_LOGO_ANCHO_MAX_PX
        alto = max(1, int(round(ancho * img.height / img.width)))
    col, col_off = _est_ancla_por_x_rgo(
        ws, tabla_der_px - ancho - EST_RGO_LOGO_MARGEN_PX)
    try:
        _est_estampar_imagen(
            ws, ruta, col=col, fila=0, col_off=col_off, row_off=19050,
            cx=ancho * EST_EMU_POR_PX, cy=alto * EST_EMU_POR_PX,
        )
    except Exception as e:
        print(f"[estimaciones] {contexto}: no se pudo estampar el logo "
              f"({e}) — la hoja sale sin logo")


def _est_afirmar_plantilla_sin_imagenes(ws, nombre_hoja: str) -> None:
    """Guarda del hallazgo D1: wb.copy_worksheet() pierde las imagenes EN
    SILENCIO (verificado, openpyxl 3.1.5). Si una hoja PLANTILLA llegara a
    traer imagenes, cada copia saldria sin ellas y nada avisaria — mejor
    cortar aca con un error explicito que entregar documentos incompletos."""
    if ws._images:
        raise HTTPException(status_code=500, detail={
            "error": "plantilla_con_imagenes",
            "detalle": (
                f"la hoja {nombre_hoja} de la plantilla trae "
                f"{len(ws._images)} imagen(es), y wb.copy_worksheet() las "
                f"pierde en silencio al clonar — la PLANTILLA debe nacer sin "
                f"imagenes (se reconstruye con "
                f"scripts/limpiar_plantilla_estimacion.py) y las imagenes se "
                f"estampan al generar, hoja por hoja"
            ),
        })


def _est_agregar_hojas_rco_rfo(wb, req, catalogo, facturas_por_clave, nombres_usados):
    """Issue #27 — crea las hojas CD-COAF-RCO-XX y CD-COAF-RFO-XX, una por
    clave con entregas del periodo (mismo criterio que las RGO), copiando
    las hojas PLANTILLA y completando lo que la copia pierde o lo que es por
    clave. Devuelve (nombres_rco, nombres_rfo) en el orden del catalogo.

    Todo lo que un humano tendria que llenar queda lleno (decision 1): el
    encabezado viaja por las formulas a REO-01 que la PLANTILLA ya trae (y
    que copy_worksheet SI conserva), la fila 15 se escribe aca por clave, el
    croquis se estampa en la RCO si esta archivado, y los logos DOMICEM se
    re-estampan. Lo unico manual que queda son las fotos de la RFO."""
    plantillas = {}
    for familia, nombre_plantilla in (("RCO", EST_RCO_PLANTILLA), ("RFO", EST_RFO_PLANTILLA)):
        if nombre_plantilla not in wb.sheetnames:
            raise HTTPException(status_code=500, detail={
                "error": "plantilla_sin_hojas_rco_rfo",
                "detalle": (
                    f"la plantilla de {req.empresa}/{req.fase} no trae la hoja "
                    f"{nombre_plantilla} — sin ella el documento saldria sin sus "
                    f"hojas RCO/RFO y pareceria completo sin estarlo; hay que "
                    f"reconstruirla con scripts/limpiar_plantilla_estimacion.py"
                ),
            })
        ws_p = wb[nombre_plantilla]
        _est_afirmar_plantilla_sin_imagenes(ws_p, nombre_plantilla)
        plantillas[familia] = ws_p

    nombres = {"RCO": [], "RFO": []}
    claves_sin_croquis = []
    for c in catalogo:
        if not facturas_por_clave[c["clave"]]:
            continue   # clave sin entregas, sin hoja (decision 3)
        fila_reo = EST_REO_FIRST_ROW + (c["orden"] - 1)
        for familia, prefijo in (("RCO", EST_RCO_PREFIJO), ("RFO", EST_RFO_PREFIJO)):
            ws_p = plantillas[familia]
            nombre = _est_nombre_hoja(c["clave"], nombres_usados, prefijo)
            ws = wb.copy_worksheet(ws_p)
            ws.title = nombre

            # Config de impresion y print_area EN CADA HOJA, DESPUES de
            # copiar — verificado (openpyxl 3.1.5): wb.copy_worksheet()
            # pierde print_area en silencio (los merges y las formulas si
            # sobreviven). El footer tampoco sobrevive la copia (medido aca
            # mismo, no estaba en el spec) — se repone desde la PLANTILLA.
            ultima_fila, escala = _est_geometria_rco_rfo(familia, req.empresa, req.fase)
            ws.page_setup.orientation = "landscape"
            ws.page_setup.scale = escala
            ws.page_setup.fitToWidth = None
            ws.page_setup.fitToHeight = 0
            ws.sheet_properties.pageSetUpPr.fitToPage = False
            ws.print_area = f"'{nombre}'!$A$1:$J${ultima_fila}"
            ws.oddFooter.center.text = ws_p.oddFooter.center.text

            # fila 15 — partida como valor (igual que la RGO) y clave/
            # concepto/U.M. por formula a la fila de esta clave en REO-01
            # (criterio 2), como en los documentos del cliente.
            #
            # El hallazgo que el #27 dejo marcado aca — la columna A del REO
            # llevaba c["orden"] y no c["clave"], asi que en
            # VMO/PATIO DE MANIOBRAS-TRA esta B15 heredaba la clave
            # equivocada y contradecia a su RGO hermana — quedo ARREGLADO
            # en el REO el 2026-09-01. Custodiado por
            # tests/test_reo_columna_clave.py, que verifica que las tres
            # hojas de una clave digan lo mismo, tambien recalculadas.
            #
            # El PARTIDA: (A15) queda VACIO — issue #37, decidido 2026-09-02.
            # Los 15 documentos del cliente dejan ahi una formula fija a
            # 'CD-COAF-REO-01'!$A$16, y esa celda esta vacia en las 24
            # planillas medidas (varios traen 0 como valor cacheado, que es
            # justo lo que da una referencia a una celda vacia). O sea: en sus
            # documentos ese casillero sale en blanco siempre. Se copia ese
            # criterio, que es el que el resto del generador viene siguiendo.
            # No se escribe la formula porque produciria el mismo blanco
            # agregando una dependencia entre hojas; no escribir nada deja el
            # archivo identico y es mas simple. Antes iba c["orden"], un
            # numero que el cliente nunca vio en ese casillero.
            ws.cell(15, 1).value = None
            ws.cell(15, 2).value = f"='CD-COAF-REO-01'!$A${fila_reo}"
            ws.cell(15, 3).value = f"='CD-COAF-REO-01'!$B${fila_reo}"
            ws.cell(15, 10).value = f"='CD-COAF-REO-01'!$C${fila_reo}"

            if familia == "RCO":
                ruta_croquis = _est_buscar_croquis(req.empresa, req.fase, c["clave"])
                if ruta_croquis is None:
                    claves_sin_croquis.append(str(c["clave"]))
                else:
                    try:
                        _est_insertar_croquis(ws, ruta_croquis, ultima_fila)
                    except Exception as e:
                        # un PNG corrupto o con extension falsa no aborta la
                        # generacion: se omite, se registra, el documento sale
                        print(f"[estimaciones] croquis ilegible para "
                              f"{req.empresa}/{req.fase} clave {c['clave']} "
                              f"({ruta_croquis}): {e} — la RCO sale con el "
                              f"marco vacio")
                        claves_sin_croquis.append(str(c["clave"]))

            _est_estampar_logos(ws, req.empresa, nombre)
            nombres[familia].append(nombre)

    if claves_sin_croquis:
        print(f"[estimaciones] {req.empresa}/{req.fase}: sin croquis archivado "
              f"para las claves {', '.join(claves_sin_croquis)} — las RCO salen "
              f"con el marco vacio (se archivan en {EST_CROQUIS_DIR})")
    return nombres["RCO"], nombres["RFO"]


def _est_filas_firma_reo(ws_reo) -> tuple[int, int]:
    """Issue #33 — devuelve (fila_nombre, fila_cargo) del bloque de firma de
    CD-COAF-REO-01, detectadas leyendo la hoja: la fila del cargo es la que
    lleva el rotulo EST_REO_FIRMA_ANCLA en la columna B, y la del nombre es
    la inmediatamente anterior.

    Revienta con un error explicito si el ancla falta o aparece mas de una
    vez, en vez de adivinar una fila: el documento sale firmado o no sale.
    """
    filas = [
        r for r in range(1, ws_reo.max_row + 1)
        if isinstance(ws_reo.cell(r, EST_REO_FIRMA_ANCLA_COL).value, str)
        and ws_reo.cell(r, EST_REO_FIRMA_ANCLA_COL).value.strip().upper() == EST_REO_FIRMA_ANCLA
    ]
    if len(filas) != 1 or filas[0] < 2:
        raise HTTPException(status_code=500, detail={
            "error": "bloque_de_firma_no_encontrado",
            "detalle": (
                f"CD-COAF-REO-01 deberia tener exactamente un rotulo "
                f"'{EST_REO_FIRMA_ANCLA}' en la columna B (la fila del cargo del "
                f"bloque de firma) y se encontraron {len(filas)}: {filas} — la "
                f"plantilla cambio de estructura, hay que revisarla antes de "
                f"generar un documento oficial sin firma"
            ),
        })
    return filas[0] - 1, filas[0]


def _est_escribir_firma_rgo(ws_rgo, ws_reo, contratista: str) -> None:
    """Issue #33 — escribe nombre y cargo del bloque de firma de la RGO como
    VALOR, copiados de REO-01 desde la fila donde realmente estan. Issue #35 —
    escribe ademas el contratista, que viene de EST_CONTRATISTA y no de REO-01.

    Se escribe valor y no una formula corregida a proposito: una formula
    obliga a que algo recalcule el libro (Excel o LibreOffice) para que el
    nombre aparezca, y el mismo mecanismo que la llevo a apuntar a la fila
    equivocada la puede volver a desalinear sin que nadie se entere. Un
    valor sale igual en el .xlsx, en el PDF y al leerlo con openpyxl, asi
    que ademas se puede verificar en un test sin depender de LibreOffice.
    No se pierde nada dinamico: el generador nunca escribe el bloque de
    firma de REO-01 — es texto fijo de la plantilla de cada fase.

    Se llama sobre CD-COAF-RGO-PLANTILLA antes de clonarla, asi el arreglo
    viaja solo a todas las hojas RGO y, por el snapshot del pie que ya
    hacen _est_redimensionar_rgo()/_est_rgo_paginado(), tambien a la
    posicion final del pie y a la firma repetida de cada pagina.
    """
    from openpyxl.utils import get_column_letter

    fila_nombre, fila_cargo = _est_filas_firma_reo(ws_reo)
    fila_rgo_nombre, fila_rgo_cargo = EST_RGO_SIG_ROWS

    for col_reo, col_rgo in EST_FIRMA_COLS:
        for fila_reo, fila_rgo in ((fila_nombre, fila_rgo_nombre), (fila_cargo, fila_rgo_cargo)):
            valor = ws_reo.cell(fila_reo, col_reo).value
            texto = valor.strip() if isinstance(valor, str) else ""
            if not texto or texto.startswith("="):
                coord = f"{get_column_letter(col_reo)}{fila_reo}"
                raise HTTPException(status_code=500, detail={
                    "error": "bloque_de_firma_vacio",
                    "detalle": (
                        f"CD-COAF-REO-01!{coord} deberia traer el texto del bloque "
                        f"de firma y trae {valor!r} — la plantilla cambio de "
                        f"estructura, hay que revisarla antes de generar un "
                        f"documento oficial sin firma"
                    ),
                })
            ws_rgo.cell(fila_rgo, col_rgo).value = texto

    # la firma de gerencia de obra era una formula matricial sobre H60:K60;
    # ya reemplazada por un escalar en H60, las 3 celdas restantes se quedan
    # con el 0 cacheado del rango original si no se limpian
    col_gerencia = EST_FIRMA_COLS[1][1]
    for c in range(col_gerencia + 1, col_gerencia + EST_RGO_FIRMA_ARRAY_SPAN):
        ws_rgo.cell(fila_rgo_nombre, c).value = None

    # Issue #35 — el contratista. Solo fila de nombre: el rotulo "CONTRATISTA"
    # de la fila de abajo es fijo de la plantilla y no se toca.
    texto_contratista = contratista.strip() if isinstance(contratista, str) else ""
    if not texto_contratista:
        raise HTTPException(status_code=500, detail={
            "error": "contratista_vacio",
            "detalle": (
                f"el contratista de la empresa deberia venir de EST_CONTRATISTA "
                f"y llego {contratista!r} — sin el, la hoja RGO saldria con el "
                f"literal cableado de la plantilla, que dice 'VMO CONCRETOS' "
                f"incluso en las fases de DOMICEM"
            ),
        })
    ws_rgo.cell(fila_rgo_nombre, EST_RGO_FIRMA_COL_CONTRATISTA).value = texto_contratista


def _est_fila_dato_rgo(i: int) -> int:
    """Fila absoluta del folio i (0-indexado) en una hoja RGO. Con 40 folios
    o menos coincide con EST_RGO_FIRST_ROW + i (hoja de una sola pagina, el
    comportamiento historico); del folio 41 en adelante cada pagina corre
    EST_RGO_PERIODO filas hacia abajo (issue #18)."""
    pagina, offset = divmod(i, EST_RGO_CAPACIDAD_NATIVA)
    return EST_RGO_FIRST_ROW + pagina * EST_RGO_PERIODO + offset

def _est_redimensionar_rgo(ws, n_filas: int) -> int:
    """Ajusta una hoja RGO (copia en memoria de CD-COAF-RGO-PLANTILLA, ya
    duplicada con wb.copy_worksheet para UN producto) para que el pie
    (TOTAL + firmas) quede donde corresponde segun n_filas de entregas.

    - n_filas <= 40 (capacidad nativa): comportamiento historico intacto —
      la hoja se encoge (TOTAL en 18+n) o queda nativa (n == 40, TOTAL en
      58), una sola pagina continua, sin saltos.
    - n_filas > 40: hoja paginada en bloques de 40 folios por pagina
      (issue #18, exigencia del cliente 2026-08-27) — ver
      _est_rgo_paginado(). Reemplaza al viejo camino de "crecer" la hoja
      continua.

    Nunca usa insert_rows()/delete_rows() (openpyxl no ajusta formulas ni
    celdas combinadas de forma confiable con esas funciones, confirmado con
    Codex el 2026-08-20 antes de construir esto) — todo se mueve a mano,
    celda por celda. Devuelve la fila donde quedo el TOTAL (para la formula
    de REO-01 que lo referencia).
    """
    if n_filas > EST_RGO_CAPACIDAD_NATIVA:
        return _est_rgo_paginado(ws, n_filas)

    first = EST_RGO_FIRST_ROW
    if n_filas == EST_RGO_CAPACIDAD_NATIVA:
        return EST_RGO_TOTAL_ROW

    filas_pie_originales = [EST_RGO_TOTAL_ROW] + list(EST_RGO_SIG_ROWS)
    # a diferencia de REO-01 (que si tiene 1 fila en blanco antes de
    # TOTALES), la hoja RGO nativa NO tiene fila en blanco entre la ultima
    # fila de dato y TOTAL (fila 57 dato, fila 58 TOTAL, sin hueco) — bug
    # encontrado con el caso limite n=40 (capacidad nativa, sin redimensionar)
    nuevo_total_row = first + n_filas
    # entre TOTAL y las firmas tambien hay 1 fila en blanco en la plantilla
    # nativa (58 TOTAL, 59 blanco, 60 firma1, 61 firma2) — hay que respetar
    # ese mismo hueco en la posicion nueva, si no las firmas quedan pegadas
    # al TOTAL y una de las dos se pierde (bug encontrado probando esto)
    filas_pie_nuevas = [nuevo_total_row, nuevo_total_row + 2, nuevo_total_row + 3]
    filas_a_no_ocultar = set(filas_pie_nuevas) | {nuevo_total_row + 1}  # el hueco entre TOTAL y firma1

    # capturar el pie (valores + estilos) ANTES de tocar nada
    snapshot = []
    for r in filas_pie_originales:
        fila = {}
        for c in range(1, 12):
            cell = ws.cell(r, c)
            fila[c] = {
                "value": cell.value, "font": _copiar_estilo(cell.font),
                "border": _copiar_estilo(cell.border), "fill": _copiar_estilo(cell.fill),
                "alignment": _copiar_estilo(cell.alignment), "protection": _copiar_estilo(cell.protection),
                "number_format": cell.number_format,
            }
        snapshot.append((r, fila, ws.row_dimensions[r].height))

    # quitar TODAS las fusiones que toquen tanto la posicion vieja del pie
    # como la posicion nueva (esta ultima puede traer fusiones de fila de
    # dato "D18:F18 estilo" heredadas de la plantilla nativa de 40 filas si
    # se esta encogiendo — sin esto quedan 2 fusiones pisadas una con otra,
    # bug encontrado probando el caso de encoger). Solo la celda superior-
    # izquierda de una fusion es escribible, por eso esto va antes que
    # cualquier escritura de valores/fusiones nuevas
    filas_afectadas = set(filas_pie_originales) | set(filas_pie_nuevas)
    pie_merges = [str(m) for m in list(ws.merged_cells.ranges)
                  if any(m.min_row <= r <= m.max_row for r in filas_pie_originales)]
    for rng in list(ws.merged_cells.ranges):
        if any(rng.min_row <= r <= rng.max_row for r in filas_afectadas):
            ws.unmerge_cells(str(rng))

    # (el viejo camino de "crecer" la hoja continua para n > 40 vivio aca
    # hasta el issue #18; hoy ese caso lo cubre _est_rgo_paginado, asi que
    # de aqui en adelante siempre es encoger: n_filas < 40)

    # limpiar todo el rango entre la ultima fila de dato usada y el viejo
    # pie; las filas sobrantes quedan ocultas en vez de borradas —
    # openpyxl no borra filas de forma segura
    limite_inferior = max(EST_RGO_SIG_ROWS[-1], filas_pie_nuevas[-1])
    for r in range(first + n_filas, limite_inferior + 1):
        for c in range(1, 12):
            ws.cell(r, c).value = None
        if r not in filas_a_no_ocultar:
            ws.row_dimensions[r].hidden = True

    # reescribir el pie en su nueva posicion
    for (r_original, fila, altura), r_nuevo in zip(snapshot, filas_pie_nuevas):
        ws.row_dimensions[r_nuevo].height = altura
        ws.row_dimensions[r_nuevo].hidden = False
        for c, datos in fila.items():
            valor = datos["value"]
            if isinstance(valor, ArrayFormula):
                # una formula matricial guarda su rango (ref) — hay que
                # correrlo a la fila nueva o quedaria apuntando a la fila vieja
                ancho = valor.ref.split(":")
                from openpyxl.utils.cell import coordinate_from_string
                col_ini, _ = coordinate_from_string(ancho[0])
                col_fin, _ = coordinate_from_string(ancho[1]) if len(ancho) > 1 else (col_ini, None)
                valor = ArrayFormula(ref=f"{col_ini}{r_nuevo}:{col_fin}{r_nuevo}", text=valor.text)
            cell = ws.cell(r_nuevo, c)
            cell.value = valor
            cell.font = datos["font"]; cell.border = datos["border"]; cell.fill = datos["fill"]
            cell.alignment = datos["alignment"]; cell.protection = datos["protection"]
            cell.number_format = datos["number_format"]
        for rng in pie_merges:
            from openpyxl.utils.cell import range_boundaries
            min_col, min_row, max_col, max_row = range_boundaries(rng)
            if min_row == r_original:
                ws.merge_cells(start_row=r_nuevo, start_column=min_col, end_row=r_nuevo, end_column=max_col)

    ws.cell(nuevo_total_row, 7).value = f"=SUM(G{first}:G{first + n_filas - 1})"
    return nuevo_total_row


def _est_rgo_paginado(ws, n_filas: int) -> int:
    """Issue #18 — construye la hoja RGO paginada en bloques de 40 folios
    por pagina (exigencia del cliente, 2026-08-27). Solo se llama con
    n_filas > EST_RGO_CAPACIDAD_NATIVA; con 40 o menos manda el
    comportamiento historico de _est_redimensionar_rgo, intacto.

    Por cada pagina k (0-indexada, periodo de EST_RGO_PERIODO = 48 filas):
    - datos en 18+k*48 .. 18+k*48+39 — SIEMPRE 40 filas, la ultima pagina
      incluida aunque quede a medio llenar (igual que los documentos
      reales del cliente: en su RGO-06 los datos terminan en 227 pero el
      bloque llega a 252 y recien ahi va el TOTAL)
    - pie en las 4 filas siguientes: pagina intermedia -> blanco, blanco,
      firma1, firma2 (los blancos copian estilo/altura/fusiones de las
      filas 58-59 de la plantilla pero sin el rotulo TOTAL: ni la formula);
      ultima pagina -> TOTAL, blanco, firma1, firma2
    - salto de pagina explicito en la fila de la segunda firma
      (Break(id=N) corta DESPUES de la fila N); no hay salto despues de la
      ultima pagina, asi que len(row_breaks.brk) == paginas - 1
    - encabezado de la pagina siguiente en las 4 filas que siguen al pie:
      copia de las filas 14-17 (etiquetas, valores, blanco, titulos)

    El TOTAL aparece UNA sola vez, en el pie de la ultima pagina, y su
    formula suma un rango por pagina en orden ascendente y sin coma
    colgante: =SUM(G18:G57,G66:G105,...) — mismo valor que calculan los
    documentos del cliente, sin reproducir el desorden de armarlos a mano.

    Misma restriccion heredada que _est_redimensionar_rgo: nunca
    insert_rows()/delete_rows() — encabezado, pie y filas de dato se
    replican celda por celda (valor, formula, estilo, fusiones y altura de
    fila), reusando el mismo mecanismo de snapshot + reescritura que ya
    usa el camino de una pagina para mover el pie. Devuelve la fila del
    TOTAL para la formula de REO-01.
    """
    from openpyxl.utils.cell import coordinate_from_string, range_boundaries

    first = EST_RGO_FIRST_ROW
    bloque = EST_RGO_CAPACIDAD_NATIVA
    paginas = -(-n_filas // bloque)  # ceil(n_filas / bloque) sin importar math

    filas_enc = list(EST_RGO_ENC_ROWS)
    # pie completo de la plantilla: 58 TOTAL, 59 blanco, 60 firma1, 61 firma2
    filas_pie = [EST_RGO_TOTAL_ROW, EST_RGO_TOTAL_ROW + 1] + list(EST_RGO_SIG_ROWS)

    # ── snapshots (valores + estilos + alturas + fusiones) ANTES de tocar nada ──
    def _snapshot_fila(r):
        fila = {}
        for c in range(1, 12):
            cell = ws.cell(r, c)
            fila[c] = {
                "value": cell.value, "font": _copiar_estilo(cell.font),
                "border": _copiar_estilo(cell.border), "fill": _copiar_estilo(cell.fill),
                "alignment": _copiar_estilo(cell.alignment), "protection": _copiar_estilo(cell.protection),
                "number_format": cell.number_format,
            }
        return fila, ws.row_dimensions[r].height

    snap_enc = [(r,) + _snapshot_fila(r) for r in filas_enc]
    snap_pie = [(r,) + _snapshot_fila(r) for r in filas_pie]
    # modelo de fila de dato para las paginas 2+ (misma eleccion que el
    # viejo camino de crecer: la ultima fila de dato nativa)
    fila_dato_modelo, altura_dato = _snapshot_fila(EST_RGO_LAST_ROW)

    # las fusiones de encabezado y pie de la plantilla son todas de una
    # sola fila (C14:G14, C15:G15, D17:F17, A58:F58, A60:B60, D60:F60,
    # A61:B61, D61:F61) — se capturan como strings y se reconstruyen fila
    # por fila en cada replica
    merges_enc = [str(m) for m in ws.merged_cells.ranges
                  if any(m.min_row <= r <= m.max_row for r in filas_enc)]
    merges_pie = [str(m) for m in ws.merged_cells.ranges
                  if any(m.min_row <= r <= m.max_row for r in filas_pie)]

    # el pie nativo (58-61) se reescribe como pie de la pagina 1 — igual
    # que en el camino de una pagina, hay que desfusionarlo antes de
    # escribir (solo la celda superior-izquierda de una fusion es
    # escribible). Las fusiones D:F de las filas de dato 18-57 no se tocan.
    for rng in list(ws.merged_cells.ranges):
        if any(rng.min_row <= r <= rng.max_row for r in filas_pie):
            ws.unmerge_cells(str(rng))

    def _escribir_fila(r_dst, fila, altura, r_src=None, merges=()):
        ws.row_dimensions[r_dst].height = altura
        ws.row_dimensions[r_dst].hidden = False
        for c, datos in fila.items():
            valor = datos["value"]
            if isinstance(valor, ArrayFormula):
                # una formula matricial guarda su rango (ref) — hay que
                # correrlo a la fila nueva o quedaria apuntando a la vieja
                partes = valor.ref.split(":")
                col_ini, _ = coordinate_from_string(partes[0])
                col_fin, _ = coordinate_from_string(partes[1]) if len(partes) > 1 else (col_ini, None)
                valor = ArrayFormula(ref=f"{col_ini}{r_dst}:{col_fin}{r_dst}", text=valor.text)
            cell = ws.cell(r_dst, c)
            cell.value = valor
            cell.font = _copiar_estilo(datos["font"])
            cell.border = _copiar_estilo(datos["border"])
            cell.fill = _copiar_estilo(datos["fill"])
            cell.alignment = _copiar_estilo(datos["alignment"])
            cell.protection = _copiar_estilo(datos["protection"])
            cell.number_format = datos["number_format"]
        for rng in merges:
            min_col, min_row, _max_col, _max_row = range_boundaries(rng)
            if min_row == r_src:
                ws.merge_cells(start_row=r_dst, start_column=min_col,
                               end_row=r_dst, end_column=_max_col)

    rangos_por_pagina = []
    total_row = None
    for k in range(paginas):
        d0 = first + k * EST_RGO_PERIODO
        d_fin = d0 + bloque - 1
        rangos_por_pagina.append(f"G{d0}:G{d_fin}")

        if k > 0:
            # filas de dato de las paginas 2+: clonar estilo/altura y la
            # fusion D:F de una fila de dato nativa (las de la pagina 1,
            # 18-57, ya estan en la plantilla y no se tocan)
            for r in range(d0, d_fin + 1):
                _escribir_fila(r, fila_dato_modelo, altura_dato)
                ws.merge_cells(f"D{r}:F{r}")

        pie0 = d_fin + 1
        es_ultima = k == paginas - 1
        for idx, (r_src, fila, altura) in enumerate(snap_pie):
            _escribir_fila(pie0 + idx, fila, altura, r_src=r_src, merges=merges_pie)
        if es_ultima:
            total_row = pie0
        else:
            # pie intermedio: mismo estilo/altura/fusiones que la fila 58,
            # pero sin el rotulo TOTAL: (col A) ni la formula (col G) —
            # queda visualmente igual al hueco que la plantilla deja antes
            # de las firmas
            ws.cell(pie0, 1).value = None
            ws.cell(pie0, 7).value = None
            ws.row_breaks.append(Break(id=pie0 + EST_RGO_PIE_FILAS - 1))
            for idx, (r_src, fila, altura) in enumerate(snap_enc):
                _escribir_fila(pie0 + EST_RGO_PIE_FILAS + idx, fila, altura,
                               r_src=r_src, merges=merges_enc)

    ws.cell(total_row, 7).value = "=SUM(" + ",".join(rangos_por_pagina) + ")"
    return total_row

# Registro (empresa,fase) -> plantilla + capacidad (cantidad de filas de
# producto que esa plantilla trae de forma nativa, ver
# scripts/limpiar_plantilla_estimacion.py). Si catalogo_estimacion tiene
# MENOS productos que la capacidad, las filas sobrantes quedan en blanco
# (nunca se borran/mueven filas — unico caso real: MACAO 2, ver
# docs/designs/generador-estimaciones-plantillas.md). Si tiene MAS, se
# rechaza en _est_plantilla_de_fase.
#
# `renglones_extra`: productos que el documento del cliente todavia NO trae y
# que la plantilla suma por su cuenta, ocupando la fila en blanco que el
# documento real deja entre el bloque y TOTALES (por eso como mucho 1: no se
# inserta ninguna fila, nada de abajo se corre). La capacidad los incluye.
# Los aplica scripts/limpiar_plantilla_estimacion.py al reconstruir.
# Casos: VMO/EXTERIORES clave 16, Mortero fc250, agregado el 2026-10-05
# porque aparecieron 2 conduces (M700019645/46, 14 m3, 2026-09-05) sin renglon;
# VMO/CEDIS clave 13, Pavimentacion rigida MR-42 a 166,45, agregado el
# 2026-10-20 por 17 conduces (128 m3, 2026-09-22 a 2026-10-01) sin renglon.
EST_PLANTILLAS = {
    ("DOMICEM", "CAVERNAS"): {"archivo": "plantilla_estimacion_DOMICEM_CAVERNAS.xlsx", "capacidad": 13},
    ("DOMICEM", "VIVIENDAS"): {"archivo": "plantilla_estimacion_DOMICEM_VIVIENDAS.xlsx", "capacidad": 9},
    ("DOMICEM", "MACAO 2"): {"archivo": "plantilla_estimacion_DOMICEM_MACAO_2.xlsx", "capacidad": 9},
    ("DOMICEM", "PATIO DE MANIOBRAS-TRB"): {"archivo": "plantilla_estimacion_DOMICEM_PATIO_DE_MANIOBRAS_TRB.xlsx", "capacidad": 4},
    ("VMO", "CANCHAS"): {"archivo": "plantilla_estimacion_VMO_CANCHAS.xlsx", "capacidad": 3},
    ("VMO", "CEDIS"): {"archivo": "plantilla_estimacion_VMO_CEDIS.xlsx", "capacidad": 13,
                       "renglones_extra": 1},
    ("VMO", "PATIO DE MANIOBRAS-TRA"): {"archivo": "plantilla_estimacion_VMO_PATIO_DE_MANIOBRAS_TRA.xlsx", "capacidad": 4},
    ("VMO", "PODIUM-1-2-3"): {"archivo": "plantilla_estimacion_VMO_PODIUM_1_2_3.xlsx", "capacidad": 3},
    ("VMO", "EXTERIORES"): {"archivo": "plantilla_estimacion_VMO_EXTERIORES.xlsx", "capacidad": 16,
                            "renglones_extra": 1},
}


def _est_plantilla_de_fase(empresa: str, fase: str, catalogo: list) -> str:
    info = EST_PLANTILLAS.get((empresa, fase))
    if not info:
        raise HTTPException(status_code=500, detail={
            "error": "plantilla_no_encontrada",
            "detalle": f"no hay plantilla registrada para {empresa}/{fase}",
        })
    ruta = os.path.join(EST_DATA_DIR, info["archivo"])
    if not os.path.exists(ruta):
        raise HTTPException(status_code=500, detail={
            "error": "plantilla_no_encontrada",
            "detalle": f"falta el archivo {info['archivo']} para {empresa}/{fase}",
        })
    catalogo_len = len(catalogo)
    if catalogo_len > info["capacidad"]:
        raise HTTPException(status_code=422, detail={
            "error": "catalogo_desincronizado",
            "detalle": (
                f"catalogo_estimacion tiene {catalogo_len} productos para {empresa}/{fase} "
                f"pero la plantilla {info['archivo']} solo soporta {info['capacidad']} — "
                f"hay que reconstruir la plantilla con scripts/limpiar_plantilla_estimacion.py"
            ),
        })
    # El codigo usa `orden` para calcular la fila fisica exacta donde se
    # escribe cada producto (EST_REO_FIRST_ROW + orden - 1) — un hueco en la
    # secuencia escribiria en la fila equivocada de un documento oficial sin
    # ningun error. Duplicados son imposibles a nivel de esquema (PK
    # compuesta empresa/fase/orden en catalogo_estimacion).
    ordenes = sorted(c["orden"] for c in catalogo)
    if ordenes != list(range(1, catalogo_len + 1)):
        raise HTTPException(status_code=422, detail={
            "error": "catalogo_desincronizado",
            "detalle": (
                f"catalogo_estimacion para {empresa}/{fase} tiene 'orden' con huecos "
                f"({ordenes}) — debe ser una secuencia contigua 1..{catalogo_len} sin huecos, "
                f"o un producto escribiria en la fila fisica equivocada del documento oficial"
            ),
        })
    return ruta

def _est_normalizar(descripcion: str) -> str:
    s = (descripcion or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s.rstrip(".").upper()


def _est_normalizar_catalogo(descripcion: str) -> str:
    """Como _est_normalizar, pero ademas quita una posible etiqueta de elemento
    estructural al final (2+ palabras en MAYUSCULAS, ej. 'LOSAS Y VIGAS',
    'PILOTES') que Vision no puede leer porque no esta en el documento fisico.
    OJO: la deteccion de mayusculas debe hacerse ANTES de normalizar a mayusculas
    todo el texto, si no cualquier palabra final calificaria como "etiqueta"."""
    s = (descripcion or "").strip()
    s = re.sub(r"\s+", " ", s)
    m = re.match(r"^(.*?)\s+([A-Z0-9()/\-]{1,}(?:\s+[A-Z0-9()/\-]{1,}){1,})$", s)
    base = m.group(1) if m else s
    base = re.sub(r"\s+", " ", base).strip().rstrip(".")
    return base.upper()


_EST_ALIAS_DESCRIPCION_FACTURA = {
    # (empresa, fase) -> {texto normalizado (_est_normalizar, sin recortar
    # etiqueta) tal cual aparece en la factura real -> clave del catalogo}.
    # Escopeado por fase a proposito (corregido 2026-08-27, ver abajo): un
    # alias nunca debe poder aplicarse a una fase distinta de la que se
    # verifico, aunque esa otra fase tenga una clave con el mismo numero
    # para un producto totalmente distinto.
    ("DOMICEM", "MACAO 2"): {
        # clave 7 (LOSAS Y VIGAS HIDROFUGO): confirmado con el usuario
        # 2026-08-25 que "Imp" es el mismo aditivo que "Hidrofugo" — Vision/el
        # papel del conduce lo abrevia distinto al texto canonico del catalogo
        # real ("...rev. 6"+/- 1", Hidrofugo. LOSAS Y VIGAS (HIDROFUGO)"), y esto
        # va a seguir pasando (no fue un lote puntual). Verificado contra 9
        # facturas reales de 2026-07-24 que quedaban sin resolver por esto.
        'HORMIGÓN 350KG/CM2, AMB IIIA (EHE), AG 3/8",T 32C, A/C= 0.45, MIN. C: 300KG, REV. 6" +/- 1", IMP': "7",
        # clave 6 ($154.02): agregado 2026-09-02 (issue #23). El conduce
        # M800014137 (2026-07-24, 1.5 m3) trae impreso el CODIGO DE PRODUCTO
        # 4419, y el 4419 de `Lista de precios.xlsx` es exactamente el producto
        # de la clave 6. Del texto del catalogo lo separan solo espacios:
        # "AMB. III A" contra "AMB. IIIA", y 'REV. 6"+ / -1"' contra
        # 'REV. 6"+/- 1"'. _est_normalizar colapsa espacios repetidos pero no
        # los inserta ni los borra, asi que no alcanza. Leido del PDF fisico
        # (estimaciones/facturas/procesadas/07-24-M8-14137.pdf), no inferido
        # por parecido de texto.
        'HORMIGÓN FC350 KG/CM2, AMB. III A (EHE), AGG 3/8", TEMP. 32C, A/C=0.50, REV. 6"+ / -1"': "6",
    },
    ("DOMICEM", "CAVERNAS"): {
        # 3 alias encontrados en la auditoria de 2026-08-27 (comparacion
        # contra los documentos reales EST_DOMICEM_..._N44/N45). CAVERNAS
        # usa textos de revenimiento/formato distintos a los de CEDIS/VIVIENDAS
        # para variantes del mismo producto — verificado contra el N44/N45
        # real: el "Esta Estimacion" de cada clave coincide exacto una vez
        # aplicado el alias (clave 2: 370.0 m3 = $41,070; clave 3: 173.0 m3 =
        # $21,106; clave 1: 52.0 m3 = $5,668).
        'HORMIGÓN 150 KG/CM2, AG 3/4",T 35C, REV. 7" +/- 1"': "2",
        'HORMIGÓN 210,AGG 3/4, TEMP 35C, REV. 6+/-1': "3",
        'HORMIGÓN FC100 KG/CM2, AGG 3/4", TEMP. 35C, REV. 6"+/- 1"': "1",
        # clave 2 ($111): agregado 2026-09-02 (issues #23 y #26). Cuarta
        # variante de revenimiento del mismo hormigon 150 — el catalogo dice
        # rev. 6", el alias de arriba cubre el 7", y este conduce dice 8".
        # No se dedujo por parecido: el conduce M800013172 (2026-06-30, 7.0 m3)
        # trae impreso el CODIGO DE PRODUCTO 44510, y el 44510 de
        # `Lista de precios.xlsx` es 'Hormigón 150 kg/cm2, Ag 3/4",T 35C,
        # rev. 7" +/- 1"' a $111.00, o sea la clave 2. El 8" del texto es un
        # tipeo de la planta en el campo libre; el codigo manda. Leido del PDF
        # ("Puente 1/06-30-M8-13172.pdf" en conduces/archivos/Puente 1.zip).
        'HORMIGÓN 150 KG/CM2, AG 3/4",T 35C, REV. 8" +/- 1"': "2",
    },
    ("VMO", "EXTERIORES"): {
        # 2 alias agregados 2026-09-02 (issue #23), los dos verificados contra
        # el CODIGO DE PRODUCTO impreso en el conduce, no por parecido de texto.
        # Los PDFs viven en conduces/archivos/Puente 1.zip.
        #
        # clave 9 ($147) — 75 facturas, 479.0 m3, junio 2026. El conduce
        # 06-01-M8-12024 trae el codigo 44522, y el 44522 de
        # `Lista de precios.xlsx` es 'Hormigón 280 kg/cm2, Ag 3/4",T 32C,
        # rev. 7" +/- 1", imp' a $147.00 — texto identico al de la factura. El
        # catalogo escribe ese mismo producto como '...rev. Imp', sin el
        # revenimiento, y por eso no matcheaba. Cierra la disyuntiva del #23
        # entre la clave 8 ($136) y la 9 ($147), $5,269 de diferencia, a favor
        # de la 9. Coincide ademas con el N17 real de EXTERIORES, que asigna
        # 255 m3 a la clave 9 y cero a la 8 en el periodo 17-jun/16-jul.
        'HORMIGÓN 280 KG/CM2, AG 3/4",T 32C, REV. 7" +/- 1", IMP': "9",
        # clave 8 ($136) — 22 facturas, 119.0 m3, 1 al 13 de junio 2026. El
        # conduce 06-01-M8-12025 trae el codigo 4415, y el 4415 de
        # `Lista de precios.xlsx` es 'Hormigón Fc280 kg/cm2, Agg 3/4",
        # Temp. 32C, rev. 6"+/- 1"' a $136.00 — texto identico al de la
        # factura. Es la misma especificacion de la clave 8, escrita con las
        # abreviaturas largas ("Fc280", "Agg", "Temp.") en vez de las cortas.
        'HORMIGÓN FC280 KG/CM2, AGG 3/4", TEMP. 32C, REV. 6"+/- 1"': "8",
    },
    ("VMO", "PATIO DE MANIOBRAS-TRA"): {
        # clave 4 ($186.98): agregado 2026-09-02 (issue #23). 3 facturas,
        # 20.0 m3, todas del 2026-07-13. El conduce 07-13-M8-13751 trae
        # impreso el CODIGO DE PRODUCTO 4477, y `Lista de precios.xlsx` tiene
        # una fila explicita "MACAO ALTO RESORT S.R.L, (PATIO DE MANIOBRA TRA)"
        # con el codigo 4477 a $186.98, que es la clave 4 de esta fase.
        # OJO: TRA es la unica fase donde `orden` y `clave` NO coinciden (el
        # orden 2 tiene clave 3 y el orden 3 tiene clave 2). Aca da igual
        # porque el orden 4 tiene clave 4, pero no copiar este alias a otra
        # fase asumiendo que la numeracion se traslada.
        'HORMIGÓN 350KG/CM2, AMB IIIA (EHE), AG 3/8",T 32C, A/C= 0.45, MIN. C: 300KG, REV. 6" +/- 1", IMP': "4",
    },
    ("VMO", "PODIUM-1-2-3"): {
        # falta una coma antes de "Fibra" en el catalogo (clave 3) respecto
        # al texto real de las 240 facturas historicas. Verificado contra
        # EST_VMO_PODIUM_1,2,3_PPACT_N05 real: 935.0 m3 = $132,770, el 100%
        # de la estimacion del periodo.
        'HORMIGÓN 280 KG/CM2, AG 3/4",T 32C, REV. 7" +/- 1", FIBRA': "3",
    },
}


def _est_catalogo_norm_a_clave(catalogo: list, empresa: str, fase: str) -> dict:
    """Como {_est_normalizar_catalogo(desc): clave}, pero si 2 productos del
    catalogo normalizan al mismo texto (colision real conocida: MACAO 2
    'CIMENTACION TORRES' vs 'TORRE GRUA', mismo concreto exacto, sin ninguna
    forma de distinguirlos desde la factura fisica), esa clave queda con
    valor None a proposito — el llamador debe tratar None igual que 'no matcheo',
    forzando revision manual siempre, nunca auto-asignar a una de las dos.

    Tambien agrega los alias conocidos de _EST_ALIAS_DESCRIPCION_FACTURA para
    (empresa, fase) — variantes de texto reales que no matchean por
    normalizacion estandar pero se confirmaron como el mismo producto. Solo
    se agrega un alias si la clave a la que apunta existe en ESTE catalogo y
    si el texto no coincide ya con algo del catalogo (nunca pisa una colision
    real). Escopeado por (empresa, fase) a proposito — un alias de una fase
    NUNCA se aplica a otra, aunque comparta el mismo numero de clave (bug
    real encontrado en la auditoria de 2026-08-27, ver test de regresion)."""
    resultado: dict = {}
    for c in catalogo:
        norm = _est_normalizar_catalogo(c["descripcion"])
        resultado[norm] = None if norm in resultado else c["clave"]
    claves_catalogo = {c["clave"] for c in catalogo}
    alias_fase = _EST_ALIAS_DESCRIPCION_FACTURA.get((empresa, fase), {})
    for alias_norm, alias_clave in alias_fase.items():
        if alias_clave in claves_catalogo and alias_norm not in resultado:
            resultado[alias_norm] = alias_clave
    return resultado


def _est_revisar_claves_resueltas(conn, empresa: str = None, fase: str = None) -> dict:
    """Issue #25 — aviso pasivo: revisa TODA `facturas.clave_resuelta` guardada
    contra lo que el catalogo y los alias vigentes de su (empresa, fase) dirian
    HOY para esa misma descripcion.

    SOLO LECTURA por contrato: no escribe una sola fila, no corrige nada y no
    bloquea ninguna generacion. Detecta y devuelve; quien mira decide.

    El defecto que cubre: `clave = clave_resuelta or auto_match` le da prioridad
    absoluta y permanente a la resolucion manual, asi que un alias agregado
    DESPUES nunca la revalida. Es lo que dejo 56 conduces / 370 m3 de CAVERNAS
    en la clave 3 ($122) cuando iban en la 2 ($111) — $4,070 de mas, y ademas
    desbordo 114 m3 a la serie PPACT equivocada.

    OJO con la distincion: `estimaciones_generar()` y `_est_clasificar_series()`
    ya manejan la `clave_resuelta` que apunta a una clave que ya NO existe en el
    catalogo (la tratan como no resuelta). Lo que hoy pasa en silencio, y es lo
    que este detector agrega, es la `clave_resuelta` que apunta a una clave
    VALIDA pero distinta de la que el auto-match daria hoy.

    Se agrupa por (empresa, fase, descripcion, clave_resuelta) — el aviso es
    accionable por producto, no por conduce: las 265 resoluciones reales caen en
    5 grupos. Cada grupo cae en exactamente uno de tres desenlaces, que se
    devuelven separados a proposito para no mezclarlos:

      - `discrepan`      el auto-match da una clave VALIDA y distinta de
                         clave_resuelta. Es el caso que dolio: trae las dos
                         claves con su descripcion y su P.U. de catalogo, y los
                         m3 y el dinero que salen segun cual se use.
      - `sin_auto_match` hoy la descripcion no matchea nada (ni catalogo ni
                         alias, o cayo en una colision real que
                         `_est_catalogo_norm_a_clave()` marca None a proposito).
                         La resolucion manual sigue siendo la unica fuente: no
                         es un error, pero conviene poder verlas.
      - `coinciden`      el auto-match da exactamente lo mismo que se resolvio a
                         mano. La resolucion ya es redundante.

    Cada fila lleva ademas `clave_resuelta_obsoleta`: la clave guardada ya no
    existe en el catalogo de su fase. Es ortogonal a los tres desenlaces (puede
    darse tanto con auto-match como sin el) y es el caso borde que el generador
    ya absorbe hoy — se marca igual porque cambia la lectura de la fila: sin
    auto-match Y obsoleta significa que esa factura hoy bloquea la generacion
    hasta que alguien la reasigne a mano.

    El dinero sale del P.U. del CATALOGO, no de `facturas.precio_unitario`: es el
    que `_est_generar_workbook()` escribe en la columna P.U. de REO-01, o sea el
    que termina cobrandose. Queda None si al producto le falta precio.

    `empresa`/`fase` son filtros opcionales e independientes. Una fase sin
    catalogo cargado no se puede evaluar: sus filas caen en `sin_auto_match` y
    `clave_resuelta_obsoleta` queda False (sin catalogo no hay con que afirmar
    que la clave sea obsoleta).
    """
    condiciones = ["clave_resuelta IS NOT NULL", "TRIM(clave_resuelta) <> ''"]
    params: list = []
    if empresa is not None:
        condiciones.append("empresa = ?")
        params.append(empresa)
    if fase is not None:
        condiciones.append("fase = ?")
        params.append(fase)
    filas = conn.execute(
        "SELECT empresa, fase, descripcion, clave_resuelta, id_documento, cantidad "
        f"FROM facturas WHERE {' AND '.join(condiciones)} "
        "ORDER BY empresa, fase, descripcion, clave_resuelta, id_documento",
        params
    ).fetchall()

    grupos: dict = {}
    for f_empresa, f_fase, descripcion, clave_resuelta, id_documento, cantidad in filas:
        g = grupos.setdefault((f_empresa, f_fase, descripcion, clave_resuelta),
                              {"ids": [], "cantidad": 0.0})
        g["ids"].append(id_documento)
        g["cantidad"] += cantidad or 0.0

    cache_catalogo: dict = {}  # (empresa, fase) -> (por_clave, norm_a_clave)

    def _catalogo_de(empresa_fase):
        if empresa_fase not in cache_catalogo:
            cat = _est_catalogo_fase(conn, empresa_fase[0], empresa_fase[1])
            cache_catalogo[empresa_fase] = (
                {c["clave"]: c for c in cat},
                _est_catalogo_norm_a_clave(cat, empresa_fase[0], empresa_fase[1]),
            )
        return cache_catalogo[empresa_fase]

    discrepan, sin_auto_match, coinciden = [], [], []
    for (f_empresa, f_fase, descripcion, clave_resuelta), g in grupos.items():
        por_clave, norm_a_clave = _catalogo_de((f_empresa, f_fase))
        # None es un valor real del mapa (colision de catalogo marcada a
        # proposito) y significa lo mismo que "no matcheo": nunca auto-asignar.
        clave_auto = norm_a_clave.get(_est_normalizar(descripcion))
        if clave_auto not in por_clave:
            clave_auto = None

        prod_resuelta = por_clave.get(clave_resuelta)
        prod_auto = por_clave.get(clave_auto)
        cantidad = g["cantidad"]

        def _importe(prod):
            if prod is None or prod.get("precio_unitario") is None:
                return None
            return round(cantidad * prod["precio_unitario"], 2)

        importe_resuelta, importe_auto = _importe(prod_resuelta), _importe(prod_auto)
        fila = {
            "empresa": f_empresa,
            "fase": f_fase,
            "descripcion": descripcion,
            "facturas": len(g["ids"]),
            "ids": g["ids"],
            "cantidad": round(cantidad, 4),
            "clave_resuelta": clave_resuelta,
            "descripcion_resuelta": prod_resuelta["descripcion"] if prod_resuelta else None,
            "precio_resuelta": prod_resuelta["precio_unitario"] if prod_resuelta else None,
            "importe_resuelta": importe_resuelta,
            "clave_auto": clave_auto,
            "descripcion_auto": prod_auto["descripcion"] if prod_auto else None,
            "precio_auto": prod_auto["precio_unitario"] if prod_auto else None,
            "importe_auto": importe_auto,
            "diferencia": (None if importe_resuelta is None or importe_auto is None
                           else round(importe_resuelta - importe_auto, 2)),
            "clave_resuelta_obsoleta": bool(por_clave) and clave_resuelta not in por_clave,
        }
        if clave_auto is None:
            sin_auto_match.append(fila)
        elif clave_auto == clave_resuelta:
            coinciden.append(fila)
        else:
            discrepan.append(fila)

    def _orden(f):
        return (-abs(f["diferencia"] or 0), -f["cantidad"], f["empresa"] or "", f["fase"] or "")

    discrepan.sort(key=_orden)
    sin_auto_match.sort(key=_orden)
    coinciden.sort(key=_orden)

    return {
        "discrepan": discrepan,
        "sin_auto_match": sin_auto_match,
        "coinciden": coinciden,
        "resumen": {
            "facturas_revisadas": len(filas),
            "grupos": len(grupos),
            "facturas_discrepan": sum(f["facturas"] for f in discrepan),
            "facturas_sin_auto_match": sum(f["facturas"] for f in sin_auto_match),
            "facturas_coinciden": sum(f["facturas"] for f in coinciden),
            "cantidad_discrepan": round(sum(f["cantidad"] for f in discrepan), 4),
            # suma solo de las discrepancias con las dos puntas con precio: un
            # producto sin P.U. no puede sumar 0 como si no hubiera plata en
            # juego, seria mentir por omision. Se cuentan aparte.
            "diferencia_total": round(sum(f["diferencia"] for f in discrepan
                                          if f["diferencia"] is not None), 2),
            "discrepan_sin_precio": sum(1 for f in discrepan if f["diferencia"] is None),
            "claves_obsoletas": sum(
                f["facturas"] for f in (discrepan + sin_auto_match + coinciden)
                if f["clave_resuelta_obsoleta"]),
        },
    }


def _est_cerradas_previas(conn, empresa: str, fase: str, fecha_desde: str):
    """Issue #17 — suma por (clave, serie) de las estimaciones cerradas
    ANTERIORES al periodo pedido (fecha_hasta < fecha_desde, estricto: una
    cerrada que toca el periodo no es "anterior"), y la fecha_hasta mas
    tardia entre ellas (None si no hay ninguna).

    Tolera que la tabla estimacion_cerrada no exista todavia (BD de antes de
    la migracion de este issue, o fixtures minimos de tests): eso equivale a
    "no hay nada cerrado", que reproduce exactamente el comportamiento
    anterior al issue — el acumulado se reconstruye desde el seed replayando
    las facturas del hueco."""
    try:
        filas = conn.execute(
            "SELECT clave, serie, SUM(cantidad), MAX(fecha_hasta) FROM estimacion_cerrada "
            "WHERE empresa = ? AND fase = ? AND fecha_hasta < ? GROUP BY clave, serie",
            (empresa, fase, fecha_desde)
        ).fetchall()
    except sqlite3.OperationalError:
        return {}, None
    sumas, hasta = {}, None
    for clave, serie, total, max_hasta in filas:
        sumas[(clave, serie)] = total or 0.0
        if hasta is None or max_hasta > hasta:
            hasta = max_hasta
    return sumas, hasta


def _est_clasificar_series(conn, empresa: str, fase: str, catalogo: list, fecha_desde: str,
                            fecha_hasta: str | None = None) -> dict:
    """Issue #12 — contratos paralelos (principal vs PPACT) por producto.
    Reemplaza a _est_calcular_acumulado_anterior() (issue #11, borrada).

    Para cada producto del catalogo, calcula el acumulado ANTERIOR (a
    fecha_desde, sin incluirla — todo lo de antes del periodo) de CADA serie
    (principal/ppact). Si se da fecha_hasta, ademas clasifica cada factura de
    "esta estimacion" (fecha_desde a fecha_hasta, AMBAS inclusive — mismo
    criterio BETWEEN que ya usa el resto del proyecto, ej.
    estimaciones_generar()) en la serie que le corresponde.

    Reglas (issue #16, confirmadas por X 2026-08-27 — reemplazan a las del
    issue #12):
    - El LOTE nunca se divide entre series. El lote es el total de facturas
      del producto dentro del periodo [fecha_desde, fecha_hasta]: si
      acumulado_anterior + lote cabe en el tope
      (cantidad_proyecto_principal), TODO el lote va a principal; si no,
      TODO el lote va a PPACT y el acumulado del principal no se toca.
    - El contrato principal NO se cierra nunca: desbordar en un periodo no
      condena a PPACT a los periodos siguientes (el flag 'crossed' pegajoso
      del issue #12 se elimino).
    - Issue #17: el acumulado ANTERIOR arranca de seed + estimaciones
      CERRADAS anteriores al periodo (fecha_hasta < fecha_desde), sumadas
      directo por (clave, serie) desde estimacion_cerrada — las facturas
      cubiertas por esos cierres no se recorren ni se replayean. El "hueco"
      pasa a ser solo lo que quedo DESPUES de la ultima cerrada (o de
      fecha_base si no hay ninguna) y antes de fecha_desde.
    - El hueco restante se calcula factura por factura, sin flag pegajoso:
      cada una va al principal si cabe entera, a PPACT si no, y una
      posterior que quepa vuelve a entrar al principal. Cuando ese hueco
      tiene facturas, el retorno lo avisa (aviso_acumulado_por_factura)
      porque ese calculo NO usa la regla de lote — cerrar la estimacion
      anterior lo evita (issue #17, criterio 10).
    - PPACT no tiene techo.
    - Un producto sin fila serie='ppact' en estimacion_acumulado_base
      empieza su PPACT desde 0 en el momento en que la clasificacion lo
      cruza por primera vez (no hace falta sembrar una base de PPACT para
      productos que todavia no cruzaron nunca).
    - Cada producto acumula SOLO sus propias facturas posteriores a SU
      PROPIA fecha_base (columna "principal") — si en el futuro dos
      productos de la misma fase tienen fecha_base distinta, una factura
      fechada entre la fecha_base mas temprana y la mas tardia NO se cuenta
      dos veces: solo cuenta para el/los producto(s) cuya propia fecha_base
      ya paso.
    - Productos sin ninguna fila en estimacion_acumulado_base (fase sin
      datos sembrados) devuelven 'principal': {'calculado': None, ...},
      'ppact': {'calculado': None, ...} — igual que el issue #11, sin
      cambio de comportamiento para fases no sembradas.
    - Desempate estable: si 2+ facturas del mismo producto comparten
      exactamente la misma fecha, se procesan en orden de id_documento
      (ASC) — determinista, no depende del orden de insercion en la BD.

    Devuelve:
        {"por_clave": {clave: {
            "principal": {"calculado": float|None, "tope": float|None},
            "ppact":     {"calculado": float|None},
        }},
        "facturas_periodo": [(id_documento, clave, serie, fecha, cantidad, precio_unitario, descripcion), ...],
        "sin_resolver": [descripcion, ...],
        "aviso_acumulado_por_factura": None | {"facturas": N}}

    aviso_acumulado_por_factura (issue #16, AC #6): {"facturas": N} cuando
    existen facturas en el hueco fecha_base < fecha < fecha_desde de esta
    (empresa, fase) — N es el TOTAL de facturas en el hueco de toda la fase
    (no por clave: un solo aviso por pantalla aunque toque varias claves).
    None cuando el hueco esta vacio o cuando fecha_hasta es None (sin
    periodo no hay lote, la regla de lote no aplica y el aviso tampoco).
    """
    bases = {}  # clave -> {"principal": (fecha_base, cantidad_base, tope), "ppact": (fecha_base, cantidad_base)}
    for clave, serie, fecha_base, cantidad_base, tope in conn.execute(
        "SELECT clave, serie, fecha_base, cantidad_base, cantidad_proyecto_principal "
        "FROM estimacion_acumulado_base WHERE empresa = ? AND fase = ?", (empresa, fase)
    ).fetchall():
        bases.setdefault(clave, {})[serie] = (fecha_base, cantidad_base, tope) if serie == "principal" else (fecha_base, cantidad_base)

    # Issue #17 — libro mayor: lo ya cerrado ANTES de este periodo entra al
    # acumulado como suma directa (seed + cerradas), y las facturas cubiertas
    # por esos cierres (fecha <= cerradas_hasta) ya no se recorren ni se
    # replayean — el corte del hueco avanza de fecha_base a la fecha_hasta de
    # la ultima cerrada. Con la tabla vacia (o inexistente) todo esto es un
    # no-op y el calculo es identico al de antes del issue (criterio 5).
    cerradas_sumas, cerradas_hasta = _est_cerradas_previas(conn, empresa, fase, fecha_desde)

    resultado = {c["clave"]: {"principal": {"calculado": None, "tope": None}, "ppact": {"calculado": None}} for c in catalogo}
    catalogo_norm_a_clave = _est_catalogo_norm_a_clave(catalogo, empresa, fase)
    catalogo_por_clave = {c["clave"]: c for c in catalogo}

    # CRITICO: el matching/armado de facturas_periodo tiene que pasar SIEMPRE,
    # tenga o no la fase datos en estimacion_acumulado_base — de lo contrario
    # estimaciones_generar() se queda sin facturas para las 8 fases que
    # todavia no tienen PPACT sembrado, rompiendo la generacion para TODAS
    # ellas (bug real encontrado en la 3ra ronda de revision de este spec).
    # Sin ninguna base en toda la fase: se trae el rango de siempre
    # (fecha_desde a fecha_hasta, ambos inclusive, igual que ya hace
    # estimaciones_generar() hoy) y CUALQUIER factura matcheada se clasifica
    # 'principal' sin calculado (None) — comportamiento identico al issue #11.
    fechas_base_principal = [b["principal"][0] for b in bases.values() if "principal" in b]
    if fechas_base_principal:
        fecha_query_desde = min(fechas_base_principal)
        # issue #17: lo cubierto por cierres previos no se consulta siquiera —
        # asi el resultado no depende de las facturas anteriores al corte
        # (criterio 12: borrarlas de la BD no cambia nada)
        if cerradas_hasta is not None and cerradas_hasta > fecha_query_desde:
            fecha_query_desde = cerradas_hasta
        fecha_query_desde_exclusive = True
    else:
        fecha_query_desde = fecha_desde
        fecha_query_desde_exclusive = False
    fecha_limite = fecha_hasta if fecha_hasta else fecha_desde

    condicion_desde = "fecha > ?" if fecha_query_desde_exclusive else "fecha >= ?"
    filas = conn.execute(
        f"SELECT id_documento, descripcion, clave_resuelta, cantidad, precio_unitario, fecha FROM facturas "
        f"WHERE empresa = ? AND fase = ? AND {condicion_desde} AND fecha <= ? ORDER BY fecha ASC, id_documento ASC",
        (empresa, fase, fecha_query_desde, fecha_limite)
    ).fetchall()

    por_clave_facturas: dict[str, list] = {}
    sin_resolver = []
    for id_documento, descripcion, clave_resuelta, cantidad, precio_unitario, fecha in filas:
        # Issue #36 — la prioridad clave_resuelta > auto-match se mantiene,
        # pero solo cuando la guardada sirve. Antes esto era un `or`, y el
        # cortocircuito hacia que una clave_resuelta obsoleta (apunta a una
        # clave que ya no existe en el catalogo) impidiera que el auto-match
        # se consultara siquiera: una factura cuya descripcion matchea
        # perfecto el catalogo de hoy caia igual en sin_resolver.
        auto_match = catalogo_norm_a_clave.get(_est_normalizar(descripcion))
        clave = clave_resuelta if clave_resuelta in catalogo_por_clave else auto_match
        if not clave or clave not in catalogo_por_clave:
            sin_resolver.append(descripcion)
            continue
        por_clave_facturas.setdefault(clave, []).append(
            (id_documento, fecha, cantidad or 0, precio_unitario, descripcion)
        )

    facturas_periodo = []
    facturas_en_hueco = 0  # total de la fase, para aviso_acumulado_por_factura
    for clave in catalogo_por_clave:
        series = bases.get(clave, {})
        if "principal" not in series:
            # producto sin base sembrada: cualquier factura suya en el rango
            # ya matcheada (por_clave_facturas) va entera a 'principal', sin
            # calculado — mismo comportamiento que el issue #11 para fases
            # no sembradas, y necesario para que estimaciones_generar() no
            # se quede sin datos.
            for id_documento, fecha, cantidad, precio_unitario, descripcion in por_clave_facturas.get(clave, []):
                if fecha_hasta is not None and fecha_desde <= fecha:
                    facturas_periodo.append((id_documento, clave, "principal", fecha, cantidad, precio_unitario, descripcion))
            continue
        fecha_base_p, running, tope = series["principal"]
        _, acumulado_ppact = series.get("ppact", (fecha_base_p, 0))
        # fecha_base de la fila 'ppact' es solo metadata informativa (a que
        # fecha corresponde el cantidad_base sembrado) — NO se usa en la
        # clasificacion.
        hay_ppact_sembrado = "ppact" in series
        # issue #17: acumulado = seed + estimaciones cerradas anteriores al
        # periodo, por serie. Un cierre con cantidad en ppact implica que
        # PPACT ya se uso de verdad — se muestra aunque no haya base
        # sembrada de ppact.
        running += cerradas_sumas.get((clave, "principal"), 0.0)
        ppact_cerrado = cerradas_sumas.get((clave, "ppact"), 0.0)
        acumulado_ppact += ppact_cerrado
        # hubo_ppact solo gobierna si ppact.calculado se devuelve como
        # numero o como None (misma semantica de presentacion que el
        # 'crossed or hay_ppact_sembrado' del issue #12) — ya NO es un flag
        # de clasificacion: el contrato principal no se cierra nunca.
        hubo_ppact = (tope is not None and running >= tope) or ppact_cerrado > 0

        # separar "hueco" (fecha_base < fecha < fecha_desde: acumulado
        # anterior, se calcula factura por factura) de "lote" (fecha_desde
        # <= fecha <= fecha_hasta: se decide de una sola vez). Con
        # fecha_hasta None no hay periodo ni lote: todo lo anterior a
        # fecha_desde es hueco y lo que caiga exactamente en fecha_desde se
        # ignora (igual que hoy: el snapshot del acumulado anterior nunca
        # lo incluia y sin periodo tampoco hay facturas_periodo).
        anteriores, lote = [], []
        # issue #17: el corte del hueco es lo ultimo cubierto — la fecha_hasta
        # de la ultima estimacion cerrada si la hay, si no la fecha_base del
        # seed. Lo anterior al corte ya esta contado en seed + cerradas.
        corte = fecha_base_p
        if cerradas_hasta is not None and cerradas_hasta > corte:
            corte = cerradas_hasta
        for f in por_clave_facturas.get(clave, []):
            fecha = f[1]
            # cada factura solo cuenta si es posterior al corte de ESTE
            # producto especifico (no al minimo global) — evita contar dos
            # veces algo que ya esta dentro de cantidad_base (o de una
            # estimacion cerrada) cuando fecha_base difiere entre productos
            if fecha <= corte:
                continue
            if fecha < fecha_desde:
                anteriores.append(f)
            elif fecha_hasta is not None:
                # ya se filtro por fecha <= fecha_hasta en el SELECT
                lote.append(f)

        # 1) acumulado anterior: replay factura por factura SIN flag
        # pegajoso. Cada una va al principal si cabe entera en el tope, a
        # ppact si no — y una posterior que quepa vuelve a entrar al
        # principal (issue #16: desbordar no cierra el contrato). El orden
        # es el del SELECT (fecha ASC, id_documento ASC): con empate de
        # fecha decide id_documento, deterministico.
        for _, _, cantidad, _, _ in anteriores:
            if tope is None or running + cantidad <= tope:
                running += cantidad
            else:
                acumulado_ppact += cantidad
                hubo_ppact = True
        principal_anterior, ppact_anterior = running, acumulado_ppact
        if fecha_hasta is not None:
            facturas_en_hueco += len(anteriores)

        # 2) el lote del periodo se PARTE factura por factura (cambio de
        # regla 2026-09-25, decidido por Axel — reemplaza al "lote entero"
        # del issue #16, que mandaba los 344 m3 del 210 de CAVERNAS a ppact
        # con 262 m3 todavia libres en el principal): en orden cronologico,
        # cada conduce va ENTERO al principal si cabe en el tope; si no
        # cabe, ese conduce va a ppact pero los siguientes mas chicos que
        # si quepan siguen entrando al principal — el mismo replay sin flag
        # pegajoso que ya usaba el hueco (arriba). Un conduce jamas se
        # divide entre series.
        for id_documento, fecha, cantidad, precio_unitario, descripcion in lote:
            if tope is None or running + cantidad <= tope:
                serie_factura = "principal"
                running += cantidad
            else:
                serie_factura = "ppact"
                acumulado_ppact += cantidad
                hubo_ppact = True
            facturas_periodo.append((id_documento, clave, serie_factura, fecha, cantidad, precio_unitario, descripcion))

        resultado[clave]["principal"] = {"calculado": principal_anterior, "tope": tope}
        resultado[clave]["ppact"] = {"calculado": ppact_anterior if (hubo_ppact or hay_ppact_sembrado) else None}

    aviso = {"facturas": facturas_en_hueco} if (fecha_hasta is not None and facturas_en_hueco) else None
    return {"por_clave": resultado, "facturas_periodo": facturas_periodo,
            "sin_resolver": sorted(set(sin_resolver)),
            "aviso_acumulado_por_factura": aviso}


def _est_avisos_cierre(conn, empresa: str, fase: str, numero_estimacion: str,
                       fecha_desde: str, fecha_hasta: str) -> list[dict]:
    """Issue #17 — avisos (no bloqueantes) antes de cerrar una estimacion.
    Chequeo a nivel (empresa, fase), nunca por clave:

    - "re_cierre": ya existe una cerrada con ESTE mismo numero_estimacion.
      `_est_cerrar_estimacion()` hace DELETE + INSERT, asi que re-cerrar
      reemplaza las cantidades de un documento que puede estar entregado, y
      la clasificacion de hoy no tiene por que dar lo mismo que la del dia
      del cierre (alias nuevos, facturas aprobadas despues, catalogo
      corregido). Antes este caso no producia NINGUN aviso: el chequeo de
      solapamiento excluye el propio numero a proposito y el de hueco
      tambien, asi que la lista salia vacia y la ruta ejecutaba el
      DELETE + INSERT sin pedir confirmacion. El aviso trae lo que se va a
      reemplazar (rango, cuando se cerro, filas y cantidad) para que la
      decision se tome viendo el numero y no de memoria. La correccion
      legitima sigue siendo posible: confirmar_aviso, o /reabrir y cerrar
      de nuevo.
    - El solapamiento con OTRO numero ya no es un aviso: es un bloqueo
      (issue #96, ver _est_cierres_solapados()).
    - "hueco": fecha_desde es posterior al dia siguiente de lo ultimo
      cubierto. Lo ultimo cubierto es la fecha_hasta mas tardia de las
      cerradas (excluyendo el propio numero); para el primer cierre de la
      fase, la fecha_base del seed. Sin cerradas ni seed no hay referencia
      y no se avisa hueco.

    Los avisos permiten continuar con confirmacion explicita (la empresa
    puede haber salteado un periodo legitimamente) — el 409/confirmar_aviso
    vive en la ruta, no aca."""
    avisos = []
    # va primero a proposito: es el mas grave de los tres — los otros dos
    # avisan sobre el calendario, este sobre pisar un documento ya emitido
    previa = conn.execute(
        "SELECT MIN(fecha_desde), MAX(fecha_hasta), MAX(cerrada_en), COUNT(*), "
        "COALESCE(SUM(cantidad), 0) FROM estimacion_cerrada "
        "WHERE empresa = ? AND fase = ? AND numero_estimacion = ?",
        (empresa, fase, numero_estimacion)
    ).fetchone()
    if previa and previa[3]:
        avisos.append({"tipo": "re_cierre", "numero_estimacion": numero_estimacion,
                       "fecha_desde": previa[0], "fecha_hasta": previa[1],
                       "cerrada_en": previa[2], "filas": previa[3],
                       "cantidad_total": previa[4]})
    ultima_cubierta = conn.execute(
        "SELECT MAX(fecha_hasta) FROM estimacion_cerrada "
        "WHERE empresa = ? AND fase = ? AND numero_estimacion != ?",
        (empresa, fase, numero_estimacion)
    ).fetchone()[0]
    if ultima_cubierta is None:
        ultima_cubierta = conn.execute(
            "SELECT MAX(fecha_base) FROM estimacion_acumulado_base WHERE empresa = ? AND fase = ?",
            (empresa, fase)
        ).fetchone()[0]
    if ultima_cubierta is not None:
        desde_esperado = (date.fromisoformat(ultima_cubierta) + timedelta(days=1)).isoformat()
        if fecha_desde > desde_esperado:
            avisos.append({"tipo": "hueco", "ultima_cubierta": ultima_cubierta,
                           "desde_esperado": desde_esperado})
    return avisos


def _est_cierres_solapados(conn, empresa: str, fase: str, numero_estimacion: str,
                           fecha_desde: str, fecha_hasta: str) -> list[dict]:
    """Issue #96 — las estimaciones cerradas de esa (empresa, fase), con OTRO
    numero, cuyo rango comparte al menos un dia con el pedido (ambos extremos
    inclusive). El propio numero queda fuera: re-cerrarlo es "re_cierre", que
    reemplaza y avisa.

    Era un aviso confirmable y paso a ser bloqueo porque cualquier dia en
    comun se cuenta DOS veces: _est_cerradas_previas() suma todo lo cerrado
    antes del periodo pedido. El 2026-10-05 CAVERNAS, MACAO 2 y CEDIS
    quedaron con 17/08 -> 16/09 cerrado dos veces —el 2026-10-01 con numero
    `2026-08-17_2026-09-16` y ese dia como N40/N40/N20— y el documento
    siguiente habria arrancado con el acumulado duplicado (MACAO 2 clave 8:
    7.913,5 m3 de mas). Corregir un numero sigue siendo posible: /reabrir el
    viejo y cerrar con el nuevo."""
    filas = conn.execute(
        "SELECT DISTINCT numero_estimacion, fecha_desde, fecha_hasta FROM estimacion_cerrada "
        "WHERE empresa = ? AND fase = ? AND numero_estimacion != ? "
        "AND fecha_desde <= ? AND fecha_hasta >= ? ORDER BY fecha_desde, numero_estimacion",
        (empresa, fase, numero_estimacion, fecha_hasta, fecha_desde)
    ).fetchall()
    return [{"numero_estimacion": n, "fecha_desde": d, "fecha_hasta": h} for n, d, h in filas]


def _est_bloquear_si_solapa(conn, empresa, fase, numero_estimacion, fecha_desde, fecha_hasta):
    solapados = _est_cierres_solapados(conn, empresa, fase, numero_estimacion,
                                       fecha_desde, fecha_hasta)
    if solapados:
        raise HTTPException(status_code=400, detail={
            "error": "cierre_solapado", "detalle": solapados})


def _est_pendientes_del_periodo(conn, empresa: str, fase: str,
                                fecha_desde: str, fecha_hasta: str) -> list[dict]:
    """Issue #38 — los pendientes por revision de esa (empresa, fase) cuya
    fecha cae DENTRO del periodo, ambos extremos inclusive (mismo criterio
    BETWEEN que usa todo el resto del proyecto).

    Cerrar con uno de estos vivo lo pierde para siempre: no entra al libro
    mayor de este periodo (no esta en facturas) y queda detras del corte, asi
    que ningun periodo futuro lo replaya. Ya paso — el cierre de MACAO 2 del
    17-jul al 16-ago se llevo 4,5 m3 que hoy no se le facturan a nadie.

    Un pendiente con fecha NULL no matchea el BETWEEN y no bloquea: sin fecha
    no se puede afirmar que sea del periodo, el mismo lado conservador que
    toma cuenta_para_estimaciones. Uno con fecha fuera del periodo tampoco
    bloquea — el alcance es el periodo que se esta cerrando, no el backlog.

    Orden fijo por (fecha, id_documento): el detalle del 400 se compara
    entero en los tests y sin ORDER BY seria intermitente. Mismo criterio de
    desempate que _est_clasificar_series().

    Tolera que la tabla no exista (BD armada a mano en un test): sin tabla no
    hay pendientes que proteger, igual que _est_cerradas_previas()."""
    try:
        filas = conn.execute(
            "SELECT id_documento, fecha, cantidad, motivo, archivo_pdf "
            "FROM pendientes_revision "
            "WHERE empresa = ? AND fase = ? AND fecha BETWEEN ? AND ? "
            "ORDER BY fecha, id_documento",
            (empresa, fase, fecha_desde, fecha_hasta)
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [{"id_documento": id_documento, "fecha": fecha, "cantidad": cantidad,
             "motivo": motivo, "archivo_pdf": archivo_pdf}
            for id_documento, fecha, cantidad, motivo, archivo_pdf in filas]


def _est_cerrar_estimacion(conn, empresa: str, fase: str, catalogo: list,
                           numero_estimacion: str, fecha_desde: str, fecha_hasta: str) -> int:
    """Issue #17 — cierra una estimacion: registra en estimacion_cerrada, por
    (clave, serie), la suma de las facturas_periodo que clasifico
    _est_clasificar_series() para ese periodo. Solo filas con cantidad > 0.

    Es DELETE + INSERT dentro de BEGIN IMMEDIATE, NO un INSERT OR REPLACE:
    la primary key sola no alcanza — si al re-cerrar una clave quedo en
    cero, ya no se inserta fila para ella y con OR REPLACE la fila vieja
    sobreviviria, dejando el acumulado inflado para siempre (criterio 11).
    Requiere una conexion en autocommit (isolation_level=None) para que el
    BEGIN IMMEDIATE explicito controle la transaccion completa.

    Devuelve la cantidad de filas insertadas. No decide avisos ni
    confirmaciones (eso es _est_avisos_cierre() + la ruta).

    Issue #38 — los dos bloqueos y TODAS las lecturas que los deciden corren
    DENTRO del BEGIN IMMEDIATE, no antes. Chequear afuera deja una carrera
    real: entre el chequeo y el INSERT alguien puede aprobar un pendiente (o
    mover una factura a pendientes_revision) y el cierre escribe igual, con
    numeros que ya no son los que se validaron. Con las lecturas bajo el
    mismo lock, cualquier otra conexion que intente escribir mientras tanto
    encuentra la base bloqueada. Los dos bloqueos hacen ROLLBACK antes de
    levantar la HTTPException."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        # issue #96: bloqueante, igual que los pendientes — y bajo el mismo
        # lock, para que nadie cierre el mismo rango entre el chequeo y el INSERT
        _est_bloquear_si_solapa(conn, empresa, fase, numero_estimacion, fecha_desde, fecha_hasta)
        pendientes = _est_pendientes_del_periodo(conn, empresa, fase, fecha_desde, fecha_hasta)
        if pendientes:
            # issue #38: bloqueante, NO un aviso confirmable — cerrar con un
            # pendiente del periodo vivo lo deja fuera del libro mayor Y
            # detras del corte, o sea perdido para siempre. La regla es que
            # no queda ningun conduce para la proxima estimacion: se aprueba
            # o se descarta ANTES de cerrar.
            raise HTTPException(status_code=400, detail={
                "error": "pendientes_en_el_periodo", "detalle": pendientes})
        clasificacion = _est_clasificar_series(conn, empresa, fase, catalogo, fecha_desde, fecha_hasta)
        if clasificacion["sin_resolver"]:
            # cerrar con facturas sin resolver las dejaria fuera del libro mayor
            # para siempre (el proximo periodo ya no las replaya) — mismo bloqueo
            # que /generar, se resuelven primero
            raise HTTPException(status_code=400, detail={
                "error": "facturas_sin_resolver", "detalle": clasificacion["sin_resolver"]})
        sumas: dict[tuple[str, str], float] = {}
        for _, clave, serie, _, cantidad, _, _ in clasificacion["facturas_periodo"]:
            sumas[(clave, serie)] = sumas.get((clave, serie), 0.0) + (cantidad or 0.0)
        cerrada_en = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "DELETE FROM estimacion_cerrada WHERE empresa = ? AND fase = ? AND numero_estimacion = ?",
            (empresa, fase, numero_estimacion)
        )
        insertadas = 0
        for (clave, serie), cantidad in sorted(sumas.items()):
            if cantidad <= 0:
                continue
            conn.execute(
                "INSERT INTO estimacion_cerrada "
                "(empresa, fase, clave, serie, numero_estimacion, fecha_desde, fecha_hasta, cantidad, cerrada_en) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (empresa, fase, clave, serie, numero_estimacion, fecha_desde, fecha_hasta, cantidad, cerrada_en)
            )
            insertadas += 1
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return insertadas


def _est_catalogo_fase(conn, empresa: str, fase: str):
    rows = conn.execute(
        "SELECT clave, descripcion, precio_unitario, orden FROM catalogo_estimacion "
        "WHERE empresa = ? AND fase = ? ORDER BY orden",
        (empresa, fase)
    ).fetchall()
    return [{"clave": r[0], "descripcion": r[1], "precio_unitario": r[2], "orden": r[3]} for r in rows]


def _est_vista_previa(conn, empresa: str, fase: str, fecha_desde: str, fecha_hasta: str):
    catalogo = _est_catalogo_fase(conn, empresa, fase)
    if not catalogo:
        raise HTTPException(status_code=404, detail="catalogo_no_definido")
    _est_plantilla_de_fase(empresa, fase, catalogo)  # valida plantilla/sincronizacion temprano

    grupos = conn.execute(
        "SELECT descripcion, COUNT(*), SUM(cantidad) FROM facturas "
        "WHERE empresa = ? AND fase = ? AND fecha BETWEEN ? AND ? "
        "GROUP BY descripcion",
        (empresa, fase, fecha_desde, fecha_hasta)
    ).fetchall()

    catalogo_norm_a_clave = _est_catalogo_norm_a_clave(catalogo, empresa, fase)
    catalogo_por_clave = {c["clave"]: c for c in catalogo}

    resultado_catalogo = {c["clave"]: {**c, "facturas_matcheadas": None} for c in catalogo}
    sin_match = []
    for desc, count, suma in grupos:
        clave = catalogo_norm_a_clave.get(_est_normalizar(desc))
        c = catalogo_por_clave.get(clave) if clave else None
        if c:
            resultado_catalogo[c["clave"]]["facturas_matcheadas"] = {
                "descripcion_factura": desc, "cantidad_facturas": count, "cantidad_total": suma
            }
        else:
            sin_match.append({"descripcion": desc, "cantidad_facturas": count, "cantidad_total": suma})

    clasificacion = _est_clasificar_series(conn, empresa, fase, catalogo, fecha_desde, fecha_hasta)
    for clave, info in clasificacion["por_clave"].items():
        resultado_catalogo[clave]["principal"] = info["principal"]
        resultado_catalogo[clave]["ppact"] = info["ppact"]

    facturas_periodo = [
        {
            "id_documento": id_documento, "clave": clave, "serie": serie,
            "fecha": fecha, "cantidad": cantidad, "precio_unitario": precio_unitario,
            "descripcion": descripcion,
        }
        for id_documento, clave, serie, fecha, cantidad, precio_unitario, descripcion in clasificacion["facturas_periodo"]
    ]

    return {
        "catalogo": [resultado_catalogo[c["clave"]] for c in catalogo],
        "sin_match": sin_match,
        "facturas_periodo": facturas_periodo,
        "sin_resolver": clasificacion["sin_resolver"],
        # issue #16 AC #6 — None o {"facturas": N}: hay N facturas en el
        # hueco fecha_base..fecha_desde cuyo acumulado se calculo factura
        # por factura (no con la regla de lote)
        "aviso_acumulado_por_factura": clasificacion["aviso_acumulado_por_factura"],
    }

def _est_slug(texto: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", texto.strip().upper()).strip("_")


_FOOTER_TAG_REGEX = re.compile(
    r"(<(?:odd|even|first)(?:Header|Footer)>)(.*?)(</(?:odd|even|first)(?:Header|Footer)>)",
    re.DOTALL,
)


def _est_arreglar_saltos_footer(ruta_xlsx):
    """Parchea el .xlsx YA GUARDADO reemplazando el escape _x000a_ (salto de
    linea de Excel dentro de header/footer) por un salto de linea real,
    solo dentro de los nodos <oddHeader>/<oddFooter>/etc. — issue #6,
    hallazgo #2.

    No se puede resolver seteando ws.oddFooter.center.text = "...".replace()
    antes de wb.save() como en principio propone el issue: openpyxl ya
    decodifica _x000a_ a "\n" al CARGAR el workbook (unescape() en
    HeaderFooterItem.from_tree), asi que ese texto en memoria nunca
    contiene el string literal "_x000a_" para reemplazar — y al guardar,
    HeaderFooterItem.__str__() vuelve a escapar cualquier "\n" a _x000a_
    sin excepcion (openpyxl.utils.escape.escape(), confirmado leyendo el
    codigo fuente). Cualquier "\n" que pongamos via la API publica termina
    re-escapado igual en el XML de salida — por eso el parche va sobre el
    XML crudo ya guardado, despues de wb.save(), no sobre el objeto Python."""
    with zipfile.ZipFile(ruta_xlsx, "r") as zin:
        entries = []
        for item in zin.infolist():
            data = zin.read(item.filename)
            if (item.filename.startswith("xl/worksheets/") and item.filename.endswith(".xml")
                    and b"_x000a_" in data):
                texto = data.decode("utf-8")
                texto = _FOOTER_TAG_REGEX.sub(
                    lambda m: m.group(1) + m.group(2).replace("_x000a_", "\n") + m.group(3),
                    texto,
                )
                data = texto.encode("utf-8")
            entries.append((item, data))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for item, data in entries:
            zout.writestr(item, data)
    with open(ruta_xlsx, "wb") as f:
        f.write(buf.getvalue())


# ═══ Anexar los conduces escaneados al PDF de la estimacion ═══
#
# El documento que la empresa entrega no es solo la planilla: el PDF del
# cliente trae DESPUES de las hojas la foto de cada conduce, una por pagina.
# Medido sobre EST_DOMICEM_MACAO_II_..._N33: 1.291 paginas, de las cuales 48
# son el documento y 1.243 son escaneos, contra 19 imagenes en el .xlsx del
# mismo documento. Sin esto el PDF que generamos sale sin el respaldo.
#
# El mapeo NO hay que adivinarlo: `facturas.archivo_pdf` ya guarda el nombre
# del escaneo de cada conduce (`06-01-M8-12024.pdf` <-> `M800012024`).

# De donde salen los escaneos. Se aceptan varias fuentes porque los lotes
# llegan de a uno (Puente 1, Puente 2, ...) y conviene poder soltar el
# siguiente sin tocar codigo: cada .zip que aparezca en conduces/archivos/ y
# cada .pdf suelto en conduces/archivos/escaneos/ entran solos al indice.
#
# La tercera fuente es EST_PROCESADAS (`estimaciones/facturas/procesadas/`), el
# respaldo que el propio sistema deja al importar: `importar_puente.py` desde
# el 2026-08-24 y el website al incorporar validos. Faltaba, y el 2026-09-25
# costo 29 paginas ESCANEO NO DISPONIBLE en el principal de MACAO 2 y otras 29
# distintas en su PPACT, con los 58 archivos existiendo ahi. `secuencia.py` no
# lo detecta porque reconcilia por NUMERO de conduce y este indice mapea por
# NOMBRE de archivo: son dos controles sobre fuentes distintas, y el
# incompleto era este.
EST_ESCANEOS_DIR = os.path.join(BASE_DIR, "conduces", "archivos")
EST_ESCANEOS_SUELTOS = os.path.join(EST_ESCANEOS_DIR, "escaneos")


def _est_indice_escaneos(directorio: str | None = None,
                         procesadas: str | None = None) -> dict:
    """Mapea nombre de archivo -> donde esta el escaneo de ese conduce.

    El valor es `(None, ruta)` para un PDF en disco —suelto o de procesadas/— y
    `(ruta_zip, nombre_interno)` para uno adentro de un zip.

    Precedencia, de menor a mayor: zip, procesadas/, suelto.

    - El zip le gana a procesadas/ **a proposito**: los bytes son los mismos
      (`importar_puente.py` escribe el `zf.read()` tal cual, sin rotar ni
      reescribir), asi que procesadas/ solo llena huecos y ningun escaneo que
      hoy resuelve cambia de fuente.
    - El suelto sigue ganandole a todo: es el punto de extension para dejar una
      version mejor escaneada.

    Inyectar `directorio` apaga la fuente real de procesadas/ salvo que se pase
    `procesadas` explicito. Es para los tests: un fixture con su propio arbol
    no tiene por que leer los PDFs de produccion.

    Nunca revienta: un zip corrupto o un directorio ausente se saltea y se
    loguea, porque esto corre dentro de una generacion que ya tiene el .xlsx
    guardado y no se puede tirar abajo por un archivo.
    """
    base = directorio or EST_ESCANEOS_DIR
    if procesadas is None and directorio is None:
        procesadas = EST_PROCESADAS
    indice: dict[str, tuple] = {}

    if os.path.isdir(base):
        for nombre in sorted(os.listdir(base)):
            if not nombre.lower().endswith(".zip"):
                continue
            ruta_zip = os.path.join(base, nombre)
            try:
                with zipfile.ZipFile(ruta_zip) as zf:
                    for interno in zf.namelist():
                        if interno.lower().endswith(".pdf"):
                            indice.setdefault(os.path.basename(interno), (ruta_zip, interno))
            except Exception:
                print(f"[estimaciones] escaneos: no se pudo leer {ruta_zip}, se saltea")
                traceback.print_exc()
    else:
        # Aviso y se sigue: procesadas/ es una fuente aparte y puede alcanzar
        # sola. Antes esto era un `return` y dejaba el indice vacio.
        print(f"[estimaciones] escaneos: no existe el directorio {base}")

    if procesadas and os.path.isdir(procesadas):
        for nombre in sorted(os.listdir(procesadas)):
            if nombre.lower().endswith(".pdf"):
                indice.setdefault(nombre, (None, os.path.join(procesadas, nombre)))

    sueltos = os.path.join(base, "escaneos")
    if os.path.isdir(sueltos):
        for nombre in sorted(os.listdir(sueltos)):
            if nombre.lower().endswith(".pdf"):
                indice[nombre] = (None, os.path.join(sueltos, nombre))  # pisa a los dos a proposito

    return indice


def _est_orden_de_anexado(catalogo, facturas_por_clave) -> list:
    """Los conduces en el orden en que van al PDF: por clave siguiendo el
    catalogo, y adentro de cada clave por fecha y numero de documento.

    Se itera `catalogo` tal cual viene porque ya esta en orden de renglon.
    OJO (misma trampa que el REO): `orden` es la posicion fisica y `clave` es
    la etiqueta, y no son intercambiables — aca `clave` se usa SOLO como llave
    del diccionario, nunca para ordenar.
    """
    salida = []
    for c in catalogo:
        facturas = facturas_por_clave.get(c["clave"]) or []
        for f in sorted(facturas, key=lambda x: (x.get("fecha") or "", x.get("id_documento") or "")):
            salida.append((c["clave"], f.get("id_documento"), f.get("archivo_pdf")))
    return salida


def _est_pagina_faltante(doc, id_documento: str, archivo: str | None):
    """Deja constancia visible de un conduce cuyo escaneo no aparecio.

    Se escribe una pagina en vez de saltearlo en silencio, por la misma razon
    que una fila sin precio entra avisando y no en $0: el documento del cliente
    tiene una foto por conduce, asi que una ausencia muda se lee como si el
    conduce no existiera. Con la pagina, el hueco se ve antes de entregar.
    """
    pagina = doc.new_page()
    texto = (
        "ESCANEO NO DISPONIBLE\n\n"
        f"Conduce: {id_documento or '(sin numero)'}\n"
        f"Archivo esperado: {archivo or '(la factura no tiene archivo_pdf)'}\n\n"
        "El conduce esta registrado y contabilizado en la estimacion; lo que\n"
        "falta es la imagen del papel. Ver HANDOFF.md, \"Los escaneos de un\n"
        "lote importado pueden no existir\"."
    )
    pagina.insert_textbox(fitz.Rect(56, 90, pagina.rect.width - 56, 380),
                          texto, fontsize=11, fontname="helv", align=0)


def _est_anexar_escaneos(ruta_pdf: str, catalogo, facturas_por_clave,
                         indice: dict | None = None,
                         empresa: str | None = None) -> dict:
    """Anexa al PDF ya convertido la foto de cada conduce de la estimacion.

    Devuelve el parte: cuantos se anexaron, cuantos faltaron y cuales. Nunca
    propaga una excepcion — el .xlsx y el .pdf ya existen y valen por si
    mismos, asi que un fallo acá degrada el resultado pero no lo pierde. Esa
    es la misma politica de `_est_convertir_a_pdf()`.
    """
    parte = {"total": 0, "anexados": 0, "faltantes": [], "sin_referencia": 0, "error": None}
    conduces = _est_orden_de_anexado(catalogo, facturas_por_clave)
    parte["total"] = len(conduces)
    if not conduces:
        return parte

    # "no se que archivo buscar" NO es lo mismo que "se cual y no esta", y la
    # diferencia decide si va una pagina de aviso. Una factura sin
    # `archivo_pdf` (una BD que no registra el escaneo) no puede generar un
    # aviso util: no hay nada que nombrar. Se cuenta aparte y no se anexa
    # nada. Si NINGUNA lo tiene, el PDF no se toca — asi una estimacion sobre
    # una BD que no lleva escaneos sale exactamente igual que antes.
    parte["sin_referencia"] = sum(1 for _, _, archivo in conduces if not archivo)
    if parte["sin_referencia"] == len(conduces):
        parte["error"] = "ninguna factura del periodo tiene archivo_pdf"
        return parte

    if indice is None:
        indice = _est_indice_escaneos()
    if not indice:
        parte["error"] = "no se encontro ninguna fuente de escaneos"
        print(f"[estimaciones] escaneos: {parte['error']}, el PDF sale sin conduces anexados")
        return parte

    tmp = ruta_pdf + ".tmp"
    try:
        doc = fitz.open(ruta_pdf)
        try:
            # 2026-09-25 (pedido de Axel) — los escaneos van intercalados:
            # detras de la hoja RGO (el listado) de su propia clave, en vez
            # de todos juntos al final. CEO/REO/RCO/RFO no se mueven. Si los
            # bloques RGO del PDF no se pueden aparear con las claves
            # (cantidad distinta, titulo que cambio), se degrada al
            # comportamiento anterior — todo al final — avisando al log.
            grupos = []  # [(clave, [(id_documento, archivo), ...])] en orden de catalogo
            for clave, id_documento, archivo in conduces:
                if not grupos or grupos[-1][0] != clave:
                    grupos.append((clave, []))
                grupos[-1][1].append((id_documento, archivo))

            # cada hoja RGO arranca con su pagina "RESUMEN DE GENERADORES"
            # (titulo con letras espaciadas, por eso se colapsa el texto).
            # OJO: las RCO/RFO TAMBIEN traen ese texto en su encabezado — se
            # distinguen porque sus paginas arrancan con el nombre de hoja
            # ("CD-COAF-...") y las paginas RGO no (medido el 2026-09-25 en
            # un documento real: sin este filtro daba 6 bloques para 2 RGO).
            inicios = []
            for i in range(doc.page_count):
                t = doc[i].get_text()
                if ("RESUMENDEGENERADORES" in t.replace(" ", "").upper()
                        and not t.lstrip().startswith("CD-COAF-")):
                    inicios.append(i)
            fin_reporte = doc.page_count
            if inicios:
                # el bloque RGO termina donde arranca la primera hoja RCO/RFO
                for i in range(inicios[-1] + 1, doc.page_count):
                    if doc[i].get_text().lstrip().startswith("CD-COAF-"):
                        fin_reporte = i
                        break

            # 2026-09-25 (pedido de Axel) — logo en CADA bloque de 40: las
            # paginas 2+ de una RGO arrancan directo con la banda
            # PARTIDA/CLAVE (no hay espacio de celda como en la pagina 1),
            # asi que su logo se estampa DIRECTO sobre el PDF, en el margen
            # superior derecho del papel, alineado al borde real de la
            # tabla de esa pagina (el maximo X de sus lineas dibujadas).
            if empresa and inicios:
                archivo_logo = EST_LOGO_RGO_POR_EMPRESA.get(empresa)
                ruta_logo = (os.path.join(EST_LOGOS_DIR, archivo_logo)
                             if archivo_logo else None)
                if ruta_logo and os.path.exists(ruta_logo):
                    try:
                        with fitz.open(ruta_logo) as im_logo:
                            proporcion = im_logo[0].rect.height / im_logo[0].rect.width
                        ancho_pt = 68.0
                        alto_pt = ancho_pt * proporcion
                        for i in range(inicios[0], fin_reporte):
                            if i in inicios:
                                continue  # pagina 1 del bloque: ya trae el suyo
                            pagina = doc[i]
                            bordes = [d["rect"].x1 for d in pagina.get_drawings()]
                            x_der = max(bordes) if bordes else pagina.rect.width - 62
                            pagina.insert_image(
                                fitz.Rect(x_der - ancho_pt, 66 - alto_pt, x_der, 66),
                                filename=ruta_logo,
                            )
                    except Exception:
                        print("[estimaciones] escaneos: no se pudo estampar el "
                              "logo de bloque en el PDF — los bloques salen sin logo")
                        traceback.print_exc()

            def _sub_doc(filas):
                """Arma un doc con los escaneos de una clave, en su orden."""
                sub = fitz.open()
                for id_documento, archivo in filas:
                    if not archivo:
                        continue  # ya contado en sin_referencia
                    ubicacion = indice.get(os.path.basename(archivo))
                    if ubicacion is None:
                        parte["faltantes"].append(id_documento)
                        _est_pagina_faltante(sub, id_documento, archivo)
                        continue
                    ruta_zip, interno = ubicacion
                    try:
                        if ruta_zip is None:
                            with open(interno, "rb") as f:
                                datos = f.read()
                        else:
                            with zipfile.ZipFile(ruta_zip) as zf:
                                datos = zf.read(interno)
                        with fitz.open(stream=datos, filetype="pdf") as src:
                            sub.insert_pdf(src)
                        parte["anexados"] += 1
                    except Exception:
                        # un escaneo ilegible no puede tumbar los otros 1.242
                        parte["faltantes"].append(id_documento)
                        _est_pagina_faltante(sub, id_documento, archivo)
                        print(f"[estimaciones] escaneos: {archivo} no se pudo anexar")
                        traceback.print_exc()
                return sub

            # los sub-docs se arman en orden de catalogo (el parte queda igual
            # que siempre) y se insertan de atras hacia adelante para que los
            # indices de insercion no se corran
            subs = [_sub_doc(filas) for _clave, filas in grupos]
            intercalar = bool(grupos) and len(inicios) == len(grupos)
            if not intercalar and grupos:
                print("[estimaciones] escaneos: no se pudieron aparear los bloques "
                      f"RGO ({len(inicios)}) con las claves con entregas "
                      f"({len(grupos)}); los escaneos van todos al final")
            if intercalar:
                for k in range(len(subs) - 1, -1, -1):
                    if subs[k].page_count:
                        tope = inicios[k + 1] if k + 1 < len(inicios) else fin_reporte
                        doc.insert_pdf(subs[k], start_at=tope)
            else:
                for sub in subs:
                    if sub.page_count:
                        doc.insert_pdf(sub)
            for s in subs:
                s.close()
            doc.save(tmp, deflate=True, garbage=3)
        finally:
            doc.close()
        os.replace(tmp, ruta_pdf)
    except Exception:
        parte["error"] = "fallo al anexar; el PDF queda sin los conduces"
        traceback.print_exc()
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        return parte

    if parte["faltantes"] or parte["sin_referencia"]:
        print(f"[estimaciones] escaneos: {parte['anexados']}/{parte['total']} anexados, "
              f"{len(parte['faltantes'])} sin imagen (cada uno con su pagina de aviso), "
              f"{parte['sin_referencia']} sin archivo_pdf en la BD")
    return parte


def _est_nombre_entregable(empresa: str, fase_slug: str, serie: str,
                           fecha_desde: str, fecha_hasta: str) -> str:
    """El nombre del .xlsx que se entrega. Issue #83.

    Antes era `EST_{empresa}_{fase}_{desde}_{hasta}_{YYYYmmdd_HHMMSS}.xlsx`, y
    eso **perdia documentos en silencio**: la serie no estaba en el nombre y el
    timestamp tenia resolucion de un segundo, asi que generar el `principal` y
    el `ppact` del mismo periodo —que es el par que se genera uno detras del
    otro— escribia dos veces el MISMO archivo y el segundo pisaba al primero.
    Medido el 2026-09-30: los dos `download_url` distintos apuntaban al mismo
    .xlsx, y el que la API ofrecia como ppact traia el OC del principal.

    En produccion no mordia porque LibreOffice mete segundos entre una
    generacion y la siguiente; sin soffice —el runner de CI— las dos caen en el
    mismo segundo. O sea que lo que parecia un test flaky era el defecto.

    Tres cosas lo cierran:

    - **La serie va en el nombre**, en mayuscula como la escribe el cliente en
      sus propios archivos (`..._PPACT_N06_...`).
    - **Milisegundos** en el timestamp, que es lo que hace improbable el choque
      entre dos generaciones de la MISMA serie.
    - Y un sufijo `_2`, `_3`... si el nombre ya existe, que es lo que lo hace
      imposible en vez de improbable. Alcanza porque el caso real son dos
      pedidos **secuenciales**: cuando arranca el segundo, el archivo del
      primero ya esta en disco. Bajo concurrencia real seguiria siendo TOCTOU,
      pero no la hay: el auth es un token compartido de un solo usuario y la
      generacion es sincronica.
    """
    _exigir_fechas_iso(fecha_desde, fecha_hasta)
    ahora = datetime.now()
    marca = ahora.strftime("%Y%m%d_%H%M%S") + f"_{ahora.microsecond // 1000:03d}"
    base = (f"EST_{empresa}_{fase_slug}_{serie.upper()}"
            f"_{fecha_desde}_{fecha_hasta}_{marca}")
    nombre = base + ".xlsx"
    sufijo = 1
    while os.path.exists(os.path.join(EST_REPORTES_DIR, nombre)):
        sufijo += 1
        nombre = f"{base}_{sufijo}.xlsx"
    return nombre


def _est_convertir_a_pdf(ruta_xlsx, nombre_xlsx):
    """Convierte el .xlsx recien guardado a PDF con LibreOffice headless
    (mismo binario que tests/test_calculo_estimacion.py y
    tests/test_rgo_capacidad_dinamica.py ya usan para forzar recalculo
    real). Nunca revienta la generacion: el Excel ya quedo guardado con
    exito antes de llamar esta funcion, asi que cualquier fallo (soffice no
    instalado, timeout, returncode != 0, o el .pdf ausente en disco pese a
    returncode == 0) se loguea y devuelve None en vez de propagar."""
    if not EST_SOFFICE:
        print("[estimaciones] conversion a PDF omitida: LibreOffice (soffice) no esta instalado")
        return None

    nombre_pdf = os.path.splitext(nombre_xlsx)[0] + ".pdf"
    ruta_pdf = os.path.join(EST_REPORTES_DIR, nombre_pdf)
    try:
        resultado = subprocess.run(
            [EST_SOFFICE, "--headless", "--convert-to", "pdf", "--outdir", EST_REPORTES_DIR, ruta_xlsx],
            capture_output=True, timeout=60,
        )
        if resultado.returncode != 0:
            print(f"[estimaciones] conversion a PDF fallo (returncode={resultado.returncode}): "
                  f"{resultado.stderr!r}")
            return None
        if not os.path.exists(ruta_pdf):
            print(f"[estimaciones] conversion a PDF: soffice devolvio returncode 0 pero "
                  f"{ruta_pdf} no existe")
            return None
        return nombre_pdf
    except Exception:
        traceback.print_exc()
        return None


def _est_generar_workbook(ruta_plantilla, req, catalogo, productos_por_clave, facturas_por_clave):
    """Arma y guarda el .xlsx — extraido de estimaciones_generar() para
    poder correrlo con asyncio.to_thread() (ver comentario en el caller)."""
    wb = openpyxl.load_workbook(ruta_plantilla, data_only=False)
    ws_reo = wb["CD-COAF-REO-01"]
    ws_rgo_plantilla = wb["CD-COAF-RGO-PLANTILLA"]

    # Issue #33 — el bloque de firma de la RGO viene cableado a la fila
    # 37/38 de REO-01, que solo es la fila correcta en 2 de las 9 fases. Se
    # reescribe con el texto real ANTES de clonar la hoja, asi lo heredan
    # todas las RGO y todas las paginas del camino paginado.
    _est_escribir_firma_rgo(ws_rgo_plantilla, ws_reo, EST_CONTRATISTA[req.empresa])

    ws_reo["A2"] = EST_CLIENTE
    ws_reo["B7"] = EST_OBRA_TEXTO.get((req.empresa, req.fase), req.fase)
    ws_reo["B9"] = EST_CONTRATISTA[req.empresa]
    oc_contrato = _est_oc_contrato_por_serie(req.empresa, req.fase, req.serie)
    ws_reo["M9"] = int(oc_contrato) if oc_contrato.isdigit() else oc_contrato
    ws_reo["A12"] = req.numero_estimacion
    _sin_formula(ws_reo["A12"])
    ws_reo["B12"] = "ORDINARIA"
    formato_fecha = '[$-80A]d" de "mmmm" de "yyyy;@'
    for celda, valor in (("E12", req.fecha_desde), ("H12", req.fecha_hasta),
                         ("K12", req.fecha_estimacion)):
        ws_reo[celda] = _est_fecha_excel(valor)
        _sin_formula(ws_reo[celda])
        ws_reo[celda].number_format = formato_fecha
    ws_reo["N12"] = req.semana

    etiqueta_anterior, etiqueta_actual, etiqueta_acumulada = _est_etiquetas_rango(
        req.numero_estimacion
    )
    ws_reo["H16"] = etiqueta_anterior
    ws_reo["K16"] = etiqueta_actual
    ws_reo["N16"] = etiqueta_acumulada

    # 2026-09-25 — logo VMO en CEO-01 y REO-01 (mismas anclas que usa el
    # cliente). En DOMICEM el dict no tiene entrada y no estampa nada: sus
    # CEO/REO traen el logo nativo en la plantilla.
    if "CD-COAF-CEO-01" in wb.sheetnames:
        _est_estampar_logos(wb["CD-COAF-CEO-01"], req.empresa, "CD-COAF-CEO-01",
                            juego=EST_LOGOS_CEO_POR_EMPRESA)
    _est_estampar_logos(ws_reo, req.empresa, "CD-COAF-REO-01",
                        juego=EST_LOGOS_REO_POR_EMPRESA)

    # Guarda del hallazgo D1 (issue #27): copy_worksheet pierde las imagenes
    # en silencio, asi que ninguna hoja PLANTILLA puede traerlas.
    _est_afirmar_plantilla_sin_imagenes(ws_rgo_plantilla, "CD-COAF-RGO-PLANTILLA")

    total_facturas = 0
    productos_con_entregas = 0
    nombres_usados = set(wb.sheetnames)
    nombres_rgo = []
    for c in catalogo:
        # OJO: aca conviven los dos campos y NO son intercambiables.
        #
        #   orden -> POSICION fisica del renglon en la hoja. Se queda.
        #   clave -> ETIQUETA del producto, lo que va en la columna A
        #            (rotulada CLAVE en la fila 15). Es lo que cambia.
        #
        # Coinciden en 70 de las 72 filas del catalogo real, por eso el bug
        # vivio tanto. En VMO/PATIO DE MANIOBRAS-TRA estan cruzadas
        # (orden 2 -> clave '3', orden 3 -> clave '2') y el documento real
        # del cliente trae 1,3,2,4 en esa columna: la CLAVE, no la posicion.
        #
        # Si alguien "corrige" tambien el calculo de `fila` usando la clave,
        # en TRA se intercambian dos renglones ENTEROS del REO (concepto,
        # P.U., acumulados) y eso si mueve plata. La columna A, en cambio,
        # no participa de ninguna formula: se verifico que las 9 plantillas
        # solo referencian A2/A3/A12 (cliente, obra, numero de estimacion).
        fila = EST_REO_FIRST_ROW + (c["orden"] - 1)
        prod_req = productos_por_clave[c["clave"]]
        # entero cuando se puede, como lo traen los documentos del cliente
        clave = c["clave"]
        ws_reo.cell(fila, 1).value = int(clave) if str(clave).isdigit() else clave
        ws_reo.cell(fila, 2).value = c["descripcion"]
        ws_reo.cell(fila, 3).value = "m3"
        ws_reo.cell(fila, 4).value = prod_req.cantidad_proyecto
        ws_reo.cell(fila, 5).value = c["precio_unitario"]
        ws_reo.cell(fila, 8).value = prod_req.acumulado_anterior_cantidad

        facturas = facturas_por_clave[c["clave"]]
        if facturas:
            productos_con_entregas += 1
            sheet_name = _est_nombre_hoja(c["clave"], nombres_usados, "CD-COAF-RGO-")
            nombres_rgo.append(sheet_name)
            ws_rgo = wb.copy_worksheet(ws_rgo_plantilla)
            ws_rgo.title = sheet_name

            # Config de impresion — issue #18. La plantilla no trae ninguna,
            # asi que hay que ponerla, o el PDF sale partido (issue #6,
            # hallazgo #1).
            #
            # El issue #6 la resolvio con landscape + "ajustar a 1 pagina de
            # ancho", y eso arreglo el corte horizontal. Pero mide mal el
            # alto: a esa escala un bloque de EST_RGO_PERIODO filas NO entra
            # en una pagina, asi que LibreOffice agrega saltos AUTOMATICOS
            # ademas de los explicitos y los bloques de 40 salen partidos.
            # Medido generando PDFs reales con 175 folios: daba
            # 27+13, 36+4, 36+4, 36+4, 15 en 10 paginas.
            #
            # Se pasa al mismo setup que usan los documentos del cliente
            # (medido en sus hojas RGO: portrait, escala fija 64, sin
            # "ajustar a"): con eso el mismo caso da 40/40/40/40/15 exacto.
            # El salto explicito solo manda si el bloque cabe fisicamente.
            ws_rgo.page_setup.orientation = "portrait"
            ws_rgo.page_setup.scale = 64
            ws_rgo.page_setup.fitToWidth = None
            ws_rgo.page_setup.fitToHeight = 0
            ws_rgo.sheet_properties.pageSetUpPr.fitToPage = False

            # PARTIDA: (A15) vacio — issue #37, mismo criterio que en RCO/RFO
            # (ver el comentario largo en _est_generar_workbook): en los 15
            # documentos del cliente ese casillero sale en blanco siempre.
            ws_rgo.cell(15, 1).value = None
            ws_rgo.cell(15, 2).value = c["clave"]
            ws_rgo.cell(15, 3).value = c["descripcion"]
            ws_rgo.cell(15, 8).value = "m3"

            facturas_orden = sorted(facturas, key=lambda f: (f["fecha"], f["id_documento"]))
            total_row_rgo = _est_redimensionar_rgo(ws_rgo, len(facturas_orden))

            # Area de impresion acotada a las columnas A:I y hasta la ultima
            # fila usada (el pie de la ultima pagina, 3 filas debajo del
            # TOTAL) — issue #18. Sin esto, a escala fija las columnas a la
            # derecha de I generan una BANDA ENTERA de paginas en blanco:
            # el caso de 175 folios daba 10 paginas (5 con datos + 5 vacias)
            # en vez de 5. Los documentos del cliente hacen lo mismo y
            # extienden el rango segun las paginas (su hoja de 63 folios
            # tiene A1:I111).
            ws_rgo.print_area = f"'{sheet_name}'!$A$1:$I${total_row_rgo + 3}"

            # 2026-09-25 — logo en la esquina derecha de CADA bloque de 40
            # folios de la RGO (sello DOMICEM o logo VMO segun empresa)
            _est_estampar_logos_rgo(ws_rgo, req.empresa, sheet_name,
                                    len(facturas_orden))

            for i, f in enumerate(facturas_orden):
                # issue #18: con mas de 40 folios la hoja sale paginada y
                # cada pagina corre EST_RGO_PERIODO filas hacia abajo; con
                # 40 o menos esto es EST_RGO_FIRST_ROW + i, como siempre
                r = _est_fila_dato_rgo(i)
                ws_rgo.cell(r, 1).value = f["fecha"]
                ws_rgo.cell(r, 2).value = f["id_documento"]
                ws_rgo.cell(r, 3).value = i + 1
                ws_rgo.cell(r, 7).value = f["cantidad"]
                total_facturas += 1

            ws_reo.cell(fila, 11).value = f"='{sheet_name}'!G{total_row_rgo}"

    # Issue #27 — las hojas RCO/RFO por clave, DESPUES del bucle de RGO: son
    # hoja-final (no escriben ni una celda de REO-01 ni de las RGO, criterio
    # 9) y asi el bloque queda anulable de un solo lugar para probarlo.
    nombres_rco, nombres_rfo = _est_agregar_hojas_rco_rfo(
        wb, req, catalogo, facturas_por_clave, nombres_usados
    )

    wb.remove(ws_rgo_plantilla)
    for nombre_plantilla in (EST_RCO_PLANTILLA, EST_RFO_PLANTILLA):
        if nombre_plantilla in wb.sheetnames:
            wb.remove(wb[nombre_plantilla])

    # Decision 6 — hojas agrupadas por tipo: caratula, resumen, todas las
    # RGO, todas las RCO, todas las RFO (se descarto intercalar por clave).
    # Sin esto quedarian RGO-01..RGO-NN seguidas de RCO-01, RFO-01, RCO-02...
    # en el orden en que copy_worksheet las fue anexando.
    orden_final = (["CD-COAF-CEO-01", "CD-COAF-REO-01"]
                   + nombres_rgo + nombres_rco + nombres_rfo)
    conocidas = set(orden_final)
    wb._sheets = ([wb[nombre] for nombre in orden_final if nombre in wb.sheetnames]
                  + [ws for ws in wb._sheets if ws.title not in conocidas])
    wb.active = 0

    fase_slug = _est_slug(req.fase)
    nombre = _est_nombre_entregable(req.empresa, fase_slug, req.serie,
                                    req.fecha_desde, req.fecha_hasta)
    ruta_tmp = os.path.join(EST_REPORTES_DIR, nombre + ".tmp")
    ruta_final = os.path.join(EST_REPORTES_DIR, nombre)
    wb.save(ruta_tmp)
    _est_arreglar_saltos_footer(ruta_tmp)
    os.replace(ruta_tmp, ruta_final)

    nombre_pdf = _est_convertir_a_pdf(ruta_final, nombre)

    # Los conduces escaneados van DESPUES de convertir: se anexan al PDF ya
    # hecho, no al .xlsx. LibreOffice no los pondria (y `copy_worksheet` de
    # openpyxl pierde imagenes en silencio, ver HANDOFF), asi que el unico
    # lugar donde el anexado es fiable es sobre el PDF terminado.
    escaneos = {"total": 0, "anexados": 0, "faltantes": [], "error": None}
    if nombre_pdf:
        escaneos = _est_anexar_escaneos(
            os.path.join(EST_REPORTES_DIR, nombre_pdf), catalogo,
            facturas_por_clave, empresa=req.empresa
        )
    else:
        escaneos["error"] = "no hubo PDF que anexar (fallo la conversion con LibreOffice)"

    return total_facturas, productos_con_entregas, nombre, nombre_pdf, escaneos


# ═══════════════════════════════════════════════════════════════════════════
# Modulo de Logistica — el historial de dias
# ═══════════════════════════════════════════════════════════════════════════
#
# Que se guarda y que no, que es la decision que define esta base:
#
#   SE GUARDA lo que no es derivable — las filas crudas de los dos Excel, los
#   supuestos DE ESE DIA (cargue, calidad, tolerancia, y trayecto+zona por
#   planta), los trayectos que alguien corrigio a mano y las observaciones que
#   escribio.
#
#   NO SE GUARDA el resultado: ni el estado de cada pedido, ni la diferencia,
#   ni el porcentaje. Eso se recalcula al abrir el dia, con la misma funcion
#   que calcula el dia de hoy. Guardarlo seria tener el mismo numero en dos
#   lugares, y ademas obligaria a reimplementar el cruce en Python — dos
#   implementaciones del mismo calculo se separan siempre.
#
# Que los supuestos viajen CON el dia es lo que hace que abrir un dia viejo
# reproduzca exactamente lo que se vio ese dia, en vez de recalcularlo con los
# supuestos de hoy. Y como los crudos estan, un supuesto que resulte
# equivocado se puede corregir hacia atras en vez de quedar grabado.

def _log_conn():
    """Conexion a la base de Logistica, creando el directorio si hace falta.

    isolation_level=None (autocommit) porque _log_guardar_dia() maneja su
    propia transaccion explicita: el reemplazo de un dia es un DELETE + INSERT
    y tiene que ser todo o nada.
    """
    os.makedirs(os.path.dirname(LOG_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(LOG_DB_PATH, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def setup_logistica_db(conn=None):
    """Crea las tablas si no estan. Idempotente y barata: la llaman las rutas
    que escriben, igual que setup_est_db(), para que una base nueva o un
    checkout limpio no necesiten un paso manual.

    Las columnas que solo se muestran (pedido, prioridad, conduce, elemento) se
    declaran TEXT a proposito: en el Excel a veces vienen numero y a veces
    texto, y para mostrarlas da igual. Las que entran a alguna cuenta
    —hora_min, cantidad— son REAL.
    """
    propia = conn is None
    conn = conn or _log_conn()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS logistica_dia (
            fecha            TEXT PRIMARY KEY,
            guardado_en      TEXT NOT NULL,
            cargue_min       REAL NOT NULL,
            calidad_min      REAL NOT NULL,
            tolerancia_min   REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS logistica_dia_planta (
            fecha        TEXT NOT NULL,
            planta       TEXT NOT NULL,
            trayecto_min REAL,
            zona         TEXT,
            PRIMARY KEY (fecha, planta),
            FOREIGN KEY (fecha) REFERENCES logistica_dia(fecha) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS logistica_programacion (
            fecha     TEXT NOT NULL,
            orden     INTEGER NOT NULL,
            cliente   TEXT, obra TEXT, hora_min REAL, pedido TEXT, cantidad REAL,
            elemento  TEXT, producto TEXT, prioridad TEXT, zona_hoja TEXT,
            -- REAL y no INTEGER: el Excel los trae con media unidad.
            -- NULL significa "la planilla no traia la columna", que no es lo
            -- mismo que 0 ("no se despacho nada") — repartirCamiones() cae a
            -- la cantidad programada solo en el primer caso.
            despachado REAL, pendiente REAL,
            PRIMARY KEY (fecha, orden),
            FOREIGN KEY (fecha) REFERENCES logistica_dia(fecha) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS logistica_cargue (
            fecha     TEXT NOT NULL,
            orden     INTEGER NOT NULL,
            ficha     TEXT, hora_min REAL, cliente TEXT, conduce TEXT,
            elemento  TEXT, planta TEXT, obra TEXT, cantidad REAL,
            PRIMARY KEY (fecha, orden),
            FOREIGN KEY (fecha) REFERENCES logistica_dia(fecha) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS logistica_trayecto_override (
            fecha   TEXT NOT NULL,
            clave   TEXT NOT NULL,
            minutos REAL NOT NULL,
            PRIMARY KEY (fecha, clave),
            FOREIGN KEY (fecha) REFERENCES logistica_dia(fecha) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS logistica_observacion (
            fecha TEXT NOT NULL,
            clave TEXT NOT NULL,
            texto TEXT NOT NULL,
            PRIMARY KEY (fecha, clave),
            FOREIGN KEY (fecha) REFERENCES logistica_dia(fecha) ON DELETE CASCADE
        );
        -- Responsable de cada fila (2026-10-06): VMO, Cliente o Externo. Tabla
        -- propia y no una columna de logistica_observacion porque `texto` es
        -- NOT NULL: una fila con responsable y sin observacion no cabria.
        -- Motivo de cada fila (2026-10-06). Sin CHECK a proposito, a
        -- diferencia de responsable: la lista de motivos va a crecer, y un
        -- CHECK obligaria a reconstruir la tabla para agregar uno. La valida
        -- la ruta, contra LOG_MOTIVOS.
        CREATE TABLE IF NOT EXISTS logistica_motivo (
            fecha TEXT NOT NULL,
            clave TEXT NOT NULL,
            valor TEXT NOT NULL,
            PRIMARY KEY (fecha, clave),
            FOREIGN KEY (fecha) REFERENCES logistica_dia(fecha) ON DELETE CASCADE
        );
        -- Incumplidas que el usuario paso a cumplido a mano (2026-10-26). Solo
        -- la clave: el motivo, que es obligatorio, ya esta en logistica_motivo.
        CREATE TABLE IF NOT EXISTS logistica_cumplido_manual (
            fecha TEXT NOT NULL,
            clave TEXT NOT NULL,
            PRIMARY KEY (fecha, clave),
            FOREIGN KEY (fecha) REFERENCES logistica_dia(fecha) ON DELETE CASCADE
        );
        -- Los dos reportes del sistema que alimentan la pagina Indicadores
        -- (2026-10-28). No cuelgan de logistica_dia: se suben por rango de
        -- fechas, aparte del dia, y un rango nuevo reemplaza esas fechas.
        -- "Metros bombeados por equipo": m3 de cada equipo en cada dia.
        CREATE TABLE IF NOT EXISTS logistica_bombeo (
            fecha  TEXT NOT NULL,
            equipo TEXT NOT NULL,
            nombre TEXT,
            m3     REAL NOT NULL,
            PRIMARY KEY (fecha, equipo)
        );
        -- "Cumplimiento de tiempos de despacho": un renglon por pedido. Las
        -- horas en minutos desde las 00:00; NULL es "el sistema no la tiene".
        CREATE TABLE IF NOT EXISTS logistica_tiempo_pedido (
            fecha             TEXT NOT NULL,
            orden             INTEGER NOT NULL,
            ord_comp          TEXT,
            planta            TEXT,
            cliente           TEXT,
            hora_ini          REAL,
            hora_fin          REAL,
            cantidad          REAL NOT NULL,
            total_in          REAL NOT NULL,
            logro             TEXT,
            total_despachado  REAL NOT NULL,
            viajes_programados REAL,
            viajes_efectuados REAL NOT NULL,
            bomba             TEXT,
            PRIMARY KEY (fecha, orden)
        );
        CREATE TABLE IF NOT EXISTS logistica_responsable (
            fecha TEXT NOT NULL,
            clave TEXT NOT NULL,
            valor TEXT NOT NULL CHECK (valor IN ('VMO', 'Cliente', 'Externo')),
            PRIMARY KEY (fecha, clave),
            FOREIGN KEY (fecha) REFERENCES logistica_dia(fecha) ON DELETE CASCADE
        );
        """)
        # Migracion idempotente para las bases que ya existian sin estas dos
        # columnas (mismo patron PRAGMA table_info que usa setup_est_db).
        # CREATE TABLE IF NOT EXISTS no toca una tabla ya creada, asi que sin
        # esto el INSERT de abajo falla en cualquier base anterior al arreglo.
        cols = [c[1] for c in conn.execute("PRAGMA table_info(logistica_programacion)")]
        for columna in ("despachado", "pendiente"):
            if columna not in cols:
                conn.execute(f"ALTER TABLE logistica_programacion ADD COLUMN {columna} REAL")
        # bomba, vendedor y zona de la planilla (2026-10-06), con el mismo patron
        for columna in ("bomba", "vendedor", "zona_prog"):
            if columna not in cols:
                conn.execute(f"ALTER TABLE logistica_programacion ADD COLUMN {columna} TEXT")
        # `tolerancia_adelanto_min` (2026-10-02) entra igual: los dias guardados
        # antes quedan en NULL y el navegador cae al default al abrirlos. Es
        # NULL y no un numero escrito porque un dia viejo NO tenia ese supuesto,
        # y fingir que lo tuvo seria inventarle una decision que nadie tomo.
        cols_dia = [c[1] for c in conn.execute("PRAGMA table_info(logistica_dia)")]
        if "tolerancia_adelanto_min" not in cols_dia:
            conn.execute("ALTER TABLE logistica_dia ADD COLUMN tolerancia_adelanto_min REAL")
        # `espaciamiento_min` (2026-10-06), mismo criterio: NULL es "no habia"
        if "espaciamiento_min" not in cols_dia:
            conn.execute("ALTER TABLE logistica_dia ADD COLUMN espaciamiento_min REAL")
    finally:
        if propia:
            conn.close()


def _log_avisos_guardar(conn, fecha: str) -> list[dict]:
    """Avisos antes de guardar un dia. Hoy hay uno solo: que ese dia YA esta
    guardado y se va a reemplazar.

    No bloquea —la correccion legitima es lo mas comun: el Excel del dia llego
    incompleto y despues se rehizo— pero exige confirmacion explicita, y el
    aviso trae lo que se va a reemplazar para que la decision se tome mirando
    el numero y no de memoria.

    El patron es prestado del aviso "re_cierre" de Estimaciones, y la razon de
    que exista es la misma: guardar un dia es DELETE + INSERT, y un
    DELETE + INSERT silencioso sobre algo que alguien ya reporto ya costo caro
    una vez en este proyecto (ver HANDOFF.md).
    """
    fila = conn.execute(
        "SELECT d.guardado_en, "
        "  (SELECT COUNT(*) FROM logistica_programacion p WHERE p.fecha = d.fecha), "
        "  (SELECT COUNT(*) FROM logistica_cargue c WHERE c.fecha = d.fecha), "
        "  (SELECT COALESCE(SUM(c.cantidad), 0) FROM logistica_cargue c WHERE c.fecha = d.fecha), "
        "  (SELECT COUNT(*) FROM logistica_observacion o WHERE o.fecha = d.fecha) "
        "FROM logistica_dia d WHERE d.fecha = ?", (fecha,)
    ).fetchone()
    if not fila:
        return []
    return [{"tipo": "reemplazo", "fecha": fecha, "guardado_en": fila[0],
             "pedidos": fila[1], "cargues": fila[2], "m3": fila[3],
             "observaciones": fila[4]}]


def _log_guardar_dia(conn, dia: dict) -> dict:
    """Guarda (o reemplaza) un dia entero, en UNA transaccion.

    El borrado de logistica_dia arrastra el resto por ON DELETE CASCADE, asi
    que no hay forma de que queden filas de un dia sin su cabecera. Si algo
    falla a mitad, el rollback deja el dia anterior intacto: nunca se queda a
    medio reemplazar.
    """
    fecha = dia["fecha"]
    conn.execute("BEGIN")
    try:
        conn.execute("DELETE FROM logistica_dia WHERE fecha = ?", (fecha,))
        conn.execute(
            "INSERT INTO logistica_dia (fecha, guardado_en, cargue_min, calidad_min, "
            "tolerancia_min, tolerancia_adelanto_min, espaciamiento_min) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (fecha, datetime.now().isoformat(timespec="seconds"),
             dia["cargue"], dia["calidad"], dia["tolerancia"],
             dia.get("toleranciaAdelanto"), dia.get("espaciamiento")))
        conn.executemany(
            "INSERT INTO logistica_dia_planta (fecha, planta, trayecto_min, zona) "
            "VALUES (?, ?, ?, ?)",
            [(fecha, p["planta"], p.get("trayecto"), p.get("zona")) for p in dia["plantas"]])
        conn.executemany(
            "INSERT INTO logistica_programacion (fecha, orden, cliente, obra, hora_min, "
            "pedido, cantidad, elemento, producto, prioridad, zona_hoja, "
            "despachado, pendiente, bomba, vendedor, zona_prog) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(fecha, i, r.get("cliente"), r.get("obra"), r.get("horaMin"), r.get("pedido"),
              r.get("cantidad"), r.get("elemento"), r.get("producto"), r.get("prioridad"),
              r.get("zonaSheet"), r.get("despachado"), r.get("pendiente"),
              r.get("bomba"), r.get("vendedor"), r.get("zonaProg"))
             for i, r in enumerate(dia["programacion"])])
        conn.executemany(
            "INSERT INTO logistica_cargue (fecha, orden, ficha, hora_min, cliente, conduce, "
            "elemento, planta, obra, cantidad) VALUES (?,?,?,?,?,?,?,?,?,?)",
            [(fecha, i, r.get("ficha"), r.get("horaMin"), r.get("cliente"), r.get("conduce"),
              r.get("elemento"), r.get("planta"), r.get("obra"), r.get("cantidad"))
             for i, r in enumerate(dia["cargue_rows"])])
        conn.executemany(
            "INSERT INTO logistica_trayecto_override (fecha, clave, minutos) VALUES (?,?,?)",
            [(fecha, k, v) for k, v in dia["trayectoOverrides"].items()])
        conn.executemany(
            "INSERT INTO logistica_observacion (fecha, clave, texto) VALUES (?,?,?)",
            [(fecha, k, v) for k, v in dia["observaciones"].items() if (v or "").strip()])
        conn.executemany(
            "INSERT INTO logistica_responsable (fecha, clave, valor) VALUES (?,?,?)",
            [(fecha, k, v) for k, v in (dia.get("responsables") or {}).items()])
        conn.executemany(
            "INSERT INTO logistica_motivo (fecha, clave, valor) VALUES (?,?,?)",
            [(fecha, k, v) for k, v in (dia.get("motivos") or {}).items()])
        conn.executemany(
            "INSERT OR IGNORE INTO logistica_cumplido_manual (fecha, clave) VALUES (?,?)",
            [(fecha, k) for k in (dia.get("cumplidosManuales") or [])])
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {"fecha": fecha, "pedidos": len(dia["programacion"]),
            "cargues": len(dia["cargue_rows"])}


# Los reportes de Indicadores (2026-10-28). Cada subida reemplaza su rango
# entero en UNA transaccion: lo que habia de esas fechas se borra y entra lo
# nuevo, y si algo falla queda lo anterior. Fechas fuera del rango no se tocan.
LOG_IND_COLUMNAS = {
    "logistica_bombeo": ("fecha", "equipo", "nombre", "m3"),
    "logistica_tiempo_pedido": ("fecha", "orden", "ord_comp", "planta", "cliente", "hora_ini",
                                "hora_fin", "cantidad", "total_in", "logro", "total_despachado",
                                "viajes_programados", "viajes_efectuados", "bomba"),
}


def _log_ind_reemplazar(conn, tabla: str, desde: str, hasta: str, filas: list[tuple]) -> dict:
    cols = LOG_IND_COLUMNAS[tabla]
    conn.execute("BEGIN")
    try:
        antes = conn.execute(f"SELECT COUNT(*) FROM {tabla} WHERE fecha BETWEEN ? AND ?",
                             (desde, hasta)).fetchone()[0]
        conn.execute(f"DELETE FROM {tabla} WHERE fecha BETWEEN ? AND ?", (desde, hasta))
        conn.executemany(f"INSERT INTO {tabla} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                         filas)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {"desde": desde, "hasta": hasta, "filas": len(filas), "reemplazadas": antes}


def _log_ind_leer(conn, desde: str, hasta: str) -> dict:
    """Las filas de los dos reportes en el rango, y que fechas hay cargadas de
    cada uno (para que la pagina diga que falta subir)."""
    def filas(tabla):
        cols = LOG_IND_COLUMNAS[tabla]
        return [dict(zip(cols, f)) for f in conn.execute(
            f"SELECT {', '.join(cols)} FROM {tabla} WHERE fecha BETWEEN ? AND ? ORDER BY fecha",
            (desde, hasta))]

    def fechas(tabla):
        return [f[0] for f in conn.execute(f"SELECT DISTINCT fecha FROM {tabla} ORDER BY fecha")]

    return {"bombeo": filas("logistica_bombeo"), "tiempos": filas("logistica_tiempo_pedido"),
            "fechas": {"bombeo": fechas("logistica_bombeo"),
                       "tiempos": fechas("logistica_tiempo_pedido")}}


def _log_listar_dias(conn) -> list[dict]:
    """El indice del historial: un renglon por dia guardado, del mas nuevo al
    mas viejo.

    Trae solo lo que es una cuenta directa sobre lo guardado. **El porcentaje
    de cumplimiento NO viene de aca**: es derivado del cruce, y el cruce vive
    en el JavaScript. Ponerlo en esta consulta obligaria a reimplementarlo en
    Python, que es exactamente lo que el diseno de esta base evita.
    """
    filas = conn.execute("""
        SELECT d.fecha, d.guardado_en,
               (SELECT COUNT(*) FROM logistica_programacion p WHERE p.fecha = d.fecha),
               (SELECT COUNT(*) FROM logistica_cargue c WHERE c.fecha = d.fecha),
               (SELECT COALESCE(SUM(c.cantidad), 0) FROM logistica_cargue c WHERE c.fecha = d.fecha),
               (SELECT COUNT(DISTINCT c.cliente) FROM logistica_cargue c WHERE c.fecha = d.fecha),
               (SELECT COUNT(DISTINCT c.ficha) FROM logistica_cargue c WHERE c.fecha = d.fecha)
        FROM logistica_dia d ORDER BY d.fecha DESC
    """).fetchall()
    return [{"fecha": f[0], "guardado_en": f[1], "pedidos": f[2], "cargues": f[3],
             "m3": f[4], "clientes": f[5], "camiones": f[6]} for f in filas]


def _log_leer_dia(conn, fecha: str) -> dict | None:
    """Todo lo guardado de un dia, en la misma forma que el dashboard maneja en
    memoria, para que reabrirlo sea cargar el estado y recalcular.

    `orden` reproduce el orden del archivo original; no entra en ningun
    calculo (el cruce ordena por hora) pero hace que la vista sea la misma.
    """
    cab = conn.execute(
        "SELECT guardado_en, cargue_min, calidad_min, tolerancia_min, "
        "tolerancia_adelanto_min, espaciamiento_min FROM logistica_dia WHERE fecha = ?",
        (fecha,)).fetchone()
    if not cab:
        return None

    programacion = [
        {"cliente": f[0], "obra": f[1], "horaMin": f[2], "pedido": f[3], "cantidad": f[4],
         "elemento": f[5], "producto": f[6], "prioridad": f[7], "zonaSheet": f[8],
         "despachado": f[9], "pendiente": f[10],
         "bomba": f[11], "vendedor": f[12], "zonaProg": f[13]}
        for f in conn.execute(
            "SELECT cliente, obra, hora_min, pedido, cantidad, elemento, producto, "
            "prioridad, zona_hoja, despachado, pendiente, bomba, vendedor, zona_prog "
            "FROM logistica_programacion "
            "WHERE fecha = ? ORDER BY orden", (fecha,))]

    cargue = [
        {"ficha": f[0], "horaMin": f[1], "cliente": f[2], "conduce": f[3],
         "elemento": f[4], "planta": f[5], "obra": f[6], "cantidad": f[7]}
        for f in conn.execute(
            "SELECT ficha, hora_min, cliente, conduce, elemento, planta, obra, cantidad "
            "FROM logistica_cargue WHERE fecha = ? ORDER BY orden", (fecha,))]

    plantas = [{"planta": f[0], "trayecto": f[1], "zona": f[2]} for f in conn.execute(
        "SELECT planta, trayecto_min, zona FROM logistica_dia_planta WHERE fecha = ? "
        "ORDER BY planta", (fecha,))]

    overrides = {f[0]: f[1] for f in conn.execute(
        "SELECT clave, minutos FROM logistica_trayecto_override WHERE fecha = ?", (fecha,))}
    observaciones = {f[0]: f[1] for f in conn.execute(
        "SELECT clave, texto FROM logistica_observacion WHERE fecha = ?", (fecha,))}
    responsables = {f[0]: f[1] for f in conn.execute(
        "SELECT clave, valor FROM logistica_responsable WHERE fecha = ?", (fecha,))}
    motivos = {f[0]: f[1] for f in conn.execute(
        "SELECT clave, valor FROM logistica_motivo WHERE fecha = ?", (fecha,))}
    cumplidos_manuales = [f[0] for f in conn.execute(
        "SELECT clave FROM logistica_cumplido_manual WHERE fecha = ? ORDER BY clave", (fecha,))]

    return {"fecha": fecha, "guardado_en": cab[0],
            # `toleranciaAdelanto` viaja aunque sea None: un dia guardado antes
            # del 2026-10-02 no tenia ese supuesto, y el navegador distingue
            # None ("no habia") de un numero ("se decidio esto").
            "supuestos": {"cargue": cab[1], "calidad": cab[2], "tolerancia": cab[3],
                          "toleranciaAdelanto": cab[4], "espaciamiento": cab[5],
                          "plantas": plantas},
            "programacion": programacion, "cargue": cargue,
            "trayectoOverrides": overrides, "observaciones": observaciones,
            "responsables": responsables, "motivos": motivos,
            "cumplidosManuales": cumplidos_manuales}


def _log_borrar_dia(conn, fecha: str) -> dict | None:
    """Borra un dia guardado (boton Borrar del Historial, 2026-10-12).

    ANTES de borrar deja el dia completo —lo mismo que devuelve
    _log_leer_dia(), con observaciones, motivos y responsables— en un JSON en
    `borrados/`, al lado de la base. Borrar es lo unico del modulo que no se
    corrige volviendo a guardar: el trabajo cargado a mano en ese dia no esta
    en ningun Excel. Con la copia, un borrado por error se recupera.

    El resto de las tablas cae por ON DELETE CASCADE, como en el reemplazo.
    Devuelve None si el dia no existe.
    """
    dia = _log_leer_dia(conn, fecha)
    if dia is None:
        return None
    carpeta = os.path.join(os.path.dirname(LOG_DB_PATH), "borrados")
    os.makedirs(carpeta, exist_ok=True)
    respaldo = os.path.join(carpeta, f"{fecha}__borrado_{datetime.now():%Y%m%d_%H%M%S}.json")
    with open(respaldo, "w", encoding="utf-8") as f:
        json.dump(dia, f, ensure_ascii=False, indent=1)
    conn.execute("BEGIN")
    try:
        conn.execute("DELETE FROM logistica_dia WHERE fecha = ?", (fecha,))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {"fecha": fecha, "respaldo": os.path.basename(respaldo),
            "pedidos": len(dia["programacion"]), "cargues": len(dia["cargue"])}


# ================= REPORTE DE CANCELADOS (2026-10-12) =================
#
# El Excel de la pestana "Reporte cancelados": los pedidos no despachados de
# un rango de dias, en una tabla con formato y una hoja de resumen.
#
# Igual que el resto del modulo, **aca no se calcula que es un cancelado**:
# las filas y el resumen los arma reporteCancelados() en logistica.logic.js
# —con la misma filasCancelados() del Excel de un dia— y llegan hechos. Esto
# solo les da formato. Se hace en el servidor porque la libreria de Excel del
# navegador (SheetJS gratis) no escribe estilos ni tablas, y openpyxl si.

LOG_AZUL = "003087"
LOG_ROJO = "CC0000"
LOG_GRIS = "5B6472"
_LOG_ESTILO_TABLA = "TableStyleMedium2"


def _log_fecha(texto: str):
    return datetime.strptime(texto, "%Y-%m-%d")


def _log_titulo(ws, titulo: str, desde: str, hasta: str):
    ws["A1"] = titulo
    ws["A1"].font = Font(size=16, bold=True, color=LOG_AZUL)
    rango = f"del {_log_fecha(desde):%d/%m/%Y} al {_log_fecha(hasta):%d/%m/%Y}"
    ws["A2"] = f"VMO Concretos · {rango} · generado el {datetime.now():%d/%m/%Y %H:%M}"
    ws["A2"].font = Font(size=10, color=LOG_GRIS)


def _log_tabla(ws, nombre: str, fila: int, col: int, encabezado: list, datos: list,
               formatos: dict | None = None, anchos: list | None = None):
    """Una tabla de Excel (con filtros y filas en franjas) desde (fila, col).
    Devuelve la ultima fila escrita. Sin datos no se crea la tabla: Excel
    marca como dañado un archivo con una tabla de cero filas."""
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table, TableStyleInfo

    formatos = formatos or {}
    for j, titulo in enumerate(encabezado):
        c = ws.cell(row=fila, column=col + j, value=titulo)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=LOG_AZUL)
        c.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[fila].height = 32
    for i, valores in enumerate(datos, start=1):
        for j, v in enumerate(valores):
            c = _sin_formula(ws.cell(row=fila + i, column=col + j, value=v))
            if j in formatos:
                c.number_format = formatos[j]
            # Las fechas a la izquierda: en el Resumen la columna de la fecha
            # es ancha por las etiquetas de arriba y quedaban lejos.
            c.alignment = Alignment(vertical="top", wrap_text=isinstance(v, str) and len(v) > 30,
                                    horizontal="left" if isinstance(v, datetime) else None)
    if anchos:
        for j, ancho in enumerate(anchos):
            ws.column_dimensions[get_column_letter(col + j)].width = ancho
    if datos:
        ref = (f"{get_column_letter(col)}{fila}:"
               f"{get_column_letter(col + len(encabezado) - 1)}{fila + len(datos)}")
        tabla = Table(displayName=nombre, ref=ref)
        tabla.tableStyleInfo = TableStyleInfo(name=_LOG_ESTILO_TABLA, showRowStripes=True)
        ws.add_table(tabla)
    return fila + len(datos)


def _log_fila_total(ws, fila: int, col: int, valores: list, formatos: dict):
    from openpyxl.styles import Border, Side
    for j, v in enumerate(valores):
        c = ws.cell(row=fila, column=col + j, value=v)
        c.font = Font(bold=True)
        c.border = Border(top=Side(style="medium", color=LOG_AZUL))
        if j in formatos and v is not None:
            c.number_format = formatos[j]


def log_reporte_cancelados_xlsx(desde: str, hasta: str, encabezado: list, filas: list,
                                resumen: dict) -> bytes:
    """El Excel del reporte: hoja "Cancelados" con un renglon por pedido y hoja
    "Resumen" con los totales, por dia, por motivo y por responsable."""
    import io

    M3, FECHA, HORA = "#,##0.0", "dd/mm/yyyy", "h:mm AM/PM"
    wb = openpyxl.Workbook()

    ws = wb.active
    ws.title = "Cancelados"
    _log_titulo(ws, "Reporte de pedidos cancelados", desde, hasta)
    datos = [[
        _log_fecha(f["fecha"]), f["semana"],
        # La hora como fraccion del dia, que es lo que Excel entiende por hora.
        None if f["horaFraccion"] is None else f["horaFraccion"],
        f["cliente"], f["obra"], f["vendedor"], f["zona"], f["elemento"], f["servicio"],
        f["producto"], f["volumen"], f["razon"], f["responsable"], f["motivo"],
    ] for f in filas]
    formatos = {0: FECHA, 2: HORA, 10: M3}
    anchos = [12, 22, 17, 40, 34, 18, 16, 18, 17, 36, 16, 40, 15, 30]
    if datos:
        ultima = _log_tabla(ws, "Cancelados", 4, 1, encabezado, datos, formatos, anchos)
        _log_fila_total(ws, ultima + 1, 1,
                        ["TOTAL", f"{len(datos)} pedidos", None, None, None, None, None, None,
                         None, None, resumen["m3Cancelado"]],
                        {10: M3})
        ws.freeze_panes = "A5"
    else:
        ws["A4"] = "No hay pedidos cancelados en los días guardados de este rango."
        ws["A4"].font = Font(italic=True, color=LOG_GRIS)
        ws.column_dimensions["A"].width = 60

    wr = wb.create_sheet("Resumen")
    _log_titulo(wr, "Resumen de cancelados", desde, hasta)
    kpis = [
        ("Días guardados en el rango", resumen["diasRevisados"], "0"),
        ("Días con cancelados", resumen["diasConCancelados"], "0"),
        ("Pedidos cancelados (sin nada despachado)", resumen["entregas"], "0"),
        ("m³ cancelados", resumen["m3Cancelado"], M3),
    ]
    for i, (etiqueta, valor, fmt) in enumerate(kpis, start=4):
        wr.cell(row=i, column=1, value=etiqueta).font = Font(color=LOG_GRIS)
        c = wr.cell(row=i, column=2, value=valor)
        c.number_format = fmt
        c.font = Font(bold=True, size=12, color=LOG_ROJO if i == 7 else LOG_AZUL)
    wr.column_dimensions["A"].width = 38
    wr.column_dimensions["B"].width = 14

    inicio = 10
    wr.cell(row=inicio - 1, column=1, value="Por día").font = Font(bold=True, color=LOG_AZUL)
    _log_tabla(wr, "PorDia", inicio, 1, ["Fecha", "Pedidos", "m³ cancelados"],
               [[_log_fecha(d["fecha"]), d["entregas"], d["m3Cancelado"]]
                for d in resumen["porDia"]],
               {0: FECHA, 2: M3}, [38, 12, 15])
    for titulo, nombre, col, grupos in (("Por motivo", "PorMotivo", 5, resumen["porMotivo"]),
                                        ("Por responsable", "PorResponsable", 10,
                                         resumen["porResponsable"])):
        wr.cell(row=inicio - 1, column=col, value=titulo).font = Font(bold=True, color=LOG_AZUL)
        _log_tabla(wr, nombre, inicio, col,
                   [titulo.replace("Por m", "M").replace("Por r", "R"), "Pedidos",
                    "m³ cancelados", "% de los m³"],
                   [[g["nombre"], g["entregas"], g["m3Cancelado"], g["pct"] / 100] for g in grupos],
                   {2: M3, 3: "0%"}, [34, 10, 15, 12])
    wr.cell(row=inicio - 1, column=1).alignment = Alignment(vertical="bottom")

    # Impreso o pasado a PDF: horizontal y a una pagina de ancho, con el
    # encabezado de la tabla repetido en cada hoja.
    for hoja in (ws, wr):
        hoja.page_setup.orientation = "landscape"
        hoja.page_setup.fitToWidth = 1
        hoja.page_setup.fitToHeight = 0
        hoja.sheet_properties.pageSetUpPr.fitToPage = True
    if datos:
        ws.print_title_rows = "4:4"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────
# LOGISTICA — Reporte del dia en PDF (2026-10-15)
# ─────────────────────────────────────────────
# Los numeros llegan hechos por reporteDelDia(), en logistica.logic.js (la
# misma cuenta que la pantalla); aca solo se dibujan con PyMuPDF, que ya esta
# en requirements. Fuentes base-14 (Helvetica): cubren acentos, ñ y ³, pero
# NO la raya larga ni el ✓, asi que el texto usa "-" y "·".

_LOG_PDF_W, _LOG_PDF_H, _LOG_PDF_M = 842, 595, 30   # A4 apaisado
_LOG_TINTA = (0.10, 0.13, 0.18)
_LOG_GRIS = (0.42, 0.46, 0.52)
_LOG_LINEA = (0.86, 0.88, 0.91)
_LOG_FONDO = (0.96, 0.97, 0.98)
_LOG_AZUL = (0.224, 0.529, 0.898)      # Frecuencia de despacho, como en pantalla
_LOG_NARANJA = (0.851, 0.349, 0.149)   # Inicio de carga
_LOG_OK = (0.08, 0.52, 0.33)
_LOG_MAL = (0.78, 0.16, 0.16)
_LOG_COLOR_RESPONSABLE = {"VMO": (0.83, 0.18, 0.18), "Cliente": (0.30, 0.38, 0.50),
                          "Externo": (0.86, 0.62, 0.10)}
_LOG_DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
# Diseno con banda (opcion 2 de 5, elegida por el usuario el 2026-10-22): el
# encabezado y el pie en el azul noche de la app, el logo con letras blancas
# y una raya del rojo del logo.
_LOG_NOCHE = (0.051, 0.094, 0.161)       # #0D1829, el fondo de la app
_LOG_NOCHE_TEXTO = (0.561, 0.639, 0.737)  # #8FA3BC
_LOG_ROJO_LOGO = (0.910, 0.251, 0.184)    # #E8402F
_LOG_BANDA_ALTO = 66
_LOG_PIE_ALTO = 22
_LOG_LOGO = os.path.join(BASE_DIR, "static", "logo.png")


_log_logo_cache = {}


def _log_logo_blanco():
    """static/logo.png recortado a la marca y con las letras negras en blanco,
    para que se lea sobre la banda oscura. Se arma una vez por proceso."""
    if "png" not in _log_logo_cache:
        from PIL import Image, ImageChops
        im = Image.open(_LOG_LOGO).convert("RGBA")
        im = im.crop(im.getbbox())
        im.thumbnail((600, 600))
        oscuro = im.convert("L").point(lambda v: 255 if v < 90 else 0)
        mascara = ImageChops.multiply(oscuro, im.getchannel("A"))
        im.paste(Image.new("RGBA", im.size, (255, 255, 255, 255)), mask=mascara)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        _log_logo_cache["png"] = (buf.getvalue(), im.height / im.width)
    return _log_logo_cache["png"]


def _log_num(n, decimales=0) -> str:
    """Como fmtInt del navegador (es-DO): coma de miles, punto decimal."""
    n = n or 0
    if decimales and n != int(n):
        return f"{n:,.{decimales}f}"
    return f"{int(round(n)):,}"


def _log_hhmm(m) -> str:
    if m is None:
        return "-"
    m = int(round(m)) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def _log_dif(m) -> str:
    if m is None:
        return "-"
    signo = "-" if m < 0 else "+"
    a = int(round(abs(m)))
    return signo + (f"{a // 60}h {a % 60:02d}m" if a >= 60 else f"{a}m")


def _log_pct(p) -> str:
    return "-" if p is None else f"{p}%"


class _LogLienzo:
    """Lo minimo para escribir y dibujar sin repetir fuente, color y recorte."""

    def __init__(self, page):
        self.p = page

    def texto(self, x, y, s, tam=8, negrita=False, color=_LOG_TINTA, ancho=None, alinear="izq"):
        fuente = "hebo" if negrita else "helv"
        s = str(s if s is not None else "")
        if ancho is not None:
            while s and fitz.get_text_length(s, fontname=fuente, fontsize=tam) > ancho:
                s = s[:-4].rstrip() + "..." if len(s) > 4 else ""
        largo = fitz.get_text_length(s, fontname=fuente, fontsize=tam)
        if alinear == "der" and ancho is not None:
            x = x + ancho - largo
        elif alinear == "centro" and ancho is not None:
            x = x + (ancho - largo) / 2
        self.p.insert_text((x, y), s, fontname=fuente, fontsize=tam, color=color)
        return largo

    def caja(self, x0, y0, x1, y1, relleno=None, borde=None, ancho_borde=0.6):
        if x1 <= x0 or y1 <= y0:
            return
        self.p.draw_rect(fitz.Rect(x0, y0, x1, y1), color=borde, fill=relleno, width=ancho_borde)

    def linea(self, x0, y0, x1, y1, color=_LOG_LINEA, ancho=0.6):
        self.p.draw_line((x0, y0), (x1, y1), color=color, width=ancho)


def _log_barra_pct(c, x, y, ancho, pct, color):
    """Barra horizontal de 0 a 100 con el % al lado. Sin dato, solo el guion."""
    c.caja(x, y - 6, x + ancho, y, relleno=_LOG_FONDO)
    if pct is not None:
        c.caja(x, y - 6, x + ancho * max(0, min(pct, 100)) / 100, y, relleno=color)
    c.texto(x + ancho + 4, y, _log_pct(pct), tam=8, negrita=True)


def _log_encabezado_pagina(c, titulo, fecha_txt, supuestos):
    """La banda oscura de arriba: logo, modulo, titulo, fecha y supuestos.
    Termina en y=_LOG_BANDA_ALTO + 3; el contenido arranca donde siempre."""
    M, W, B = _LOG_PDF_M, _LOG_PDF_W, _LOG_BANDA_ALTO
    c.caja(0, 0, W, B, relleno=_LOG_NOCHE)
    c.caja(0, B, W, B + 3, relleno=_LOG_ROJO_LOGO)
    png, prop = _log_logo_blanco()
    ancho_logo = 70
    alto_logo = ancho_logo * prop
    y_logo = (B - alto_logo) / 2
    # La imagen va una sola vez en el PDF: las paginas siguientes la reusan.
    doc = c.p.parent
    rect = fitz.Rect(M, y_logo, M + ancho_logo, y_logo + alto_logo)
    if getattr(doc, "_vmo_logo_xref", 0):
        c.p.insert_image(rect, xref=doc._vmo_logo_xref)
    else:
        doc._vmo_logo_xref = c.p.insert_image(rect, stream=png)
    x = M + ancho_logo + 20
    c.texto(x, 27, "LOGÍSTICA", tam=7.5, negrita=True, color=_LOG_NOCHE_TEXTO)
    c.texto(x, 48, titulo, tam=18, negrita=True, color=(1, 1, 1), ancho=W - M - x - 300)
    c.texto(W - M - 440, 30, fecha_txt, tam=11, negrita=True, color=(1, 1, 1), ancho=440, alinear="der")
    if supuestos:
        c.texto(W - M - 440, 46, supuestos, tam=7, color=_LOG_NOCHE_TEXTO, ancho=440, alinear="der")


def _log_pie(c, texto, i, n):
    M, W, H = _LOG_PDF_M, _LOG_PDF_W, _LOG_PDF_H
    c.caja(0, H - _LOG_PIE_ALTO, W, H, relleno=_LOG_NOCHE)
    c.texto(M, H - 9, f"VMO Concretos · Logística · {texto}", tam=7, color=_LOG_NOCHE_TEXTO)
    c.texto(W - M - 120, H - 9, f"Página {i} de {n}", tam=7, color=_LOG_NOCHE_TEXTO, ancho=120, alinear="der")


def _log_tabla_grupos(c, x, y, ancho, titulo, filas, tipo):
    """Responsables o motivos: nombre, entregas, m³, % con barra. En los
    motivos va entre parentesis el desglose por responsable (`detalle`)."""
    c.texto(x, y, titulo, tam=10, negrita=True)
    y += 14
    cols = [("", ancho - 200), ("Entregas", 46), ("m³", 50), ("% de los incumplidos", 104)]
    xx = x
    for nombre, w in cols:
        c.texto(xx, y, nombre, tam=6.5, negrita=True, color=_LOG_GRIS, ancho=w - 4,
                alinear="izq" if xx == x else "der")
        xx += w
    y += 4
    c.linea(x, y, x + ancho, y)
    for f in filas:
        y += 13
        sin_dato = f["nombre"].startswith("Sin ")
        etiqueta = f["nombre"] + (f"  ({f['detalle']})" if f.get("detalle") and tipo != "responsable" else "")
        if tipo == "responsable":
            muestra = _LOG_COLOR_RESPONSABLE.get(f["nombre"], _LOG_LINEA)
            c.caja(x, y - 7, x + 7, y, relleno=muestra)
            c.texto(x + 11, y, f["nombre"], tam=8, color=_LOG_GRIS if sin_dato else _LOG_TINTA, ancho=cols[0][1] - 15)
        else:
            c.texto(x, y, etiqueta, tam=7.5, color=_LOG_GRIS if sin_dato else _LOG_TINTA, ancho=cols[0][1] - 6)
        xx = x + cols[0][1]
        c.texto(xx, y, _log_num(f["entregas"]), tam=8, ancho=cols[1][1] - 4, alinear="der")
        xx += cols[1][1]
        c.texto(xx, y, _log_num(f["m3"], 1), tam=8, ancho=cols[2][1] - 4, alinear="der")
        xx += cols[2][1] + 8
        _log_barra_pct(c, xx, y, 64, f["pct"], _LOG_GRIS if sin_dato else _LOG_TINTA)
        c.linea(x, y + 4, x + ancho, y + 4, ancho=0.3)
    return y


def log_nombre_reporte_dia(desde: str, hasta: str) -> str:
    """Un dia conserva el nombre de siempre; un rango lleva las dos fechas."""
    if desde == hasta:
        return f"Reporte_dia_VMO_{desde}.pdf"
    return f"Reporte_VMO_{desde}_al_{hasta}.pdf"


def _log_fecha_corta(iso: str) -> str:
    f = datetime.strptime(iso, "%Y-%m-%d")
    return f"{_LOG_DIAS_SEMANA[f.weekday()][:3]} {f:%d/%m}"


def _log_tabla_bloques(c, y, bloques, nom_pct, nom_ped, separar_en=(), negrita_primero=True):
    """La tabla de bloques (General, zonas, servicios; o un renglon por dia):
    los dos % con barra y los conteos. Devuelve la y de la ultima linea."""
    M, W = _LOG_PDF_M, _LOG_PDF_W
    cols = [("", 104), (nom_pct, 135), (nom_ped, 135), ("Entregas a tiempo", 86), ("m³ a tiempo", 92),
            ("Incumplidas", 64), ("m³ despachados", 76), ("Cargues", 50), ("Camiones", 0)]
    cols[-1] = ("Camiones", W - 2 * M - sum(w for _, w in cols[:-1]))
    xx = M
    for i, (nombre, w) in enumerate(cols):
        c.texto(xx, y, nombre, tam=6.5, negrita=True, color=_LOG_GRIS, ancho=w - 6,
                alinear="izq" if i < 3 else "der")
        xx += w
    y += 4
    c.linea(M, y, W - M, y)
    for i, b in enumerate(bloques):
        if i in separar_en:
            y += 3
            c.linea(M, y, W - M, y, ancho=0.3)
        y += 15
        negrita = negrita_primero and i == 0
        c.texto(M, y, b["nombre"], tam=8.5, negrita=negrita, ancho=cols[0][1] - 6)
        xx = M + cols[0][1]
        _log_barra_pct(c, xx, y, 100, b["pct"], _LOG_AZUL)
        xx += cols[1][1]
        _log_barra_pct(c, xx, y, 100, b["pctPedidos"], _LOG_NARANJA)
        xx += cols[2][1]
        valores = [f"{b['pedidosCumplidos']} de {b['pedidos']}",
                   f"{_log_num(b['m3Cumplidos'])} de {_log_num(b['m3'])}",
                   _log_num(b["incumplidos"]), _log_num(b["m3Despachado"]),
                   _log_num(b["cargues"]), _log_num(b["camiones"], 1)]
        for (_, w), v in zip(cols[3:], valores):
            c.texto(xx, y, v, tam=8, negrita=negrita, ancho=w - 6, alinear="der")
            xx += w
    y += 8
    c.linea(M, y, W - M, y)
    return y


def _log_grafica_por_cliente(c, y, filas, tope_entregas, responsable="Cliente"):
    """Barras horizontales de las incumplidas de un responsable por compania.
    La barra se mide contra la compania con mas (`tope_entregas`), no contra
    el 100%: con 25 companias al 3% cada una, contra el 100% no se ve nada."""
    M, W = _LOG_PDF_M, _LOG_PDF_W
    cols = [("Compañía", 250, "izq"), ("Motivos", 220, "izq"), ("Incumplidas", 190, "izq"),
            ("m³", 55, "der"), ("% del servicio", 0, "der")]
    cols[-1] = ("% del servicio", W - 2 * M - sum(w for _, w, _ in cols[:-1]), "der")
    xx = M
    for nombre, w, al in cols:
        c.texto(xx, y, nombre, tam=6.5, negrita=True, color=_LOG_GRIS, ancho=w - 8, alinear=al)
        xx += w
    y += 4
    c.linea(M, y, W - M, y)
    color = _LOG_COLOR_RESPONSABLE[responsable]
    for f in filas:
        y += 14
        xx = M
        c.texto(xx, y, f["nombre"], tam=7.5, ancho=cols[0][1] - 8)
        xx += cols[0][1]
        c.texto(xx, y, f.get("detalle") or "", tam=6.5, color=_LOG_GRIS, ancho=cols[1][1] - 8)
        xx += cols[1][1]
        largo = (cols[2][1] - 30) * f["entregas"] / max(tope_entregas, 1)
        c.caja(xx, y - 8, xx + largo, y + 1, relleno=color)
        c.texto(xx + largo + 4, y, _log_num(f["entregas"]), tam=8, negrita=True)
        xx += cols[2][1]
        c.texto(xx, y, _log_num(f["m3"], 1), tam=8, ancho=cols[3][1] - 8, alinear="der")
        xx += cols[3][1]
        c.texto(xx, y, _log_pct(f["pct"]), tam=8, ancho=cols[4][1], alinear="der")
        c.linea(M, y + 4, W - M, y + 4, ancho=0.25)
    return y


def log_reporte_dia_pdf(rep: dict) -> bytes:
    """El Reporte del dia en PDF. Desde el 2026-10-21 tambien de un rango
    (desde < hasta): la pagina 1 es el rango junto, despues va una tabla con
    un renglon por dia y el detalle lleva la fecha de cada entrega."""
    M, W, H = _LOG_PDF_M, _LOG_PDF_W, _LOG_PDF_H
    desde = datetime.strptime(rep["desde"], "%Y-%m-%d")
    hasta = datetime.strptime(rep["hasta"], "%Y-%m-%d")
    es_rango = rep["desde"] != rep["hasta"]
    por_dia = rep.get("porDia") or []
    if es_rango:
        n_dias = len(por_dia)
        titulo = "Reporte del período"
        fecha_txt = (f"{desde:%d/%m/%Y} al {hasta:%d/%m/%Y} · "
                     f"{n_dias} {'día guardado' if n_dias == 1 else 'días guardados'}")
        pie = f"Reporte del período {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}"
        lapso = "del período"
    else:
        titulo = "Reporte del día"
        fecha_txt = f"{_LOG_DIAS_SEMANA[desde.weekday()]} {desde:%d/%m/%Y}"
        pie = f"Reporte del día {fecha_txt}"
        lapso = "del día"
    sup = rep.get("supuestos") or {}
    varian = set(sup.get("varian") or [])
    def minutos(clave):
        if clave in varian:
            return "varía"
        v = sup.get(clave)
        return "-" if v is None else f"{v:g} min"
    supuestos = (f"Cargue {minutos('cargue')} · Calidad {minutos('calidad')} · "
                 f"Tolerancia {minutos('tolerancia')} · Hora programada +{minutos('ajusteHora')}")
    nom_pct = rep["nombres"]["pct"]
    nom_ped = rep["nombres"]["pctPedidos"]
    doc = fitz.open()

    # ── Pagina 1: resumen, zonas/servicio y motivos ─────────────────────
    c = _LogLienzo(doc.new_page(width=W, height=H))
    _log_encabezado_pagina(c, titulo, fecha_txt, supuestos)
    gen = rep["bloques"][0]
    tarjetas = [
        (nom_pct, _log_pct(gen["pct"]), f"{_log_num(gen['m3Cumplidos'])} de {_log_num(gen['m3'])} m³ a tiempo", _LOG_AZUL),
        (nom_ped, _log_pct(gen["pctPedidos"]), f"{gen['pedidosCumplidos']} de {gen['pedidos']} entregas a tiempo", _LOG_NARANJA),
        ("Incumplidas", _log_num(gen["incumplidos"]), "entregas que llegaron tarde", None),
        ("m³ despachados", _log_num(gen["m3Despachado"]), f"todo el cargue {lapso}", None),
        ("Cargues", _log_num(gen["cargues"]), "viajes de camión", None),
        ("Camiones", _log_num(gen["camiones"], 1),
         "promedio por día (fichas distintas)" if es_rango else "fichas distintas", None),
    ]
    y0, alto, sep = M + 52, 60, 8
    ancho_t = (W - 2 * M - sep * (len(tarjetas) - 1)) / len(tarjetas)
    for i, (et, valor, sub, color) in enumerate(tarjetas):
        # Tarjeta blanca con borde y una franja arriba: del color de la
        # metrica en las dos de cumplimiento (y el numero tambien), oscura
        # en las demas.
        x = M + i * (ancho_t + sep)
        c.caja(x, y0, x + ancho_t, y0 + alto, relleno=(1, 1, 1), borde=_LOG_LINEA)
        c.caja(x, y0, x + ancho_t, y0 + 3, relleno=color or _LOG_TINTA)
        c.texto(x + 10, y0 + 17, et.upper(), tam=6.5, negrita=True, color=_LOG_GRIS, ancho=ancho_t - 16)
        c.texto(x + 10, y0 + 40, valor, tam=21, negrita=True, color=color or _LOG_TINTA)
        c.texto(x + 10, y0 + 52, sub, tam=6.5, color=_LOG_GRIS, ancho=ancho_t - 16)

    # Tabla por zona y servicio
    y = y0 + alto + 26
    c.texto(M, y, "Por zona y por servicio", tam=10, negrita=True)
    y = _log_tabla_bloques(c, y + 14, rep["bloques"], nom_pct, nom_ped, separar_en=(1, 3))
    no_eval = rep.get("noEvaluables") or []
    if no_eval:
        y += 11
        c.texto(M, y, "No entran al porcentaje: " + " · ".join(f"{n['estado']} {n['entregas']}" for n in no_eval),
                tam=7, color=_LOG_GRIS, ancho=W - 2 * M)

    # Responsables (izquierda) y motivos (derecha)
    y_abajo = y + 26
    ancho_izq = 330
    cob = rep.get("cobertura") or {}
    if cob.get("incumplidos"):
        _log_tabla_grupos(c, M, y_abajo, ancho_izq, "Incumplidas por responsable",
                          rep["porResponsable"], "responsable")
        motivos = rep["porMotivo"]
        tope = int((H - M - 40 - (y_abajo + 18)) // 13)
        extra = len(motivos) - tope
        if extra > 0:
            motivos = motivos[:tope - 1]
        yy = _log_tabla_grupos(c, M + ancho_izq + 40, y_abajo, W - 2 * M - ancho_izq - 40,
                               "Motivos de las incumplidas", motivos, "motivo")
        if extra > 0:
            c.texto(M + ancho_izq + 40, yy + 13, f"y {extra + 1} motivos más", tam=7, color=_LOG_GRIS)
        faltan = []
        if cob.get("sinMotivo"):
            faltan.append(f"{cob['sinMotivo']} sin motivo")
        if cob.get("sinResponsable"):
            faltan.append(f"{cob['sinResponsable']} sin responsable")
        if faltan:
            c.texto(M, H - M - 18, f"De {cob['incumplidos']} incumplidas, " + " y ".join(faltan)
                    + ": se cargan en el dashboard del día y se vuelve a guardar.", tam=7, color=_LOG_MAL)
    else:
        c.texto(M, y_abajo, f"Ninguna entrega incumplida {'en el período' if es_rango else 'este día'}.",
                tam=10, negrita=True, color=_LOG_OK)
    tolerancia = "la tolerancia de cada día" if "tolerancia" in varian else minutos("tolerancia")
    c.texto(M, H - M - 6,
            f"{nom_pct}: m³ de las entregas a tiempo sobre los m³ evaluados. {nom_ped}: entregas a tiempo sobre "
            f"entregas evaluadas. Una entrega cumple si su primer camión llega como máximo "
            f"{tolerancia} tarde (llegar antes cumple).",
            tam=6.5, color=_LOG_GRIS, ancho=W - 2 * M)
    if es_rango:
        c.texto(M, H - M - 28, "Los % del período juntan todas las entregas de los días guardados: "
                "no promedian los porcentajes de cada día. Camiones es el promedio por día.", tam=6.5, color=_LOG_GRIS, ancho=W - 2 * M)

    # ── Incumplidas del cliente y de VMO: por servicio y por compania ───
    # Cada responsable arranca pagina; adentro van Con bomba y Directo uno
    # debajo del otro, y una seccion que no cabe sigue en la pagina de al lado.
    for grupo in rep.get("incumplidasPorResponsable") or []:
        quien = grupo["responsable"]
        titulo_r = "Incumplidas del cliente" if quien == "Cliente" else "Incumplidas de VMO"
        n = grupo["entregas"]
        resumen = (f"{n} {'incumplida' if n == 1 else 'incumplidas'} con responsable {quien} · "
                   + " · ".join(f"{s['servicio']} {s['entregas']}" for s in grupo["servicios"]))
        # Las barras de los dos servicios se miden contra la misma compania.
        tope = max((f["entregas"] for s in grupo["servicios"] for f in s["companias"]), default=1)
        fondo = H - M - 22

        def pagina_nueva(sigue):
            cc = _LogLienzo(doc.new_page(width=W, height=H))
            _log_encabezado_pagina(cc, titulo_r, fecha_txt, supuestos)
            cc.texto(M, M + 58, resumen + (" (sigue)" if sigue else ""), tam=10, negrita=True)
            cc.texto(M, H - M - 6, f"Solo las incumplidas marcadas con responsable {quien}. El % de cada "
                     "compañía es sobre las incumplidas de ese servicio.", tam=6.5, color=_LOG_GRIS,
                     ancho=W - 2 * M)
            return cc, M + 70

        cc, y = pagina_nueva(False)
        for serv in grupo["servicios"]:
            filas = serv["companias"]
            i = 0
            while i < len(filas):
                # titulo (22) + encabezado de la tabla (20) + al menos 3 filas
                if y + 42 + 3 * 14 > fondo:
                    cc, y = pagina_nueva(True)
                caben = max(int((fondo - (y + 42)) // 14), 1)
                y += 22
                cc.texto(M, y, f"{serv['servicio']} · {serv['entregas']} "
                         f"{'incumplida' if serv['entregas'] == 1 else 'incumplidas'} · "
                         f"{_log_num(serv['m3'], 1)} m³" + (" (sigue)" if i else ""), tam=9, negrita=True,
                         color=_LOG_TINTA)
                y = _log_grafica_por_cliente(cc, y + 16, filas[i:i + caben], tope, quien) + 6
                i += caben

    # ── En un rango: un renglon por dia ─────────────────────────────────
    if es_rango and por_dia:
        filas_por_pagina = int((H - M - 20 - (M + 72)) // 15)
        for i in range(0, len(por_dia), filas_por_pagina):
            cc = _LogLienzo(doc.new_page(width=W, height=H))
            _log_encabezado_pagina(cc, "Por día", fecha_txt, supuestos)
            tanda = [{**b, "nombre": _log_fecha_corta(b["nombre"])} for b in por_dia[i:i + filas_por_pagina]]
            _log_tabla_bloques(cc, M + 58, tanda, nom_pct, nom_ped, negrita_primero=False)

    # ── Paginas siguientes: detalle de entregas ─────────────────────────
    # Estado en 72 y no 58 (2026-10-26): "Cumplido (manual)" salia cortado.
    cols = [("Cliente", 104, "izq"), ("Obra", 84, "izq"), ("Elemento", 60, "izq"), ("Servicio", 44, "izq"),
            ("Hora prog.", 44, "der"), ("m³ prog.", 34, "der"), ("m³ real", 32, "der"), ("Cam.", 28, "der"),
            ("1er cargue", 42, "der"), ("Planta", 48, "izq"), ("Llegada", 34, "der"), ("Dif.", 42, "der"),
            ("Estado", 72, "izq"), ("Resp.", 36, "izq"), ("Motivo", 0, "izq")]
    if es_rango:
        # La fecha de cada entrega, a costa de Cliente y Obra.
        cols[0] = ("Cliente", 88, "izq")
        cols[1] = ("Obra", 70, "izq")
        cols.insert(0, ("Fecha", 30, "izq"))
    cols[-1] = ("Motivo", W - 2 * M - sum(w for _, w, _ in cols[:-1]), "izq")
    entregas = rep.get("entregas") or []

    def nueva_pagina_detalle():
        cc = _LogLienzo(doc.new_page(width=W, height=H))
        _log_encabezado_pagina(cc, "Detalle de entregas", fecha_txt, "")
        yy = M + 58
        xx = M
        for nombre, w, al in cols:
            cc.texto(xx, yy, nombre, tam=6.5, negrita=True, color=_LOG_GRIS,
                     ancho=w - (5 if al == "izq" else 9), alinear=al)
            xx += w
        cc.linea(M, yy + 4, W - M, yy + 4)
        return cc, yy + 4

    if entregas:
        c, y = nueva_pagina_detalle()
        estado_previo = fecha_previa = None
        for e in entregas:
            alto = 12 + (9 if e.get("observacion") else 0)
            if y + alto > H - M - 8:
                c, y = nueva_pagina_detalle()
                estado_previo = fecha_previa = None
            # Entre dias, una linea oscura; entre estados del mismo dia, gris.
            if fecha_previa is not None and e.get("fecha") != fecha_previa:
                c.linea(M, y + 1, W - M, y + 1, color=_LOG_TINTA, ancho=0.8)
            elif estado_previo is not None and e["estado"] != estado_previo:
                c.linea(M, y + 1, W - M, y + 1, color=_LOG_GRIS, ancho=0.5)
            estado_previo = e["estado"]
            fecha_previa = e.get("fecha")
            y += 11
            color_estado = {"Incumplido": _LOG_MAL, "Cumplido": _LOG_OK,
                            "Cumplido (manual)": _LOG_OK}.get(e["estado"], _LOG_GRIS)
            valores = [e["cliente"], e["obra"], e["elemento"], e["servicio"], _log_hhmm(e["horaProg"]),
                       _log_num(e["cantProg"], 1), _log_num(e["cantReal"], 1), _log_num(e["cargues"]),
                       _log_hhmm(e["primerCargue"]), e["planta"], _log_hhmm(e["llegada"]), _log_dif(e["diff"]),
                       e["estado"], e["responsable"], e["motivo"]]
            if es_rango:
                valores.insert(0, f"{e['fecha'][8:10]}/{e['fecha'][5:7]}" if e.get("fecha") else "")
            xx = M
            for (nombre, w, al), v in zip(cols, valores):
                es_estado = nombre == "Estado"
                c.texto(xx, y, v, tam=7, negrita=es_estado and e["estado"] == "Incumplido",
                        color=color_estado if es_estado or nombre == "Dif." else _LOG_TINTA,
                        ancho=w - (5 if al == "izq" else 9), alinear=al)
                xx += w
            if e.get("observacion"):
                y += 9
                c.texto(M + 8, y, "Obs.: " + e["observacion"], tam=6.5, color=_LOG_GRIS, ancho=W - 2 * M - 8)
            c.linea(M, y + 3, W - M, y + 3, ancho=0.25)

    n = doc.page_count
    for i, pagina in enumerate(doc, 1):
        _log_pie(_LogLienzo(pagina), pie, i, n)
    contenido = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return contenido


# =====================================================================
# COMERCIAL (2026-10-19)
# =====================================================================
#
# El dashboard comercial que hasta hoy era un Excel ("DASHBOARD COMERCIAL
# 2026"): cada mes se pegaba el DESPACHOS del mes en la hoja ACUMULADO y se
# refrescaban 8 tablas dinamicas. Aca se replica igual, con la misma logica.
#
# Ambiente separado (regla del usuario): base propia y su propia carga. No
# lee ni escribe las bases de Conduces, Estimaciones ni Logistica, aunque
# hablen de los mismos conduces.
#
# Igual que Logistica, la base es un deposito: guarda las filas tal como
# vienen y el calculo del dashboard vive en static/comercial.logic.js.
#
# Dos cosas se suben:
#   - Los despachos del mes (el DESPACHOS SEPTIEMBRE 2026.xls de cada mes, o
#     la hoja ACUMULADO del dashboard para la carga inicial). Cada mes que
#     trae el archivo REEMPLAZA a ese mes en la base.
#   - El plan comercial (rolling forecast). El Excel solo usa la fila
#     "DESPACHOS HORMIGON" (m3 de hormigon planificados por mes) para el
#     cumplimiento; es lo unico que se guarda. Un plan nuevo reemplaza los
#     meses que trae.

COM_DB_PATH = os.path.join(BASE_DIR, "comercial", "db", "comercial.db")
COM_EXCEL_MAX_BYTES = 25 * 1024 * 1024
# La hoja ACUMULADO de enero a septiembre trae 38.323 filas; un ano entero
# rondaria las 55.000. El tope deja margen y frena un archivo equivocado.
COM_MAX_FILAS = 150000

# Las 17 columnas del despachos, en orden, con los nombres que traen los dos
# formatos reales: el DESPACHOS del mes (COLUMN1, idPlanta, idCliente...) y la
# hoja ACUMULADO (VENDEDOR, PLANTA, ID CLIENTE...). Se comparan sin espacios,
# puntos ni mayusculas.
COM_COLUMNAS = (
    ("vendedor", ("VENDEDOR", "COLUMN1")),
    ("planta", ("PLANTA", "IDPLANTA")),
    ("id_cliente", ("IDCLIENTE",)),
    ("cliente", ("CLIENTE",)),
    ("conduce", ("CONDUCE",)),
    ("fecha", ("FECHA",)),
    ("categoria", ("CATEGORIA",)),
    ("condicion", ("CONDICION", "IDCONDICION")),
    ("id_producto", ("IDPRODUCTO",)),
    ("producto", ("PRODUCTO",)),
    ("cantidad", ("CANTIDAD",)),
    ("precio", ("PRECIO",)),
    ("line_total", ("LINETOTAL",)),
    ("precio_minimo", ("PRECIOMINIMO", "PRECIOMIN")),
    ("direccion", ("DIRECCION",)),
    ("zona", ("ZONA",)),
    ("rango_fc", ("RANGOFC",)),
)
COM_NUMERICAS = ("cantidad", "precio", "line_total", "precio_minimo")
COM_MESES = ("ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO",
             "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE")


class ComercialArchivoInvalido(ValueError):
    """El archivo no tiene el formato esperado. El mensaje va tal cual a la
    pantalla de carga, asi que se escribe para quien sube el archivo."""


def _com_conn():
    os.makedirs(os.path.dirname(COM_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(COM_DB_PATH, isolation_level=None)
    return conn


def setup_comercial_db(conn=None):
    """Crea las tablas si no estan. Idempotente, como setup_logistica_db()."""
    propia = conn is None
    conn = conn or _com_conn()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS comercial_despacho (
            mes TEXT NOT NULL,              -- YYYY-MM, la llave del reemplazo
            vendedor TEXT, planta TEXT, id_cliente TEXT, cliente TEXT,
            conduce TEXT, fecha TEXT NOT NULL, categoria TEXT, condicion TEXT,
            id_producto TEXT, producto TEXT,
            cantidad REAL NOT NULL, precio REAL, line_total REAL, precio_minimo REAL,
            direccion TEXT, zona TEXT, rango_fc TEXT
        );
        CREATE INDEX IF NOT EXISTS ix_comercial_despacho_mes ON comercial_despacho(mes);
        CREATE TABLE IF NOT EXISTS comercial_plan (
            mes TEXT PRIMARY KEY,           -- YYYY-MM
            m3 REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS comercial_carga (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,             -- 'despachos' | 'plan'
            archivo TEXT NOT NULL,
            meses TEXT NOT NULL,            -- JSON: ["2026-09", ...]
            filas INTEGER NOT NULL,
            m3 REAL NOT NULL,
            cargado_en TEXT NOT NULL
        );
        """)
        # El precio presupuestado del mes (2026-10-21): la fila PRECIO
        # DIRECTO, MES del plan. Las bases de antes no tienen la columna.
        if "precio" not in [r[1] for r in conn.execute("PRAGMA table_info(comercial_plan)")]:
            conn.execute("ALTER TABLE comercial_plan ADD COLUMN precio REAL")
    finally:
        if propia:
            conn.close()


def _com_clave_columna(texto) -> str:
    return re.sub(r"[\s._]", "", str(texto or "")).upper()


def _com_texto(v):
    """Texto limpio. El Excel trae 'PUNTA CANA ' y 'PUNTA CANA' como zonas
    distintas segun el mes; recortado, la tabla dinamica de un ano entero los
    junta, que es lo que muestra el dashboard."""
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).strip()
    return s or None


def _com_hojas(contenido: bytes, nombre: str):
    """Las hojas del archivo como (nombre, filas). Acepta .xls (el DESPACHOS
    que exporta el sistema) y .xlsx (el ACUMULADO del dashboard). Las fechas
    del .xls llegan como numero de serie y se convierten aca."""
    ext = os.path.splitext(nombre.lower())[1]
    if ext == ".xls":
        try:
            libro = xlrd.open_workbook(file_contents=contenido)
        except Exception:
            raise ComercialArchivoInvalido("No se pudo abrir el archivo .xls.")
        hojas = []
        for h in libro.sheets():
            filas = []
            for i in range(h.nrows):
                fila = []
                for c in h.row(i):
                    if c.ctype == xlrd.XL_CELL_DATE:
                        fila.append(xlrd.xldate_as_datetime(c.value, libro.datemode))
                    elif c.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                        fila.append(None)
                    else:
                        fila.append(c.value)
                filas.append(fila)
            hojas.append((h.name, filas))
        return hojas
    if ext in (".xlsx", ".xlsm"):
        try:
            libro = openpyxl.load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
        except Exception:
            raise ComercialArchivoInvalido("No se pudo abrir el archivo .xlsx.")
        try:
            return [(h.title, [list(f) for f in h.iter_rows(values_only=True)]) for h in libro.worksheets]
        finally:
            libro.close()
    raise ComercialArchivoInvalido("El archivo tiene que ser Excel (.xls o .xlsx).")


def _com_fecha(v, datemode=0):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)) and v > 0:
        # Un .xlsx con la columna como numero en vez de fecha.
        return (datetime(1899, 12, 30) + timedelta(days=float(v))).date()
    if isinstance(v, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(v.strip(), fmt).date()
            except ValueError:
                pass
    return None


def com_leer_despachos(contenido: bytes, nombre: str) -> list[dict]:
    """Las filas de despachos del archivo, una por linea de conduce.

    De todas las hojas usa la mas grande que tenga las 17 columnas: el
    DESPACHOS del mes trae ademas SDQ, PROYECTOS y PUNTA CANA, que son
    pedazos de la misma hoja y no se suman.
    """
    candidatas = []
    for nombre_hoja, filas in _com_hojas(contenido, nombre):
        for i, fila in enumerate(filas[:5]):
            claves = [_com_clave_columna(c) for c in fila]
            indices = {}
            for campo, alias in COM_COLUMNAS:
                pos = next((j for j, k in enumerate(claves) if k in alias), None)
                if pos is not None:
                    indices[campo] = pos
            if len(indices) == len(COM_COLUMNAS):
                candidatas.append((len(filas) - i - 1, nombre_hoja, i, indices, filas))
                break
    if not candidatas:
        esperadas = ", ".join(a[0] for _, a in COM_COLUMNAS)
        raise ComercialArchivoInvalido(
            f"Ninguna hoja tiene las 17 columnas del despachos ({esperadas}).")
    _, nombre_hoja, fila_titulos, indices, filas = max(candidatas, key=lambda c: c[0])

    salida, errores = [], []
    for n, fila in enumerate(filas[fila_titulos + 1:], start=fila_titulos + 2):
        valores = {campo: (fila[pos] if pos < len(fila) else None) for campo, pos in indices.items()}
        if all(v is None or (isinstance(v, str) and not v.strip()) for v in valores.values()):
            continue
        f = _com_fecha(valores["fecha"])
        if f is None:
            errores.append(f"fila {n}: fecha vacía o inválida")
            continue
        registro = {campo: _com_texto(valores[campo]) for campo, _ in COM_COLUMNAS
                    if campo not in COM_NUMERICAS and campo != "fecha"}
        for campo in COM_NUMERICAS:
            v = valores[campo]
            if v is None or (isinstance(v, str) and not v.strip()):
                registro[campo] = None
                continue
            # Un numero escrito como texto ("56,000.00", "RD$ 8,000") se lee
            # igual; uno que no se puede leer es error, como la cantidad (#175,
            # 2026-10-23). Antes LINE TOTAL o PRECIO en texto quedaban vacios
            # sin aviso y esa fila sumaba RD$ 0 a lo vendido.
            if isinstance(v, str):
                v = re.sub(r"RD\$|\s|,", "", v, flags=re.I)
            try:
                registro[campo] = float(v)
            except (TypeError, ValueError):
                registro[campo] = None
                errores.append(f"fila {n}: {campo.replace('_', ' ')} no es un número ({valores[campo]!r})")
        if registro["cantidad"] is None and not any(e.startswith(f"fila {n}:") for e in errores):
            errores.append(f"fila {n}: cantidad vacía")
        registro["fecha"] = f.isoformat()
        registro["mes"] = f.strftime("%Y-%m")
        salida.append(registro)
    if errores:
        extra = f" y {len(errores) - 10} más" if len(errores) > 10 else ""
        raise ComercialArchivoInvalido(
            f"La hoja '{nombre_hoja}' tiene filas que no se pueden leer: "
            + "; ".join(errores[:10]) + extra + ".")
    if not salida:
        raise ComercialArchivoInvalido(f"La hoja '{nombre_hoja}' no tiene despachos.")
    if len(salida) > COM_MAX_FILAS:
        raise ComercialArchivoInvalido(
            f"El archivo trae {len(salida):,} filas; el máximo es {COM_MAX_FILAS:,}.")
    return salida


def _com_fila_del_plan(contenido: bytes, nombre: str, clave: str, etiqueta: str) -> dict[str, float] | None:
    """{YYYY-MM: valor} de la fila `clave` del plan comercial (sin espacios ni
    signos, como _com_clave_columna). Los meses salen de los titulos de arriba
    ("Plan Septiembre 2026"). None si el plan no trae esa fila."""
    for _, filas in _com_hojas(contenido, nombre):
        for i, fila in enumerate(filas):
            col = next((j for j, v in enumerate(fila)
                        if isinstance(v, str) and _com_clave_columna(v) == clave), None)
            if col is None:
                continue
            titulos = next((filas[k] for k in range(i - 1, -1, -1)
                            if any(isinstance(v, str) and v.strip().upper().startswith("PLAN ") for v in filas[k])), None)
            if titulos is None:
                raise ComercialArchivoInvalido(
                    f"Se encontró la fila {etiqueta} pero no los títulos 'Plan <mes> <año>' arriba.")
            plan = {}
            for j, t in enumerate(titulos):
                m = re.match(r"^\s*PLAN\s+([A-ZÁÉÍÓÚ]+)\s+(\d{4})\s*$", str(t or "").upper())
                if not m or m.group(1) not in COM_MESES or j >= len(fila):
                    continue
                v = fila[j]
                if not isinstance(v, (int, float)):
                    raise ComercialArchivoInvalido(
                        f"{etiqueta} de {m.group(1).capitalize()} {m.group(2)} no es un número "
                        "(¿el Excel se guardó con las fórmulas sin calcular?).")
                plan[f"{m.group(2)}-{COM_MESES.index(m.group(1)) + 1:02d}"] = float(v)
            return plan
    return None


def com_leer_plan(contenido: bytes, nombre: str) -> dict[str, float]:
    """{YYYY-MM: m3} de la fila DESPACHOS HORMIGON del plan comercial, que es
    la que usa el dashboard para el cumplimiento ('DASHB COMERCIAL 2026'!B337:
    m3 vendidos del mes / 'Comercializacion Hormigon'!N3)."""
    plan = _com_fila_del_plan(contenido, nombre, "DESPACHOSHORMIGON", "La fila DESPACHOS HORMIGON")
    if plan is None:
        raise ComercialArchivoInvalido(
            "No se encontró la fila 'DESPACHOS HORMIGON' (hoja Comercializacion Hormigon del plan comercial).")
    if not plan:
        raise ComercialArchivoInvalido("La fila DESPACHOS HORMIGON no trae ningún mes de plan.")
    return plan


def com_leer_precio_plan(contenido: bytes, nombre: str) -> dict[str, float]:
    """{YYYY-MM: RD$/m3} de la fila PRECIO DIRECTO, MES del plan (2026-10-21):
    el precio presupuestado, que el plan calcula como INGRESOS DIRECTO, MES /
    DESPACHOS HORMIGON. Va contra el precio real (RD$ vendidos / m3) en el
    indicador "precio vs ppto". Opcional: un plan sin la fila sube igual, sin
    precio; un mes en 0 (el IFERROR del plan) queda sin precio."""
    precios = _com_fila_del_plan(contenido, nombre, "PRECIODIRECTO,MES", "El precio del plan") or {}
    return {m: v for m, v in precios.items() if v > 0}


def com_resumen_despachos(filas: list[dict], conn) -> list[dict]:
    """Por cada mes del archivo: filas, m3 y RD$, y lo que ya hay guardado de
    ese mes (que es lo que se va a reemplazar)."""
    por_mes = {}
    for f in filas:
        r = por_mes.setdefault(f["mes"], {"mes": f["mes"], "filas": 0, "m3": 0.0, "rd": 0.0})
        r["filas"] += 1
        r["m3"] += f["cantidad"] or 0
        r["rd"] += f["line_total"] or 0
    for mes, r in por_mes.items():
        actual = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(cantidad), 0) FROM comercial_despacho WHERE mes = ?",
            (mes,)).fetchone()
        r["filas_actuales"], r["m3_actuales"] = actual
    return [por_mes[m] for m in sorted(por_mes)]


def com_guardar_despachos(filas: list[dict], archivo: str, conn) -> list[str]:
    """Reemplaza cada mes que trae el archivo. Todo o nada."""
    meses = sorted({f["mes"] for f in filas})
    campos = ["mes", "fecha"] + [c for c, _ in COM_COLUMNAS if c != "fecha"]
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.executemany("DELETE FROM comercial_despacho WHERE mes = ?", [(m,) for m in meses])
        conn.executemany(
            f"INSERT INTO comercial_despacho ({', '.join(campos)}) VALUES ({', '.join('?' * len(campos))})",
            [tuple(f[c] for c in campos) for f in filas])
        conn.execute(
            "INSERT INTO comercial_carga (tipo, archivo, meses, filas, m3, cargado_en) VALUES (?, ?, ?, ?, ?, ?)",
            ("despachos", archivo, json.dumps(meses), len(filas),
             sum(f["cantidad"] or 0 for f in filas), datetime.now().isoformat(timespec="seconds")))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return meses


def com_guardar_plan(plan: dict[str, float], archivo: str, conn, precios: dict[str, float] | None = None) -> list[str]:
    meses = sorted(plan)
    precios = precios or {}
    conn.execute("BEGIN IMMEDIATE")
    try:
        # Un mes sin precio en el archivo conserva el que ya estaba (#174,
        # 2026-10-23): un plan sin la fila PRECIO DIRECTO, MES lo dejaba en
        # NULL sin avisar, y precio y ventas vs ppto pasaban a "—".
        conn.executemany(
            "INSERT INTO comercial_plan (mes, m3, precio) VALUES (?, ?, ?) "
            "ON CONFLICT(mes) DO UPDATE SET m3 = excluded.m3, "
            "precio = COALESCE(excluded.precio, comercial_plan.precio)",
            [(m, plan[m], precios.get(m)) for m in meses])
        conn.execute(
            "INSERT INTO comercial_carga (tipo, archivo, meses, filas, m3, cargado_en) VALUES (?, ?, ?, ?, ?, ?)",
            ("plan", archivo, json.dumps(meses), len(meses), sum(plan.values()),
             datetime.now().isoformat(timespec="seconds")))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return meses


# Las columnas que usa el dashboard (las 7 de los filtros mas los numeros).
# Las de texto van como indice a una lista de valores distintos: 38.000 filas
# con el nombre del cliente repetido pesarian varias veces mas.
COM_DIMENSIONES = ("vendedor", "planta", "cliente", "condicion", "zona", "rango_fc")

# El plan ORIGINAL de los meses que el rolling forecast ya reemplazo por lo real
# (#180, 2026-10-23). El vs ppto del Excel ('DASHB COMERCIAL 2026'!B329:B337)
# divide Ene-Jun por '[1]Comercializacion Hormigon'!F3:K3, que es "PLAN
# COMERCIAL 2026 ACT.xlsx", y Jul-Sep por el ROLLING FORECAST. En el rolling,
# Ene-Jun traen los m3 reales (Ene 23.524 contra 23.526,5 vendidos), asi que
# el acumulado comparaba real contra real y daba 107% en vez de 126%.
# Los valores son los que el Excel del dashboard guarda de ese archivo (el ACT
# no esta en la PC); son el presupuesto del ano y no cambian. Ese archivo solo
# trae m3: los meses de aca no tienen precio de plan, porque el del rolling en
# esos meses tambien es el real. Para 2027 hay que agregar su plan original.
COM_PLAN_ORIGINAL = {
    "2026-01": 23270.5, "2026-02": 25959.341139255164, "2026-03": 27652.000000000007,
    "2026-04": 26437.5, "2026-05": 27917.500000000004, "2026-06": 28787.000000000007,
}


def com_datos_dashboard(conn, anio: int) -> dict:
    valores = {d: [] for d in COM_DIMENSIONES}
    indice = {d: {} for d in COM_DIMENSIONES}

    # Nombres que solo cambian en mayusculas ("OFICINA" y "Oficina") son uno
    # solo, como en la tabla dinamica del Excel, que no las distingue (#179,
    # 2026-10-23). Se muestra la primera forma del ano; lo guardado no cambia.
    def idx(dim, v):
        v = v or ""
        k = v.casefold()
        if k not in indice[dim]:
            indice[dim][k] = len(valores[dim])
            valores[dim].append(v)
        return indice[dim][k]

    filas = []
    for r in conn.execute(
            f"SELECT mes, {', '.join(COM_DIMENSIONES)}, cantidad, precio, line_total "
            "FROM comercial_despacho WHERE mes LIKE ? ORDER BY fecha", (f"{anio:04d}-%",)):
        mes = int(r[0][5:7])
        filas.append([mes] + [idx(d, r[1 + i]) for i, d in enumerate(COM_DIMENSIONES)]
                     + [r[7] or 0, r[8], r[9] or 0])
    plan, plan_precio = {}, {}
    for m, m3, precio in conn.execute(
            "SELECT mes, m3, precio FROM comercial_plan WHERE mes LIKE ?", (f"{anio:04d}-%",)):
        if m in COM_PLAN_ORIGINAL:
            continue
        plan[int(m[5:7])] = m3
        if precio is not None:
            plan_precio[int(m[5:7])] = precio
    for m, m3 in COM_PLAN_ORIGINAL.items():
        if m.startswith(f"{anio:04d}-"):
            plan[int(m[5:7])] = m3
    anios = [int(a) for (a,) in conn.execute(
        "SELECT DISTINCT substr(mes, 1, 4) FROM comercial_despacho ORDER BY 1")]
    return {"anio": anio, "anios": anios, "dimensiones": list(COM_DIMENSIONES), "valores": valores,
            "filas": filas, "plan": plan, "planPrecio": plan_precio}


def com_cargas(conn, limite: int = 50) -> list[dict]:
    return [{"id": i, "tipo": t, "archivo": a, "meses": json.loads(m), "filas": f, "m3": x, "cargado_en": c}
            for i, t, a, m, f, x, c in conn.execute(
                "SELECT id, tipo, archivo, meses, filas, m3, cargado_en FROM comercial_carga "
                "ORDER BY id DESC LIMIT ?", (limite,))]
