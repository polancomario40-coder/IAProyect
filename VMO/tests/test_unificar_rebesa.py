"""
Tests de scripts/unificar_compania_rebesa.py — la fusion de las dos
escrituras de CONSTRUCTORA REBESA en `conduces.compania` (issue #24).

Todo corre sobre BDs temporales; ninguna prueba toca db/conduces.db ni los
reportes/facturas reales del proyecto.

Correr con: python -m pytest tests/test_unificar_rebesa.py -v
"""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import _cache_reportes  # noqa: E402
import unificar_compania_rebesa as uni  # noqa: E402


@pytest.fixture(autouse=True)
def _aislar_efectos(tmp_path, monkeypatch):
    """CRITICO, misma leccion que en test_conduces.py: el script llama a
    limpiar_cache_reportes() y escribe un respaldo. Sin esto los tests
    borrarian los reportes/facturas REALES y llenarian backups/db/ del
    proyecto. autouse=True para que ningun test futuro de este archivo pueda
    repetir el error por olvido."""
    monkeypatch.setattr(_cache_reportes, "REPORTES_DIR", str(tmp_path / "reportes_test"))
    monkeypatch.setattr(_cache_reportes, "FACTURAS_DIR", str(tmp_path / "facturas_test"))
    monkeypatch.setattr(uni, "BACKUP_DIR", tmp_path / "backups_test")


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

# Mismo esquema pero SIN llave primaria — sirve para forzar la colision de
# id_conduce, que con el esquema real es imposible.
SCHEMA_SIN_PK = SCHEMA_CONDUCES.replace("TEXT PRIMARY KEY", "TEXT")


def _insertar(conn, id_conduce, compania, precio=100.0, cantidad=10.0,
              producto="GRAVILLA", almacen="Macao", estado="no_pagado"):
    conn.execute(
        "INSERT INTO conduces (id_conduce, fecha, producto, compania, precio, "
        "cantidad, almacen, estado, id_transporte) VALUES (?,?,?,?,?,?,?,?,?)",
        (id_conduce, "2026-07-01", producto, compania, precio, cantidad,
         almacen, estado, None),
    )


def _db_universo_real(tmp_path, schema=SCHEMA_CONDUCES, n_variante=None,
                      n_canonico=None, extras=None):
    """BD con el universo auditado del issue #24: 1152 filas sin coma, 75 con
    coma, y 10 companias mas (12 distintas en total)."""
    n_variante = uni.ESPERADO_VARIANTE if n_variante is None else n_variante
    n_canonico = uni.ESPERADO_CANONICO if n_canonico is None else n_canonico
    db_path = tmp_path / "conduces_test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(schema)
    for i in range(n_canonico):
        _insertar(conn, f"C{i:05d}", uni.CANONICO,
                  precio=None if i < 3 else 100.0)  # algunas sin precio
    for i in range(n_variante):
        _insertar(conn, f"V{i:05d}", uni.VARIANTE, precio=200.0, cantidad=5.0)
    for j in range(10):  # las otras 10 companias
        _insertar(conn, f"O{j:05d}", f"OTRA COMPANIA {j}")
    for fila in (extras or []):
        _insertar(conn, *fila)
    conn.commit()
    conn.close()
    return db_path


def _companias(db_path):
    conn = sqlite3.connect(str(db_path))
    filas = dict(conn.execute(
        "SELECT compania, COUNT(*) FROM conduces GROUP BY compania").fetchall())
    conn.close()
    return filas


def _snapshot_sin_compania(db_path):
    """Todas las filas con todos los campos MENOS `compania`, por id."""
    conn = sqlite3.connect(str(db_path))
    cols = [r[1] for r in conn.execute("PRAGMA table_info(conduces)")
            if r[1] != "compania"]
    filas = {r[0]: r for r in conn.execute(
        f"SELECT {', '.join(cols)} FROM conduces")}
    conn.close()
    return filas


# ── Caso feliz ──────────────────────────────────────────────────────────────

def test_aplicar_une_las_75_filas_bajo_el_canonico(tmp_path):
    db = _db_universo_real(tmp_path)
    assert uni.main(["--aplicar", "--db", str(db)]) == 0

    comps = _companias(db)
    assert uni.VARIANTE not in comps
    assert comps[uni.CANONICO] == uni.ESPERADO_CANONICO + uni.ESPERADO_VARIANTE
    assert len(comps) == uni.ESPERADO_COMPANIAS - 1


def test_aplicar_no_toca_ningun_otro_campo(tmp_path):
    """Regla 8 del CLAUDE.md: solo se escribe `compania`, nunca se mueve un
    valor de un campo a otro."""
    db = _db_universo_real(tmp_path)
    antes = _snapshot_sin_compania(db)
    uni.main(["--aplicar", "--db", str(db)])
    assert _snapshot_sin_compania(db) == antes


def test_aplicar_conserva_filas_y_monto_totales(tmp_path):
    db = _db_universo_real(tmp_path)
    conn = sqlite3.connect(str(db))
    q = ("SELECT COUNT(*), ROUND(SUM(COALESCE(precio,0)*COALESCE(cantidad,0)),2) "
         "FROM conduces")
    antes = conn.execute(q).fetchone()
    conn.close()

    uni.main(["--aplicar", "--db", str(db)])

    conn = sqlite3.connect(str(db))
    assert conn.execute(q).fetchone() == antes
    conn.close()


def test_aplicar_deja_un_respaldo(tmp_path):
    db = _db_universo_real(tmp_path)
    uni.main(["--aplicar", "--db", str(db)])
    copias = list((tmp_path / "backups_test").glob("conduces_pre_unificar_rebesa_*.db"))
    assert len(copias) == 1
    # El respaldo tiene el estado PREVIO: las 75 filas siguen con coma ahi.
    conn = sqlite3.connect(str(copias[0]))
    assert conn.execute("SELECT COUNT(*) FROM conduces WHERE compania = ?",
                        (uni.VARIANTE,)).fetchone()[0] == uni.ESPERADO_VARIANTE
    conn.close()


# ── --check no escribe ──────────────────────────────────────────────────────

def test_check_no_escribe_nada(tmp_path):
    db = _db_universo_real(tmp_path)
    antes = _companias(db)
    assert uni.main(["--check", "--db", str(db)]) == 0
    assert _companias(db) == antes
    assert not (tmp_path / "backups_test").exists()  # ni siquiera respalda


# ── Idempotencia ────────────────────────────────────────────────────────────

def test_correrlo_dos_veces_deja_la_bd_igual_que_una(tmp_path):
    db = _db_universo_real(tmp_path)
    uni.main(["--aplicar", "--db", str(db)])
    despues_una = _companias(db)
    snapshot_una = _snapshot_sin_compania(db)

    assert uni.main(["--aplicar", "--db", str(db)]) == 0

    assert _companias(db) == despues_una
    assert _snapshot_sin_compania(db) == snapshot_una


def test_segunda_corrida_no_respalda_porque_no_escribe(tmp_path):
    db = _db_universo_real(tmp_path)
    uni.main(["--aplicar", "--db", str(db)])
    uni.main(["--aplicar", "--db", str(db)])
    copias = list((tmp_path / "backups_test").glob("*.db"))
    assert len(copias) == 1  # solo el de la primera corrida


# ── Guardas ─────────────────────────────────────────────────────────────────

def test_guarda_variante_inesperada_aborta_sin_escribir(tmp_path):
    """Una tercera escritura de la empresa (aca con puntos) no se puede unir
    a ciegas: el script tiene que abortar, no adivinar."""
    db = _db_universo_real(
        tmp_path, extras=[("X00001", "CONSTRUCTORA REBESA S.R.L.")])
    antes = _companias(db)

    with pytest.raises(SystemExit) as e:
        uni.main(["--aplicar", "--db", str(db)])

    assert "inesperada" in str(e.value)
    assert "CONSTRUCTORA REBESA S.R.L." in str(e.value)
    assert _companias(db) == antes
    assert not (tmp_path / "backups_test").exists()


def test_guarda_conteo_distinto_de_75_aborta_sin_escribir(tmp_path):
    db = _db_universo_real(tmp_path, n_variante=74)
    antes = _companias(db)

    with pytest.raises(SystemExit) as e:
        uni.main(["--aplicar", "--db", str(db)])

    assert "74 filas" in str(e.value)
    assert _companias(db) == antes
    assert not (tmp_path / "backups_test").exists()


def test_guarda_conteo_del_canonico_distinto_aborta(tmp_path):
    db = _db_universo_real(tmp_path, n_canonico=1000)
    antes = _companias(db)

    with pytest.raises(SystemExit) as e:
        uni.main(["--aplicar", "--db", str(db)])

    assert "1000 filas" in str(e.value)
    assert _companias(db) == antes


def test_guarda_tabla_conduces_ausente_aborta(tmp_path):
    db = tmp_path / "vacia.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE otra_cosa (x TEXT)")
    conn.commit()
    conn.close()

    with pytest.raises(SystemExit) as e:
        uni.main(["--aplicar", "--db", str(db)])

    assert "no tiene la tabla `conduces`" in str(e.value)


def test_guarda_columna_compania_ausente_aborta(tmp_path):
    db = tmp_path / "rara.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE conduces (id_conduce TEXT PRIMARY KEY, otra TEXT)")
    conn.commit()
    conn.close()

    with pytest.raises(SystemExit) as e:
        uni.main(["--aplicar", "--db", str(db)])

    assert "compania" in str(e.value)


def test_guarda_colision_de_id_conduce_aborta_sin_escribir(tmp_path):
    """Con el esquema real esto es imposible (id_conduce es PRIMARY KEY), pero
    la guarda tiene que estar viva para el dia que el esquema cambie."""
    db = _db_universo_real(tmp_path, schema=SCHEMA_SIN_PK,
                           extras=[("C00000", uni.VARIANTE)])
    # Ahora hay 76 con coma; se ajusta el esperado para que la guarda que
    # dispare sea la de colision y no la del conteo.
    antes = _companias(db)

    with pytest.raises(SystemExit) as e:
        uni.main(["--aplicar", "--db", str(db), "--forzar"])

    assert "llave primaria" in str(e.value)
    assert "C00000" in str(e.value)
    assert _companias(db) == antes
    assert not (tmp_path / "backups_test").exists()


def test_bd_inexistente_aborta(tmp_path):
    with pytest.raises(SystemExit) as e:
        uni.main(["--check", "--db", str(tmp_path / "no_existe.db")])
    assert "no se encuentra la BD" in str(e.value)


def test_forzar_permite_aplicar_con_un_universo_distinto(tmp_path):
    """La guarda del conteo es incomoda a proposito, pero se puede saltar."""
    db = _db_universo_real(tmp_path, n_variante=3, n_canonico=5)

    assert uni.main(["--aplicar", "--db", str(db), "--forzar"]) == 0

    comps = _companias(db)
    assert uni.VARIANTE not in comps
    assert comps[uni.CANONICO] == 8


# ── Cache de reportes ───────────────────────────────────────────────────────

def test_no_limpia_la_cache_cuando_la_db_no_es_produccion(tmp_path, monkeypatch):
    """Probar contra una copia no debe borrar los reportes reales."""
    reportes = tmp_path / "reportes_test"
    reportes.mkdir()
    (reportes / "reporte_viejo.html").write_text("x", encoding="utf-8")

    db = _db_universo_real(tmp_path)
    uni.main(["--aplicar", "--db", str(db)])

    assert (reportes / "reporte_viejo.html").exists()


def test_limpia_la_cache_cuando_la_db_es_la_de_produccion(tmp_path, monkeypatch):
    """Al revés: sobre la BD de produccion hay que invalidar el HTML cacheado,
    o `generar_reporte_compania` seguiria sirviendo un reporte del canonico
    generado antes de la fusion, sin las 75 filas nuevas."""
    reportes = tmp_path / "reportes_test"
    reportes.mkdir()
    (reportes / "reporte_viejo.html").write_text("x", encoding="utf-8")

    db = _db_universo_real(tmp_path)
    monkeypatch.setattr(uni, "DB_PATH", db)  # esta BD temporal hace de "produccion"
    uni.main(["--aplicar", "--db", str(db)])

    assert not (reportes / "reporte_viejo.html").exists()
