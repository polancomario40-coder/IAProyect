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


# ---- Rotacion de cartera (2026-11-19): "Solicitudes" por fecha de corte ----

def factura(cliente="IRUYA SRL", moneda="RD$", fecha="2026-10-31", **cambios):
    return {"fecha": fecha, "moneda": moneda, "cliente": cliente, "factura": "FT-00061555",
            "fechaFactura": "2026-10-20", "no_venc": 100, "d30": 50, "d60": 0, "d90": 0, "d120": 0,
            "balance": 150, **cambios}


def corte(filas, fecha="2026-10-31", tasa=60.5689):
    return {"desde": fecha, "hasta": fecha, "tasa": tasa, "filas": filas}


def test_la_cartera_se_guarda_por_corte_y_vuelve_con_la_clasificacion(cliente):
    c, h = cliente
    res = c.post("/api/logistica/indicadores/cartera", json=corte([factura(), factura("DOMICEM (MACAO)", "US$")]), headers=h)
    assert res.status_code == 200, res.text
    d = leer(c, h)
    assert [(f["fecha"], f["moneda"], f["cliente"], f["no_venc"], f["tasa"]) for f in d["cartera"]] == [
        ("2026-10-31", "RD$", "IRUYA SRL", 100, 60.5689), ("2026-10-31", "US$", "DOMICEM (MACAO)", 100, 60.5689)]
    assert d["fechas"]["cartera"] == ["2026-10-31"]
    # La clasificacion de octubre viene cargada en una base nueva.
    clas = {x["cliente"]: (x["zona"], x["trato"]) for x in d["cartera_clientes"]}
    assert len(clas) == 129
    assert clas["IRUYA SRL"] == ("Santo Domingo", "normal")
    assert clas["CONSTRUCTORA A E SRL"] == ("Santo Domingo", "especial")
    assert clas["DOMICEM (MACAO)"] == ("Punta Cana", "normal")
    assert clas["TEKTON SRL"] == (None, "fuera")
    # Subir el mismo corte otra vez lo reemplaza entero.
    res = c.post("/api/logistica/indicadores/cartera", json=corte([factura(no_venc=7)]), headers=h)
    assert res.json()["reemplazadas"] == 2
    assert [f["no_venc"] for f in leer(c, h)["cartera"]] == [7]


def test_la_cartera_es_un_corte_por_vez_y_con_dolares_pide_la_tasa(cliente):
    c, h = cliente
    def sube(cuerpo):
        return c.post("/api/logistica/indicadores/cartera", json=cuerpo, headers=h)
    res = sube({"desde": "2026-10-01", "hasta": "2026-10-31", "filas": [factura()]})
    assert (res.status_code, res.json()["detail"]) == (422, "un_solo_corte")
    res = sube(corte([factura(moneda="US$")], tasa=None))
    assert (res.status_code, res.json()["detail"]) == (422, "falta_tasa")
    assert sube(corte([factura()], tasa=None)).status_code == 200, "solo RD$ no necesita tasa"
    assert sube(corte([factura(moneda="EUR")])).status_code == 422
    assert sube(corte([factura(fecha="2026-10-30")])).status_code == 422, "fila de otro corte"


def test_la_zona_de_un_cliente_de_la_cartera_se_cambia(cliente):
    c, h = cliente
    def pon(cuerpo):
        return c.put("/api/logistica/cartera/clientes", json=cuerpo, headers=h)
    res = pon({"cliente": "ERIMIL SRL ", "zona": "Santo Domingo", "trato": "normal"})
    assert res.status_code == 200, res.text
    assert res.json() == {"cliente": "ERIMIL SRL", "zona": "Santo Domingo", "trato": "normal"}
    assert pon({"cliente": "IRUYA SRL", "zona": "Santo Domingo", "trato": "fuera"}).json()["zona"] is None
    clas = {x["cliente"]: (x["zona"], x["trato"]) for x in leer(c, h)["cartera_clientes"]}
    assert clas["ERIMIL SRL"] == ("Santo Domingo", "normal")
    assert clas["IRUYA SRL"] == (None, "fuera")
    assert len(clas) == 130
    res = pon({"cliente": "X", "zona": None, "trato": "normal"})
    assert (res.status_code, res.json()["detail"]) == (422, "falta_zona")
    assert pon({"cliente": "X", "zona": "Santiago", "trato": "normal"}).status_code == 422
    assert pon({"cliente": "X", "zona": "Punta Cana", "trato": "otro"}).status_code == 422
    assert c.put("/api/logistica/cartera/clientes", json={"cliente": "X", "zona": "Punta Cana", "trato": "normal"}).status_code == 401
    assert c.post("/api/logistica/indicadores/cartera", json=corte([factura()])).status_code == 401


# ---- Cumplimiento a cubicacion (2026-11-19): el empleado del reporte de tiempos ----

def test_el_reporte_de_tiempos_guarda_el_empleado(cliente):
    c, h = cliente
    res = c.post("/api/logistica/indicadores/tiempos", headers=h, json={
        "desde": "2026-10-01", "hasta": "2026-10-01",
        "filas": [pedido(empleado="ZABDIEL FRUCTUOSO"), pedido(ordComp="00112597")]})
    assert res.status_code == 200, res.text
    assert [(f["ord_comp"], f["empleado"]) for f in leer(c, h)["tiempos"]] == [
        ("00112596", "ZABDIEL FRUCTUOSO"), ("00112597", None)]


def test_una_base_sin_la_columna_empleado_la_recibe(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "LOG_DB_PATH", str(tmp_path / "vieja.db"))
    core.setup_logistica_db()
    conn = core._log_conn()
    try:
        conn.execute("ALTER TABLE logistica_tiempo_pedido DROP COLUMN empleado")
        core.setup_logistica_db(conn)
        assert "empleado" in [c[1] for c in conn.execute("PRAGMA table_info(logistica_tiempo_pedido)")]
    finally:
        conn.close()


# ---- Resistencia a compresion (2026-11-19): las roturas de Calidad ----

def test_las_roturas_se_guardan_por_rango(cliente):
    c, h = cliente
    fila = {"fecha": "2026-10-01", "planta": "Movil VII", "conduce": "M200122790", "cliente": "TERRAMARE",
            "producto": "HORMIGON 350", "fc": 350, "r7": 391.08, "r28": 510.48}
    res = c.post("/api/logistica/indicadores/roturas", headers=h, json={
        "desde": "2026-10-01", "hasta": "2026-10-03", "filas": [fila, {**fila, "fecha": "2026-10-03", "r28": None}]})
    assert res.status_code == 200, res.text
    d = leer(c, h)
    assert [(f["fecha"], f["planta"], f["fc"], f["r28"]) for f in d["roturas"]] == [
        ("2026-10-01", "Movil VII", 350, 510.48), ("2026-10-03", "Movil VII", 350, None)]
    assert d["fechas"]["roturas"] == ["2026-10-01", "2026-10-03"]
    # Subir el rango de nuevo lo reemplaza; una rotura en 0 o una fila fuera del rango no entran.
    assert c.post("/api/logistica/indicadores/roturas", headers=h, json={
        "desde": "2026-10-01", "hasta": "2026-10-03", "filas": [fila]}).json()["reemplazadas"] == 2
    assert c.post("/api/logistica/indicadores/roturas", headers=h, json={
        "desde": "2026-10-01", "hasta": "2026-10-03", "filas": [{**fila, "r28": 0}]}).status_code == 422
    assert c.post("/api/logistica/indicadores/roturas", headers=h, json={
        "desde": "2026-10-01", "hasta": "2026-10-02", "filas": [{**fila, "fecha": "2026-10-05"}]}).status_code == 422
    assert c.post("/api/logistica/indicadores/roturas", json={"desde": "2026-10-01", "hasta": "2026-10-01", "filas": []}).status_code == 401


# ---- Compras: entregas en el plazo (2026-11-19) ----

def test_las_compras_se_guardan_por_rango_de_la_oc(cliente):
    c, h = cliente
    linea = {"fecha": "2026-10-30", "solicitud": "59781-33", "descripcion": "ALAMBRE", "fechaSolicitud": "2025-07-29",
             "fechaRecepcion": "2026-11-19", "dias": 477, "objetivo": 30, "aplica": True, "cumple": False}
    res = c.post("/api/logistica/indicadores/compras", headers=h, json={
        "desde": "2026-10-01", "hasta": "2026-10-31", "filas": [linea, {**linea, "solicitud": "65833-1", "dias": 3, "cumple": True}]})
    assert res.status_code == 200, res.text
    d = leer(c, h)
    assert [(f["solicitud"], f["dias"], f["objetivo"], f["aplica"], f["cumple"]) for f in d["compras"]] == [
        ("59781-33", 477, 30, 1, 0), ("65833-1", 3, 30, 1, 1)]
    assert d["fechas"]["compras"] == ["2026-10-30"]
    assert c.post("/api/logistica/indicadores/compras", headers=h, json={
        "desde": "2026-10-01", "hasta": "2026-10-31", "filas": [linea]}).json()["reemplazadas"] == 2
    assert c.post("/api/logistica/indicadores/compras", headers=h, json={
        "desde": "2026-10-01", "hasta": "2026-10-31", "filas": [{**linea, "cumple": None}]}).status_code == 422
    assert c.post("/api/logistica/indicadores/compras", json={"desde": "2026-10-01", "hasta": "2026-10-01", "filas": []}).status_code == 401
