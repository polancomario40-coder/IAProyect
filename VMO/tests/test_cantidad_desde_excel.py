"""
La cantidad del conduce tambien sale del Excel (2026-10-20).

Antes el cruce con el Excel solo corregia descripcion y cliente: la cantidad
entraba tal cual la leia Vision. Una firma encima del numero hizo leer 9 en
M800016570 (el papel dice 7,0) y 1 en M800016621 (dice 7), y 42 conduces de
MACAO 2 entraron con otra cantidad. Ahora la Cant. del Excel manda, como la
descripcion, y la diferencia queda en "Corregidos con el Excel".

Correr con: python -m pytest tests/test_cantidad_desde_excel.py -v
"""
import io
import os
import sqlite3
import sys

import openpyxl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402

NOMBRE = "09-30-M8-16570.pdf"
INFO = {"fecha": "2026-09-30", "planta": "M8", "id_documento": "M800016570"}
DESC = 'Hormigon 150 kg/cm2, Ag 3/4",T 35C, rev. 7" +/- 1"'
CLIENTE = "MACAO ALTO RESORT SRL  (CIUDAD PALACE - CAVERNAS Y EXT)"


def _excel(filas):
    libro = openpyxl.Workbook()
    h = libro.active
    h.append(["Conduce", "Fecha", "Cliente", "Producto", "Cant.", "Planta", "Codigo"])
    for f in filas:
        h.append(f)
    buf = io.BytesIO()
    libro.save(buf)
    return buf.getvalue()


def _fila(cant, conduce="M800016570", codigo=NOMBRE):
    return [conduce, "2026-09-30", CLIENTE, DESC, cant, "M8 Macao", codigo]


def _enriquecer(cantidad_vision, lookup):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE precios_vmo (descripcion TEXT, fase TEXT, precio_unitario REAL)")
    conn.execute("CREATE TABLE precios_domicem (descripcion TEXT, fase TEXT, precio_unitario REAL)")
    conn.execute("INSERT INTO precios_domicem VALUES (?, 'CAVERNAS', 111.0)", (DESC,))
    datos = {"cliente": "x", "obra": "LIDOMI", "descripcion": DESC, "cantidad": cantidad_vision}
    resultado = core._enriquecer_y_matchear(conn, datos, INFO, NOMBRE, lookup)
    conn.close()
    return resultado


def test_el_lookup_trae_la_cantidad():
    lookup = core.cargar_lookup_excel(_excel([_fila(7)]))
    assert lookup["por_archivo"][core._excel_norm_archivo(NOMBRE)]["cantidad"] == 7.0


def test_la_cantidad_del_excel_corrige_la_de_vision_y_el_total():
    r = _enriquecer(9.0, core.cargar_lookup_excel(_excel([_fila(7)])))
    assert r["cantidad"] == 7.0
    assert r["total"] == 777.0, "el total se calcula con la cantidad corregida"
    assert r["_correccion_excel_cantidad"] == {"campo": "cantidad", "vision": 9.0, "excel": 7.0}


def test_vision_sin_cantidad_tambien_se_completa():
    r = _enriquecer(None, core.cargar_lookup_excel(_excel([_fila(5)])))
    assert r["cantidad"] == 5.0
    assert r["_correccion_excel_cantidad"]["vision"] is None


def test_si_coinciden_no_se_marca_correccion():
    r = _enriquecer(7.0, core.cargar_lookup_excel(_excel([_fila(7)])))
    assert r["cantidad"] == 7.0
    assert "_correccion_excel_cantidad" not in r


def test_sin_cant_en_el_excel_queda_lo_de_vision():
    r = _enriquecer(9.0, core.cargar_lookup_excel(_excel([_fila(None)])))
    assert r["cantidad"] == 9.0
    assert "_correccion_excel_cantidad" not in r


def test_dos_filas_del_mismo_conduce_con_distinta_cantidad_son_conflicto():
    lookup = core.cargar_lookup_excel(_excel([_fila(7), _fila(9)]))
    assert core._excel_norm_id("M800016570") in lookup["conflictos"]
    r = _enriquecer(9.0, lookup)
    assert r["_sin_fila_excel"] is True, "no se adivina cual cantidad es la buena"
