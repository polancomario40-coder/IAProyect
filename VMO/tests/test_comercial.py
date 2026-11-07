"""
Modulo Comercial (2026-10-19): leer los Excel, guardarlos y devolverlos.

Los numeros del dashboard NO se prueban aca: los arma dashboard() en
static/comercial.logic.js y los cubre tests/logistica/comercial.test.js.
Aca va lo del servidor: que lea los dos formatos reales del despachos (el
.xls del mes y la hoja ACUMULADO), que un mes nuevo reemplace solo ese mes,
que el plan salga de la fila DESPACHOS HORMIGON, que todo pida sesion y que
use su propia base.

Correr solo estas:  python -m pytest tests/test_comercial.py -v
"""
import io
import os
import sys
import uuid
from datetime import datetime

import openpyxl
import pytest
import xlwt
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import main  # noqa: E402

TITULOS_MES = ["COLUMN1", "idPlanta", "idCliente", "Cliente", "Conduce", "fecha", "Categoria", "idCondicion",
               "idProducto", "Producto", "Cantidad", "Precio", "LineTotal", "Preciominimo", "Direccion", "ZONA",
               "RANGO FC "]
TITULOS_ACUMULADO = ["VENDEDOR", "PLANTA", "ID CLIENTE", "CLIENTE", "CONDUCE", "FECHA", "CATEGORIA", "CONDICION ",
                     "ID PRODUCTO", "PRODUCTO", "CANTIDAD", "PRECIO", "LINE TOTAL", "PRECIO MIN.", "DIRECCION ",
                     "ZONA", "RANGO FC "]


def fila(fecha, cantidad=7.0, cliente="ACME SRL", zona="SDQ", vendedor="Ana Taveras", precio=8000.0):
    return [vendedor, "Movil II", "1104", cliente, "M200000001", fecha, "INGENIEROS", "30 DIAS", "44824",
            "HORMIGON 240", cantidad, precio, cantidad * precio if isinstance(cantidad, float) else None, 0.0,
            "OBRA: X", zona, "FC 240 KG/CM2 "]


def xls_del_mes(filas, extra_hoja=None):
    """Como el DESPACHOS SEPTIEMBRE 2026.xls: fechas como serie de Excel y,
    ademas de la hoja entera, una hoja con un pedazo (SDQ)."""
    libro = xlwt.Workbook()
    estilo_fecha = xlwt.easyxf(num_format_str="yyyy-mm-dd")
    for nombre, contenido in [("DESPACHOS", filas)] + ([("SDQ", extra_hoja)] if extra_hoja else []):
        h = libro.add_sheet(nombre)
        for j, t in enumerate(TITULOS_MES):
            h.write(0, j, t)
        for i, f in enumerate(contenido, start=1):
            for j, v in enumerate(f):
                if isinstance(v, datetime):
                    h.write(i, j, v, estilo_fecha)
                elif v is not None:
                    h.write(i, j, v)
    buf = io.BytesIO()
    libro.save(buf)
    return buf.getvalue()


def xlsx_acumulado(filas):
    libro = openpyxl.Workbook()
    libro.active.title = "DASHB COMERCIAL 2026"
    h = libro.create_sheet("ACUMULADO")
    h.append(TITULOS_ACUMULADO)
    for f in filas:
        h.append(f)
    buf = io.BytesIO()
    libro.save(buf)
    return buf.getvalue()


def xlsx_plan(valores=(23524, 34331, 41700), con_fila=True, precios=None):
    libro = openpyxl.Workbook()
    h = libro.active
    h.title = "Comercializacion Hormigon"
    h.append([None, None, None, None, "Estacionalidad", 0.8, 0.9, 1])
    h.append(["Concatenar", "Localidades", "Resistencias", "Datos", None,
              "Plan Enero 2026", "Plan Febrero 2026", "Plan Marzo 2026"])
    h.append([None, None, None, None, "DESPACHOS HORMIGON " if con_fila else "OTRA COSA", *valores])
    h.append([None, None, None, None, "Santo Domingo", 1, 2, 3])
    if precios is not None:
        h.append([None, None, None, None, "PRECIO DIRECTO, MES", *precios])
    buf = io.BytesIO()
    libro.save(buf)
    return buf.getvalue()


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "COM_DB_PATH", str(tmp_path / "comercial.db"))
    # El plan original de 2026 (#180) taparia el plan de prueba de Ene-Mar; el
    # test que lo prueba lo pone de nuevo.
    monkeypatch.setattr(core, "COM_PLAN_ORIGINAL", {})
    token = f"test-{uuid.uuid4().hex}"
    core.active_tokens[token] = datetime.now()
    yield TestClient(main.app), {"Authorization": f"Bearer {token}"}
    core.active_tokens.pop(token, None)


def subir(c, h, ruta, contenido, nombre, confirmar):
    return c.post(ruta, headers=h, files={"archivo": (nombre, contenido)},
                  data={"confirmar": "true" if confirmar else "false"})


# ── Leer ──

def test_lee_el_xls_del_mes_y_usa_la_hoja_entera_no_el_pedazo():
    filas = [fila(datetime(2026, 9, 1), 6.0), fila(datetime(2026, 9, 2), 6.5, zona="PUNTA CANA ")]
    leidas = core.com_leer_despachos(xls_del_mes(filas, extra_hoja=filas[:1]), "DESPACHOS SEPTIEMBRE 2026.xls")
    assert len(leidas) == 2, "la hoja SDQ es un pedazo de la misma y no se suma"
    assert leidas[0]["fecha"] == "2026-09-01" and leidas[0]["mes"] == "2026-09"
    assert leidas[0]["vendedor"] == "Ana Taveras", "COLUMN1 es el vendedor"
    assert leidas[1]["zona"] == "PUNTA CANA", "'PUNTA CANA ' con espacio es la misma zona"
    assert leidas[0]["rango_fc"] == "FC 240 KG/CM2"
    assert sum(f["cantidad"] for f in leidas) == 12.5


def test_lee_la_hoja_acumulado_de_varios_meses():
    filas = [fila(datetime(2026, 1, 2)), fila(datetime(2026, 2, 3)), fila(datetime(2026, 2, 4))]
    leidas = core.com_leer_despachos(xlsx_acumulado(filas), "DASHBOARD COMERCIAL 2026..xlsx")
    assert [f["mes"] for f in leidas] == ["2026-01", "2026-02", "2026-02"]


def test_un_excel_sin_las_columnas_se_rechaza_con_un_mensaje_legible():
    libro = openpyxl.Workbook()
    libro.active.append(["Cliente", "Cantidad"])
    buf = io.BytesIO()
    libro.save(buf)
    with pytest.raises(core.ComercialArchivoInvalido, match="17 columnas"):
        core.com_leer_despachos(buf.getvalue(), "x.xlsx")


def test_una_fila_con_cantidad_invalida_dice_cual_es():
    filas = [fila(datetime(2026, 9, 1)), fila(datetime(2026, 9, 1), cantidad="seis")]
    with pytest.raises(core.ComercialArchivoInvalido, match="fila 3"):
        core.com_leer_despachos(xlsx_acumulado(filas), "x.xlsx")


def test_montos_escritos_como_texto_se_leen_o_dan_error():
    """#175: LINE TOTAL o PRECIO como texto se guardaban vacios sin aviso y la
    fila sumaba RD$ 0. El texto con comas se lee; el que no es numero, error."""
    con_comas = fila(datetime(2026, 9, 1))
    con_comas[11], con_comas[12] = "RD$ 8,000.00", "56,000.00"
    leidas = core.com_leer_despachos(xlsx_acumulado([con_comas]), "x.xlsx")
    assert (leidas[0]["precio"], leidas[0]["line_total"]) == (8000.0, 56000.0)
    malo = fila(datetime(2026, 9, 1))
    malo[12] = "pendiente"
    with pytest.raises(core.ComercialArchivoInvalido, match=r"fila 2: line total no es un número"):
        core.com_leer_despachos(xlsx_acumulado([malo]), "x.xlsx")


def test_el_plan_sale_de_la_fila_despachos_hormigon():
    assert core.com_leer_plan(xlsx_plan(), "plan.xlsx") == {"2026-01": 23524, "2026-02": 34331, "2026-03": 41700}
    with pytest.raises(core.ComercialArchivoInvalido, match="DESPACHOS HORMIGON"):
        core.com_leer_plan(xlsx_plan(con_fila=False), "plan.xlsx")


def test_otro_formato_de_archivo_se_rechaza():
    with pytest.raises(core.ComercialArchivoInvalido, match=r"\.xls o \.xlsx"):
        core.com_leer_despachos(b"hola", "despachos.csv")


# ── Rutas ──

def test_todo_pide_sesion(cliente):
    c, _ = cliente
    assert c.get("/api/comercial/datos").status_code == 401
    assert c.get("/api/comercial/cargas").status_code == 401
    assert c.post("/api/comercial/despachos", files={"archivo": ("a.xlsx", b"x")}).status_code == 401
    assert c.post("/api/comercial/plan", files={"archivo": ("a.xlsx", b"x")}).status_code == 401


def test_sin_confirmar_no_guarda_y_confirmando_reemplaza_solo_los_meses_que_trae(cliente):
    c, h = cliente
    agosto_sep = xlsx_acumulado([fila(datetime(2026, 8, 5), 10.0), fila(datetime(2026, 9, 5), 4.0)])
    r = subir(c, h, "/api/comercial/despachos", agosto_sep, "acumulado.xlsx", False)
    assert r.status_code == 200 and r.json()["guardado"] is False
    assert c.get("/api/comercial/datos", headers=h).json()["filas"] == []

    assert subir(c, h, "/api/comercial/despachos", agosto_sep, "acumulado.xlsx", True).json()["guardado"]
    septiembre = xls_del_mes([fila(datetime(2026, 9, 1), 6.0), fila(datetime(2026, 9, 2), 6.0)])
    previa = subir(c, h, "/api/comercial/despachos", septiembre, "DESPACHOS SEPTIEMBRE 2026.xls", False).json()
    assert previa["meses"] == [{"mes": "2026-09", "filas": 2, "m3": 12.0, "rd": 96000.0,
                                "filas_actuales": 1, "m3_actuales": 4.0}]
    subir(c, h, "/api/comercial/despachos", septiembre, "DESPACHOS SEPTIEMBRE 2026.xls", True)

    datos = c.get("/api/comercial/datos?anio=2026", headers=h).json()
    por_mes = {}
    for f in datos["filas"]:
        por_mes[f[0]] = por_mes.get(f[0], 0) + f[7]
    assert por_mes == {8: 10.0, 9: 12.0}, "agosto queda; septiembre se reemplaza entero"
    assert [c_["tipo"] for c_ in c.get("/api/comercial/cargas", headers=h).json()["cargas"]] == ["despachos", "despachos"]


def test_los_datos_van_con_los_textos_en_una_lista_aparte(cliente):
    c, h = cliente
    filas = [fila(datetime(2026, 9, 1), cliente="ACME"), fila(datetime(2026, 9, 2), cliente="BETA"),
             fila(datetime(2026, 9, 3), cliente="ACME")]
    subir(c, h, "/api/comercial/despachos", xlsx_acumulado(filas), "a.xlsx", True)
    datos = c.get("/api/comercial/datos", headers=h).json()
    assert datos["anio"] == 2026 and datos["anios"] == [2026]
    clientes = datos["valores"]["cliente"]
    i = datos["dimensiones"].index("cliente") + 1
    assert [clientes[f[i]] for f in datos["filas"]] == ["ACME", "BETA", "ACME"]


def test_nombres_que_solo_cambian_en_mayusculas_son_uno_solo(cliente):
    """#179: la tabla dinamica del Excel no distingue mayusculas; "OFICINA" y
    "Oficina" tienen que ser una sola barra, con el nombre que aparece primero."""
    c, h = cliente
    filas = [fila(datetime(2026, 8, 1), vendedor="Oficina", zona="PUNTA CANA"),
             fila(datetime(2026, 9, 1), vendedor="OFICINA", zona="Punta Cana")]
    subir(c, h, "/api/comercial/despachos", xlsx_acumulado(filas), "a.xlsx", True)
    datos = c.get("/api/comercial/datos", headers=h).json()
    assert datos["valores"]["vendedor"] == ["Oficina"]
    assert datos["valores"]["zona"] == ["PUNTA CANA"]
    i = datos["dimensiones"].index("vendedor") + 1
    assert {f[i] for f in datos["filas"]} == {0}


def test_el_plan_se_guarda_y_uno_nuevo_reemplaza_los_meses_que_trae(cliente):
    c, h = cliente
    assert subir(c, h, "/api/comercial/plan", xlsx_plan(), "plan.xlsx", True).status_code == 200
    previa = subir(c, h, "/api/comercial/plan", xlsx_plan((1, 2, 3)), "plan2.xlsx", False).json()
    assert previa["meses"][0] == {"mes": "2026-01", "m3": 1, "m3_actual": 23524,
                                  "precio": None, "precio_actual": None}
    assert subir(c, h, "/api/comercial/plan", b"no", "plan.csv", False).status_code == 400
    subir(c, h, "/api/comercial/despachos", xlsx_acumulado([fila(datetime(2026, 1, 2))]), "a.xlsx", True)
    assert c.get("/api/comercial/datos", headers=h).json()["plan"] == {"1": 23524, "2": 34331, "3": 41700}


def test_un_archivo_invalido_da_400_con_el_motivo(cliente):
    c, h = cliente
    r = subir(c, h, "/api/comercial/despachos", xlsx_plan(), "plan.xlsx", False)
    assert r.status_code == 400 and "17 columnas" in r.json()["detail"]


def test_es_un_ambiente_separado():
    """Regla del usuario: cada modulo con su base. Comercial no abre las
    bases de Conduces, Estimaciones ni Logistica."""
    assert core.COM_DB_PATH not in (core.DB_PATH, core.EST_DB_PATH, core.LOG_DB_PATH)
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rutas = open(os.path.join(raiz, "routes_comercial.py"), encoding="utf-8").read()
    for otra in ("DB_PATH", "EST_DB_PATH", "LOG_DB_PATH", "_log_conn", "setup_est_db"):
        assert f"core.{otra}" not in rutas


# ── Precio vs ppto (2026-10-21) ──────────────────────────────────────────

def test_el_precio_del_plan_sale_de_la_fila_precio_directo_mes():
    precios = core.com_leer_precio_plan(xlsx_plan(precios=(8462.41, 8622.9, 0)), "plan.xlsx")
    assert precios == {"2026-01": 8462.41, "2026-02": 8622.9}, "un mes en 0 (IFERROR) queda sin precio"
    assert core.com_leer_precio_plan(xlsx_plan(), "plan.xlsx") == {}, "un plan sin la fila sube igual"


def test_el_precio_del_plan_se_guarda_y_llega_al_dashboard(cliente):
    c, h = cliente
    r = subir(c, h, "/api/comercial/plan", xlsx_plan(precios=(8462.41, 8622.9, 8586.51)), "plan.xlsx", True)
    assert r.status_code == 200
    assert r.json()["meses"][0]["precio"] == 8462.41
    subir(c, h, "/api/comercial/despachos", xlsx_acumulado([fila(datetime(2026, 1, 2))]), "a.xlsx", True)
    datos = c.get("/api/comercial/datos", headers=h).json()
    assert datos["planPrecio"] == {"1": 8462.41, "2": 8622.9, "3": 8586.51}


def test_un_plan_sin_precio_conserva_el_precio_guardado(cliente):
    """#174: subir un plan sin la fila PRECIO DIRECTO, MES dejaba el precio en
    NULL y precio y ventas vs ppto pasaban a "—" sin aviso."""
    c, h = cliente
    subir(c, h, "/api/comercial/plan", xlsx_plan(precios=(8462.41, 8622.9, 8586.51)), "plan.xlsx", True)
    previa = subir(c, h, "/api/comercial/plan", xlsx_plan((1, 2, 3)), "plan2.xlsx", False).json()
    assert previa["meses"][0]["precio"] is None and previa["meses"][0]["precio_actual"] == 8462.41
    subir(c, h, "/api/comercial/plan", xlsx_plan((1, 2, 3)), "plan2.xlsx", True)
    subir(c, h, "/api/comercial/despachos", xlsx_acumulado([fila(datetime(2026, 1, 2))]), "a.xlsx", True)
    datos = c.get("/api/comercial/datos", headers=h).json()
    assert datos["plan"] == {"1": 1, "2": 2, "3": 3}, "los m3 si se reemplazan"
    assert datos["planPrecio"] == {"1": 8462.41, "2": 8622.9, "3": 8586.51}
    subir(c, h, "/api/comercial/plan", xlsx_plan((1, 2, 3), precios=(9000, 0, 0)), "plan3.xlsx", True)
    assert c.get("/api/comercial/datos", headers=h).json()["planPrecio"]["1"] == 9000, "un precio nuevo si reemplaza"


def test_ene_jun_van_contra_el_plan_original_y_sin_precio(cliente, monkeypatch):
    """#180: como el Excel, un mes con plan original usa ese y no el rolling
    (que en esos meses trae lo real), y no tiene precio de plan."""
    c, h = cliente
    monkeypatch.setattr(core, "COM_PLAN_ORIGINAL", {"2026-01": 23270.5})
    subir(c, h, "/api/comercial/plan", xlsx_plan(precios=(8462.41, 8622.9, 8586.51)), "plan.xlsx", True)
    subir(c, h, "/api/comercial/despachos", xlsx_acumulado([fila(datetime(2026, 1, 2))]), "a.xlsx", True)
    datos = c.get("/api/comercial/datos", headers=h).json()
    assert datos["plan"] == {"1": 23270.5, "2": 34331, "3": 41700}
    assert datos["planPrecio"] == {"2": 8622.9, "3": 8586.51}


def test_el_plan_original_es_el_que_guarda_el_excel_del_dashboard():
    # Los seis valores de '[1]Comercializacion Hormigon'!F3:K3 (PLAN COMERCIAL 2026 ACT).
    assert sorted(core.COM_PLAN_ORIGINAL) == [f"2026-0{m}" for m in range(1, 7)]
    assert round(sum(core.COM_PLAN_ORIGINAL.values()), 2) == 160023.84


def test_una_base_de_antes_gana_la_columna_precio(tmp_path, monkeypatch):
    import sqlite3
    ruta = tmp_path / "vieja.db"
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE comercial_plan (mes TEXT PRIMARY KEY, m3 REAL NOT NULL)")
    con.execute("INSERT INTO comercial_plan VALUES ('2026-09', 27474.17)")
    con.commit()
    core.setup_comercial_db(con)
    assert con.execute("SELECT mes, m3, precio FROM comercial_plan").fetchall() == [("2026-09", 27474.17, None)]
    core.setup_comercial_db(con)   # idempotente
    con.close()
