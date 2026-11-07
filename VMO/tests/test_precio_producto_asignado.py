"""
Una factura asignada a mano a otro producto se cobra al precio de ese
producto (2026-10-20).

El caso real: el conduce M800016916 (MACAO 2) dice "rev. 7"" y en la lista de
precios solo esta el de rev. 6", asi que entro con precio_unitario NULL. En la
pantalla de revision se asigno al producto 6, que es justamente para darle
precio, pero la generacion seguia bloqueada con `precios_faltantes: 6`: el
chequeo miraba el precio de la factura, no el del producto elegido.

Todo sobre BDs temporales — nunca la BD real.

Correr con: python -m pytest tests/test_precio_producto_asignado.py -v
"""
import os
import sqlite3
import sys
import uuid
from datetime import datetime

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import main  # noqa: E402

EMPRESA = "DOMICEM"
FASE = "CAVERNAS"
DESC = "Hormigon Fc350, Agg 3/8, rev. 6"
DESC_SIN_PRECIO = "Hormigon Fc350, Agg 3/8, rev. 7"
DESDE, HASTA = "2026-07-01", "2026-07-31"


def _bd(tmp_path, monkeypatch, facturas, pu_catalogo=111.0):
    """`facturas` = [(id_documento, descripcion, precio_unitario, clave_resuelta)]."""
    db_path = tmp_path / f"est_{uuid.uuid4().hex}.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE catalogo_estimacion (
        empresa TEXT, fase TEXT, orden INTEGER, clave TEXT,
        descripcion TEXT, precio_unitario REAL,
        PRIMARY KEY (empresa, fase, orden)
    )""")
    conn.execute("""CREATE TABLE facturas (
        id_documento TEXT PRIMARY KEY, fecha DATE, empresa TEXT, fase TEXT,
        descripcion TEXT, cantidad REAL, precio_unitario REAL, clave_resuelta TEXT
    )""")
    conn.execute("""CREATE TABLE estimacion_acumulado_base (
        empresa TEXT, fase TEXT, clave TEXT,
        serie TEXT NOT NULL CHECK (serie IN ('principal','ppact')),
        fecha_base DATE, cantidad_base REAL, cantidad_proyecto_principal REAL,
        PRIMARY KEY (empresa, fase, clave, serie)
    )""")
    conn.execute("INSERT INTO catalogo_estimacion VALUES (?,?,1,'6',?,?)", (EMPRESA, FASE, DESC, pu_catalogo))
    for id_doc, desc, precio, resuelta in facturas:
        conn.execute(
            "INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,"
            "cantidad,precio_unitario,clave_resuelta) VALUES (?,?,?,?,?,4.5,?,?)",
            (id_doc, "2026-07-15", EMPRESA, FASE, desc, precio, resuelta))
    conn.commit()
    conn.close()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    monkeypatch.setattr(core, "EST_SOFFICE", None)
    token = f"test-token-{uuid.uuid4().hex}"
    core.active_tokens[token] = datetime.now()
    return token


def _generar(token, reasignaciones=None):
    try:
        return TestClient(main.app).post(
            "/api/estimaciones/generar",
            json={
                "empresa": EMPRESA, "fase": FASE, "fecha_desde": DESDE, "fecha_hasta": HASTA,
                "numero_estimacion": "N01", "fecha_estimacion": "2026-08-31", "semana": 1,
                "productos": [{"clave": "6", "cantidad_proyecto": 10000, "acumulado_anterior_cantidad": 0}],
                "reasignaciones": reasignaciones or {}, "serie": "principal",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)


def test_asignada_en_la_pantalla_toma_el_precio_del_producto(tmp_path, monkeypatch):
    token = _bd(tmp_path, monkeypatch, [("F1", DESC, 111.0, None), ("F2", DESC_SIN_PRECIO, None, None)])
    res = _generar(token, {DESC_SIN_PRECIO: "6"})
    assert res.status_code == 200, res.text


def test_asignada_antes_y_guardada_tambien(tmp_path, monkeypatch):
    """El caso de M800016916: la asignacion ya quedo en clave_resuelta."""
    token = _bd(tmp_path, monkeypatch, [("F2", DESC_SIN_PRECIO, None, "6")])
    res = _generar(token)
    assert res.status_code == 200, res.text


def test_si_el_producto_elegido_tampoco_tiene_precio_sigue_bloqueando(tmp_path, monkeypatch):
    token = _bd(tmp_path, monkeypatch, [("F2", DESC_SIN_PRECIO, None, "6")], pu_catalogo=None)
    res = _generar(token)
    assert res.status_code == 422
    assert res.json()["detail"] == {"error": "precios_faltantes", "detalle": ["6"]}


def test_la_que_matchea_sola_sin_precio_sigue_bloqueando(tmp_path, monkeypatch):
    """El chequeo sigue sirviendo para lo que era: una factura del mismo
    producto que entro sin precio es un dato a revisar, no se tapa."""
    token = _bd(tmp_path, monkeypatch, [("F1", DESC, None, None)])
    res = _generar(token)
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "precios_faltantes"
