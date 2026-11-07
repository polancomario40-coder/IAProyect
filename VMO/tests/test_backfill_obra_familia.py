"""
tests/test_backfill_obra_familia.py — scripts/backfill_obra_familia.py
(issue #72): deriva obra_familia = core.normalizar_obra_papel(obra_papel)
para las filas existentes de las TRES tablas, sin llamar a Vision (gratis y
determinístico, a diferencia de backfill_obra_papel.py).

Contrato bajo test:
  - rellena las tres tablas (facturas, pendientes_revision,
    pendiente_descartado) aplicando la mecánica + el mapa confirmado
  - obra_papel IS NULL → obra_familia queda NULL (y obra_papel NO se toca
    nunca: es la evidencia cruda)
  - recalcula donde obra_familia DIFIERA de lo derivado, no solo NULL — si
    el mapa evoluciona, re-correrlo converge
  - --check no escribe nada; --aplicar es transaccional e idempotente
    (segunda corrida = 0 cambios)

Correr con: python -m pytest tests/test_backfill_obra_familia.py -v
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
from scripts import backfill_obra_familia  # noqa: E402


def _bd_backfill(tmp_path, monkeypatch):
    """BD real (setup_est_db) en tmp_path, apuntada a la vez por el script
    (DB_PATH) y por core (EST_DB_PATH — el setup_est_db() que corre el script
    migra por ahí). Filas con los 4 casos: variante mapeada, familia propia
    desconocida, obra_papel NULL, y obra_familia pre-escrita DIVERGENTE."""
    db_path = tmp_path / "est_backfill.db"
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    monkeypatch.setattr(backfill_obra_familia, "DB_PATH", db_path)
    core.setup_est_db()
    conn = sqlite3.connect(str(db_path))
    conn.executemany(
        "INSERT INTO facturas (id_documento, obra_papel, obra_familia) VALUES (?,?,?)",
        [("F1", "BAHUUER", None),          # variante mapeada → BAHUWER
         ("F2", "OBRA RARA X", None),      # desconocida → familia propia
         ("F3", None, None),               # sin papel → queda NULL
         ("F4", "MALESPIN", "VIEJA")])     # divergente → se recalcula
    conn.execute("INSERT INTO pendientes_revision (archivo_pdf, obra_papel, motivo) "
                 "VALUES ('p.pdf', 'PÁRMOL', 'falta sello')")
    conn.execute("INSERT INTO pendiente_descartado (archivo_pdf, obra_papel, "
                 "descartado_por, descartado_motivo, descartado_fecha) "
                 "VALUES ('d.pdf', 'GORA LADO B', 'A. Oller', 'x', '2026-09-14T00:00:00')")
    conn.commit()
    conn.close()
    return db_path


def _leer(db_path, sql):
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_backfill_check_no_escribe(tmp_path, monkeypatch, capsys):
    db_path = _bd_backfill(tmp_path, monkeypatch)
    backfill_obra_familia.main(["--check"])
    salida = capsys.readouterr().out
    assert "no se escribio nada" in salida
    # nada cambió: los 4 valores previos siguen tal cual
    assert _leer(db_path, "SELECT obra_familia FROM facturas ORDER BY id_documento") \
        == [(None,), (None,), (None,), ("VIEJA",)]
    assert _leer(db_path, "SELECT obra_familia FROM pendientes_revision") == [(None,)]
    assert _leer(db_path, "SELECT obra_familia FROM pendiente_descartado") == [(None,)]


def test_backfill_aplicar_rellena_las_tres_tablas_y_respeta_null(tmp_path, monkeypatch, capsys):
    db_path = _bd_backfill(tmp_path, monkeypatch)
    backfill_obra_familia.main(["--aplicar"])
    salida = capsys.readouterr().out
    assert "OK — 5 filas actualizadas." in salida  # F3 (NULL→NULL) no cuenta
    assert _leer(db_path,
                 "SELECT obra_papel, obra_familia FROM facturas ORDER BY id_documento") == [
        ("BAHUUER", "BAHUWER"),            # el mapa confirmado
        ("OBRA RARA X", "OBRA RARA X"),    # familia propia, NUNCA por parecido
        (None, None),                      # sin papel: queda NULL
        ("MALESPIN", "MALESPIN MACAO II"), # divergente recalculada
    ]
    assert _leer(db_path, "SELECT obra_papel, obra_familia FROM pendientes_revision") \
        == [("PÁRMOL", "PARMOL")]          # la mecánica saca la tilde; cruda intacta
    assert _leer(db_path, "SELECT obra_papel, obra_familia FROM pendiente_descartado") \
        == [("GORA LADO B", "GOBA LADO B")]


def test_backfill_es_idempotente(tmp_path, monkeypatch, capsys):
    db_path = _bd_backfill(tmp_path, monkeypatch)
    backfill_obra_familia.main(["--aplicar"])
    capsys.readouterr()
    backfill_obra_familia.main(["--aplicar"])  # segunda corrida: 0 cambios
    salida = capsys.readouterr().out
    assert "Nada que aplicar" in salida
    conn = sqlite3.connect(str(db_path))
    try:
        for tabla in backfill_obra_familia.TABLAS:
            assert backfill_obra_familia.cambios_pendientes(conn, tabla) == [], tabla
    finally:
        conn.close()
