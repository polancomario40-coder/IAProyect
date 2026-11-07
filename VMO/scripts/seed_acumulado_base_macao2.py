"""Siembra la base de "acumulado anterior" para DOMICEM/MACAO 2 (issue #11).

Valores reales confirmados por el usuario el 2026-08-25, sacados de
EST_DOMICEM_MACAO_II_4800029677_N34_22072026_V01.xlsx (columna "ACUMULADO
ACTUAL" de la hoja CD-COAF-REO-01) — fecha_base=2026-07-16 (fin del periodo
de esa estimacion, no la fecha en que se armo el documento).

Antes de insertar, valida que el catalogo de MACAO 2 tenga exactamente las
9 claves esperadas ('1'..'9') — si el catalogo no coincide (ej. el issue #10
todavia no esta aplicado en esta BD), aborta sin insertar nada. Idempotente
(INSERT OR REPLACE, mismo patron que scripts/seed_precios_catalogo.py).

Issue #12 extendio estimacion_acumulado_base con la columna "serie" (PK
compuesta empresa,fase,clave,serie) — este script siempre siembra
serie='principal' (el contrato principal, unico concepto que existia antes
del issue #12). El tope del contrato principal (cantidad_proyecto_principal)
y la fila serie='ppact' de la clave 7 los siembra un script aparte,
scripts/seed_contrato_principal_macao2.py.
"""
import argparse
import os
import sqlite3
import sys


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "estimaciones", "db", "estimaciones.db")

EMPRESA = "DOMICEM"
FASE = "MACAO 2"
FECHA_BASE = "2026-07-16"

# clave -> (producto, cantidad_base) — solo para el mensaje de consola, la
# clave es lo unico que se usa para escribir en la BD
ACUMULADO_BASE_MACAO2 = [
    ("1", "PLANTILLA", 1369.5),
    ("2", "PILOTES", 14223.0),
    ("3", "CIMENTACION TORRES", 26023.5),
    ("4", "TORRE GRUA", 548.5),
    ("5", "MURO DE CONTENCION", 198.5),
    ("6", "COLUMNAS - MUROS", 19681.25),
    ("7", "LOSAS Y VIGAS (HIDROFUGO)", 10445.0),
    ("8", "LOSAS Y VIGAS", 49569.5),
    ("9", 'Hormigón Fc350 Agg 3/8" imp', 6785.5),
]

CLAVES_ESPERADAS = {str(i) for i in range(1, 10)}


def seed(db_path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path)
    try:
        claves_reales = {
            r[0] for r in conn.execute(
                "SELECT clave FROM catalogo_estimacion WHERE empresa = ? AND fase = ?",
                (EMPRESA, FASE),
            ).fetchall()
        }
        if claves_reales != CLAVES_ESPERADAS:
            print(
                f"ERROR: catalogo_estimacion para {EMPRESA}/{FASE} tiene las claves "
                f"{sorted(claves_reales)}, se esperaban exactamente {sorted(CLAVES_ESPERADAS)}. "
                "El issue #10 (separar CIMENTACION TORRES / TORRE GRUA) no parece estar "
                "aplicado en esta base de datos — no se inserto nada.",
                file=sys.stderr,
            )
            sys.exit(1)

        antes = conn.execute(
            "SELECT COUNT(*) FROM estimacion_acumulado_base WHERE empresa = ? AND fase = ?",
            (EMPRESA, FASE),
        ).fetchone()[0]

        # UPSERT explicito, NUNCA "INSERT OR REPLACE": REPLACE borra la fila
        # en conflicto y la vuelve a insertar solo con las columnas listadas
        # aqui — cualquier columna no listada (cantidad_proyecto_principal,
        # issue #12) vuelve a su default (NULL), perdiendo el tope del
        # contrato principal si este script se corre DESPUES de
        # scripts/seed_contrato_principal_macao2.py. Bug real encontrado
        # verificando el issue #12 a mano contra la BD de produccion de este
        # worktree — confirmado con un repro minimo en sqlite antes de
        # arreglarlo. El UPSERT de abajo solo toca fecha_base/cantidad_base,
        # dejando cantidad_proyecto_principal intacto en filas existentes.
        conn.executemany(
            "INSERT INTO estimacion_acumulado_base "
            "(empresa, fase, clave, serie, fecha_base, cantidad_base) VALUES (?,?,?,'principal',?,?) "
            "ON CONFLICT(empresa, fase, clave, serie) DO UPDATE SET "
            "fecha_base = excluded.fecha_base, cantidad_base = excluded.cantidad_base",
            [(EMPRESA, FASE, clave, FECHA_BASE, cantidad) for clave, _, cantidad in ACUMULADO_BASE_MACAO2],
        )
        conn.commit()

        despues = conn.execute(
            "SELECT COUNT(*) FROM estimacion_acumulado_base WHERE empresa = ? AND fase = ?",
            (EMPRESA, FASE),
        ).fetchone()[0]
        return antes, despues
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Siembra estimacion_acumulado_base para DOMICEM/MACAO 2 (issue #11)"
    )
    parser.add_argument("db_path", nargs="?", default=DEFAULT_DB_PATH, help="Ruta de estimaciones.db")
    args = parser.parse_args()
    antes, despues = seed(args.db_path)
    print(f"Seed listo: estimacion_acumulado_base ({EMPRESA}/{FASE}) antes={antes}, despues={despues}")


if __name__ == "__main__":
    main()
