"""
Construye una plantilla_estimacion_{empresa}_{fase}.xlsx limpia a partir del
Excel real de esa fase (estimaciones/data/plantillas_por_fase/{empresa}/*.xlsx).

Deja solo CD-COAF-CEO-01 y CD-COAF-REO-01 del archivo real (que ya trae la
posicion correcta de la fila 17 en adelante y del pie de pagina para esa
fase especifica), copia CD-COAF-RGO-PLANTILLA (generica, sin cambios) desde
la plantilla ya validada de CEDIS, y limpia el bloque de productos:

- Borra A,B,C,D,E,H,K de cada fila de producto (se llenan al generar)
- Reescribe explicitamente las formulas de F,I,L,N,O,Q,R,T en cada fila de
  producto — nunca se confia en lo que traiga el archivo real, porque se
  encontro al menos 1 de 9 archivos (CAVERNAS) con esa columna pegada como
  numero literal en vez de formula viva (revisado con Codex antes de tocar
  los 9 documentos oficiales, ver docs/designs/generador-estimaciones-plantillas.md)
- Reescribe la fila de TOTALES (SUM/AVERAGE) para el rango exacto del bloque
- Nunca borra ni inserta filas — la "capacidad" de la plantilla es la
  cantidad de filas de producto que el archivo real ya trae de forma
  natural. Si el catalogo tiene menos productos que esa capacidad (unico
  caso real: MACAO 2, catalogo=8 pero el documento real trae 9 filas por la
  fusion de "CIMENTACION TORRES"/"TORRE GRUA"), la fila sobrante queda en
  blanco — no aporta a las formulas y no requiere mover el pie de pagina.

Issue #27 — ademas construye CD-COAF-RCO-PLANTILLA y CD-COAF-RFO-PLANTILLA
(croquis de ubicacion y reporte fotografico), copiando la ESTRUCTURA (estilos,
merges, anchos/altos, margenes) de una hoja real bien formada y reescribiendo
TODO el contenido de forma explicita — misma filosofia que las formulas de
REO-01: nunca se confia en lo que traiga el archivo real. Las firmas se
resuelven contra la fila REAL del bloque de firma del REO de esa fase
(localizada con el ancla CONTRATISTA del issue #33), nunca con formula fija a
E37 — la fila 37/38 solo es correcta en 2 de las 9 fases.

Sobre las imagenes (hallazgo D1 del spec): wb.copy_worksheet() pierde las
imagenes EN SILENCIO al generar, asi que la PLANTILLA debe nacer sin ninguna.
El spec pedia "fallar si la hoja fuente trae imagenes", pero eso es
incumplible tal cual: las hojas fuente verificadas (CEDIS N09 RCO-01/RFO-01)
SI traen una imagen — el croquis/las fotos de contenido, que justamente NO son
plantilla. La copia de aca es celda por celda y no puede arrastrar imagenes
por construccion; ademas _afirmar_hoja_sin_imagenes() lo verifica ruidosamente
sobre la hoja construida, y core._est_afirmar_plantilla_sin_imagenes() vuelve
a verificarlo al generar, que es donde la perdida silenciosa haria dano.

Uso:
    python scripts/limpiar_plantilla_estimacion.py --list
    python scripts/limpiar_plantilla_estimacion.py --fase "DOMICEM/CAVERNAS"
    python scripts/limpiar_plantilla_estimacion.py --todas
    python scripts/limpiar_plantilla_estimacion.py --todas --solo-rco-rfo

--solo-rco-rfo agrega (o reemplaza) las hojas RCO/RFO-PLANTILLA sobre el
archivo de plantilla YA EXISTENTE, sin reconstruir CEO/REO/RGO: las 9
plantillas committeadas llevan un post-proceso estetico posterior
(scripts/normalizar_estetica_rgo.py) que una reconstruccion completa no
reproduce, asi que para extenderlas se tocan solo las hojas nuevas.

La plantilla GENERICA (plantilla_estimacion.xlsx) NO lleva RCO/RFO-PLANTILLA
— decision explicita del issue #27 (la seccion 10 del spec lo dejaba como
pregunta abierta): el generador nunca la abre (EST_PLANTILLAS solo registra
las 9 por fase; la generica es la fuente de la RGO generica de aca arriba y
fixture de tests), y las hojas RCO/RFO son por-fase por construccion — sus
firmas anclan a la fila real del REO de cada fase y su geometria depende de
la fase. Una version "generica" hornearia las filas de firma del REO que esa
plantilla traiga, exactamente la clase de bug del #33. Lo custodia
tests/test_rco_rfo.py::test_la_plantilla_generica_no_lleva_rco_rfo.
"""
import argparse
import os
import shutil
import sys
from copy import copy

import openpyxl
from openpyxl.cell.cell import MergedCell

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from core import (  # noqa: E402
    EST_RCO_PLANTILLA, EST_RFO_PLANTILLA, EST_RCO_TITULO_A5, EST_RFO_TITULO_A5,
    EST_RCO_ROTULO_A17, EST_RFO_ROTULO_A17, EST_RCO_RFO_FILAS_PIE,
    EST_PLANTILLAS, _est_filas_firma_reo, _est_geometria_rco_rfo,
)

# Los 15 documentos reales del cliente pesan 768 MB y no se versionan, asi
# que en un worktree/checkout secundario no estan: EST_FUENTES_DIR permite
# apuntar a la carpeta del checkout principal (solo lectura) sin copiarla.
FUENTES_DIR = os.environ.get("EST_FUENTES_DIR") or os.path.join(
    BASE_DIR, "estimaciones", "data", "plantillas_por_fase")
DEST_DIR = os.path.join(BASE_DIR, "estimaciones", "data")
PLANTILLA_RGO_ORIGEN = os.path.join(DEST_DIR, "plantilla_estimacion.xlsx")

# ── Issue #27 — fuentes de estructura de las hojas RCO/RFO ────────────────
#
# RCO-01/RFO-01 de VMO CEDIS N09: candidatas verificadas por el spec (claves
# por formula, sin #REF!, sin logos-imagen, titulo A5 correcto en ambas).
# La RFO de MACAO 2 es la excepcion de geometria (52 filas, decision 4) y su
# estructura no puede salir de una hoja de 46 — se toma de una hoja real de
# MACAO 2 (sus 20 RFO son perfectamente uniformes; la N33 RFO-02 tiene el
# titulo A5 correcto).
FUENTE_RCO = ("VMO/EST_VMO_CEDIS_4800036588_N09_22072026_V01.xlsx", "CD-COAF-RCO-01")
FUENTE_RFO = ("VMO/EST_VMO_CEDIS_4800036588_N09_22072026_V01.xlsx", "CD-COAF-RFO-01")
FUENTE_RFO_MACAO2 = ("DOMICEM/EST_DOMICEM_MACAO_II_4800029677_N33_22072026_V01.xlsx", "CD-COAF-RFO-02")

# Merges que definen el cuerpo de cada familia (medidos sobre los documentos
# reales): la RCO lleva un marco unico para el croquis; la RFO, 4 cuadrantes
# para las fotos. Se afirman sobre la hoja construida — si la fuente cambia
# de estructura, esto corta ruidosamente en vez de committear una plantilla
# deforme.
MERGES_CUERPO = {
    ("RCO", 46): ("A18:J43",),
    ("RFO", 46): ("A18:E30", "F18:J30", "A31:E43", "F31:J43"),
    ("RFO", 52): ("A18:E36", "F18:J36", "A37:E49", "F37:J49"),
}

# Pie de pagina de las hojas RCO/RFO — el cliente cablea el nombre de la hoja
# en el texto (y se le desactualiza: la RFO-02 de MACAO 2 N33 dice
# "CD-COAF-RFO-01"); &A pone el nombre real de cada hoja y no se desincroniza
FOOTER_RCO_RFO = "&A\nPág. &P de &N"

FIRST_ROW = 17
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
CLEAR_COLS = ["A", "B", "C", "D", "E", "H", "K"]

# (empresa, fase) -> archivo fuente relativo a FUENTES_DIR
FASES = {
    ("DOMICEM", "CAVERNAS"): "DOMICEM/EST_DOMICEM_CIUDAD_PALACE_CAVERNAS_EXTERIORES_4800029676_N42_22072026_V01.xlsx",
    ("DOMICEM", "VIVIENDAS"): "DOMICEM/EST_DOMICEM_CIUDAD_PALACE_VIVIENDAS_PPACT_N04_22072026_V01.xlsx",
    ("DOMICEM", "MACAO 2"): "DOMICEM/EST_DOMICEM_MACAO_II_4800029677_N33_22072026_V01.xlsx",
    ("DOMICEM", "PATIO DE MANIOBRAS-TRB"): "DOMICEM/EST_DOMICEM_PATIO DE MANIOBRAS_TRB_4800032854_N17_22072026_V01.xlsx",
    ("VMO", "CANCHAS"): "VMO/EST_VMO_CANCHAS_4800037426_N04_22072026_V1 Rv.xlsx",
    ("VMO", "CEDIS"): "VMO/EST_VMO_CEDIS_4800036588_N09_22072026_V01.xlsx",
    ("VMO", "PATIO DE MANIOBRAS-TRA"): "VMO/EST_VMO_PATIO DE MANIOBRAS_TRA_4800025583_N09_22072026.xlsx",
    ("VMO", "PODIUM-1-2-3"): "VMO/EST_VMO_PODIUM 1,2,3_PPACT_N04_22072026_V1.xlsx",
    ("VMO", "EXTERIORES"): "VMO/EST_VMO_PPACT_AREA_EXTERIORES_N17_22072026_V01.xlsx",
}


def _slug(empresa: str, fase: str) -> str:
    s = f"{empresa}_{fase}".upper()
    out = []
    for ch in s:
        out.append(ch if ch.isalnum() else "_")
    slug = "".join(out)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")


def _detectar_capacidad(ws) -> int:
    """Cuenta filas de producto consecutivas desde FIRST_ROW mientras A o B
    tengan contenido."""
    r = FIRST_ROW
    while ws.cell(r, 1).value is not None or ws.cell(r, 2).value is not None:
        r += 1
    return r - FIRST_ROW


def _copiar_celdas_y_dimensiones(ws_src, ws_dst) -> None:
    """Copia valores, estilos, merges y dimensiones entre workbooks distintos.
    _style no es transferible entre workbooks (indices a su propia tabla de
    estilos) — hay que copiar los objetos de estilo en si, no el indice
    interno. Las imagenes NO se copian por construccion: esta funcion solo ve
    celdas, y es a proposito (ver docstring del modulo)."""
    for row in ws_src.iter_rows():
        for cell in row:
            dst = ws_dst.cell(cell.row, cell.column, value=cell.value)
            if cell.has_style:
                dst.font = copy(cell.font)
                dst.border = copy(cell.border)
                dst.fill = copy(cell.fill)
                dst.number_format = cell.number_format
                dst.protection = copy(cell.protection)
                dst.alignment = copy(cell.alignment)
    for merged in ws_src.merged_cells.ranges:
        ws_dst.merge_cells(str(merged))
    for col_letter, dim in ws_src.column_dimensions.items():
        ws_dst.column_dimensions[col_letter].width = dim.width
    for idx, dim in ws_src.row_dimensions.items():
        ws_dst.row_dimensions[idx].height = dim.height


def _afirmar_hoja_sin_imagenes(ws, contexto: str) -> None:
    """La PLANTILLA debe nacer SIN imagenes (hallazgo D1: copy_worksheet las
    pierde en silencio al generar, asi que una plantilla con logos produciria
    hojas sin logos sin que nada avise). Falla ruidoso si una construccion
    futura las arrastrara por accidente."""
    if ws._images:
        raise ValueError(
            f"{contexto}: la hoja construida trae {len(ws._images)} imagen(es) "
            f"y la PLANTILLA debe nacer sin ninguna — wb.copy_worksheet() las "
            f"perderia en silencio al generar (openpyxl 3.1.5, verificado)"
        )


_CACHE_FUENTES: dict = {}


def _hoja_fuente(archivo_rel: str, hoja: str):
    ruta = os.path.join(FUENTES_DIR, archivo_rel)
    if ruta not in _CACHE_FUENTES:
        if not os.path.exists(ruta):
            raise FileNotFoundError(
                f"falta el documento fuente {ruta} — las hojas RCO/RFO-PLANTILLA "
                f"se construyen desde los documentos reales del cliente"
            )
        _CACHE_FUENTES[ruta] = openpyxl.load_workbook(ruta, data_only=False)
    wb = _CACHE_FUENTES[ruta]
    if hoja not in wb.sheetnames:
        raise ValueError(f"{archivo_rel}: no trae la hoja {hoja}")
    return wb[hoja]


def construir_hoja_rco_rfo(wb_dst, empresa: str, fase: str, familia: str) -> None:
    """Construye CD-COAF-{RCO|RFO}-PLANTILLA en wb_dst (que ya debe traer
    CD-COAF-REO-01): estructura copiada de la hoja real fuente, contenido
    reescrito explicitamente celda por celda."""
    assert familia in ("RCO", "RFO")
    if familia == "RCO":
        archivo_rel, hoja_src = FUENTE_RCO
        titulo_a5, rotulo_a17 = EST_RCO_TITULO_A5, EST_RCO_ROTULO_A17
        nombre_dst = EST_RCO_PLANTILLA
    else:
        archivo_rel, hoja_src = (FUENTE_RFO_MACAO2 if (empresa, fase) == ("DOMICEM", "MACAO 2")
                                 else FUENTE_RFO)
        titulo_a5, rotulo_a17 = EST_RFO_TITULO_A5, EST_RFO_ROTULO_A17
        nombre_dst = EST_RFO_PLANTILLA

    ultima_fila, escala = _est_geometria_rco_rfo(familia, empresa, fase)
    ws_src = _hoja_fuente(archivo_rel, hoja_src)

    ws = wb_dst.create_sheet(nombre_dst)
    _copiar_celdas_y_dimensiones(ws_src, ws)

    # altos de fila EFECTIVOS: las filas sin alto explicito en la fuente usan
    # el defaultRowHeight de SU hoja (12.75), que no coincide con el default
    # de una hoja nueva (15) — sin esto el marco del croquis saldria mas alto
    # que el real y el area de impresion ya no cabria en una pagina
    ws.sheet_format.defaultRowHeight = ws_src.sheet_format.defaultRowHeight
    ws.sheet_format.defaultColWidth = ws_src.sheet_format.defaultColWidth
    for fila in range(1, ultima_fila + 1):
        if fila not in ws.row_dimensions or ws.row_dimensions[fila].height is None:
            ws.row_dimensions[fila].height = ws_src.sheet_format.defaultRowHeight

    # limpiar TODO el contenido copiado del cuerpo y del pie (la fuente trae
    # el croquis... no: trae los VALORES de firma de su estimacion, un A15
    # con formula a la clave de SU hoja, y en MACAO 2 hasta valores literales
    # de encabezado) — se borra parejo y se reescribe explicito lo que va
    for fila in range(15, ultima_fila + 1):
        for col in range(1, 13):
            celda = ws.cell(fila, col)
            if not isinstance(celda, MergedCell):
                celda.value = None
    # columnas K/L de las filas de encabezado: nunca llevan contenido
    for fila in range(1, 15):
        for col in (11, 12):
            celda = ws.cell(fila, col)
            if not isinstance(celda, MergedCell):
                celda.value = None

    # ── encabezado (mismas formulas que CD-COAF-RGO-PLANTILLA) ──
    ws["A2"] = "='CD-COAF-REO-01'!$A$2"
    ws["A3"] = "='CD-COAF-REO-01'!$A$3"
    ws["A5"] = titulo_a5
    ws["A7"] = "OBRA:"
    ws["B7"] = "='CD-COAF-REO-01'!$B$7"
    ws["A9"] = "CONTRATISTA:"
    ws["B9"] = "='CD-COAF-REO-01'!$B$9"
    ws["F9"] = "OC / CONTRATO:"
    ws["G9"] = "='CD-COAF-REO-01'!$M$9"
    ws["A11"] = "ESTIMACION:"
    ws["B11"] = "TIPO:"
    ws["D11"] = "PERIODO:"
    ws["G11"] = "FECHA: "
    ws["H11"] = "SEMANA:"
    ws["A12"] = "='CD-COAF-REO-01'!$A$12"
    ws["B12"] = "='CD-COAF-REO-01'!$B$12"
    ws["D12"] = "='CD-COAF-REO-01'!$E$12"
    ws["E12"] = "A"
    ws["F12"] = "='CD-COAF-REO-01'!$H$12"
    ws["G12"] = "='CD-COAF-REO-01'!$K$12"
    ws["H12"] = "='CD-COAF-REO-01'!$N$12"
    ws["A14"] = "PARTIDA:"
    ws["B14"] = "CLAVE:"
    ws["C14"] = "CONCEPTO:"
    ws["J14"] = "U. M."
    # la fila 15 (partida/clave/concepto/U.M.) queda vacia: el generador la
    # escribe por clave, igual que hace con la RGO
    ws["A17"] = rotulo_a17

    # ── firmas — ancladas a la fila REAL del bloque de firma del REO de
    # ESTA fase (issue #33: la formula fija a E37 solo acierta en 2 de 9
    # fases y el formato contable disfraza el hueco de dato). Ademas la
    # fuente traia E46 apuntando a una hoja RGO concreta ("='CD-COAF-RGO-03'
    # !$D$61") que puede no existir en el documento generado.
    fila_nombre, fila_cargo = _est_filas_firma_reo(wb_dst["CD-COAF-REO-01"])
    f_nombre, f_cargo = ultima_fila - 1, ultima_fila
    ws[f"B{f_nombre}"] = f"='CD-COAF-REO-01'!$B${fila_nombre}"
    ws[f"E{f_nombre}"] = f"='CD-COAF-REO-01'!$E${fila_nombre}"
    ws[f"H{f_nombre}"] = f"='CD-COAF-REO-01'!$K${fila_nombre}"
    ws[f"B{f_cargo}"] = "CONTRATISTA"
    ws[f"E{f_cargo}"] = f"='CD-COAF-REO-01'!$E${fila_cargo}"
    ws[f"H{f_cargo}"] = f"='CD-COAF-REO-01'!$K${fila_cargo}"

    # ── configuracion de pagina ──
    ws.page_margins = copy(ws_src.page_margins)
    ws.print_options.horizontalCentered = ws_src.print_options.horizontalCentered
    ws.page_setup.orientation = "landscape"
    ws.page_setup.scale = escala
    ws.page_setup.fitToWidth = None
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = False
    ws.print_area = f"A1:J{ultima_fila}"
    ws.oddFooter.center.text = FOOTER_RCO_RFO

    # ── verificaciones ruidosas ──
    _afirmar_hoja_sin_imagenes(ws, f"{empresa}/{fase} {nombre_dst}")
    merges = {str(m) for m in ws.merged_cells.ranges}
    for esperado in MERGES_CUERPO[(familia, ultima_fila)]:
        if esperado not in merges:
            raise ValueError(
                f"{empresa}/{fase} {nombre_dst}: falta el merge {esperado} del "
                f"cuerpo — la hoja fuente {archivo_rel}::{hoja_src} cambio de "
                f"estructura, revisar antes de committear la plantilla"
            )
    fin_marco = ultima_fila - EST_RCO_RFO_FILAS_PIE
    if any(m.min_row <= fin_marco < m.max_row for m in ws.merged_cells.ranges):
        raise ValueError(
            f"{empresa}/{fase} {nombre_dst}: hay un merge que cruza el fin del "
            f"marco (fila {fin_marco}) — la geometria no cierra"
        )


def agregar_rco_rfo(empresa: str, fase: str, verbose: bool = True) -> str:
    """Modo --solo-rco-rfo: agrega (o reemplaza) las hojas RCO/RFO-PLANTILLA
    sobre el archivo de plantilla YA CONSTRUIDO de esa fase, sin tocar
    CEO/REO/RGO (conservan el post-proceso estetico que una reconstruccion
    completa no reproduce). Idempotente."""
    nombre = f"plantilla_estimacion_{_slug(empresa, fase)}.xlsx"
    destino = os.path.join(DEST_DIR, nombre)
    if not os.path.exists(destino):
        raise FileNotFoundError(
            f"{destino} no existe — construirlo primero con --fase/--todas"
        )
    wb = openpyxl.load_workbook(destino, data_only=False)
    for hoja in (EST_RCO_PLANTILLA, EST_RFO_PLANTILLA):
        if hoja in wb.sheetnames:
            del wb[hoja]
    construir_hoja_rco_rfo(wb, empresa, fase, "RCO")
    construir_hoja_rco_rfo(wb, empresa, fase, "RFO")
    tmp = destino + ".tmp"
    wb.save(tmp)
    os.replace(tmp, destino)
    if verbose:
        print(f"OK  {empresa}/{fase:28s} + RCO/RFO-PLANTILLA -> {nombre}")
    return destino


def limpiar(empresa: str, fase: str, verbose: bool = True) -> str:
    archivo_rel = FASES[(empresa, fase)]
    origen = os.path.join(FUENTES_DIR, archivo_rel)
    if not os.path.exists(origen):
        raise FileNotFoundError(origen)

    wb = openpyxl.load_workbook(origen, data_only=False)

    reo_name = "CD-COAF-REO-01"
    ceo_name = "CD-COAF-CEO-01"
    if reo_name not in wb.sheetnames or ceo_name not in wb.sheetnames:
        raise ValueError(f"{archivo_rel}: faltan hojas {reo_name}/{ceo_name}")

    ws_reo = wb[reo_name]
    capacidad = _detectar_capacidad(ws_reo)
    if capacidad < 1:
        raise ValueError(f"{archivo_rel}: no se detecto bloque de productos en fila {FIRST_ROW}")

    # eliminar todas las hojas menos CEO-01 y REO-01
    for name in list(wb.sheetnames):
        if name not in (ceo_name, reo_name):
            del wb[name]

    # fila 16 (encabezado de sub-columnas) puede traer etiquetas de una
    # estimacion anterior (ej. "N42") — se limpia para no dejar info vieja
    for col in ("H", "K", "N"):
        ws_reo[f"{col}16"] = None

    # limpiar + reescribir formulas del bloque de productos
    for i in range(capacidad):
        r = FIRST_ROW + i
        for col in CLEAR_COLS:
            ws_reo[f"{col}{r}"] = None
        for col, tmpl in FORMULAS.items():
            ws_reo[f"{col}{r}"] = tmpl.format(r=r)

    last_row = FIRST_ROW + capacidad - 1
    totales_row = last_row + 2  # 1 fila en blanco de por medio, ya presente en el archivo real
    a_totales = ws_reo.cell(totales_row, 1).value
    if a_totales != "TOTALES:":
        raise ValueError(
            f"{archivo_rel}: fila de TOTALES esperada en {totales_row} pero A{totales_row}={a_totales!r} "
            f"(capacidad detectada={capacidad}) — revisar antes de continuar"
        )

    # Renglones que el documento del cliente todavia no trae (ver
    # EST_PLANTILLAS en core). Ocupan la fila en blanco de antes de TOTALES,
    # con el estilo de la ultima fila de producto (bordes incluidos), asi que
    # no se inserta nada y TOTALES, firmas y pie no se mueven.
    extra = EST_PLANTILLAS.get((empresa, fase), {}).get("renglones_extra", 0)
    if extra > 1:
        raise ValueError(f"{empresa}/{fase}: renglones_extra={extra} — solo cabe 1 sin insertar filas")
    for i in range(extra):
        r = last_row + 1 + i
        for col in range(1, ws_reo.max_column + 1):
            src = ws_reo.cell(last_row, col)
            dst = ws_reo.cell(r, col)
            if isinstance(src, MergedCell) or isinstance(dst, MergedCell):
                continue
            if src.has_style:
                dst.font = copy(src.font)
                dst.border = copy(src.border)
                dst.fill = copy(src.fill)
                dst.number_format = src.number_format
                dst.protection = copy(src.protection)
                dst.alignment = copy(src.alignment)
        for col, tmpl in FORMULAS.items():
            ws_reo[f"{col}{r}"] = tmpl.format(r=r)
    last_row += extra
    capacidad += extra
    ws_reo[f"F{totales_row}"] = f"=SUM(F{FIRST_ROW}:F{last_row})"
    ws_reo[f"I{totales_row}"] = f"=SUM(I{FIRST_ROW}:I{last_row})"
    ws_reo[f"L{totales_row}"] = f"=SUM(L{FIRST_ROW}:L{last_row})"
    ws_reo[f"O{totales_row}"] = f"=SUM(O{FIRST_ROW}:O{last_row})"
    ws_reo[f"R{totales_row}"] = f"=SUM(R{FIRST_ROW}:R{last_row})"
    ws_reo[f"T{totales_row}"] = f"=AVERAGE(T{FIRST_ROW}:T{last_row})"

    # copiar la hoja RGO generica (sin cambios) desde la plantilla de CEDIS ya validada
    wb_rgo = openpyxl.load_workbook(PLANTILLA_RGO_ORIGEN, data_only=False)
    ws_rgo_src = wb_rgo["CD-COAF-RGO-PLANTILLA"]
    ws_rgo_dst = wb.create_sheet("CD-COAF-RGO-PLANTILLA")
    _copiar_celdas_y_dimensiones(ws_rgo_src, ws_rgo_dst)
    _afirmar_hoja_sin_imagenes(ws_rgo_dst, f"{empresa}/{fase} CD-COAF-RGO-PLANTILLA")

    # Issue #27 — las hojas RCO/RFO-PLANTILLA (croquis y reporte fotografico)
    construir_hoja_rco_rfo(wb, empresa, fase, "RCO")
    construir_hoja_rco_rfo(wb, empresa, fase, "RFO")

    nombre = f"plantilla_estimacion_{_slug(empresa, fase)}.xlsx"
    destino = os.path.join(DEST_DIR, nombre)
    tmp = destino + ".tmp"
    wb.save(tmp)
    os.replace(tmp, destino)

    if verbose:
        print(f"OK  {empresa}/{fase:28s} capacidad={capacidad:2d}  totales_row={totales_row}  -> {nombre}")
    return destino


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--fase", help="empresa/fase, ej. DOMICEM/CAVERNAS")
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--solo-rco-rfo", action="store_true",
                    help="solo agrega/reemplaza RCO/RFO-PLANTILLA sobre la "
                         "plantilla existente, sin reconstruir CEO/REO/RGO")
    args = ap.parse_args()

    if args.list:
        for (empresa, fase) in FASES:
            print(f"{empresa}/{fase}")
        return

    accion = agregar_rco_rfo if args.solo_rco_rfo else limpiar

    if args.fase:
        empresa, fase = args.fase.split("/", 1)
        accion(empresa, fase)
        return

    if args.todas:
        for (empresa, fase) in FASES:
            accion(empresa, fase)
        return

    ap.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
