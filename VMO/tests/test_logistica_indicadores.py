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


# ---- Cinco listas mas de CBS (2026-11-17) ----

def batchada(fecha="2026-10-01", planta="SDN", **cambios):
    return {"fecha": fecha, "planta": planta, "conduce": "158559", "m3": 7, "minutos": 4.5, "estado": "Realizado",
            "dev_cemento": 0.4, "dev_agregados": -1.2, "dev_agua": 2.5, "dev_aditivos": None, **cambios}


def subir(c, h, tipo, filas, desde="2026-10-01", hasta="2026-10-31", **extra):
    return c.post(f"/api/logistica/indicadores/{tipo}", headers=h,
                  json={"desde": desde, "hasta": hasta, "filas": filas, **extra})


def test_los_reportes_nuevos_se_guardan_y_vuelven(cliente):
    c, h = cliente
    assert subir(c, h, "disponibilidad", [
        {"fecha": "2026-10-01", "tipo": "TROMPOS", "equipo": "F-1", "utilizado": 3, "disponible": 1},
        {"fecha": "2026-10-01", "tipo": "CAMION BOMBA", "equipo": "Bom.20", "utilizado": 0, "disponible": None}]).status_code == 200
    assert subir(c, h, "incidencias", [{"fecha": "2026-10-02", "planta": "Movil IV", "cliente": "ACME",
                                        "volumen": 59, "percepcion": "Tardanza Bomba"}]).status_code == 200
    assert subir(c, h, "reclamos", [{"fecha": "2026-10-05", "reclamo": "00001166", "cliente": "DICONFO",
                                     "tipo": "Reclamo", "estado": "PENDIENTE", "procede": "PROCEDE", "costo": 1151.44}]).status_code == 200
    assert subir(c, h, "anulados", [{"fecha": "2026-10-03", "conduce": "M800016622", "planta": "Movil VIII",
                                     "cliente": "MACAO", "m3": 3.5, "causa": "DESPERDICIO", "comentario": "tuberia tapada"}]).status_code == 200
    d = leer(c, h)
    assert [(f["equipo"], f["disponible"]) for f in sorted(d["disponibilidad"], key=lambda f: f["equipo"])] == [("Bom.20", None), ("F-1", 1)]
    assert d["incidencias"][0]["percepcion"] == "Tardanza Bomba"
    assert (d["reclamos"][0]["estado"], d["reclamos"][0]["costo"]) == ("PENDIENTE", 1151.44)
    assert (d["anulados"][0]["causa"], d["anulados"][0]["m3"]) == ("DESPERDICIO", 3.5)
    assert d["fechas"]["reclamos"] == ["2026-10-05"]
    assert d["bombeo"] == [] and d["tiempos"] == [], "los dos de antes siguen en la respuesta"


def test_las_batchadas_de_un_formato_no_borran_las_del_otro(cliente):
    """SDN y las moviles vienen en dos Excel con las mismas fechas: subir uno
    no puede borrar el otro."""
    c, h = cliente
    assert subir(c, h, "batchadas", [batchada()], fuente="sdn").status_code == 200
    assert subir(c, h, "batchadas", [batchada(planta="Movil II"), batchada(planta="Movil II", minutos=None)],
                 fuente="moviles").status_code == 200
    assert sorted(f["planta"] for f in leer(c, h)["batchadas"]) == ["Movil II", "Movil II", "SDN"]
    res = subir(c, h, "batchadas", [batchada(minutos=5)], fuente="sdn")
    assert res.json()["reemplazadas"] == 1
    d = leer(c, h)["batchadas"]
    assert sorted((f["planta"], f["minutos"]) for f in d if f["planta"] == "SDN") == [("SDN", 5)]
    assert len(d) == 3
    assert subir(c, h, "batchadas", [batchada()], fuente="otra").status_code == 422


def test_los_reportes_nuevos_rechazan_repetidos_y_valores_imposibles(cliente):
    c, h = cliente
    eq = {"fecha": "2026-10-01", "tipo": "TROMPOS", "equipo": "F-1", "utilizado": 1, "disponible": 1}
    assert subir(c, h, "disponibilidad", [eq, eq]).status_code == 422
    assert subir(c, h, "disponibilidad", [{**eq, "disponible": 2}]).status_code == 422
    rec = {"fecha": "2026-10-05", "reclamo": "1", "estado": "PENDIENTE"}
    assert subir(c, h, "reclamos", [rec, rec]).status_code == 422
    anu = {"fecha": "2026-10-03", "conduce": "M1", "m3": 1}
    assert subir(c, h, "anulados", [anu, anu]).status_code == 422
    assert subir(c, h, "incidencias", [{"fecha": "2026-11-09"}]).status_code == 422, "fuera del rango"
    d = leer(c, h)
    assert all(d[k] == [] for k in ("disponibilidad", "reclamos", "anulados", "incidencias"))


def test_las_rutas_nuevas_piden_token(cliente):
    c, _ = cliente
    for tipo in ("disponibilidad", "batchadas", "incidencias", "reclamos", "anulados"):
        assert c.post(f"/api/logistica/indicadores/{tipo}",
                      json={"desde": "2026-10-01", "hasta": "2026-10-01", "fuente": "sdn", "filas": []}).status_code == 401, tipo
