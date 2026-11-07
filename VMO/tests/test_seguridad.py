"""
Tests de la puerta de entrada (seguridad.py) — auditoria OWASP del
2026-10-07, previa a publicar la app en internet.

Correr con: python -m pytest tests/test_seguridad.py -v
"""
import os
import sys
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import main  # noqa: E402
import seguridad  # noqa: E402

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def _reset_estado_global(tmp_path, monkeypatch):
    core.active_tokens.clear()
    core.login_attempts.clear()
    seguridad.fallos_globales.clear()
    # generar-reporte escribe en REPORTES_DIR: nunca en la carpeta real
    monkeypatch.setattr(core, "REPORTES_DIR", str(tmp_path))
    monkeypatch.delenv("PROXY_CONFIABLE", raising=False)
    yield
    core.active_tokens.clear()
    core.login_attempts.clear()
    seguridad.fallos_globales.clear()


@pytest.fixture
def token():
    t = "token-de-prueba-seguridad"
    core.active_tokens[t] = datetime.now()
    return {"Authorization": f"Bearer {t}"}


# ── Toda ruta de datos exige token ──

def test_toda_ruta_de_la_api_queda_bajo_un_prefijo_protegido():
    """Una ruta nueva fuera de los prefijos protegidos quedaria publica si a
    alguien se le olvida el verificar_token(): este test lo frena."""
    # app.routes no sirve: desde FastAPI 0.14x cada include_router queda
    # envuelto y sus rutas no se ven ahi. El esquema OpenAPI si las lista todas.
    rutas = list(main.app.openapi()["paths"])
    assert len(rutas) > 25
    sueltas = [r for r in rutas if r not in seguridad.RUTAS_PUBLICAS and not seguridad.requiere_token(r)]
    assert sueltas == []


def test_anonimo_no_llega_a_subir_un_zip():
    res = client.post("/api/estimaciones/procesar-zip",
                      files={"archivo": ("a.zip", b"x" * 1000), "excel": ("a.xlsx", b"y")})
    assert res.status_code == 401


def test_al_anonimo_se_lo_frena_antes_de_mirar_el_cuerpo(monkeypatch):
    """401 y no 413: la puerta revisa el token antes que nada. Si el token se
    revisara recien en la ruta, este cuerpo de mas ya se habria leido."""
    monkeypatch.setattr(seguridad, "LIMITE_POR_DEFECTO", 1000)
    res = client.post("/api/generar-reporte", content=b"{" + b" " * 5000 + b"}",
                      headers={"Content-Type": "application/json"})
    assert res.status_code == 401


def test_token_vencido_se_rechaza_en_la_puerta():
    core.active_tokens["viejo"] = datetime.now() - timedelta(hours=core.TOKEN_TTL_HORAS + 1)
    res = client.get("/companias", headers={"Authorization": "Bearer viejo"})
    assert res.status_code == 401


def test_openapi_sigue_publico_en_desarrollo_para_el_cierre():
    """scripts/cierre.py lo pide sin token para reconocer el servidor."""
    assert client.get("/openapi.json").status_code == 200


def test_el_portal_y_el_login_siguen_siendo_publicos():
    assert client.get("/").status_code == 200
    assert client.post("/login", json={"usuario": "x", "contrasena": "y"}).status_code == 401


# ── Tope de tamano ──

def test_cuerpo_grande_declarado_se_corta_con_413(token, monkeypatch):
    monkeypatch.setattr(seguridad, "LIMITE_POR_DEFECTO", 1000)
    res = client.post("/api/generar-reporte", content=b"{" + b" " * 5000 + b"}",
                      headers={**token, "Content-Type": "application/json"})
    assert res.status_code == 413


def test_cuerpo_grande_sin_content_length_tambien_se_corta(token, monkeypatch):
    """Por partes (chunked) no hay Content-Length: se cuentan los bytes."""
    monkeypatch.setattr(seguridad, "LIMITE_POR_DEFECTO", 1000)
    partes = iter([b"{" + b" " * 700, b" " * 700 + b"}"])
    res = client.post("/api/generar-reporte", content=partes,
                      headers={**token, "Content-Type": "application/json"})
    assert res.status_code == 413


def test_el_zip_tiene_su_propio_tope_mas_alto():
    assert seguridad.limite_de("/api/estimaciones/procesar-zip") > core.EST_ZIP_MAX_BYTES + core.EST_EXCEL_MAX_BYTES
    assert seguridad.limite_de("/api/generar-reporte") == seguridad.LIMITE_POR_DEFECTO


# ── Cabeceras ──

@pytest.mark.parametrize("ruta", ["/", "/logistica.html", "/companias"])
def test_cabeceras_de_seguridad_en_todas_las_respuestas(ruta):
    res = client.get(ruta)
    assert "frame-ancestors 'self'" in res.headers["content-security-policy"]
    assert "connect-src 'self'" in res.headers["content-security-policy"]
    assert "cdnjs" not in res.headers["content-security-policy"]
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "SAMEORIGIN"


# ── Login ──

def test_login_con_variables_vacias_no_deja_entrar_en_blanco(monkeypatch):
    monkeypatch.setattr(core, "LOGIN_USER", "")
    monkeypatch.setattr(core, "LOGIN_PASS", "")
    res = client.post("/login", json={"usuario": "", "contrasena": ""})
    assert res.status_code == 401
    assert core.active_tokens == {}


def test_login_correcto_da_un_token_largo(monkeypatch):
    monkeypatch.setattr(core, "LOGIN_USER", "usuario")
    monkeypatch.setattr(core, "LOGIN_PASS", "una-contrasena-larga")
    res = client.post("/login", json={"usuario": "usuario", "contrasena": "una-contrasena-larga"})
    assert res.status_code == 200
    assert len(res.json()["token"]) >= 40


def test_bloqueo_global_aunque_el_atacante_cambie_de_ip(monkeypatch):
    monkeypatch.setattr(core, "LOGIN_USER", "usuario")
    monkeypatch.setattr(core, "LOGIN_PASS", "una-contrasena-larga")
    monkeypatch.setattr(seguridad, "LOGIN_MAX_FALLOS_GLOBALES", 3)
    monkeypatch.setenv("PROXY_CONFIABLE", "1")
    for i in range(3):
        res = client.post("/login", json={"usuario": "usuario", "contrasena": "mal"},
                          headers={"X-Forwarded-For": f"10.0.0.{i}"})
        assert res.status_code == 401
    res = client.post("/login", json={"usuario": "usuario", "contrasena": "una-contrasena-larga"},
                      headers={"X-Forwarded-For": "10.0.0.99"})
    assert res.status_code == 429


def test_detras_del_proxy_cuenta_la_ultima_ip_no_la_que_escribe_el_cliente(monkeypatch):
    monkeypatch.setattr(core, "LOGIN_USER", "usuario")
    monkeypatch.setattr(core, "LOGIN_PASS", "una-contrasena-larga")
    monkeypatch.setenv("PROXY_CONFIABLE", "1")
    for i in range(core.LOGIN_MAX_INTENTOS):
        client.post("/login", json={"usuario": "usuario", "contrasena": "mal"},
                    headers={"X-Forwarded-For": f"1.2.3.{i}, 200.0.0.1"})
    assert "200.0.0.1" in core.login_attempts
    assert core.login_attempts["200.0.0.1"]["bloqueado_hasta"] is not None


def test_sin_proxy_confiable_se_ignora_x_forwarded_for(monkeypatch):
    class _Req:
        headers = {"x-forwarded-for": "6.6.6.6"}

        class client:
            host = "127.0.0.1"
    assert seguridad.ip_cliente(_Req()) == "127.0.0.1"


def test_la_purga_no_libera_una_ip_bloqueada(monkeypatch):
    monkeypatch.setattr(seguridad, "LOGIN_MAX_IPS_EN_MEMORIA", 2)
    ahora = datetime.now()
    core.login_attempts.update({
        "a": {"fallos": 3, "bloqueado_hasta": None},
        "b": {"fallos": 0, "bloqueado_hasta": ahora + timedelta(minutes=5)},
        "c": {"fallos": 0, "bloqueado_hasta": ahora - timedelta(minutes=5)},
    })
    seguridad.purgar_intentos_vencidos(ahora)
    assert list(core.login_attempts) == ["b"]


# ── Fechas que terminan en nombres de archivo ──

def test_fecha_con_ruta_se_rechaza_en_la_api(token):
    res = client.post("/api/generar-reporte", headers=token,
                      json={"fecha_desde": "2026-01-01", "fecha_hasta": "x/../../static/pwn"})
    assert res.status_code == 422


def test_fecha_con_ruta_se_rechaza_tambien_en_core():
    """El chat llama a core con lo que devuelve el modelo, sin pydantic."""
    with pytest.raises(ValueError):
        core.generar_reporte("2026-01-01", "x/../../static/pwn")


def test_vista_previa_valida_las_fechas_del_query(token):
    res = client.get("/api/estimaciones/vista-previa", headers=token,
                     params={"empresa": "VMO", "fase": "CEDIS",
                             "fecha_desde": "2026-01-01", "fecha_hasta": "../x"})
    assert res.status_code == 422


# ── Arranque en produccion ──

def test_produccion_no_arranca_con_contrasena_corta(monkeypatch):
    monkeypatch.setattr(core, "LOGIN_USER", "usuario")
    monkeypatch.setattr(core, "LOGIN_PASS", "corta")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    with pytest.raises(RuntimeError, match="LOGIN_PASS"):
        seguridad.exigir_credenciales_fuertes()


def test_produccion_arranca_con_credenciales_fuertes(monkeypatch):
    monkeypatch.setattr(core, "LOGIN_USER", "usuario")
    monkeypatch.setattr(core, "LOGIN_PASS", "una-contrasena-de-veinte")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    seguridad.exigir_credenciales_fuertes()
