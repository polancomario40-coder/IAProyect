"""
Los dos reportes del sistema de la pagina Indicadores (2026-10-28), por HTTP:
"Metros bombeados por equipo" y "Cumplimiento de tiempos de despacho". Se
suben por rango de fechas y lo nuevo reemplaza ese rango; el calculo vive en
static/logistica.logic.js y lo cubre tests/logistica/indicadores.test.js.

Ninguna prueba toca la base real: `core.LOG_DB_PATH` se apunta a tmp_path.
"""
import os
import sys
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import main  # noqa: E402


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "LOG_DB_PATH", str(tmp_path / "logistica.db"))
    token = f"test-{uuid.uuid4().hex}"
    core.active_tokens[token] = datetime.now()
    yield TestClient(main.app), {"Authorization": f"Bearer {token}"}
    core.active_tokens.pop(token, None)


def bombeo(desde="2026-10-01", hasta="2026-10-03", filas=None):
    return {"desde": desde, "hasta": hasta, "filas": filas if filas is not None else [
        {"fecha": "2026-10-01", "equipo": "B-44", "nombre": "Bom.44", "m3": 207},
        {"fecha": "2026-10-02", "equipo": "B-44", "nombre": "Bom.44", "m3": 251.5},
        {"fecha": "2026-10-01", "equipo": "700", "nombre": "Alquilada", "m3": 30.5},
    ]}


def pedido(fecha="2026-10-01", **cambios):
    return {"fecha": fecha, "ordComp": "00112596", "planta": "SanIsidro", "cliente": "CIVILTEC",
            "horaIni": 480, "horaFin": 900, "cantidad": 60.5, "totalIn": 46, "logro": "NO",
            "totalDespachado": 60.5, "viajesProgramados": 9, "viajesEfectuados": 7, "bomba": "40", **cambios}


def leer(c, h, desde="2026-10-01", hasta="2026-10-31"):
    res = c.get(f"/api/logistica/indicadores?desde={desde}&hasta={hasta}", headers=h)
    assert res.status_code == 200, res.text
    return res.json()


def test_el_bombeo_se_guarda_y_vuelve(cliente):
    c, h = cliente
    res = c.post("/api/logistica/indicadores/bombeo", json=bombeo(), headers=h)
    assert res.status_code == 200, res.text
    assert res.json()["filas"] == 3
    d = leer(c, h)
    assert sorted((f["fecha"], f["equipo"], f["m3"]) for f in d["bombeo"]) == [
        ("2026-10-01", "700", 30.5), ("2026-10-01", "B-44", 207), ("2026-10-02", "B-44", 251.5)]
    assert d["fechas"]["bombeo"] == ["2026-10-01", "2026-10-02"]


def test_subir_otra_vez_reemplaza_solo_ese_rango(cliente):
    """Lo nuevo pisa las fechas de su rango, incluso un dia que ahora viene
    vacio; las fechas de afuera quedan como estaban."""
    c, h = cliente
    c.post("/api/logistica/indicadores/bombeo", json=bombeo(), headers=h)
    res = c.post("/api/logistica/indicadores/bombeo", headers=h, json=bombeo(
        desde="2026-10-02", hasta="2026-10-02", filas=[]))
    assert res.json()["reemplazadas"] == 1
    d = leer(c, h)
    assert sorted((f["fecha"], f["equipo"]) for f in d["bombeo"]) == [("2026-10-01", "700"), ("2026-10-01", "B-44")]


def test_los_tiempos_se_guardan_y_vuelven_con_las_horas(cliente):
    c, h = cliente
    res = c.post("/api/logistica/indicadores/tiempos", headers=h, json={
        "desde": "2026-10-01", "hasta": "2026-10-05",
        "filas": [pedido(), pedido("2026-10-05", horaFin=None, cliente="ABREU")]})
    assert res.status_code == 200, res.text
    d = leer(c, h)
    assert [(f["fecha"], f["cliente"], f["hora_ini"], f["hora_fin"], f["total_in"]) for f in d["tiempos"]] == [
        ("2026-10-01", "CIVILTEC", 480, 900, 46), ("2026-10-05", "ABREU", 480, None, 46)]
    assert d["fechas"]["tiempos"] == ["2026-10-01", "2026-10-05"]


def test_una_fila_fuera_del_rango_se_rechaza_sin_escribir(cliente):
    """Lo que se borra es el rango: una fila de afuera quedaria pisando otra
    fecha sin que nadie lo pidiera."""
    c, h = cliente
    res = c.post("/api/logistica/indicadores/tiempos", headers=h, json={
        "desde": "2026-10-01", "hasta": "2026-10-02", "filas": [pedido("2026-10-09")]})
    assert res.status_code == 422
    assert leer(c, h)["tiempos"] == []


def test_un_rango_al_reves_o_un_equipo_repetido_se_rechazan(cliente):
    c, h = cliente
    assert c.post("/api/logistica/indicadores/bombeo", headers=h,
                  json=bombeo(desde="2026-10-03", hasta="2026-10-01", filas=[])).status_code == 422
    repetido = [{"fecha": "2026-10-01", "equipo": "B-44", "m3": 1}, {"fecha": "2026-10-01", "equipo": "B-44", "m3": 2}]
    assert c.post("/api/logistica/indicadores/bombeo", headers=h,
                  json=bombeo(filas=repetido)).status_code == 422


def test_las_rutas_piden_token(cliente):
    c, _ = cliente
    assert c.post("/api/logistica/indicadores/bombeo", json=bombeo()).status_code == 401
    assert c.post("/api/logistica/indicadores/tiempos", json={"desde": "2026-10-01", "hasta": "2026-10-01", "filas": []}).status_code == 401
    assert c.get("/api/logistica/indicadores?desde=2026-10-01&hasta=2026-10-31").status_code == 401


def test_una_fecha_mal_escrita_se_rechaza(cliente):
    c, h = cliente
    assert c.get("/api/logistica/indicadores?desde=ayer&hasta=2026-10-31", headers=h).status_code == 422
    assert c.post("/api/logistica/indicadores/bombeo", headers=h,
                  json=bombeo(desde="01/10/2026")).status_code == 422
