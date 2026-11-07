"""
Primera suite de pruebas del proyecto. Cubre solo el generador de
Estimaciones: verifica que las 9 plantillas (una por fase) tengan la
estructura correcta y que la cantidad de productos de catalogo_estimacion
no exceda la capacidad de su plantilla (la misma verificacion que hace
main.py al generar, pero corrida contra las 9 fases de una sola vez).

No prueba el calculo de Excel en si (requiere LibreOffice, no instalado en
esta maquina) — solo estructura: hojas presentes, formulas de cada fila de
producto, fila de TOTALES, y ausencia de #REF!.

Correr con: python -m pytest tests/ -v
"""
import os
import sqlite3
import sys

import openpyxl
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import EST_PLANTILLAS, EST_DATA_DIR, EST_DB_PATH, EST_REO_FIRST_ROW  # noqa: E402

FORMULAS = {
    "F": "=D{r}*E{r}",
    "I": "=+E{r}*H{r}",
    "L": "=E{r}*K{r}",
    "N": "=H{r}+K{r}",
    "O": "=E{r}*N{r}",
    "Q": "=D{r}-N{r}",
    "R": "=E{r}*Q{r}",
    "T": "=IFERROR(N{r}/D{r},0)",
}


# estimaciones.db esta en .gitignore, asi que un checkout que no la tenga —CI,
# un clone limpio, un worktree— no puede correr la guardia de capacidad: sin
# catalogo no hay contra que comparar. Se saltea diciendo por que, mismo
# criterio que `requiere_documentos_cliente` en tests/test_rco_rfo.py. Sin
# esto la suite falla en CI con un `unable to open database file` que parece
# un bug del codigo y no lo es.
requiere_base_estimaciones = pytest.mark.skipif(
    not os.path.exists(EST_DB_PATH),
    reason="estimaciones.db no esta en este checkout (esta en .gitignore)",
)


def catalogo_counts():
    conn = sqlite3.connect(EST_DB_PATH)
    rows = conn.execute(
        "SELECT empresa, fase, COUNT(*) FROM catalogo_estimacion GROUP BY empresa, fase"
    ).fetchall()
    conn.close()
    return {(empresa, fase): n for empresa, fase, n in rows}


FASES = sorted(EST_PLANTILLAS.keys())


@pytest.mark.parametrize("empresa,fase", FASES)
def test_plantilla_existe(empresa, fase):
    info = EST_PLANTILLAS[(empresa, fase)]
    ruta = os.path.join(EST_DATA_DIR, info["archivo"])
    assert os.path.exists(ruta), f"falta {info['archivo']} para {empresa}/{fase}"


@pytest.mark.parametrize("empresa,fase", FASES)
def test_plantilla_tiene_las_5_hojas(empresa, fase):
    # issue #27: a las 3 hojas historicas se suman CD-COAF-RCO-PLANTILLA y
    # CD-COAF-RFO-PLANTILLA (croquis de ubicacion y reporte fotografico)
    info = EST_PLANTILLAS[(empresa, fase)]
    wb = openpyxl.load_workbook(os.path.join(EST_DATA_DIR, info["archivo"]), data_only=False)
    assert set(wb.sheetnames) == {
        "CD-COAF-CEO-01", "CD-COAF-REO-01", "CD-COAF-RGO-PLANTILLA",
        "CD-COAF-RCO-PLANTILLA", "CD-COAF-RFO-PLANTILLA",
    }


@pytest.mark.parametrize("empresa,fase", FASES)
def test_bloque_de_productos_correcto(empresa, fase):
    info = EST_PLANTILLAS[(empresa, fase)]
    capacidad = info["capacidad"]
    wb = openpyxl.load_workbook(os.path.join(EST_DATA_DIR, info["archivo"]), data_only=False)
    ws = wb["CD-COAF-REO-01"]

    first = EST_REO_FIRST_ROW
    last = first + capacidad - 1
    for r in range(first, last + 1):
        for col in ("A", "B", "C", "D", "E", "H", "K"):
            assert ws[f"{col}{r}"].value is None, f"{empresa}/{fase} {col}{r} deberia estar vacio"
        for col, tmpl in FORMULAS.items():
            esperado = tmpl.format(r=r)
            assert ws[f"{col}{r}"].value == esperado, (
                f"{empresa}/{fase} {col}{r}: {ws[f'{col}{r}'].value!r} != {esperado!r}"
            )


@pytest.mark.parametrize("empresa,fase", FASES)
def test_totales_row(empresa, fase):
    info = EST_PLANTILLAS[(empresa, fase)]
    capacidad = info["capacidad"]
    wb = openpyxl.load_workbook(os.path.join(EST_DATA_DIR, info["archivo"]), data_only=False)
    ws = wb["CD-COAF-REO-01"]

    first = EST_REO_FIRST_ROW
    last = first + capacidad - 1
    # Un renglon extra ocupa la fila en blanco de antes de TOTALES (ver
    # EST_PLANTILLAS): TOTALES no se mueve, queda pegado al bloque.
    totales_row = last + 2 - info.get("renglones_extra", 0)
    assert ws.cell(totales_row, 1).value == "TOTALES:"
    for col in ("F", "I", "L", "O", "R"):
        assert ws[f"{col}{totales_row}"].value == f"=SUM({col}{first}:{col}{last})"
    assert ws[f"T{totales_row}"].value == f"=AVERAGE(T{first}:T{last})"


@pytest.mark.parametrize("empresa,fase", FASES)
def test_rgo_plantilla_generica(empresa, fase):
    info = EST_PLANTILLAS[(empresa, fase)]
    wb = openpyxl.load_workbook(os.path.join(EST_DATA_DIR, info["archivo"]), data_only=False)
    ws = wb["CD-COAF-RGO-PLANTILLA"]
    assert ws["A58"].value == "TOTAL:"
    assert ws["G58"].value == "=SUM(G18:G57)"
    assert len(ws.merged_cells.ranges) >= 15


@pytest.mark.parametrize("empresa,fase", FASES)
def test_sin_ref_errors(empresa, fase):
    info = EST_PLANTILLAS[(empresa, fase)]
    wb = openpyxl.load_workbook(os.path.join(EST_DATA_DIR, info["archivo"]), data_only=False)
    for sheet in wb.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str):
                    assert "#REF" not in cell.value, f"{empresa}/{fase} {sheet.title}!{cell.coordinate}"


@requiere_base_estimaciones
def test_catalogo_no_excede_capacidad_de_ninguna_plantilla():
    """Guardia de sincronizacion (T4): si alguien agrega productos a
    catalogo_estimacion sin reconstruir la plantilla de esa fase, esta
    prueba lo detecta antes de que llegue a produccion."""
    counts = catalogo_counts()
    fallas = []
    for (empresa, fase), n in counts.items():
        info = EST_PLANTILLAS.get((empresa, fase))
        if not info:
            fallas.append(f"{empresa}/{fase}: catalogo_estimacion tiene {n} productos pero no hay plantilla registrada")
            continue
        if n > info["capacidad"]:
            fallas.append(
                f"{empresa}/{fase}: catalogo tiene {n} productos, plantilla {info['archivo']} solo soporta {info['capacidad']}"
            )
    assert not fallas, "\n".join(fallas)
