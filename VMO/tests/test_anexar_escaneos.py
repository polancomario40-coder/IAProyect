"""
Tests del anexado de conduces escaneados al PDF de la estimacion.

El documento que la empresa entrega trae, despues de las hojas, la foto de
cada conduce, una por pagina: medido sobre el par real
`EST_DOMICEM_MACAO_II_..._N33`, el PDF tiene 1.291 paginas (48 de documento y
1.243 de escaneos) contra 19 imagenes en el .xlsx del mismo documento.

Ninguna prueba toca `conduces/archivos/` ni las bases reales: los escaneos son
PDFs de una pagina fabricados con fitz en un zip temporal.

**El ultimo test va por HTTP a proposito.** La leccion del issue #31 es que un
campo que existe en `core` pero no viaja por la ruta no le llega a nadie: ahi
`sin_precio` se perdio porque las rutas rearmaban la respuesta a mano, con 7
tests en verde que llamaban a la primitiva directo.

Correr con: python -m pytest tests/test_anexar_escaneos.py -v
"""
import os
import sqlite3
import sys
import uuid
import zipfile
from datetime import datetime

import fitz
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import main  # noqa: E402 (solo para main.app — TestClient necesita la app con los routers)

requiere_libreoffice = pytest.mark.skipif(
    core.EST_SOFFICE is None,
    reason="LibreOffice no esta instalado — se salta la verificacion por HTTP del PDF",
)


def _pdf_de_una_pagina(texto):
    """Un PDF minimo en bytes, que hace de escaneo de un conduce."""
    doc = fitz.open()
    doc.new_page().insert_text((72, 100), texto)
    datos = doc.tobytes()
    doc.close()
    return datos


def _fuente(tmp_path, escaneos, nombre_zip="Puente 1.zip"):
    """Directorio de fuentes con un zip de escaneos adentro."""
    base = tmp_path / "archivos"
    base.mkdir(exist_ok=True)
    with zipfile.ZipFile(base / nombre_zip, "w") as zf:
        for nombre, texto in escaneos.items():
            zf.writestr(f"Puente 1/{nombre}", _pdf_de_una_pagina(texto))
    return str(base)


def _procesadas(tmp_path, escaneos):
    """El respaldo que el propio sistema deja al importar: PDFs sueltos, sin
    zip, en estimaciones/facturas/procesadas/."""
    proc = tmp_path / "procesadas"
    proc.mkdir(exist_ok=True)
    for nombre, texto in escaneos.items():
        (proc / nombre).write_bytes(_pdf_de_una_pagina(texto))
    return str(proc)


def _documento(tmp_path, paginas=2, nombre="est.pdf"):
    doc = fitz.open()
    for i in range(paginas):
        doc.new_page().insert_text((72, 100), f"hoja {i}")
    ruta = str(tmp_path / nombre)
    doc.save(ruta)
    doc.close()
    return ruta


def _cat(*claves):
    return [{"clave": c, "orden": i + 1} for i, c in enumerate(claves)]


# ── el indice de escaneos ──

def test_indice_toma_todos_los_zips_del_directorio(tmp_path):
    base = _fuente(tmp_path, {"06-01-M8-11.pdf": "uno"})
    with zipfile.ZipFile(os.path.join(base, "Puente 2.zip"), "w") as zf:
        zf.writestr("Puente 2/08-01-M8-22.pdf", _pdf_de_una_pagina("dos"))
    indice = core._est_indice_escaneos(base)
    assert set(indice) == {"06-01-M8-11.pdf", "08-01-M8-22.pdf"}, (
        "cada zip nuevo que aparezca tiene que entrar solo, sin tocar codigo"
    )


def test_un_escaneo_suelto_le_gana_al_del_zip(tmp_path):
    base = _fuente(tmp_path, {"06-01-M8-11.pdf": "el del zip"})
    sueltos = os.path.join(base, "escaneos")
    os.makedirs(sueltos)
    with open(os.path.join(sueltos, "06-01-M8-11.pdf"), "wb") as f:
        f.write(_pdf_de_una_pagina("el mejor"))
    ruta_zip, interno = core._est_indice_escaneos(base)["06-01-M8-11.pdf"]
    assert ruta_zip is None and interno.endswith("escaneos" + os.sep + "06-01-M8-11.pdf")


def test_directorio_inexistente_da_indice_vacio_sin_reventar(tmp_path):
    assert core._est_indice_escaneos(str(tmp_path / "no-existe")) == {}


def test_procesadas_llena_los_huecos_que_ningun_zip_tiene(tmp_path):
    """El caso real del 2026-09-25: 58 escaneos que existian SOLO en
    estimaciones/facturas/procesadas/ (el respaldo que deja el propio import)
    salieron como paginas ESCANEO NO DISPONIBLE porque el indice no miraba esa
    carpeta. secuencia.py no lo vio: reconcilia por numero de conduce y este
    indice mapea por nombre de archivo."""
    base = _fuente(tmp_path, {"06-01-M8-11.pdf": "el del zip"})
    proc = _procesadas(tmp_path, {"09-20-M8-99.pdf": "solo en procesadas"})
    indice = core._est_indice_escaneos(base, procesadas=proc)
    assert set(indice) == {"06-01-M8-11.pdf", "09-20-M8-99.pdf"}
    ruta_zip, ruta = indice["09-20-M8-99.pdf"]
    assert ruta_zip is None and ruta == os.path.join(proc, "09-20-M8-99.pdf")


def test_el_zip_le_gana_a_procesadas(tmp_path):
    """A proposito, y es lo que hace que el arreglo sea puramente aditivo: los
    bytes de procesadas/ son el `zf.read()` tal cual (importar_puente.py no
    rota ni reescribe), asi que ningun escaneo que ya resolvia cambia de
    fuente."""
    base = _fuente(tmp_path, {"06-01-M8-11.pdf": "el del zip"})
    proc = _procesadas(tmp_path, {"06-01-M8-11.pdf": "la copia"})
    ruta_zip, interno = core._est_indice_escaneos(base, procesadas=proc)["06-01-M8-11.pdf"]
    assert ruta_zip is not None and interno.endswith("06-01-M8-11.pdf")


def test_un_escaneo_suelto_le_gana_tambien_a_procesadas(tmp_path):
    """El suelto es el punto de extension para dejar una version mejor
    escaneada: tiene que ganarle a las DOS fuentes automaticas."""
    base = _fuente(tmp_path, {"06-01-M8-11.pdf": "el del zip"})
    proc = _procesadas(tmp_path, {"06-01-M8-11.pdf": "la copia"})
    sueltos = os.path.join(base, "escaneos")
    os.makedirs(sueltos)
    with open(os.path.join(sueltos, "06-01-M8-11.pdf"), "wb") as f:
        f.write(_pdf_de_una_pagina("el mejor"))
    ruta_zip, ruta = core._est_indice_escaneos(base, procesadas=proc)["06-01-M8-11.pdf"]
    assert ruta_zip is None and ruta.endswith("escaneos" + os.sep + "06-01-M8-11.pdf")


def test_procesadas_alcanza_sola_si_no_hay_directorio_de_zips(tmp_path):
    """conduces/archivos/ esta en .gitignore y un worktree limpio no lo tiene.
    Antes eso devolvia indice vacio de una por un `return` temprano; ahora
    avisa y sigue, porque procesadas/ es una fuente aparte."""
    proc = _procesadas(tmp_path, {"09-20-M8-99.pdf": "solo en procesadas"})
    indice = core._est_indice_escaneos(str(tmp_path / "no-existe"), procesadas=proc)
    assert set(indice) == {"09-20-M8-99.pdf"}


def test_inyectar_directorio_no_lee_la_procesadas_real(tmp_path):
    """Aislamiento: un fixture con su propio arbol no toca los PDFs de
    produccion. Sin esto, los tests de arriba leerian
    estimaciones/facturas/procesadas/ y su set de nombres no cerraria."""
    base = _fuente(tmp_path, {"06-01-M8-11.pdf": "uno"})
    assert set(core._est_indice_escaneos(base)) == {"06-01-M8-11.pdf"}


# ── el orden en que van al PDF ──

def test_orden_sigue_el_catalogo_y_adentro_fecha_y_documento():
    fpc = {
        "2": [{"id_documento": "MB", "fecha": "2026-06-05", "archivo_pdf": "b.pdf"}],
        "1": [{"id_documento": "MZ", "fecha": "2026-06-09", "archivo_pdf": "z.pdf"},
              {"id_documento": "MA", "fecha": "2026-06-01", "archivo_pdf": "a.pdf"}],
    }
    orden = core._est_orden_de_anexado(_cat("1", "2"), fpc)
    assert [x[1] for x in orden] == ["MA", "MZ", "MB"]


# ── el anexado ──

def test_anexa_cada_conduce_en_orden_detras_del_documento(tmp_path):
    base = _fuente(tmp_path, {"a.pdf": "conduce A", "b.pdf": "conduce B"})
    ruta = _documento(tmp_path, paginas=2)
    fpc = {"1": [{"id_documento": "MA", "fecha": "2026-06-01", "archivo_pdf": "a.pdf"},
                 {"id_documento": "MB", "fecha": "2026-06-02", "archivo_pdf": "b.pdf"}]}
    parte = core._est_anexar_escaneos(ruta, _cat("1"), fpc, indice=core._est_indice_escaneos(base))
    assert parte["anexados"] == 2 and parte["faltantes"] == []
    with fitz.open(ruta) as doc:
        assert doc.page_count == 4
        assert "conduce A" in doc[2].get_text()
        assert "conduce B" in doc[3].get_text()


def test_un_escaneo_que_falta_deja_pagina_de_aviso_con_el_numero(tmp_path):
    """Se escribe una pagina en vez de saltearlo en silencio: el documento del
    cliente tiene una foto por conduce, asi que una ausencia muda se lee como
    si el conduce no existiera."""
    base = _fuente(tmp_path, {"a.pdf": "conduce A"})
    ruta = _documento(tmp_path, paginas=1)
    fpc = {"1": [{"id_documento": "MA", "fecha": "2026-06-01", "archivo_pdf": "a.pdf"},
                 {"id_documento": "M800014432", "fecha": "2026-06-02", "archivo_pdf": "08-01-M8-14432.pdf"}]}
    parte = core._est_anexar_escaneos(ruta, _cat("1"), fpc, indice=core._est_indice_escaneos(base))
    assert parte["anexados"] == 1
    assert parte["faltantes"] == ["M800014432"]
    with fitz.open(ruta) as doc:
        assert doc.page_count == 3
        aviso = doc[2].get_text()
        assert "ESCANEO NO DISPONIBLE" in aviso
        assert "M800014432" in aviso, "el aviso tiene que decir DE CUAL conduce falta la foto"


def test_una_factura_sin_archivo_pdf_no_es_un_faltante(tmp_path):
    """"No se que archivo buscar" no es lo mismo que "se cual y no esta": sin
    nombre no hay aviso util que escribir, asi que se cuenta aparte."""
    base = _fuente(tmp_path, {"a.pdf": "conduce A"})
    ruta = _documento(tmp_path, paginas=1)
    fpc = {"1": [{"id_documento": "MA", "fecha": "2026-06-01", "archivo_pdf": "a.pdf"},
                 {"id_documento": "MB", "fecha": "2026-06-02", "archivo_pdf": None}]}
    parte = core._est_anexar_escaneos(ruta, _cat("1"), fpc, indice=core._est_indice_escaneos(base))
    assert parte["anexados"] == 1
    assert parte["faltantes"] == []
    assert parte["sin_referencia"] == 1
    with fitz.open(ruta) as doc:
        assert doc.page_count == 2, "no se agrega pagina de aviso para algo que no se puede nombrar"


def test_si_ninguna_factura_tiene_archivo_pdf_el_pdf_no_se_toca(tmp_path):
    """Una BD que no registra escaneos genera exactamente el mismo PDF que
    antes de esta funcion — ni una pagina de mas."""
    base = _fuente(tmp_path, {"a.pdf": "conduce A"})
    ruta = _documento(tmp_path, paginas=2)
    antes = open(ruta, "rb").read()
    fpc = {"1": [{"id_documento": "MA", "fecha": "2026-06-01", "archivo_pdf": None}]}
    parte = core._est_anexar_escaneos(ruta, _cat("1"), fpc, indice=core._est_indice_escaneos(base))
    assert parte["anexados"] == 0 and parte["sin_referencia"] == 1
    assert "archivo_pdf" in parte["error"]
    assert open(ruta, "rb").read() == antes


def test_sin_fuente_de_escaneos_avisa_y_deja_el_pdf_intacto(tmp_path):
    ruta = _documento(tmp_path, paginas=2)
    antes = open(ruta, "rb").read()
    fpc = {"1": [{"id_documento": "MA", "fecha": "2026-06-01", "archivo_pdf": "a.pdf"}]}
    parte = core._est_anexar_escaneos(ruta, _cat("1"), fpc, indice={})
    assert parte["error"] == "no se encontro ninguna fuente de escaneos"
    assert open(ruta, "rb").read() == antes, "sin fuente no se degrada el PDF, se avisa"


def test_un_escaneo_ilegible_no_se_lleva_puestos_a_los_demas(tmp_path):
    base = tmp_path / "archivos"
    base.mkdir()
    with zipfile.ZipFile(base / "Puente 1.zip", "w") as zf:
        zf.writestr("Puente 1/a.pdf", _pdf_de_una_pagina("conduce A"))
        zf.writestr("Puente 1/roto.pdf", b"esto no es un PDF")
    ruta = _documento(tmp_path, paginas=1)
    fpc = {"1": [{"id_documento": "MA", "fecha": "2026-06-01", "archivo_pdf": "a.pdf"},
                 {"id_documento": "MR", "fecha": "2026-06-02", "archivo_pdf": "roto.pdf"}]}
    parte = core._est_anexar_escaneos(ruta, _cat("1"), fpc,
                                      indice=core._est_indice_escaneos(str(base)))
    assert parte["anexados"] == 1 and parte["faltantes"] == ["MR"]
    with fitz.open(ruta) as doc:
        assert "ESCANEO NO DISPONIBLE" in doc[2].get_text()


# ── por la ruta (leccion del issue #31) ──

def _bd_con_escaneos(tmp_path, monkeypatch, empresa, fase, facturas):
    db_path = tmp_path / f"est_{uuid.uuid4().hex}.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE catalogo_estimacion (
        empresa TEXT, fase TEXT, orden INTEGER, clave TEXT,
        descripcion TEXT, precio_unitario REAL,
        PRIMARY KEY (empresa, fase, orden))""")
    conn.execute("""CREATE TABLE facturas (
        id_documento TEXT PRIMARY KEY, fecha DATE, empresa TEXT, fase TEXT,
        descripcion TEXT, cantidad REAL, precio_unitario REAL,
        clave_resuelta TEXT, archivo_pdf TEXT)""")
    conn.execute("""CREATE TABLE estimacion_acumulado_base (
        empresa TEXT, fase TEXT, clave TEXT,
        serie TEXT NOT NULL CHECK (serie IN ('principal','ppact')),
        fecha_base DATE, cantidad_base REAL, cantidad_proyecto_principal REAL,
        PRIMARY KEY (empresa, fase, clave, serie))""")
    conn.execute("INSERT INTO catalogo_estimacion VALUES (?,?,1,'1','Producto Uno',100.0)", (empresa, fase))
    conn.execute("INSERT INTO catalogo_estimacion VALUES (?,?,2,'2','Producto Dos (sin entregas)',200.0)", (empresa, fase))
    for f in facturas:
        conn.execute(
            "INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,cantidad,"
            "precio_unitario,archivo_pdf) VALUES (?,?,?,?,'Producto Uno',?,100.0,?)",
            (f["id_documento"], f["fecha"], empresa, fase, f["cantidad"], f["archivo_pdf"]),
        )
    conn.commit()
    conn.close()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    token = f"test-token-{uuid.uuid4().hex}"
    core.active_tokens[token] = datetime.now()
    return token


@requiere_libreoffice
def test_la_ruta_devuelve_el_parte_de_escaneos_y_el_pdf_los_trae(tmp_path, monkeypatch):
    """Va por HTTP, no a la primitiva: es la unica forma de comprobar que el
    campo le llega al cliente (issue #31)."""
    facturas = [
        {"id_documento": "MA", "fecha": "2026-06-01", "cantidad": 10.0, "archivo_pdf": "a.pdf"},
        {"id_documento": "MB", "fecha": "2026-06-02", "cantidad": 5.0, "archivo_pdf": "falta.pdf"},
        {"id_documento": "MC", "fecha": "2026-06-03", "cantidad": 7.0, "archivo_pdf": "c.pdf"},
    ]
    token = _bd_con_escaneos(tmp_path, monkeypatch, "VMO", "CEDIS", facturas)
    monkeypatch.setattr(core, "EST_ESCANEOS_DIR", _fuente(tmp_path, {"a.pdf": "conduce A"}))
    # `c.pdf` existe SOLO en procesadas/: es el caso del 2026-09-25 recorrido
    # por HTTP, no llamando a la primitiva. Y el monkeypatch es obligatorio por
    # aislamiento — sin el, la ruta leeria los PDFs reales de produccion.
    monkeypatch.setattr(core, "EST_PROCESADAS", _procesadas(tmp_path, {"c.pdf": "conduce C"}))
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))

    client = TestClient(main.app)
    res = client.post("/api/estimaciones/generar", json={
        "empresa": "VMO", "fase": "CEDIS",
        "fecha_desde": "2026-06-01", "fecha_hasta": "2026-06-30",
        "numero_estimacion": "N01", "fecha_estimacion": "2026-08-24", "semana": 1,
        "productos": [{"clave": "1", "cantidad_proyecto": 1000, "acumulado_anterior_cantidad": 0},
                      {"clave": "2", "cantidad_proyecto": 1000, "acumulado_anterior_cantidad": 0}],
        "reasignaciones": {}, "serie": "principal",
    }, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text

    cuerpo = res.json()
    assert "escaneos" in cuerpo, "el parte no puede quedarse dentro de core (issue #31)"
    assert cuerpo["escaneos"]["total"] == 3
    assert cuerpo["escaneos"]["anexados"] == 2
    assert cuerpo["escaneos"]["faltantes"] == ["MB"]

    nombre_pdf = cuerpo["download_url_pdf"].rsplit("/", 1)[-1]
    with fitz.open(os.path.join(str(tmp_path), nombre_pdf)) as doc:
        textos = "\n".join(doc[i].get_text() for i in range(doc.page_count))
    assert "conduce A" in textos, "la foto del conduce tiene que estar dentro del PDF entregable"
    assert "conduce C" in textos, (
        "el escaneo que solo esta en procesadas/ tambien tiene que llegar al PDF: "
        "eso era lo que faltaba el 2026-09-25"
    )
    assert "ESCANEO NO DISPONIBLE" in textos
