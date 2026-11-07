"""
Integridad de lo que entra y sale — auditoria OWASP del 2026-10-07, previa a
publicar la app: lo que se acepta de Vision, formulas en los Excel generados,
HTML de los reportes, el nombre de los PDF y la descarga de Excel.

Correr con: python -m pytest tests/test_seguridad_integridad.py -v
"""
import json
import os
import sqlite3
import sys
from datetime import datetime

import openpyxl
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import main  # noqa: E402

client = TestClient(main.app)


# ── Lo que se acepta de Vision ──

def test_vision_no_puede_aprobar_una_factura_a_mano():
    """Un PDF con prompt injection podia hacer que el modelo devolviera las
    columnas de aprobacion manual, y la insercion las leia del mismo dict."""
    datos = core._sanear_datos_vision({
        "tiene_sello": True, "tiene_firma": True, "cliente": "X", "cantidad": 8,
        "aprobado_manual": 1, "aprobado_por": "Gerente", "motivo_bloqueo": None,
        "archivo_pdf": "../../otro.pdf",
    })
    for clave in ("aprobado_manual", "aprobado_por", "motivo_bloqueo", "archivo_pdf"):
        assert clave not in datos
    assert datos["cliente"] == "X" and datos["cantidad"] == 8.0


def test_vision_si_no_solo_acepta_verdadero_de_verdad():
    datos = core._sanear_datos_vision({"tiene_sello": "false", "tiene_firma": "true", "al_reves": 1})
    assert datos["tiene_sello"] is False
    assert datos["tiene_firma"] is True
    assert datos["al_reves"] is False


@pytest.mark.parametrize("cantidad", ["muchos", 0, -3, core.VISION_CANTIDAD_MAX + 1])
def test_vision_cantidad_imposible_es_una_lectura_mala(cantidad):
    """Error (y reintento), no un numero inventado ni un TypeError que tumbe
    el lote despues de pagar las llamadas."""
    with pytest.raises(ValueError):
        core._sanear_datos_vision({"cantidad": cantidad})


def test_vision_textos_largos_se_recortan():
    datos = core._sanear_datos_vision({"observaciones": "x" * 5000})
    assert len(datos["observaciones"]) == core.VISION_TEXTO_MAX


# ── Formulas en los Excel generados ──

def test_texto_con_igual_queda_como_texto_en_el_excel(tmp_path):
    ruta = tmp_path / "validacion.xlsx"
    core.generar_excel_validacion([{"cliente": '=WEBSERVICE("http://169.254.169.254/")',
                                    "obra": "=1+1"}], str(ruta))
    ws = openpyxl.load_workbook(ruta).active
    assert ws["G2"].value == '=WEBSERVICE("http://169.254.169.254/")'
    assert ws["G2"].data_type == "s"
    assert ws["H2"].data_type == "s"


# ── HTML de los reportes ──

def test_el_reporte_escapa_el_html_de_los_datos(tmp_path, monkeypatch):
    db = tmp_path / "conduces.db"
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE conduces (id_conduce TEXT PRIMARY KEY, fecha DATE, producto TEXT,
                    compania TEXT, precio REAL, cantidad REAL, almacen TEXT,
                    estado TEXT DEFAULT 'no_pagado', id_transporte TEXT)""")
    conn.execute("INSERT INTO conduces VALUES ('C1','2026-06-01','<script>alert(1)</script>',"
                 "'<b>ACME</b>',100,1,'A','no_pagado','<img src=x>')")
    conn.commit()
    conn.close()
    monkeypatch.setattr(core, "DB_PATH", str(db))
    monkeypatch.setattr(core, "REPORTES_DIR", str(tmp_path))

    nombre = json.loads(core.generar_reporte())["filename"]
    html = (tmp_path / nombre).read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "<img src=x>" not in html


# ── Nombre de los PDF ──

def test_nombre_de_pdf_con_salto_de_linea_no_pasa():
    assert core.parsear_nombre_pdf("01-01-M1-1.pdf") is not None
    assert core.parsear_nombre_pdf("01-01-M1-1.pdf\n") is None


# ── Descarga de Excel ──

@pytest.fixture
def auth():
    core.active_tokens["t-integridad"] = datetime.now()
    yield {"Authorization": "Bearer t-integridad"}
    core.active_tokens.pop("t-integridad", None)


def test_la_descarga_de_excel_solo_sirve_los_de_validacion(tmp_path, monkeypatch, auth):
    monkeypatch.setattr(core, "EST_DATA_DIR", str(tmp_path))
    (tmp_path / "validacion_0a1b2c3d.xlsx").write_bytes(b"x")
    (tmp_path / "estimaciones.db").write_bytes(b"x")
    (tmp_path / "Lista de precios.xlsx").write_bytes(b"x")

    assert client.get("/api/estimaciones/excel/validacion_0a1b2c3d.xlsx", headers=auth).status_code == 200
    assert client.get("/api/estimaciones/excel/estimaciones.db", headers=auth).status_code == 404
    assert client.get("/api/estimaciones/excel/Lista de precios.xlsx", headers=auth).status_code == 404
