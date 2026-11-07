# by a_oller
"""
migrar_precios_vmo_fase.py — Agrega columna 'fase' a precios_vmo (igual que ya
tiene precios_domicem) y reconstruye la tabla desde
estimaciones/data/Lista de precios.xlsx (hoja 'Lista de precios - VMO').

Solo se cargan fases actualmente activas (CANCHAS, CEDIS, EXTERIORES,
PATIO DE MANIOBRAS-TRA, PODIUM-1-2-3) — CAMPO DE GOLF, PUENTES DE MANGLAR y
BALLROOM son fases ya terminadas, se dejan fuera por ahora.

Si un codigo tiene el mismo precio en todas las fases activas donde aparece,
se guarda con fase=NULL (generico, matchea cualquier fase). Si varia, se
guarda una fila por fase.

Uso:
    python scripts/migrar_precios_vmo_fase.py
"""

import sqlite3
from collections import defaultdict
from pathlib import Path

import openpyxl

BASE_DIR    = Path(__file__).resolve().parent.parent
DB_PATH     = BASE_DIR / "estimaciones" / "db" / "estimaciones.db"
LISTA_PATH  = BASE_DIR / "estimaciones" / "data" / "Lista de precios.xlsx"

FASE_MAP = {
    "MACAO ALTO RESORT S.R.L  EXTERIORES": "EXTERIORES",
    "MACAO ALTO RESORT S.R.L- PODIUM 1, 2 Y 3": "PODIUM-1-2-3",
    "MACAO ALTO RESORT, S.R.L. (FASE III)-PODIUM": "PODIUM-1-2-3",
    "MACAO ALTO RESORT S.R.L, (PATIO DE MANIOBRA TRA)": "PATIO DE MANIOBRAS-TRA",
    "MACAO ALTO RESORT SRL (CEDIS)": "CEDIS",
    "MACAO ALTO RESORT S.R.L  CANCHAS": "CANCHAS",
    # Fases ya terminadas — se omiten intencionalmente:
    # "MACAO ALTO RESORT, S.R.L. (FASE III)-BALLROOM"
    # "MACAO ALTO RESORT, S.R.L-CAMPO DE GOLF"
    # "MACAO ALTO RESORT, S.R.L-PUENTES DE MANGLAR"
}


def main():
    wb = openpyxl.load_workbook(LISTA_PATH, data_only=True)
    ws = wb["Lista de precios - VMO"]
    rows = [r[:4] for r in ws.iter_rows(min_row=2, values_only=True) if r[0] is not None]

    # (codigo, descripcion) -> {fase: precio}
    por_producto = defaultdict(dict)
    for fase_larga, codigo, descripcion, precio in rows:
        fase = FASE_MAP.get((fase_larga or "").strip())
        if fase is None:
            continue  # fase terminada, se omite
        codigo_s = str(int(codigo))
        desc = (descripcion or "").strip()
        por_producto[(codigo_s, desc)][fase] = precio

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # PK original era solo (codigo) — no soporta varias filas por codigo con
    # distinta fase. Se recrea la tabla con PK compuesta (codigo, fase), igual
    # que precios_domicem. La lista nueva es la fuente autoritativa — no se
    # intenta "preservar" filas viejas (eso causo duplicados por diferencias
    # de espacios en blanco entre los dos archivos de origen).
    cur.execute("DROP TABLE IF EXISTS precios_vmo")
    cur.execute("""
        CREATE TABLE precios_vmo (
            codigo          TEXT,
            fase            TEXT,
            descripcion     TEXT,
            precio_unitario REAL,
            PRIMARY KEY (codigo, fase)
        )
    """)

    genericos = 0
    especificos = 0
    vistos = set()

    for (codigo, desc), precios_por_fase in por_producto.items():
        precios_unicos = set(precios_por_fase.values())
        vistos.add((codigo, desc))
        if len(precios_unicos) == 1:
            precio = precios_unicos.pop()
            cur.execute(
                "INSERT INTO precios_vmo (codigo, descripcion, precio_unitario, fase) VALUES (?,?,?,NULL)",
                (codigo, desc, precio)
            )
            genericos += 1
        else:
            for fase, precio in precios_por_fase.items():
                cur.execute(
                    "INSERT INTO precios_vmo (codigo, descripcion, precio_unitario, fase) VALUES (?,?,?,?)",
                    (codigo, desc, precio, fase)
                )
                especificos += 1
            print(f"Precio variable por fase — codigo {codigo}: {precios_por_fase} | {desc}")


    conn.commit()
    cur.execute("SELECT COUNT(*) FROM precios_vmo")
    print(f"\nprecios_vmo reconstruida: {cur.fetchone()[0]} filas ({genericos} genericas, {especificos} especificas por fase)")
    conn.close()


if __name__ == "__main__":
    main()
