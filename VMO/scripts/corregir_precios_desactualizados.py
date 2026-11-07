# by a_oller
"""
corregir_precios_desactualizados.py — Re-precia las facturas cuyo
`precio_unitario` guardado ya no coincide con lo que dice la lista de precios
vigente.

Contexto (issue #39, encontrado 2026-09-02): 40 facturas cargan un precio que
no existe en ninguna lista actual. Salian de una hoja llamada `VMO - DOMICEM`
que `Lista de precios.xlsx` tenia antes del 2026-08-19 y que hoy no esta,
reemplazada por `Lista de precios - VMO` con precios por fase. Los cuatro
precios viejos ($180.50, $120.78, $153.30, $106.70) estan los cuatro en esa
hoja del respaldo `backups/Lista de precios_pre-20260819.xlsx` y ninguno en la
lista de hoy. No es coincidencia: es una sola hoja borrada.

La causa de fondo: `scripts/backfill_precios.py` solo rellena precios NULL
(`WHERE precio_unitario IS NULL`). Nunca re-precia una fila que ya trae un
precio, aunque la lista haya cambiado debajo, asi que actualizar el xlsx no
tiene forma de propagarse a lo ya importado. Este script es la pieza que
faltaba.

ANTES DE ASUSTARSE CON EL MONTO: la diferencia suma $1,266.08, pero **no es
plata**. `facturas.precio_unitario` no se usa nunca para calcular dinero. Se
usa para UNA sola cosa: una comprobacion de presencia en
`routes_estimaciones.py`, que bloquea la generacion con `precios_faltantes` si
alguna factura de una clave lo tiene en NULL. El dinero de las estimaciones
sale del P.U. del CATALOGO (`catalogo_estimacion`), como dice explicito el
docstring de `_est_clasificar_series()` en core.py. O sea que ninguna de estas
40 filas produjo jamas un numero equivocado en un documento entregado.

Esto es higiene de datos, no una correccion financiera. Se hace igual porque
una columna que dice $180.50 cuando el precio pactado es $186.98 induce a
error a cualquiera que lea la base — de hecho indujo a error al analisis que
abrio este issue, que reporto los $1,266.08 como subfacturacion.

La fuente de verdad es `core._est_buscar_precio()`, la MISMA primitiva que usa
el importador. No se reimplementa la busqueda: si el criterio de matcheo
cambiara, este script cambia con el.

Guardas (si alguna falla no se escribe NADA):
  - solo toca filas donde `_est_buscar_precio()` devuelve un precio Y el
    guardado es distinto. Las que tienen NULL no se tocan: esas son trabajo de
    `backfill_precios.py`, y hoy son 2 cuya descripcion no matchea ninguna fila
    de la lista, asi que este script tampoco podria resolverlas.
  - exige encontrar exactamente ESPERADO_N filas; si el universo cambio
    respecto de lo auditado, aborta (salvo --forzar)
  - respaldo de la BD con la API `sqlite3.Connection.backup()` antes de
    escribir (no copia de archivo: sirve aunque la BD este en uso)
  - UPDATE transaccional: si el rowcount no coincide con lo planeado, ROLLBACK
  - verificacion posterior LEYENDO LA BD de nuevo, no confiando en lo que el
    script cree haber hecho

Tambien recalcula `total` (precio x cantidad) para que la fila no quede
internamente inconsistente.

Uso:
    python scripts/corregir_precios_desactualizados.py --check
    python scripts/corregir_precios_desactualizados.py --aplicar

`--check` sirve ademas como detector periodico: correrlo despues de cada
actualizacion de `Lista de precios.xlsx` dice si quedo deriva.
"""

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import core  # noqa: E402  (necesita BASE_DIR en el path)

DB_PATH    = BASE_DIR / "estimaciones" / "db" / "estimaciones.db"
BACKUP_DIR = BASE_DIR / "backups" / "db"

# Universo auditado el 2026-09-02 contra estimaciones.db. Si el conteo real no
# coincide, algo cambio desde entonces y hay que volver a mirar antes de
# escribir — no ajustar este numero sin auditar.
ESPERADO_N = 40


def respaldar(db_path: Path) -> Path:
    """Copia segura de la BD con la API de backup de sqlite3 (no copia de
    archivo: sirve aunque la BD este en uso). Devuelve la ruta de la copia."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    sello   = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = BACKUP_DIR / f"estimaciones_pre_reprecio_{sello}.db"
    origen = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    copia  = sqlite3.connect(destino)
    with copia:
        origen.backup(copia)
    copia.close()
    origen.close()
    return destino


def desactualizadas(conn):
    """Las filas cuyo precio guardado difiere del que da la lista vigente.

    Devuelve una lista de dicts. Compara con tolerancia de medio centavo
    porque los dos lados son REAL de sqlite y una igualdad exacta sobre
    flotantes daria falsos positivos."""
    filas = conn.execute(
        "SELECT id_documento, fecha, empresa, fase, descripcion, cantidad, "
        "       precio_unitario "
        "FROM facturas WHERE precio_unitario IS NOT NULL "
        "ORDER BY fase, id_documento"
    ).fetchall()
    fuera = []
    for f in filas:
        vigente = core._est_buscar_precio(conn, f["empresa"], f["fase"], f["descripcion"])
        if vigente is None:
            continue
        if abs(vigente - f["precio_unitario"]) <= 0.005:
            continue
        fuera.append({
            "id_documento": f["id_documento"],
            "fecha":        f["fecha"],
            "empresa":      f["empresa"],
            "fase":         f["fase"],
            "descripcion":  f["descripcion"],
            "cantidad":     f["cantidad"],
            "guardado":     f["precio_unitario"],
            "vigente":      vigente,
        })
    return fuera


def resumir(fuera):
    """Agrupa por (fase, precio viejo, precio nuevo) para que el --check se lea
    de un vistazo en vez de listar 40 lineas sueltas."""
    grupos = {}
    for f in fuera:
        k = (f["fase"], f["guardado"], f["vigente"])
        g = grupos.setdefault(k, {"n": 0, "m3": 0.0, "dif": 0.0})
        g["n"]   += 1
        g["m3"]  += f["cantidad"] or 0.0
        g["dif"] += (f["vigente"] - f["guardado"]) * (f["cantidad"] or 0.0)
    return grupos


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    grupo = ap.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--check",   action="store_true",
                       help="Solo muestra que haria, sin escribir nada")
    grupo.add_argument("--aplicar", action="store_true",
                       help="Escribe los precios nuevos en la base de datos")
    ap.add_argument("--db", type=Path, default=DB_PATH,
                    help=f"Ruta de estimaciones.db (por defecto {DB_PATH})")
    ap.add_argument("--forzar", action="store_true",
                    help=f"Aplica aunque el conteo no sea el esperado ({ESPERADO_N})")
    args = ap.parse_args()

    if not args.db.exists():
        sys.exit(f"ERROR: no se encuentra la BD: {args.db}")

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    fuera = desactualizadas(conn)

    if not fuera:
        print("No hay precios desactualizados: todas las facturas con precio "
              "coinciden con la lista vigente.")
        conn.close()
        return 0

    grupos = resumir(fuera)
    print(f"\n{len(fuera)} facturas con el precio desactualizado:\n")
    for (fase, viejo, nuevo), g in sorted(grupos.items(), key=lambda x: -abs(x[1]["dif"])):
        print(f"  {fase:24} ${viejo:>8,.2f} -> ${nuevo:>8,.2f}   "
              f"{g['n']:>3} facturas, {g['m3']:>7,.1f} m3, "
              f"diferencia ${g['dif']:>9,.2f}")
    total_dif = sum(g["dif"] for g in grupos.values())
    print(f"\n  {'TOTAL':24} {'':>8}    {'':>8}   {len(fuera):>3} facturas, "
          f"{'':>7}    diferencia ${total_dif:>9,.2f}")
    print("\n  Recordatorio: `facturas.precio_unitario` NO se usa para calcular "
          "dinero.\n  El P.U. de los documentos sale de `catalogo_estimacion`. "
          "Esa diferencia\n  no aparecio nunca en una estimacion entregada.")

    # --- Guarda: el universo tiene que ser el auditado ----------------------
    if len(fuera) != ESPERADO_N:
        msg = (f"\nATENCION: se esperaban {ESPERADO_N} filas y hay {len(fuera)}. "
               f"El universo cambio desde la auditoria del 2026-09-02.")
        if not args.forzar:
            conn.close()
            sys.exit(msg + "\nRevisar a mano, o usar --forzar si el cambio es esperado.")
        print(msg + "\nSe continua igual por --forzar.")

    if args.check:
        print("\n--check: no se escribio nada. Usar --aplicar para corregir.")
        conn.close()
        return 0

    # --- Respaldo antes de tocar nada ---------------------------------------
    copia = respaldar(args.db)
    print(f"\nRespaldo: {copia}")

    # --- UPDATE transaccional -----------------------------------------------
    try:
        with conn:
            tocadas = 0
            for f in fuera:
                nuevo_total = (round(f["vigente"] * f["cantidad"], 2)
                               if f["cantidad"] is not None else None)
                cur = conn.execute(
                    "UPDATE facturas SET precio_unitario = ?, total = ? "
                    "WHERE id_documento = ? AND precio_unitario = ?",
                    (f["vigente"], nuevo_total, f["id_documento"], f["guardado"]),
                )
                if cur.rowcount != 1:
                    raise RuntimeError(
                        f"{f['id_documento']}: el UPDATE afecto {cur.rowcount} filas, "
                        f"se esperaba 1 — se revierte todo")
                tocadas += 1
            if tocadas != len(fuera):
                raise RuntimeError(
                    f"se actualizaron {tocadas} de {len(fuera)} — se revierte todo")
    except Exception as e:
        conn.close()
        sys.exit(f"\nERROR, no se escribio nada: {e}\nLa BD quedo como estaba. "
                 f"Respaldo en {copia}")

    print(f"\n{tocadas} facturas actualizadas.")

    # --- Verificacion posterior: se relee la BD, no se confia en el script ---
    restantes = desactualizadas(conn)
    conn.close()
    if restantes:
        print(f"\nATENCION: despues del UPDATE siguen quedando {len(restantes)} "
              f"filas desactualizadas. Revisar a mano.")
        return 1
    print("Verificado releyendo la BD: no queda ninguna desactualizada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
