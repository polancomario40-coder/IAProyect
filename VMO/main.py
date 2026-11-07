# by a_oller
"""
main.py — punto de entrada de uvicorn. Sin logica propia (issue #4, Fase 2):
crea la app, monta los 4 routers, y sirve static/ al final. Toda la config,
auth y logica de negocio vive en core.py; las rutas en routes_conduces.py,
routes_estimaciones.py, routes_logistica.py y routes_comercial.py.

El de Logistica es distinto y conviene saberlo: son 3 rutas que solo guardan y
devuelven el dia. El calculo del cumplimiento NO esta en Python — vive en
static/logistica.logic.js y corre en el navegador.

Seguridad (auditoria 2026-10-07): todo pedido pasa primero por
seguridad.PuertaDeEntrada —token, tope de tamano y cabeceras— ANTES de que
FastAPI lea el cuerpo. Con PRODUCCION=1 la app no arranca con credenciales
flojas y no publica /docs ni /openapi.json. Ver seguridad.py.

Orden CRITICO: los 4 include_router() tienen que ejecutarse ANTES del
app.mount("/", ...) de abajo — ese mount es un catch-all en la raiz, si se
montara antes podria interceptar rutas de API registradas despues.
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from routes_conduces import router as router_conduces
from routes_estimaciones import router as router_estimaciones
from routes_logistica import router as router_logistica
from routes_comercial import router as router_comercial
import seguridad

if seguridad.PRODUCCION:
    seguridad.exigir_credenciales_fuertes()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
else:
    app = FastAPI()
app.add_middleware(seguridad.PuertaDeEntrada)
app.include_router(router_conduces)
app.include_router(router_estimaciones)
app.include_router(router_logistica)
app.include_router(router_comercial)

class EstaticosRevalidados(StaticFiles):
    """StaticFiles que pide revalidar antes de reusar lo cacheado.

    `no-cache` NO significa "no guardes": significa "pregunta antes de usar lo
    guardado". Como StaticFiles ya manda ETag y Last-Modified, la respuesta
    normal es un 304 vacio, asi que no cuesta ancho de banda.

    Por que hace falta (2026-10-01): el navegador cachea el HTML y el JS por
    separado, y el portal crea sus iframes por JavaScript — una carga hecha por
    script NO respeta el bypass de cache de Ctrl+Shift+R. Resultado real de ese
    dia: el HTML nuevo de las estadisticas se cargo con el logistica.logic.js
    viejo y la pagina quedo colgada en "Cargando el historial..." para siempre,
    con un ReferenceError en la consola y nada en pantalla. No es un caso raro:
    pasa en CADA cambio del JavaScript, y lo ve el usuario, no quien programa.
    """

    def file_response(self, *args, **kwargs):
        respuesta = super().file_response(*args, **kwargs)
        respuesta.headers["Cache-Control"] = "no-cache"
        return respuesta


app.mount("/", EstaticosRevalidados(directory="static", html=True), name="static")
