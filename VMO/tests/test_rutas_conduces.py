"""
Tests HTTP (via TestClient) de las 9 rutas de Conduces (hoy en
routes_conduces.py, antes en main.py) — hasta ahora sin ningun test a
nivel de ruta (test_conduces.py solo cubre las funciones de negocio con
llamadas directas, nunca via HTTP). Sirve de red de seguridad para el
split de main.py en routers (issue #4): estos tests deben responder
exactamente igual (mismo status code y mismo cuerpo JSON) antes y despues
del split — de hecho ya lo confirmaron: pasaron sin tocar ninguna
asercion, solo el import de main.X a core.X (ver core.py para el porque).

Correr con: python -m pytest tests/test_rutas_conduces.py -v
"""
import os
import sqlite3
import sys
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import main  # noqa: E402 (solo para main.app — TestClient necesita la app con los routers ya incluidos)

client = TestClient(main.app)


SCHEMA_CONDUCES = """
    CREATE TABLE conduces (
        id_conduce    TEXT PRIMARY KEY,
        fecha         DATE,
        producto      TEXT,
        compania      TEXT,
        precio        REAL,
        cantidad      REAL,
        almacen       TEXT,
        estado        TEXT DEFAULT 'no_pagado',
        id_transporte TEXT
    )
"""


@pytest.fixture(autouse=True)
def _aislar_directorios(tmp_path, monkeypatch):
    """CRITICO: nunca tocar db/conduces.db, reportes/ ni facturas/ reales —
    mismo motivo documentado en test_conduces.py (ver CLAUDE.md 2026-08-21,
    perdida real de reportes/facturas por falta de este aislamiento).
    Aca no hace falta pasar por _cache_reportes porque estas rutas escriben
    directo en core.REPORTES_DIR/core.FACTURAS_DIR — alcanza con
    monkeypatchear esos dos globals."""
    reportes_dir = tmp_path / "reportes_test"
    facturas_dir = tmp_path / "facturas_test"
    reportes_dir.mkdir()
    facturas_dir.mkdir()
    monkeypatch.setattr(core, "REPORTES_DIR", str(reportes_dir))
    monkeypatch.setattr(core, "FACTURAS_DIR", str(facturas_dir))


@pytest.fixture(autouse=True)
def _reset_estado_global():
    """active_tokens/login_attempts son dict a nivel de modulo — sin este
    reset, el orden real de ejecucion de los tests podria alterar el
    resultado (ej. intentos de login acumulados de un test disparando el
    bloqueo de 5 intentos en otro test que no tiene nada que ver)."""
    core.active_tokens.clear()
    core.login_attempts.clear()
    yield
    core.active_tokens.clear()
    core.login_attempts.clear()


@pytest.fixture
def db_conduces(tmp_path, monkeypatch):
    """BD sqlite minima con el esquema real de conduces, aislada de la BD
    de produccion — 2 compañias, 3 conduces (pagado + no_pagado mezclados)."""
    db_path = tmp_path / "conduces_test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(SCHEMA_CONDUCES)
    conn.execute(
        "INSERT INTO conduces VALUES "
        "('C1001','2026-06-01','ARENA','ACME SRL',100.0,10.0,'Bavaro','no_pagado',NULL)"
    )
    conn.execute(
        "INSERT INTO conduces VALUES "
        "('C1002','2026-06-02','GRAVILLA','ACME SRL',200.0,5.0,'Bavaro','pagado',NULL)"
    )
    conn.execute(
        "INSERT INTO conduces VALUES "
        "('C1003','2026-06-03','PIEDRA','OTRA COMPANIA',150.0,8.0,'SanIsidro','no_pagado',NULL)"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(core, "DB_PATH", str(db_path))
    return str(db_path)


@pytest.fixture
def token_valido():
    token = "test-token-conduces"
    core.active_tokens[token] = datetime.now()
    return token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── POST /login ──

def test_login_credenciales_correctas_devuelve_token(monkeypatch):
    monkeypatch.setattr(core, "LOGIN_USER", "user_test")
    monkeypatch.setattr(core, "LOGIN_PASS", "pass_test")
    res = client.post("/login", json={"usuario": "user_test", "contrasena": "pass_test"})
    assert res.status_code == 200
    body = res.json()
    assert "token" in body
    assert body["token"] in core.active_tokens


def test_login_credenciales_incorrectas_devuelve_401(monkeypatch):
    monkeypatch.setattr(core, "LOGIN_USER", "user_test")
    monkeypatch.setattr(core, "LOGIN_PASS", "pass_test")
    res = client.post("/login", json={"usuario": "user_test", "contrasena": "incorrecta"})
    assert res.status_code == 401
    assert len(core.active_tokens) == 0


# ── POST /logout ──
# Nota: /logout nunca falla con un status code de error (no llama a
# verificar_token, es idempotente por diseño) — no hay una ruta de "fallo"
# real que probar con un status distinto. El segundo test cubre el caso
# borde equivalente: token ausente/invalido no rompe nada y no afecta
# sesiones de otros usuarios.

def test_logout_con_token_valido_lo_elimina(token_valido):
    res = client.post("/logout", headers=_auth(token_valido))
    assert res.status_code == 200
    assert res.json() == {"ok": True}
    assert token_valido not in core.active_tokens


def test_logout_sin_token_no_lanza_error_ni_afecta_otras_sesiones(token_valido):
    res = client.post("/logout")
    assert res.status_code == 200
    assert res.json() == {"ok": True}
    assert token_valido in core.active_tokens


# ── POST /api/generar-reporte ──

def test_generar_reporte_exitoso(db_conduces, token_valido):
    res = client.post("/api/generar-reporte", json={}, headers=_auth(token_valido))
    assert res.status_code == 200
    body = res.json()
    assert body["download_url"] == "/download/reporte_general_todos.html"
    filename = body["download_url"].split("/download/")[1]
    assert os.path.exists(os.path.join(core.REPORTES_DIR, filename))


def test_generar_reporte_sin_token_devuelve_401():
    res = client.post("/api/generar-reporte", json={})
    assert res.status_code == 401


# ── POST /api/generar-reporte-compania ──

def test_generar_reporte_compania_exitoso(db_conduces, token_valido):
    res = client.post(
        "/api/generar-reporte-compania",
        json={"compania": "ACME SRL"},
        headers=_auth(token_valido),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["download_url"].startswith("/download/reporte_")
    filename = body["download_url"].split("/download/")[1]
    assert os.path.exists(os.path.join(core.REPORTES_DIR, filename))


def test_generar_reporte_compania_sin_token_devuelve_401():
    res = client.post("/api/generar-reporte-compania", json={"compania": "ACME SRL"})
    assert res.status_code == 401


# ── POST /api/generar-factura ──

def test_generar_factura_exitoso(db_conduces, token_valido):
    res = client.post(
        "/api/generar-factura",
        json={"compania": "ACME SRL"},
        headers=_auth(token_valido),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["download_url"].startswith("/download-factura/")
    filename = body["download_url"].split("/download-factura/")[1]
    assert os.path.exists(os.path.join(core.FACTURAS_DIR, filename))


def test_generar_factura_sin_compania_devuelve_400(token_valido):
    res = client.post(
        "/api/generar-factura",
        json={"compania": ""},
        headers=_auth(token_valido),
    )
    assert res.status_code == 400


# ── GET /download-factura/{filename} ──

def test_download_factura_exitoso(token_valido):
    contenido = "<html><body>factura de prueba</body></html>"
    filename = "factura_prueba.html"
    with open(os.path.join(core.FACTURAS_DIR, filename), "w", encoding="utf-8") as f:
        f.write(contenido)
    res = client.get(f"/download-factura/{filename}", headers=_auth(token_valido))
    assert res.status_code == 200
    assert contenido in res.text


def test_download_factura_inexistente_devuelve_404(token_valido):
    res = client.get("/download-factura/no_existe.html", headers=_auth(token_valido))
    assert res.status_code == 404


# ── GET /companias ──

def test_companias_exitoso(db_conduces, token_valido):
    res = client.get("/companias", headers=_auth(token_valido))
    assert res.status_code == 200
    assert res.json()["companias"] == ["ACME SRL", "OTRA COMPANIA"]


def test_companias_sin_token_devuelve_401():
    res = client.get("/companias")
    assert res.status_code == 401


# ── POST /chat ──
# Mock minimo de la respuesta del SDK de anthropic — nunca se llama a la
# API real (evita costo y flakiness, pedido explicito del issue).

class _FakeBlock:
    def __init__(self, type_, text=None, name=None, input=None, id=None):
        self.type = type_
        self.text = text
        self.name = name
        self.input = input
        self.id = id

    def model_dump(self):
        d = {"type": self.type}
        if self.text is not None:
            d["text"] = self.text
        if self.name is not None:
            d["name"] = self.name
        if self.input is not None:
            d["input"] = self.input
        if self.id is not None:
            d["id"] = self.id
        return d


class _FakeResponse:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content


def test_chat_exitoso_mockeado(token_valido, monkeypatch):
    def fake_create(**kwargs):
        return _FakeResponse("end_turn", [_FakeBlock("text", text="Hola, en que te ayudo?")])

    monkeypatch.setattr(core.client.messages, "create", fake_create)
    res = client.post("/chat", json={"message": "hola"}, headers=_auth(token_valido))
    assert res.status_code == 200
    body = res.json()
    assert body["response"] == "Hola, en que te ayudo?"
    assert body["download_url"] is None
    assert body["consulta_data"] is None


def test_chat_con_tool_use_genera_reporte(db_conduces, token_valido, monkeypatch):
    """Cubre el loop completo de tool use (no solo el end_turn directo):
    Claude pide generar_reporte, el backend lo ejecuta de verdad (BD
    aislada) y solo despues Claude devuelve el texto final."""
    llamadas = []

    def fake_create(**kwargs):
        llamadas.append(kwargs)
        if len(llamadas) == 1:
            return _FakeResponse(
                "tool_use",
                [_FakeBlock("tool_use", name="generar_reporte", input={}, id="toolu_1")],
            )
        return _FakeResponse("end_turn", [_FakeBlock("text", text="Reporte listo")])

    monkeypatch.setattr(core.client.messages, "create", fake_create)
    res = client.post(
        "/chat", json={"message": "dame un reporte general"}, headers=_auth(token_valido)
    )
    assert res.status_code == 200
    body = res.json()
    assert body["download_url"] == "/download/reporte_general_todos.html"
    assert len(llamadas) == 2


def test_chat_sin_token_devuelve_401():
    res = client.post("/chat", json={"message": "hola"})
    assert res.status_code == 401


# ── GET /download/{filename} ──

def test_download_exitoso(token_valido):
    contenido = "<html><body>reporte de prueba</body></html>"
    filename = "reporte_prueba.html"
    with open(os.path.join(core.REPORTES_DIR, filename), "w", encoding="utf-8") as f:
        f.write(contenido)
    res = client.get(f"/download/{filename}", headers=_auth(token_valido))
    assert res.status_code == 200
    assert contenido in res.text


def test_download_inexistente_devuelve_404(token_valido):
    res = client.get("/download/no_existe.html", headers=_auth(token_valido))
    assert res.status_code == 404


# ── Issue #31 — `sin_precio` tiene que sobrevivir la ruta, no solo core ──
#
# Los tests del #31 llamaban a core.generar_reporte() directo y pasaban, pero
# las tres rutas rearmaban la respuesta a mano y tiraban el campo. Se descubrio
# pegandole por HTTP al servidor DESPUES de mergear. Estos tests van por la
# ruta a proposito: es el unico nivel donde el bug era visible.

@pytest.fixture
def db_con_conduce_sin_precio(tmp_path, monkeypatch):
    """Dos pendientes de la misma compañia: uno con precio y otro sin. El
    monto correcto es 1.000 y el faltante es 1 de 2."""
    db_path = tmp_path / "conduces_sin_precio.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(SCHEMA_CONDUCES)
    conn.execute(
        "INSERT INTO conduces VALUES "
        "('C2001','2026-06-01','ARENA','ACME SRL',100.0,10.0,'Bavaro','no_pagado',NULL)"
    )
    conn.execute(
        "INSERT INTO conduces VALUES "
        "('C2002','2026-07-01','ARENA','ACME SRL',NULL,7.0,'Bavaro','no_pagado',NULL)"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(core, "DB_PATH", str(db_path))
    return str(db_path)


def test_ruta_generar_reporte_devuelve_sin_precio(db_con_conduce_sin_precio, token_valido):
    res = client.post("/api/generar-reporte", json={}, headers=_auth(token_valido))
    assert res.status_code == 200
    body = res.json()
    assert body["cached"] is False
    assert "sin_precio" in body, (
        "la ruta rearma la respuesta a mano — si se agrega un campo en core "
        "hay que pasarlo por _respuesta_reporte(), no alcanza con devolverlo"
    )
    assert body["sin_precio"] == 1


def test_ruta_generar_reporte_compania_devuelve_sin_precio(db_con_conduce_sin_precio, token_valido):
    res = client.post("/api/generar-reporte-compania", json={"compania": "ACME SRL"},
                      headers=_auth(token_valido))
    assert res.status_code == 200
    assert res.json()["sin_precio"] == 1


def test_ruta_generar_factura_devuelve_sin_precio(db_con_conduce_sin_precio, token_valido):
    res = client.post("/api/generar-factura", json={"compania": "ACME SRL"},
                      headers=_auth(token_valido))
    assert res.status_code == 200
    assert res.json()["sin_precio"] == 1


def test_ruta_reporte_cacheado_devuelve_sin_precio_None_no_cero(db_con_conduce_sin_precio, token_valido):
    """El camino de cache no recalcula nada, asi que el conteo no se conoce.
    Devolver 0 ahi seria mentir: dirian que no falta ninguno cuando faltan.
    La clave viaja igual, con None explicito, para que quien la consuma pueda
    distinguir 'no se sabe' de 'no falta ninguno' mirando `cached`."""
    primera = client.post("/api/generar-reporte", json={}, headers=_auth(token_valido))
    assert primera.json()["cached"] is False
    assert primera.json()["sin_precio"] == 1

    segunda = client.post("/api/generar-reporte", json={}, headers=_auth(token_valido))
    assert segunda.json()["cached"] is True
    assert "sin_precio" in segunda.json()
    assert segunda.json()["sin_precio"] is None


def test_ruta_reporte_sin_faltantes_devuelve_sin_precio_cero(db_conduces, token_valido):
    """Con todos los precios cargados el campo es 0, no None — el 0 es una
    afirmacion ('no falta ninguno') y solo se puede hacer si se calculo."""
    res = client.post("/api/generar-reporte", json={}, headers=_auth(token_valido))
    assert res.json()["sin_precio"] == 0
