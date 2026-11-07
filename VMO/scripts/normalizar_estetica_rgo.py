# by a_oller
"""
normalizar_estetica_rgo.py — arregla 2 defectos SOLO ESTETICOS de la hoja
CD-COAF-RGO-PLANTILLA en las 9 plantillas de estimacion.

Los 2 defectos (reportados por el usuario 2026-08-26 con un screenshot de una
estimacion real de MACAO 2, y confirmados identicos en las 9 plantillas):

1. Columna B (FOLIO REMISION) con la alineacion mezclada: 3 filas 'center',
   3 filas 'left' y 34 sin alineacion explicita. En el documento se ve como
   si los primeros folios estuvieran indentados y el resto no. El documento
   real del jefe usa 'center' en TODAS las filas de dato (verificado contra
   EST_DOMICEM_MACAO_II_..._N34_...xlsx, hoja CD-COAF-RGO-02), asi que se
   normaliza a 'center'.

2. Columna "NO. ECONOMICO DEL TRANSPORTE" (D:F) combinada solo en 21 de las 40
   filas de dato (faltan 38-47 y 49-56). Donde no esta combinada se ven las
   divisiones internas D|E|F como una linea vertical partiendo la columna
   vacia. Se combinan todas. La convencion del propio codigo ya es "combinada":
   _est_redimensionar_rgo() (core.py) hace merge_cells(f"D{r}:F{r}") en cada
   fila que crea mas alla de la capacidad nativa.

NO TOCA NADA MAS. Verificado antes de escribir este script que las celdas
B/D/E/F de las filas 18-57 estan TODAS vacias en las 9 plantillas (sin valores
ni formulas), asi que combinarlas y alinearlas no puede perder contenido. Las
formulas (columna G, fila de TOTAL, referencias cruzadas a REO-01) no se tocan
en absoluto.

Idempotente: correrlo 2 veces deja el mismo resultado.

Uso:
    python scripts/normalizar_estetica_rgo.py --check   # solo reporta, no escribe
    python scripts/normalizar_estetica_rgo.py
"""

import argparse
import glob
import os
import sys

import openpyxl
from openpyxl.styles import Alignment

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(BASE_DIR, "estimaciones", "data")
# Las 9 por fase MAS la generica sin sufijo. La generica es la FUENTE de la hoja
# RGO: scripts/limpiar_plantilla_estimacion.py la copia tal cual al reconstruir
# cualquier plantilla (PLANTILLA_RGO_ORIGEN). Si no se normaliza tambien, el
# defecto vuelve en cuanto alguien regenere una plantilla.
PLANTILLAS_GLOB = os.path.join(_DATA_DIR, "plantilla_estimacion_*.xlsx")
PLANTILLA_GENERICA = os.path.join(_DATA_DIR, "plantilla_estimacion.xlsx")

HOJA_RGO = "CD-COAF-RGO-PLANTILLA"
# mismas constantes que core.py (EST_RGO_FIRST_ROW / EST_RGO_LAST_ROW)
PRIMERA_FILA = 18
ULTIMA_FILA = 57
COL_FOLIO = 2  # B


def _celdas_con_contenido(ws):
    """Guardia de seguridad: si alguna celda que vamos a tocar tiene algo,
    abortamos. Nunca combinar sobre contenido — perderia todo menos la
    esquina superior izquierda."""
    sucias = []
    for r in range(PRIMERA_FILA, ULTIMA_FILA + 1):
        for col in ("B", "D", "E", "F"):
            if ws[f"{col}{r}"].value not in (None, ""):
                sucias.append(f"{col}{r}")
    return sucias


def normalizar(path, escribir=True):
    """Devuelve (merges_agregados, alineaciones_corregidas)."""
    wb = openpyxl.load_workbook(path)
    if HOJA_RGO not in wb.sheetnames:
        return None
    ws = wb[HOJA_RGO]

    sucias = _celdas_con_contenido(ws)
    if sucias:
        print(f"ERROR {os.path.basename(path)}: celdas con contenido en el rango a "
              f"normalizar ({sucias[:5]}...) — no se toco nada.", file=sys.stderr)
        sys.exit(1)

    merges = {str(m) for m in ws.merged_cells.ranges}
    agregados = 0
    for r in range(PRIMERA_FILA, ULTIMA_FILA + 1):
        if f"D{r}:F{r}" not in merges:
            ws.merge_cells(f"D{r}:F{r}")
            agregados += 1

    corregidas = 0
    for r in range(PRIMERA_FILA, ULTIMA_FILA + 1):
        celda = ws.cell(row=r, column=COL_FOLIO)
        if (celda.alignment.horizontal or None) != "center":
            # copy() preserva vertical/wrap/indent y solo cambia horizontal
            celda.alignment = openpyxl.styles.Alignment(
                horizontal="center",
                vertical=celda.alignment.vertical,
                wrap_text=celda.alignment.wrap_text,
                shrink_to_fit=celda.alignment.shrink_to_fit,
                indent=celda.alignment.indent,
            )
            corregidas += 1

    if escribir and (agregados or corregidas):
        wb.save(path)
    return agregados, corregidas


def main():
    parser = argparse.ArgumentParser(
        description="Normaliza la estetica de la hoja RGO en las 9 plantillas (merges D:F + alineacion de folios)"
    )
    parser.add_argument("--check", action="store_true", help="Solo reporta, no escribe")
    args = parser.parse_args()

    plantillas = sorted(glob.glob(PLANTILLAS_GLOB))
    if not plantillas:
        print(f"ERROR: no se encontro ninguna plantilla en {PLANTILLAS_GLOB}", file=sys.stderr)
        sys.exit(1)
    if os.path.exists(PLANTILLA_GENERICA):
        plantillas.append(PLANTILLA_GENERICA)  # la fuente de la hoja RGO, ver arriba

    total_m = total_a = 0
    for path in plantillas:
        r = normalizar(path, escribir=not args.check)
        if r is None:
            print(f"{os.path.basename(path):<52} (sin hoja {HOJA_RGO}, se salta)")
            continue
        merges, alin = r
        total_m += merges
        total_a += alin
        estado = "ya estaba OK" if not (merges or alin) else f"merges +{merges}, alineaciones {alin}"
        print(f"{os.path.basename(path):<52} {estado}")

    verbo = "faltarian" if args.check else "aplicados"
    print(f"RESUMEN: {total_m} merges {verbo}, {total_a} alineaciones {verbo} "
          f"en {len(plantillas)} plantillas")


if __name__ == "__main__":
    main()
