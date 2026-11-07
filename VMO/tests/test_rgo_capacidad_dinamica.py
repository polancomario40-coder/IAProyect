"""
Verifica _est_redimensionar_rgo() — la hoja de generadores (RGO) de cada
producto ya no tiene un tope fijo de 40 facturas por periodo (MACAO 2 llega
a mas de 900 facturas/mes en un solo producto, muy por encima de ese
limite pensado originalmente para CEDIS). Cubre encoger (menos de 40),
exacto (40) y — desde el issue #18 — el camino paginado (mas de 40): la
hoja sale dividida en bloques de 40 folios por pagina, con encabezado y
firmas repetidos, salto de pagina explicito despues de la segunda firma,
contador continuo entre paginas y un unico TOTAL al final que suma un
rango por pagina. Con 40 o menos NO cambia nada: la hoja se encoge o queda
nativa igual que siempre, una sola pagina, sin saltos.

Verifica tanto la estructura (posiciones de datos/pie/encabezado, saltos,
sin fusiones de celda pisadas, sin contenido viejo sobreviviendo fuera de
los bloques) como el calculo real via LibreOffice.

Se salta la verificacion de calculo si LibreOffice no esta instalado.
"""
import os
import shutil
import subprocess
import sys

import openpyxl
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import (  # noqa: E402
    _est_redimensionar_rgo, _est_fila_dato_rgo, EST_RGO_FIRST_ROW,
    EST_RGO_CAPACIDAD_NATIVA, EST_RGO_PERIODO, EST_RGO_TOTAL_ROW,
    EST_RGO_PIE_FILAS, EST_DATA_DIR,
)

PLANTILLA_MAESTRA = os.path.join(EST_DATA_DIR, "plantilla_estimacion.xlsx")
FIRST = EST_RGO_FIRST_ROW           # 18
BLOQUE = EST_RGO_CAPACIDAD_NATIVA   # 40
PERIODO = EST_RGO_PERIODO           # 48


def _paginas(n):
    return -(-n // BLOQUE)


def _total_row_esperada(n):
    if n < BLOQUE:
        return FIRST + n                # camino historico: encoger
    if n == BLOQUE:
        return EST_RGO_TOTAL_ROW        # camino historico: nativa (58)
    # paginado: el TOTAL va despues del bloque COMPLETO de 40 de la ultima
    # pagina, aunque quede a medio llenar
    return FIRST + (_paginas(n) - 1) * PERIODO + BLOQUE


def _bloques(n):
    """Clasifica las filas de la hoja para n folios: devuelve
    (filas_de_dato_por_pagina, filas_de_pie, filas_de_encabezado_repetido).
    Todas absolutas. El encabezado original 14-17 no se incluye (nunca se
    toca); los encabezados repetidos si."""
    if n <= BLOQUE:
        tr = _total_row_esperada(n)
        datos = [list(range(FIRST, FIRST + max(n, 0)))] if n else [[]]
        # pie historico: TOTAL, blanco, firma1, firma2 (para n < 40 el
        # blanco es tr+1 y las firmas tr+2/tr+3; para n == 40 es 58-61)
        pie = list(range(tr, tr + 4))
        return datos, pie, []
    datos, pie, enc = [], [], []
    for k in range(_paginas(n)):
        d0 = FIRST + k * PERIODO
        datos.append(list(range(d0, d0 + BLOQUE)))
        pie += list(range(d0 + BLOQUE, d0 + BLOQUE + EST_RGO_PIE_FILAS))
        if k < _paginas(n) - 1:
            enc += list(range(d0 + BLOQUE + EST_RGO_PIE_FILAS,
                              d0 + BLOQUE + EST_RGO_PIE_FILAS + 4))
    return datos, pie, enc


def _hoja_rgo_con(n_filas):
    wb = openpyxl.load_workbook(PLANTILLA_MAESTRA, data_only=False)
    ws_plantilla = wb["CD-COAF-RGO-PLANTILLA"]
    ws = wb.copy_worksheet(ws_plantilla)
    ws.title = "PRUEBA"
    wb.remove(ws_plantilla)
    total_row = _est_redimensionar_rgo(ws, n_filas)
    for i in range(n_filas):
        # mismo calculo de fila que usa el generador real (issue #18): con
        # mas de 40 folios cada pagina corre PERIODO filas hacia abajo
        r = _est_fila_dato_rgo(i)
        ws.cell(r, 1).value = f"2026-07-{(i % 28) + 1:02d}"
        ws.cell(r, 2).value = f"DOC{i + 1}"
        ws.cell(r, 3).value = i + 1
        ws.cell(r, 7).value = 5
    return wb, ws, total_row


# los n > 40 ejercitan el camino paginado del issue #18 (antes ejercitaban
# el viejo camino de "crecer" la hoja continua, reemplazado por este)
CASOS = [1, 5, 39, 40, 41, 79, 80, 81, 175, 200, 937]


@pytest.mark.parametrize("n_filas", CASOS)
def test_sin_fusiones_pisadas(n_filas):
    wb, ws, _ = _hoja_rgo_con(n_filas)
    ranges = list(ws.merged_cells.ranges)
    for i in range(len(ranges)):
        for j in range(i + 1, len(ranges)):
            a, b = ranges[i], ranges[j]
            solapa = not (
                a.max_row < b.min_row or b.max_row < a.min_row
                or a.max_col < b.min_col or b.max_col < a.min_col
            )
            assert not solapa, f"n={n_filas}: fusiones pisadas {a} / {b}"


@pytest.mark.parametrize("n_filas", CASOS)
def test_pie_en_la_posicion_correcta_sin_basura(n_filas):
    """Reescrito para el issue #18: la intencion original (el pie va donde
    corresponde y no queda basura) sigue vigente, pero con n > 40 el TOTAL
    ya no va en 18+n con formula continua sino en el pie de la ultima
    pagina con un rango por pagina. La verificacion de basura ahora cubre
    el criterio 10 completo: toda celda A-K desde la fila 14 que no
    pertenezca a un bloque de datos, encabezado o pie debe estar en None,
    y dentro de los bloques de datos las filas sin folio tambien."""
    wb, ws, total_row = _hoja_rgo_con(n_filas)

    assert total_row == _total_row_esperada(n_filas)
    assert ws.cell(total_row, 1).value == "TOTAL:"
    if n_filas <= BLOQUE:
        assert ws.cell(total_row, 7).value == f"=SUM(G{FIRST}:G{FIRST + n_filas - 1})"
    else:
        rangos = ",".join(
            f"G{FIRST + k * PERIODO}:G{FIRST + k * PERIODO + BLOQUE - 1}"
            for k in range(_paginas(n_filas))
        )
        assert ws.cell(total_row, 7).value == f"=SUM({rangos})"
    assert ws.cell(total_row + 2, 1).value == "VMO CONCRETOS"
    assert ws.cell(total_row + 3, 1).value == "CONTRATISTA"

    datos, pie, enc = _bloques(n_filas)
    filas_dato = {r for pagina in datos for r in pagina}
    filas_con_folio = {_est_fila_dato_rgo(i) for i in range(n_filas)}
    filas_bloque = filas_dato | set(pie) | set(enc) | {14, 15, 16, 17}

    # margen despues del ultimo pie: no debe existir NADA mas abajo
    ultima_fila = max(filas_bloque) + 20
    for r in range(14, ultima_fila + 1):
        for c in range(1, 12):
            v = ws.cell(r, c).value
            if r in filas_con_folio:
                # dentro de una fila con folio, las columnas que las
                # facturas nunca tocan deben seguir vacias (bug real: los
                # restos de la firma sobrevivian en medio de los datos)
                if c in (4, 5, 6, 8, 9, 10, 11):
                    assert v is None, f"n={n_filas} fila {r} col {c} tiene basura: {v!r}"
            elif r in filas_bloque and r not in filas_dato:
                continue  # encabezados y pies llevan su propio contenido
            else:
                # fila de dato sin folio, o fila fuera de todo bloque
                assert v is None, f"n={n_filas} fila {r} col {c} tiene basura: {v!r}"


# ── issue #18 — layout paginado ──

@pytest.mark.parametrize("n_filas", [1, 39, 40, 41, 79, 80, 81, 175])
def test_layout_paginado(n_filas):
    """Posicion de datos, pies, encabezados y saltos para cada n. Con
    n <= 40 verifica que NO cambio nada: mismo layout historico, cero
    saltos de pagina, ningun encabezado repetido."""
    wb, ws, total_row = _hoja_rgo_con(n_filas)
    paginas = _paginas(n_filas)

    assert total_row == _total_row_esperada(n_filas)

    if n_filas <= BLOQUE:
        # camino historico intacto: una sola pagina, sin saltos, sin
        # encabezados repetidos (criterio 1)
        assert list(ws.row_breaks.brk) == []
        assert ws.cell(FIRST, 2).value == "DOC1"
        assert ws.cell(FIRST + n_filas - 1, 2).value == f"DOC{n_filas}"
        assert ws.cell(total_row + 2, 1).value == "VMO CONCRETOS"
        assert ws.cell(total_row + 3, 1).value == "CONTRATISTA"
        return

    # saltos: uno por pagina menos la ultima, DESPUES de la segunda firma
    saltos_esperados = [FIRST + k * PERIODO + BLOQUE + 3 for k in range(paginas - 1)]
    assert sorted(b.id for b in ws.row_breaks.brk) == saltos_esperados
    assert len(ws.row_breaks.brk) == paginas - 1

    for k in range(paginas):
        d0 = FIRST + k * PERIODO
        pie0 = d0 + BLOQUE
        # primer folio de la pagina (todas las paginas tienen al menos 1
        # folio: paginas = ceil(n/40))
        assert ws.cell(d0, 2).value == f"DOC{k * BLOQUE + 1}", f"pagina {k}"
        # firmas repetidas en TODAS las paginas
        assert ws.cell(pie0 + 2, 1).value == "VMO CONCRETOS", f"pagina {k}"
        assert ws.cell(pie0 + 3, 1).value == "CONTRATISTA", f"pagina {k}"
        if k < paginas - 1:
            # pie intermedio: sin rotulo TOTAL ni formula
            assert ws.cell(pie0, 1).value is None
            assert ws.cell(pie0, 7).value is None
            # encabezado repetido: etiquetas, valores, blanco, titulos
            enc0 = pie0 + EST_RGO_PIE_FILAS
            assert ws.cell(enc0, 1).value == "PARTIDA:"
            assert ws.cell(enc0, 8).value == "U. M."
            assert ws.cell(enc0 + 3, 1).value == "FECHA DE ENTREGA"
            assert ws.cell(enc0 + 3, 7).value == "CANTIDAD"
        else:
            assert pie0 == total_row
            assert ws.cell(pie0, 1).value == "TOTAL:"

    # el ultimo folio cae donde dice el contador de paginas
    assert ws.cell(_est_fila_dato_rgo(n_filas - 1), 2).value == f"DOC{n_filas}"


@pytest.mark.parametrize("n_filas", [41, 175])
def test_contador_continuo_sin_huecos(n_filas):
    """El contador de la columna 3 sigue corriendo entre paginas (41, 42,
    ...) sin reiniciar ni saltar: leidos en orden de fila son 1..n."""
    wb, ws, _ = _hoja_rgo_con(n_filas)
    datos, _, _ = _bloques(n_filas)
    leidos = []
    for pagina in datos:
        for r in pagina:
            v = ws.cell(r, 3).value
            if v is not None:
                leidos.append(v)
    assert leidos == list(range(1, n_filas + 1))


@pytest.mark.parametrize("n_filas,formula", [
    (41, "=SUM(G18:G57,G66:G105)"),
    (175, "=SUM(G18:G57,G66:G105,G114:G153,G162:G201,G210:G249)"),
])
def test_formula_total_un_rango_por_pagina(n_filas, formula):
    """Criterio 6: un rango por pagina, orden ascendente, sin coma
    colgante (no se reproduce el desorden de los documentos del cliente)."""
    wb, ws, total_row = _hoja_rgo_con(n_filas)
    assert ws.cell(total_row, 7).value == formula


def test_ultima_pagina_conserva_bloque_completo():
    """Criterio 5: con 41 folios el TOTAL no queda pegado al unico dato de
    la pagina 2 — el bloque de 40 se conserva completo (datos en 66, filas
    67-105 vacias, TOTAL en 106), igual que los documentos del cliente."""
    wb, ws, total_row = _hoja_rgo_con(41)
    assert ws.cell(66, 2).value == "DOC41"
    for r in range(67, 106):
        for c in range(1, 12):
            assert ws.cell(r, c).value is None, f"fila {r} col {c}"
    assert total_row == 106
    assert ws.cell(106, 1).value == "TOTAL:"
    assert ws.cell(108, 1).value == "VMO CONCRETOS"
    assert ws.cell(109, 1).value == "CONTRATISTA"


# ── issue #18 — integracion: REO-01 referencia el TOTAL de una hoja paginada ──

def test_reo01_referencia_el_total_de_hoja_paginada(tmp_path, monkeypatch):
    """Criterio 8, por el camino real (endpoint /generar contra una BD
    sintetica): con 45 facturas la hoja RGO sale paginada (2 paginas,
    TOTAL en 106) y la columna K de REO-01 apunta exactamente ahi."""
    import sqlite3
    import uuid
    from datetime import datetime
    from fastapi.testclient import TestClient
    import core
    import main

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
    conn.execute("INSERT INTO catalogo_estimacion VALUES ('VMO','CEDIS',1,'1','Producto Uno',100.0)")
    for i in range(45):
        conn.execute(
            "INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,cantidad,precio_unitario) "
            "VALUES (?,?,?,?,'Producto Uno',?,100.0)",
            (f"F{i:04d}", f"2026-06-{(i % 28) + 1:02d}", "VMO", "CEDIS", 10.0),
        )
    conn.commit()
    conn.close()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    monkeypatch.setattr(core, "EST_SOFFICE", None)  # sin PDF, no hace falta aqui
    token = f"test-token-{uuid.uuid4().hex}"
    core.active_tokens[token] = datetime.now()

    client = TestClient(main.app)
    res = client.post(
        "/api/estimaciones/generar",
        json={
            "empresa": "VMO", "fase": "CEDIS",
            "fecha_desde": "2026-06-01", "fecha_hasta": "2026-06-30",
            "numero_estimacion": "N01", "fecha_estimacion": "2026-08-28",
            "semana": 1,
            "productos": [{"clave": "1", "cantidad_proyecto": 1000, "acumulado_anterior_cantidad": 0}],
            "reasignaciones": {}, "serie": "principal",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text

    nombre = res.json()["download_url"].rsplit("/", 1)[-1]
    wb = openpyxl.load_workbook(os.path.join(str(tmp_path), nombre))
    ws_rgo = wb["CD-COAF-RGO-01"]
    ws_reo = wb["CD-COAF-REO-01"]

    # 45 folios -> 2 paginas, TOTAL en 18 + 48 + 40 = 106
    assert len(ws_rgo.row_breaks.brk) == 1
    assert ws_rgo.cell(106, 1).value == "TOTAL:"
    assert ws_rgo.cell(106, 7).value == "=SUM(G18:G57,G66:G105)"
    assert ws_reo.cell(17, 11).value == "='CD-COAF-RGO-01'!G106"


# ── calculo real con LibreOffice ──

def _soffice():
    encontrado = shutil.which("soffice") or shutil.which("soffice.exe")
    if encontrado:
        return encontrado
    for c in (r"C:\Program Files\LibreOffice\program\soffice.exe",
              r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
        if os.path.exists(c):
            return c
    return None


SOFFICE = _soffice()


def _recalcular_con_libreoffice(wb, tmp_path):
    entrada = tmp_path / "entrada"
    salida = tmp_path / "salida"
    entrada.mkdir()
    salida.mkdir()
    ruta = str(entrada / "prueba.xlsx")
    wb.save(ruta)

    resultado = subprocess.run(
        [SOFFICE, "--headless", "--calc", "--convert-to", "xlsx", "--outdir", str(salida), ruta],
        capture_output=True, text=True, timeout=60,
    )
    assert resultado.returncode == 0, resultado.stderr
    wb2 = openpyxl.load_workbook(str(salida / "prueba.xlsx"), data_only=True)
    return wb2["PRUEBA"]


@pytest.mark.skipif(SOFFICE is None, reason="LibreOffice no esta instalado")
@pytest.mark.parametrize("n_filas", [1, EST_RGO_CAPACIDAD_NATIVA - 1, EST_RGO_CAPACIDAD_NATIVA + 1, 937])
def test_calculo_real_recalculado(n_filas, tmp_path):
    # adaptado para el issue #18: con n > 40 total_row ya no es 18+n sino
    # el pie de la ultima pagina — la posicion esperada viene de
    # _total_row_esperada y el resto de las verificaciones no cambia
    wb, ws, total_row = _hoja_rgo_con(n_filas)
    assert total_row == _total_row_esperada(n_filas)

    ws2 = _recalcular_con_libreoffice(wb, tmp_path)
    assert ws2.cell(total_row, 7).value == pytest.approx(n_filas * 5)
    assert ws2.cell(total_row + 2, 1).value == "VMO CONCRETOS"
    assert ws2.cell(total_row + 3, 1).value == "CONTRATISTA"


@pytest.mark.skipif(SOFFICE is None, reason="LibreOffice no esta instalado")
def test_calculo_real_recalculado_paginado(tmp_path):
    """Criterio 7: el TOTAL de una hoja de 175 folios (5 paginas, formula
    con un rango por pagina) recalculado por LibreOffice da exactamente la
    suma real de las cantidades."""
    wb, ws, total_row = _hoja_rgo_con(175)
    assert total_row == 250

    ws2 = _recalcular_con_libreoffice(wb, tmp_path)
    assert ws2.cell(250, 7).value == pytest.approx(175 * 5)
    assert ws2.cell(252, 1).value == "VMO CONCRETOS"
    assert ws2.cell(253, 1).value == "CONTRATISTA"
