# -*- coding: utf-8 -*-
"""Agrega el MR-42 a CEDIS en la base real (2026-10-20).

17 conduces de VMO/CEDIS (128 m3, 2026-09-22 a 2026-10-01) de
"PAVIMENTACION RIGIDA MR-42, T35C" entraron sin precio: el producto no estaba
en la lista de precios ni en el catalogo de la estimacion. Precio 166,45,
clave 13 confirmados por el usuario; tope del principal 0 porque no es del
contrato original y va todo a PPACT (primero se puso 128, corregido el mismo dia). Lo mismo va en los seeds
(seed_precios_catalogo.py, seed_acumulado_base_fases.py) y la plantilla de
CEDIS ya trae el renglon 13 (renglones_extra en EST_PLANTILLAS).

Hace, en una transaccion y despues de respaldar la base:
  - precios_vmo: 44942 / CEDIS / MR-42 / 166,45
  - catalogo_estimacion: VMO / CEDIS / orden 13 / clave 13 / MR-42 / 166,45
  - estimacion_acumulado_base: VMO / CEDIS / 13 / principal / 2026-07-16 / 0 / 0
  - las 17 facturas sin precio: precio_unitario 166,45 y total
Si cualquiera ya existe, o no son 17 facturas, no toca nada.

Uso: python scripts/agregar_mr42_cedis.py
"""
import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE_DIR, "estimaciones", "db", "estimaciones.db")
DESC = "PAVIMENTACION RIGIDA MR-42, T35C"
PRECIO = 166.45


def main():
    respaldo = os.path.join(BASE_DIR, "backups",
                            f"estimaciones_antes_mr42_{datetime.now():%Y%m%d_%H%M%S}.db")
    origen = sqlite3.connect(DB)
    destino = sqlite3.connect(respaldo)
    origen.backup(destino)
    destino.close()
    origen.close()
    print("respaldo:", respaldo)

    con = sqlite3.connect(DB, isolation_level=None)
    con.execute("BEGIN IMMEDIATE")
    try:
        if con.execute("SELECT 1 FROM catalogo_estimacion WHERE empresa = 'VMO' AND fase = 'CEDIS' "
                       "AND (orden = 13 OR clave = '13')").fetchone():
            raise SystemExit("CEDIS ya tiene clave 13 en el catalogo — no se toca nada")
        if con.execute("SELECT 1 FROM precios_vmo WHERE TRIM(descripcion) = ?", (DESC,)).fetchone():
            raise SystemExit("el MR-42 ya esta en precios_vmo — no se toca nada")
        con.execute("INSERT INTO precios_vmo (codigo, fase, descripcion, precio_unitario) "
                    "VALUES ('44942', 'CEDIS', ?, ?)", (DESC, PRECIO))
        con.execute("INSERT INTO catalogo_estimacion (empresa, fase, orden, clave, descripcion, precio_unitario) "
                    "VALUES ('VMO', 'CEDIS', 13, '13', ?, ?)", (DESC, PRECIO))
        con.execute("INSERT INTO estimacion_acumulado_base (empresa, fase, clave, serie, fecha_base, "
                    "cantidad_base, cantidad_proyecto_principal) "
                    "VALUES ('VMO', 'CEDIS', '13', 'principal', '2026-07-16', 0.0, 0.0)")
        cur = con.execute("UPDATE facturas SET precio_unitario = ?, total = round(cantidad * ?, 2) "
                          "WHERE empresa = 'VMO' AND fase = 'CEDIS' AND TRIM(descripcion) = ? "
                          "AND precio_unitario IS NULL", (PRECIO, PRECIO, DESC))
        if cur.rowcount != 17:
            raise SystemExit(f"se esperaban 17 facturas sin precio y son {cur.rowcount} — se revierte todo")
        m3, total = con.execute("SELECT sum(cantidad), round(sum(total), 2) FROM facturas "
                                "WHERE fase = 'CEDIS' AND TRIM(descripcion) = ?", (DESC,)).fetchone()
        con.execute("COMMIT")
        print(f"OK: MR-42 en CEDIS a {PRECIO}; 17 facturas, {m3} m3, total {total}")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
