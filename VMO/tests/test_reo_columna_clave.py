"""
La columna A de CD-COAF-REO-01 (rotulada CLAVE) lleva la CLAVE del producto,
no su posicion en la hoja.

El generador escribia ahi c["orden"]. Coincide con c["clave"] en 70 de las 72
filas del catalogo real, por eso el bug vivio meses sin que nadie lo notara:
la unica fase donde se separan es VMO/PATIO DE MANIOBRAS-TRA, que tiene las
claves 2 y 3 cruzadas (orden 2 -> clave '3', orden 3 -> clave '2'). Los dos
documentos reales del cliente de esa fase traen 1,3,2,4 en esa columna.

El sintoma no era solo un rotulo mal en el REO: la clave sale hoy por dos
caminos distintos y en TRA se contradecian dentro del mismo documento.

    RGO-XX!B15  -> VALOR,   escrito como c["clave"]
    RCO-XX!B15  -> FORMULA, a la columna A de la fila del REO (issue #27)
    RFO-XX!B15  -> FORMULA, idem

O sea que la RGO-03 decia "3" y su RCO-03 hermana resolvia a 2.

Estos tests custodian las dos mitades del arreglo:

  1. el VALOR de la columna A pasa a ser la clave, y
  2. el CALCULO DE LA FILA sigue siendo por orden.

La (2) importa tanto como la (1): si alguien "termina de corregir" el bug
cambiando tambien `fila = EST_REO_FIRST_ROW + (c["orden"] - 1)`, en TRA se
intercambian dos renglones ENTEROS del REO (concepto, P.U., acumulados) y eso
si mueve plata. Por eso se afirma tambien que cada fila conserva su concepto.

La BD es sintetica: reproduce el cruce de TRA, no lee el catalogo real (misma
regla que el resto de la suite — los tests no tocan carpetas de datos). El
dato de produccion se midio a mano y quedo en el issue.

Correr con: python -m pytest tests/test_reo_columna_clave.py -v
"""
import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime

import openpyxl
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import main  # noqa: E402 (solo para main.app)
from core import EST_REO_FIRST_ROW  # noqa: E402

EMPRESA = "VMO"
FASE = "PATIO DE MANIOBRAS-TRA"

# (orden, clave, descripcion) — el cruce real de TRA: la clave 3 va SEGUNDA y
# la clave 2 TERCERA, igual que en los dos documentos del cliente de esta fase
CATALOGO_TRA = [
    (1, "1", "Producto de la clave uno"),
    (2, "3", "Producto de la clave tres"),
    (3, "2", "Producto de la clave dos"),
    (4, "4", "Producto de la clave cuatro"),
]
CLAVES = [clave for _, clave, _ in CATALOGO_TRA]
DESC_POR_CLAVE = {clave: desc for _, clave, desc in CATALOGO_TRA}
# lo que trae la columna A del documento real del cliente
COLUMNA_A_DEL_CLIENTE = [1, 3, 2, 4]

SOFFICE = core.EST_SOFFICE
requiere_libreoffice = pytest.mark.skipif(
    SOFFICE is None,
    reason="LibreOffice no esta instalado — se salta la verificacion con recalculo real",
)


# ── helpers ───────────────────────────────────────────────────────────────

def _entorno_croquis(tmp_path, monkeypatch):
    """Croquis y logos VACIOS y aislados — nunca se toca estimaciones/data/.
    Sin croquis archivado la RCO sale con el marco vacio y el documento se
    genera igual, que es todo lo que estos tests necesitan."""
    croquis_dir = tmp_path / "croquis"
    logos_dir = croquis_dir / "logos"
    logos_dir.mkdir(parents=True)
    monkeypatch.setattr(core, "EST_CROQUIS_DIR", str(croquis_dir))
    monkeypatch.setattr(core, "EST_LOGOS_DIR", str(logos_dir))


def _bd_tra(tmp_path, monkeypatch):
    """Catalogo de TRA con el cruce orden != clave, y una factura por clave
    (todas con entregas, asi salen las 4 ternas RGO/RCO/RFO)."""
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
    for orden, clave, desc in CATALOGO_TRA:
        conn.execute("INSERT INTO catalogo_estimacion VALUES (?,?,?,?,?,100.0)",
                     (EMPRESA, FASE, orden, clave, desc))
    for i, (_, clave, desc) in enumerate(CATALOGO_TRA):
        conn.execute(
            "INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,cantidad,precio_unitario) "
            "VALUES (?,?,?,?,?,?,100.0)",
            (f"F{i + 1:03d}", f"2026-06-{i + 1:02d}", EMPRESA, FASE, desc, 10),
        )
    conn.commit()
    conn.close()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))

    token = f"test-token-{uuid.uuid4().hex}"
    core.active_tokens[token] = datetime.now()
    return token


def _generar(tmp_path, monkeypatch):
    """Genera la estimacion de TRA end-to-end por la ruta HTTP real."""
    _entorno_croquis(tmp_path, monkeypatch)
    token = _bd_tra(tmp_path, monkeypatch)
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    monkeypatch.setattr(core, "EST_SOFFICE", None)   # el PDF no aporta aca

    client = TestClient(main.app)
    res = client.post(
        "/api/estimaciones/generar",
        json={
            "empresa": EMPRESA, "fase": FASE,
            "fecha_desde": "2026-06-01", "fecha_hasta": "2026-06-30",
            "numero_estimacion": "N01", "fecha_estimacion": "2026-08-24", "semana": 1,
            "productos": [
                {"clave": c, "cantidad_proyecto": 10000, "acumulado_anterior_cantidad": 0}
                for c in CLAVES
            ],
            "reasignaciones": {}, "serie": "principal",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        assert res.status_code == 200, res.text
    finally:
        core.active_tokens.pop(token, None)
    nombre = res.json()["download_url"].rsplit("/", 1)[-1]
    return os.path.join(str(tmp_path), nombre)


def _fila_apuntada(formula):
    """Devuelve el numero de fila al que apunta una formula a la columna A de
    REO-01. Falla ruidoso si la formula no es la esperada, en vez de devolver
    None y hacer pasar la asercion de arriba."""
    assert isinstance(formula, str) and "REO-01" in formula and "$A$" in formula, \
        f"B15 no es la formula a la columna A del REO: {formula!r}"
    return int(formula.split("$A$")[1])


# ── el arreglo ────────────────────────────────────────────────────────────

def test_reo_columna_a_lleva_la_clave_no_el_orden(tmp_path, monkeypatch):
    """La columna A sale 1,3,2,4 — la CLAVE, exactamente como el documento
    real del cliente. Con el bug salia 1,2,3,4 (la posicion)."""
    wb = openpyxl.load_workbook(_generar(tmp_path, monkeypatch))
    try:
        reo = wb["CD-COAF-REO-01"]
        columna_a = [reo.cell(EST_REO_FIRST_ROW + i, 1).value for i in range(len(CATALOGO_TRA))]
        assert columna_a == COLUMNA_A_DEL_CLIENTE, (
            f"columna A del REO: {columna_a}, se esperaba {COLUMNA_A_DEL_CLIENTE} "
            f"(la clave). Si salio [1, 2, 3, 4] volvio el bug del orden."
        )
        # enteros, no strings — asi los traen los documentos del cliente
        assert all(isinstance(v, int) for v in columna_a), columna_a
    finally:
        wb.close()


def test_la_fila_de_cada_producto_la_sigue_dando_el_orden(tmp_path, monkeypatch):
    """La otra mitad del arreglo: cambio el VALOR de la celda, NO el calculo
    de la fila. Cada renglon conserva su concepto en la posicion que le da el
    orden. Si alguien "corrigiera" tambien `fila` usando la clave, en TRA se
    intercambiarian dos renglones enteros (concepto, P.U., acumulados)."""
    wb = openpyxl.load_workbook(_generar(tmp_path, monkeypatch))
    try:
        reo = wb["CD-COAF-REO-01"]
        for orden, clave, desc in CATALOGO_TRA:
            fila = EST_REO_FIRST_ROW + (orden - 1)
            assert reo.cell(fila, 2).value == desc, (
                f"fila {fila} (orden {orden}): concepto {reo.cell(fila, 2).value!r}, "
                f"se esperaba el de la clave {clave}"
            )
            assert reo.cell(fila, 1).value == int(clave)
    finally:
        wb.close()


def test_las_tres_hojas_de_una_clave_no_se_contradicen(tmp_path, monkeypatch):
    """RGO (valor) y RCO/RFO (formula a la columna A) tienen que decir la
    misma clave. Se verifica que la formula apunte a la FILA correcta, no que
    el texto de la formula sea igual a algo: comparar strings de formula
    pasaria aunque la fila apuntada estuviera mal."""
    wb = openpyxl.load_workbook(_generar(tmp_path, monkeypatch))
    try:
        reo = wb["CD-COAF-REO-01"]
        for clave in CLAVES:
            sufijo = f"-{int(clave):02d}"
            rgo = wb[f"CD-COAF-RGO{sufijo}"]
            assert str(rgo["B15"].value) == clave, (
                f"RGO{sufijo}!B15 = {rgo['B15'].value!r}, se esperaba {clave!r}"
            )
            for familia in ("RCO", "RFO"):
                ws = wb[f"CD-COAF-{familia}{sufijo}"]
                fila = _fila_apuntada(ws["B15"].value)
                assert reo.cell(fila, 1).value == int(clave), (
                    f"{familia}{sufijo}!B15 apunta a A{fila}, que vale "
                    f"{reo.cell(fila, 1).value!r} — contradice a su RGO ({clave})"
                )
                # y la fila apuntada es de verdad la de este producto
                assert reo.cell(fila, 2).value == DESC_POR_CLAVE[clave]
    finally:
        wb.close()


@requiere_libreoffice
def test_las_tres_hojas_coinciden_recalculadas_con_libreoffice(tmp_path, monkeypatch):
    """Lo anterior lee el TEXTO de la formula; esto lee su RESULTADO, que es
    lo que ve quien abre el documento. Se recalcula con LibreOffice — el
    mismo camino que usa la exportacion a PDF."""
    ruta = _generar(tmp_path, monkeypatch)
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
        for clave in CLAVES:
            sufijo = f"-{int(clave):02d}"
            valores = {
                familia: wb[f"CD-COAF-{familia}{sufijo}"]["B15"].value
                for familia in ("RGO", "RCO", "RFO")
            }
            # la RGO lo escribe como texto y las otras dos lo resuelven a
            # numero: se comparan normalizados a string
            normalizados = {f: str(v) for f, v in valores.items()}
            assert set(normalizados.values()) == {clave}, (
                f"clave {clave}: las tres hojas no coinciden -> {valores}"
            )
            for familia in ("RCO", "RFO"):
                assert wb[f"CD-COAF-{familia}{sufijo}"]["C15"].value == DESC_POR_CLAVE[clave]
    finally:
        wb.close()


def test_partida_a15_sale_vacia_en_las_tres_hojas(tmp_path, monkeypatch):
    """Issue #37 — el PARTIDA: (A15) va VACIO en RGO, RCO y RFO.

    Los 15 documentos del cliente dejan ahi una formula fija a
    'CD-COAF-REO-01'!$A$16, y esa celda esta vacia en las 24 planillas
    medidas, asi que en sus documentos ese casillero sale en blanco siempre.
    Nosotros no escribimos la formula: producir el mismo blanco agregando una
    dependencia entre hojas no aporta nada. Antes iba el `orden` del catalogo,
    un numero que el cliente nunca vio en ese casillero.

    Ojo con el vecino: B15 (CLAVE:) SI lleva contenido y lo cubre
    test_las_tres_hojas_de_una_clave_no_se_contradicen — este test afirma que
    vaciar A15 no se llevo puesto a B15.
    """
    wb = openpyxl.load_workbook(_generar(tmp_path, monkeypatch))
    try:
        for clave in CLAVES:
            sufijo = f"-{int(clave):02d}"
            for familia in ("RGO", "RCO", "RFO"):
                ws = wb[f"CD-COAF-{familia}{sufijo}"]
                assert ws["A14"].value == "PARTIDA:", (
                    f"{familia}{sufijo}!A14 = {ws['A14'].value!r} — el rotulo se movio, "
                    "este test esta mirando la celda equivocada"
                )
                assert ws["A15"].value is None, (
                    f"{familia}{sufijo}!A15 = {ws['A15'].value!r}, se esperaba vacio (issue #37)"
                )
                assert ws["B15"].value is not None, (
                    f"{familia}{sufijo}!B15 quedo vacio — vaciar A15 no debe tocar la CLAVE:"
                )
    finally:
        wb.close()
