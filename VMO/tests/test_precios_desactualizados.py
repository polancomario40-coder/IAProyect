"""
Tests de scripts/corregir_precios_desactualizados.py — el re-precio de las
facturas cuyo `precio_unitario` quedo viejo respecto de la lista vigente
(issue #39).

Todo corre sobre BDs temporales; ninguna prueba toca estimaciones.db ni
backups/db/ del proyecto.

Correr con: python -m pytest tests/test_precios_desactualizados.py -v
"""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import corregir_precios_desactualizados as fix  # noqa: E402


@pytest.fixture(autouse=True)
def _aislar_respaldos(tmp_path, monkeypatch):
    """CRITICO, misma leccion que en test_unificar_rebesa.py: el script deja
    un respaldo antes de escribir. Sin esto los tests llenarian backups/db/
    del proyecto con copias de BDs sinteticas. autouse=True para que ningun
    test futuro de este archivo pueda repetir el error por olvido."""
    monkeypatch.setattr(fix, "BACKUP_DIR", tmp_path / "backups_test")


SCHEMA = """
    CREATE TABLE facturas (
        id_documento    TEXT PRIMARY KEY,
        fecha           DATE,
        descripcion     TEXT,
        cantidad        REAL,
        precio_unitario REAL,
        total           REAL,
        empresa         TEXT,
        fase            TEXT
    );
    CREATE TABLE precios_domicem (
        fase TEXT, codigo TEXT, descripcion TEXT, precio_unitario REAL
    );
    CREATE TABLE precios_vmo (
        codigo TEXT, fase TEXT, descripcion TEXT, precio_unitario REAL
    );
"""

# Descripciones sinteticas: no importa que digan, importa que la de "vieja"
# exista en la lista de precios con un valor distinto al guardado.
D_VIEJA   = "Hormigon Sintetico A"
D_AL_DIA  = "Hormigon Sintetico B"
D_HUERFANA = "Hormigon Sintetico Sin Precio"


def _db(tmp_path, n_viejas=3, con_null=True, con_huerfana=True):
    """BD minima: n_viejas facturas con precio desactualizado, una al dia,
    opcionalmente una en NULL y una cuya descripcion no esta en la lista."""
    ruta = tmp_path / "est_test.db"
    conn = sqlite3.connect(ruta)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO precios_domicem VALUES ('MACAO 2','C1',?,200.0)", (D_VIEJA,))
    conn.execute("INSERT INTO precios_domicem VALUES ('MACAO 2','C2',?,50.0)", (D_AL_DIA,))
    for i in range(n_viejas):
        conn.execute(
            "INSERT INTO facturas VALUES (?,?,?,?,?,?,?,?)",
            (f"V{i:03d}", "2026-06-01", D_VIEJA, 10.0, 180.0, 1800.0, "DOMICEM", "MACAO 2"))
    conn.execute("INSERT INTO facturas VALUES ('OK001','2026-06-02',?,4.0,50.0,200.0,'DOMICEM','MACAO 2')",
                 (D_AL_DIA,))
    if con_null:
        conn.execute("INSERT INTO facturas VALUES ('NUL001','2026-06-03',?,7.0,NULL,NULL,'DOMICEM','MACAO 2')",
                     (D_VIEJA,))
    if con_huerfana:
        conn.execute("INSERT INTO facturas VALUES ('HUE001','2026-06-04',?,5.0,99.0,495.0,'DOMICEM','MACAO 2')",
                     (D_HUERFANA,))
    conn.commit()
    conn.close()
    return ruta


def _snapshot(ruta):
    conn = sqlite3.connect(ruta)
    filas = conn.execute(
        "SELECT id_documento, precio_unitario, total FROM facturas ORDER BY id_documento"
    ).fetchall()
    conn.close()
    return filas


def _correr(ruta, *args, esperado=None, monkeypatch=None):
    if esperado is not None:
        monkeypatch.setattr(fix, "ESPERADO_N", esperado)
    monkeypatch.setattr(sys, "argv", ["corregir_precios_desactualizados.py",
                                      "--db", str(ruta), *args])
    return fix.main()


# ── deteccion ─────────────────────────────────────────────────────────────

def test_detecta_solo_las_desactualizadas(tmp_path):
    conn = sqlite3.connect(_db(tmp_path))
    conn.row_factory = sqlite3.Row
    fuera = fix.desactualizadas(conn)
    conn.close()
    assert [f["id_documento"] for f in fuera] == ["V000", "V001", "V002"]
    assert all(f["guardado"] == 180.0 and f["vigente"] == 200.0 for f in fuera)


def test_no_toca_la_que_ya_esta_al_dia(tmp_path):
    conn = sqlite3.connect(_db(tmp_path)); conn.row_factory = sqlite3.Row
    ids = {f["id_documento"] for f in fix.desactualizadas(conn)}
    conn.close()
    assert "OK001" not in ids


def test_no_toca_las_de_precio_null(tmp_path):
    """Los NULL son trabajo de backfill_precios.py, no de este script: aca no
    hay nada que "actualizar", hay algo que rellenar, y son casos distintos."""
    conn = sqlite3.connect(_db(tmp_path)); conn.row_factory = sqlite3.Row
    ids = {f["id_documento"] for f in fix.desactualizadas(conn)}
    conn.close()
    assert "NUL001" not in ids


def test_no_toca_la_que_no_matchea_ninguna_fila_de_la_lista(tmp_path):
    """Si _est_buscar_precio() no devuelve nada, no hay con que comparar. Una
    descripcion huerfana no es un precio desactualizado."""
    conn = sqlite3.connect(_db(tmp_path)); conn.row_factory = sqlite3.Row
    ids = {f["id_documento"] for f in fix.desactualizadas(conn)}
    conn.close()
    assert "HUE001" not in ids


def test_tolerancia_de_medio_centavo_no_marca_falsos_positivos(tmp_path):
    """Los dos lados son REAL de sqlite; una igualdad exacta sobre flotantes
    daria positivos que no son."""
    ruta = _db(tmp_path, n_viejas=0, con_null=False, con_huerfana=False)
    conn = sqlite3.connect(ruta)
    conn.execute("INSERT INTO facturas VALUES ('EPS01','2026-06-05',?,1.0,50.004,50.0,'DOMICEM','MACAO 2')",
                 (D_AL_DIA,))
    conn.commit()
    conn.row_factory = sqlite3.Row
    assert fix.desactualizadas(conn) == []
    conn.close()


# ── --check no escribe ────────────────────────────────────────────────────

def test_check_no_escribe_nada(tmp_path, monkeypatch):
    ruta = _db(tmp_path)
    antes = _snapshot(ruta)
    assert _correr(ruta, "--check", esperado=3, monkeypatch=monkeypatch) == 0
    assert _snapshot(ruta) == antes


def test_check_no_deja_respaldo(tmp_path, monkeypatch):
    ruta = _db(tmp_path)
    _correr(ruta, "--check", esperado=3, monkeypatch=monkeypatch)
    assert not fix.BACKUP_DIR.exists()


# ── --aplicar ─────────────────────────────────────────────────────────────

def test_aplicar_actualiza_precio_y_recalcula_total(tmp_path, monkeypatch):
    ruta = _db(tmp_path)
    assert _correr(ruta, "--aplicar", esperado=3, monkeypatch=monkeypatch) == 0
    filas = dict((f[0], (f[1], f[2])) for f in _snapshot(ruta))
    for i in range(3):
        assert filas[f"V{i:03d}"] == (200.0, 2000.0), "precio y total tienen que moverse juntos"


def test_aplicar_no_toca_las_otras_tres_filas(tmp_path, monkeypatch):
    ruta = _db(tmp_path)
    _correr(ruta, "--aplicar", esperado=3, monkeypatch=monkeypatch)
    filas = dict((f[0], (f[1], f[2])) for f in _snapshot(ruta))
    assert filas["OK001"] == (50.0, 200.0)
    assert filas["NUL001"] == (None, None)
    assert filas["HUE001"] == (99.0, 495.0)


def test_aplicar_deja_un_respaldo(tmp_path, monkeypatch):
    ruta = _db(tmp_path)
    _correr(ruta, "--aplicar", esperado=3, monkeypatch=monkeypatch)
    copias = list(fix.BACKUP_DIR.glob("estimaciones_pre_reprecio_*.db"))
    assert len(copias) == 1
    # y el respaldo tiene los precios VIEJOS, que es el punto de respaldar
    conn = sqlite3.connect(copias[0])
    assert conn.execute("SELECT precio_unitario FROM facturas WHERE id_documento='V000'").fetchone()[0] == 180.0
    conn.close()


def test_correrlo_dos_veces_deja_la_bd_igual_que_una(tmp_path, monkeypatch):
    ruta = _db(tmp_path)
    _correr(ruta, "--aplicar", esperado=3, monkeypatch=monkeypatch)
    despues_una = _snapshot(ruta)
    assert _correr(ruta, "--aplicar", esperado=3, monkeypatch=monkeypatch) == 0
    assert _snapshot(ruta) == despues_una


def test_segunda_corrida_no_respalda_porque_no_hay_nada_que_hacer(tmp_path, monkeypatch):
    ruta = _db(tmp_path)
    _correr(ruta, "--aplicar", esperado=3, monkeypatch=monkeypatch)
    antes = len(list(fix.BACKUP_DIR.glob("*.db")))
    _correr(ruta, "--aplicar", esperado=3, monkeypatch=monkeypatch)
    assert len(list(fix.BACKUP_DIR.glob("*.db"))) == antes


# ── guardas ───────────────────────────────────────────────────────────────

def test_guarda_universo_distinto_aborta_sin_escribir(tmp_path, monkeypatch):
    """Si el conteo real no es el auditado, algo cambio y hay que mirar antes
    de escribir. Es la guarda que evita que el script corrija de mas."""
    ruta = _db(tmp_path)
    antes = _snapshot(ruta)
    with pytest.raises(SystemExit) as e:
        _correr(ruta, "--aplicar", esperado=99, monkeypatch=monkeypatch)
    assert "se esperaban 99" in str(e.value)
    assert _snapshot(ruta) == antes
    assert not fix.BACKUP_DIR.exists(), "no debe respaldar si aborta antes de escribir"


def test_forzar_permite_aplicar_con_un_universo_distinto(tmp_path, monkeypatch):
    ruta = _db(tmp_path)
    assert _correr(ruta, "--aplicar", "--forzar", esperado=99, monkeypatch=monkeypatch) == 0
    filas = dict((f[0], (f[1], f[2])) for f in _snapshot(ruta))
    assert filas["V000"] == (200.0, 2000.0)


def test_bd_inexistente_aborta(tmp_path, monkeypatch):
    with pytest.raises(SystemExit) as e:
        _correr(tmp_path / "no_existe.db", "--check", esperado=3, monkeypatch=monkeypatch)
    assert "no se encuentra la BD" in str(e.value)


def test_sin_desactualizadas_no_hace_nada_y_sale_bien(tmp_path, monkeypatch):
    ruta = _db(tmp_path, n_viejas=0, con_null=False, con_huerfana=False)
    assert _correr(ruta, "--aplicar", esperado=0, monkeypatch=monkeypatch) == 0
    assert not fix.BACKUP_DIR.exists()


def test_check_y_aplicar_son_mutuamente_excluyentes(tmp_path, monkeypatch):
    ruta = _db(tmp_path)
    with pytest.raises(SystemExit):
        _correr(ruta, "--check", "--aplicar", esperado=3, monkeypatch=monkeypatch)


def test_hay_que_elegir_uno_de_los_dos(tmp_path, monkeypatch):
    """Sin --check ni --aplicar el script no corre: no tiene modo por defecto
    que escriba, a proposito."""
    ruta = _db(tmp_path)
    with pytest.raises(SystemExit):
        _correr(ruta, esperado=3, monkeypatch=monkeypatch)


# ── la fuente de verdad ───────────────────────────────────────────────────

def test_usa_la_primitiva_de_core_no_una_copia(tmp_path, monkeypatch):
    """Si el criterio de matcheo de core cambiara, este script tiene que
    cambiar con el. Se verifica que de verdad lo llame, no que reimplemente
    una busqueda parecida."""
    import core
    llamadas = []
    original = core._est_buscar_precio

    def espia(conn, empresa, fase, descripcion):
        llamadas.append((empresa, fase, descripcion))
        return original(conn, empresa, fase, descripcion)

    monkeypatch.setattr(core, "_est_buscar_precio", espia)
    conn = sqlite3.connect(_db(tmp_path)); conn.row_factory = sqlite3.Row
    fix.desactualizadas(conn)
    conn.close()
    assert llamadas, "desactualizadas() no llamo a core._est_buscar_precio()"
    assert ("DOMICEM", "MACAO 2", D_VIEJA) in llamadas
