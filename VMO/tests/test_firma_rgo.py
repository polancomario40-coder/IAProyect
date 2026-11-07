"""
Cubre issue #33 — el bloque de firma de las hojas RGO salia vacio en 7 de
las 9 fases y cruzado en una octava.

La hoja CD-COAF-RGO-PLANTILLA trae el bloque cableado a la fila 37/38 de
CD-COAF-REO-01 (D60 ='CD-COAF-REO-01'!E37, D61 =...!$E$38, H60 formula
matricial =...!K37:N37, H61 =...!$K$38), pero el bloque de firma de REO-01
solo esta en 37/38 en 2 de las 9 fases: cada plantilla tiene distinta
cantidad de renglones de producto, asi que la firma quedo a distinta
altura. Medido recalculando con LibreOffice antes del arreglo, el
documento entregado salia asi:

    DOMICEM/CAVERNAS                 nombre=0  cargo='DULCE MIRJAM SALDIVAR BAUTISTA'  (cruzada)
    DOMICEM/MACAO 2                  correcta
    DOMICEM/PATIO DE MANIOBRAS-TRB   nombre=0  cargo=0
    DOMICEM/VIVIENDAS                nombre=0  cargo=0
    VMO/CANCHAS                      nombre=0  cargo=0
    VMO/CEDIS                        correcta
    VMO/EXTERIORES                   nombre=0  cargo=0
    VMO/PATIO DE MANIOBRAS-TRA       nombre=0  cargo=0
    VMO/PODIUM-1-2-3                 nombre=0  cargo=0

(no salia en blanco sino con un "0" en el renglon del nombre y con
" $   - " en el del cargo — esas celdas llevan formato contable, asi que
una referencia a celda vacia se imprime como monto cero.) La firma de
gerencia de obra (columna H) estaba rota exactamente igual que la del
analista (columna D).

El arreglo escribe nombre y cargo como VALOR al generar, leyendolos de
REO-01 en la fila donde realmente estan — fila detectada leyendo la hoja
(rotulo "CONTRATISTA" en la columna B), no cableada en un diccionario
fase->fila que se desincronizaria en silencio la proxima vez que alguien
reconstruya una plantilla.

Correr con: python -m pytest tests/test_firma_rgo.py -v
"""
import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime

import openpyxl
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import main  # noqa: E402 (solo para main.app)
from core import (  # noqa: E402
    EST_PLANTILLAS, EST_DATA_DIR, EST_RGO_FIRST_ROW, EST_RGO_CAPACIDAD_NATIVA,
    EST_RGO_PERIODO, EST_FIRMA_COLS, _est_filas_firma_reo, _est_escribir_firma_rgo,
)

FASES = sorted(EST_PLANTILLAS.keys())

# capturado al importar: _generar_xlsx() monkeypatchea core.EST_SOFFICE a
# None para saltarse la conversion a PDF, que no aporta nada a lo que se
# verifica aca — el recalculo de este archivo usa el binario real igual
SOFFICE = core.EST_SOFFICE
requiere_libreoffice = pytest.mark.skipif(
    SOFFICE is None,
    reason="LibreOffice no esta instalado — se salta la verificacion con recalculo real",
)

COL_ANALISTA_RGO = EST_FIRMA_COLS[0][1]   # D
COL_GERENCIA_RGO = EST_FIRMA_COLS[1][1]   # H


# ── helpers ───────────────────────────────────────────────────────────────

def _bd_sintetica(tmp_path, monkeypatch, empresa, fase, facturas):
    """BD sqlite minima con un solo producto de catalogo (cabe en la
    plantilla de las 9 fases, la mas chica soporta 3) — mismo patron que
    tests/test_generar_pdf_estimacion.py::_bd_sintetica."""
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
    conn.execute(
        "INSERT INTO catalogo_estimacion VALUES (?,?,1,'1','Producto Uno',100.0)", (empresa, fase)
    )
    for f in facturas:
        conn.execute(
            "INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,cantidad,precio_unitario) "
            "VALUES (?,?,?,?,'Producto Uno',?,100.0)",
            (f["id_documento"], f["fecha"], empresa, fase, f["cantidad"]),
        )
    conn.commit()
    conn.close()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))

    token = f"test-token-{uuid.uuid4().hex}"
    core.active_tokens[token] = datetime.now()
    return token


def _generar_xlsx(tmp_path, monkeypatch, empresa, fase, n_facturas=1, con_pdf=False):
    """Genera la estimacion end-to-end por la ruta HTTP real y devuelve la
    ruta del .xlsx. Por defecto apaga la conversion a PDF: no aporta nada a
    lo que se verifica aca y cuesta ~2s de LibreOffice por fase."""
    facturas = [
        {"id_documento": f"F{i + 1:03d}", "fecha": f"2026-06-{(i % 28) + 1:02d}", "cantidad": 10}
        for i in range(n_facturas)
    ]
    token = _bd_sintetica(tmp_path, monkeypatch, empresa, fase, facturas)
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    if not con_pdf:
        monkeypatch.setattr(core, "EST_SOFFICE", None)

    client = TestClient(main.app)
    res = client.post(
        "/api/estimaciones/generar",
        json={
            "empresa": empresa, "fase": fase,
            "fecha_desde": "2026-06-01", "fecha_hasta": "2026-06-30",
            "numero_estimacion": "N01", "fecha_estimacion": "2026-08-24", "semana": 1,
            "productos": [{"clave": "1", "cantidad_proyecto": 10000, "acumulado_anterior_cantidad": 0}],
            "reasignaciones": {}, "serie": "principal",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    nombre = res.json()["download_url"].rsplit("/", 1)[-1]
    return os.path.join(str(tmp_path), nombre)


def _firma_esperada(empresa, fase):
    """(nombre_analista, cargo_analista, nombre_gerencia, cargo_gerencia)
    leidos de la plantilla en disco de esa fase, en la fila real del bloque
    de firma."""
    info = EST_PLANTILLAS[(empresa, fase)]
    wb = openpyxl.load_workbook(os.path.join(EST_DATA_DIR, info["archivo"]), data_only=False)
    ws = wb["CD-COAF-REO-01"]
    fila_nombre, fila_cargo = _est_filas_firma_reo(ws)
    valores = tuple(
        ws.cell(fila, col_reo).value.strip()
        for col_reo, _ in EST_FIRMA_COLS
        for fila in (fila_nombre, fila_cargo)
    )
    wb.close()
    return valores


def _filas_de_firma(ws):
    """Filas (nombre, cargo) de cada bloque de firma presente en una hoja
    RGO ya generada, localizadas por el rotulo CONTRATISTA de la columna A."""
    filas = [r for r in range(1, ws.max_row + 1) if ws.cell(r, 1).value == "CONTRATISTA"]
    return [(r - 1, r) for r in filas]


def _hoja_rgo(ruta_xlsx, data_only=False):
    wb = openpyxl.load_workbook(ruta_xlsx, data_only=data_only)
    return wb, wb["CD-COAF-RGO-01"]


# ── el test que faltaba: las 9 fases, sobre el workbook generado ──────────

@pytest.mark.parametrize("empresa,fase", FASES)
def test_firma_de_la_rgo_no_queda_vacia_en_ninguna_fase(empresa, fase, tmp_path, monkeypatch):
    """Issue #33 — abre el .xlsx generado de cada una de las 9 fases y
    verifica que las 4 celdas del bloque de firma (nombre y cargo del
    analista, nombre y cargo de gerencia de obra) traen el texto real de la
    plantilla de esa fase. Antes del arreglo, 7 de las 9 traian la formula
    cableada a REO-01!E37/E38, que resolvia a 0."""
    ruta = _generar_xlsx(tmp_path, monkeypatch, empresa, fase)
    wb, ws = _hoja_rgo(ruta)

    bloques = _filas_de_firma(ws)
    assert len(bloques) == 1, f"{empresa}/{fase}: se esperaba 1 bloque de firma, hay {len(bloques)}"
    fila_nombre, fila_cargo = bloques[0]

    obtenido = (
        ws.cell(fila_nombre, COL_ANALISTA_RGO).value,
        ws.cell(fila_cargo, COL_ANALISTA_RGO).value,
        ws.cell(fila_nombre, COL_GERENCIA_RGO).value,
        ws.cell(fila_cargo, COL_GERENCIA_RGO).value,
    )
    for celda, valor in zip(("nombre analista", "cargo analista",
                             "nombre gerencia", "cargo gerencia"), obtenido):
        assert isinstance(valor, str) and valor.strip(), (
            f"{empresa}/{fase}: {celda} quedo en {valor!r} — el bloque de firma "
            f"sale vacio en el documento entregado"
        )
        assert not valor.startswith("="), (
            f"{empresa}/{fase}: {celda} sigue siendo una formula ({valor!r}) — "
            f"tiene que quedar escrito como valor"
        )

    assert obtenido == _firma_esperada(empresa, fase), (
        f"{empresa}/{fase}: la firma no coincide con la de su plantilla"
    )
    wb.close()


@pytest.mark.parametrize("empresa,fase", FASES)
def test_firma_de_la_rgo_no_deja_restos_de_la_formula_matricial(empresa, fase, tmp_path, monkeypatch):
    """La firma de gerencia era una formula matricial sobre H60:K60 que
    dejaba un 0 cacheado en I, J y K. Al pasar a valor escalar esas 3
    celdas tienen que quedar limpias, o el documento sale con tres ceros
    sueltos al lado del nombre del ingeniero."""
    ruta = _generar_xlsx(tmp_path, monkeypatch, empresa, fase)
    wb, ws = _hoja_rgo(ruta)
    fila_nombre, _ = _filas_de_firma(ws)[0]
    for col in range(COL_GERENCIA_RGO + 1, COL_GERENCIA_RGO + 4):
        assert ws.cell(fila_nombre, col).value is None, (
            f"{empresa}/{fase}: quedo basura de la formula matricial en "
            f"{openpyxl.utils.get_column_letter(col)}{fila_nombre}"
        )
    wb.close()


@requiere_libreoffice
@pytest.mark.parametrize("empresa,fase", FASES)
def test_firma_recalculada_con_libreoffice_no_da_cero(empresa, fase, tmp_path, monkeypatch):
    """Mismo criterio pero sobre el libro RECALCULADO — es la forma en que
    se manifestaba el bug (openpyxl mostraba la formula, el 0 solo aparecia
    al recalcular, que es lo que hace LibreOffice al exportar el PDF y
    Excel al abrirlo). Se salta si LibreOffice no esta instalado, mismo
    patron que tests/test_calculo_estimacion.py."""
    ruta = _generar_xlsx(tmp_path, monkeypatch, empresa, fase)

    salida = tmp_path / "calc"
    salida.mkdir(exist_ok=True)
    resultado = subprocess.run(
        [SOFFICE, "--headless", "--calc", "--convert-to", "xlsx",
         "--outdir", str(salida), ruta],
        capture_output=True, text=True, timeout=120,
    )
    assert resultado.returncode == 0, f"LibreOffice fallo: {resultado.stderr}"
    ruta_calc = salida / os.path.basename(ruta)
    assert ruta_calc.exists()

    wb, ws = _hoja_rgo(str(ruta_calc), data_only=True)
    fila_nombre, fila_cargo = _filas_de_firma(ws)[0]
    for col, quien in ((COL_ANALISTA_RGO, "analista"), (COL_GERENCIA_RGO, "gerencia")):
        for fila, que in ((fila_nombre, "nombre"), (fila_cargo, "cargo")):
            valor = ws.cell(fila, col).value
            assert isinstance(valor, str) and valor.strip(), (
                f"{empresa}/{fase}: {que} de {quien} recalculado da {valor!r} "
                f"(el bug del issue #33 daba 0)"
            )
    wb.close()


def test_firma_se_repite_en_todas_las_paginas_del_camino_paginado(tmp_path, monkeypatch):
    """Con mas de 40 folios la hoja sale paginada (issue #18) y el pie —
    firma incluida — se repite en cada pagina. El arreglo se aplica sobre
    CD-COAF-RGO-PLANTILLA antes de clonarla, asi que tiene que viajar a
    todas las paginas por el mismo snapshot del pie que ya existia."""
    empresa, fase = "VMO", "PATIO DE MANIOBRAS-TRA"   # una de las fases rotas
    n = EST_RGO_CAPACIDAD_NATIVA + 5                  # 45 folios -> 2 paginas
    ruta = _generar_xlsx(tmp_path, monkeypatch, empresa, fase, n_facturas=n)
    wb, ws = _hoja_rgo(ruta)

    bloques = _filas_de_firma(ws)
    assert len(bloques) == 2, f"se esperaban 2 bloques de firma (2 paginas), hay {len(bloques)}"
    esperado = _firma_esperada(empresa, fase)
    for i, (fila_nombre, fila_cargo) in enumerate(bloques):
        obtenido = (
            ws.cell(fila_nombre, COL_ANALISTA_RGO).value,
            ws.cell(fila_cargo, COL_ANALISTA_RGO).value,
            ws.cell(fila_nombre, COL_GERENCIA_RGO).value,
            ws.cell(fila_cargo, COL_GERENCIA_RGO).value,
        )
        assert obtenido == esperado, f"pagina {i + 1}: firma incorrecta {obtenido!r}"

    # las firmas caen donde el paginado las pone: pie de cada pagina
    assert bloques[0][0] == EST_RGO_FIRST_ROW + EST_RGO_CAPACIDAD_NATIVA + 2
    assert bloques[1][0] == EST_RGO_FIRST_ROW + EST_RGO_PERIODO + EST_RGO_CAPACIDAD_NATIVA + 2
    wb.close()


# ── deteccion de la fila del bloque de firma ──────────────────────────────

@pytest.mark.parametrize("empresa,fase", FASES)
def test_el_bloque_de_firma_es_detectable_en_las_9_plantillas(empresa, fase):
    """Guardia de sincronizacion: si alguien reconstruye una plantilla y el
    bloque de firma deja de ser localizable (o el nombre/cargo quedan
    vacios), esto lo detecta aca en vez de en un documento ya entregado."""
    info = EST_PLANTILLAS[(empresa, fase)]
    wb = openpyxl.load_workbook(os.path.join(EST_DATA_DIR, info["archivo"]), data_only=False)
    ws = wb["CD-COAF-REO-01"]
    fila_nombre, fila_cargo = _est_filas_firma_reo(ws)
    assert fila_cargo == fila_nombre + 1
    for col_reo, _ in EST_FIRMA_COLS:
        for fila in (fila_nombre, fila_cargo):
            valor = ws.cell(fila, col_reo).value
            assert isinstance(valor, str) and valor.strip() and not valor.startswith("="), (
                f"{empresa}/{fase}: REO-01 fila {fila} col {col_reo} trae {valor!r}"
            )
    wb.close()


def test_la_fila_de_firma_no_es_la_misma_en_todas_las_fases():
    """Deja constancia de la causa raiz: cablear la fila 37/38 (lo que hace
    la plantilla de la RGO) solo acierta en 2 de las 9 fases."""
    filas = {}
    for empresa, fase in FASES:
        info = EST_PLANTILLAS[(empresa, fase)]
        wb = openpyxl.load_workbook(os.path.join(EST_DATA_DIR, info["archivo"]), data_only=False)
        filas[(empresa, fase)] = _est_filas_firma_reo(wb["CD-COAF-REO-01"])[0]
        wb.close()
    assert len(set(filas.values())) > 1, "si esto falla, el bug ya no puede reproducirse"
    en_37 = [k for k, v in filas.items() if v == 37]
    assert len(en_37) == 2, f"cambio la disposicion de las plantillas: {filas}"


def test_deteccion_falla_ruidosa_si_no_hay_ancla(tmp_path):
    """Sin el rotulo CONTRATISTA no se adivina una fila: se corta la
    generacion con un error explicito. Un documento oficial sale firmado o
    no sale."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["B10"] = "OTRA COSA"
    with pytest.raises(HTTPException) as exc:
        _est_filas_firma_reo(ws)
    assert exc.value.detail["error"] == "bloque_de_firma_no_encontrado"


def test_deteccion_falla_ruidosa_si_el_ancla_esta_duplicada():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["B10"] = "CONTRATISTA"
    ws["B20"] = "contratista"
    with pytest.raises(HTTPException) as exc:
        _est_filas_firma_reo(ws)
    assert exc.value.detail["error"] == "bloque_de_firma_no_encontrado"


def test_escribir_firma_falla_ruidosa_si_el_nombre_esta_vacio():
    """El caso exacto de CAVERNAS/TRB/etc. antes del arreglo, pero ahora en
    la fila detectada: si ahi no hay texto, no se genera un documento con
    la firma en blanco — se corta."""
    wb = openpyxl.Workbook()
    ws_reo = wb.active
    ws_reo.title = "REO"
    ws_reo["B30"] = "CONTRATISTA"       # fila 29 = nombre, 30 = cargo
    ws_reo["E30"] = "ANALISTA DE ESTIMACIONES"
    ws_reo["K29"] = "ING. FULANO"
    ws_reo["K30"] = "GERENCIA DE OBRA"
    # E29 (nombre del analista) queda vacia a proposito
    ws_rgo = wb.create_sheet("RGO")
    with pytest.raises(HTTPException) as exc:
        _est_escribir_firma_rgo(ws_rgo, ws_reo, "DOMICEM S.A")
    assert exc.value.detail["error"] == "bloque_de_firma_vacio"
    assert "E29" in exc.value.detail["detalle"]


# ── issue #35 — el contratista de la RGO ─────────────────────────────────
#
# La celda A60 (fusionada A60:B60, encima del rotulo fijo "CONTRATISTA" de
# A61) traia el literal cableado "VMO CONCRETOS" en las 10 plantillas,
# incluidas las 4 de DOMICEM: toda estimacion de DOMICEM salia nombrando a
# la empresa equivocada como contratista en cada hoja RGO, mientras el
# resumen de esa misma estimacion decia DOMICEM S.A. Verificado contra los
# documentos reales del cliente: sus estimaciones DOMICEM dicen
# "DOMICEM S.A" ahi, asi que era error nuestro y no una convencion suya.

@pytest.mark.parametrize("empresa,fase", FASES)
def test_el_contratista_de_la_rgo_es_el_de_la_empresa(empresa, fase, tmp_path, monkeypatch):
    """El caso que dolia: en DOMICEM tiene que decir DOMICEM, no el literal
    'VMO CONCRETOS' que traen cableado las 10 plantillas."""
    ruta = _generar_xlsx(tmp_path, monkeypatch, empresa, fase)
    wb, ws = _hoja_rgo(ruta)
    try:
        fila_nombre, _ = _filas_de_firma(ws)[0]
        assert ws.cell(fila_nombre, 1).value == core.EST_CONTRATISTA[empresa]
        if empresa == "DOMICEM":
            assert ws.cell(fila_nombre, 1).value != "VMO CONCRETOS"
            assert "DOMICEM" in ws.cell(fila_nombre, 1).value
    finally:
        wb.close()


@pytest.mark.parametrize("empresa,fase", FASES)
def test_el_contratista_de_la_rgo_coincide_con_el_del_resumen(empresa, fase, tmp_path, monkeypatch):
    """RGO y REO-01 no pueden divergir: las dos salen de EST_CONTRATISTA."""
    ruta = _generar_xlsx(tmp_path, monkeypatch, empresa, fase)
    wb = openpyxl.load_workbook(ruta)
    try:
        ws_rgo = wb["CD-COAF-RGO-01"]
        fila_nombre, _ = _filas_de_firma(ws_rgo)[0]
        assert ws_rgo.cell(fila_nombre, 1).value == wb["CD-COAF-REO-01"]["B9"].value
    finally:
        wb.close()


@pytest.mark.parametrize("empresa,fase", FASES)
def test_el_rotulo_contratista_de_la_rgo_no_se_toca(empresa, fase, tmp_path, monkeypatch):
    """La fila de abajo es el rotulo fijo de la plantilla, no un cargo que
    haya que escribir. Si se pisara, la hoja quedaria sin decir que ese
    nombre es el del contratista."""
    ruta = _generar_xlsx(tmp_path, monkeypatch, empresa, fase)
    wb, ws = _hoja_rgo(ruta)
    try:
        _, fila_cargo = _filas_de_firma(ws)[0]
        assert ws.cell(fila_cargo, 1).value == "CONTRATISTA"
    finally:
        wb.close()


def test_el_contratista_siempre_lleva_sa():
    """Decision del dueno del proyecto (2026-08-31): cuando la celda va al
    contratista, siempre tiene que decir S.A. Fija la constante para que
    nadie la acorte despues sin darse cuenta de que sale en el documento."""
    for empresa, texto in core.EST_CONTRATISTA.items():
        assert texto.rstrip(".").endswith("S.A"), f"{empresa} -> {texto!r}"


def test_el_contratista_se_repite_en_todas_las_paginas_del_camino_paginado(tmp_path, monkeypatch):
    """Con mas de 40 folios el pie se replica por pagina; el contratista
    tiene que viajar en todas, igual que las otras dos firmas."""
    ruta = _generar_xlsx(tmp_path, monkeypatch, "VMO", "PATIO DE MANIOBRAS-TRA", n_facturas=45)
    wb, ws = _hoja_rgo(ruta)
    try:
        bloques = _filas_de_firma(ws)
        assert len(bloques) >= 2, f"se esperaban >=2 bloques de firma y hay {len(bloques)}"
        for fila_nombre, _ in bloques:
            assert ws.cell(fila_nombre, 1).value == core.EST_CONTRATISTA["VMO"]
    finally:
        wb.close()


def test_escribir_firma_falla_ruidosa_si_el_contratista_esta_vacio():
    """Sin contratista no se genera un documento con el literal cableado de
    la plantilla — se corta, igual que con el nombre del analista."""
    wb = openpyxl.Workbook()
    ws_reo = wb.active
    ws_reo.title = "REO"
    ws_reo["B30"] = "CONTRATISTA"       # fila 29 = nombre, 30 = cargo
    ws_reo["E29"] = "FULANA DE TAL"
    ws_reo["E30"] = "ANALISTA DE ESTIMACIONES"
    ws_reo["K29"] = "ING. FULANO"
    ws_reo["K30"] = "GERENCIA DE OBRA"
    ws_rgo = wb.create_sheet("RGO")
    with pytest.raises(HTTPException) as exc:
        _est_escribir_firma_rgo(ws_rgo, ws_reo, "   ")
    assert exc.value.detail["error"] == "contratista_vacio"
