# by a_oller
"""
estado.py — Imprime el estado del proyecto, calculado en el momento.

Existe porque el estado escrito a mano en un .md caduca solo. El bloque
"Estado" del HANDOFF llego a tener ~10 numeros tipeados (tests, punta de main,
filas en las bases, issues abiertos) y TODOS eran derivables: para el
2026-09-04 `AGENDA.md` afirmaba 483 tests cuando eran 626, y `main` en un hash
de tres dias antes. El arreglo no es reescribir esos numeros mas seguido, es no
escribirlos: este script los calcula cada vez que se corre.

Regla de oro: **nunca imprimir un numero que no se pudo calcular.** Si falta la
base, si `gh` no responde o si esto no es un repo git, el bloque dice por que no
sabe. Un "no disponible" es informacion; un numero viejo es una mentira.

Uso:
    python scripts/estado.py

Salida pensada para leer de un vistazo al arrancar una sesion. No escribe nada:
solo lee, y abre las bases en modo solo-lectura.
"""

import shutil
import sqlite3
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DB_CONDUCES = BASE_DIR / "conduces" / "db" / "conduces.db"
DB_ESTIMACIONES = BASE_DIR / "estimaciones" / "db" / "estimaciones.db"

# Prefijo que separa un commit del siguiente al parsear `git log --name-only`.
CENTINELA = "@@"


def _correr(cmd, timeout=60):
    """Corre un comando y devuelve (stdout, None) o (None, motivo del fallo)."""
    if shutil.which(cmd[0]) is None:
        return None, cmd[0] + " no esta instalado o no esta en el PATH"
    try:
        r = subprocess.run(
            cmd, cwd=BASE_DIR, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, cmd[0] + " no respondio en " + str(timeout) + "s"
    if r.returncode != 0:
        motivo = (r.stderr or r.stdout or "").strip().splitlines()
        return None, motivo[0] if motivo else cmd[0] + " devolvio codigo " + str(r.returncode)
    return r.stdout.strip(), None


def _git(*args):
    return _correr(["git", *args])


def _titulo(texto):
    print("\n" + texto)
    print("-" * len(texto))


def _no_se(que, motivo):
    print("  " + que + ": NO DISPONIBLE — " + motivo)


# Rutas que son documentacion: un commit que solo las toca no cambia el sistema.
def _es_documentacion(ruta):
    return ruta.endswith(".md") or ruta.startswith(("documentos/", "dropoff/"))


def parsear_ultimo_cambio(salida):
    """Primer commit de `salida` que toca algo que no sea documentacion.

    `salida` es lo que imprime `git log --format=CENTINELA... --name-only`.
    Se usa un centinela porque `--name-only` mete una linea EN BLANCO entre el
    asunto y la lista de archivos: separando por lineas vacias, el primer nombre
    de archivo se toma como si fuera el commit siguiente. Ese bug estuvo vivo y
    hacia que este campo reportara "AGENDA.md" como si fuera un commit.

    Los merges no listan archivos, asi que se saltean solos y lo que se
    devuelve es el commit que realmente trajo el cambio.
    """
    cabecera, tocados = None, []
    for linea in salida.splitlines() + [CENTINELA + " fin"]:
        if linea.startswith(CENTINELA + " "):
            if cabecera and any(not _es_documentacion(t) for t in tocados):
                return cabecera, None
            cabecera, tocados = linea[len(CENTINELA) + 1:], []
        elif linea.strip():
            tocados.append(linea.strip())
    return None, "no aparece en los ultimos 40 commits (son todos de documentacion)"


def _ultimo_cambio_de_comportamiento():
    """Como parsear_ultimo_cambio(), pero yendo a buscar el log a git.

    No es lo mismo que la punta: los commits de solo documentacion la mueven sin
    mover el sistema. Ese desfase fue exactamente lo que rompio el campo
    equivalente del HANDOFF dos veces seguidas (PR #55).
    """
    salida, err = _git("log", "-40", "--format=" + CENTINELA + " %h %s", "--name-only")
    if err:
        return None, err
    return parsear_ultimo_cambio(salida)


def bloque_git():
    _titulo("git")

    punta, err = _git("log", "--oneline", "-1")
    if err:
        _no_se("punta", err)
        return
    print("  punta            : " + punta)

    cambio, err = _ultimo_cambio_de_comportamiento()
    if err:
        _no_se("ultimo cambio de comportamiento", err)
    else:
        print("  ultimo cambio de comportamiento (saltea commits de solo documentacion):")
        print("                     " + cambio)

    rama, _ = _git("rev-parse", "--abbrev-ref", "HEAD")
    sucio, _ = _git("status", "--porcelain")
    print("  rama             : " + (rama or "?"))
    print("  arbol            : " + ("limpio" if sucio == "" else "CON CAMBIOS SIN COMMITEAR"))

    seguimiento, err = _git("status", "-sb")
    if not err and seguimiento:
        primera = seguimiento.splitlines()[0]
        desfasado = "[ahead" in primera or "[behind" in primera
        print("  vs origin        : " + ("DESINCRONIZADO — " if desfasado else "") + primera)

    ramas, err = _git("branch", "--format=%(refname:short)")
    if not err:
        otras = [b.strip() for b in ramas.splitlines() if b.strip() and b.strip() != "main"]
        print("  ramas aparte de main: " + (", ".join(otras) if otras else "ninguna"))

    wt, err = _git("worktree", "list")
    if not err:
        extra = wt.splitlines()[1:]
        print("  worktrees extra  : " + (str(len(extra)) if extra else "ninguno"))


def solapes_libro_mayor(con):
    """Pares de estimaciones cerradas de la misma (empresa, fase), con
    distinto numero, cuyos rangos comparten al menos un dia. Cada dia en
    comun se cuenta dos veces en el acumulado anterior (issue #96). El cierre
    ya los bloquea; esto encuentra los que entraron antes o por otro camino.
    El 2026-10-05 el unico sintoma fue que el libro mayor paso de 31 a 44
    lineas en un dia."""
    return con.execute(
        "with r as (select distinct empresa, fase, numero_estimacion n, fecha_desde d, "
        "fecha_hasta h from estimacion_cerrada) "
        "select a.empresa, a.fase, a.n, a.d, a.h, b.n, b.d, b.h from r a join r b "
        "on a.empresa = b.empresa and a.fase = b.fase and a.n < b.n "
        "and a.d <= b.h and a.h >= b.d order by a.empresa, a.fase, a.d"
    ).fetchall()


def bloque_datos():
    _titulo("datos")

    if not DB_CONDUCES.exists():
        _no_se("conduces", "no existe " + str(DB_CONDUCES.relative_to(BASE_DIR)) + " (esta en .gitignore)")
    else:
        con = sqlite3.connect("file:" + DB_CONDUCES.as_posix() + "?mode=ro", uri=True)
        try:
            total = con.execute("select count(*) from conduces").fetchone()[0]
            print("  conduces         : {:,} en base".format(total))
        finally:
            con.close()

    if not DB_ESTIMACIONES.exists():
        _no_se("estimaciones", "no existe " + str(DB_ESTIMACIONES.relative_to(BASE_DIR)) + " (esta en .gitignore)")
        return

    con = sqlite3.connect("file:" + DB_ESTIMACIONES.as_posix() + "?mode=ro", uri=True)
    try:
        c = con.cursor()
        contar = lambda sql: c.execute(sql).fetchone()[0]

        facturas = contar("select count(*) from facturas")
        pendientes = contar("select count(*) from pendientes_revision")
        catalogo = contar("select count(*) from catalogo_estimacion")
        fases_catalogo = contar("select count(distinct fase) from catalogo_estimacion")
        fases_datos = contar(
            "select count(distinct fase) from facturas where fase is not null and fase <> ''"
        )
        print("  estimaciones     : {:,} facturas, {} pendientes por revision, "
              "{} productos de catalogo".format(facturas, pendientes, catalogo))
        print("  fases con datos  : {} de {} del catalogo".format(fases_datos, fases_catalogo))

        cerradas = contar("select count(*) from estimacion_cerrada")
        fases_cerradas = contar("select count(distinct fase) from estimacion_cerrada")
        print("  libro mayor      : {} lineas cerradas en {} de {} fases".format(
            cerradas, fases_cerradas, fases_catalogo))
        for e, f, n1, d1, h1, n2, d2, h2 in solapes_libro_mayor(con):
            print("  OJO SOLAPE       : {}/{} {} ({} -> {}) y {} ({} -> {})".format(
                e, f, n1, d1, h1, n2, d2, h2))
            print("                     esos dias se cuentan DOS veces en el acumulado")

        faltan = [f for (f,) in c.execute(
            "select distinct fase from catalogo_estimacion "
            "where fase not in (select fase from estimacion_cerrada) order by fase"
        )]
        if faltan:
            print("  nunca cerradas   : " + ", ".join(faltan))
            print("                     (puede ser que no tuvieran entregas en el rango,")
            print("                      no necesariamente que falte cerrarlas)")

        fila = c.execute(
            "select fecha_desde, fecha_hasta from estimacion_cerrada "
            "order by fecha_hasta desc, cerrada_en desc limit 1"
        ).fetchone()
        if fila:
            print("  ultimo periodo cerrado: {} -> {}".format(fila[0], fila[1]))
    finally:
        con.close()


def bloque_issues():
    _titulo("issues abiertos")
    salida, err = _correr(
        ["gh", "issue", "list", "--state", "open", "--limit", "50",
         "--json", "number,title", "--jq", r'.[] | "  #\(.number) \(.title)"'],
        timeout=60,
    )
    if err:
        _no_se("issues", err)
        return
    print(salida if salida.strip() else "  ninguno")


def bloque_tests():
    _titulo("tests")
    salida, err = _correr(
        ["python", "-m", "pytest", "tests/", "--collect-only", "-q"], timeout=300
    )
    if err:
        _no_se("cantidad de tests", err)
        return
    lineas = [l for l in salida.splitlines() if l.strip()]
    print("  colectados       : " + (lineas[-1] if lineas else "?"))
    print("  OJO: esto CUENTA los tests, no los corre. Para saber si estan en")
    print("       verde: python -m pytest tests/ -q   (~3m40s)")


def main():
    print("=" * 64)
    print("ESTADO DEL PROYECTO — calculado ahora, no escrito a mano")
    print("=" * 64)
    bloque_git()
    bloque_datos()
    bloque_issues()
    bloque_tests()
    print()
    print("Lo que este script NO sabe, porque no es derivable y vive en prosa:")
    print("  - las trampas que cuestan caro    -> HANDOFF.md")
    print("  - por que se decidio algo         -> memory/log.md (se consulta con grep)")
    print("  - reglas de negocio y contexto    -> CLAUDE.md")
    print()


if __name__ == "__main__":
    main()
