"""
Tests de scripts/estado.py — el parseo del log de git.

Solo se prueba `parsear_ultimo_cambio()`, que es la unica pieza con logica
propia: el resto del script son consultas SQL y llamadas a subprocess, y
probarlas seria probar sqlite y git. Nada de esto toca las bases ni corre git.

Correr con: python -m pytest tests/test_estado.py -v
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import estado  # noqa: E402

C = estado.CENTINELA


def _log(*commits):
    """Arma la salida de `git log --format='<CENTINELA> %h %s' --name-only`.

    Cada commit es (asunto, [archivos]). Reproduce el detalle que rompio el
    parser: git mete una linea EN BLANCO entre el asunto y los archivos.
    """
    partes = []
    for asunto, archivos in commits:
        partes.append(C + " " + asunto)
        partes.append("")  # <- la linea en blanco que git agrega
        partes.extend(archivos)
        if archivos:
            partes.append("")
    return "\n".join(partes)


def test_devuelve_el_commit_de_codigo_y_no_un_nombre_de_archivo():
    """REGRESION: la version con separacion por lineas vacias devolvia
    "AGENDA.md" como si fuera un commit, porque tomaba el primer nombre de
    archivo despues del blanco como la cabecera siguiente."""
    salida = _log(
        ("a03f14c docs: AGENDA deja de ser el arranque", ["AGENDA.md", "HANDOFF.md"]),
        ("8fbaed7 Sembrar las 7 claves de VIVIENDAS", ["core.py", "tests/test_x.py"]),
    )
    cambio, err = estado.parsear_ultimo_cambio(salida)
    assert err is None
    assert cambio == "8fbaed7 Sembrar las 7 claves de VIVIENDAS"
    assert not cambio.endswith(".md")


def test_saltea_los_commits_de_solo_documentacion():
    salida = _log(
        ("1111111 docs: uno", ["README.md"]),
        ("2222222 docs: dos", ["CLAUDE.md", "TODOS.md"]),
        ("3333333 fix: el de verdad", ["routes_conduces.py"]),
    )
    cambio, err = estado.parsear_ultimo_cambio(salida)
    assert err is None
    assert cambio == "3333333 fix: el de verdad"


def test_los_pdf_de_documentos_no_son_cambio_de_comportamiento():
    """El commit que versiono el correo a X toco .pdf, no .md, y aun asi es
    documentacion: sin esto el script lo reportaba como cambio del sistema."""
    salida = _log(
        ("aaaaaaa docs: versionar el correo", ["documentos/mail_para_X_2026-09-03.pdf"]),
        ("bbbbbbb feat: algo real", ["core.py"]),
    )
    cambio, err = estado.parsear_ultimo_cambio(salida)
    assert err is None
    assert cambio == "bbbbbbb feat: algo real"


def test_los_merges_no_listan_archivos_y_se_saltean():
    salida = _log(
        ("ccccccc Merge pull request #56", []),
        ("ddddddd docs: solo prosa", ["HANDOFF.md"]),
        ("eeeeeee refactor: codigo", ["main.py"]),
    )
    cambio, err = estado.parsear_ultimo_cambio(salida)
    assert err is None
    assert cambio == "eeeeeee refactor: codigo"


def test_sin_ningun_commit_de_codigo_avisa_en_vez_de_inventar():
    """La regla del script: nunca imprimir un dato que no se pudo calcular."""
    salida = _log(
        ("1111111 docs: uno", ["README.md"]),
        ("2222222 docs: dos", ["AGENDA.md"]),
    )
    cambio, err = estado.parsear_ultimo_cambio(salida)
    assert cambio is None
    assert "documentacion" in err


def test_es_documentacion_distingue_ruta_de_extension():
    assert estado._es_documentacion("HANDOFF.md")
    assert estado._es_documentacion("documentos/spec_rco_rfo.md")
    assert estado._es_documentacion("dropoff/analisis_issue31.md")
    assert estado._es_documentacion("documentos/mail_para_X_2026-09-03.pdf")
    assert not estado._es_documentacion("core.py")
    assert not estado._es_documentacion("estimaciones/plantillas/base.xlsx")


# ---- Salida con caracteres que cp1252 no tiene (2026-11-04) ----
# El cierre se cayo en "issues abiertos" por la flecha del titulo del issue
# #98: con la salida a un pipe, Windows le da a Python cp1252.

import io  # noqa: E402
import subprocess  # noqa: E402

TITULO = "  #98 Idea: mapa ejecutivo de plantas, obras y flujos planta → obra"


def _salida_cp1252():
    return io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")


def test_reproduce_el_fallo_sin_el_arreglo(monkeypatch):
    """Que el test de abajo pruebe algo: sin consola_utf8, revienta."""
    monkeypatch.setattr(sys, "stdout", _salida_cp1252())
    monkeypatch.setattr(estado, "_correr", lambda cmd, timeout=60: (TITULO, None))
    try:
        estado.bloque_issues()
    except UnicodeEncodeError:
        return
    raise AssertionError("se esperaba UnicodeEncodeError con salida cp1252")


def test_bloque_issues_no_revienta_con_un_titulo_que_cp1252_no_tiene(monkeypatch):
    salida = _salida_cp1252()
    monkeypatch.setattr(sys, "stdout", salida)
    monkeypatch.setattr(estado, "_correr", lambda cmd, timeout=60: (TITULO, None))
    estado.consola_utf8()
    estado.bloque_issues()
    salida.flush()
    assert "planta → obra" in salida.buffer.getvalue().decode("utf-8")


def test_consola_utf8_no_revienta_si_stdout_no_es_un_textiowrapper(monkeypatch):
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    estado.consola_utf8()


def test_en_un_pipe_cp1252_de_verdad_sale_en_utf8():
    """El caso real: otro proceso, salida a un pipe y cp1252 forzado."""
    scripts = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
    codigo = "import sys; sys.path.insert(0, sys.argv[1]); import estado; estado.consola_utf8(); print('planta \u2192 obra')"
    r = subprocess.run([sys.executable, "-c", codigo, scripts], capture_output=True,
                       env={**os.environ, "PYTHONIOENCODING": "cp1252"}, timeout=60)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    assert r.stdout.decode("utf-8").strip() == "planta → obra"


def test_estado_main_arregla_la_salida_antes_de_imprimir(monkeypatch):
    """Lo primero que hace main es pasar la salida a UTF-8; se corta ahi para
    no correr git, las bases ni gh."""
    class Corte(Exception):
        pass

    def cortar():
        raise Corte()

    monkeypatch.setattr(estado, "consola_utf8", cortar)
    try:
        estado.main()
    except Corte:
        return
    raise AssertionError("main no llamo a consola_utf8 antes de imprimir")
