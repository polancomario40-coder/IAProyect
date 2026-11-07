# by a_oller
"""
corregir_descripcion_desde_excel.py — Repara facturas que quedaron sin
precio_unitario porque la descripcion que guardo Vision trae errores de OCR.

Contexto (2026-08-26): el precio se matchea por `descripcion` exacta (TRIM) +
fase. El pipeline del sitio web (`core.py`) guarda la descripcion que LEE
Vision, que en documentos escaneados sale con basura ("AM0. IIIA",
"Tolup. 02C", "Asg 3/8\"", "AMP UIA (UIA)"); el pipeline de lotes
(`scripts/importar_puente.py`) la toma del Excel, que viene tipeada limpia.
Por eso las facturas subidas por el sitio pueden quedar sin precio, y una sola
factura sin precio bloquea la generacion de toda una estimacion
(422 `precios_faltantes`, routes_estimaciones.py).

Este script toma el Excel como fuente de verdad para la descripcion — mismo
criterio que ya usa importar_puente.py — y recalcula precio y total.

Guardas (aborta la fila, no el script, si alguna falla):
  - la factura tiene que existir y estar SIN precio (idempotente: si ya tiene
    precio no se toca, para poder correrlo dos veces sin efecto)
  - la cantidad de la BD tiene que coincidir con la del Excel — si no
    coinciden, algo mas esta mal y no se toca nada de esa fila
  - la descripcion del Excel tiene que tener precio para esa fase

Nunca se mueven valores entre campos (regla critica del proyecto): solo se
reescriben `descripcion`, `precio_unitario` y `total`, cada uno con su valor.

Uso:
    python scripts/corregir_descripcion_desde_excel.py --check
    python scripts/corregir_descripcion_desde_excel.py --aplicar
    python scripts/corregir_descripcion_desde_excel.py --check --fase "MACAO 2"
"""

import argparse
import sqlite3
import sys
from pathlib import Path

import openpyxl

BASE_DIR   = Path(__file__).resolve().parent.parent
DB_PATH    = BASE_DIR / "estimaciones" / "db" / "estimaciones.db"
EXCEL_PATH = BASE_DIR / "conduces" / "archivos" / "CONDUCES 18-08-2026.xlsx"

# Columnas del Excel de lookup (mismo layout que usa importar_puente.py)
COL_CONDUCE  = 0
COL_PRODUCTO = 3
COL_CANTIDAD = 4


def cargar_excel(path: Path) -> dict:
    """{id_documento: (descripcion, cantidad)} del Excel de lookup."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    datos = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or not row[COL_CONDUCE]:
            continue
        conduce = str(row[COL_CONDUCE]).strip()
        desc    = (str(row[COL_PRODUCTO]).strip() if row[COL_PRODUCTO] else None)
        cant    = float(row[COL_CANTIDAD]) if row[COL_CANTIDAD] is not None else None
        datos[conduce] = (desc, cant)
    wb.close()
    return datos


def buscar_precio(conn, empresa: str, fase: str, descripcion: str):
    """Mismo matching que usa el resto del sistema: descripcion exacta (TRIM)
    + fase. DOMICEM siempre exige fase exacta; VMO admite el generico
    (fase IS NULL) como respaldo."""
    if empresa == "DOMICEM":
        row = conn.execute(
            "SELECT precio_unitario FROM precios_domicem "
            "WHERE TRIM(descripcion) = ? AND fase = ?",
            (descripcion, fase),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT precio_unitario FROM precios_vmo "
            "WHERE TRIM(descripcion) = ? AND (fase = ? OR fase IS NULL) "
            "ORDER BY fase IS NULL",
            (descripcion, fase),
        ).fetchone()
    return row[0] if row else None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    grupo = ap.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--check",   action="store_true",
                       help="Solo muestra que haria, sin escribir nada")
    grupo.add_argument("--aplicar", action="store_true",
                       help="Escribe los cambios en la base de datos")
    ap.add_argument("--fase", help="Limitar a una fase (ej. \"MACAO 2\")")
    args = ap.parse_args()

    if not EXCEL_PATH.exists():
        sys.exit(f"ERROR: no se encuentra el Excel de lookup: {EXCEL_PATH}")

    excel = cargar_excel(EXCEL_PATH)
    print(f"Excel: {len(excel)} filas cargadas de {EXCEL_PATH.name}\n")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    sql = ("SELECT id_documento, fecha, empresa, fase, cantidad, descripcion "
           "FROM facturas WHERE precio_unitario IS NULL")
    params = ()
    if args.fase:
        sql += " AND fase = ?"
        params = (args.fase,)
    candidatas = conn.execute(sql + " ORDER BY fecha", params).fetchall()

    print(f"Facturas sin precio_unitario: {len(candidatas)}\n")
    if not candidatas:
        print("Nada que corregir.")
        conn.close()
        return

    a_corregir, saltadas = [], []
    for f in candidatas:
        idd = f["id_documento"]
        if idd not in excel:
            saltadas.append((idd, "no esta en el Excel"))
            continue
        desc_excel, cant_excel = excel[idd]
        if not desc_excel:
            saltadas.append((idd, "el Excel no trae descripcion"))
            continue
        if cant_excel is None or float(f["cantidad"] or 0) != cant_excel:
            saltadas.append((idd, f"cantidad no coincide (BD={f['cantidad']} Excel={cant_excel})"))
            continue
        precio = buscar_precio(conn, f["empresa"], f["fase"], desc_excel)
        if precio is None:
            saltadas.append((idd, f"la descripcion del Excel no tiene precio en {f['fase']}"))
            continue
        total = round(precio * float(f["cantidad"]), 2)
        a_corregir.append({
            "id_documento": idd, "fecha": f["fecha"], "fase": f["fase"],
            "cantidad": f["cantidad"], "desc_vieja": f["descripcion"],
            "desc_nueva": desc_excel, "precio": precio, "total": total,
        })

    print(f"Se pueden corregir : {len(a_corregir)}")
    print(f"Se saltan          : {len(saltadas)}\n")

    for c in a_corregir:
        print(f"  {c['id_documento']:14} {c['fecha']}  {c['fase']:8} "
              f"cant={c['cantidad']:<6} precio={c['precio']:<8} total={c['total']}")
        print(f"      antes: {c['desc_vieja'][:78]!r}")
        print(f"      ahora: {c['desc_nueva'][:78]!r}")
    if saltadas:
        print("\n  SALTADAS:")
        for idd, motivo in saltadas:
            print(f"    {idd:14} {motivo}")

    if args.check:
        print("\n--check: no se escribio nada.")
        conn.close()
        return

    if not a_corregir:
        print("\nNo hay nada que aplicar.")
        conn.close()
        return

    try:
        conn.execute("BEGIN")
        for c in a_corregir:
            cur = conn.execute(
                "UPDATE facturas SET descripcion = ?, precio_unitario = ?, total = ? "
                "WHERE id_documento = ? AND precio_unitario IS NULL",
                (c["desc_nueva"], c["precio"], c["total"], c["id_documento"]),
            )
            if cur.rowcount != 1:
                raise RuntimeError(
                    f"{c['id_documento']}: el UPDATE afecto {cur.rowcount} filas, se esperaba 1"
                )
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        sys.exit(f"\nERROR — se revirtio todo, la BD quedo intacta: {e}")

    restantes = conn.execute(
        "SELECT COUNT(*) FROM facturas WHERE precio_unitario IS NULL"
        + (" AND fase = ?" if args.fase else ""),
        (args.fase,) if args.fase else (),
    ).fetchone()[0]
    conn.close()

    print(f"\nOK — {len(a_corregir)} facturas corregidas.")
    print(f"Facturas sin precio que quedan{f' en {args.fase}' if args.fase else ''}: {restantes}")


if __name__ == "__main__":
    main()
