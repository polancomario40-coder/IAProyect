"""
seguridad.py — la puerta de entrada: lo que se revisa ANTES de que FastAPI lea
una sola linea del pedido. Auditoria OWASP ASVS del 2026-10-07, previa a
publicar la app en internet.

Por que un middleware y no `verificar_token()` en cada ruta (que sigue estando):
FastAPI lee y valida el cuerpo entero ANTES de entrar al handler, asi que el
`verificar_token()` de la primera linea llega tarde. Un anonimo podia mandar un
multipart de varios GB a /api/estimaciones/procesar-zip —Starlette lo vuelca a
disco temporal sin tope— o un JSON gigante a /api/logistica/dias, y llenar el
disco o la RAM sin haber hecho login. Ademas, la proteccion ruta por ruta
depende de no olvidarse nunca la llamada; aca una ruta nueva bajo /api/ nace
protegida (y tests/test_seguridad.py falla si aparece una ruta fuera de los
prefijos protegidos).

Tres cosas:
  1. Token valido para todo lo que no sea /login, /logout o un archivo de
     static/ (el portal es publico antes del login; los datos no).
  2. Tope de tamano del cuerpo por ruta, contando los bytes que llegan (no
     alcanza con Content-Length: puede faltar si el envio es por partes).
  3. Cabeceras de seguridad en TODAS las respuestas (CSP, nosniff,
     frame-ancestors, y HSTS en produccion).
"""
import hmac
import json
import os
from collections import deque
from datetime import datetime, timedelta

from fastapi import HTTPException

import core

# Produccion = la app publicada. Cambia tres cosas: exige credenciales fuertes
# al arrancar, apaga /docs y /openapi.json, y manda HSTS. En la PC de
# desarrollo queda apagado: scripts/cierre.py usa /openapi.json para reconocer
# el servidor local.
PRODUCCION = os.getenv("PRODUCCION") == "1"

# Rutas de la API: todo lo que empieza asi exige token antes de leer el cuerpo.
# /docs y /openapi.json NO estan: en produccion directamente no existen, y en
# la PC de desarrollo scripts/cierre.py le pide /openapi.json al servidor sin
# token para reconocerlo antes de cerrarlo.
PREFIJOS_PROTEGIDOS = ("/api/", "/chat", "/download", "/companias")
RUTAS_PUBLICAS = ("/login", "/logout")

MB = 1024 * 1024
# El ZIP de escaneos (EST_ZIP_MAX_BYTES) + el Excel (EST_EXCEL_MAX_BYTES) + el
# envoltorio multipart. Un dia de logistica con LOG_MAX_FILAS filas ronda los
# 6 MB. Todo lo demas son formularios chicos.
LIMITE_POR_RUTA = {
    "/api/estimaciones/procesar-zip": core.EST_ZIP_MAX_BYTES + core.EST_EXCEL_MAX_BYTES + 5 * MB,
    "/api/logistica/dias": 16 * MB,
    # Comercial: el Excel de despachos o el ACUMULADO del ano (~5 MB hoy).
    "/api/comercial/despachos": core.COM_EXCEL_MAX_BYTES + 2 * MB,
    "/api/comercial/plan": core.COM_EXCEL_MAX_BYTES + 2 * MB,
}
LIMITE_POR_DEFECTO = 2 * MB

# Lo que el navegador tiene permitido cargar. 'unsafe-inline' en script-src
# porque index.html usa onclick/onchange en linea; sacarlos es trabajo aparte.
# Aun asi esta politica corta lo que importa: que un script inyectado mande el
# token a otro sitio (connect-src 'self') y que otro sitio meta el portal en
# un iframe (frame-ancestors 'self').
CSP = "; ".join([
    "default-src 'self'",
    # Sin CDN: SheetJS se sirve desde static/vendor (PR #108).
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: blob:",
    "connect-src 'self'",
    "frame-ancestors 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
])


def cabeceras_de_seguridad() -> list[tuple[bytes, bytes]]:
    cabeceras = [
        (b"content-security-policy", CSP.encode()),
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"SAMEORIGIN"),
        (b"referrer-policy", b"same-origin"),
    ]
    if PRODUCCION:
        cabeceras.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))
    return cabeceras


def requiere_token(ruta: str) -> bool:
    if ruta in RUTAS_PUBLICAS:
        return False
    return ruta.startswith(PREFIJOS_PROTEGIDOS)


def limite_de(ruta: str) -> int:
    return LIMITE_POR_RUTA.get(ruta, LIMITE_POR_DEFECTO)


class _CuerpoDemasiadoGrande(HTTPException):
    """Es un HTTPException a proposito: FastAPI re-lanza los HTTPException que
    salen de leer el cuerpo (en vez de convertirlos en un 400 generico), asi
    que el cliente recibe el 413 aunque el corte pase a mitad del multipart."""

    def __init__(self, limite: int):
        super().__init__(status_code=413, detail=f"El envío supera el máximo de {limite // MB} MB.")


class PuertaDeEntrada:
    """Middleware ASGI puro: corre antes de que FastAPI lea el cuerpo."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        extra = cabeceras_de_seguridad()
        iniciada = False

        async def enviar(mensaje):
            nonlocal iniciada
            if mensaje["type"] == "http.response.start":
                iniciada = True
                mensaje = dict(mensaje)
                mensaje["headers"] = list(mensaje.get("headers", [])) + extra
            await send(mensaje)

        async def responder(status: int, detalle: str):
            cuerpo = json.dumps({"detail": detalle}, ensure_ascii=False).encode("utf-8")
            await enviar({"type": "http.response.start", "status": status,
                          "headers": [(b"content-type", b"application/json; charset=utf-8"),
                                      (b"content-length", str(len(cuerpo)).encode())]})
            await send({"type": "http.response.body", "body": cuerpo})

        ruta = scope.get("path", "")
        cabeceras = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}

        if requiere_token(ruta):
            try:
                core.verificar_token(cabeceras.get("authorization"))
            except HTTPException as e:
                await responder(e.status_code, e.detail)
                return

        limite = limite_de(ruta)
        declarado = cabeceras.get("content-length")
        if declarado and declarado.isdigit() and int(declarado) > limite:
            await responder(413, _CuerpoDemasiadoGrande(limite).detail)
            return

        leidos = 0

        async def recibir():
            nonlocal leidos
            mensaje = await receive()
            if mensaje["type"] == "http.request":
                leidos += len(mensaje.get("body", b""))
                if leidos > limite:
                    raise _CuerpoDemasiadoGrande(limite)
            return mensaje

        try:
            await self.app(scope, recibir, enviar)
        except _CuerpoDemasiadoGrande as e:
            if iniciada:
                raise
            await responder(413, e.detail)


# ── Login ──

# Fallos de login de TODOS los origenes en la ventana de bloqueo. El bloqueo
# por IP no alcanza solo: detras de un proxy, o si un atacante rota de IP, cada
# IP arranca de cero. Con una contrasena larga el ataque igual es inviable;
# esto lo hace ademas lento y visible.
LOGIN_MAX_FALLOS_GLOBALES = 50
fallos_globales: deque = deque()


def ip_cliente(request) -> str:
    """La IP de quien pide. Detras del proxy de la nube, `request.client.host`
    es la IP del PROXY: con eso, cinco fallos de cualquiera bloqueaban el login
    de la empresa entera. Con PROXY_CONFIABLE=1 se toma la ULTIMA IP de
    X-Forwarded-For, que es la que agrega el proxy propio; la primera la
    escribe el cliente y se puede falsificar."""
    if os.getenv("PROXY_CONFIABLE") == "1":
        partes = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if partes:
            return partes[-1]
    return request.client.host if request.client else "desconocida"


def credenciales_correctas(usuario: str, contrasena: str) -> bool:
    """Compara en tiempo constante y SIN cortocircuito (las dos comparaciones
    corren siempre). Con usuario o contrasena sin configurar —o configurados
    vacios, `""`— no entra nadie: antes `"" == ""` dejaba pasar un login en
    blanco si la variable existia vacia en el servidor."""
    if not core.LOGIN_USER or not core.LOGIN_PASS:
        return False
    ok_usuario = hmac.compare_digest(usuario.encode("utf-8"), core.LOGIN_USER.encode("utf-8"))
    ok_contrasena = hmac.compare_digest(contrasena.encode("utf-8"), core.LOGIN_PASS.encode("utf-8"))
    return ok_usuario and ok_contrasena


def bloqueo_global_activo(ahora: datetime) -> bool:
    ventana = ahora - timedelta(minutes=core.LOGIN_BLOQUEO_MINUTOS)
    while fallos_globales and fallos_globales[0] < ventana:
        fallos_globales.popleft()
    return len(fallos_globales) >= LOGIN_MAX_FALLOS_GLOBALES


def registrar_fallo_global(ahora: datetime):
    fallos_globales.append(ahora)


LOGIN_MAX_IPS_EN_MEMORIA = 10_000


def purgar_intentos_vencidos(ahora: datetime):
    """`login_attempts` vive en memoria y antes nunca se limpiaba: un atacante
    rotando IPs lo hacia crecer sin limite. Solo se purga al pasar el tope, y
    solo lo que no esta bloqueado ahora: purgar siempre le borraria a una IP
    los fallos que lleva contados y le regalaria intentos."""
    if len(core.login_attempts) < LOGIN_MAX_IPS_EN_MEMORIA:
        return
    for ip in list(core.login_attempts):
        hasta = core.login_attempts[ip]["bloqueado_hasta"]
        if not hasta or hasta < ahora:
            core.login_attempts.pop(ip, None)


# ── Arranque en produccion ──

LOGIN_PASS_MIN = 15
LOGIN_USER_MIN = 4


def exigir_credenciales_fuertes():
    """En produccion la app NO arranca con credenciales flojas: es mejor un
    servidor caido con un mensaje claro que uno publicado con una contrasena
    de 6 caracteres o, peor, sin contrasena."""
    usuario, contrasena = core.LOGIN_USER or "", core.LOGIN_PASS or ""
    problemas = []
    if len(usuario) < LOGIN_USER_MIN:
        problemas.append(f"LOGIN_USER tiene que tener al menos {LOGIN_USER_MIN} caracteres")
    if len(contrasena) < LOGIN_PASS_MIN:
        problemas.append(f"LOGIN_PASS tiene que tener al menos {LOGIN_PASS_MIN} caracteres")
    if not os.getenv("ANTHROPIC_API_KEY"):
        problemas.append("falta ANTHROPIC_API_KEY")
    if problemas:
        raise RuntimeError("No se arranca en produccion: " + "; ".join(problemas) + ". Revisar el .env.")
