# by a_oller
import sqlite3
import sys
import os
from datetime import datetime, timedelta

import xlrd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cache_reportes import limpiar_cache_reportes  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "conduces", "db", "conduces.db")

COL_REFERENCIA  = 3
COL_FECHA       = 4
COL_ALMACEN     = 6
COL_PRODUCTO    = 9
COL_GRUPO       = 10
COL_ENTRADAS    = 12
COL_XCOSTO      = 15
COL_COMPANIA    = 18

def excel_fecha(n):
    try:
        return (datetime(1899, 12, 30) + timedelta(days=int(n))).strftime("%Y-%m-%d")
    except Exception:
        return None

def importar(archivo):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    wb = xlrd.open_workbook(archivo)
    ws = wb.sheets()[0]

    nuevos = 0
    sin_precio = 0
    duplicados = 0
    invalidos = 0
    ids_usados = {}

    for i in range(1, ws.nrows):
        row = ws.row_values(i)

        if str(row[COL_GRUPO]).strip() == "SERVICIOS VARIOS":
            continue

        id_raw     = str(row[COL_REFERENCIA]).strip()
        fecha      = excel_fecha(row[COL_FECHA]) if row[COL_FECHA] else None
        producto   = str(row[COL_PRODUCTO]).strip() or None
        compania   = str(row[COL_COMPANIA]).strip() or None
        almacen    = str(row[COL_ALMACEN]).strip() or None
        cantidad   = row[COL_ENTRADAS] if row[COL_ENTRADAS] != "" else None
        xcosto     = row[COL_XCOSTO]
        precio     = float(xcosto) if xcosto not in ("", None) else None

        # Separar id_transporte si el ID tiene formato "conduce/transporte"
        if '/' in id_raw:
            partes = id_raw.split('/', 1)
            id_base = partes[0].strip()
            id_transporte = partes[1].strip()
        else:
            id_base = id_raw
            id_transporte = None

        if len(id_base) < 4:
            print(f"  ID inválido ignorado: '{id_base}' (debe tener al menos 4 caracteres)")
            invalidos += 1
            continue

        # Manejar IDs duplicados con sufijo -2, -3, ...
        if id_base not in ids_usados:
            ids_usados[id_base] = 1
            id_conduce = id_base
        else:
            ids_usados[id_base] += 1
            id_conduce = f"{id_base}-{ids_usados[id_base]}"

        try:
            cursor.execute("""
                INSERT INTO conduces (id_conduce, fecha, producto, compania, precio, cantidad, almacen, id_transporte)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (id_conduce, fecha, producto, compania, precio, cantidad, almacen, id_transporte))
            nuevos += 1
            # Issue #31: XCosto viene vacia en tandas enteras (100% de julio
            # 2026) y el conduce entra con precio NULL. Los reportes lo cuentan
            # como $0 sin avisar, asi que al menos que el import lo diga. Se
            # cuenta despues del INSERT: un duplicado ignorado no suma.
            if precio is None:
                sin_precio += 1
        except sqlite3.IntegrityError:
            duplicados += 1

    conn.commit()
    conn.close()

    if nuevos:
        limpiar_cache_reportes()

    print(f"Importacion completa: {nuevos} nuevos, {duplicados} duplicados ignorados, {invalidos} inválidos ignorados.")
    if sin_precio:
        pct = sin_precio * 100 // nuevos if nuevos else 0
        print(f"  AVISO: {sin_precio} de {nuevos} ({pct}%) entraron SIN PRECIO "
              f"(columna {COL_XCOSTO} 'XCosto' vacia en el Excel).")
        print(f"  Esos conduces cuentan como $0 en el Monto Pendiente y en los "
              f"reportes por compañia. Revisar el archivo de origen antes de "
              f"usar esas cifras.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/importar_xls.py archivo.xls")
    else:
        importar(sys.argv[1])
