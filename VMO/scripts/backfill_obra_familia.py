# by a_oller
"""
backfill_obra_familia.py — Deriva `obra_familia` (issue #72) desde
`obra_papel` para las filas existentes de las TRES tablas: facturas,
pendientes_revision y pendiente_descartado.

obra_familia = core.normalizar_obra_papel(obra_papel): normalizacion mecanica
(tildes, mayusculas, puntuacion, espacios) + el mapa de equivalencias
CONFIRMADO A MANO del issue #72 (core.EQUIVALENCIAS_OBRA). NO llama a Vision:
es gratis y deterministico — a diferencia de backfill_obra_papel.py, que si
paga una llamada por fila.

`obra_papel` NO se toca: es la evidencia cruda. Este script solo escribe
`obra_familia`, y la recalcula donde DIFIERA de lo derivado (no solo donde
este NULL): si el mapa evoluciona, re-correrlo converge al mapa vigente.
Una fila con obra_papel NULL queda con obra_familia NULL.

Transaccional (todo o nada) e idempotente: la segunda corrida seguida
encuentra 0 cambios.

Uso:
    python scripts/backfill_obra_familia.py --check     # que haria, sin escribir
    python scripts/backfill_obra_familia.py --aplicar   # escribe (backup antes!)
"""

import argparse
import sqlite3
import sys
from collections import Counter
from pathlib import Path

# Los scripts asumen vivir UN NIVEL debajo de la raiz: moverlo de carpeta le
# cambia BASE_DIR sin lanzar ningun error, y pasaria a leer y escribir donde
# no es. Misma convencion que los otros ~22 scripts.
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
import core  # noqa: E402  (necesita BASE_DIR en el path)

DB_PATH = BASE_DIR / "estimaciones" / "db" / "estimaciones.db"

TABLAS = ("facturas", "pendientes_revision", "pendiente_descartado")


def cambios_pendientes(conn, tabla):
    """[(rowid, obra_papel, derivada)] de las filas cuya obra_familia difiere
    de lo que deriva el mapa vigente. rowid y no la PK de cada tabla, para
    tratar a las tres igual (facturas keyea por id_documento, las otras dos
    por archivo_pdf) — ninguna es WITHOUT ROWID."""
    filas = conn.execute(
        f"SELECT rowid, obra_papel, obra_familia FROM {tabla}").fetchall()
    cambios = []
    for rowid, obra_papel, obra_familia in filas:
        derivada = core.normalizar_obra_papel(obra_papel)
        if obra_familia != derivada:
            cambios.append((rowid, obra_papel, derivada))
    return cambios


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    grupo = ap.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--check",   action="store_true",
                       help="Solo muestra que haria, sin escribir nada")
    grupo.add_argument("--aplicar", action="store_true",
                       help="Escribe los cambios en la base de datos")
    args = ap.parse_args(argv)

    # La migracion del issue #72 es idempotente y vive en setup_est_db() /
    # _est_crear_tabla_pendientes(): un backfill sobre una BD anterior a la
    # columna tiene que crearla, no reventar con "no such column".
    # core.EST_DB_PATH apunta a la misma BD (mismo BASE_DIR).
    core.setup_est_db()

    conn = sqlite3.connect(DB_PATH)
    try:
        print(f"BD: {DB_PATH}\n")
        por_tabla = {t: cambios_pendientes(conn, t) for t in TABLAS}
        total = sum(len(c) for c in por_tabla.values())
        for tabla, cambios in por_tabla.items():
            n_filas = conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
            print(f"{tabla}: {n_filas} filas, {len(cambios)} por actualizar")
            for _rowid, obra_papel, derivada in cambios[:10]:
                print(f"    {obra_papel!r} -> {derivada!r}")
            if len(cambios) > 10:
                print(f"    ... y {len(cambios) - 10} mas")

        if args.check:
            _resumen_familias(conn, aplicado=False)
            print(f"\n--check: no se escribio nada ({total} filas cambiarian).")
            return

        if total == 0:
            _resumen_familias(conn, aplicado=True)
            print("\nNada que aplicar: la BD ya converge al mapa vigente.")
            return

        try:
            conn.execute("BEGIN")
            for tabla, cambios in por_tabla.items():
                for rowid, _obra_papel, derivada in cambios:
                    cur = conn.execute(
                        f"UPDATE {tabla} SET obra_familia = ? WHERE rowid = ?",
                        (derivada, rowid))
                    if cur.rowcount != 1:
                        raise RuntimeError(
                            f"{tabla} rowid={rowid}: el UPDATE afecto "
                            f"{cur.rowcount} filas, se esperaba 1")
            conn.commit()
        except Exception as e:
            conn.rollback()
            sys.exit(f"\nERROR — se revirtio todo, la BD quedo intacta: {e}")

        print(f"\nOK — {total} filas actualizadas.")
        _resumen_familias(conn, aplicado=True)
    finally:
        conn.close()


def _resumen_familias(conn, aplicado):
    """Cuantas filas por familia. Con --check muestra lo DERIVADO (lo que
    quedaria tras aplicar), no lo guardado — es el resumen para decidir."""
    # Dos caminos, misma cuenta: derivado en memoria (--check) o leido de la
    # columna ya escrita (--aplicar) — deben coincidir por construccion.
    print("\nResumen por familia (facturas):")
    conteo = Counter()
    if aplicado:
        filas = conn.execute(
            "SELECT obra_familia, COUNT(*) FROM facturas GROUP BY obra_familia").fetchall()
        for familia, n in filas:
            conteo[familia] = n
    else:
        for (obra_papel,) in conn.execute("SELECT obra_papel FROM facturas"):
            conteo[core.normalizar_obra_papel(obra_papel)] += 1
    for familia, n in conteo.most_common():
        print(f"  {n:6}  {familia if familia is not None else '(NULL)'}")


if __name__ == "__main__":
    main()
