# by a_oller
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "conduces", "db", "conduces.db")

def setup(db_path=None):
    ruta_db = db_path or DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(ruta_db)), exist_ok=True)
    conn = sqlite3.connect(ruta_db)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conduces (
            id_conduce    TEXT PRIMARY KEY,
            fecha         DATE,
            producto      TEXT,
            compania      TEXT,
            precio        REAL,
            cantidad      REAL,
            almacen       TEXT,
            estado        TEXT DEFAULT 'no_pagado',
            id_transporte TEXT,
            fecha_pago    DATETIME
        )
    """)

    conn.commit()
    conn.close()
    print(f"Base de datos lista: {ruta_db}")

if __name__ == "__main__":
    setup()
