"""Siembra los topes del contrato principal + la fila PPACT de MACAO 2
(issue #12 — contratos paralelos por producto).

Valores reales verificados el 2026-08-25 contra los documentos
EST_DOMICEM_MACAO_II_4800029677_N34_22072026_V01.xlsx (contrato principal) y
EST_DOMICEM_MACAO_II_4800029677_PPACT_N04_22072026_V01.xlsx (PPACT), ambos
con periodo 2026-06-17 a 2026-07-16 — ver la tabla completa en el Context
del issue #12.

Este script asume que estimacion_acumulado_base YA tiene las 9 filas
serie='principal' de MACAO 2 sembradas por el issue #11
(scripts/seed_acumulado_base_macao2.py) — si no las encuentra, aborta sin
tocar nada (el issue #11 no esta aplicado en esta BD). Actualiza esas 9
filas con su cantidad_proyecto_principal (el tope real) e inserta 1 fila
nueva serie='ppact' para la clave 7 ("LOSAS Y VIGAS (HIDROFUGO)"), el unico
producto que ya cruzo su tope.

Idempotente (UPDATE + INSERT OR REPLACE), mismo patron que
scripts/seed_acumulado_base_macao2.py.
"""
import argparse
import os
import sqlite3
import sys


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "estimaciones", "db", "estimaciones.db")

EMPRESA = "DOMICEM"
FASE = "MACAO 2"

# clave -> (producto, tope del contrato principal en m3)
TOPES_CONTRATO_PRINCIPAL_MACAO2 = [
    ("1", "PLANTILLA", 1372.0),
    ("2", "PILOTES", 19178.0),
    ("3", "CIMENTACION TORRES", 26027.0),
    ("4", "TORRE GRUA", 549.0),
    ("5", "MURO DE CONTENCION", 199.0),
    ("6", "COLUMNAS - MUROS", 27848.0),
    ("7", "LOSAS Y VIGAS (HIDROFUGO)", 10445.0),
    ("8", "LOSAS Y VIGAS", 81499.0),
    ("9", 'Hormigón Fc350 Agg 3/8" imp', 9112.0),
]

CLAVES_ESPERADAS = {str(i) for i in range(1, 10)}

# Unico producto con actividad PPACT confirmada hoy — agota su contrato
# principal exactamente (10445 de 10445, 100%) al 16-jul-2026.
CLAVE_PPACT = "7"
FECHA_BASE_PPACT = "2026-07-16"
CANTIDAD_BASE_PPACT = 1767.0


def seed(db_path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path)
    try:
        claves_principal = {
            r[0] for r in conn.execute(
                "SELECT clave FROM estimacion_acumulado_base "
                "WHERE empresa = ? AND fase = ? AND serie = 'principal'",
                (EMPRESA, FASE),
            ).fetchall()
        }
        if claves_principal != CLAVES_ESPERADAS:
            print(
                f"ERROR: estimacion_acumulado_base (serie='principal') para {EMPRESA}/{FASE} tiene "
                f"las claves {sorted(claves_principal)}, se esperaban exactamente "
                f"{sorted(CLAVES_ESPERADAS)}. El issue #11 (scripts/seed_acumulado_base_macao2.py) "
                "no parece estar aplicado en esta base de datos — no se inserto/actualizo nada.",
                file=sys.stderr,
            )
            sys.exit(1)

        antes_topes = conn.execute(
            "SELECT COUNT(*) FROM estimacion_acumulado_base "
            "WHERE empresa = ? AND fase = ? AND serie = 'principal' AND cantidad_proyecto_principal IS NOT NULL",
            (EMPRESA, FASE),
        ).fetchone()[0]
        antes_ppact = conn.execute(
            "SELECT COUNT(*) FROM estimacion_acumulado_base WHERE empresa = ? AND fase = ? AND serie = 'ppact'",
            (EMPRESA, FASE),
        ).fetchone()[0]

        conn.executemany(
            "UPDATE estimacion_acumulado_base SET cantidad_proyecto_principal = ? "
            "WHERE empresa = ? AND fase = ? AND clave = ? AND serie = 'principal'",
            [(tope, EMPRESA, FASE, clave) for clave, _, tope in TOPES_CONTRATO_PRINCIPAL_MACAO2],
        )
        conn.execute(
            "INSERT OR REPLACE INTO estimacion_acumulado_base "
            "(empresa, fase, clave, serie, fecha_base, cantidad_base, cantidad_proyecto_principal) "
            "VALUES (?,?,?,'ppact',?,?,NULL)",
            (EMPRESA, FASE, CLAVE_PPACT, FECHA_BASE_PPACT, CANTIDAD_BASE_PPACT),
        )
        conn.commit()

        despues_topes = conn.execute(
            "SELECT COUNT(*) FROM estimacion_acumulado_base "
            "WHERE empresa = ? AND fase = ? AND serie = 'principal' AND cantidad_proyecto_principal IS NOT NULL",
            (EMPRESA, FASE),
        ).fetchone()[0]
        despues_ppact = conn.execute(
            "SELECT COUNT(*) FROM estimacion_acumulado_base WHERE empresa = ? AND fase = ? AND serie = 'ppact'",
            (EMPRESA, FASE),
        ).fetchone()[0]
        return (antes_topes, despues_topes), (antes_ppact, despues_ppact)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Siembra topes de contrato principal + fila PPACT de DOMICEM/MACAO 2 (issue #12)"
    )
    parser.add_argument("db_path", nargs="?", default=DEFAULT_DB_PATH, help="Ruta de estimaciones.db")
    args = parser.parse_args()
    (antes_topes, despues_topes), (antes_ppact, despues_ppact) = seed(args.db_path)
    print(
        f"Seed listo: topes de contrato principal ({EMPRESA}/{FASE}) antes={antes_topes}, despues={despues_topes} "
        f"(de 9); filas serie='ppact' antes={antes_ppact}, despues={despues_ppact} (de 1)"
    )


if __name__ == "__main__":
    main()
