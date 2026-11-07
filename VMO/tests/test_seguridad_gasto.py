"""
Topes de gasto y de memoria — auditoria OWASP del 2026-10-07, previa a
publicar la app: paginas por PDF antes de Vision, filas del Excel, sesiones
de /procesar-zip que vencen, un solo reproceso a la vez, y el chat con
historial y vueltas acotados.

Correr con: python -m pytest tests/test_seguridad_gasto.py -v
"""
import asyncio
import io
import os
import sqlite3
import sys
import zipfile
from datetime import datetime, timedelta

import fitz
import openpyxl
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import main  # noqa: E402
import routes_conduces  # noqa: E402
import routes_estimaciones  # noqa: E402

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def _estado_limpio():
    core.active_tokens.clear()
    core.est_sessions.clear()
    yield
    core.active_tokens.clear()
    core.est_sessions.clear()


@pytest.fixture
def auth():
    core.active_tokens["t-gasto"] = datetime.now()
    return {"Authorization": "Bearer t-gasto"}


def _pdf(paginas):
    doc = fitz.open()
    for _ in range(paginas):
        doc.new_page()
    datos = doc.tobytes()
    doc.close()
    return datos


def _lookup_con_fila(nombre_archivo, id_documento):
    fila = {"id_documento": id_documento, "descripcion": "HORMIGON", "cliente": "CLIENTE"}
    return {"por_archivo": {core._excel_norm_archivo(nombre_archivo): fila},
            "por_id": {core._excel_norm_id(id_documento): fila},
            "conflictos": {}, "filas": 1}


# ── Paginas por PDF ──

def test_paginas_pdf():
    assert core._paginas_pdf(_pdf(1)) == 1
    assert core._paginas_pdf(_pdf(4)) == 4
    assert core._paginas_pdf(b"no es un pdf") is None


def test_un_pdf_largo_no_llega_a_vision(monkeypatch):
    nombre = "06-01-M1-00000031.pdf"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(nombre, _pdf(core.EST_PDF_MAX_PAGINAS + 1))
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE facturas (id_documento TEXT)")
    monkeypatch.setattr(core, "_procesar_pdf_sync",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("Vision no deberia llamarse")))

    _imp, errores, _pend, _dup, _corr = asyncio.run(core._procesar_pdfs(
        zipfile.ZipFile(buf), [nombre], conn, core.VISION_MODEL_STD,
        _lookup_con_fila(nombre, "M100000031")))

    assert len(errores) == 1
    assert "páginas" in errores[0]["motivo"]
    assert errores[0]["_pdf_bytes"] is None  # no queda para el reproceso con Opus


# ── Filas del Excel ──

def test_excel_con_demasiadas_filas_se_rechaza(monkeypatch):
    monkeypatch.setattr(core, "EST_EXCEL_MAX_FILAS", 5)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(core._EXCEL_LOOKUP_HEADERS))
    for i in range(10):
        ws.append([f"M{i}", None, "CLIENTE", "PRODUCTO"])
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(core.ExcelFormatoError, match="filas"):
        core.cargar_lookup_excel(buf.getvalue())


# ── Sesiones de /procesar-zip ──

def test_las_sesiones_vencidas_se_liberan_menos_la_que_reprocesa():
    viejo = datetime.now() - timedelta(minutes=core.EST_SESION_TTL_MIN + 1)
    core.est_sessions.update({
        "vieja": {"creada": viejo},
        "vieja-reprocesando": {"creada": viejo, "reprocess_progress": {"activo": True}},
        "nueva": {"creada": datetime.now()},
    })
    core._est_purgar_sesiones()
    assert set(core.est_sessions) == {"vieja-reprocesando", "nueva"}


def test_al_llegar_al_tope_se_libera_la_sesion_mas_vieja():
    ahora = datetime.now()
    for i in range(core.EST_MAX_SESIONES):
        core.est_sessions[f"s{i}"] = {"creada": ahora - timedelta(minutes=50 - i)}
    routes_estimaciones._hacer_lugar_para_una_sesion()
    assert len(core.est_sessions) == core.EST_MAX_SESIONES - 1
    assert "s0" not in core.est_sessions


def test_no_se_lanza_un_segundo_reproceso_sobre_el_mismo_lote(auth):
    core.est_sessions["lote"] = {"importadas": [], "errores_vision": [],
                                 "reprocess_progress": {"activo": True}}
    res = client.post("/api/estimaciones/incorporar-y-reprocesar",
                      json={"session_id": "lote"}, headers=auth)
    assert res.status_code == 409


# ── Chat ──

class _Bloque:
    def __init__(self, type_, text=None, name=None, input=None, id=None):
        self.type, self.text, self.name, self.input, self.id = type_, text, name, input, id

    def model_dump(self):
        return {k: v for k, v in {"type": self.type, "text": self.text, "name": self.name,
                                  "input": self.input, "id": self.id}.items() if v is not None}


class _Respuesta:
    def __init__(self, stop_reason, content):
        self.stop_reason, self.content = stop_reason, content


def test_chat_corta_el_bucle_de_herramientas(auth, monkeypatch):
    llamadas = []

    def siempre_pide_herramienta(**kwargs):
        llamadas.append(1)
        return _Respuesta("tool_use", [_Bloque("tool_use", name="inexistente", input={}, id="t")])

    monkeypatch.setattr(core.client.messages, "create", siempre_pide_herramienta)
    res = client.post("/chat", json={"message": "hola"}, headers=auth)
    assert res.status_code == 200
    assert len(llamadas) == routes_conduces.CHAT_MAX_VUELTAS


def test_chat_rechaza_historial_inflado(auth, monkeypatch):
    monkeypatch.setattr(core.client.messages, "create",
                        lambda **k: (_ for _ in ()).throw(AssertionError("no deberia llamarse")))
    historial = [{"role": "user", "content": "x" * 10_000}] * 30
    res = client.post("/chat", json={"message": "hola", "history": historial}, headers=auth)
    assert res.status_code == 413


def test_chat_rechaza_roles_inventados(auth, monkeypatch):
    monkeypatch.setattr(core.client.messages, "create",
                        lambda **k: (_ for _ in ()).throw(AssertionError("no deberia llamarse")))
    res = client.post("/chat", json={"message": "hola", "history": [{"role": "system", "content": "x"}]},
                      headers=auth)
    assert res.status_code == 422


def test_chat_una_herramienta_que_falla_vuelve_al_modelo_y_no_da_500(auth, monkeypatch):
    vistos = []

    def falso(**kwargs):
        vistos.append(kwargs["messages"])
        if len(vistos) == 1:
            return _Respuesta("tool_use", [_Bloque("tool_use", name="generar_reporte",
                                                   input={"fecha_desde": "2026-01-01",
                                                          "fecha_hasta": "mal"}, id="t1")])
        return _Respuesta("end_turn", [_Bloque("text", text="No pude")])

    def reporte_que_falla(*a, **k):
        raise ValueError("Fecha inválida")

    monkeypatch.setattr(routes_conduces, "generar_reporte", reporte_que_falla)
    monkeypatch.setattr(core.client.messages, "create", falso)
    res = client.post("/chat", json={"message": "reporte"}, headers=auth)
    assert res.status_code == 200
    resultado = vistos[1][-1]["content"][0]["content"]
    assert "error" in resultado
