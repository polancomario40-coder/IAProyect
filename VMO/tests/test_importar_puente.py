"""
tests/test_importar_puente.py — primera cobertura de pytest para
scripts/importar_puente.py (issue #8, 2026-08-24).

Este script no tiene (ni tenia antes de este issue) una suite de pytest
completa — llama a la API real de Vision para casi todo, asi que la mayoria
de su comportamiento se verifica a mano (ver CLAUDE.md). La UNICA pieza
nueva de este issue que es una funcion pura sin ninguna llamada a Vision es
decidir_no_macao2() — extraida especificamente para poder cubrirla aqui sin
mockear la API de Anthropic.

Issue #19 (2026-08-28): se agregan los tests de CARACTERIZACION de las 7
funciones de datos que se van a unificar con core.py (get_fase_empresa,
buscar_precio, insert_factura, asegurar_tabla_pendientes,
guardar_pendiente_revision, resolver_pendiente_si_existe, mas
decidir_no_macao2 que ya estaba cubierta). Capturan el comportamiento
ACTUAL del script duplicado, sobre entradas reales, y son la red de
seguridad del refactor: si el refactor obliga a editar uno de estos tests,
el comportamiento cambio y hay que parar, no ajustar el test.

Correr con: python -m pytest tests/test_importar_puente.py -v
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importar_puente  # noqa: E402
import core  # noqa: E402  — solo para parchear los directorios de salida (ver _parchear_dirs)


def test_decidir_no_macao2_con_firma_no_bloquea():
    assert importar_puente.decidir_no_macao2(tiene_firma=True, doble_chequeo_fallo=False) is None


def test_decidir_no_macao2_sin_firma_bloquea():
    assert importar_puente.decidir_no_macao2(tiene_firma=False, doble_chequeo_fallo=False) == "falta firma"


def test_decidir_no_macao2_doble_chequeo_fallo_bloquea():
    # Aunque Haiku haya dicho tiene_firma=True, si el doble-chequeo con
    # Sonnet fallo (error de API) no se confia en el — mismo criterio
    # conservador que el resto del pipeline (ver core.py y Fase 2 de este
    # mismo script).
    assert importar_puente.decidir_no_macao2(tiene_firma=True, doble_chequeo_fallo=True) == "falta firma"


def test_decidir_no_macao2_vertical_va_a_revision():
    assert importar_puente.decidir_no_macao2(True, False, pagina_vertical=True) ==         core.EST_MOTIVO_PAGINA_VERTICAL
    # sin firma sigue mandando "falta firma"
    assert importar_puente.decidir_no_macao2(False, False, pagina_vertical=True) == "falta firma"


def test_decidir_macao2_conserva_los_motivos_de_siempre():
    """Caracterizacion de lo que estaba en linea en el bucle de Fase 2."""
    assert importar_puente.decidir_macao2(True, False) is None
    # "falta sello" y no "sin sello": tiene que ser un motivo aprobable.
    assert importar_puente.decidir_macao2(False, False) == "falta sello"
    assert "falta sello" in core.EST_MOTIVOS_APROBABLES
    assert importar_puente.decidir_macao2(True, True) == "verificación de sello/firma falló"
    assert importar_puente.decidir_macao2(False, True) == "verificación de sello/firma falló"


def test_decidir_macao2_vertical_va_a_revision():
    assert importar_puente.decidir_macao2(True, False, pagina_vertical=True) ==         core.EST_MOTIVO_PAGINA_VERTICAL
    assert importar_puente.decidir_macao2(False, False, pagina_vertical=True) == "falta sello"


# ═════════════════════════════════════════════════════════════════════════
# Issue #19 — tests de caracterizacion (fase 1). Capturan el comportamiento
# ACTUAL de las funciones de datos duplicadas, ANTES del refactor.
# ═════════════════════════════════════════════════════════════════════════

# Los 15 valores distintos de `cliente` que existen HOY en la tabla facturas
# (tabla de caracterizacion del issue #19, fijada aca como constante a
# proposito — el test NO lee la BD). Los 2 que esperan (None, None) son
# corrupciones reales de OCR ("MACAO 1" en vez de "MACAO II") que HOY van a
# pendientes_revision por los dos caminos de importacion: el refactor NO debe
# "arreglarlos" — cambiar eso seria un cambio de comportamiento sin validar,
# por eso este test los fija en None a proposito.
CLIENTES_REALES = [
    ("MACAO ALTO RESORT S.R.L, (MACAO II, ESTRUCTURA)",        "MACAO 2",               "DOMICEM"),
    ("MACAO ALTO RESORT S.R.L- PODIUM 1, 2 Y 3",               "PODIUM-1-2-3",          "VMO"),
    ("MACAO ALTO RESORT SRL  (CIUDAD PALACE - CAVERNAS Y EXT)", "CAVERNAS",             "DOMICEM"),
    ("MACAO ALTO RESORT S.R.L  EXTERIORES",                    "EXTERIORES",            "VMO"),
    ("MACAO ALTO RESORT SRL (CEDIS)",                          "CEDIS",                 "VMO"),
    ("MACAO ALTO RESORT SRL, (CIUDAD PALACE - VIVIENDAS)",     "VIVIENDAS",             "DOMICEM"),
    ("MACAO ALTO RESORT, S.R.L. - CIMENTACIONES MACAO II",     "MACAO 2",               "DOMICEM"),
    ("MACAO ALTO RESORT S.R.L, PATIO MANIOBRAS TRB",           "PATIO DE MANIOBRAS-TRB", "DOMICEM"),
    ("MACAO ALTO RESORT S.R.L  CANCHAS",                       "CANCHAS",               "VMO"),
    ("MACAO ALTO RESORT S.R.L. (MACAO II, ESTRUCTURA)",        "MACAO 2",               "DOMICEM"),
    ("MACAO ALTO RESORT S.R.L, (PATIO DE MANIOBRA TRA)",       "PATIO DE MANIOBRAS-TRA", "VMO"),
    ("MACÃO ALTO RESORT S.R.L. (MACAO II, ESTRUCTURA)",        "MACAO 2",               "DOMICEM"),
    ("MACAO ALTO RESORT S.R.L. (MACAO 1), ESTRUCTURA)",        None,                    None),
    ("MACAO AIYORESORT S.R.L. (MACAO II ESTRUCTURA)",          "MACAO 2",               "DOMICEM"),
    ("MACAO AITO RESORT S.R.L. (MACAO 1, ESTRUCTURA)",         None,                    None),
]

# Casos sinteticos extra (hardcodeados, NO leidos de CLIENTE_FASE — esa
# constante desaparece con el refactor): cubren las fases que los 15 clientes
# reales no tocan, para fijar tambien su fase y empresa actuales.
CLIENTES_SINTETICOS = [
    ("OBRA CAMPO DE GOLF",        "CAMPO DE GOLF",           "VMO"),
    ("PUENTES DE MANGLAR ETAPA 2", "PUENTES DE MANGLAR",     "VMO"),
    ("SALON BALLROOM",            "BALLROOM",                "VMO"),
    ("X PATIO MANIOBRAS TRA",     "PATIO DE MANIOBRAS-TRA",  "VMO"),
    ("X PATIO DE MANIOBRA TRB",   "PATIO DE MANIOBRAS-TRB",  "DOMICEM"),
    ("CIMENTACIONES MACAO",       "MACAO 2",                 "DOMICEM"),
]


def test_caracterizacion_fase_de_los_15_clientes_reales():
    for cliente, fase_esperada, _ in CLIENTES_REALES:
        fase, _empresa = importar_puente.get_fase_empresa(cliente)
        assert fase == fase_esperada, f"cliente {cliente!r}: fase {fase!r} != {fase_esperada!r}"
    # Sin cliente no hay fase (va a pendientes_revision):
    assert importar_puente.get_fase_empresa(None) == (None, None)
    assert importar_puente.get_fase_empresa("") == (None, None)


def test_caracterizacion_empresa_de_los_15_clientes_reales():
    for cliente, _, empresa_esperada in CLIENTES_REALES:
        _fase, empresa = importar_puente.get_fase_empresa(cliente)
        assert empresa == empresa_esperada, f"cliente {cliente!r}: empresa {empresa!r} != {empresa_esperada!r}"


def test_caracterizacion_fase_empresa_casos_sinteticos():
    for cliente, fase_esperada, empresa_esperada in CLIENTES_SINTETICOS:
        assert importar_puente.get_fase_empresa(cliente) == (fase_esperada, empresa_esperada), cliente


# ── esquema minimo para los tests con BD (temporal, en memoria) ──────────

def _conn_esquema():
    """BD en memoria con el esquema real de facturas (31 columnas, incluidas
    sin_firma, clave_resuelta, las 5 de aprobacion manual del issue #20,
    obra_papel del issue #67 y obra_familia del issue #72, que en produccion
    entran por migracion de setup_est_db),
    pendientes_revision y las 2 tablas de precios, con seeds
    conocidos. El test nunca toca la BD de produccion."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE facturas (
        id_documento TEXT PRIMARY KEY, fecha DATE, planta TEXT,
        orden_compra TEXT, referencia TEXT, distancia TEXT, cliente TEXT,
        obra TEXT, obra_papel TEXT, obra_familia TEXT, bomba TEXT,
        id_producto TEXT, descripcion TEXT,
        cantidad REAL, precio_unitario REAL, total REAL, ficha TEXT,
        chofer TEXT, hora_salida TEXT, observaciones TEXT, archivo_pdf TEXT,
        empresa TEXT, fase TEXT, fecha_importacion DATETIME,
        sin_firma INTEGER DEFAULT 0, clave_resuelta TEXT,
        aprobado_manual INTEGER DEFAULT 0, aprobado_por TEXT,
        aprobado_motivo TEXT, aprobado_fecha TEXT, motivo_bloqueo TEXT)""")
    conn.execute("""CREATE TABLE precios_domicem (
        fase TEXT, codigo TEXT, descripcion TEXT, precio_unitario REAL,
        PRIMARY KEY (fase, codigo))""")
    conn.execute("""CREATE TABLE precios_vmo (
        codigo TEXT, fase TEXT, descripcion TEXT, precio_unitario REAL,
        PRIMARY KEY (codigo, fase))""")
    # El seed de DOMICEM lleva un espacio al final a proposito: la query
    # real hace TRIM(descripcion) del lado de la BD.
    conn.executemany("INSERT INTO precios_domicem VALUES (?,?,?,?)", [
        ("MACAO 2",  "D-350", "Hormigon Industrial 350 Kg/cm2 ", 8000.0),
        ("CAVERNAS", "D-350", "Hormigon Industrial 350 Kg/cm2",  7500.0),
    ])
    conn.executemany("INSERT INTO precios_vmo VALUES (?,?,?,?)", [
        ("V-240",       None,    "Hormigon 240", 6000.0),
        ("V-240-CEDIS", "CEDIS", "Hormigon 240", 6200.0),
    ])
    importar_puente.asegurar_tabla_pendientes(conn.cursor())
    return conn


def _parchear_dirs(monkeypatch, tmp_path):
    """Redirige a tmp_path TODOS los nombres por los que puede salir una
    escritura fisica de PDF (los del script Y los de core, que en produccion
    apuntan al mismo directorio). La caracterizacion fija el comportamiento
    observable — 'el PDF queda en el directorio de procesadas/pendientes
    vigente' — no cual variable global lo referencia."""
    pend = tmp_path / "pendientes"
    proc = tmp_path / "procesadas"
    pend.mkdir()
    proc.mkdir()
    monkeypatch.setattr(importar_puente, "PENDIENTES_DIR", pend)
    monkeypatch.setattr(importar_puente, "PROCESADAS_DIR", proc)
    monkeypatch.setattr(core, "EST_PENDIENTES", str(pend))
    monkeypatch.setattr(core, "EST_PROCESADAS", str(proc))
    return pend, proc


# ── buscar_precio ────────────────────────────────────────────────────────

def test_buscar_precio_domicem_filtra_por_fase():
    cur = _conn_esquema().cursor()
    # La misma descripcion existe en 2 fases DOMICEM con precios distintos:
    assert importar_puente.buscar_precio(cur, "DOMICEM", "MACAO 2",  "Hormigon Industrial 350 Kg/cm2") == 8000.0
    assert importar_puente.buscar_precio(cur, "DOMICEM", "CAVERNAS", "Hormigon Industrial 350 Kg/cm2") == 7500.0
    # Fase sin fila en precios_domicem — no cae a otra fase ni a NULL:
    assert importar_puente.buscar_precio(cur, "DOMICEM", "VIVIENDAS", "Hormigon Industrial 350 Kg/cm2") is None
    # El argumento se limpia con strip() y la BD con TRIM():
    assert importar_puente.buscar_precio(cur, "DOMICEM", "MACAO 2", "  Hormigon Industrial 350 Kg/cm2  ") == 8000.0


def test_buscar_precio_vmo_prefiere_fase_exacta_y_cae_a_fase_null():
    cur = _conn_esquema().cursor()
    # Con fila de fase exacta, gana la fase exacta (ORDER BY fase IS NULL):
    assert importar_puente.buscar_precio(cur, "VMO", "CEDIS", "Hormigon 240") == 6200.0
    # Sin fila de fase exacta, cae al precio generico con fase NULL:
    assert importar_puente.buscar_precio(cur, "VMO", "EXTERIORES", "Hormigon 240") == 6000.0


def test_buscar_precio_descripcion_inexistente_devuelve_none():
    cur = _conn_esquema().cursor()
    assert importar_puente.buscar_precio(cur, "DOMICEM", "MACAO 2", "Hormigon Fantasma") is None
    assert importar_puente.buscar_precio(cur, "VMO", "CEDIS", "Hormigon Fantasma") is None


def test_buscar_precio_descripcion_vacia_devuelve_none():
    cur = _conn_esquema().cursor()
    assert importar_puente.buscar_precio(cur, "DOMICEM", "MACAO 2", "") is None
    assert importar_puente.buscar_precio(cur, "DOMICEM", "MACAO 2", None) is None
    assert importar_puente.buscar_precio(cur, "VMO", "CEDIS", "   ") is None


def test_buscar_precio_empresa_none_usa_el_camino_vmo():
    # Comportamiento ACTUAL (y deliberadamente conservado): cualquier empresa
    # distinta de 'DOMICEM' — incluida None, que es como llegan las filas de
    # fase no reconocida que Fase 1 igual importa si tienen firma — consulta
    # precios_vmo. Con fase None solo puede matchear una fila de fase NULL.
    cur = _conn_esquema().cursor()
    assert importar_puente.buscar_precio(cur, None, None, "Hormigon 240") == 6000.0


# ── insert_factura ───────────────────────────────────────────────────────

_NOW = "2026-08-28T10:00:00"

_ROW_BASE = {
    "id_documento": "M800099001",
    "fecha":        "2026-08-01",
    "planta":       "M8",
    "cliente":      "MACAO ALTO RESORT S.R.L, (MACAO II, ESTRUCTURA)",
    "descripcion":  "Hormigon Industrial 350 Kg/cm2",
    "cantidad":     8.0,
    "fase":         "MACAO 2",
    "empresa":      "DOMICEM",
    "archivo_pdf":  "08-01-M8-00099001.pdf",
}

_VISION_DATA = {
    "orden_compra": "OC-1", "referencia": "REF-1", "distancia": "12 KM",
    # Issue #67 — la linea `OBRA:` del papel. Es a proposito DISTINTA de la
    # fase ("MACAO 2"), que es lo que el script guarda en `obra`: si las dos
    # columnas se cruzaran, este valor lo delata.
    "obra": "CONCAVA",
    "bomba": "SI", "id_producto": "P350", "ficha": "F-77",
    "chofer": "JUAN PEREZ", "hora_salida": "08:15", "observaciones": "ninguna",
}


def test_insert_factura_fila_completa_y_pdf(tmp_path, monkeypatch):
    _pend, proc = _parchear_dirs(monkeypatch, tmp_path)
    conn = _conn_esquema()
    cur = conn.cursor()
    pdf = b"%PDF-fake-issue-19"
    inserted = importar_puente.insert_factura(
        cur, dict(_ROW_BASE), dict(_VISION_DATA), _NOW, pdf_bytes=pdf, sin_firma=False)
    assert inserted == 1
    fila = cur.execute("""SELECT id_documento, fecha, planta, orden_compra, referencia,
        distancia, cliente, obra, obra_papel, bomba, id_producto, descripcion, cantidad,
        precio_unitario, total, ficha, chofer, hora_salida, observaciones,
        archivo_pdf, empresa, fase, fecha_importacion, sin_firma, clave_resuelta
        FROM facturas WHERE id_documento = 'M800099001'""").fetchone()
    assert fila == (
        "M800099001", "2026-08-01", "M8", "OC-1", "REF-1",
        "12 KM", _ROW_BASE["cliente"],
        "MACAO 2",          # obra: el script guarda LA FASE como obra
        "CONCAVA",          # obra_papel (issue #67): la linea OBRA: del papel
        "SI", "P350", "Hormigon Industrial 350 Kg/cm2", 8.0,
        8000.0,             # precio matcheado en precios_domicem por fase
        64000.0,            # total = round(precio * cantidad, 2)
        "F-77", "JUAN PEREZ", "08:15", "ninguna",
        "08-01-M8-00099001.pdf", "DOMICEM", "MACAO 2",
        _NOW,               # fecha_importacion: el 'now' que paso el llamador
        0,
        None,               # clave_resuelta NUNCA la escribe la importacion
    )
    # El PDF de respaldo queda en procesadas:
    assert (proc / "08-01-M8-00099001.pdf").read_bytes() == pdf


def test_insert_factura_duplicado_insert_or_ignore(tmp_path, monkeypatch):
    _pend, proc = _parchear_dirs(monkeypatch, tmp_path)
    conn = _conn_esquema()
    cur = conn.cursor()
    pdf_1 = b"%PDF-original"
    assert importar_puente.insert_factura(cur, dict(_ROW_BASE), dict(_VISION_DATA), _NOW,
                                          pdf_bytes=pdf_1) == 1
    # Mismo id_documento otra vez, con otros datos: INSERT OR IGNORE — devuelve
    # 0, la fila original queda intacta y el PDF NO se reescribe.
    row_2 = dict(_ROW_BASE, cliente="OTRO CLIENTE")
    assert importar_puente.insert_factura(cur, row_2, {}, "2026-08-29T00:00:00",
                                          pdf_bytes=b"%PDF-otro") == 0
    cliente, pdf_en_disco = (
        cur.execute("SELECT cliente FROM facturas WHERE id_documento='M800099001'").fetchone()[0],
        (proc / "08-01-M8-00099001.pdf").read_bytes(),
    )
    assert cliente == _ROW_BASE["cliente"]
    assert pdf_en_disco == pdf_1
    assert cur.execute("SELECT COUNT(*) FROM facturas").fetchone()[0] == 1


def test_insert_factura_sin_firma_y_sin_pdf_bytes(tmp_path, monkeypatch):
    _pend, proc = _parchear_dirs(monkeypatch, tmp_path)
    conn = _conn_esquema()
    cur = conn.cursor()
    # sin_firma=True se persiste como 1; vision_data=None equivale a {} (todos
    # los campos de Vision quedan NULL); sin pdf_bytes NO se escribe archivo.
    row_a = dict(_ROW_BASE)
    assert importar_puente.insert_factura(cur, row_a, None, _NOW, sin_firma=True) == 1
    sin_firma, orden_compra = cur.execute(
        "SELECT sin_firma, orden_compra FROM facturas WHERE id_documento='M800099001'").fetchone()
    assert (sin_firma, orden_compra) == (1, None)
    assert not (proc / "08-01-M8-00099001.pdf").exists()

    row_b = dict(_ROW_BASE, id_documento="M800099002", archivo_pdf="08-01-M8-00099002.pdf")
    assert importar_puente.insert_factura(cur, row_b, {}, _NOW, sin_firma=False) == 1
    assert cur.execute(
        "SELECT sin_firma FROM facturas WHERE id_documento='M800099002'").fetchone()[0] == 0


# ── pendientes_revision: crear tabla, guardar, resolver ──────────────────

COLUMNAS_PENDIENTES = [
    "archivo_pdf", "id_documento", "fecha", "planta", "orden_compra",
    "referencia", "distancia", "cliente", "obra", "obra_papel", "obra_familia",
    "bomba",
    "id_producto", "descripcion", "cantidad", "precio_unitario", "total",
    "ficha", "chofer", "hora_salida", "observaciones", "empresa", "fase",
    "motivo", "fecha_pendiente",
]


def test_asegurar_tabla_pendientes_idempotente():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    importar_puente.asegurar_tabla_pendientes(cur)
    columnas = [c[1] for c in cur.execute("PRAGMA table_info(pendientes_revision)").fetchall()]
    assert columnas == COLUMNAS_PENDIENTES
    cur.execute("INSERT INTO pendientes_revision (archivo_pdf) VALUES ('x.pdf')")
    # Segunda corrida: no falla ni toca las filas existentes.
    importar_puente.asegurar_tabla_pendientes(cur)
    assert cur.execute("SELECT COUNT(*) FROM pendientes_revision").fetchone()[0] == 1


def test_guardar_pendiente_revision_guarda_fila_y_pdf(tmp_path, monkeypatch):
    pend, _proc = _parchear_dirs(monkeypatch, tmp_path)
    conn = _conn_esquema()
    cur = conn.cursor()
    pdf = b"%PDF-pendiente"
    importar_puente.guardar_pendiente_revision(
        cur, dict(_ROW_BASE), dict(_VISION_DATA), "falta firma", pdf, _NOW)
    fila = cur.execute("""SELECT archivo_pdf, id_documento, fecha, planta, orden_compra,
        referencia, distancia, cliente, obra, obra_papel, bomba, id_producto,
        descripcion, cantidad, precio_unitario, total, ficha, chofer, hora_salida,
        observaciones, empresa, fase, motivo, fecha_pendiente
        FROM pendientes_revision""").fetchone()
    assert fila == (
        "08-01-M8-00099001.pdf", "M800099001", "2026-08-01", "M8", "OC-1",
        "REF-1", "12 KM", _ROW_BASE["cliente"],
        "MACAO 2",      # obra: tambien aca el script guarda LA FASE como obra
        "CONCAVA",      # obra_papel (issue #67), distinta de la fase
        "SI", "P350", "Hormigon Industrial 350 Kg/cm2",
        8.0,
        None, None,     # precio_unitario y total: siempre NULL en pendientes
        "F-77", "JUAN PEREZ", "08:15", "ninguna",
        "DOMICEM", "MACAO 2", "falta firma",
        _NOW,           # fecha_pendiente: el 'now' que paso el llamador
    )
    assert (pend / "08-01-M8-00099001.pdf").read_bytes() == pdf
    # INSERT OR REPLACE: reintentar el mismo archivo_pdf actualiza, no duplica.
    importar_puente.guardar_pendiente_revision(
        cur, dict(_ROW_BASE), {}, "sin sello", pdf, _NOW)
    assert cur.execute("SELECT COUNT(*) FROM pendientes_revision").fetchone()[0] == 1
    assert cur.execute("SELECT motivo FROM pendientes_revision").fetchone()[0] == "sin sello"


def test_guardar_pendiente_revision_sin_pdf_bytes_no_escribe(tmp_path, monkeypatch):
    pend, _proc = _parchear_dirs(monkeypatch, tmp_path)
    conn = _conn_esquema()
    cur = conn.cursor()
    importar_puente.guardar_pendiente_revision(
        cur, dict(_ROW_BASE), {}, "falta firma", None, _NOW)
    assert cur.execute("SELECT COUNT(*) FROM pendientes_revision").fetchone()[0] == 1
    assert not (pend / "08-01-M8-00099001.pdf").exists()


# ── Issue #72 — obra_familia por el camino masivo ────────────────────────
#
# Los dos dicts del script (insert_factura y guardar_pendiente_revision)
# derivan obra_familia = core.normalizar_obra_papel(vd.get('obra')) — la
# forma agrupada de la MISMA lectura que va cruda a obra_papel. Se usa
# "Bahuuer" (variante real de OCR) para que las dos columnas queden con
# valores distintos: si se cruzan o la derivación se pierde, se ve.

def test_insert_factura_deriva_obra_familia(tmp_path, monkeypatch):
    _parchear_dirs(monkeypatch, tmp_path)
    cur = _conn_esquema().cursor()
    vd = dict(_VISION_DATA, obra="Bahuuer")
    assert importar_puente.insert_factura(cur, dict(_ROW_BASE), vd, _NOW) == 1
    assert cur.execute(
        "SELECT obra_papel, obra_familia FROM facturas WHERE id_documento='M800099001'"
    ).fetchone() == ("Bahuuer", "BAHUWER")
    # Y sin lectura de Vision no se inventa nada: cruda y familia quedan NULL
    # (normalizar_obra_papel(None) es None — no se deriva de la fase ni de
    # ningún otro campo). Va en el mismo test a propósito: la mitad de arriba
    # es la que falla sin el fix, esta mitad fija el contrato del NULL.
    row_b = dict(_ROW_BASE, id_documento="M800099002", archivo_pdf=None)
    assert importar_puente.insert_factura(cur, row_b, None, _NOW) == 1
    assert cur.execute(
        "SELECT obra_papel, obra_familia FROM facturas WHERE id_documento='M800099002'"
    ).fetchone() == (None, None)


def test_guardar_pendiente_revision_deriva_obra_familia(tmp_path, monkeypatch):
    _parchear_dirs(monkeypatch, tmp_path)
    cur = _conn_esquema().cursor()
    vd = dict(_VISION_DATA, obra="Bahuuer")
    importar_puente.guardar_pendiente_revision(
        cur, dict(_ROW_BASE), vd, "falta firma", None, _NOW)
    assert cur.execute(
        "SELECT obra_papel, obra_familia FROM pendientes_revision"
    ).fetchone() == ("Bahuuer", "BAHUWER")


def test_resolver_pendiente_borra_fila_y_pdf(tmp_path, monkeypatch):
    pend, _proc = _parchear_dirs(monkeypatch, tmp_path)
    conn = _conn_esquema()
    cur = conn.cursor()
    importar_puente.guardar_pendiente_revision(
        cur, dict(_ROW_BASE), {}, "falta firma", b"%PDF-pendiente", _NOW)
    assert (pend / "08-01-M8-00099001.pdf").exists()

    resultado = importar_puente.resolver_pendiente_si_existe(cur, "M800099001")
    assert resultado is None  # la funcion no devuelve nada
    assert cur.execute("SELECT COUNT(*) FROM pendientes_revision").fetchone()[0] == 0
    assert not (pend / "08-01-M8-00099001.pdf").exists()


def test_resolver_pendiente_inexistente_o_sin_id_no_hace_nada(tmp_path, monkeypatch):
    _parchear_dirs(monkeypatch, tmp_path)
    conn = _conn_esquema()
    cur = conn.cursor()
    importar_puente.guardar_pendiente_revision(
        cur, dict(_ROW_BASE), {}, "falta firma", b"%PDF", _NOW)
    importar_puente.resolver_pendiente_si_existe(cur, "M8_NO_EXISTE")
    importar_puente.resolver_pendiente_si_existe(cur, None)
    importar_puente.resolver_pendiente_si_existe(cur, "")
    assert cur.execute("SELECT COUNT(*) FROM pendientes_revision").fetchone()[0] == 1


def test_resolver_pendiente_pdf_bloqueado_no_propaga(tmp_path, monkeypatch):
    # Contrato documentado en el propio script: si el unlink() del PDF falla
    # (permiso de Windows, archivo abierto), NO se propaga la excepcion — el
    # DELETE de pendientes_revision ya corrio y el PDF queda huerfano
    # detectable, mejor que romper el flujo del lote completo.
    pend, _proc = _parchear_dirs(monkeypatch, tmp_path)
    conn = _conn_esquema()
    cur = conn.cursor()
    importar_puente.guardar_pendiente_revision(
        cur, dict(_ROW_BASE), {}, "falta firma", b"%PDF-bloqueado", _NOW)
    pdf_path = pend / "08-01-M8-00099001.pdf"
    handle = open(pdf_path, "rb")  # en Windows esto bloquea el unlink()
    try:
        importar_puente.resolver_pendiente_si_existe(cur, "M800099001")  # no debe lanzar
    finally:
        handle.close()
    assert cur.execute("SELECT COUNT(*) FROM pendientes_revision").fetchone()[0] == 0
    # No se asegura nada sobre el archivo: en Windows queda huerfano (unlink
    # fallo y se trago la excepcion), en otros SO el unlink pudo funcionar.


# ── integracion minima del modulo (criterio 8 del issue #19) ─────────────

def test_modulo_importa_y_progreso_txt_esta_muerto():
    # El modulo ya se importo arriba sin error (si `import importar_puente`
    # fallara, fallaria la coleccion completa de este archivo). Issue #78:
    # puente_progreso.txt esta MUERTO — anotaba "visto" en vez de
    # "importado" y enterro 9 conduces rechazados. Si la constante
    # reaparece, alguien esta restaurando ese mecanismo. El progreso real es
    # la base (tabla_donde_esta, sobre las tres tablas), y main() es
    # parametrizable para poder probar el flujo sin la API real.
    assert not hasattr(importar_puente, "PROGRESO_TXT")
    import inspect
    params = inspect.signature(importar_puente.main).parameters
    assert set(params) >= {"zip_path", "excel_path", "client"}


# ═════════════════════════════════════════════════════════════════════════
# Issue #19 — fase 2: comportamiento NUEVO tras unificar con core. Estos 4
# clientes antes daban (None, None) — iban a pendientes_revision — y ahora
# clasifican igual que core._normalizar_fase(). Son casos que la vieja tabla
# CLIENTE_FASE no cubria; el resto de los clientes no cambia (eso lo fijan
# los tests de caracterizacion de arriba, que no se tocaron en el refactor).
# ═════════════════════════════════════════════════════════════════════════

def test_unificado_macao_11_de_ocr_clasifica_como_macao_2():
    # "MACAO 11" es un error real de OCR de Vision (numeros romanos "II"
    # leidos como dos unos, visto 2026-08-26 en M800012439) que core ya
    # aprendio a manejar y la tabla local del script no.
    assert importar_puente.get_fase_empresa("MACAO 11") == ("MACAO 2", "DOMICEM")
    assert importar_puente.get_fase_empresa(
        "MACAO ALTO RESORT S.R.L., (MACAO 11, ESTRUCTURA)") == ("MACAO 2", "DOMICEM")


def test_unificado_macao_2_con_digito_clasifica():
    assert importar_puente.get_fase_empresa("MACAO 2") == ("MACAO 2", "DOMICEM")


def test_unificado_patio_de_maniobras_trb_sin_guion_clasifica():
    assert importar_puente.get_fase_empresa(
        "PATIO DE MANIOBRAS TRB") == ("PATIO DE MANIOBRAS-TRB", "DOMICEM")


def test_unificado_patio_de_maniobras_tra_sin_guion_clasifica():
    assert importar_puente.get_fase_empresa(
        "PATIO DE MANIOBRAS TRA") == ("PATIO DE MANIOBRAS-TRA", "VMO")


def test_unificado_cliente_fase_eliminada():
    # Criterio 4 del issue: la tabla local duplicada ya no existe — la unica
    # fuente de fase/empresa es core (_normalizar_fase + FASES_DOMICEM).
    assert not hasattr(importar_puente, "CLIENTE_FASE")


# ── Issue #48 (2026-09-02) — las dos fases extraen los campos del papel ──
#
# Fase 1 llamaba a verificar_firma(), cuyo prompt pide SOLO tiene_sello y
# tiene_firma, y despues pasaba un dict vacio a insert_factura. El `{}` era
# fiel — no habia nada que pasar — pero el efecto era que las 9 columnas que
# unicamente Vision puede llenar quedaban en NULL: medido, 0 de 901 facturas
# en las 8 fases que no son MACAO 2, contra 2.548-3.284 de 3.284 en MACAO 2.
#
# El bug no estaba en QUE se pasaba sino en CUAL de las dos funciones de
# Vision se llamaba, asi que los tests van a las dos cosas: el contrato de
# cada prompt, y que ningun call site vuelva a pasar un dict literal vacio.

# Issue #67 (2026-09-07) suma "obra": el prompt NO la pedia, asi que el
# camino masivo no podia guardar la linea `OBRA:` ni queriendo. Sacarla de
# aca vuelve a dejar obra_papel en NULL para todo lote nuevo, en silencio.
_CAMPOS_SOLO_VISION = ("orden_compra", "referencia", "distancia", "obra",
                       "bomba", "id_producto", "ficha", "chofer",
                       "hora_salida", "observaciones")


class _BloqueTexto:
    type = "text"

    def __init__(self, text):
        self.text = text


class _RespuestaFalsa:
    def __init__(self, text):
        self.content = [_BloqueTexto(text)]


class _MessagesFalso:
    def __init__(self, padre):
        self._padre = padre

    def create(self, **kw):
        self._padre.llamadas.append(kw)
        return _RespuestaFalsa('{"tiene_sello": true, "tiene_firma": true}')


class _ClienteFalso:
    """Cliente Anthropic de mentira: no llama a nada, solo captura el prompt.
    Permite verificar el CONTRATO de cada funcion de Vision sin gastar una
    llamada real ni depender de la red."""

    def __init__(self):
        self.llamadas = []
        self.messages = _MessagesFalso(self)

    @property
    def ultimo_prompt(self):
        return self.llamadas[-1]["messages"][0]["content"][1]["text"]


def test_vision_extract_pide_los_diez_campos_que_solo_el_papel_tiene():
    cli = _ClienteFalso()
    importar_puente.vision_extract(cli, b"%PDF-fake")
    prompt = cli.ultimo_prompt
    # Se mira SOLO el bloque JSON (hasta la llave de cierre), no el prompt
    # entero: desde el issue #67 al final va core.EST_OBRA_PAPEL_PROMPT, que
    # menciona "obra" en prosa. Buscando en todo el texto, sacar la clave del
    # esquema no rompia este test — o sea que no guardaba nada. Comprobado
    # mutando el prompt, no supuesto.
    esquema = prompt.split("}")[0]
    faltan = [c for c in _CAMPOS_SOLO_VISION if f'"{c}"' not in esquema]
    assert not faltan, f"vision_extract dejo de pedir: {faltan}"
    assert "tiene_sello" in esquema and "tiene_firma" in esquema


def test_vision_extract_pide_la_orientacion():
    """Si al_reves se cae del esquema, el modelo no lo devuelve y el masivo
    vuelve a entrar los dados vuelta de cabeza sin que nada avise."""
    cli = _ClienteFalso()
    importar_puente.vision_extract(cli, b"%PDF-fake")
    assert '"al_reves"' in cli.ultimo_prompt.split("}")[0]


class _RespuestaDeLectura:
    # Nombres propios: _RespuestaFalsa, _RespuestaConGuion y
    # _ClienteConGuion se redefinen mas abajo con otra firma.
    def __init__(self, text):
        self.content = [_BloqueTexto(text)]


class _ClienteDeLectura:
    """Devuelve las respuestas en orden y guarda el PDF que recibio cada
    llamada, para ver si la relectura fue con el PDF rotado."""

    def __init__(self, respuestas):
        import json as _json
        self._respuestas = [_json.dumps(r) for r in respuestas]
        self.pdfs = []
        self.messages = self

    def create(self, **kw):
        import base64 as _b64
        self.pdfs.append(_b64.standard_b64decode(kw["messages"][0]["content"][0]["source"]["data"]))
        return _RespuestaDeLectura(self._respuestas.pop(0))


def _pdf_una_pagina():
    import fitz
    doc = fitz.open()
    doc.new_page()
    datos = doc.tobytes()
    doc.close()
    return datos


def test_vision_extract_relee_rotado_y_lo_avisa():
    """REGRESION: los 4 dados vuelta conocidos entraron por el masivo, que no
    preguntaba la orientacion. La segunda lectura va con la pagina a 180 y
    el resultado lleva `_rotado` para que el doble-chequeo mire lo mismo."""
    import fitz
    cli = _ClienteDeLectura([{"al_reves": True, "obra": None},
                            {"al_reves": False, "obra": "EXTERIORES1111"}])
    datos = importar_puente.vision_extract(cli, _pdf_una_pagina())
    assert datos["obra"] == "EXTERIORES1111"
    assert datos["_rotado"] is True
    assert len(cli.pdfs) == 2
    assert fitz.open(stream=cli.pdfs[1], filetype="pdf")[0].rotation == 180


def test_vision_extract_derecho_no_paga_una_segunda_llamada():
    cli = _ClienteDeLectura([{"al_reves": False, "obra": "LIDOMI"}])
    datos = importar_puente.vision_extract(cli, _pdf_una_pagina())
    assert len(cli.pdfs) == 1
    assert "_rotado" not in datos


def test_vision_extract_rota_una_sola_vez():
    cli = _ClienteDeLectura([{"al_reves": True}, {"al_reves": True}])
    importar_puente.vision_extract(cli, _pdf_una_pagina())
    assert len(cli.pdfs) == 2


def test_verificar_firma_es_el_prompt_liviano_y_no_pide_esos_campos():
    """Documenta por que existen las dos funciones. verificar_firma es el
    doble-chequeo barato: si algun dia empieza a pedir los 11 campos, deja de
    ser barato y este test avisa."""
    cli = _ClienteFalso()
    importar_puente.verificar_firma(cli, b"%PDF-fake")
    prompt = cli.ultimo_prompt
    pide_de_mas = [c for c in _CAMPOS_SOLO_VISION if c in prompt]
    assert not pide_de_mas, f"verificar_firma se volvio pesado, pide: {pide_de_mas}"
    assert "tiene_sello" in prompt and "tiene_firma" in prompt
    assert cli.llamadas[-1]["max_tokens"] < 500


def test_ningun_call_site_pasa_un_dict_vacio_como_vision_data():
    """Regresion del issue #48. Antes, la rama no-MACAO 2 de main() llamaba a
    insert_factura(cur, row, {}, ...) y a guardar_pendiente_revision(cur, row,
    {}, ...). Como el dict era literal y vacio, las 9 columnas quedaban en
    NULL sin que nada fallara.

    Se chequea sobre el AST y no con un grep para que sobreviva al formato:
    lo que se afirma es que el argumento vision_data es una VARIABLE, no un
    diccionario escrito a mano."""
    import ast
    ruta = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts", "importar_puente.py")
    arbol = ast.parse(open(ruta, encoding="utf-8").read())
    objetivo = {"insert_factura": 2, "guardar_pendiente_revision": 2}  # nombre -> indice de vision_data
    ofensores = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call) or not isinstance(nodo.func, ast.Name):
            continue
        idx = objetivo.get(nodo.func.id)
        if idx is None or len(nodo.args) <= idx:
            continue
        arg = nodo.args[idx]
        if isinstance(arg, ast.Dict) and not arg.keys:
            ofensores.append(f"{nodo.func.id}() en la linea {nodo.lineno} recibe {{}}")
    assert not ofensores, (
        "vision_data no puede ser un dict literal vacio — las 9 columnas de "
        "Vision quedarian en NULL en silencio:\n  " + "\n  ".join(ofensores))


# ═════════════════════════════════════════════════════════════════════════
# Issue #78 (2026-09-09) — lote OneDrive 09-2026: Excel nuevo por cabecera,
# fase antes de Vision, muerte de puente_progreso.txt y resumen que
# reconcilia. Fixtures chicos armados aca mismo (xlwt para .xls, openpyxl
# para .xlsx, zipfile para el ZIP) — nunca se toca el lote real.
# ═════════════════════════════════════════════════════════════════════════

import zipfile
from datetime import date

import pytest

CABECERAS_NUEVAS = ("Conduce", "Fecha", "Referencia", "Cliente", "Producto",
                    "Cant.", "Unidad", "Planta", "Anotaciones", "Codigo")
CABECERAS_VIEJAS = ("Conduce", "Fecha", "Cliente", "Producto", "Cant.",
                    "Planta", "Codigo")

_CLIENTE_MACAO2 = "MACAO ALTO RESORT S.R.L, (MACAO II, ESTRUCTURA)"
_CLIENTE_M4     = "INVERSIONES VIGAFILI SRL "  # cliente real de M4: no normaliza a ninguna fase


def _escribir_xls(path, filas, cabeceras=CABECERAS_NUEVAS, con_hoja_pivote=True,
                  nombre_hoja="COnduces"):
    """Un .xls (BIFF) como el real: con la hoja de tabla dinamica PRIMERO y
    la de datos despues, y las fechas como celdas de fecha de Excel."""
    import xlwt
    wb = xlwt.Workbook()
    if con_hoja_pivote:
        ws0 = wb.add_sheet("Sheet1")
        ws0.write(0, 0, "Months (Fecha)")
        ws0.write(0, 1, "(Multiple Items)")
        ws0.write(2, 0, "Sum of Cant.")
    ws = wb.add_sheet(nombre_hoja)
    estilo_fecha = xlwt.easyxf(num_format_str="M/D/YY")
    for c, h in enumerate(cabeceras):
        ws.write(0, c, h)
    for r, fila in enumerate(filas, 1):
        for c, v in enumerate(fila):
            if hasattr(v, "strftime"):
                ws.write(r, c, v, estilo_fecha)
            else:
                ws.write(r, c, v)
    wb.save(str(path))
    return path


def _escribir_xlsx(path, filas, cabeceras=CABECERAS_VIEJAS):
    """Un .xlsx con el formato viejo de 7 columnas."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "COnduces"
    ws.append(list(cabeceras))
    for fila in filas:
        ws.append(list(fila))
    wb.save(str(path))
    return path


_FILA_M8 = ("M800099001", date(2026, 8, 20), "/", _CLIENTE_MACAO2,
            "Hormigon Industrial 350 Kg/cm2", 8, "EDU-633", "M8 Macao", "",
            "08-20-M8-99001.pdf")
_FILA_M4 = ("M400000123", date(2026, 8, 19), "/", _CLIENTE_M4,
            "MORTERO PARA FINO FC 140 KG/CM2", 7, "EDU-761", "M4 Punta Cana",
            "", "08-19-M4-123.pdf")


# ── load_excel por cabecera (issue #78, punto 1) ─────────────────────────

def test_load_excel_xls_nuevo_por_cabecera_y_ambos_indices(tmp_path):
    """El .xls de 10 columnas con la hoja pivote primero: los campos salen de
    SUS columnas (con el mapeo posicional viejo, cliente seria '/' y codigo
    'EDU-633'), la fecha serial de Excel sale como YYYY-MM-DD, y el mismo
    registro queda indexado por Codigo y por Conduce."""
    xls = _escribir_xls(tmp_path / "COnduces.xls", [_FILA_M8, _FILA_M4])
    por_codigo, por_id = importar_puente.load_excel(xls)

    r = por_codigo["08-20-m8-99001.pdf"]
    assert r["id_documento"] == "M800099001"
    assert r["cliente"] == _CLIENTE_MACAO2          # NO la Referencia "/"
    assert r["codigo"] == "08-20-m8-99001.pdf"      # NO la Unidad "EDU-633"
    assert r["fecha"] == "2026-08-20"
    assert r["descripcion"] == "Hormigon Industrial 350 Kg/cm2"
    assert r["cantidad"] == 8.0
    assert (r["fase"], r["empresa"]) == ("MACAO 2", "DOMICEM")
    assert por_id["M800099001"] is r                # mismo registro, dos llaves

    m4 = por_id["M400000123"]
    assert (m4["fase"], m4["empresa"]) == (None, None)  # M4: fase desconocida


def test_load_excel_xlsx_viejo_sigue_entrando(tmp_path):
    """El formato historico de 7 columnas (.xlsx) se lee igual — por
    cabecera, no por extension ni por posicion."""
    xlsx = _escribir_xlsx(tmp_path / "viejo.xlsx", [
        ("M300054578", date(2026, 4, 18), _CLIENTE_MACAO2,
         "Hormigon X", 7, "M3 Macao", "04-18-M3-54578.pdf"),
    ])
    por_codigo, por_id = importar_puente.load_excel(xlsx)
    r = por_codigo["04-18-m3-54578.pdf"]
    assert r["id_documento"] == "M300054578"
    assert r["cliente"] == _CLIENTE_MACAO2
    assert r["fecha"] == "2026-04-18"
    assert por_id["M300054578"] is r


def test_load_excel_columna_faltante_error_claro(tmp_path):
    """Sin la columna Codigo en NINGUNA hoja, el error dice que falta y en
    que hoja — no un IndexError ni un mapeo silenciosamente corrido."""
    sin_codigo = tuple(h for h in CABECERAS_NUEVAS if h != "Codigo")
    xls = _escribir_xls(tmp_path / "roto.xls",
                        [_FILA_M8[:-1]], cabeceras=sin_codigo)
    with pytest.raises(ValueError) as exc:
        importar_puente.load_excel(xls)
    assert "Codigo" in str(exc.value)
    assert "COnduces" in str(exc.value)  # la hoja mas parecida, nombrada


def test_load_excel_elige_la_hoja_por_cabeceras_no_la_primera(tmp_path):
    """La hoja de tabla dinamica viene PRIMERO en el .xls real. Elegir 'la
    activa' o 'la primera' — lo que hacia el codigo viejo y lo que el spec
    del issue #78 no menciona — leeria el pivote y daria 0 registros."""
    xls = _escribir_xls(tmp_path / "COnduces.xls", [_FILA_M8])
    por_codigo, _por_id = importar_puente.load_excel(xls)
    assert len(por_codigo) == 1


def test_buscar_fila_excel_cae_al_indice_por_id(tmp_path):
    """El camino de los recuperados: un nombre a la convencion que no esta
    letra a letra en la columna Codigo entra igual, reconstruyendo el id
    (planta + numero a 8 digitos) contra el indice por Conduce."""
    xls = _escribir_xls(tmp_path / "COnduces.xls", [_FILA_M8])
    por_codigo, por_id = importar_puente.load_excel(xls)
    # Mismo conduce, nombre distinto del Codigo (p.ej. renombrado con la
    # fecha de otro dia por recuperar_nombres.py):
    fila = importar_puente.buscar_fila_excel(por_codigo, por_id, "08-21-M8-99001.pdf")
    assert fila is not None and fila["id_documento"] == "M800099001"
    assert importar_puente.buscar_fila_excel(por_codigo, por_id, "99-99-X9-1.pdf") is None


# ── infraestructura de integracion: BD en archivo, ZIP y clientes falsos ──

def _crear_db_archivo(tmp_path):
    """La BD minima que main() necesita, en un ARCHIVO (main abre DB_PATH por
    su cuenta): facturas + las 2 tablas de precios con un seed conocido. Las
    tablas de pendientes las crea main() via asegurar_tabla_pendientes."""
    db = tmp_path / "estimaciones.db"
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE facturas (
        id_documento TEXT PRIMARY KEY, fecha DATE, planta TEXT,
        orden_compra TEXT, referencia TEXT, distancia TEXT, cliente TEXT,
        obra TEXT, obra_papel TEXT, obra_familia TEXT, bomba TEXT,
        id_producto TEXT, descripcion TEXT,
        cantidad REAL, precio_unitario REAL, total REAL, ficha TEXT,
        chofer TEXT, hora_salida TEXT, observaciones TEXT, archivo_pdf TEXT,
        empresa TEXT, fase TEXT, fecha_importacion DATETIME,
        sin_firma INTEGER DEFAULT 0, clave_resuelta TEXT,
        aprobado_manual INTEGER DEFAULT 0, aprobado_por TEXT,
        aprobado_motivo TEXT, aprobado_fecha TEXT, motivo_bloqueo TEXT)""")
    conn.execute("""CREATE TABLE precios_domicem (
        fase TEXT, codigo TEXT, descripcion TEXT, precio_unitario REAL,
        PRIMARY KEY (fase, codigo))""")
    conn.execute("""CREATE TABLE precios_vmo (
        codigo TEXT, fase TEXT, descripcion TEXT, precio_unitario REAL,
        PRIMARY KEY (codigo, fase))""")
    conn.execute("INSERT INTO precios_domicem VALUES ('MACAO 2','D-350','Hormigon Industrial 350 Kg/cm2',8000.0)")
    conn.commit()
    conn.close()
    return db


def _escribir_zip(tmp_path, entradas, nombre="lote.zip"):
    """entradas: {nombre_en_el_zip: bytes}."""
    ruta = tmp_path / nombre
    with zipfile.ZipFile(ruta, "w") as zf:
        for nombre_zip, contenido in entradas.items():
            zf.writestr(nombre_zip, contenido)
    return ruta


def _preparar_entorno(tmp_path, monkeypatch):
    """Redirige BD, directorios de PDFs y el log de errores a tmp_path, y
    anula la pausa de rate limit. Devuelve la ruta de la BD."""
    db = _crear_db_archivo(tmp_path)
    monkeypatch.setattr(importar_puente, "DB_PATH", db)
    monkeypatch.setattr(importar_puente, "ERRORES_TXT", tmp_path / "errores.txt")
    _parchear_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr(importar_puente.time, "sleep", lambda _s: None)
    return db


class _MensajesConGuion:
    def __init__(self, padre):
        self._padre = padre

    def create(self, **kw):
        self._padre.llamadas += 1
        if self._padre.respuesta is None:
            raise AssertionError(
                "Vision NO debia llamarse en esta rama — esta llamada habria "
                "pagado la API real")
        return _RespuestaFalsa(self._padre.respuesta)


class _ClienteConGuion:
    """Cliente Anthropic falso: devuelve siempre el mismo JSON y cuenta las
    llamadas. Con respuesta None, EXPLOTA — el mock que prueba que una rama
    no paga Vision (regla 3 del brief del issue #78)."""

    def __init__(self, respuesta=None):
        self.respuesta = respuesta
        self.llamadas = 0
        self.messages = _MensajesConGuion(self)


# ── fase desconocida se salta ANTES de Vision (issue #78, punto 2) ───────

def test_fase_desconocida_no_paga_vision_ni_deja_fila(tmp_path, monkeypatch, capsys):
    """Un PDF cuyo cliente del Excel no normaliza a ninguna fase (M4) se
    cuenta como fase_desconocida SIN llamar a Vision y sin fila en ninguna
    tabla. El cliente falso explota si algo lo llama; ademas el contador de
    vision_error tiene que quedar en 0 — si la guarda de fase se saca, el
    documento entra al loop de Vision y una de las dos cosas delata."""
    db = _preparar_entorno(tmp_path, monkeypatch)
    xls = _escribir_xls(tmp_path / "COnduces.xls", [_FILA_M4])
    zip_path = _escribir_zip(tmp_path, {
        "19-8-2026-M4/08-19-M4-123.pdf": b"%PDF-m4",
        "19-8-2026-M4/foto.jpeg": b"\xff\xd8jpeg",   # no_pdf, para que el total no sea trivial
    })

    cliente = _ClienteConGuion(respuesta=None)  # explota si se llama
    ret = importar_puente.main(zip_path, xls, client=cliente)

    assert ret == 0
    assert cliente.llamadas == 0
    salida = capsys.readouterr().out
    assert "fase_desconocida: 1" in salida
    assert "vision_error:     0" in salida
    assert "08-19-M4-123.pdf" in salida          # listado, no solo contado
    assert "La cuenta cierra: 2 = 2" in salida
    conn = sqlite3.connect(db)
    for tabla in ("facturas", "pendientes_revision", "pendiente_descartado"):
        assert conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0] == 0, tabla
    conn.close()


# ── el resumen reconcilia o el exit code lo grita (issue #78, punto 4) ───

def test_resumen_descuadrado_exit_distinto_de_cero(capsys):
    stats = {c: 0 for c in importar_puente.CATEGORIAS}
    stats["sin_firma_ok"] = 0
    listados = {c: [] for c in importar_puente.CATEGORIAS}
    stats["ok"] = 2
    # 2 contados contra 3 archivos: no cierra.
    assert importar_puente.resumen_final(stats, listados, 3) != 0
    assert "NO CIERRA" in capsys.readouterr().out
    # Y con la cuenta cerrada, exit 0:
    assert importar_puente.resumen_final(stats, listados, 2) == 0


def test_resumen_lista_nombres_de_toda_categoria_no_ok(capsys):
    stats = {c: 0 for c in importar_puente.CATEGORIAS}
    stats["sin_firma_ok"] = 0
    listados = {c: [] for c in importar_puente.CATEGORIAS}
    for categoria, nombre in (("sin_excel", "x1.pdf"), ("fase_desconocida", "x2.pdf"),
                              ("ya_registrado", "x3.pdf (en pendientes_revision)"),
                              ("rechazado", "x4.pdf (sin sello)"),
                              ("vision_error", "x5.pdf (timeout)"), ("no_pdf", "x6.jpeg")):
        stats[categoria] = 1
        listados[categoria].append(nombre)
    stats["ok"] = 1
    stats["duplicado"] = 1
    assert importar_puente.resumen_final(stats, listados, 8) == 0
    salida = capsys.readouterr().out
    for nombre in ("x1.pdf", "x2.pdf", "x3.pdf", "x4.pdf", "x5.pdf", "x6.jpeg"):
        assert nombre in salida, nombre


# ── rechazado -> borrar de pendientes -> re-corrida lo reintenta ─────────
# (issue #78, punto 3 y criterio 5 — la regresion contra puente_progreso.txt)

def test_rechazado_se_reintenta_solo_si_se_borra_de_pendientes(tmp_path, monkeypatch, capsys):
    """Corrida 1: un MACAO 2 sin sello queda rechazado en pendientes_revision.
    Corrida 2 (mismo lote): CERO llamadas a Vision — ya esta registrado.
    Corrida 3, tras borrar su fila de pendientes_revision: se reintenta, paga
    Vision de nuevo y esta vez (con sello) queda en facturas.

    Esta es la regresion del issue #78 contra puente_progreso.txt: con el
    progreso por archivo restaurado, la corrida 3 lo saltearia ('visto') y el
    documento quedaria enterrado para siempre — asi se perdieron los 9."""
    db = _preparar_entorno(tmp_path, monkeypatch)
    xls = _escribir_xls(tmp_path / "COnduces.xls", [_FILA_M8])
    zip_path = _escribir_zip(tmp_path, {"08-20-M8-99001.pdf": b"%PDF-m8"})

    # Corrida 1 — Vision dice sin sello: rechazado.
    cliente_1 = _ClienteConGuion('{"tiene_sello": false, "tiene_firma": true}')
    assert importar_puente.main(zip_path, xls, client=cliente_1) == 0
    assert cliente_1.llamadas >= 1
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM pendientes_revision").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM facturas").fetchone()[0] == 0
    conn.close()

    # Corrida 2 — mismo lote: cero Vision, el rechazado NO se repaga.
    cliente_2 = _ClienteConGuion(respuesta=None)  # explota si se llama
    assert importar_puente.main(zip_path, xls, client=cliente_2) == 0
    assert cliente_2.llamadas == 0
    assert "ya_registrado:    1" in capsys.readouterr().out

    # Se borra la fila (la senal humana de "reintentalo").
    conn = sqlite3.connect(db)
    conn.execute("DELETE FROM pendientes_revision WHERE id_documento = 'M800099001'")
    conn.commit()
    conn.close()

    # Corrida 3 — se reintenta y con sello entra a facturas.
    cliente_3 = _ClienteConGuion('{"tiene_sello": true, "tiene_firma": true}')
    assert importar_puente.main(zip_path, xls, client=cliente_3) == 0
    assert cliente_3.llamadas >= 1
    conn = sqlite3.connect(db)
    assert conn.execute(
        "SELECT COUNT(*) FROM facturas WHERE id_documento = 'M800099001'").fetchone()[0] == 1
    conn.close()


def test_recorrida_inmediata_duplicado_sin_vision(tmp_path, monkeypatch, capsys):
    """Criterio 4 del issue #78: re-correr el mismo lote justo despues de
    importar no paga una sola llamada — el importado es duplicado contra
    facturas, chequeado ANTES de Vision."""
    db = _preparar_entorno(tmp_path, monkeypatch)
    xls = _escribir_xls(tmp_path / "COnduces.xls", [_FILA_M8])
    zip_path = _escribir_zip(tmp_path, {"08-20-M8-99001.pdf": b"%PDF-m8"})

    cliente_1 = _ClienteConGuion('{"tiene_sello": true, "tiene_firma": true}')
    assert importar_puente.main(zip_path, xls, client=cliente_1) == 0
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM facturas").fetchone()[0] == 1
    conn.close()

    cliente_2 = _ClienteConGuion(respuesta=None)
    assert importar_puente.main(zip_path, xls, client=cliente_2) == 0
    assert cliente_2.llamadas == 0
    assert "duplicado:        1" in capsys.readouterr().out
