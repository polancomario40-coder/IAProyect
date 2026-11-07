# by a_oller
import sqlite3
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "conduces", "db", "conduces.db")

def consultar(ids):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for id_conduce in ids:
        id_conduce = id_conduce.strip()
        cursor.execute("SELECT id_conduce, fecha, producto, compania, precio, cantidad, estado FROM conduces WHERE id_conduce = ?", (id_conduce,))
        row = cursor.fetchone()

        if row is None:
            print(f"{id_conduce}: NO ENCONTRADO")
        else:
            id_c, fecha, producto, compania, precio, cantidad, estado = row
            print(f"{id_c} | {fecha} | {producto} | {compania} | {precio} | {cantidad} | {estado.upper()}")

    conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python consultar.py C-001 C-002 C-003")
    else:
        consultar(sys.argv[1:])
