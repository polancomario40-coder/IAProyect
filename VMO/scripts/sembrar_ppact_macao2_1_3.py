# -*- coding: utf-8 -*-
"""Siembra la base PPACT de los productos 1 y 3 de MACAO 2 (2026-10-20).

La PPACT de agosto (17/08 -> 16/09) salio con Acumulado Anterior N01-N06 de
15,50 (clave 1) y 67,00 (clave 3), escritos a mano: en
estimacion_acumulado_base solo estaba sembrada la PPACT de la clave 7
(1.767), asi que la pantalla deja vacio el acumulado de 1 y 3 y la PPACT de
septiembre salia sin esos renglones. Con la base sembrada, la pantalla los
precarga sola (acumulado y Cant. Proyecto).

Respalda la base antes. Inserta en una transaccion; si ya existen filas PPACT
para 1 o 3 no toca nada.

Uso: python scripts/sembrar_ppact_macao2_1_3.py
"""
import os
import sqlite3
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
import core  # noqa: E402

DB = os.path.join(BASE_DIR, "estimaciones", "db", "estimaciones.db")
SEMILLAS = {"1": 15.5, "3": 67.0}


def main():
    respaldo = os.path.join(BASE_DIR, "backups",
                            f"estimaciones_antes_ppact13_{datetime.now():%Y%m%d_%H%M%S}.db")
    origen = sqlite3.connect(DB)
    destino = sqlite3.connect(respaldo)
    origen.backup(destino)
    destino.close()
    origen.close()
    print("respaldo:", respaldo)

    con = sqlite3.connect(DB, isolation_level=None)
    con.execute("BEGIN IMMEDIATE")
    try:
        for clave, cantidad in SEMILLAS.items():
            ya = con.execute("SELECT cantidad_base FROM estimacion_acumulado_base WHERE empresa = 'DOMICEM' "
                             "AND fase = 'MACAO 2' AND clave = ? AND serie = 'ppact'", (clave,)).fetchone()
            if ya:
                raise SystemExit(f"clave {clave} ya tiene base PPACT ({ya[0]}) — no se toca nada")
            con.execute("INSERT INTO estimacion_acumulado_base (empresa, fase, clave, serie, fecha_base, "
                        "cantidad_base, cantidad_proyecto_principal) "
                        "VALUES ('DOMICEM', 'MACAO 2', ?, 'ppact', '2026-07-16', ?, NULL)", (clave, cantidad))
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    catalogo = core._est_catalogo_fase(con, "DOMICEM", "MACAO 2")
    por_clave = core._est_clasificar_series(con, "DOMICEM", "MACAO 2", catalogo,
                                            "2026-09-17", "2026-10-16")["por_clave"]
    con.close()
    for clave in ("1", "3", "7"):
        print(f"OK clave {clave}: acumulado PPACT {por_clave[clave]['ppact']['calculado']}")


if __name__ == "__main__":
    main()
