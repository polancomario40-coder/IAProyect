# by a_oller
import sqlite3
import csv
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cache_reportes import limpiar_cache_reportes  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "conduces", "db", "conduces.db")

def importar(archivo):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    nuevos = 0
    duplicados = 0
    invalidos = 0

    with open(archivo, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            id_raw = row.get('id_conduce', '').strip()

            # Separar id_transporte si el ID tiene formato "conduce/transporte"
            if '/' in id_raw:
                partes = id_raw.split('/', 1)
                id_conduce = partes[0].strip()
                id_transporte = partes[1].strip()
            else:
                id_conduce = id_raw
                id_transporte = None

            if len(id_conduce) < 4:
                print(f"  ID inválido ignorado: '{id_conduce}' (debe tener al menos 4 caracteres)")
                invalidos += 1
                continue
            try:
                cursor.execute("""
                    INSERT INTO conduces (id_conduce, fecha, producto, compania, precio, cantidad, id_transporte)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (id_conduce, row.get('fecha'), row.get('producto'), row.get('compania'),
                      row.get('precio'), row.get('cantidad'), id_transporte))
                nuevos += 1
            except sqlite3.IntegrityError:
                duplicados += 1

    conn.commit()
    conn.close()

    if nuevos:
        limpiar_cache_reportes()

    print(f"Importacion completa: {nuevos} nuevos, {duplicados} duplicados ignorados, {invalidos} inválidos ignorados.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python importar.py archivo.csv")
    else:
        importar(sys.argv[1])
