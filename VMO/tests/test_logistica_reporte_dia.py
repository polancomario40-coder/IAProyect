"""
El PDF del Reporte del dia (2026-10-15), por HTTP.

Los numeros NO se prueban aca: los arma reporteDelDia() en
static/logistica.logic.js y los cubre tests/logistica/reporte_dia.test.js.
Aca se prueba lo que hace la ruta: que pida sesion, que valide lo que llega
y que el PDF diga lo que recibio.

Correr solo estas:  python -m pytest tests/test_logistica_reporte_dia.py -v
"""
import os
import sys
import uuid
from datetime import datetime

import fitz
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import main  # noqa: E402


@pytest.fixture
def cliente():
    token = f"test-{uuid.uuid4().hex}"
    core.active_tokens[token] = datetime.now()
    yield TestClient(main.app), {"Authorization": f"Bearer {token}"}
    core.active_tokens.pop(token, None)


def bloque(nombre, pct=54, pct_pedidos=62):
    return {"nombre": nombre, "pct": pct, "pctPedidos": pct_pedidos, "pedidos": 21,
            "pedidosCumplidos": 13, "m3": 1216, "m3Cumplidos": 651, "incumplidos": 8,
            "m3Despachado": 1278, "cargues": 143, "camiones": 55}


def entrega(cliente="ACME SRL", estado="Incumplido", **cambios):
    base = {"cliente": cliente, "obra": "TORRE", "elemento": "LOSA", "servicio": "Con bomba",
            "horaProg": 480, "cantProg": 16, "cantReal": 16, "cargues": 2, "primerCargue": 450,
            "planta": "Movil II", "zona": "Santo Domingo", "llegada": 525, "diff": 45,
            "estado": estado, "responsable": "VMO", "motivo": "TARDANZA DE BOMBA",
            "observacion": ""}
    base.update(cambios)
    return base


def pedido(**cambios):
    base = {
        "desde": "2026-10-14",
        "hasta": "2026-10-14",
        "supuestos": {"cargue": 15, "calidad": 10, "tolerancia": 30, "ajusteHora": 60},
        "nombres": {"pct": "Frecuencia de despacho", "pctPedidos": "Inicio de carga"},
        "bloques": [bloque("General"), bloque("Santo Domingo", 66, 69), bloque("Punta Cana", 20, 40),
                    bloque("Con bomba"), bloque("Directo", None, None)],
        "noEvaluables": [{"estado": "Sin programación", "entregas": 1}],
        "porResponsable": [{"nombre": "VMO", "entregas": 1, "m3": 16, "pct": 100, "pctAcumulado": 100,
                            "detalle": "VMO 1"}],
        "porMotivo": [{"nombre": "TARDANZA DE BOMBA", "entregas": 1, "m3": 16, "pct": 100,
                       "pctAcumulado": 100, "detalle": "VMO 1"}],
        "cobertura": {"incumplidos": 1, "sinMotivo": 0, "sinResponsable": 0},
        "entregas": [entrega(), entrega("BETA SA", "Cumplido", responsable="", motivo="",
                                        observacion="llegó antes")],
    }
    base.update(cambios)
    return base


def texto_del_pdf(res):
    doc = fitz.open(stream=res.content, filetype="pdf")
    return doc.page_count, "\n".join(p.get_text() for p in doc)


def test_devuelve_un_pdf_con_el_resumen_y_el_detalle(cliente):
    c, h = cliente
    res = c.post("/api/logistica/reporte-dia", json=pedido(), headers=h)
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/pdf"
    assert 'filename="Reporte_dia_VMO_2026-10-14.pdf"' in res.headers["content-disposition"]
    paginas, texto = texto_del_pdf(res)
    assert paginas == 2, "resumen y detalle"
    for esperado in ("Reporte del día", "miércoles 14/10/2026", "Tolerancia 30 min", "Frecuencia de despacho", "54%",
                     "Inicio de carga", "62%", "Santo Domingo", "Directo", "TARDANZA DE BOMBA",
                     "Detalle de entregas", "ACME SRL", "BETA SA", "Obs.: llegó antes",
                     "Sin programación 1", "Página 2 de 2"):
        assert esperado in texto, esperado


def test_cada_pagina_lleva_el_logo_en_la_banda_y_la_imagen_va_una_sola_vez(cliente):
    # Diseno con banda (2026-10-22): logo de VMO arriba a la izquierda en
    # todas las paginas, sin repetir la imagen dentro del PDF.
    c, h = cliente
    res = c.post("/api/logistica/reporte-dia", headers=h,
                 json=pedido(entregas=[entrega(f"CLIENTE {i}") for i in range(90)]))
    doc = fitz.open(stream=res.content, filetype="pdf")
    assert doc.page_count >= 3
    xrefs = set()
    for pagina in doc:
        imagenes = pagina.get_images()
        assert len(imagenes) == 1
        xrefs.add(imagenes[0][0])
        rect = pagina.get_image_rects(imagenes[0][0])[0]
        assert rect.y1 <= core._LOG_BANDA_ALTO and rect.x0 < 100
    assert len(xrefs) == 1
    assert "VMO Concretos · Logística" in doc[0].get_text()


def test_sin_incumplidas_lo_dice_en_vez_de_tablas_vacias(cliente):
    c, h = cliente
    res = c.post("/api/logistica/reporte-dia", headers=h, json=pedido(
        porResponsable=[], porMotivo=[], cobertura={"incumplidos": 0, "sinMotivo": 0, "sinResponsable": 0},
        entregas=[entrega(estado="Cumplido")]))
    assert res.status_code == 200
    assert "Ninguna entrega incumplida" in texto_del_pdf(res)[1]


def test_avisa_las_incumplidas_sin_motivo(cliente):
    c, h = cliente
    res = c.post("/api/logistica/reporte-dia", headers=h, json=pedido(
        cobertura={"incumplidos": 3, "sinMotivo": 2, "sinResponsable": 1}))
    assert "2 sin motivo y 1 sin responsable" in texto_del_pdf(res)[1]


def test_muchas_entregas_siguen_en_mas_paginas(cliente):
    c, h = cliente
    res = c.post("/api/logistica/reporte-dia", headers=h,
                 json=pedido(entregas=[entrega(f"CLIENTE {i}") for i in range(90)]))
    paginas, texto = texto_del_pdf(res)
    assert paginas >= 3
    assert "CLIENTE 89" in texto
    assert f"Página {paginas} de {paginas}" in texto


def test_pide_sesion_y_valida_lo_que_llega(cliente):
    c, h = cliente
    assert c.post("/api/logistica/reporte-dia", json=pedido()).status_code == 401
    assert c.post("/api/logistica/reporte-dia", headers=h,
                  json=pedido(desde="2026-13-45", hasta="2026-13-45")).status_code == 400
    assert c.post("/api/logistica/reporte-dia", headers=h, json=pedido(desde="14/10/2026")).status_code == 422
    assert c.post("/api/logistica/reporte-dia", headers=h,
                  json=pedido(desde="2026-10-15", hasta="2026-10-14")).status_code == 400
    malo = pedido()
    malo["bloques"][0]["pct"] = 140
    assert c.post("/api/logistica/reporte-dia", headers=h, json=malo).status_code == 422
    assert c.post("/api/logistica/reporte-dia", headers=h,
                  json=pedido(entregas=[entrega(observacion="x" * 1001)])).status_code == 422


# ── Rango de fechas (2026-10-21) ──────────────────────────────────────────

def pedido_rango(**cambios):
    dias = [dict(bloque("2026-10-13", 40, 50)), dict(bloque("2026-10-14", 60, 70))]
    base = pedido(desde="2026-10-13", hasta="2026-10-14", porDia=dias,
                  entregas=[entrega("ACME SRL", fecha="2026-10-13"), entrega("BETA SA", "Cumplido", fecha="2026-10-14")])
    base.update(cambios)
    return base


def test_un_rango_lleva_las_fechas_el_renglon_por_dia_y_la_fecha_de_cada_entrega(cliente):
    c, h = cliente
    res = c.post("/api/logistica/reporte-dia", json=pedido_rango(), headers=h)
    assert res.status_code == 200, res.text
    assert 'filename="Reporte_VMO_2026-10-13_al_2026-10-14.pdf"' in res.headers["content-disposition"]
    paginas, texto = texto_del_pdf(res)
    assert paginas == 3, "resumen, por dia y detalle"
    for esperado in ("Reporte del período", "13/10/2026 al 14/10/2026", "2 días guardados", "Por día",
                     "mar 13/10", "mié 14/10", "Fecha", "13/10", "todo el cargue del período",
                     "no promedian", "Página 3 de 3"):
        assert esperado in texto, esperado
    assert "Reporte del día" not in texto


def test_un_dia_no_lleva_la_pagina_por_dia(cliente):
    c, h = cliente
    res = c.post("/api/logistica/reporte-dia", headers=h, json=pedido(porDia=[bloque("2026-10-14")]))
    paginas, texto = texto_del_pdf(res)
    assert paginas == 2
    assert "Por día" not in texto


def test_un_supuesto_que_vario_dice_varia(cliente):
    c, h = cliente
    res = c.post("/api/logistica/reporte-dia", headers=h, json=pedido_rango(
        supuestos={"cargue": 15, "calidad": 10, "tolerancia": None, "ajusteHora": 60, "varian": ["tolerancia"]}))
    texto = texto_del_pdf(res)[1]
    assert "Tolerancia varía" in texto
    assert "la tolerancia de cada día" in texto


def test_muchos_dias_siguen_en_mas_paginas(cliente):
    c, h = cliente
    dias = [bloque(f"2026-08-{d:02d}") for d in range(1, 32)] + [bloque(f"2026-09-{d:02d}") for d in range(1, 31)]
    res = c.post("/api/logistica/reporte-dia", headers=h,
                 json=pedido_rango(desde="2026-08-01", hasta="2026-09-30", porDia=dias))
    assert res.status_code == 200, res.text
    paginas, texto = texto_del_pdf(res)
    assert paginas >= 4
    assert "mié 30/09" in texto


def test_en_un_rango_camiones_es_promedio_por_dia(cliente):
    c, h = cliente
    rango = pedido_rango()
    rango["bloques"][0]["camiones"] = 41.5
    res = c.post("/api/logistica/reporte-dia", headers=h, json=rango)
    assert res.status_code == 200, res.text
    texto = texto_del_pdf(res)[1]
    assert "41.5" in texto
    assert "promedio por día" in texto


# ── Incumplidas del cliente y de VMO, por servicio y compania ──────────
# (cliente 2026-10-21; VMO y Con bomba / Directo 2026-10-22)

def grupo(nombre, entregas, pct, detalle=""):
    return {"nombre": nombre, "entregas": entregas, "m3": entregas * 8.0, "pct": pct,
            "pctAcumulado": pct, "detalle": detalle}


def responsable(quien, **servicios):
    """responsable("VMO", bomba=[grupos], directo=[grupos])"""
    nombres = {"bomba": "Con bomba", "directo": "Directo"}
    servs = [{"servicio": nombres[k], "entregas": sum(g["entregas"] for g in v),
              "m3": sum(g["m3"] for g in v), "companias": v} for k, v in servicios.items()]
    return {"responsable": quien, "entregas": sum(x["entregas"] for x in servs), "servicios": servs}


def test_cliente_y_vmo_van_por_servicio_y_por_compania(cliente):
    c, h = cliente
    res = c.post("/api/logistica/reporte-dia", headers=h, json=pedido(incumplidasPorResponsable=[
        responsable("Cliente", bomba=[grupo("FIDEICOMISO OPUS", 3, 75, "RETRASOS EN OBRA 2, SIN COLOCACION 1"),
                                      grupo("ALBA SANCHEZ", 1, 25, "ELEMENTO NO LISTO 1")],
                    directo=[grupo("CORALES DEL CARIBE", 2, 100, "RETRASOS EN OBRA 2")]),
        responsable("VMO", bomba=[grupo("SYGEN", 1, 100, "TARDANZA DE BOMBA 1")])]))
    assert res.status_code == 200, res.text
    doc = fitz.open(stream=res.content, filetype="pdf")
    assert doc.page_count == 4, "resumen, cliente, VMO y detalle"
    cli, vmo = doc[1].get_text(), doc[2].get_text()
    for esperado in ("Incumplidas del cliente", "6 incumplidas con responsable Cliente · Con bomba 4 · Directo 2",
                     "Con bomba · 4 incumplidas", "Directo · 2 incumplidas", "FIDEICOMISO OPUS",
                     "RETRASOS EN OBRA 2, SIN COLOCACION 1", "CORALES DEL CARIBE", "75%", "% del servicio"):
        assert esperado in cli, esperado
    for esperado in ("Incumplidas de VMO", "1 incumplida con responsable VMO · Con bomba 1", "SYGEN",
                     "TARDANZA DE BOMBA 1"):
        assert esperado in vmo, esperado
    assert "Directo" not in vmo.split("Con bomba 1")[1].split("Solo las")[0]


def test_sin_incumplidas_del_cliente_ni_de_vmo_no_van_las_paginas(cliente):
    c, h = cliente
    paginas, texto = texto_del_pdf(c.post("/api/logistica/reporte-dia", headers=h, json=pedido()))
    assert paginas == 2
    assert "Incumplidas del cliente" not in texto and "Incumplidas de VMO" not in texto


def test_muchas_companias_siguen_en_otra_pagina(cliente):
    c, h = cliente
    res = c.post("/api/logistica/reporte-dia", headers=h, json=pedido(incumplidasPorResponsable=[
        responsable("Cliente", bomba=[grupo(f"COMPANIA {i}", 1, 2) for i in range(30)],
                    directo=[grupo(f"OTRA {i}", 1, 4) for i in range(25)])]))
    assert res.status_code == 200, res.text
    paginas, texto = texto_del_pdf(res)
    assert paginas == 5, "resumen, 3 del cliente y detalle"
    assert "COMPANIA 29" in texto and "OTRA 24" in texto and "(sigue)" in texto


def test_un_responsable_que_no_es_cliente_ni_vmo_se_rechaza(cliente):
    c, h = cliente
    res = c.post("/api/logistica/reporte-dia", headers=h, json=pedido(incumplidasPorResponsable=[
        responsable("Externo", bomba=[grupo("X", 1, 100)])]))
    assert res.status_code == 422
