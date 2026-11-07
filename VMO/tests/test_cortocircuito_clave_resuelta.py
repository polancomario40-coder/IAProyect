"""
Issue #36 — una `clave_resuelta` obsoleta impedia que el auto-match se
consultara siquiera, y bloqueaba la generacion.

El patron era, en los dos caminos de matcheo del proyecto:

    clave = clave_resuelta or catalogo_norm_a_clave.get(_est_normalizar(descripcion))
    if clave not in claves_validas:
        clave = None

El cortocircuito del `or` hace que, si `clave_resuelta` tiene CUALQUIER
valor, el auto-match no se consulte. Si ademas ese valor ya no existe en el
catalogo, la linea siguiente lo anula — pero para entonces el auto-match ya
se perdio. Una factura cuya descripcion matchea perfecto el catalogo de hoy
caia igual en `sin_resolver`, y en el endpoint de generacion eso levanta
`facturas_sin_resolver` (400) y frena el documento.

Es el caso opuesto al del issue #25: alla una resolucion manual vieja le
ganaba al catalogo *y se usaba*; aca le ganaba *y no dejaba usar nada*.

Se arregla en los dos lugares, porque `_est_clasificar_series()` (core) y el
endpoint de generacion (routes) repiten el patron y el resultado del primero
decide a que serie va cada factura:

    clave = clave_resuelta if clave_resuelta in claves_validas else auto_match

La prioridad `clave_resuelta > auto-match` queda intacta para el caso normal,
que es la razon de ser de la columna. Lo unico que cambia es que pasa cuando
la guardada es invalida.

Todo sobre BDs temporales — nunca la BD real.

Correr con: python -m pytest tests/test_cortocircuito_clave_resuelta.py -v
"""
import os
import sqlite3
import sys
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import main  # noqa: E402

EMPRESA = "DOMICEM"
FASE = "CAVERNAS"
DESC = "Hormigon 150 kg/cm2, Ag 3/4, rev. 6"
DESDE, HASTA = "2026-07-01", "2026-07-31"

# El catalogo tiene la clave "2"; la "9" no existe y se usa como la
# clave_resuelta obsoleta de los casos de abajo.
CLAVE_BUENA = "2"
CLAVE_OBSOLETA = "9"


def _bd(tmp_path, monkeypatch, facturas):
    """`facturas` = [(id_documento, descripcion, clave_resuelta)]."""
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
    conn.execute(
        "INSERT INTO catalogo_estimacion VALUES (?,?,1,?,?,111.0)",
        (EMPRESA, FASE, CLAVE_BUENA, DESC))
    for id_doc, desc, resuelta in facturas:
        conn.execute(
            "INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,"
            "cantidad,precio_unitario,clave_resuelta) VALUES (?,?,?,?,?,7.0,111.0,?)",
            (id_doc, "2026-07-15", EMPRESA, FASE, desc, resuelta))
    conn.commit()
    conn.close()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    token = f"test-token-{uuid.uuid4().hex}"
    core.active_tokens[token] = datetime.now()
    return str(db_path), token


def _clasificar(db_path):
    """Camino de core: _est_clasificar_series()."""
    conn = sqlite3.connect(db_path)
    try:
        catalogo = core._est_catalogo_fase(conn, EMPRESA, FASE)
        return core._est_clasificar_series(conn, EMPRESA, FASE, catalogo, DESDE, HASTA)
    finally:
        conn.close()


def _vista_previa(token):
    """Camino de core, por HTTP: vista-previa delega en _est_clasificar_series."""
    client = TestClient(main.app)
    return client.get(
        "/api/estimaciones/vista-previa",
        params={"empresa": EMPRESA, "fase": FASE,
                "fecha_desde": DESDE, "fecha_hasta": HASTA},
        headers={"Authorization": f"Bearer {token}"},
    )


def _generar(token, tmp_path, monkeypatch):
    """Camino de routes: el matcheo propio del endpoint de generacion."""
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    monkeypatch.setattr(core, "EST_SOFFICE", None)
    client = TestClient(main.app)
    return client.post(
        "/api/estimaciones/generar",
        json={
            "empresa": EMPRESA, "fase": FASE,
            "fecha_desde": DESDE, "fecha_hasta": HASTA,
            "numero_estimacion": "N01", "fecha_estimacion": "2026-08-31", "semana": 1,
            "productos": [{"clave": CLAVE_BUENA, "cantidad_proyecto": 10000,
                           "acumulado_anterior_cantidad": 0}],
            "reasignaciones": {}, "serie": "principal",
        },
        headers={"Authorization": f"Bearer {token}"},
    )


def _claves_usadas(clasificacion):
    return {f[0]: f[1] for f in clasificacion["facturas_periodo"]}


# ── caso 1: la resolucion manual valida sigue mandando ────────────────────
# Es la razon de ser de la columna y no cambia con este arreglo.

def test_clave_resuelta_valida_le_sigue_ganando_al_auto_match(tmp_path, monkeypatch):
    """La descripcion no matchea nada, pero hay resolucion manual valida:
    se usa esa. Comportamiento identico al de antes del arreglo."""
    db_path, _ = _bd(tmp_path, monkeypatch,
                     [("F1", "descripcion que no matchea nada", CLAVE_BUENA)])
    clas = _clasificar(db_path)
    assert clas["sin_resolver"] == []
    assert _claves_usadas(clas)["F1"] == CLAVE_BUENA


# ── caso 2: el defecto — obsoleta pero la descripcion matchea ─────────────

def test_clave_resuelta_obsoleta_no_tapa_el_auto_match_en_core(tmp_path, monkeypatch):
    """El caso que bloqueaba: la guardada apunta a una clave que ya no
    existe, pero la descripcion matchea perfecto el catalogo de hoy."""
    db_path, _ = _bd(tmp_path, monkeypatch, [("F1", DESC, CLAVE_OBSOLETA)])
    clas = _clasificar(db_path)
    assert clas["sin_resolver"] == [], "la obsoleta tapo el auto-match"
    assert _claves_usadas(clas)["F1"] == CLAVE_BUENA


def test_clave_resuelta_obsoleta_no_ensucia_el_sin_resolver_de_vista_previa(tmp_path, monkeypatch):
    """Vista-previa devuelve DOS listas distintas y solo una tenia el
    defecto: `sin_match` sale de un auto-match puro que nunca mira
    `clave_resuelta`, asi que siempre estuvo bien; `sin_resolver` viene de
    _est_clasificar_series() y es la que se ensuciaba. Se afirma sobre esa,
    que es la que este arreglo toca."""
    _, token = _bd(tmp_path, monkeypatch, [("F1", DESC, CLAVE_OBSOLETA)])
    try:
        res = _vista_previa(token)
    finally:
        core.active_tokens.pop(token, None)
    assert res.status_code == 200, res.text
    datos = res.json()
    assert datos["sin_resolver"] == []
    assert datos["sin_match"] == []   # este nunca estuvo roto, se fija igual


def test_clave_resuelta_obsoleta_no_bloquea_la_generacion(tmp_path, monkeypatch):
    """El sintoma que se veia: 400 facturas_sin_resolver sobre una factura
    que el catalogo de hoy resuelve sola."""
    _, token = _bd(tmp_path, monkeypatch, [("F1", DESC, CLAVE_OBSOLETA)])
    try:
        res = _generar(token, tmp_path, monkeypatch)
    finally:
        core.active_tokens.pop(token, None)
    assert res.status_code == 200, res.text


# ── caso 3: sin salida real, sigue cayendo en sin_resolver ────────────────

def test_obsoleta_y_sin_auto_match_sigue_sin_resolver_en_core(tmp_path, monkeypatch):
    """Cuando de verdad no hay con que resolver, el comportamiento no
    cambia: no se inventa una clave."""
    db_path, _ = _bd(tmp_path, monkeypatch,
                     [("F1", "descripcion que no matchea nada", CLAVE_OBSOLETA)])
    clas = _clasificar(db_path)
    assert clas["sin_resolver"] == ["descripcion que no matchea nada"]
    assert "F1" not in _claves_usadas(clas)


def test_obsoleta_y_sin_auto_match_sigue_bloqueando_la_generacion(tmp_path, monkeypatch):
    _, token = _bd(tmp_path, monkeypatch,
                   [("F1", "descripcion que no matchea nada", CLAVE_OBSOLETA)])
    try:
        res = _generar(token, tmp_path, monkeypatch)
    finally:
        core.active_tokens.pop(token, None)
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "facturas_sin_resolver"


# ── el borde que ya existia: sin clave_resuelta, auto-match manda ─────────

def test_sin_clave_resuelta_se_usa_el_auto_match(tmp_path, monkeypatch):
    db_path, _ = _bd(tmp_path, monkeypatch, [("F1", DESC, None)])
    clas = _clasificar(db_path)
    assert clas["sin_resolver"] == []
    assert _claves_usadas(clas)["F1"] == CLAVE_BUENA


def test_los_dos_caminos_coinciden_factura_por_factura(tmp_path, monkeypatch):
    """Criterio de aceptacion 4: core y routes tienen que resolver igual.
    Si divergen, la estimacion se genera con una clave y se clasifica en la
    serie de otra."""
    facturas = [
        ("F1", DESC, CLAVE_BUENA),        # valida
        ("F2", DESC, CLAVE_OBSOLETA),     # obsoleta, con auto-match
        ("F3", DESC, None),               # sin resolucion
    ]
    db_path, token = _bd(tmp_path, monkeypatch, facturas)
    clas = _clasificar(db_path)
    assert clas["sin_resolver"] == []
    assert _claves_usadas(clas) == {"F1": CLAVE_BUENA, "F2": CLAVE_BUENA, "F3": CLAVE_BUENA}
    try:
        res = _generar(token, tmp_path, monkeypatch)
    finally:
        core.active_tokens.pop(token, None)
    assert res.status_code == 200, res.text


def test_la_generacion_no_persiste_la_clave_del_auto_match(tmp_path, monkeypatch):
    """El arreglo no corrige la columna: solo deja de dejarse tapar por
    ella. Persistir seria reescribir una resolucion manual sin que nadie lo
    haya pedido — eso es el issue #25, y es aviso, no correccion."""
    db_path, token = _bd(tmp_path, monkeypatch, [("F1", DESC, CLAVE_OBSOLETA)])
    try:
        assert _generar(token, tmp_path, monkeypatch).status_code == 200
    finally:
        core.active_tokens.pop(token, None)
    conn = sqlite3.connect(db_path)
    try:
        guardada = conn.execute(
            "SELECT clave_resuelta FROM facturas WHERE id_documento = 'F1'").fetchone()[0]
    finally:
        conn.close()
    assert guardada == CLAVE_OBSOLETA
