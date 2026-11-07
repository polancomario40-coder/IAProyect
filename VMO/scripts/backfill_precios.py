# by a_oller
"""
backfill_precios.py — Re-matchea precio_unitario para facturas que quedaron sin
precio (bug de importar_puente.py: insert_factura() nunca buscaba el precio).

Matchea por descripcion (viene del Excel), no por id_producto (Vision no es
confiable para el codigo de producto en MACAO 2; en las otras fases el codigo
directamente no se guardaba hasta el issue #48).

OJO — este script SOLO rellena NULL (`WHERE precio_unitario IS NULL`). NO
re-precia una fila que ya trae un precio, aunque `Lista de precios.xlsx` haya
cambiado debajo, asi que actualizar el xlsx no se propaga a lo ya importado.
Esa deriva la cubre `scripts/corregir_precios_desactualizados.py` (issue #39),
que compara contra `core._est_buscar_precio()` y corrige lo que quedo viejo.
Correr ese con `--check` despues de cada actualizacion de la lista de precios.

Uso:
    python scripts/backfill_precios.py
"""

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH  = BASE_DIR / "estimaciones" / "db" / "estimaciones.db"


def main():
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    cur.execute("SELECT empresa, COUNT(*) FROM facturas WHERE precio_unitario IS NULL GROUP BY empresa")
    pendientes_antes = dict(cur.fetchall())
    print(f"Sin precio antes del backfill — DOMICEM: {pendientes_antes.get('DOMICEM', 0)}, VMO: {pendientes_antes.get('VMO', 0)}")

    cur.execute("""
        UPDATE facturas
        SET precio_unitario = (
                SELECT p.precio_unitario FROM precios_domicem p
                WHERE TRIM(facturas.descripcion) = TRIM(p.descripcion)
                  AND facturas.fase = p.fase
            ),
            total = (
                SELECT p.precio_unitario * facturas.cantidad FROM precios_domicem p
                WHERE TRIM(facturas.descripcion) = TRIM(p.descripcion)
                  AND facturas.fase = p.fase
            )
        WHERE empresa = 'DOMICEM' AND precio_unitario IS NULL
    """)

    cur.execute("""
        UPDATE facturas
        SET precio_unitario = (
                SELECT p.precio_unitario FROM precios_vmo p
                WHERE TRIM(facturas.descripcion) = TRIM(p.descripcion)
                  AND (p.fase = facturas.fase OR p.fase IS NULL)
                ORDER BY p.fase IS NULL
                LIMIT 1
            ),
            total = (
                SELECT p.precio_unitario * facturas.cantidad FROM precios_vmo p
                WHERE TRIM(facturas.descripcion) = TRIM(p.descripcion)
                  AND (p.fase = facturas.fase OR p.fase IS NULL)
                ORDER BY p.fase IS NULL
                LIMIT 1
            )
        WHERE empresa = 'VMO' AND precio_unitario IS NULL
    """)

    conn.commit()

    cur.execute("SELECT empresa, COUNT(*) FROM facturas WHERE precio_unitario IS NULL GROUP BY empresa")
    pendientes_despues = dict(cur.fetchall())

    domicem_actualizadas = pendientes_antes.get('DOMICEM', 0) - pendientes_despues.get('DOMICEM', 0)
    vmo_actualizadas      = pendientes_antes.get('VMO', 0) - pendientes_despues.get('VMO', 0)

    print(f"DOMICEM — filas con precio agregado: {domicem_actualizadas}")
    print(f"VMO — filas con precio agregado:      {vmo_actualizadas}")
    print(f"Sin precio despues — DOMICEM: {pendientes_despues.get('DOMICEM', 0)}, VMO: {pendientes_despues.get('VMO', 0)}")
    print(f"(las que quedan sin precio son productos que faltan en precios_vmo/precios_domicem)")

    conn.close()


if __name__ == "__main__":
    main()
