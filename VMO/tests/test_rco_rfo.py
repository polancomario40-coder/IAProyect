"""
Cubre issue #27 — hojas CD-COAF-RCO-XX (Croquis de Ubicacion) y CD-COAF-RFO-XX
(Reporte Fotografico) en el generador de estimaciones.

Una RCO y una RFO por clave con entregas del periodo, en paralelo a las RGO
(el "6 y 6" del issue original era falso — medido: entre 2 y 13 RCO por
documento del cliente). No tienen tabla ni formulas de calculo: cuerpo de
marco fusionado + imagenes flotantes, largo fijo, sin paginacion.

Los dos hallazgos que estos tests custodian:

- D1: wb.copy_worksheet() de openpyxl 3.1.5 pierde print_area, el footer y
  TODAS las imagenes, en silencio (los merges y las formulas si sobreviven).
  Por eso el generador re-fija la config de impresion y re-estampa las
  imagenes EN CADA HOJA despues de copiar, y la PLANTILLA debe nacer sin
  imagenes. El test de regresion del criterio 11 demuestra que sin el fix la
  print_area sale vacia.
- El titulo real de A5 viene con las letras espaciadas una por una (asi lo
  escribe el cliente en sus 156 hojas), con un doble espacio irregular en
  "D E    U B I C A C I O N". Un test que afirme el string plano
  "REPORTE FOTOGRAFICO" falla siempre — se afirma el string EXACTO (T7).

Los croquis de los tests son PNG sinteticos en memoria (criterio 10) — no
necesitan los archivos reales de estimaciones/data/croquis/.

Correr con: python -m pytest tests/test_rco_rfo.py -v
"""
import os
import re
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime
from types import SimpleNamespace

import openpyxl
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image as PILImage

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import main  # noqa: E402 (solo para main.app)
from core import (  # noqa: E402
    EST_DATA_DIR, EST_PLANTILLAS, EST_REO_FIRST_ROW,
    EST_RCO_PLANTILLA, EST_RFO_PLANTILLA,
    EST_RCO_TITULO_A5, EST_RFO_TITULO_A5, EST_RCO_ROTULO_A17, EST_RFO_ROTULO_A17,
    EST_RCO_RFO_PRIMERA_FILA_MARCO, EST_RCO_RFO_FILAS_PIE, EST_EMU_POR_PX,
    _est_buscar_croquis, _est_col_px, _est_fila_px, _est_filas_firma_reo,
    _est_geometria_rco_rfo, _est_id_clave,
)

FASES = sorted(EST_PLANTILLAS.keys())

# capturado al importar: _generar_xlsx() monkeypatchea core.EST_SOFFICE a None
# para saltarse la conversion a PDF cuando no aporta nada
SOFFICE = core.EST_SOFFICE
requiere_libreoffice = pytest.mark.skipif(
    SOFFICE is None,
    reason="LibreOffice no esta instalado — se salta la verificacion con recalculo real",
)

# Los 15 documentos reales del cliente (768 MB) no se versionan: en un
# checkout que no los tenga, los tests que comparan contra ellos se saltan.
FUENTES_DIR = os.environ.get("EST_FUENTES_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "estimaciones", "data", "plantillas_por_fase")
DOC_REAL_CEDIS = os.path.join(FUENTES_DIR, "VMO", "EST_VMO_CEDIS_4800036588_N09_22072026_V01.xlsx")
requiere_documentos_cliente = pytest.mark.skipif(
    not os.path.exists(DOC_REAL_CEDIS),
    reason="los documentos fuente del cliente no estan en este checkout "
           "(EST_FUENTES_DIR para apuntarlos)",
)


# ── helpers ───────────────────────────────────────────────────────────────

def _png(ruta, ancho, alto, color="lightgray"):
    PILImage.new("RGB", (ancho, alto), color).save(ruta)
    return str(ruta)


def _entorno_croquis(tmp_path, monkeypatch):
    """Carpetas de croquis y logos VACIAS y aisladas (los tests siembran el
    PNG sintetico que necesiten) — nunca se toca estimaciones/data/croquis/."""
    croquis_dir = tmp_path / "croquis"
    logos_dir = croquis_dir / "logos"
    logos_dir.mkdir(parents=True)
    monkeypatch.setattr(core, "EST_CROQUIS_DIR", str(croquis_dir))
    monkeypatch.setattr(core, "EST_LOGOS_DIR", str(logos_dir))
    return croquis_dir, logos_dir


def _bd_sintetica(tmp_path, monkeypatch, empresa, fase, claves_con_facturas):
    """Catalogo de 3 productos (cabe en la plantilla de las 9 fases; la mas
    chica soporta 3) y facturas solo para las claves pedidas — mismo patron
    que tests/test_firma_rgo.py::_bd_sintetica."""
    db_path = tmp_path / f"est_{uuid.uuid4().hex}.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE catalogo_estimacion (
        empresa TEXT, fase TEXT, orden INTEGER, clave TEXT,
        descripcion TEXT, precio_unitario REAL,
        PRIMARY KEY (empresa, fase, orden)
    )""")
    conn.execute("""CREATE TABLE facturas (
        id_documento TEXT PRIMARY KEY, fecha DATE, empresa TEXT, fase TEXT,
        descripcion TEXT, cantidad REAL, precio_unitario REAL, clave_resuelta TEXT
    )""")
    conn.execute("""CREATE TABLE estimacion_acumulado_base (
        empresa TEXT, fase TEXT, clave TEXT,
        serie TEXT NOT NULL CHECK (serie IN ('principal','ppact')),
        fecha_base DATE, cantidad_base REAL, cantidad_proyecto_principal REAL,
        PRIMARY KEY (empresa, fase, clave, serie)
    )""")
    descripciones = {"1": "Producto Uno", "2": "Producto Dos", "3": "Producto Tres"}
    for orden, (clave, desc) in enumerate(sorted(descripciones.items()), start=1):
        conn.execute("INSERT INTO catalogo_estimacion VALUES (?,?,?,?,?,100.0)",
                     (empresa, fase, orden, clave, desc))
    for i, clave in enumerate(claves_con_facturas):
        conn.execute(
            "INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,cantidad,precio_unitario) "
            "VALUES (?,?,?,?,?,?,100.0)",
            (f"F{i + 1:03d}", f"2026-06-{(i % 28) + 1:02d}", empresa, fase,
             descripciones[clave], 10),
        )
    conn.commit()
    conn.close()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))

    token = f"test-token-{uuid.uuid4().hex}"
    core.active_tokens[token] = datetime.now()
    return token


def _generar_xlsx(tmp_path, monkeypatch, empresa, fase,
                  claves_con_facturas=("1",), con_pdf=False, subdir=""):
    """Genera la estimacion end-to-end por la ruta HTTP real y devuelve la
    ruta del .xlsx. No arma el entorno de croquis: cada test lo declara
    explicito con _entorno_croquis().

    subdir separa las salidas de dos generaciones del MISMO test: el nombre
    del archivo lleva timestamp con resolucion de segundos, asi que dos
    generaciones seguidas en la misma carpeta caen en el mismo nombre y la
    segunda PISA a la primera — un test que luego "compare" los dos archivos
    estaria comparando el mismo contra si mismo, en silencio."""
    salida = os.path.join(str(tmp_path), subdir) if subdir else str(tmp_path)
    os.makedirs(salida, exist_ok=True)
    token = _bd_sintetica(tmp_path, monkeypatch, empresa, fase, claves_con_facturas)
    monkeypatch.setattr(core, "EST_REPORTES_DIR", salida)
    if not con_pdf:
        monkeypatch.setattr(core, "EST_SOFFICE", None)

    client = TestClient(main.app)
    res = client.post(
        "/api/estimaciones/generar",
        json={
            "empresa": empresa, "fase": fase,
            "fecha_desde": "2026-06-01", "fecha_hasta": "2026-06-30",
            "numero_estimacion": "N01", "fecha_estimacion": "2026-08-24", "semana": 1,
            "productos": [
                {"clave": c, "cantidad_proyecto": 10000, "acumulado_anterior_cantidad": 0}
                for c in ("1", "2", "3")
            ],
            "reasignaciones": {}, "serie": "principal",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    nombre = res.json()["download_url"].rsplit("/", 1)[-1]
    return os.path.join(salida, nombre)


def _rango_print_area(ws):
    """'$A$1:$J$46' sin el prefijo de nombre de hoja (openpyxl lo devuelve
    con la hoja por delante)."""
    return (ws.print_area or "").split("!")[-1]


def _marco_emu(ws, ultima_fila):
    """(ancho, alto) del marco A18:J{ultima-3} en EMU, calculado igual que
    core._est_insertar_croquis."""
    fila_ini = EST_RCO_RFO_PRIMERA_FILA_MARCO
    fila_fin = ultima_fila - EST_RCO_RFO_FILAS_PIE
    ancho = sum(_est_col_px(ws, c) for c in range(1, 11)) * EST_EMU_POR_PX
    alto = sum(_est_fila_px(ws, f) for f in range(fila_ini, fila_fin + 1)) * EST_EMU_POR_PX
    return ancho, alto


# ── plantillas: titulos, firmas y ausencia de imagenes ───────────────────

@pytest.mark.parametrize("empresa,fase", FASES)
def test_titulos_a5_y_rotulos_a17_de_las_plantillas(empresa, fase):
    """T7 — el A5 real viene con las letras espaciadas una por una y el de la
    RCO trae un doble espacio irregular; se afirma el string EXACTO (la
    decision explicita del criterio 2: afirmar sobre el string exacto, no
    normalizar espacios antes de comparar). La RFO va con el titulo CORRECTO
    de su tipo (decision 5) aunque 6 de los 15 documentos del cliente la
    titulen 'CROQUIS DE UBICACION' por descuido."""
    info = EST_PLANTILLAS[(empresa, fase)]
    wb = openpyxl.load_workbook(os.path.join(EST_DATA_DIR, info["archivo"]))
    try:
        rco, rfo = wb[EST_RCO_PLANTILLA], wb[EST_RFO_PLANTILLA]
        assert rco["A5"].value == EST_RCO_TITULO_A5
        assert rfo["A5"].value == EST_RFO_TITULO_A5
        assert rco["A17"].value == EST_RCO_ROTULO_A17
        assert rfo["A17"].value == EST_RFO_ROTULO_A17
        # el espaciado letra-por-letra es la forma real — que nadie lo
        # "normalice" a texto plano sin darse cuenta de que asi no es el
        # documento del cliente
        assert "R E S U M E N" in EST_RFO_TITULO_A5
        assert "D E    U B I C A C" in EST_RCO_TITULO_A5   # el doble espacio irregular
    finally:
        wb.close()


@requiere_documentos_cliente
def test_titulos_a5_coinciden_con_el_documento_real_del_cliente():
    """T7, verificacion contra el cliente: CEDIS N09 es la fuente verificada
    por el spec (titulo A5 correcto en ambas familias). Si esto falla, la
    constante ya no es byte-exacta al documento real."""
    wb = openpyxl.load_workbook(DOC_REAL_CEDIS, read_only=True)
    try:
        assert wb["CD-COAF-RCO-01"]["A5"].value == EST_RCO_TITULO_A5
        assert wb["CD-COAF-RFO-01"]["A5"].value == EST_RFO_TITULO_A5
    finally:
        wb.close()


@pytest.mark.parametrize("empresa,fase", FASES)
def test_firmas_de_las_plantillas_apuntan_a_la_fila_real_del_reo(empresa, fase):
    """Criterio 3 — las formulas de firma de RCO/RFO-PLANTILLA anclan a la
    fila REAL del bloque de firma del REO de ESA fase (TRB 29/30 y
    EXTERIORES 40/41 incluidas), nunca a la E37 fija que causo el bug del
    issue #33 en 7 de las 9 fases."""
    info = EST_PLANTILLAS[(empresa, fase)]
    wb = openpyxl.load_workbook(os.path.join(EST_DATA_DIR, info["archivo"]))
    try:
        fila_nombre, fila_cargo = _est_filas_firma_reo(wb["CD-COAF-REO-01"])
        for familia, hoja in (("RCO", EST_RCO_PLANTILLA), ("RFO", EST_RFO_PLANTILLA)):
            ws = wb[hoja]
            ultima_fila, _ = _est_geometria_rco_rfo(familia, empresa, fase)
            f_nombre, f_cargo = ultima_fila - 1, ultima_fila
            assert ws[f"E{f_nombre}"].value == f"='CD-COAF-REO-01'!$E${fila_nombre}"
            assert ws[f"E{f_cargo}"].value == f"='CD-COAF-REO-01'!$E${fila_cargo}"
            assert ws[f"H{f_nombre}"].value == f"='CD-COAF-REO-01'!$K${fila_nombre}"
            assert ws[f"H{f_cargo}"].value == f"='CD-COAF-REO-01'!$K${fila_cargo}"
            assert ws[f"B{f_nombre}"].value == f"='CD-COAF-REO-01'!$B${fila_nombre}"
            assert ws[f"B{f_cargo}"].value == "CONTRATISTA"
    finally:
        wb.close()


def test_la_fila_de_firma_no_es_la_misma_en_todas_las_fases_tampoco_aca():
    """Deja constancia de por que la formula fija a E37 seria el bug del #33
    otra vez: las filas reales difieren entre fases (TRB 29/30, EXTERIORES
    40/41...). Si esto falla, el bug ya no puede reproducirse."""
    filas = set()
    for empresa, fase in FASES:
        info = EST_PLANTILLAS[(empresa, fase)]
        wb = openpyxl.load_workbook(os.path.join(EST_DATA_DIR, info["archivo"]))
        filas.add(_est_filas_firma_reo(wb["CD-COAF-REO-01"]))
        wb.close()
    assert len(filas) > 1
    assert (29, 30) in filas    # PATIO DE MANIOBRAS-TRB (y TRA)
    assert (40, 41) in filas    # EXTERIORES


@pytest.mark.parametrize("empresa,fase", FASES)
def test_las_plantillas_rco_rfo_nacen_sin_imagenes(empresa, fase):
    """Hallazgo D1 — copy_worksheet pierde las imagenes en silencio, asi que
    una PLANTILLA con logos produciria hojas sin logos sin que nada avise.
    Las imagenes se estampan al generar, hoja por hoja."""
    info = EST_PLANTILLAS[(empresa, fase)]
    wb = openpyxl.load_workbook(os.path.join(EST_DATA_DIR, info["archivo"]))
    try:
        assert wb[EST_RCO_PLANTILLA]._images == []
        assert wb[EST_RFO_PLANTILLA]._images == []
    finally:
        wb.close()


def test_la_plantilla_generica_no_lleva_rco_rfo():
    """Decision explicita (pregunta abierta de la seccion 10 del spec):
    plantilla_estimacion.xlsx NO lleva RCO/RFO-PLANTILLA. El generador nunca
    la abre (EST_PLANTILLAS solo registra las 9 por fase) — es la fuente de
    la hoja RGO generica al reconstruir plantillas y fixture de tests. Las
    hojas RCO/RFO son por-fase por construccion: sus firmas anclan a la fila
    real del REO de cada fase y su geometria depende de la fase (MACAO 2),
    asi que una version "generica" hornearia las filas de firma del REO que
    esa plantilla traiga — exactamente la clase de bug del #33. Si un dia
    una fase nueva naciera de la generica, la guarda plantilla_sin_hojas_
    rco_rfo corta ruidoso con instrucciones en vez de firmar mal."""
    wb = openpyxl.load_workbook(os.path.join(EST_DATA_DIR, "plantilla_estimacion.xlsx"))
    try:
        assert set(wb.sheetnames) == {"CD-COAF-CEO-01", "CD-COAF-REO-01", "CD-COAF-RGO-PLANTILLA"}
    finally:
        wb.close()


# ── unidades chicas: geometria, id de clave, busqueda de croquis ─────────

def test_geometria_por_familia_y_fase():
    """Decision 4 — RCO A1:J46 siempre, MACAO 2 incluida; RFO A1:J46 salvo
    MACAO 2 que va A1:J52 (y a escala 70: el spec decia 76 parejo, pero las
    25 hojas J52 del cliente usan 70 — a 76 el PDF saldria partido)."""
    assert _est_geometria_rco_rfo("RCO", "VMO", "CEDIS") == (46, 76)
    assert _est_geometria_rco_rfo("RFO", "VMO", "CEDIS") == (46, 76)
    assert _est_geometria_rco_rfo("RCO", "DOMICEM", "MACAO 2") == (46, 76)
    assert _est_geometria_rco_rfo("RFO", "DOMICEM", "MACAO 2") == (52, 70)


def test_id_clave_para_nombres_de_archivo():
    """La misma normalizacion que los nombres de hoja (2 digitos si es
    numerica), para que CD-COAF-RCO-07 busque *_07.png y no *_7.png."""
    assert _est_id_clave("7") == "07"
    assert _est_id_clave(7) == "07"
    assert _est_id_clave("12") == "12"
    assert _est_id_clave(" 3 ") == "03"
    assert _est_id_clave("A/B") == "A-B"
    assert _est_id_clave("") == "SIN-CLAVE"


def test_buscar_croquis_por_clave_pisa_al_de_fase(tmp_path, monkeypatch):
    """Patron {EMPRESA}_{FASE}_{clave} pisa a {EMPRESA}_{FASE} (necesario
    para EXTERIORES, con 6 croquis distintos entre sus RCO), y se aceptan
    .png y .jpg (el sembrado guarda JPEG cuando el PNG pasa el tope D2)."""
    croquis_dir, _ = _entorno_croquis(tmp_path, monkeypatch)
    assert _est_buscar_croquis("VMO", "CEDIS", "1") is None

    fase = _png(croquis_dir / "VMO_CEDIS.jpg", 40, 30)
    assert _est_buscar_croquis("VMO", "CEDIS", "1") == fase
    assert _est_buscar_croquis("VMO", "CEDIS", "7") == fase

    clave7 = _png(croquis_dir / "VMO_CEDIS_07.png", 40, 30)
    assert _est_buscar_croquis("VMO", "CEDIS", "7") == clave7
    assert _est_buscar_croquis("VMO", "CEDIS", "1") == fase

    # el slug sanea espacios y guiones — PATIO DE MANIOBRAS-TRB no rompe
    trb = _png(croquis_dir / "DOMICEM_PATIO_DE_MANIOBRAS_TRB.png", 40, 30)
    assert _est_buscar_croquis("DOMICEM", "PATIO DE MANIOBRAS-TRB", "2") == trb


# ── generador: hojas por clave, orden, fila 15, encabezado ───────────────

def test_hojas_por_clave_con_entregas_y_orden_agrupado_por_tipo(tmp_path, monkeypatch):
    """Criterios 1 y 7 — una RCO y una RFO por clave CON facturas (la clave
    sin entregas no trae ninguna de las tres, decision 3), agrupadas por
    tipo: CEO, REO, todas las RGO, todas las RCO, todas las RFO (decision
    6). Las hojas PLANTILLA no viajan al documento final."""
    _entorno_croquis(tmp_path, monkeypatch)
    ruta = _generar_xlsx(tmp_path, monkeypatch, "VMO", "CEDIS",
                         claves_con_facturas=("1", "2"))
    wb = openpyxl.load_workbook(ruta)
    try:
        assert wb.sheetnames == [
            "CD-COAF-CEO-01", "CD-COAF-REO-01",
            "CD-COAF-RGO-01", "CD-COAF-RGO-02",
            "CD-COAF-RCO-01", "CD-COAF-RCO-02",
            "CD-COAF-RFO-01", "CD-COAF-RFO-02",
        ]
    finally:
        wb.close()


def test_fila_15_encabezado_firma_y_footer_de_las_hojas_generadas(tmp_path, monkeypatch):
    """Criterio 2 (estructura) — la fila 15 lleva clave/concepto/U.M. por
    formula a la fila de SU clave en REO-01; el encabezado completo viaja por
    las formulas de la plantilla (decision 1: 'llena TODO' — lo unico manual
    que queda son las fotos de la RFO); las firmas anclan a la fila real del
    REO; el footer (que copy_worksheet tambien pierde — medido aca, no estaba
    en el spec) queda repuesto.

    A15 (PARTIDA:) va VACIO desde el issue #37 (2026-09-02). Antes llevaba el
    `orden` del catalogo como valor; se cambio para copiar a los documentos
    del cliente, donde ese casillero sale en blanco siempre. El test dedicado
    es test_partida_a15_sale_vacia_en_las_tres_hojas en
    tests/test_reo_columna_clave.py, que ademas cubre la RGO."""
    _entorno_croquis(tmp_path, monkeypatch)
    ruta = _generar_xlsx(tmp_path, monkeypatch, "VMO", "CEDIS",
                         claves_con_facturas=("1", "2"))
    wb = openpyxl.load_workbook(ruta)
    try:
        fila_nombre, fila_cargo = _est_filas_firma_reo(wb["CD-COAF-REO-01"])
        for nombre, orden in (("CD-COAF-RCO-02", 2), ("CD-COAF-RFO-02", 2),
                              ("CD-COAF-RCO-01", 1), ("CD-COAF-RFO-01", 1)):
            ws = wb[nombre]
            fila_reo = EST_REO_FIRST_ROW + (orden - 1)
            # fila 15 por clave — A15 (PARTIDA:) vacio, issue #37
            assert ws["A15"].value is None
            assert ws["B15"].value == f"='CD-COAF-REO-01'!$A${fila_reo}"
            assert ws["C15"].value == f"='CD-COAF-REO-01'!$B${fila_reo}"
            assert ws["J15"].value == f"='CD-COAF-REO-01'!$C${fila_reo}"
            # encabezado completo (obra, contratista, OC/contrato, numero,
            # tipo, periodo, fecha, semana) — por formula a REO-01
            assert ws["A2"].value == "='CD-COAF-REO-01'!$A$2"
            assert ws["B7"].value == "='CD-COAF-REO-01'!$B$7"
            assert ws["B9"].value == "='CD-COAF-REO-01'!$B$9"
            assert ws["G9"].value == "='CD-COAF-REO-01'!$M$9"
            assert ws["A12"].value == "='CD-COAF-REO-01'!$A$12"
            assert ws["B12"].value == "='CD-COAF-REO-01'!$B$12"
            assert ws["D12"].value == "='CD-COAF-REO-01'!$E$12"
            assert ws["E12"].value == "A"
            assert ws["F12"].value == "='CD-COAF-REO-01'!$H$12"
            assert ws["G12"].value == "='CD-COAF-REO-01'!$K$12"
            assert ws["H12"].value == "='CD-COAF-REO-01'!$N$12"
            # firma anclada a la fila real del bloque del REO (criterio 3)
            ultima = int(_rango_print_area(ws).rsplit("$", 1)[-1])
            assert ws[f"E{ultima - 1}"].value == f"='CD-COAF-REO-01'!$E${fila_nombre}"
            assert ws[f"E{ultima}"].value == f"='CD-COAF-REO-01'!$E${fila_cargo}"
            # footer repuesto tras la copia (&A = nombre real de la hoja)
            assert (ws.oddFooter.center.text or "").startswith("&A")
    finally:
        wb.close()


@requiere_libreoffice
def test_fila_15_y_encabezado_recalculados_con_libreoffice(tmp_path, monkeypatch):
    """Criterio 2 (recalculo real) — B15/C15/J15 y el encabezado resuelven a
    los valores correctos al recalcular, que es lo que hace LibreOffice al
    exportar el PDF y Excel al abrir el archivo."""
    _entorno_croquis(tmp_path, monkeypatch)
    ruta = _generar_xlsx(tmp_path, monkeypatch, "VMO", "CEDIS",
                         claves_con_facturas=("1", "2"))
    salida = tmp_path / "calc"
    salida.mkdir()
    resultado = subprocess.run(
        [SOFFICE, "--headless", "--calc", "--convert-to", "xlsx",
         "--outdir", str(salida), ruta],
        capture_output=True, text=True, timeout=120,
    )
    assert resultado.returncode == 0, f"LibreOffice fallo: {resultado.stderr}"
    wb = openpyxl.load_workbook(str(salida / os.path.basename(ruta)), data_only=True)
    try:
        for nombre, clave, desc in (("CD-COAF-RCO-01", 1, "Producto Uno"),
                                    ("CD-COAF-RFO-02", 2, "Producto Dos")):
            ws = wb[nombre]
            assert ws["B15"].value == clave, f"{nombre}: B15 resolvio a {ws['B15'].value!r}"
            assert ws["C15"].value == desc
            assert ws["J15"].value == "m3"
            assert ws["B9"].value == core.EST_CONTRATISTA["VMO"]
            assert ws["A12"].value == "N01"
            assert ws["H12"].value == 1        # semana
    finally:
        wb.close()


# ── criterio 11 — regresion: print_area se pierde al copiar ──────────────

def test_regresion_copy_worksheet_pierde_print_area_y_footer():
    """La demostracion de que el fix hace falta: una copia PELADA de la
    PLANTILLA sale sin print_area y sin footer aunque la fuente los tenga
    (openpyxl 3.1.5, verificado — el spec solo registraba print_area; el
    footer se encontro midiendo). Si una version futura de openpyxl los
    conserva, esto avisa que la re-fijacion quedo redundante. El fix en si
    lo custodia test_print_area_y_config_de_impresion_por_fase: sin re-fijar
    print_area en cada hoja, ahi saldria vacia."""
    info = EST_PLANTILLAS[("VMO", "CEDIS")]
    wb = openpyxl.load_workbook(os.path.join(EST_DATA_DIR, info["archivo"]))
    try:
        origen = wb[EST_RCO_PLANTILLA]
        assert _rango_print_area(origen) == "$A$1:$J$46"
        assert origen.oddFooter.center.text

        copia = wb.copy_worksheet(origen)
        assert not copia.print_area, (
            "wb.copy_worksheet() ya conserva print_area — el re-fijado del "
            "generador quedo redundante, revisar antes de quitarlo"
        )
        assert not copia.oddFooter.center.text
    finally:
        wb.close()


@pytest.mark.parametrize("empresa,fase", FASES)
def test_print_area_y_config_de_impresion_por_fase(empresa, fase, tmp_path, monkeypatch):
    """Criterios 5 y 6, y el test de regresion del criterio 11: print_area
    PRESENTE en cada hoja generada (copy_worksheet la pierde en silencio —
    si se quita el re-fijado del generador, esto falla), con la geometria de
    la decision 4 y la config de impresion medida: landscape, sin saltos de
    fila, escala 76 (70 para la RFO de MACAO 2, como sus 25 hojas reales)."""
    _entorno_croquis(tmp_path, monkeypatch)
    ruta = _generar_xlsx(tmp_path, monkeypatch, empresa, fase)
    wb = openpyxl.load_workbook(ruta)
    try:
        for familia, nombre in (("RCO", "CD-COAF-RCO-01"), ("RFO", "CD-COAF-RFO-01")):
            ws = wb[nombre]
            ultima_fila, escala = _est_geometria_rco_rfo(familia, empresa, fase)
            assert _rango_print_area(ws) == f"$A$1:$J${ultima_fila}", (
                f"{empresa}/{fase} {nombre}: print_area {ws.print_area!r} — "
                f"la perdida silenciosa de copy_worksheet volvio"
            )
            assert ws.page_setup.orientation == "landscape"
            assert int(ws.page_setup.scale) == escala
            assert not ws.sheet_properties.pageSetUpPr.fitToPage
            assert len(ws.row_breaks.brk) == 0
            assert len(ws.col_breaks.brk) == 0
    finally:
        wb.close()


# ── criterio 11 — regresion: los totales no cambian ni un centavo ────────

def test_totales_identicos_con_y_sin_hojas_rco_rfo(tmp_path, monkeypatch):
    """Criterios 9 y 11 — las hojas nuevas son hoja-final: no escriben ni
    una celda de CEO-01, REO-01 ni de las RGO. Se genera el mismo documento
    con el bloque RCO/RFO anulado y las tres hojas historicas tienen que
    quedar IDENTICAS celda por celda (valores y formulas — de ahi que los
    totales recalculados no puedan cambiar ni un centavo).

    Las dos generaciones van a carpetas SEPARADAS (subdir): el timestamp del
    nombre tiene resolucion de segundos, asi que en la misma carpeta la
    segunda pisaria a la primera y esto compararia un archivo contra si
    mismo — el test pasaria con y sin cualquier fix (verificado saboteando:
    asi nacio, y el assert de abajo sobre wb_con lo delata)."""
    _entorno_croquis(tmp_path, monkeypatch)
    ruta_con = _generar_xlsx(tmp_path, monkeypatch, "VMO", "CEDIS",
                             claves_con_facturas=("1", "2"), subdir="con")
    monkeypatch.setattr(core, "_est_agregar_hojas_rco_rfo",
                        lambda *args, **kwargs: ([], []))
    ruta_sin = _generar_xlsx(tmp_path, monkeypatch, "VMO", "CEDIS",
                             claves_con_facturas=("1", "2"), subdir="sin")
    assert ruta_con != ruta_sin

    wb_con = openpyxl.load_workbook(ruta_con)
    wb_sin = openpyxl.load_workbook(ruta_sin)
    try:
        # que el "con" traiga de verdad las hojas nuevas y el "sin" no —
        # sin esto el test podria estar comparando dos documentos "sin"
        assert "CD-COAF-RCO-01" in wb_con.sheetnames
        assert "CD-COAF-RFO-02" in wb_con.sheetnames
        assert [h for h in wb_sin.sheetnames if "RCO" in h or "RFO" in h] == []
        for hoja in ("CD-COAF-CEO-01", "CD-COAF-REO-01", "CD-COAF-RGO-01", "CD-COAF-RGO-02"):
            celdas_con = {(c.row, c.column): c.value
                          for fila in wb_con[hoja].iter_rows() for c in fila
                          if c.value is not None}
            celdas_sin = {(c.row, c.column): c.value
                          for fila in wb_sin[hoja].iter_rows() for c in fila
                          if c.value is not None}
            assert celdas_con == celdas_sin, f"{hoja}: cambio al agregar RCO/RFO"
    finally:
        wb_con.close()
        wb_sin.close()


# ── croquis: presente, ausente, ilegible, por clave ──────────────────────

def test_croquis_anclado_en_el_marco_con_proporcion_conservada(tmp_path, monkeypatch):
    """Criterio 4 — la RCO trae exactamente 1 croquis anclado dentro de
    A18:J43, con la proporcion nativa conservada y centrado en el marco
    (anclar sin definir escala puede cumplir un test y salir deformado
    igual — por eso se afirma la caja ext en EMU). La RFO y las hojas VMO no
    llevan ninguna otra imagen."""
    croquis_dir, _ = _entorno_croquis(tmp_path, monkeypatch)
    _png(croquis_dir / "VMO_CEDIS.png", 800, 200)   # 4:1, bien apaisado
    ruta = _generar_xlsx(tmp_path, monkeypatch, "VMO", "CEDIS")
    wb = openpyxl.load_workbook(ruta)
    try:
        ws = wb["CD-COAF-RCO-01"]
        assert len(ws._images) == 1
        assert wb["CD-COAF-RFO-01"]._images == []

        ancla = ws._images[0].anchor
        cx, cy = ancla.ext.cx, ancla.ext.cy
        # proporcion nativa 4:1 conservada (tolerancia de redondeo a EMU)
        assert abs(cx / cy - 800 / 200) < 0.01, f"deformado: {cx}x{cy}"

        # el marcador esta NORMALIZADO: el offset cae dentro de su propia
        # celda ancla. LibreOffice recorta al renderizar un colOff/rowOff
        # mas grande que la celda (verificado sobre el PDF real de
        # EXTERIORES: el croquis salia pegado a la izquierda del marco) —
        # un ancla "col A + offset gigante" cumple el centrado en EMU y
        # sale descentrada igual en el documento entregado.
        col, fila = ancla._from.col, ancla._from.row
        assert col >= 0 and fila >= EST_RCO_RFO_PRIMERA_FILA_MARCO - 1
        assert ancla._from.colOff < _est_col_px(ws, col + 1) * EST_EMU_POR_PX
        assert ancla._from.rowOff < _est_fila_px(ws, fila + 1) * EST_EMU_POR_PX

        # posicion ABSOLUTA desde la esquina del marco (A18)
        x_abs = sum(_est_col_px(ws, c) for c in range(1, col + 1)) * EST_EMU_POR_PX \
            + ancla._from.colOff
        y_abs = sum(_est_fila_px(ws, f)
                    for f in range(EST_RCO_RFO_PRIMERA_FILA_MARCO, fila + 1)) * EST_EMU_POR_PX \
            + ancla._from.rowOff
        # cabe COMPLETO dentro del marco, contando el offset de centrado
        marco_w, marco_h = _marco_emu(ws, 46)
        assert x_abs + cx <= marco_w
        assert y_abs + cy <= marco_h
        # centrado: el offset absoluto es la mitad exacta del hueco sobrante
        assert abs(2 * x_abs + cx - marco_w) <= 2
        assert abs(2 * y_abs + cy - marco_h) <= 2
    finally:
        wb.close()


def test_croquis_ausente_no_aborta_y_queda_en_el_log(tmp_path, monkeypatch, capsys):
    """Criterio 4 — sin croquis archivado la RCO sale con el marco vacio (el
    propio cliente entrega hojas asi), la generacion NO se aborta, y queda
    registrado en el log que fase quedo sin croquis."""
    _entorno_croquis(tmp_path, monkeypatch)   # carpeta vacia
    ruta = _generar_xlsx(tmp_path, monkeypatch, "VMO", "CEDIS")
    wb = openpyxl.load_workbook(ruta)
    try:
        assert wb["CD-COAF-RCO-01"]._images == []
    finally:
        wb.close()
    assert "sin croquis archivado" in capsys.readouterr().out


def test_croquis_ilegible_no_aborta_y_queda_en_el_log(tmp_path, monkeypatch, capsys):
    """Politica del spec — un PNG corrupto o con extension falsa no puede
    abortar la generacion entera: se omite, se registra, el documento sale."""
    croquis_dir, _ = _entorno_croquis(tmp_path, monkeypatch)
    (croquis_dir / "VMO_CEDIS.png").write_bytes(b"esto no es un png")
    ruta = _generar_xlsx(tmp_path, monkeypatch, "VMO", "CEDIS")
    wb = openpyxl.load_workbook(ruta)
    try:
        assert wb["CD-COAF-RCO-01"]._images == []
    finally:
        wb.close()
    assert "croquis ilegible" in capsys.readouterr().out


def test_croquis_por_clave_pisa_al_de_fase_en_el_documento(tmp_path, monkeypatch):
    """EXTERIORES usa 6 croquis distintos entre sus RCO: la clave con
    archivo propio lo lleva, las demas llevan el de la fase."""
    croquis_dir, _ = _entorno_croquis(tmp_path, monkeypatch)
    _png(croquis_dir / "VMO_CEDIS.png", 400, 300)       # 4:3 — el de fase
    _png(croquis_dir / "VMO_CEDIS_02.png", 900, 300)    # 3:1 — el de la clave 2
    ruta = _generar_xlsx(tmp_path, monkeypatch, "VMO", "CEDIS",
                         claves_con_facturas=("1", "2"))
    wb = openpyxl.load_workbook(ruta)
    try:
        proporciones = {}
        for nombre in ("CD-COAF-RCO-01", "CD-COAF-RCO-02"):
            imagenes = wb[nombre]._images
            assert len(imagenes) == 1
            proporciones[nombre] = imagenes[0].anchor.ext.cx / imagenes[0].anchor.ext.cy
        assert abs(proporciones["CD-COAF-RCO-01"] - 4 / 3) < 0.01
        assert abs(proporciones["CD-COAF-RCO-02"] - 3) < 0.01
    finally:
        wb.close()


# ── logos por empresa (decision D4) ──────────────────────────────────────

def test_hojas_domicem_llevan_croquis_mas_logos_y_vmo_solo_croquis(tmp_path, monkeypatch):
    """Criterio 4 — DOMICEM: cabecera + sello re-estampados en RCO y RFO
    (copy_worksheet los pierde igual que el croquis); la RCO ademas con su
    croquis. VMO: ningun logo-imagen. El alto de cada logo se deriva de la
    proporcion nativa del archivo, para no estamparlo deformado."""
    croquis_dir, logos_dir = _entorno_croquis(tmp_path, monkeypatch)
    _png(croquis_dir / "DOMICEM_MACAO_2.png", 600, 400)
    _png(logos_dir / "DOMICEM_cabecera.png", 740, 40)
    _png(logos_dir / "DOMICEM_sello.png", 200, 200)
    ruta = _generar_xlsx(tmp_path, monkeypatch, "DOMICEM", "MACAO 2")
    wb = openpyxl.load_workbook(ruta)
    try:
        ws_rco, ws_rfo = wb["CD-COAF-RCO-01"], wb["CD-COAF-RFO-01"]
        assert len(ws_rco._images) == 3    # croquis + cabecera + sello
        assert len(ws_rfo._images) == 2    # solo los logos

        # los logos van arriba (filas 1-2, 0-based 0-1); el croquis en el marco
        filas_ancla_rfo = sorted(im.anchor._from.row for im in ws_rfo._images)
        assert filas_ancla_rfo == [0, 1]
        assert max(im.anchor._from.row for im in ws_rco._images) >= EST_RCO_RFO_PRIMERA_FILA_MARCO - 1

        # proporcion del logo conservada (cabecera 740x40 = 18.5)
        cabecera = next(im for im in ws_rfo._images if im.anchor.ext.cx > im.anchor.ext.cy * 5)
        assert abs(cabecera.anchor.ext.cx / cabecera.anchor.ext.cy - 740 / 40) < 1.0
    finally:
        wb.close()


def test_hojas_vmo_sin_logos(tmp_path, monkeypatch):
    croquis_dir, logos_dir = _entorno_croquis(tmp_path, monkeypatch)
    _png(croquis_dir / "VMO_CEDIS.png", 600, 400)
    # aunque los archivos de logo EXISTAN, VMO no los lleva
    _png(logos_dir / "DOMICEM_cabecera.png", 740, 40)
    _png(logos_dir / "DOMICEM_sello.png", 200, 200)
    ruta = _generar_xlsx(tmp_path, monkeypatch, "VMO", "CEDIS")
    wb = openpyxl.load_workbook(ruta)
    try:
        assert len(wb["CD-COAF-RCO-01"]._images) == 1
        assert wb["CD-COAF-RFO-01"]._images == []
    finally:
        wb.close()


def test_logo_ausente_no_aborta_y_queda_en_el_log(tmp_path, monkeypatch, capsys):
    """Un logo es decorativo: si falta el archivo, la hoja sale sin el, se
    loguea, y el documento oficial no se cae por eso."""
    croquis_dir, _ = _entorno_croquis(tmp_path, monkeypatch)   # logos/ vacia
    _png(croquis_dir / "DOMICEM_MACAO_2.png", 600, 400)
    ruta = _generar_xlsx(tmp_path, monkeypatch, "DOMICEM", "MACAO 2")
    wb = openpyxl.load_workbook(ruta)
    try:
        assert len(wb["CD-COAF-RCO-01"]._images) == 1   # solo el croquis
        assert wb["CD-COAF-RFO-01"]._images == []
    finally:
        wb.close()
    assert "falta el logo" in capsys.readouterr().out


# ── guardas ruidosas ─────────────────────────────────────────────────────

def test_generacion_corta_si_la_plantilla_no_trae_las_hojas_rco_rfo():
    """Sin la hoja PLANTILLA el documento saldria sin sus RCO/RFO y
    pareceria completo sin estarlo — se corta con instrucciones."""
    wb = openpyxl.Workbook()
    wb.active.title = "CD-COAF-REO-01"
    req = SimpleNamespace(empresa="VMO", fase="CEDIS")
    with pytest.raises(HTTPException) as exc:
        core._est_agregar_hojas_rco_rfo(wb, req, [], {}, set())
    assert exc.value.detail["error"] == "plantilla_sin_hojas_rco_rfo"


def test_generacion_corta_si_una_plantilla_trae_imagenes(tmp_path):
    """Guarda del hallazgo D1 en el generador: si una hoja PLANTILLA llegara
    a traer imagenes, cada copia saldria sin ellas y nada avisaria — mejor
    cortar con un error explicito que entregar documentos incompletos."""
    from openpyxl.drawing.image import Image as XLImage
    ruta_png = _png(tmp_path / "logo.png", 50, 50)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.add_image(XLImage(ruta_png))
    with pytest.raises(HTTPException) as exc:
        core._est_afirmar_plantilla_sin_imagenes(ws, "CD-COAF-RCO-PLANTILLA")
    assert exc.value.detail["error"] == "plantilla_con_imagenes"


# ── criterio 8 — el PDF real sale entero, sin partir las hojas nuevas ────

@requiere_libreoffice
@pytest.mark.parametrize("empresa,fase", [("VMO", "CEDIS"), ("DOMICEM", "MACAO 2")])
def test_pdf_incluye_rco_y_rfo_en_una_pagina_cada_una(empresa, fase, tmp_path, monkeypatch):
    """Criterio 8 sobre MAS de una fase (MACAO 2 es la excepcion de
    geometria: RFO a 52 filas y escala 70): el PDF trae exactamente 5
    paginas — CEO, REO, RGO, RCO y RFO, cada una entera. Si una RCO/RFO
    saliera partida (la escala o el print_area mal), habria 6+ paginas; si
    no viajara al PDF, 4 o menos. Medir el PDF, no el .xlsx."""
    croquis_dir, logos_dir = _entorno_croquis(tmp_path, monkeypatch)
    _png(croquis_dir / f"{core._est_slug(empresa)}_{core._est_slug(fase)}.png", 800, 500)
    _png(logos_dir / "DOMICEM_cabecera.png", 740, 40)
    _png(logos_dir / "DOMICEM_sello.png", 200, 200)
    ruta = _generar_xlsx(tmp_path, monkeypatch, empresa, fase, con_pdf=True)
    ruta_pdf = ruta[:-len(".xlsx")] + ".pdf"
    assert os.path.exists(ruta_pdf), "la conversion a PDF no dejo el archivo"

    data = open(ruta_pdf, "rb").read()
    # \b excluye el nodo /Type/Pages: cuenta solo los objetos de pagina
    paginas = len(re.findall(rb"/Type\s*/Page\b", data))
    assert paginas == 5, f"{empresa}/{fase}: el PDF trae {paginas} paginas y se esperaban 5"
