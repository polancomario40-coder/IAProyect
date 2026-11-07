# -*- coding: utf-8 -*-
"""Corrige la cantidad de 42 conduces de MACAO 2 (periodo 2026-09-17 ->
2026-10-16) que Vision leyo distinto al Excel de conduces.

El hallazgo (2026-10-20): la N39 daba RD$ 1.253.231,09 y la tabla dinamica
del cliente RD$ 1.291.544,16. Los 1.132 conduces son los mismos en los dos
lados; 42 tienen otra cantidad (camiones de 7-8 m3 leidos como 1, 2, 3...,
dos sin cantidad) y suman 150,72 m3. Mismo caso que
corregir_cantidades_macao2_ac050.py.

Respalda la base antes. Corre en una transaccion: cada UPDATE exige la
cantidad vieja exacta y afectar 1 fila, y al final el periodo debe sumar
8.171 m3 o se revierte todo. Es idempotente: una segunda corrida no encuentra
diferencias y aborta sin tocar nada.

Uso: python scripts/corregir_cantidades_macao2_n39.py "C:/ruta/Book1 (4).xlsx"
"""
import os
import sqlite3
import sys
from datetime import datetime

import openpyxl

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE_DIR, "estimaciones", "db", "estimaciones.db")
DESDE, HASTA = "2026-09-17", "2026-10-16"
ESPERADAS = 42
ESPERADO_TOTAL = 8171.0


def main(excel):
    filas = list(openpyxl.load_workbook(excel, read_only=True, data_only=True).active.iter_rows(values_only=True))[1:]
    del_excel = {r[0]: float(r[5]) for r in filas if r[0] and r[9]}

    respaldo = os.path.join(BASE_DIR, "backups",
                            f"estimaciones_antes_cant42_{datetime.now():%Y%m%d_%H%M%S}.db")
    origen = sqlite3.connect(DB)
    destino = sqlite3.connect(respaldo)
    origen.backup(destino)
    destino.close()
    origen.close()
    print("respaldo:", respaldo)

    con = sqlite3.connect(DB, isolation_level=None)
    con.execute("BEGIN IMMEDIATE")
    try:
        db = con.execute("SELECT id_documento, cantidad FROM facturas "
                         "WHERE fase = 'MACAO 2' AND fecha BETWEEN ? AND ?", (DESDE, HASTA)).fetchall()
        cambios = [(i, q, del_excel[i]) for i, q in db if abs((q or 0) - del_excel[i]) > 0.001]
        if len(cambios) != ESPERADAS:
            raise SystemExit(f"hay {len(cambios)} diferencias, se esperaban {ESPERADAS} — no se toca nada")
        for i, vieja, nueva in cambios:
            cur = con.execute(
                "UPDATE facturas SET cantidad = ?, total = round(? * precio_unitario, 2) "
                "WHERE id_documento = ? AND cantidad IS ?", (nueva, nueva, i, vieja))
            if cur.rowcount != 1:
                raise SystemExit(f"{i}: el UPDATE afecto {cur.rowcount} filas — se revierte todo")
        suma = con.execute("SELECT round(sum(cantidad), 2) FROM facturas "
                           "WHERE fase = 'MACAO 2' AND fecha BETWEEN ? AND ?", (DESDE, HASTA)).fetchone()[0]
        if suma != ESPERADO_TOTAL:
            raise SystemExit(f"el periodo quedo en {suma}, se esperaba {ESPERADO_TOTAL} — se revierte todo")
        con.execute("COMMIT")
        print(f"OK: {len(cambios)} cantidades corregidas; MACAO 2 {DESDE} a {HASTA} = {suma} m3")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main(sys.argv[1])
