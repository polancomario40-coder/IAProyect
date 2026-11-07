# by a_oller
"""
routes_conduces.py — las 9 rutas HTTP de Conduces (issue #4, Fase 2).

Referencia config/estado mutable compartido (DB_PATH, REPORTES_DIR,
FACTURAS_DIR, active_tokens, login_attempts, LOGIN_USER/PASS, client,
SYSTEM_PROMPT, TOOLS) via `core.NOMBRE` en vez de `from core import NOMBRE`
— ver el docstring de core.py para el porque (evita el bug de monkeypatch
sobre una copia importada por valor). Funciones puras de negocio si se
importan directo, son seguras.
"""
import asyncio
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

import core
import seguridad
from core import (
    verificar_token,
    generar_reporte,
    generar_reporte_compania,
    generar_factura,
    consultar_conduces,
    _nombre_archivo_seguro,
)

router = APIRouter()


class LoginRequest(BaseModel):
    usuario: str = Field(max_length=200)
    contrasena: str = Field(max_length=200)

@router.post("/login")
async def login(req: LoginRequest, request: Request):
    ahora = datetime.now()
    ip = seguridad.ip_cliente(request)
    seguridad.purgar_intentos_vencidos(ahora)
    intento = core.login_attempts.get(ip, {"fallos": 0, "bloqueado_hasta": None})

    if intento["bloqueado_hasta"] and ahora < intento["bloqueado_hasta"]:
        raise HTTPException(status_code=429, detail="Demasiados intentos fallidos. Intenta más tarde.")
    if seguridad.bloqueo_global_activo(ahora):
        raise HTTPException(status_code=429, detail="Demasiados intentos fallidos. Intenta más tarde.")

    if seguridad.credenciales_correctas(req.usuario, req.contrasena):
        core.login_attempts.pop(ip, None)
        token = secrets.token_urlsafe(32)
        core.active_tokens[token] = ahora
        return {"token": token}

    seguridad.registrar_fallo_global(ahora)
    intento["fallos"] += 1
    if intento["fallos"] >= core.LOGIN_MAX_INTENTOS:
        intento["bloqueado_hasta"] = datetime.now() + timedelta(minutes=core.LOGIN_BLOQUEO_MINUTOS)
        intento["fallos"] = 0
    core.login_attempts[ip] = intento
    raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

@router.post("/logout")
async def logout(authorization: str = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        core.active_tokens.pop(token, None)
    return {"ok": True}


class ReporteRequest(BaseModel):
    fecha_desde: core.FechaISO | None = None
    fecha_hasta: core.FechaISO | None = None

class ReporteCompaniaRequest(BaseModel):
    compania: str
    fecha_desde: core.FechaISO | None = None
    fecha_hasta: core.FechaISO | None = None

def _respuesta_reporte(data: dict, prefijo_descarga: str) -> dict:
    """Arma la respuesta de las rutas que generan un HTML descargable.

    Issue #31: `sin_precio` viaja hasta el cliente. La primitiva de core lo
    devuelve, pero estas rutas rearmaban la respuesta a mano y lo tiraban junto
    con `total`/`pagados`/`pendientes` — se descubrio pegandole por HTTP al
    servidor DESPUES de mergear, porque los tests del #31 llamaban a
    core.generar_reporte() directo y nunca pasaban por aca.

    `sin_precio` es None cuando la respuesta salio del cache: ese camino no
    recalcula nada, asi que el conteo no se conoce. **None significa "no se
    sabe", NO significa cero** — quien lo consuma tiene que mirar `cached`
    primero. Se devuelve la clave siempre, con None explicito, para que la
    ausencia no se confunda con una version vieja de la API.
    """
    return {
        "download_url": f"{prefijo_descarga}/{data['filename']}",
        "cached": data.get("cached", False),
        "sin_precio": data.get("sin_precio"),
    }


@router.post("/api/generar-reporte")
async def api_generar_reporte(req: ReporteRequest, authorization: str = Header(None)):
    verificar_token(authorization)
    resultado = generar_reporte(req.fecha_desde, req.fecha_hasta)
    data = json.loads(resultado)
    return _respuesta_reporte(data, "/download")

@router.post("/api/generar-reporte-compania")
async def api_generar_reporte_compania(req: ReporteCompaniaRequest, authorization: str = Header(None)):
    verificar_token(authorization)
    resultado = generar_reporte_compania(req.compania, req.fecha_desde, req.fecha_hasta)
    data = json.loads(resultado)
    return _respuesta_reporte(data, "/download")

class FacturaRequest(BaseModel):
    compania: str
    fecha_desde: core.FechaISO | None = None
    fecha_hasta: core.FechaISO | None = None
    conduces: list[str] = []

@router.post("/api/generar-factura")
async def api_generar_factura(req: FacturaRequest, authorization: str = Header(None)):
    verificar_token(authorization)
    if not req.compania:
        raise HTTPException(status_code=400, detail="Se requiere una compañía")
    resultado = generar_factura(req.compania, req.fecha_desde, req.fecha_hasta, req.conduces or None)
    data = json.loads(resultado)
    return _respuesta_reporte(data, "/download-factura")

@router.get("/download-factura/{filename}")
async def download_factura(filename: str, authorization: str = Header(None)):
    verificar_token(authorization)
    filename = _nombre_archivo_seguro(filename)
    filepath = os.path.join(core.FACTURAS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return FileResponse(filepath, media_type="text/html", filename=filename)

@router.get("/companias")
async def get_companias(authorization: str = Header(None)):
    verificar_token(authorization)
    conn = sqlite3.connect(core.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT compania FROM conduces ORDER BY compania")
    companias = [row[0] for row in cursor.fetchall()]
    conn.close()
    return {"companias": companias}


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


# Topes del chat (auditoria de seguridad 2026-10-07). El historial lo manda el
# navegador y se reenvia entero a Opus en cada vuelta, y el bucle de
# herramientas no tenia fin: un historial inflado, o un modelo que pide
# herramientas sin parar, se traducia en dolares por pedido.
CHAT_MAX_MENSAJES = 60
CHAT_MAX_BYTES_HISTORIAL = 200_000
CHAT_MAX_BYTES_MENSAJE = 4_000
CHAT_MAX_VUELTAS = 5
CHAT_MAX_IDS = 200


def _validar_historial(req: ChatRequest):
    if len(req.message.encode("utf-8")) > CHAT_MAX_BYTES_MENSAJE:
        raise HTTPException(status_code=413, detail="El mensaje es demasiado largo.")
    if len(req.history) > CHAT_MAX_MENSAJES:
        raise HTTPException(status_code=413, detail="La conversación es demasiado larga: empezá una nueva.")
    if len(json.dumps(req.history, ensure_ascii=False).encode("utf-8")) > CHAT_MAX_BYTES_HISTORIAL:
        raise HTTPException(status_code=413, detail="La conversación es demasiado larga: empezá una nueva.")
    # Solo turnos de usuario y de asistente: sin esto el navegador podia
    # inventar turnos con cualquier rol.
    if any(not isinstance(m, dict) or m.get("role") not in ("user", "assistant") for m in req.history):
        raise HTTPException(status_code=422, detail="Historial inválido.")


def _ejecutar_herramienta(block) -> tuple[str, str | None, dict | None]:
    """Corre una herramienta que pidio el modelo. Devuelve (resultado para el
    modelo, download_url, consulta_data). Un error se le devuelve al modelo
    como resultado —por ejemplo una fecha que no es AAAA-MM-DD— en vez de
    tumbar el pedido con un 500."""
    entrada = block.input or {}
    try:
        if block.name == "consultar_conduces":
            ids = entrada.get("ids") or []
            if not isinstance(ids, list):
                ids = [ids]
            resultado = consultar_conduces([str(i) for i in ids[:CHAT_MAX_IDS]])
            return resultado, None, json.loads(resultado)
        if block.name == "generar_reporte":
            resultado = generar_reporte(entrada.get("fecha_desde"), entrada.get("fecha_hasta"))
            return resultado, f"/download/{json.loads(resultado)['filename']}", None
        if block.name == "generar_reporte_compania":
            resultado = generar_reporte_compania(
                str(entrada.get("compania") or ""), entrada.get("fecha_desde"), entrada.get("fecha_hasta"))
            return resultado, f"/download/{json.loads(resultado)['filename']}", None
        return json.dumps({"error": "herramienta no encontrada"}), None, None
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False), None, None


@router.post("/chat")
async def chat(req: ChatRequest, authorization: str = Header(None)):
    verificar_token(authorization)
    _validar_historial(req)
    messages = req.history + [{"role": "user", "content": req.message}]
    download_url = None
    consulta_data = None

    for _ in range(CHAT_MAX_VUELTAS):
        # En un hilo: la llamada es sincronica y, adentro de un `async def`,
        # congelaba el servidor para todos los usuarios mientras Opus pensaba.
        response = await asyncio.to_thread(
            core.client.messages.create,
            model="claude-opus-4-6",
            max_tokens=4096,
            system=core.SYSTEM_PROMPT,
            tools=core.TOOLS,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            text = next((b.text for b in response.content if b.type == "text"), "")
            new_history = messages + [{"role": "assistant", "content": text}]
            return JSONResponse(content={"response": text, "history": new_history, "download_url": download_url, "consulta_data": consulta_data}, media_type="application/json; charset=utf-8")

        if response.stop_reason != "tool_use":
            break

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                resultado, url, consulta = _ejecutar_herramienta(block)
                download_url = url or download_url
                consulta_data = consulta if consulta is not None else consulta_data
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": resultado
                })

        messages.append({
            "role": "assistant",
            "content": [b.model_dump() for b in response.content]
        })
        messages.append({"role": "user", "content": tool_results})

    return {"response": "Error procesando la solicitud.", "history": messages, "download_url": None}


@router.get("/download/{filename}")
async def download(filename: str, authorization: str = Header(None)):
    verificar_token(authorization)
    filename = _nombre_archivo_seguro(filename)
    filepath = os.path.join(core.REPORTES_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(filepath, media_type="text/html", filename=filename)
