"""
Cubre issue #6 — exportar la Estimacion a PDF ademas del .xlsx.

- hallazgo #1: CD-COAF-RGO-PLANTILLA no traia ninguna config de impresion
  (a diferencia de CEO-01/REO-01, que ya la tienen en el archivo de
  plantilla) — la tabla de generadores salia partida en 2 paginas de PDF,
  cortando columnas a la mitad.
- hallazgo #2: el pie de pagina de CEO-01/REO-01 usa el escape _x000a_
  (salto de linea de Excel) que LibreOffice no interpreta al exportar a
  PDF, y lo imprime literal.

openpyxl decodifica _x000a_ a "\n" al CARGAR el workbook y vuelve a
escaparlo a _x000a_ al GUARDAR (HeaderFooterItem.__str__ llama a
openpyxl.utils.escape.escape() sin excepcion) — por eso el fix real de
_est_arreglar_saltos_footer() parchea el XML crudo ya guardado, no el
objeto Python. Los tests de este archivo verifican eso directamente sobre
el .xlsx guardado (deterministico, sin LibreOffice) y tambien end-to-end
sobre el texto extraido del PDF real (se salta si LibreOffice no esta
instalado, mismo patron que test_calculo_estimacion.py).

Correr con: python -m pytest tests/test_generar_pdf_estimacion.py -v
"""
import os
import sqlite3
import sys
import uuid
import zipfile
from datetime import date, datetime

import openpyxl
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import main  # noqa: E402 (solo para main.app — TestClient necesita la app con los routers ya incluidos)

requiere_libreoffice = pytest.mark.skipif(
    core.EST_SOFFICE is None, reason="LibreOffice no esta instalado — se salta la verificacion end-to-end del PDF"
)


def _bd_sintetica(tmp_path, monkeypatch, empresa, fase, capacidad_catalogo, facturas):
    """BD sqlite minima con un catalogo de 2 productos (bien dentro de la
    capacidad real de la plantilla de esa fase) y las facturas que se le
    pasen — aisla estos tests de los datos reales de produccion, mismo
    patron que tests/test_estimaciones_validacion.py::bd_sintetica."""
    assert capacidad_catalogo >= 2
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
    # Issue #12 — _est_clasificar_series() (usada ahora por vista-previa y
    # generar) consulta esta tabla siempre, aunque quede vacia (fase sin
    # PPACT sembrado).
    conn.execute("""CREATE TABLE estimacion_acumulado_base (
        empresa TEXT, fase TEXT, clave TEXT,
        serie TEXT NOT NULL CHECK (serie IN ('principal','ppact')),
        fecha_base DATE, cantidad_base REAL, cantidad_proyecto_principal REAL,
        PRIMARY KEY (empresa, fase, clave, serie)
    )""")
    conn.execute(
        "INSERT INTO catalogo_estimacion VALUES (?,?,1,'1','Producto Uno',100.0)", (empresa, fase)
    )
    conn.execute(
        "INSERT INTO catalogo_estimacion VALUES (?,?,2,'2','Producto Dos (sin entregas)',200.0)", (empresa, fase)
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


def _payload(empresa, fase, fecha_desde="2026-06-01", fecha_hasta="2026-06-30"):
    return {
        "empresa": empresa, "fase": fase,
        "fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta,
        "numero_estimacion": "N01",
        "fecha_estimacion": "2026-08-24", "semana": 1,
        "productos": [
            {"clave": "1", "cantidad_proyecto": 1000, "acumulado_anterior_cantidad": 0},
            {"clave": "2", "cantidad_proyecto": 1000, "acumulado_anterior_cantidad": 0},
        ],
        "reasignaciones": {},
        "serie": "principal",
    }


def _generar(client, token, empresa, fase, tmp_path, monkeypatch):
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    res = client.post(
        "/api/estimaciones/generar", json=_payload(empresa, fase),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    return res.json()


# ── hallazgo #1 — page setup de la hoja RGO clonada ──

def test_rgo_clonada_usa_el_print_setup_del_cliente(tmp_path, monkeypatch):
    """Issue #18 — reemplaza al test del issue #6 que fijaba landscape +
    fitToWidth. Ese setup arreglaba el corte horizontal pero medía mal el
    alto: a esa escala un bloque de 40 folios no entra en una página, así
    que LibreOffice metía saltos automáticos y los bloques salían partidos
    (medido con 175 folios: 27+13, 36+4, 36+4, 36+4, 15). El setup del
    cliente (portrait + escala fija 64) da 40/40/40/40/15 exacto."""
    facturas = [{"id_documento": "F001", "fecha": "2026-06-01", "cantidad": 10}]
    token = _bd_sintetica(tmp_path, monkeypatch, "VMO", "CEDIS", 12, facturas)
    client = TestClient(main.app)
    data = _generar(client, token, "VMO", "CEDIS", tmp_path, monkeypatch)

    nombre = data["download_url"].rsplit("/", 1)[-1]
    wb = openpyxl.load_workbook(os.path.join(str(tmp_path), nombre))
    ws_rgo = wb["CD-COAF-RGO-01"]

    assert ws_rgo.page_setup.orientation == "portrait"
    assert ws_rgo.page_setup.scale == 64
    assert ws_rgo.page_setup.fitToHeight == 0
    assert ws_rgo.sheet_properties.pageSetUpPr.fitToPage is False


def test_rgo_clonada_acota_el_area_de_impresion_a_las_columnas_a_i(tmp_path, monkeypatch):
    """Issue #18 — sin print_area, a escala fija las columnas a la derecha
    de I generan una banda entera de páginas en blanco (175 folios daban 10
    páginas: 5 con datos + 5 vacías). El rango llega hasta 3 filas debajo
    del TOTAL, que es el pie de la última página."""
    facturas = [{"id_documento": "F001", "fecha": "2026-06-01", "cantidad": 10}]
    token = _bd_sintetica(tmp_path, monkeypatch, "VMO", "CEDIS", 12, facturas)
    client = TestClient(main.app)
    data = _generar(client, token, "VMO", "CEDIS", tmp_path, monkeypatch)

    nombre = data["download_url"].rsplit("/", 1)[-1]
    wb = openpyxl.load_workbook(os.path.join(str(tmp_path), nombre))
    ws_rgo = wb["CD-COAF-RGO-01"]

    # 1 factura -> la hoja se encoge, TOTAL en 18 + 1 = 19, pie hasta la 22
    assert ws_rgo.print_area == "'CD-COAF-RGO-01'!$A$1:$I$22"


# ── hallazgo #2 — _x000a_ no debe sobrevivir en el .xlsx guardado ──

def test_xlsx_guardado_no_contiene_x000a_literal(tmp_path, monkeypatch):
    facturas = [{"id_documento": "F001", "fecha": "2026-06-01", "cantidad": 10}]
    token = _bd_sintetica(tmp_path, monkeypatch, "VMO", "CEDIS", 12, facturas)
    client = TestClient(main.app)
    data = _generar(client, token, "VMO", "CEDIS", tmp_path, monkeypatch)

    nombre = data["download_url"].rsplit("/", 1)[-1]
    ruta = os.path.join(str(tmp_path), nombre)
    with zipfile.ZipFile(ruta) as z:
        for info in z.infolist():
            if info.filename.startswith("xl/worksheets/") and info.filename.endswith(".xml"):
                contenido = z.read(info.filename)
                assert b"_x000a_" not in contenido, f"{info.filename} todavia tiene _x000a_ literal"


def test_arreglar_saltos_footer_no_toca_hojas_sin_x000a(tmp_path, monkeypatch):
    # CD-COAF-RGO-PLANTILLA nunca tuvo oddFooter configurado (verificado
    # inspeccionando las 3 plantillas reales) — el parche no debe inventar
    # contenido donde no habia footer.
    facturas = [{"id_documento": "F001", "fecha": "2026-06-01", "cantidad": 10}]
    token = _bd_sintetica(tmp_path, monkeypatch, "VMO", "CEDIS", 12, facturas)
    client = TestClient(main.app)
    data = _generar(client, token, "VMO", "CEDIS", tmp_path, monkeypatch)

    nombre = data["download_url"].rsplit("/", 1)[-1]
    wb = openpyxl.load_workbook(os.path.join(str(tmp_path), nombre))
    ws_rgo = wb["CD-COAF-RGO-01"]
    assert not ws_rgo.oddFooter or not ws_rgo.oddFooter.center.text


# ── conversion a PDF nunca rompe la generacion del Excel ──

def test_conversion_pdf_devuelve_none_si_soffice_no_instalado(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "EST_SOFFICE", None)
    ruta_dummy = tmp_path / "no_importa.xlsx"
    ruta_dummy.write_bytes(b"")
    assert core._est_convertir_a_pdf(str(ruta_dummy), "no_importa.xlsx") is None


def test_conversion_pdf_devuelve_none_si_subprocess_lanza_excepcion(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "EST_SOFFICE", "soffice-no-existe")

    def _falla(*a, **k):
        raise FileNotFoundError("binario inventado para el test")

    monkeypatch.setattr(core.subprocess, "run", _falla)
    ruta_dummy = tmp_path / "no_importa.xlsx"
    ruta_dummy.write_bytes(b"")
    assert core._est_convertir_a_pdf(str(ruta_dummy), "no_importa.xlsx") is None


def test_conversion_pdf_devuelve_none_si_returncode_no_es_cero(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "EST_SOFFICE", "soffice-fake")

    class _Resultado:
        returncode = 1
        stderr = b"boom"

    monkeypatch.setattr(core.subprocess, "run", lambda *a, **k: _Resultado())
    ruta_dummy = tmp_path / "no_importa.xlsx"
    ruta_dummy.write_bytes(b"")
    assert core._est_convertir_a_pdf(str(ruta_dummy), "no_importa.xlsx") is None


def test_conversion_pdf_devuelve_none_si_pdf_no_aparece_pese_a_returncode_cero(tmp_path, monkeypatch):
    # soffice devuelve exito pero el archivo nunca aparece en disco — el
    # issue pide tratar esto tambien como fallo de conversion.
    monkeypatch.setattr(core, "EST_SOFFICE", "soffice-fake")
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))

    class _Resultado:
        returncode = 0
        stderr = b""

    monkeypatch.setattr(core.subprocess, "run", lambda *a, **k: _Resultado())
    ruta_dummy = tmp_path / "no_importa.xlsx"
    ruta_dummy.write_bytes(b"")
    assert core._est_convertir_a_pdf(str(ruta_dummy), "no_importa.xlsx") is None


def test_endpoint_generar_devuelve_download_url_pdf_null_si_conversion_falla(tmp_path, monkeypatch):
    facturas = [{"id_documento": "F001", "fecha": "2026-06-01", "cantidad": 10}]
    token = _bd_sintetica(tmp_path, monkeypatch, "VMO", "CEDIS", 12, facturas)
    monkeypatch.setattr(core, "EST_SOFFICE", "soffice-fake")
    monkeypatch.setattr(core.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    client = TestClient(main.app)

    data = _generar(client, token, "VMO", "CEDIS", tmp_path, monkeypatch)

    assert data["download_url_pdf"] is None
    # el .xlsx se genero igual, sin importar el fallo de conversion
    nombre = data["download_url"].rsplit("/", 1)[-1]
    assert os.path.exists(os.path.join(str(tmp_path), nombre))


# ── GET /descargar/{nombre} — media_type por extension ──

def test_descargar_pdf_sirve_media_type_application_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    (tmp_path / "prueba.pdf").write_bytes(b"%PDF-1.4 contenido de prueba")
    token = f"test-token-{uuid.uuid4().hex}"
    core.active_tokens[token] = datetime.now()
    client = TestClient(main.app)

    res = client.get("/api/estimaciones/descargar/prueba.pdf", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/pdf")


def test_descargar_xlsx_sigue_sirviendo_el_media_type_de_siempre(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    (tmp_path / "prueba.xlsx").write_bytes(b"contenido de prueba")
    token = f"test-token-{uuid.uuid4().hex}"
    core.active_tokens[token] = datetime.now()
    client = TestClient(main.app)

    res = client.get("/api/estimaciones/descargar/prueba.xlsx", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ── issue #9 — OC/Contrato fijo por fase, ya no viene del request ──

def test_generar_vmo_cedis_escribe_oc_contrato_correcto_en_m9(tmp_path, monkeypatch):
    facturas = [{"id_documento": "F001", "fecha": "2026-06-01", "cantidad": 10}]
    token = _bd_sintetica(tmp_path, monkeypatch, "VMO", "CEDIS", 12, facturas)
    client = TestClient(main.app)
    data = _generar(client, token, "VMO", "CEDIS", tmp_path, monkeypatch)

    nombre = data["download_url"].rsplit("/", 1)[-1]
    wb = openpyxl.load_workbook(os.path.join(str(tmp_path), nombre))
    ws_reo = wb["CD-COAF-REO-01"]
    assert ws_reo["M9"].value == 4800036588


def test_generar_domicem_viviendas_escribe_oc_contrato_correcto_en_m9(tmp_path, monkeypatch):
    facturas = [{"id_documento": "F001", "fecha": "2026-06-01", "cantidad": 10}]
    token = _bd_sintetica(tmp_path, monkeypatch, "DOMICEM", "VIVIENDAS", 9, facturas)
    client = TestClient(main.app)
    data = _generar(client, token, "DOMICEM", "VIVIENDAS", tmp_path, monkeypatch)

    nombre = data["download_url"].rsplit("/", 1)[-1]
    wb = openpyxl.load_workbook(os.path.join(str(tmp_path), nombre))
    ws_reo = wb["CD-COAF-REO-01"]
    assert ws_reo["M9"].value == "PPACT"


# Diferencias contra el documento oficial de la empresa (2026-08-26)

def test_contratista_domicem_no_tiene_punto_final():
    assert core.EST_CONTRATISTA["DOMICEM"] == "DOMICEM S.A"


def test_fecha_excel_convierte_iso_y_conserva_valores_imperfectos():
    assert core._est_fecha_excel("2026-07-17") == date(2026, 7, 17)
    assert core._est_fecha_excel("") == ""
    assert core._est_fecha_excel("17/07/2026") == "17/07/2026"


def test_etiquetas_rango_estimacion_normal_y_casos_borde():
    assert core._est_etiquetas_rango("N35") == ("N01-N34", "N35", "N01-N35")
    assert core._est_etiquetas_rango("N01") == ("", "N01", "N01-N01")
    assert core._est_etiquetas_rango("PPACT 16") == ("", "", "")

    # El numero anterior se rellena a SU ancho natural, no al del actual: la
    # estimacion anterior a N100 es N99, no N099. Bug real encontrado revisando
    # el trabajo de Codex — habria escrito una etiqueta invalida en un
    # documento oficial al llegar a la estimacion 100.
    assert core._est_etiquetas_rango("N100") == ("N01-N99", "N100", "N01-N100")
    assert core._est_etiquetas_rango("N10") == ("N01-N09", "N10", "N01-N10")

    # "N0"/"N00" no es una estimacion real. Antes devolvia el sinsentido
    # ("", "N00", "N01-N00") y lo escribia en el documento.
    assert core._est_etiquetas_rango("N0") == ("", "", "")
    assert core._est_etiquetas_rango("N00") == ("", "", "")


def test_nombre_rgo_usa_clave_y_sanitiza_no_numericas_sin_duplicar():
    # issue #27 (D3): _est_nombre_rgo se parametrizo como _est_nombre_hoja.
    # Solo cambia la llamada — los valores esperados quedan identicos, y la
    # caracterizacion completa vive en tests/test_nombre_hoja.py.
    usados = set()
    assert core._est_nombre_hoja("6", usados, "CD-COAF-RGO-") == "CD-COAF-RGO-06"
    assert core._est_nombre_hoja("A/B", usados, "CD-COAF-RGO-") == "CD-COAF-RGO-A-B"
    assert core._est_nombre_hoja("A:B", usados, "CD-COAF-RGO-") == "CD-COAF-RGO-A-B-2"


def test_generar_escribe_metadatos_con_tipos_formatos_y_rangos_oficiales(tmp_path, monkeypatch):
    facturas = [{"id_documento": "F001", "fecha": "2026-07-17", "cantidad": 10}]
    token = _bd_sintetica(tmp_path, monkeypatch, "DOMICEM", "MACAO 2", 9, facturas)
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    monkeypatch.setattr(core, "EST_SOFFICE", None)
    payload = _payload("DOMICEM", "MACAO 2", "2026-07-17", "2026-08-16")
    payload["numero_estimacion"] = "N35"
    payload["fecha_estimacion"] = "2026-08-25"

    client = TestClient(main.app)
    res = client.post(
        "/api/estimaciones/generar", json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    nombre = res.json()["download_url"].rsplit("/", 1)[-1]
    ws = openpyxl.load_workbook(os.path.join(str(tmp_path), nombre))["CD-COAF-REO-01"]

    assert ws["B9"].value == "DOMICEM S.A"
    assert ws["M9"].value == 4800029677
    formato = '[$-80A]d" de "mmmm" de "yyyy;@'
    assert [(ws[c].value.date(), ws[c].number_format) for c in ("E12", "H12", "K12")] == [
        (date(2026, 7, 17), formato),
        (date(2026, 8, 16), formato),
        (date(2026, 8, 25), formato),
    ]
    assert (ws["H16"].value, ws["K16"].value, ws["N16"].value) == (
        "N01-N34", "N35", "N01-N35",
    )


# ── end-to-end real con LibreOffice — 2 fases distintas ──

@requiere_libreoffice
def test_pdf_real_vmo_cedis_rgo_no_partida_y_sin_x000a(tmp_path, monkeypatch):
    facturas = [
        {"id_documento": "CEDISPDF001", "fecha": "2026-06-01", "cantidad": 12.5},
        {"id_documento": "CEDISPDF002", "fecha": "2026-06-02", "cantidad": 33.0},
    ]
    token = _bd_sintetica(tmp_path, monkeypatch, "VMO", "CEDIS", 12, facturas)
    client = TestClient(main.app)
    data = _generar(client, token, "VMO", "CEDIS", tmp_path, monkeypatch)

    assert data["download_url_pdf"] is not None
    nombre_pdf = data["download_url_pdf"].rsplit("/", 1)[-1]
    ruta_pdf = os.path.join(str(tmp_path), nombre_pdf)
    assert os.path.exists(ruta_pdf)

    import fitz
    doc = fitz.open(ruta_pdf)
    assert doc.page_count >= 1
    textos = [p.get_text() for p in doc]
    completo = "\n".join(textos)
    assert "_x000a_" not in completo

    # el FOLIO REMISION (columna B) y su CANTIDAD (columna G, lejos a la
    # derecha) deben aparecer en la MISMA pagina — si la hoja saliera
    # partida horizontalmente (bug original, sin fitToWidth), cada mitad
    # de columnas cae en un grupo de paginas distinto.
    pagina_con_folio = next(i for i, t in enumerate(textos) if "CEDISPDF001" in t)
    assert "12.50" in textos[pagina_con_folio]
    doc.close()


@requiere_libreoffice
def test_pdf_real_domicem_macao2_rgo_grande_no_partida(tmp_path, monkeypatch):
    # RGO grande (45 facturas, por encima de la capacidad nativa de 40 de
    # la plantilla) — ejercita a la vez el redimensionado dinamico
    # (2026-08-20) y el fix de paginado de este issue sobre una hoja que de
    # verdad crece en memoria, no solo la plantilla de 1 fila.
    facturas = [
        {"id_documento": f"MACAOPDF{i:04d}", "fecha": "2026-07-01", "cantidad": 5.0 + i}
        for i in range(45)
    ]
    token = _bd_sintetica(tmp_path, monkeypatch, "DOMICEM", "MACAO 2", 9, facturas)
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    client = TestClient(main.app)
    res = client.post(
        "/api/estimaciones/generar",
        json=_payload("DOMICEM", "MACAO 2", fecha_desde="2026-07-01", fecha_hasta="2026-07-31"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["total_facturas"] == 45
    assert data["download_url_pdf"] is not None
    nombre_pdf = data["download_url_pdf"].rsplit("/", 1)[-1]
    ruta_pdf = os.path.join(str(tmp_path), nombre_pdf)

    import fitz
    doc = fitz.open(ruta_pdf)
    textos = [p.get_text() for p in doc]
    completo = "\n".join(textos)
    assert "_x000a_" not in completo

    pagina_primera = next(i for i, t in enumerate(textos) if "MACAOPDF0000" in t)
    assert "5.00" in textos[pagina_primera]
    pagina_ultima = next(i for i, t in enumerate(textos) if "MACAOPDF0044" in t)
    assert "49.00" in textos[pagina_ultima]
    doc.close()
