"""
El Excel del Reporte de cancelados (2026-10-12), por HTTP.

Que es un cancelado y como se resume NO se prueba aca: lo arma
reporteCancelados() en static/logistica.logic.js y lo cubre
tests/logistica/reporte_cancelados.test.js. Aca se prueba lo que hace la
ruta: el formato, las tablas, y que un texto de los datos no se vuelva formula.

Correr solo estas:  python -m pytest tests/test_logistica_reporte_cancelados.py -v
"""
import io
import os
import sys
import uuid
from datetime import datetime, time

import openpyxl
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import main  # noqa: E402

ENCABEZADO = ["FECHA", "SEMANAS PROGRAMADAS", "HORA PROGRAMADA", "CLIENTE", "OBRA", "VENDEDOR",
              "ZONA", "ELEMENTO", "TIPO DE SERVICIO", "PRODUCTO", "VOL. PROGRAMADO",
              "RAZON", "RESPONSABLE", "MOTIVO"]


@pytest.fixture
def cliente():
    token = f"test-{uuid.uuid4().hex}"
    core.active_tokens[token] = datetime.now()
    yield TestClient(main.app), {"Authorization": f"Bearer {token}"}
    core.active_tokens.pop(token, None)


def fila(fecha="2026-10-02", cliente="ACME", **cambios):
    base = {"fecha": fecha, "semana": "SEMANA 1- OCTUBRE", "horaFraccion": 0.375,
            "cliente": cliente, "obra": "TORRE", "vendedor": "Ana", "zona": "SANTO DOMINGO",
            "elemento": "LOSA", "servicio": "BOMBA", "producto": "H210", "volumen": 10,
            "razon": "llovio", "responsable": "VMO",
            "motivo": "PROBLEMAS CLIMATICOS"}
    base.update(cambios)
    return base


def pedido(filas=None, **cambios):
    filas = [fila()] if filas is None else filas
    base = {
        "desde": "2026-10-01", "hasta": "2026-10-05", "encabezado": ENCABEZADO, "filas": filas,
        "resumen": {
            "diasRevisados": 2, "diasConCancelados": 1 if filas else 0, "entregas": len(filas),
            "m3Cancelado": sum(f["volumen"] for f in filas),
            "porDia": [{"fecha": "2026-10-02", "entregas": len(filas), "m3Cancelado": 10},
                       {"fecha": "2026-10-03", "entregas": 0, "m3Cancelado": 0}],
            "porMotivo": [{"nombre": "PROBLEMAS CLIMATICOS", "entregas": 1, "m3Cancelado": 10,
                           "pct": 100}] if filas else [],
            "porResponsable": [{"nombre": "VMO", "entregas": 1, "m3Cancelado": 10,
                                "pct": 100}] if filas else [],
        },
    }
    base.update(cambios)
    return base


def libro(res):
    assert res.status_code == 200, res.text
    return openpyxl.load_workbook(io.BytesIO(res.content))


def test_sin_sesion_no_hay_reporte(cliente):
    c, _ = cliente
    assert c.post("/api/logistica/reporte-cancelados", json=pedido()).status_code == 401


def test_devuelve_un_excel_con_el_nombre_del_rango(cliente):
    c, h = cliente
    res = c.post("/api/logistica/reporte-cancelados", json=pedido(), headers=h)
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert 'filename="Cancelados_VMO_2026-10-01_al_2026-10-05.xlsx"' in res.headers["content-disposition"]
    assert libro(res).sheetnames == ["Cancelados", "Resumen"]


def test_la_hoja_de_cancelados_es_una_tabla_con_fecha_hora_y_totales(cliente):
    c, h = cliente
    filas = [fila(), fila(cliente="BETA", volumen=20)]
    ws = libro(c.post("/api/logistica/reporte-cancelados", json=pedido(filas), headers=h))["Cancelados"]
    assert [ws.cell(row=4, column=j).value for j in range(1, 15)] == ENCABEZADO
    assert list(ws.tables) == ["Cancelados"]
    assert ws.tables["Cancelados"].ref == "A4:N6"
    assert ws["A5"].value == datetime(2026, 10, 2)
    assert ws["A5"].number_format == "dd/mm/yyyy"
    assert ws["C5"].value == time(9, 0) and "h:mm" in ws["C5"].number_format, "9:00 como hora de Excel"
    assert (ws["D5"].value, ws["E5"].value, ws["K5"].value) == ("ACME", "TORRE", 10)
    # La fila de total, debajo de la tabla y fuera de ella.
    assert ws["A7"].value == "TOTAL"
    assert ws["K7"].value == 30
    assert ws.freeze_panes == "A5"


def test_el_resumen_trae_los_totales_y_las_tres_tablas(cliente):
    c, h = cliente
    wr = libro(c.post("/api/logistica/reporte-cancelados", json=pedido(), headers=h))["Resumen"]
    etiquetas = {wr.cell(row=i, column=1).value: wr.cell(row=i, column=2).value for i in range(4, 8)}
    assert etiquetas["Pedidos cancelados (sin nada despachado)"] == 1
    assert etiquetas["m³ cancelados"] == 10
    assert etiquetas["Días guardados en el rango"] == 2
    assert sorted(wr.tables) == ["PorDia", "PorMotivo", "PorResponsable"]
    assert wr["E11"].value == "PROBLEMAS CLIMATICOS"
    assert wr["H11"].value == 1 and wr["H11"].number_format == "0%"
    assert wr["J11"].value == "VMO"
    assert wr["A12"].value == datetime(2026, 10, 3), "un dia sin cancelados igual aparece"


def test_un_texto_que_empieza_con_igual_queda_como_texto(cliente):
    """Cliente, obra y razon salen de los Excel que se suben y de lo que se
    escribe a mano: una `=HYPERLINK(...)` no puede volverse formula."""
    c, h = cliente
    peligro = '=HYPERLINK("http://x.example","clic")'
    ws = libro(c.post("/api/logistica/reporte-cancelados",
                      json=pedido([fila(cliente=peligro, razon="=1+1")]), headers=h))["Cancelados"]
    assert ws["D5"].value == peligro and ws["D5"].data_type == "s"
    assert ws["L5"].data_type == "s"


def test_un_rango_sin_cancelados_da_un_excel_sin_tabla(cliente):
    c, h = cliente
    wb = libro(c.post("/api/logistica/reporte-cancelados", json=pedido([]), headers=h))
    assert list(wb["Cancelados"].tables) == []
    assert "No hay pedidos cancelados" in wb["Cancelados"]["A4"].value
    assert list(wb["Resumen"].tables) == ["PorDia"]


def test_rango_invertido_o_fecha_mala_se_rechaza(cliente):
    c, h = cliente
    assert c.post("/api/logistica/reporte-cancelados",
                  json=pedido(desde="2026-10-09", hasta="2026-10-01"), headers=h).status_code == 400
    assert c.post("/api/logistica/reporte-cancelados",
                  json=pedido(desde="9/10/2026"), headers=h).status_code == 422
