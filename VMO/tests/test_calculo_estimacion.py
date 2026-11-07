"""
Verifica el CALCULO real (no solo el texto de la formula) de las 9
plantillas de Estimacion, usando LibreOffice en modo headless para forzar
el recalculo — openpyxl nunca evalua formulas por si solo.

Rellena 2 filas de producto (la primera y la ultima del bloque) con datos
sinteticos conocidos, fuerza el recalculo con LibreOffice, y compara los
valores calculados contra el resultado esperado a mano. Cubre exactamente
lo que T1 reescribio por fase (las 8 columnas de formula + TOTALES) —
la referencia cruzada a la hoja RGO (columna K) ya se verifico end-to-end
contra datos reales el 2026-08-20 (ver CLAUDE.md), no se repite aqui.

Se salta automaticamente si LibreOffice no esta instalado en la maquina.
Correr con: python -m pytest tests/test_calculo_estimacion.py -v
"""
import os
import subprocess
import sys
import tempfile

import openpyxl
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import EST_PLANTILLAS, EST_DATA_DIR, EST_REO_FIRST_ROW, EST_SOFFICE  # noqa: E402

# _encontrar_soffice() se movio a core.py (issue #6) para reutilizarlo en la
# conversion a PDF del generador de Estimaciones — este archivo ya no lo
# duplica, usa la constante EST_SOFFICE calculada una sola vez ahi.
SOFFICE = EST_SOFFICE
requiere_libreoffice = pytest.mark.skipif(
    SOFFICE is None, reason="LibreOffice no esta instalado — se salta la verificacion de calculo real"
)

FASES = sorted(EST_PLANTILLAS.keys())


def _recalcular_con_libreoffice(ruta_xlsx, outdir):
    resultado = subprocess.run(
        [SOFFICE, "--headless", "--calc", "--convert-to", "xlsx", "--outdir", outdir, ruta_xlsx],
        capture_output=True, text=True, timeout=60,
    )
    assert resultado.returncode == 0, f"LibreOffice fallo: {resultado.stderr}"
    nombre = os.path.basename(ruta_xlsx)
    ruta_out = os.path.join(outdir, nombre)
    assert os.path.exists(ruta_out), f"LibreOffice no genero {ruta_out}"
    return ruta_out


@requiere_libreoffice
@pytest.mark.parametrize("empresa,fase", FASES)
def test_calculo_real_de_la_plantilla(empresa, fase, tmp_path):
    info = EST_PLANTILLAS[(empresa, fase)]
    capacidad = info["capacidad"]
    origen = os.path.join(EST_DATA_DIR, info["archivo"])

    wb = openpyxl.load_workbook(origen, data_only=False)
    ws = wb["CD-COAF-REO-01"]

    first = EST_REO_FIRST_ROW
    last = first + capacidad - 1

    # fila 1: cantidad_proyecto=100, precio=50, acum_anterior=20 (sin entregas este periodo -> K vacio)
    ws[f"D{first}"] = 100
    ws[f"E{first}"] = 50
    ws[f"H{first}"] = 20

    # ultima fila del bloque: cantidad_proyecto=200, precio=75, acum_anterior=30
    if last != first:
        ws[f"D{last}"] = 200
        ws[f"E{last}"] = 75
        ws[f"H{last}"] = 30

    entrada_dir = tmp_path / "entrada"
    salida_dir = tmp_path / "salida"
    entrada_dir.mkdir()
    salida_dir.mkdir()

    ruta_tmp = str(entrada_dir / info["archivo"])
    wb.save(ruta_tmp)

    # LibreOffice no puede convertir "in place" (mismo dir de entrada y
    # salida) — falla con "Please verify input parameters" al intentar
    # sobrescribir el archivo que todavia tiene abierto como fuente
    ruta_calculada = _recalcular_con_libreoffice(ruta_tmp, str(salida_dir))
    wb2 = openpyxl.load_workbook(ruta_calculada, data_only=True)
    ws2 = wb2["CD-COAF-REO-01"]

    # fila 1: F=D*E, I=E*H, N=H+K(vacio->0), O=E*N, Q=D-N, R=E*Q, T=N/D
    assert ws2[f"F{first}"].value == pytest.approx(5000)
    assert ws2[f"I{first}"].value == pytest.approx(1000)
    assert ws2[f"N{first}"].value == pytest.approx(20)
    assert ws2[f"O{first}"].value == pytest.approx(1000)
    assert ws2[f"Q{first}"].value == pytest.approx(80)
    assert ws2[f"R{first}"].value == pytest.approx(4000)
    assert ws2[f"T{first}"].value == pytest.approx(0.2)

    f_total_esperado = 5000
    i_total_esperado = 1000
    o_total_esperado = 1000
    r_total_esperado = 4000

    if last != first:
        assert ws2[f"F{last}"].value == pytest.approx(15000)
        assert ws2[f"I{last}"].value == pytest.approx(2250)
        assert ws2[f"N{last}"].value == pytest.approx(30)
        assert ws2[f"O{last}"].value == pytest.approx(2250)
        assert ws2[f"Q{last}"].value == pytest.approx(170)
        assert ws2[f"R{last}"].value == pytest.approx(12750)
        f_total_esperado += 15000
        i_total_esperado += 2250
        o_total_esperado += 2250
        r_total_esperado += 12750

    # un renglon extra ocupa la fila en blanco de antes de TOTALES
    totales_row = last + 2 - EST_PLANTILLAS[(empresa, fase)].get("renglones_extra", 0)
    assert ws2.cell(totales_row, 1).value == "TOTALES:"
    assert ws2[f"F{totales_row}"].value == pytest.approx(f_total_esperado)
    assert ws2[f"I{totales_row}"].value == pytest.approx(i_total_esperado)
    assert ws2[f"O{totales_row}"].value == pytest.approx(o_total_esperado)
    assert ws2[f"R{totales_row}"].value == pytest.approx(r_total_esperado)
