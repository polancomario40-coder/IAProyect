# by a_oller
"""
migrar_torres_grua_macao2.py — separa la fila fusionada "CIMENTACION TORRES /
TORRE GRUA" de catalogo_estimacion (DOMICEM, MACAO 2) en 2 productos reales
distintos (issue #10).

Antes: 8 filas, orden 1..8, clave 3 = concreto fusionado (texto ambiguo).
Despues: 9 filas, orden 1..9, clave 3 = CIMENTACION TORRES, clave 4 = TORRE
GRUA (mismo precio 191.27 — es el mismo concreto exacto), claves 5/6/7/8/9
reindexadas 1 posicion para dejar hueco a la clave 4 nueva (texto/precio de
esas filas no cambia, solo `orden`).

Idempotente: si ya hay 9 filas para (DOMICEM, MACAO 2), no hace nada.
Valida que el estado previo sea 8 (esperado) o 9 (ya migrado) — cualquier otro
numero aborta sin tocar nada, porque significa que alguien modifico la tabla
a mano y no coincide con lo que este script espera encontrar.

Uso:
    python scripts/migrar_torres_grua_macao2.py
"""

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH  = BASE_DIR / "estimaciones" / "db" / "estimaciones.db"

EMPRESA = "DOMICEM"
FASE = "MACAO 2"

FILAS_NUEVAS = [
    (EMPRESA, FASE, 3, "3", 'Hormigón Fc350 kg/cm2, AMB. S1 (ACI), Agg 3/4", Temp. 32C, a/c=0.50, Silice 10%, rev. 8"+/- 1" CIMENTACION TORRES', 191.27),
    (EMPRESA, FASE, 4, "4", 'Hormigón Fc350 kg/cm2, AMB. S1 (ACI), Agg 3/4", Temp. 32C, a/c=0.50, Silice 10%, rev. 8"+/- 1" TORRE GRUA', 191.27),
    (EMPRESA, FASE, 5, "5", 'Hormigón Fc350 kg/cm2, AMB. S1 (ACI), Agg 3/4", Temp. 32C, a/c=0.50, Silice 10%, rev. 8"+/- 1", imp. MURO DE CONTENCION', 200.01),
    (EMPRESA, FASE, 6, "6", 'Hormigón Fc350 kg/cm2, AMB. IIIA (EHE), Agg 3/8", Temp. 32C, a/c=0.50, rev. 6"+/- 1". COLUMNAS - MUROS', 154.02),
    (EMPRESA, FASE, 7, "7", 'Hormigón 350kg/cm2, AMB IIIA (EHE), Ag 3/8",T 32C, a/c= 0.45, Min. C: 300kg, rev. 6" +/- 1", Hidrofugo. LOSAS Y VIGAS (HIDROFUGO)', 186.98),
    (EMPRESA, FASE, 8, "8", 'Hormigón Fc350 kg/cm2, AMB. IIIA (EHE), Agg 3/8", Temp. 32C, a/c=0.45, rev. 6"+/- 1". LOSAS Y VIGAS', 159.1),
    (EMPRESA, FASE, 9, "9", 'Hormigón Fc350 kg/cm2, AMB. S1 (ACI), Agg 3/8", Temp. 32C, a/c=0.50, Silice 10%, rev. 8"+/- 1", imp', 208.01),
]


def _estado_actual(conn):
    filas = conn.execute(
        "SELECT orden, clave FROM catalogo_estimacion WHERE empresa = ? AND fase = ? ORDER BY orden",
        (EMPRESA, FASE),
    ).fetchall()
    return filas


def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        filas_antes = _estado_actual(conn)
        count_antes = len(filas_antes)
        claves_antes = [f[1] for f in filas_antes]
        print(f"Estado antes: {count_antes} filas, claves = {claves_antes}")

        if count_antes == 9:
            print("Ya migrado (9 filas) — no se hace nada.")
            return

        if count_antes != 8:
            raise SystemExit(
                f"ERROR: se esperaban 8 filas (sin migrar) o 9 (ya migrado), "
                f"se encontraron {count_antes}. Estado inesperado — abortando sin tocar datos."
            )

        conn.execute("BEGIN")
        try:
            conn.execute(
                "DELETE FROM catalogo_estimacion WHERE empresa = ? AND fase = ? AND orden IN (3,4,5,6,7,8)",
                (EMPRESA, FASE),
            )
            conn.executemany(
                "INSERT INTO catalogo_estimacion (empresa, fase, orden, clave, descripcion, precio_unitario) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                FILAS_NUEVAS,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        filas_despues = _estado_actual(conn)
        count_despues = len(filas_despues)
        ordenes_despues = [f[0] for f in filas_despues]
        claves_despues = [f[1] for f in filas_despues]
        print(f"Estado despues: {count_despues} filas, ordenes = {ordenes_despues}, claves = {claves_despues}")

        if count_despues != 9:
            raise SystemExit(f"ERROR de verificacion: se esperaban 9 filas despues, hay {count_despues}.")
        if ordenes_despues != list(range(1, 10)):
            raise SystemExit(f"ERROR de verificacion: orden no es 1..9 contiguo: {ordenes_despues}")

        print("Migracion completada correctamente.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
