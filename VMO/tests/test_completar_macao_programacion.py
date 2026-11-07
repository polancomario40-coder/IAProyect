"""
scripts/completar_macao_programacion.py — agrega a los dias guardados los
pedidos de Macao del Excel de programacion (2026-11-03).

Corre el script de verdad (con node, igual que en el servidor) contra una base
en tmp_path. Ninguna prueba toca la base real.

Correr solo estas:  python -m pytest tests/test_completar_macao_programacion.py -v
"""
import os
import shutil
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime

import openpyxl
import pytest
from fastapi.testclient import TestClient

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
import core  # noqa: E402
import main  # noqa: E402

SCRIPT = os.path.join(RAIZ, "scripts", "completar_macao_programacion.py")
MACAO2 = "MACAO ALTO RESORT S.R.L, (MACAO II, ESTRUCTURA)"
CEDIS = "MACAO ALTO RESORT SRL (CEDIS)"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="el script lee el Excel con node")


def _dia(fecha, cargue_macao):
    cargue = [{"ficha": "F-1", "horaMin": 420, "cliente": "ACME", "obra": "TORRE", "planta": "Movil II",
               "cantidad": 8}]
    if cargue_macao:
        cargue.append({"ficha": "EDU-577", "horaMin": 600, "cliente": MACAO2, "obra": "MALESPIN MACAO II",
                       "elemento": "LOSA M2", "planta": "Movil III", "cantidad": 8})
    return {"fecha": fecha, "cargue": 15, "calidad": 10, "tolerancia": 30, "toleranciaAdelanto": 60,
            "plantas": [{"planta": "Movil II", "trayecto": 30, "zona": "Santo Domingo"}],
            "programacion": [{"cliente": "ACME", "obra": "TORRE", "horaMin": 480, "cantidad": 8}],
            "cargue_rows": cargue}


def _programa(carpeta, fecha):
    """Un PROGRAMA como el del sistema: ACME, MACAO II, CEDIS y VMO CONCRETOS."""
    a, m, d = fecha.split("-")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Prioridad", "Cliente", "Obra", "Bomba", "Elemento", "Producto", "Cantidad",
               "Despachado", "Pendiente", "Hora Inicio"])
    ws.append([1, "ACME", "TORRE", "40", "LOSA", "HORMIGON 210", 8, 8, 0, 46296 + 8 / 24])
    ws.append([1, MACAO2, "PARMOL", "421", "COLUMNA M5", "HORMIGON 350", 18, 0, 18, 46296 + 18 / 24])
    ws.append([1, MACAO2, "MALESPIN...", "421", "LOSA M2", "HORMIGON 350", 160, 0, 160, 46296 + 10 / 24])
    ws.append([1, CEDIS, "MOON PALACE", "", "COLUMNA", "HORMIGON 210", 4, 0, 4, 46296 + 9 / 24])
    ws.append([1, "VMO CONCRETOS S. A.", "MACAO", "", "LECHADA", "HORMIGON 210", 1, 0, 1, 46296 + 9 / 24])
    # El sistema lo baja como .xls; el lector de la app mira el contenido, no la extension.
    wb.save(os.path.join(carpeta, f"PROGRAMA {d}-{m}-{a}.xls"))


@pytest.fixture
def base(tmp_path, monkeypatch):
    """Dos dias guardados: el 21 con viajes de Macao en el cargue, el 22 sin."""
    monkeypatch.setattr(core, "LOG_DB_PATH", str(tmp_path / "logistica.db"))
    token = f"test-{uuid.uuid4().hex}"
    core.active_tokens[token] = datetime.now()
    c = TestClient(main.app)
    for fecha, macao in (("2026-10-21", True), ("2026-10-22", False)):
        assert c.post("/api/logistica/dias", json=_dia(fecha, macao),
                      headers={"Authorization": f"Bearer {token}"}).status_code == 200
    core.active_tokens.pop(token, None)
    excels = tmp_path / "excels"
    excels.mkdir()
    for fecha in ("2026-10-21", "2026-10-22"):
        _programa(str(excels), fecha)
    return str(tmp_path / "logistica.db"), str(excels)


def _correr(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


def _clientes(db, fecha):
    with sqlite3.connect(db) as conn:
        return [r[0] for r in conn.execute(
            "SELECT cliente FROM logistica_programacion WHERE fecha = ? ORDER BY orden", (fecha,))]


def test_sin_aplicar_solo_muestra(base):
    db, excels = base
    salida = _correr(db, excels)
    assert "2026-10-21: agrega 3 pedidos, 182 m3" in salida
    assert "2026-10-22: NO se completa" in salida
    assert _clientes(db, "2026-10-21") == ["ACME"]


def test_aplicar_agrega_macao_con_respaldo_y_es_idempotente(base):
    db, excels = base
    _correr(db, excels, "--aplicar")
    assert _clientes(db, "2026-10-21") == ["ACME", MACAO2, MACAO2, CEDIS], "VMO CONCRETOS no entra"
    assert _clientes(db, "2026-10-22") == ["ACME"], "sin viajes de Macao no se completa"
    assert any(f.startswith("logistica.db.antes-macao-prog-") for f in os.listdir(os.path.dirname(db)))
    with sqlite3.connect(db) as conn:
        fila = conn.execute("SELECT obra, elemento, cantidad, despachado, pendiente, bomba FROM logistica_programacion "
                            "WHERE fecha = '2026-10-21' AND obra = 'PARMOL'").fetchone()
    assert fila == ("PARMOL", "COLUMNA M5", 18.0, 0.0, 18.0, "421")
    assert "2026-10-21: ya tiene sus 3 pedidos de Macao" in _correr(db, excels, "--aplicar")
    assert _clientes(db, "2026-10-21") == ["ACME", MACAO2, MACAO2, CEDIS]


def test_completa_lo_que_falta_en_una_base_que_ya_tenia_macao_ii(base):
    # La base de la PC original tenia ya MACAO II (version anterior del script):
    # se agrega solo lo que falta, sin duplicar.
    db, excels = base
    _correr(db, excels, "--aplicar")
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM logistica_programacion WHERE fecha = '2026-10-21' AND cliente = ?", (CEDIS,))
    assert "2026-10-21: agrega 1 pedidos, 4 m3" in _correr(db, excels, "--aplicar")
    assert _clientes(db, "2026-10-21") == ["ACME", MACAO2, MACAO2, CEDIS]
