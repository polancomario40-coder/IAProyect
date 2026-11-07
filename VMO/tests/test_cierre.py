"""
Tests de scripts/cierre.py — el protocolo de cierre en un comando.

Existe porque el ritual largo se saltea: el cierre pedia tocar cinco `.md` a
mano y el 2026-09-03 se salteo `AGENDA.md`, que al dia siguiente decia 483
tests cuando eran 626.

Ninguna prueba corre git, `gh` ni el respaldo: se le pasan respuestas fijas a
las primitivas de estado.py, que es de donde cierre.py las lee.

Correr con: python -m pytest tests/test_cierre.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import backup_db  # noqa: E402
import cierre  # noqa: E402
import estado  # noqa: E402

LIMPIO = {
    ("rev-parse", "--abbrev-ref", "HEAD"): "main",
    ("status", "--porcelain"): "",
    ("status", "-sb"): "## main...origin/main",
    ("branch", "--format=%(refname:short)"): "main",
    ("worktree", "list"): "C:/repo  abc123 [main]",
}


@pytest.fixture
def git_falso(monkeypatch):
    """Deja fijar la respuesta de cada comando de git, sin correr git."""
    respuestas = dict(LIMPIO)
    monkeypatch.setattr(estado, "_git", lambda *a: (respuestas.get(a, ""), None))
    monkeypatch.setattr(estado, "_correr", lambda cmd, timeout=60: ("0", None))
    return respuestas


def test_main_limpia_pasa(git_falso):
    ok, detalle = cierre.revisar_main()
    assert ok, detalle


def test_avisa_si_no_estas_en_main(git_falso):
    git_falso[("rev-parse", "--abbrev-ref", "HEAD")] = "feat/algo"
    ok, detalle = cierre.revisar_main()
    assert not ok and "no en main" in detalle


def test_avisa_si_quedan_cambios_sin_commitear(git_falso):
    git_falso[("status", "--porcelain")] = " M core.py\n?? nuevo.py"
    ok, detalle = cierre.revisar_main()
    assert not ok and "2 archivo(s) sin commitear" in detalle


def test_avisa_si_main_no_esta_sincronizada(git_falso):
    git_falso[("status", "-sb")] = "## main...origin/main [ahead 2]"
    ok, detalle = cierre.revisar_main()
    assert not ok and "sincronizada" in detalle


def test_avisa_por_ramas_sin_borrar(git_falso):
    git_falso[("branch", "--format=%(refname:short)")] = "main\nfeat/vieja"
    ok, detalle = cierre.revisar_main()
    assert not ok and "feat/vieja" in detalle


def test_avisa_por_worktrees_colgando(git_falso):
    git_falso[("worktree", "list")] = "C:/repo abc [main]\nC:/wt1 def [rama]"
    ok, detalle = cierre.revisar_main()
    assert not ok and "worktree" in detalle


def test_avisa_por_prs_abiertos(git_falso, monkeypatch):
    monkeypatch.setattr(estado, "_correr", lambda cmd, timeout=60: ("3", None))
    ok, detalle = cierre.revisar_main()
    assert not ok and "3 PR(s) abierto(s)" in detalle


def test_gh_caido_no_convierte_el_cierre_en_un_falso_aviso(git_falso, monkeypatch):
    """Si `gh` no responde no se puede saber si hay PRs abiertos. Eso no es lo
    mismo que "hay PRs": inventar un aviso entrena a ignorarlos."""
    monkeypatch.setattr(estado, "_correr", lambda cmd, timeout=60: (None, "gh no responde"))
    ok, detalle = cierre.revisar_main()
    assert ok, detalle


def test_junta_todos_los_problemas_no_solo_el_primero(git_falso):
    git_falso[("status", "--porcelain")] = " M core.py"
    git_falso[("branch", "--format=%(refname:short)")] = "main\nfeat/vieja"
    ok, detalle = cierre.revisar_main()
    assert not ok
    assert "sin commitear" in detalle and "feat/vieja" in detalle, (
        "un cierre que reporta de a un problema por vez obliga a correrlo N veces"
    )


# ── la entrada en el log ──

def test_reconoce_una_entrada_de_hoy(tmp_path, monkeypatch):
    (tmp_path / "log.md").write_text(
        "| 2026-09-03 | vieja |\n| 2026-09-04 | de hoy |\n", encoding="utf-8")
    monkeypatch.setattr(backup_db, "MEMORIA_DIR", tmp_path)
    ok, detalle = cierre.revisar_log(hoy="2026-09-04")
    assert ok and "1 entrada" in detalle


def test_cuenta_todas_las_entradas_del_dia(tmp_path, monkeypatch):
    (tmp_path / "log.md").write_text(
        "| 2026-09-04 | una |\n\n| 2026-09-04 | dos |\n", encoding="utf-8")
    monkeypatch.setattr(backup_db, "MEMORIA_DIR", tmp_path)
    ok, detalle = cierre.revisar_log(hoy="2026-09-04")
    assert ok and "2 entrada(s)" in detalle


def test_avisa_si_no_hay_entrada_de_hoy(tmp_path, monkeypatch):
    (tmp_path / "log.md").write_text("| 2026-09-03 | solo vieja |\n", encoding="utf-8")
    monkeypatch.setattr(backup_db, "MEMORIA_DIR", tmp_path)
    ok, detalle = cierre.revisar_log(hoy="2026-09-04")
    assert not ok and "sin entradas" in detalle


def test_sin_carpeta_de_memoria_avisa_como_se_fuerza(monkeypatch):
    monkeypatch.setattr(backup_db, "MEMORIA_DIR", None)
    ok, detalle = cierre.revisar_log(hoy="2026-09-04")
    assert not ok and "MEMORIA_DIR" in detalle


# ── el dropoff: se reporta y NUNCA se borra ──

def test_el_dropoff_se_reporta_pero_no_se_borra(tmp_path, monkeypatch):
    """La regla del proyecto es que nada se borra sin probar antes que existe
    en otro lado, y nacio de haber perdido `Puente 2.zip` recien importado. El
    cierre no puede ser la excepcion: hoy en dropoff/ hay una copia unica de
    889 MB que el log decidio conservar."""
    monkeypatch.setattr(cierre, "BASE_DIR", tmp_path)
    (tmp_path / "dropoff").mkdir()
    (tmp_path / "dropoff" / "algo.xlsx").write_bytes(b"x" * 100)
    (tmp_path / "dropoff" / "preguntas_para_X.md").write_text("no me borres")

    ok, detalle = cierre.revisar_dropoff()

    assert ok is True, "reportar el dropoff nunca puede bloquear el cierre"
    assert "2 archivo(s)" in detalle
    assert "1 sin declarar" in detalle, "preguntas_para_X esta declarado, algo.xlsx no"
    assert (tmp_path / "dropoff" / "algo.xlsx").exists(), "NO puede borrar nada"
    assert (tmp_path / "dropoff" / "preguntas_para_X.md").exists()


def test_un_dropoff_vacio_no_dice_nada_raro(tmp_path, monkeypatch):
    monkeypatch.setattr(cierre, "BASE_DIR", tmp_path)
    (tmp_path / "dropoff").mkdir()
    assert cierre.revisar_dropoff() == (True, "vacio")


def test_sin_carpeta_dropoff_no_revienta(tmp_path, monkeypatch):
    monkeypatch.setattr(cierre, "BASE_DIR", tmp_path)
    ok, detalle = cierre.revisar_dropoff()
    assert ok is True and "no existe" in detalle


# ── los servidores: se cierran solos, pero solo los de este proyecto ──

def test_solo_se_cierra_lo_que_se_prueba_que_es_este_proyecto(monkeypatch):
    """La linea de comando `python -m uvicorn main:app` es identica en
    cualquier otro proyecto FastAPI de la misma maquina, asi que hace falta
    preguntarle al puerto que expone antes de matarlo."""
    monkeypatch.setattr(cierre, "servidores_del_proyecto",
                        lambda: ([], ["pid 1 en :9999 es OTRA app — no se toca"]))
    matados = []
    monkeypatch.setattr(cierre.subprocess, "run",
                        lambda *a, **k: matados.append(a) or None)

    ok, detalle = cierre.cerrar_servidores()

    assert ok is True
    assert matados == [], "una app ajena no se toca ni aunque se llame igual"
    assert "ajeno" in detalle


def test_la_huella_usa_prefijos_viejos_y_no_la_ruta_de_moda():
    """La primera version usaba /api/logistica/dias y dejaba vivo un servidor
    de la sesion anterior que era ESTE proyecto de antes de que Logistica
    tuviera rutas — o sea que salvaba justo a los viejos, que son los que este
    paso existe para cerrar."""
    assert "/api/estimaciones/" in cierre.HUELLAS_APP
    assert len(cierre.HUELLAS_APP) >= 2, "una sola ruta envejece mal"


def test_sin_servidores_corriendo_el_paso_pasa(monkeypatch):
    monkeypatch.setattr(cierre, "servidores_del_proyecto", lambda: ([], []))
    assert cierre.cerrar_servidores() == (True, "ninguno corriendo")


def test_si_uno_no_se_pudo_cerrar_el_cierre_lo_dice(monkeypatch):
    """Un servidor que sobrevive al cierre tiene que verse: un cierre en verde
    que dejo algo corriendo es peor que uno en rojo."""
    monkeypatch.setattr(cierre, "servidores_del_proyecto",
                        lambda: ([{"pid": 1, "puerto": 8000}], []))

    def explota(*a, **k):
        raise OSError("no se pudo")
    monkeypatch.setattr(cierre.subprocess, "run", explota)

    ok, detalle = cierre.cerrar_servidores()
    assert ok is False
    assert "sin cerrar" in detalle


# ── Issue #96 — el libro mayor no puede tener el mismo dia con dos numeros ──

def _bd_libro(tmp_path, filas):
    import sqlite3
    ruta = tmp_path / "estimaciones.db"
    con = sqlite3.connect(ruta)
    con.execute("create table estimacion_cerrada (empresa, fase, clave, serie, numero_estimacion, "
                "fecha_desde, fecha_hasta, cantidad, cerrada_en)")
    con.executemany("insert into estimacion_cerrada values (?,?,?,?,?,?,?,?,?)", filas)
    con.commit()
    con.close()
    return ruta


DOBLE_CIERRE_2026_10_05 = [
    ("DOMICEM", "MACAO 2", "8", "principal", "2026-08-17_2026-09-16", "2026-08-17", "2026-09-16", 7913.5, "2026-10-01"),
    ("DOMICEM", "MACAO 2", "6", "principal", "2026-08-17_2026-09-16", "2026-08-17", "2026-09-16", 2109.5, "2026-10-01"),
    ("DOMICEM", "MACAO 2", "8", "principal", "N40", "2026-08-17", "2026-09-16", 7913.5, "2026-10-05"),
    ("DOMICEM", "MACAO 2", "6", "principal", "N40", "2026-08-17", "2026-09-16", 2109.5, "2026-10-05"),
    ("DOMICEM", "MACAO 2", "8", "principal", "N39", "2026-07-17", "2026-08-16", 100.0, "2026-08-28"),
]


def test_estado_encuentra_el_doble_cierre_real_una_vez_por_par(tmp_path):
    """El caso del 2026-10-05: dos numeros, mismo rango, varias claves. Sale
    UN par (no uno por clave), y el periodo anterior contiguo no cuenta."""
    import sqlite3
    con = sqlite3.connect(_bd_libro(tmp_path, DOBLE_CIERRE_2026_10_05))
    try:
        assert estado.solapes_libro_mayor(con) == [
            ("DOMICEM", "MACAO 2", "2026-08-17_2026-09-16", "2026-08-17", "2026-09-16",
             "N40", "2026-08-17", "2026-09-16")]
    finally:
        con.close()


def test_el_cierre_de_sesion_falla_con_un_libro_mayor_solapado(tmp_path, monkeypatch):
    monkeypatch.setattr(estado, "DB_ESTIMACIONES", _bd_libro(tmp_path, DOBLE_CIERRE_2026_10_05))
    ok, detalle = cierre.revisar_libro_mayor()
    assert ok is False
    assert "1 par" in detalle


def test_el_cierre_de_sesion_pasa_con_periodos_contiguos(tmp_path, monkeypatch):
    monkeypatch.setattr(estado, "DB_ESTIMACIONES", _bd_libro(tmp_path, [
        f for f in DOBLE_CIERRE_2026_10_05 if f[4] != "2026-08-17_2026-09-16"]))
    assert cierre.revisar_libro_mayor()[0] is True
