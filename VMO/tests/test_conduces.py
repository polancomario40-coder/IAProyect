"""
Primera suite de tests del modulo Conduces (importar.py, importar_xls.py,
pagar.py, reportes en core.py) — tenia cero cobertura hasta la Fase 1 de
integridad de datos/seguridad (ver CLAUDE.md, historial de decisiones).

Correr con: python -m pytest tests/test_conduces.py -v
"""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import core  # noqa: E402
import importar  # noqa: E402
import importar_xls  # noqa: E402
import pagar  # noqa: E402
import _cache_reportes  # noqa: E402
from _cache_reportes import limpiar_cache_reportes  # noqa: E402


@pytest.fixture(autouse=True)
def _aislar_cache_reportes(tmp_path, monkeypatch):
    """CRITICO: importar.importar()/importar_xls.importar()/pagar.pagar()
    llaman a limpiar_cache_reportes() cuando hay cambios reales — sin esto,
    los tests borran los reportes/facturas REALES del proyecto (paso de
    verdad una vez, ver CLAUDE.md 2026-08-21). autouse=True para que
    NINGUN test futuro en este archivo pueda repetir el error por olvido."""
    monkeypatch.setattr(_cache_reportes, "REPORTES_DIR", str(tmp_path / "reportes_test"))
    monkeypatch.setattr(_cache_reportes, "FACTURAS_DIR", str(tmp_path / "facturas_test"))


SCHEMA_CONDUCES = """
    CREATE TABLE conduces (
        id_conduce    TEXT PRIMARY KEY,
        fecha         DATE,
        producto      TEXT,
        compania      TEXT,
        precio        REAL,
        cantidad      REAL,
        almacen       TEXT,
        estado        TEXT DEFAULT 'no_pagado',
        id_transporte TEXT
    )
"""


@pytest.fixture
def db_conduces(tmp_path):
    """BD sqlite minima con el esquema real de conduces, aislada de la BD
    de produccion."""
    db_path = tmp_path / "conduces_test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(SCHEMA_CONDUCES)
    conn.commit()
    conn.close()
    return str(db_path)


# ── Hijo 1 — validacion de ID unificada (minimo 4, sin tope) ──

def test_importar_csv_rechaza_id_menor_a_4(tmp_path, db_conduces, monkeypatch):
    monkeypatch.setattr(importar, "DB_PATH", db_conduces)
    csv_path = tmp_path / "conduces.csv"
    csv_path.write_text(
        "id_conduce,fecha,producto,compania,precio,cantidad\n"
        "C12,2026-06-01,ARENA,SUPLIDOR,100,10\n",  # 3 caracteres
        encoding="utf-8",
    )
    importar.importar(str(csv_path))
    conn = sqlite3.connect(db_conduces)
    assert conn.execute("SELECT COUNT(*) FROM conduces").fetchone()[0] == 0
    conn.close()


def test_importar_csv_acepta_id_de_4(tmp_path, db_conduces, monkeypatch):
    monkeypatch.setattr(importar, "DB_PATH", db_conduces)
    csv_path = tmp_path / "conduces.csv"
    csv_path.write_text(
        "id_conduce,fecha,producto,compania,precio,cantidad\n"
        "C123,2026-06-01,ARENA,SUPLIDOR,100,10\n",  # 4 caracteres exactos
        encoding="utf-8",
    )
    importar.importar(str(csv_path))
    conn = sqlite3.connect(db_conduces)
    assert conn.execute("SELECT COUNT(*) FROM conduces").fetchone()[0] == 1
    conn.close()


def test_importar_csv_acepta_id_largo_sin_tope(tmp_path, db_conduces, monkeypatch):
    monkeypatch.setattr(importar, "DB_PATH", db_conduces)
    id_largo = "C" * 20  # antes se rechazaba todo lo mayor a 10 caracteres
    csv_path = tmp_path / "conduces.csv"
    csv_path.write_text(
        f"id_conduce,fecha,producto,compania,precio,cantidad\n"
        f"{id_largo},2026-06-01,ARENA,SUPLIDOR,100,10\n",
        encoding="utf-8",
    )
    importar.importar(str(csv_path))
    conn = sqlite3.connect(db_conduces)
    assert conn.execute("SELECT id_conduce FROM conduces").fetchone()[0] == id_largo
    conn.close()


class _FakeSheet:
    def __init__(self, rows):
        self._rows = rows
        self.nrows = len(rows)

    def row_values(self, i):
        return self._rows[i]


class _FakeWorkbook:
    def __init__(self, rows):
        self._sheet = _FakeSheet(rows)

    def sheets(self):
        return [self._sheet]


def _fila_xls(referencia, compania="SUPLIDOR", producto="ARENA", grupo=""):
    # Indices: 3=referencia, 4=fecha, 6=almacen, 9=producto, 10=grupo,
    # 12=entradas, 15=xcosto, 18=compania (ver importar_xls.py)
    row = [""] * 19
    row[3] = referencia
    row[4] = ""
    row[6] = "ALMACEN1"
    row[9] = producto
    row[10] = grupo
    row[12] = 10
    row[15] = 100.0
    row[18] = compania
    return row


def test_importar_xls_rechaza_id_menor_a_4(tmp_path, db_conduces, monkeypatch):
    monkeypatch.setattr(importar_xls, "DB_PATH", db_conduces)
    filas = [_fila_xls("header")] + [_fila_xls("C12")]  # 3 caracteres
    monkeypatch.setattr(importar_xls.xlrd, "open_workbook", lambda archivo: _FakeWorkbook(filas))
    importar_xls.importar("archivo_falso.xls")
    conn = sqlite3.connect(db_conduces)
    assert conn.execute("SELECT COUNT(*) FROM conduces").fetchone()[0] == 0
    conn.close()


def test_importar_xls_acepta_id_de_4(tmp_path, db_conduces, monkeypatch):
    monkeypatch.setattr(importar_xls, "DB_PATH", db_conduces)
    filas = [_fila_xls("header")] + [_fila_xls("C123")]  # 4 caracteres
    monkeypatch.setattr(importar_xls.xlrd, "open_workbook", lambda archivo: _FakeWorkbook(filas))
    importar_xls.importar("archivo_falso.xls")
    conn = sqlite3.connect(db_conduces)
    assert conn.execute("SELECT COUNT(*) FROM conduces").fetchone()[0] == 1
    conn.close()


# ── Hijo 2 — auditoria minima de pagos ──

def test_pagar_migracion_agrega_columna_fecha_pago(db_conduces):
    conn = sqlite3.connect(db_conduces)
    columnas_antes = [c[1] for c in conn.execute("PRAGMA table_info(conduces)").fetchall()]
    assert "fecha_pago" not in columnas_antes
    pagar._asegurar_columna_fecha_pago(conn)
    conn.commit()
    columnas_despues = [c[1] for c in conn.execute("PRAGMA table_info(conduces)").fetchall()]
    assert "fecha_pago" in columnas_despues
    conn.close()


def test_pagar_migracion_es_idempotente(db_conduces):
    conn = sqlite3.connect(db_conduces)
    pagar._asegurar_columna_fecha_pago(conn)
    pagar._asegurar_columna_fecha_pago(conn)  # correr 2 veces no debe fallar
    conn.commit()
    conn.close()


def test_pagar_conduce_nuevo_setea_fecha_pago(db_conduces, monkeypatch):
    monkeypatch.setattr(pagar, "DB_PATH", db_conduces)
    conn = sqlite3.connect(db_conduces)
    conn.execute(
        "INSERT INTO conduces (id_conduce, fecha, producto, compania, precio, cantidad) "
        "VALUES ('C0001','2026-06-01','ARENA','SUPLIDOR',100,10)"
    )
    conn.commit()
    conn.close()

    pagar.pagar(["C0001"])

    conn = sqlite3.connect(db_conduces)
    row = conn.execute("SELECT estado, fecha_pago FROM conduces WHERE id_conduce='C0001'").fetchone()
    conn.close()
    assert row[0] == "pagado"
    assert row[1] is not None


def test_pagar_conduce_ya_pagado_no_toca_fecha_pago(db_conduces, monkeypatch):
    monkeypatch.setattr(pagar, "DB_PATH", db_conduces)
    conn = sqlite3.connect(db_conduces)
    pagar._asegurar_columna_fecha_pago(conn)
    conn.execute(
        "INSERT INTO conduces (id_conduce, fecha, producto, compania, precio, cantidad, estado, fecha_pago) "
        "VALUES ('C0002','2026-06-01','ARENA','SUPLIDOR',100,10,'pagado','2026-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()

    pagar.pagar(["C0002"])  # re-marcar un conduce ya pagado

    conn = sqlite3.connect(db_conduces)
    row = conn.execute("SELECT fecha_pago FROM conduces WHERE id_conduce='C0002'").fetchone()
    conn.close()
    assert row[0] == "2026-01-01T00:00:00"  # no se sobreescribio


# ── Hijo 3 — bug financiero (precio x cantidad, no solo precio) ──

def _db_con_conduce_cantidad_multiple(path):
    conn = sqlite3.connect(path)
    conn.execute(SCHEMA_CONDUCES)
    conn.execute(
        "INSERT INTO conduces (id_conduce, fecha, producto, compania, precio, cantidad, estado) "
        "VALUES ('C0003','2026-06-01','ARENA','SUPLIDOR A',100,5,'no_pagado')"
    )
    conn.commit()
    conn.close()


def test_generar_reporte_monto_pendiente_es_precio_por_cantidad(tmp_path, monkeypatch):
    db_path = tmp_path / "conduces.db"
    _db_con_conduce_cantidad_multiple(str(db_path))
    monkeypatch.setattr(core, "DB_PATH", str(db_path))
    monkeypatch.setattr(core, "REPORTES_DIR", str(tmp_path))

    resultado = core.generar_reporte()
    import json
    data = json.loads(resultado)
    filepath = os.path.join(str(tmp_path), data["filename"])
    html = open(filepath, encoding="utf-8").read()
    assert "$500.00" in html  # 100 x 5, no $100.00 (el bug viejo)


def test_generar_reporte_compania_monto_pendiente_es_precio_por_cantidad(tmp_path, monkeypatch):
    db_path = tmp_path / "conduces.db"
    _db_con_conduce_cantidad_multiple(str(db_path))
    monkeypatch.setattr(core, "DB_PATH", str(db_path))
    monkeypatch.setattr(core, "REPORTES_DIR", str(tmp_path))

    resultado = core.generar_reporte_compania("SUPLIDOR A")
    import json
    data = json.loads(resultado)
    filepath = os.path.join(str(tmp_path), data["filename"])
    html = open(filepath, encoding="utf-8").read()
    assert "$500.00" in html


def test_slug_compania_sanea_caracteres_especiales():
    assert core._slug_compania("CONSTRUCTORA REBESA, SRL").startswith("CONSTRUCTORA_REBESA_SRL_")
    assert core._slug_compania("O'Brien & Asociados").startswith("O_Brien_Asociados_")
    assert core._slug_compania("").startswith("x_")


def test_slug_compania_no_colisiona_entre_compania_distintas():
    # Codex encontro esto en la 3ra ronda de verificacion: "ACME, SRL" y
    # "ACME SRL" sanean al mismo texto base — sin el sufijo de hash, la
    # cache de reportes le serviria el reporte de una compania a la otra.
    assert core._slug_compania("ACME, SRL") != core._slug_compania("ACME SRL")


# ── Hijo 3 — invalidacion de cache ──

def test_limpiar_cache_reportes_borra_html(tmp_path, monkeypatch):
    reportes_dir = tmp_path / "reportes"
    facturas_dir = tmp_path / "facturas"
    reportes_dir.mkdir()
    facturas_dir.mkdir()
    (reportes_dir / "reporte_viejo.html").write_text("viejo", encoding="utf-8")
    (facturas_dir / "factura_vieja.html").write_text("vieja", encoding="utf-8")
    (reportes_dir / "no_tocar.txt").write_text("no es html", encoding="utf-8")

    import _cache_reportes
    monkeypatch.setattr(_cache_reportes, "REPORTES_DIR", str(reportes_dir))
    monkeypatch.setattr(_cache_reportes, "FACTURAS_DIR", str(facturas_dir))

    borrados = limpiar_cache_reportes()

    assert borrados == 2
    assert not (reportes_dir / "reporte_viejo.html").exists()
    assert not (facturas_dir / "factura_vieja.html").exists()
    assert (reportes_dir / "no_tocar.txt").exists()  # no borra archivos no-html


def test_limpiar_cache_reportes_no_falla_si_directorio_no_existe(tmp_path, monkeypatch):
    import _cache_reportes
    monkeypatch.setattr(_cache_reportes, "REPORTES_DIR", str(tmp_path / "no_existe"))
    monkeypatch.setattr(_cache_reportes, "FACTURAS_DIR", str(tmp_path / "tampoco_existe"))
    assert limpiar_cache_reportes() == 0  # no lanza excepcion


# ── Issue #31 — un precio NULL no vale $0, vale un numero que no sabemos ──
#
# Hasta este issue, `(precio or 0) * (cantidad or 0)` estaba repetida seis
# veces inline y ningun test cubria el caso NULL. Medido el 2026-08-31: 1.632
# de 3.523 conduces (46,3%) sin precio, todos de julio 2026, y el Monto
# Pendiente quedaba ~38% corto sin decirlo.

def _db_mixta_con_y_sin_precio(path):
    """Dos conduces pendientes de la misma compañia: uno con precio y otro
    sin. El monto correcto es 500 y el aviso tiene que decir 1 de 2."""
    conn = sqlite3.connect(path)
    conn.execute(SCHEMA_CONDUCES)
    conn.execute(
        "INSERT INTO conduces (id_conduce, fecha, producto, compania, precio, cantidad, estado) "
        "VALUES ('C0010','2026-06-01','ARENA','SUPLIDOR A',100,5,'no_pagado')"
    )
    conn.execute(
        "INSERT INTO conduces (id_conduce, fecha, producto, compania, precio, cantidad, estado) "
        "VALUES ('C0011','2026-07-01','ARENA','SUPLIDOR A',NULL,7,'no_pagado')"
    )
    conn.commit()
    conn.close()


def test_monto_y_sin_precio_cuenta_las_filas_sin_precio():
    filas = [
        ("C1", None, None, "A", 100.0, 5.0, "no_pagado"),
        ("C2", None, None, "A", None, 7.0, "no_pagado"),
        ("C3", None, None, "A", 50.0, 2.0, "pagado"),
    ]
    monto, sin_precio = core._monto_y_sin_precio(filas)
    assert monto == 600.0          # 100x5 + 0x7 + 50x2
    assert sin_precio == 1

    monto_p, sin_precio_p = core._monto_y_sin_precio(
        filas, lambda r: r[6] == "no_pagado")
    assert monto_p == 500.0
    assert sin_precio_p == 1


def test_generar_reporte_avisa_cuando_hay_conduces_sin_precio(tmp_path, monkeypatch):
    import json
    db_path = tmp_path / "conduces.db"
    _db_mixta_con_y_sin_precio(str(db_path))
    monkeypatch.setattr(core, "DB_PATH", str(db_path))
    monkeypatch.setattr(core, "REPORTES_DIR", str(tmp_path))

    data = json.loads(core.generar_reporte())
    assert data["sin_precio"] == 1, "la respuesta de la API tiene que declarar el faltante"

    html = open(os.path.join(str(tmp_path), data["filename"]), encoding="utf-8").read()
    assert "$500.00" in html
    assert "1 de 2 conduces sin precio" in html, (
        "la tarjeta de Monto Pendiente tiene que decir sobre cuantas filas esta calculada"
    )
    assert "(1 sin precio)" in html, "la tabla por compañia tambien"


def test_generar_reporte_no_avisa_nada_si_todos_tienen_precio(tmp_path, monkeypatch):
    """El aviso solo aparece cuando falta algo — si no, la tarjeta queda como
    estaba y nadie ve un cartel rojo sin motivo."""
    import json
    db_path = tmp_path / "conduces.db"
    _db_con_conduce_cantidad_multiple(str(db_path))
    monkeypatch.setattr(core, "DB_PATH", str(db_path))
    monkeypatch.setattr(core, "REPORTES_DIR", str(tmp_path))

    data = json.loads(core.generar_reporte())
    assert data["sin_precio"] == 0
    html = open(os.path.join(str(tmp_path), data["filename"]), encoding="utf-8").read()
    # se busca el div del aviso, no el texto suelto: la hoja de estilos
    # menciona "sin precio" en un comentario y siempre esta presente
    assert '<div class="nota-sin-precio">' not in html
    assert "<span class='sin-precio'>" not in html


def test_generar_reporte_compania_avisa_cuando_hay_sin_precio(tmp_path, monkeypatch):
    import json
    db_path = tmp_path / "conduces.db"
    _db_mixta_con_y_sin_precio(str(db_path))
    monkeypatch.setattr(core, "DB_PATH", str(db_path))
    monkeypatch.setattr(core, "REPORTES_DIR", str(tmp_path))

    data = json.loads(core.generar_reporte_compania("SUPLIDOR A"))
    assert data["sin_precio"] == 1
    html = open(os.path.join(str(tmp_path), data["filename"]), encoding="utf-8").read()
    assert "1 de 2 conduces sin precio" in html


def test_generar_factura_declara_los_conduces_sin_precio(tmp_path, monkeypatch):
    import json
    db_path = tmp_path / "conduces.db"
    _db_mixta_con_y_sin_precio(str(db_path))
    monkeypatch.setattr(core, "DB_PATH", str(db_path))
    monkeypatch.setattr(core, "FACTURAS_DIR", str(tmp_path))

    data = json.loads(core.generar_factura("SUPLIDOR A"))
    assert data["sin_precio"] == 1


def test_la_tarjeta_y_la_tabla_por_compania_salen_del_mismo_calculo(tmp_path, monkeypatch):
    """Regresion del motivo por el que se extrajo el helper: el total de la
    tarjeta y la suma de la tabla por compañia se calculaban por separado.
    Con una sola compañia tienen que dar identico, monto y conteo."""
    import json
    import re
    db_path = tmp_path / "conduces.db"
    _db_mixta_con_y_sin_precio(str(db_path))
    monkeypatch.setattr(core, "DB_PATH", str(db_path))
    monkeypatch.setattr(core, "REPORTES_DIR", str(tmp_path))

    data = json.loads(core.generar_reporte())
    html = open(os.path.join(str(tmp_path), data["filename"]), encoding="utf-8").read()
    montos = re.findall(r"\$500\.00", html)
    assert len(montos) >= 2, "la tarjeta y la fila de la compañia tienen que decir lo mismo"
    assert html.count("1 sin precio") + html.count("1 de 2 conduces sin precio") >= 2


def test_importar_xls_avisa_cuando_xcosto_viene_vacia(tmp_path, monkeypatch, capsys, db_conduces):
    """La causa real del issue: el sistema de origen dejo XCosto en blanco
    para julio 2026 y el importador guardo None sin quejarse. Ahora lo dice."""
    import xlwt
    monkeypatch.setattr(importar_xls, "DB_PATH", db_conduces)
    wb = xlwt.Workbook()
    ws = wb.add_sheet("h")
    for col, titulo in ((3, "Referencia"), (4, "Fecha"), (6, "Almacen"),
                        (9, "Producto"), (10, "Grupo"), (12, "Entradas"),
                        (15, "XCosto"), (18, "COLUMN1")):
        ws.write(0, col, titulo)
    # fila 1: con precio | fila 2: XCosto vacia
    for fila, (ref, xcosto) in enumerate(((("C0100"), 1200.5), (("C0101"), "")), start=1):
        ws.write(fila, 3, ref)
        ws.write(fila, 4, 46000)
        ws.write(fila, 6, "ALM")
        ws.write(fila, 9, "ARENA")
        ws.write(fila, 10, "AGREGADOS")
        ws.write(fila, 12, 10)
        if xcosto != "":
            ws.write(fila, 15, xcosto)
        ws.write(fila, 18, "SUPLIDOR A")
    ruta = tmp_path / "entrada.xls"
    wb.save(str(ruta))

    importar_xls.importar(str(ruta))
    salida = capsys.readouterr().out
    assert "2 nuevos" in salida
    assert "1 de 2" in salida and "SIN PRECIO" in salida, (
        f"el import tiene que avisar del precio faltante — salida:\n{salida}"
    )
