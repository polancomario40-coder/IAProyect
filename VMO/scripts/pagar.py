# by a_oller
import sqlite3
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cache_reportes import limpiar_cache_reportes  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "conduces", "db", "conduces.db")


def _asegurar_columna_fecha_pago(conn):
    """Migracion idempotente — agrega fecha_pago si la BD todavia no la
    tiene (tablas existentes se crean con CREATE TABLE IF NOT EXISTS, que
    no agrega columnas nuevas a una tabla que ya existe)."""
    columnas = [c[1] for c in conn.execute("PRAGMA table_info(conduces)").fetchall()]
    if "fecha_pago" not in columnas:
        conn.execute("ALTER TABLE conduces ADD COLUMN fecha_pago DATETIME")


def pagar(ids):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    _asegurar_columna_fecha_pago(conn)

    pagados = 0
    ya_pagados = []
    no_encontrados = []

    for id_conduce in ids:
        id_conduce = id_conduce.strip()
        if len(id_conduce) < 4:
            print(f"ID inválido ignorado: '{id_conduce}' (debe tener al menos 4 caracteres)")
            continue
        cursor.execute("SELECT estado FROM conduces WHERE id_conduce = ?", (id_conduce,))
        row = cursor.fetchone()

        if row is None:
            no_encontrados.append(id_conduce)
        elif row[0].lower() == "pagado":
            ya_pagados.append(id_conduce)
        else:
            cursor.execute(
                "UPDATE conduces SET estado = 'pagado', fecha_pago = ? WHERE id_conduce = ?",
                (datetime.now().isoformat(), id_conduce)
            )
            pagados += 1

    conn.commit()
    conn.close()

    if pagados:
        limpiar_cache_reportes()

    print(f"Marcados como pagados: {pagados}")
    if ya_pagados:
        print(f"Ya estaban pagados (sin cambios): {', '.join(ya_pagados)}")
    if no_encontrados:
        print(f"No encontrados: {', '.join(no_encontrados)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python pagar.py C-001 C-002 C-003")
    else:
        pagar(sys.argv[1:])
