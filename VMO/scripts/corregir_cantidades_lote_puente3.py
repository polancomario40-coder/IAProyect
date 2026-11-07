# -*- coding: utf-8 -*-
"""Registro de la segunda tanda de correcciones de cantidad del lote
Puente 3 (2026-09-25): 56 conduces mas cuya cantidad Vision leyo mal,
encontrados con el barrido COMPLETO del Excel del escaneo contra la base
(todas las fases y productos, no solo MACAO 2).

Complementa a corregir_cantidades_macao2_ac050.py (las primeras 14). El
metodo fue el mismo: cada diferencia se verifico abriendo el escaneo — el
papel le dio la razon al Excel en los 69 casos legibles de las dos tandas
(el 70mo, M800015060, tiene el escaneo recortado y la cantidad no se ve:
va por el Excel). Las fallas de Vision van en las dos direcciones — invento
30 m3 en M700019353 (44 por 14) y borro 6 en M700019702 — y la causa
visible son las anotaciones manuscritas del laboratorio junto a la columna
CANTIDAD.

Este archivo YA SE APLICO a produccion el 2026-09-25 (corrio inline desde
la terminal del usuario, con backup previo); queda como registro y es
idempotente: en una segunda corrida ningun UPDATE encuentra la cantidad
vieja y aborta sin tocar nada.
"""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE_DIR, "estimaciones", "db", "estimaciones.db")

# id -> (cantidad mal leida por Vision; None = NULL, cantidad del papel)
CORRECCIONES = {
    "M700019430": (6.0, 8.0),
    "M800015042": (6.0, 7.0),
    "M800015058": (2.0, 7.0),
    "M800015060": (None, 7.0),  # escaneo recortado: valor del Excel
    "M800015153": (6.0, 8.0),
    "M800015182": (1.0, 7.0),
    "M700019475": (2.0, 7.0),
    "M800015223": (2.0, 7.0),
    "M800015226": (1.0, 7.0),
    "M800015235": (9.0, 7.0),
    "M800015308": (1.0, 7.0),
    "M800015359": (1.0, 7.0),
    "M800015362": (1.0, 7.0),
    "M800015367": (2.0, 7.0),
    "M800015374": (1.0, 7.0),
    "M800015401": (2.0, 7.0),
    "M800015412": (2.0, 7.0),
    "M800015506": (1.0, 7.0),
    "M800015519": (2.0, 7.0),
    "M800015535": (1.0, 7.0),
    "M800015556": (9.0, 7.0),
    "M800015571": (0.0, 6.0),
    "M700019601": (2.0, 7.0),
    "M700019608": (2.0, 7.0),
    "M800015652": (1.0, 7.0),
    "M800015719": (2.0, 7.0),
    "M800015723": (1.0, 7.0),
    "M800015724": (1.0, 7.0),
    "M800015990": (1.0, 7.0),
    "M800015992": (4.0, 7.0),
    "M800015999": (2.0, 7.0),
    "M800016025": (1.0, 7.0),
    "M300057005": (3.0, 8.0),
    "M300057039": (5.0, 8.0),
    "M700019757": (0.0, 6.0),
    "M700019765": (6.0, 8.0),
    "M700019771": (18.0, 10.0),
    "M800016044": (1.0, 7.0),
    "M800016045": (9.0, 7.0),
    "M800016051": (1.0, 7.0),
    "M800016068": (1.0, 7.0),
    "M800016075": (2.0, 7.0),
    "M800016076": (9.0, 7.0),
    "M800016082": (9.0, 7.0),
    "M700019353": (44.0, 14.0),
    "M700019358": (9.0, 5.0),
    "M700019359": (8.0, 6.0),
    "M800014995": (1.0, 7.0),
    "M700019555": (1.0, 7.0),
    "M700019568": (1.0, 7.0),
    "M700019572": (2.0, 5.0),
    "M700019573": (7.6, 7.0),
    "M700019582": (2.0, 7.0),
    "M800015663": (9.0, 7.0),
    "M700019661": (15.0, 14.0),
    "M800015806": (1.0, 10.0),
}
# tras aplicar, el Fc350 a/c=0.45 de MACAO 2 del periodo debe sumar esto
ESPERADO_AC045 = 7913.5


def main():
    con = sqlite3.connect(DB, isolation_level=None)
    con.execute("BEGIN IMMEDIATE")
    try:
        for idd, (vieja, nueva) in CORRECCIONES.items():
            if vieja is None:
                cur = con.execute(
                    """UPDATE facturas
                       SET cantidad = ?, total = round(? * precio_unitario, 2)
                       WHERE id_documento = ? AND cantidad IS NULL""",
                    (nueva, nueva, idd),
                )
            else:
                cur = con.execute(
                    """UPDATE facturas
                       SET cantidad = ?, total = round(? * precio_unitario, 2)
                       WHERE id_documento = ? AND abs(cantidad - ?) < 0.001""",
                    (nueva, nueva, idd, vieja),
                )
            if cur.rowcount != 1:
                raise SystemExit(
                    f"{idd}: el UPDATE afecto {cur.rowcount} filas, "
                    f"se esperaba 1 — se revierte todo (si ya se aplico "
                    f"antes, esto es lo esperado)"
                )
        suma = con.execute(
            """SELECT round(sum(cantidad), 1) FROM facturas
               WHERE fase = 'MACAO 2' AND descripcion LIKE '%a/c=0.45%'
               AND descripcion LIKE '%IIIA%' AND descripcion LIKE '%Fc350%'
               AND fecha BETWEEN '2026-08-17' AND '2026-09-16'""",
        ).fetchone()[0]
        if suma != ESPERADO_AC045:
            raise SystemExit(
                f"el a/c=0.45 quedo en {suma}, se esperaba {ESPERADO_AC045} "
                f"— se revierte todo"
            )
        con.execute("COMMIT")
        print(f"OK: {len(CORRECCIONES)} filas corregidas y verificadas")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
