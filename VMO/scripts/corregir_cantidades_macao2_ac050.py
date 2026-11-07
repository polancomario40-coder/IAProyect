# -*- coding: utf-8 -*-
"""Corrige la cantidad de 14 conduces del producto Fc350 a/c=0.50 de MACAO 2
(periodo 2026-08-17 -> 2026-09-16) que Vision leyo mal.

El hallazgo (2026-09-25): el documento generado daba 2.033,5 m3 para la clave
del a/c=0.50 y el cuadre del cliente esperaba 2.109,5. El cruce contra el
Excel del escaneo (dropoff/Conduces Puente 3.xlsx, 1.825 filas cargadas a
mano) encontro los mismos 302 conduces con 14 cantidades distintas, cuya
diferencia suma exactamente 76,0. Se abrieron los 14 escaneos y el papel le
da la razon al Excel en los 14: todos dicen 7,00 (y M700019702 dice 6,00).
La causa visible: anotaciones manuscritas de laboratorio al lado de la
columna CANTIDAD que confundieron a Vision.

Corre en una transaccion: cada UPDATE exige la cantidad vieja exacta y
afectar 1 fila, y al final la suma del producto debe dar 2.109,5 o se
revierte todo. Tambien actualiza `total` (cantidad x precio_unitario), que
esta guardado, no calculado al vuelo.

Correr scripts/backup_db.py antes. Es idempotente por diseño: en una segunda
corrida los UPDATE no encuentran la cantidad vieja y el script aborta sin
tocar nada.
"""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE_DIR, "estimaciones", "db", "estimaciones.db")

# id -> (cantidad mal leida por Vision, cantidad del papel)
CORRECCIONES = {
    "M700019512": (2.0, 7.0),
    "M700019564": (2.0, 7.0),
    "M700019702": (0.0, 6.0),
    "M800015128": (2.0, 7.0),
    "M800015220": (1.0, 7.0),
    "M800015407": (1.0, 7.0),
    "M800015449": (1.0, 7.0),
    "M800015453": (1.0, 7.0),
    "M800015541": (1.0, 7.0),
    "M800015683": (4.0, 7.0),
    "M800015700": (1.0, 7.0),
    "M800015974": (2.0, 7.0),
    "M800015982": (1.0, 7.0),
    "M800016040": (2.0, 7.0),
}
ESPERADO_TOTAL = 2109.5
PRODUCTO_LIKE = "%a/c=0.50, rev. 6%"


def main():
    con = sqlite3.connect(DB, isolation_level=None)
    con.execute("BEGIN IMMEDIATE")
    try:
        for idd, (vieja, nueva) in CORRECCIONES.items():
            cur = con.execute(
                """UPDATE facturas
                   SET cantidad = ?, total = round(? * precio_unitario, 2)
                   WHERE id_documento = ? AND cantidad = ?""",
                (nueva, nueva, idd, vieja),
            )
            if cur.rowcount != 1:
                raise SystemExit(
                    f"{idd}: el UPDATE afecto {cur.rowcount} filas, "
                    f"se esperaba 1 — se revierte todo"
                )
        suma = con.execute(
            """SELECT round(sum(cantidad), 1) FROM facturas
               WHERE fase = 'MACAO 2' AND descripcion LIKE ?
               AND descripcion LIKE '%IIIA%'
               AND fecha BETWEEN '2026-08-17' AND '2026-09-16'""",
            (PRODUCTO_LIKE,),
        ).fetchone()[0]
        if suma != ESPERADO_TOTAL:
            raise SystemExit(
                f"la suma quedo en {suma}, se esperaba {ESPERADO_TOTAL} — "
                f"se revierte todo"
            )
        con.execute("COMMIT")
        print(f"OK: 14 filas corregidas; a/c=0.50 de MACAO 2 queda en {suma} m3")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
