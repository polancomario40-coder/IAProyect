# by a_oller
"""
unificar_compania_rebesa.py — Une las dos escrituras de CONSTRUCTORA REBESA
en `conduces.compania`, dejando el canonico sin coma (issue #24).

Contexto: la misma empresa esta escrita de dos formas en la tabla `conduces`:

    CONSTRUCTORA REBESA SRL     1,152 filas   <- canonico
    CONSTRUCTORA REBESA, SRL       75 filas   <- solo difiere en la coma

Son las unicas 2 variantes entre las 12 companias de la BD. Cualquier reporte
o factura filtrada por un nombre se pierde el otro: `generar_reporte_compania`
filtra con `compania = ?` exacto, asi que pedir "CONSTRUCTORA REBESA SRL"
hoy devuelve 1,152 de 1,227 conduces y calla los otros 75.

El canonico es el SIN coma: lo usan las 1,152 filas (incluidas 483 del mismo
lote viejo del que salieron las 75 con coma) y lo traen todas las
importaciones posteriores. Decision ya tomada en el issue #24, este script no
la reabre.

Este arreglo va ANTES del #31 (1,632 conduces sin precio, ~$39,4 millones).
Hoy las 75 filas con coma valen $1,594,861.60 y el canonico tiene 617 filas
sin precio; cuando esas filas tengan importe, un reporte filtrado por un solo
nombre escondera mucha mas plata de la que esconde hoy. Fusionar ahora son 75
filas; fusionar despues es arreglar sobre un problema mas caro.

Que escribe, exactamente: la columna `compania`, y NADA mas. El valor nuevo es
un literal constante (`CANONICO`), no sale de ninguna otra columna ni de
ninguna otra fila. Regla 8 del CLAUDE.md — nunca intercambiar valores entre
campos — y ademas se verifica: antes del UPDATE se toma la huella de las 75
filas con todas sus columnas menos `compania`, y despues del UPDATE se vuelve
a tomar; si cambio un solo byte de `precio`, `cantidad`, `fecha`, `producto`,
`almacen`, `estado`, `id_transporte` (o de cualquier columna que se agregue en
el futuro, se leen con PRAGMA table_info), se hace rollback.

Guardas (si alguna falla no se escribe NADA):
  - la BD tiene que existir y tener la tabla `conduces` con las columnas
    `id_conduce` y `compania`; si el esquema no es el esperado, aborta
  - las UNICAS escrituras que contengan "REBESA" tienen que ser las dos
    conocidas. Si aparece una tercera (`CONSTRUCTORA REBESA S.R.L.`,
    `Constructora Rebesa`, lo que sea), aborta: unir a ciegas seria adivinar
  - la variante con coma tiene que tener exactamente ESPERADO_VARIANTE filas
    y el canonico ESPERADO_CANONICO; si el universo cambio, aborta y hay que
    volver a auditar (se puede saltar con --forzar, a proposito incomodo)
  - tiene que haber exactamente ESPERADO_COMPANIAS companias distintas antes
  - ningun `id_conduce` de la variante puede existir ya bajo el canonico.
    Con el esquema de hoy esto es imposible (`id_conduce` es PRIMARY KEY de
    toda la tabla, y ademas el UPDATE no toca la PK), asi que la guarda es
    defensa en profundidad para el dia que el esquema cambie — NO es el
    riesgo real de esta operacion
  - despues del UPDATE: la cantidad de filas afectadas tiene que ser la
    contada, la huella de los otros campos tiene que ser identica, el monto
    total de la empresa tiene que conservarse, no puede quedar ninguna fila
    con la variante, y tienen que quedar ESPERADO_COMPANIAS - 1 companias
  - idempotente: si ya no quedan filas con coma y el canonico tiene la suma
    de las dos, informa "ya aplicado" y sale sin escribir. Correrlo dos veces
    deja la BD igual que correrlo una
  - transaccional: un solo UPDATE dentro de BEGIN IMMEDIATE, con rollback
    ante cualquier problema
  - respaldo obligatorio de la BD (API de backup de sqlite3, sirve aunque la
    BD este en uso) ANTES de escribir nada

Cache de reportes: `reportes/` y `facturas/` guardan HTML ya generado y
`generar_reporte_compania` lo sirve tal cual si el archivo existe. Un reporte
de CONSTRUCTORA REBESA SRL generado antes de esta fusion seguiria mostrando
1,152 conduces para siempre. Por eso, igual que importar.py / importar_xls.py
/ pagar.py, este script llama a `limpiar_cache_reportes()` despues de aplicar
— pero SOLO cuando escribio sobre la BD de produccion, para que probar contra
una copia no borre los reportes reales.

Uso:
    python scripts/unificar_compania_rebesa.py --check
    python scripts/unificar_compania_rebesa.py --check --db /ruta/copia.db
    python scripts/unificar_compania_rebesa.py --aplicar
"""

import argparse
import hashlib
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

from _cache_reportes import limpiar_cache_reportes  # noqa: E402

DB_PATH    = BASE_DIR / "conduces" / "db" / "conduces.db"
BACKUP_DIR = BASE_DIR / "backups" / "db"

CANONICO = "CONSTRUCTORA REBESA SRL"    # sin coma — el que queda
VARIANTE = "CONSTRUCTORA REBESA, SRL"   # con coma — el que se reescribe

# Marca para detectar cualquier tercera escritura de la misma empresa.
PATRON_EMPRESA = "%REBESA%"

# Universo auditado el 2026-08-31 contra db/conduces.db (solo lectura).
ESPERADO_VARIANTE  = 75
ESPERADO_CANONICO  = 1152
ESPERADO_COMPANIAS = 12


def respaldar(db_path: Path) -> Path:
    """Copia segura de la BD con la API de backup de sqlite3 (no es una copia
    de archivo: sirve aunque la BD este en uso). Devuelve la ruta de la copia.

    No se reusa `backup_db.py` porque su `main()` respalda las DOS bases del
    proyecto, siempre desde rutas fijas, escribe en `backups/backup_log.txt` y
    borra backups viejos por retencion. Este script tiene que poder respaldar
    la BD que le pasen por --db (una copia, en las pruebas) sin tocar nada de
    eso. Se usa la misma tecnica, que es lo que importa."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    sello   = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = BACKUP_DIR / f"conduces_pre_unificar_rebesa_{sello}.db"
    origen = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    copia  = sqlite3.connect(str(destino))
    try:
        with copia:
            origen.backup(copia)
    finally:
        copia.close()
        origen.close()
    return destino


def columnas_de(conn, tabla: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({tabla})")]


def huella_por_ids(conn, ids: list[str], cols_otras: list[str]) -> str:
    """SHA-1 de un conjunto de filas identificadas por `id_conduce`, con TODAS
    sus columnas menos `compania`, ordenadas por `id_conduce`.

    Es la prueba de la regla 8 del CLAUDE.md: se toma antes del UPDATE y
    despues, sobre las MISMAS filas (por id, que el UPDATE no toca). Si algun
    valor de `precio`, `cantidad`, `fecha`, `producto`, `almacen`, `estado`,
    `id_transporte` — o de cualquier columna futura — se hubiera movido, el
    hash cambia y se hace rollback."""
    seleccion = ", ".join(f'"{c}"' for c in cols_otras)
    h = hashlib.sha1()
    # En bloques, para no pasarse del limite de parametros de SQLite si algun
    # dia el universo es mucho mas grande (--forzar).
    ordenados = sorted(ids)
    for i in range(0, len(ordenados), 400):
        bloque = ordenados[i:i + 400]
        marcas = ", ".join("?" * len(bloque))
        filas = conn.execute(
            f"SELECT {seleccion} FROM conduces "
            f"WHERE id_conduce IN ({marcas}) ORDER BY id_conduce",
            bloque,
        ).fetchall()
        if len(filas) != len(bloque):
            raise RuntimeError(
                f"se esperaban {len(bloque)} filas por id y se leyeron "
                f"{len(filas)} — la BD cambio debajo del script")
        for f in filas:
            h.update(repr(tuple(f)).encode("utf-8"))
    return h.hexdigest()


def resumen(conn, compania: str) -> dict:
    """Filas, monto (precio x cantidad) y cuantas quedan sin precio."""
    fila = conn.execute(
        "SELECT COUNT(*), "
        "       ROUND(SUM(COALESCE(precio, 0) * COALESCE(cantidad, 0)), 2), "
        "       SUM(CASE WHEN precio IS NULL THEN 1 ELSE 0 END) "
        "FROM conduces WHERE compania = ?",
        (compania,),
    ).fetchone()
    return {"n": fila[0], "monto": fila[1] or 0.0, "sin_precio": fila[2] or 0}


def linea(etiqueta: str, r: dict) -> str:
    return (f"  {etiqueta:<28} {r['n']:>5} filas   ${r['monto']:>15,.2f}"
            f"   ({r['sin_precio']} sin precio)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    grupo = ap.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--check",   action="store_true",
                       help="Solo muestra que haria, sin escribir nada")
    grupo.add_argument("--aplicar", action="store_true",
                       help="Escribe el cambio en la base de datos")
    ap.add_argument("--db", type=Path, default=DB_PATH,
                    help=f"Ruta de conduces.db (por defecto {DB_PATH})")
    ap.add_argument("--forzar", action="store_true",
                    help=f"Aplica aunque los conteos no sean los esperados "
                         f"({ESPERADO_VARIANTE} con coma / {ESPERADO_CANONICO} sin coma)")
    args = ap.parse_args(argv)

    if not args.db.exists():
        sys.exit(f"ERROR: no se encuentra la BD: {args.db}")

    conn = sqlite3.connect(str(args.db))

    # --- Guarda 1: la BD tiene que tener la forma esperada -------------------
    tablas = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    if "conduces" not in tablas:
        conn.close()
        sys.exit(f"ERROR: {args.db} no tiene la tabla `conduces`. "
                 f"Tablas encontradas: {tablas}. No se escribio nada.")

    cols = columnas_de(conn, "conduces")
    faltan = [c for c in ("id_conduce", "compania") if c not in cols]
    if faltan:
        conn.close()
        sys.exit(f"ERROR: la tabla `conduces` no tiene la/s columna/s {faltan}. "
                 f"Columnas encontradas: {cols}. No se escribio nada.")
    # Todas menos `compania` — lo que NO se puede mover (regla 8).
    cols_otras = [c for c in cols if c != "compania"]

    print(f"BD        : {args.db}")
    print(f"Canonico  : {CANONICO!r}")
    print(f"Variante  : {VARIANTE!r}\n")

    # --- Guarda 2: no puede haber una tercera escritura de la empresa -------
    escrituras = conn.execute(
        "SELECT compania, COUNT(*) FROM conduces WHERE compania LIKE ? "
        "GROUP BY compania ORDER BY 2 DESC",
        (PATRON_EMPRESA,),
    ).fetchall()
    print("Escrituras que contienen REBESA:")
    for comp, n in escrituras:
        print(f"  {comp!r:<32} {n:>5} filas")
    inesperadas = [c for c, _ in escrituras if c not in (CANONICO, VARIANTE)]
    if inesperadas:
        conn.close()
        sys.exit(f"\nERROR: hay escritura/s inesperada/s de la empresa: "
                 f"{inesperadas}. Este script solo sabe unir {VARIANTE!r} a "
                 f"{CANONICO!r}; unir las demas seria adivinar. Volver a "
                 f"auditar el issue #24. No se escribio nada.")

    antes_var = resumen(conn, VARIANTE)
    antes_can = resumen(conn, CANONICO)
    companias_antes = conn.execute(
        "SELECT COUNT(DISTINCT compania) FROM conduces").fetchone()[0]

    print("\nANTES:")
    print(linea("sin coma (canonico)", antes_can))
    print(linea("con coma (variante)", antes_var))
    print(linea("TOTAL empresa", {
        "n": antes_can["n"] + antes_var["n"],
        "monto": round(antes_can["monto"] + antes_var["monto"], 2),
        "sin_precio": antes_can["sin_precio"] + antes_var["sin_precio"]}))
    print(f"  companias distintas en la BD: {companias_antes}")

    # --- Idempotencia: si ya no queda variante, no hay nada que hacer -------
    if antes_var["n"] == 0:
        conn.close()
        print("\nNo hay filas con la variante — ya esta aplicado. "
              "No se escribio nada.")
        return 0

    # --- Guarda 3: el universo tiene que ser el auditado ---------------------
    problemas = []
    if antes_var["n"] != ESPERADO_VARIANTE:
        problemas.append(f"la variante con coma tiene {antes_var['n']} filas, "
                         f"se esperaban {ESPERADO_VARIANTE}")
    if antes_can["n"] != ESPERADO_CANONICO:
        problemas.append(f"el canonico tiene {antes_can['n']} filas, "
                         f"se esperaban {ESPERADO_CANONICO}")
    if companias_antes != ESPERADO_COMPANIAS:
        problemas.append(f"hay {companias_antes} companias distintas, "
                         f"se esperaban {ESPERADO_COMPANIAS}")
    if problemas:
        aviso = "\nAVISO: el universo no es el auditado:\n" + \
                "".join(f"  - {p}\n" for p in problemas)
        if not args.forzar:
            conn.close()
            sys.exit(aviso + "No se escribio nada. Volver a auditar, o usar --forzar.")
        print(aviso + "Se sigue igual por --forzar.")

    # --- Guarda 4: colision de id_conduce (defensa en profundidad) ----------
    colisiones = conn.execute(
        "SELECT v.id_conduce FROM conduces v WHERE v.compania = ? AND EXISTS "
        "(SELECT 1 FROM conduces c WHERE c.compania = ? AND c.id_conduce = v.id_conduce)",
        (VARIANTE, CANONICO),
    ).fetchall()
    if colisiones:
        conn.close()
        sys.exit(f"\nERROR: {len(colisiones)} id_conduce existen bajo las dos "
                 f"escrituras (ej. {[c[0] for c in colisiones][:5]}). Unirlas "
                 f"chocaria con la llave primaria. No se escribio nada.")
    print("\nColisiones de id_conduce entre las dos escrituras: 0 (OK)")

    print(f"\nSe reescribiria `compania` en {antes_var['n']} filas "
          f"({VARIANTE!r} -> {CANONICO!r}).")
    print("Ningun otro campo se toca.")

    despues_esperado = {
        "n": antes_can["n"] + antes_var["n"],
        "monto": round(antes_can["monto"] + antes_var["monto"], 2),
        "sin_precio": antes_can["sin_precio"] + antes_var["sin_precio"],
    }
    print("\nDESPUES (esperado):")
    print(linea("sin coma (canonico)", despues_esperado))
    print(linea("con coma (variante)", {"n": 0, "monto": 0.0, "sin_precio": 0}))
    print(f"  companias distintas en la BD: {companias_antes - 1}")

    if args.check:
        conn.close()
        print("\n--check: no se escribio nada.")
        return 0

    # --- Huella de los campos que NO se pueden mover (regla 8) --------------
    ids_variante = [r[0] for r in conn.execute(
        "SELECT id_conduce FROM conduces WHERE compania = ?", (VARIANTE,))]
    huella_antes = huella_por_ids(conn, ids_variante, cols_otras)

    # --- Respaldo obligatorio ANTES de escribir -----------------------------
    copia = respaldar(args.db)
    print(f"\nRespaldo previo: {copia}")

    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "UPDATE conduces SET compania = ? WHERE compania = ?",
            (CANONICO, VARIANTE),
        )
        if cur.rowcount != antes_var["n"]:
            raise RuntimeError(
                f"el UPDATE afecto {cur.rowcount} filas, se esperaban "
                f"{antes_var['n']}")

        # Regla 8: las MISMAS filas (por id) tienen que traer todos sus otros
        # campos byte por byte iguales.
        huella_despues = huella_por_ids(conn, ids_variante, cols_otras)
        if huella_despues != huella_antes:
            raise RuntimeError(
                "cambio algun campo que no es `compania` en las filas "
                f"reescritas (huella {huella_antes[:12]} -> "
                f"{huella_despues[:12]}) — regla 8 del CLAUDE.md")

        # Y todas esas filas, buscadas por su id, tienen que haber quedado
        # bajo el canonico.
        bien = 0
        for i in range(0, len(ids_variante), 400):
            bloque = ids_variante[i:i + 400]
            marcas = ", ".join("?" * len(bloque))
            bien += conn.execute(
                f"SELECT COUNT(*) FROM conduces "
                f"WHERE compania = ? AND id_conduce IN ({marcas})",
                (CANONICO, *bloque),
            ).fetchone()[0]
        if bien != len(ids_variante):
            raise RuntimeError(
                f"solo {bien} de {len(ids_variante)} filas reescritas quedaron "
                f"bajo {CANONICO!r}")

        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        sys.exit(f"\nERROR — se revirtio todo, la BD quedo intacta: {e}\n"
                 f"El respaldo sigue en {copia}")

    # --- Verificacion posterior, contra la BD -------------------------------
    despues_var = resumen(conn, VARIANTE)
    despues_can = resumen(conn, CANONICO)
    companias_despues = conn.execute(
        "SELECT COUNT(DISTINCT compania) FROM conduces").fetchone()[0]

    fallas = []
    if despues_var["n"] != 0:
        fallas.append(f"quedaron {despues_var['n']} filas con la variante")
    if despues_can["n"] != despues_esperado["n"]:
        fallas.append(f"el canonico quedo en {despues_can['n']} filas, "
                      f"se esperaban {despues_esperado['n']}")
    if round(despues_can["monto"], 2) != despues_esperado["monto"]:
        fallas.append(f"el monto quedo en ${despues_can['monto']:,.2f}, "
                      f"se esperaba ${despues_esperado['monto']:,.2f}")
    if despues_can["sin_precio"] != despues_esperado["sin_precio"]:
        fallas.append(f"quedaron {despues_can['sin_precio']} filas sin precio, "
                      f"se esperaban {despues_esperado['sin_precio']}")
    if companias_despues != companias_antes - 1:
        fallas.append(f"quedaron {companias_despues} companias distintas, "
                      f"se esperaban {companias_antes - 1}")

    print(f"\nAplicado: {cur.rowcount} filas reescritas.")
    print("DESPUES (real):")
    print(linea("sin coma (canonico)", despues_can))
    print(linea("con coma (variante)", despues_var))
    print(f"  companias distintas en la BD: {companias_despues}")
    conn.close()

    if fallas:
        sys.exit("\nERROR: la verificacion posterior no cuadra:\n" +
                 "".join(f"  - {f}\n" for f in fallas) +
                 f"El respaldo previo esta en {copia}")

    # --- Cache de reportes --------------------------------------------------
    # Solo si se escribio sobre la BD de produccion: probar contra una copia
    # no debe borrar los reportes reales del proyecto.
    if args.db.resolve() == DB_PATH.resolve():
        borrados = limpiar_cache_reportes()
        print(f"\nCache de reportes/facturas limpiada: {borrados} HTML borrados "
              f"(si no, un reporte de {CANONICO!r} generado antes de la fusion "
              f"se seguiria sirviendo sin las {cur.rowcount} filas nuevas).")
    else:
        print(f"\nNo se limpio la cache de reportes: --db no es la BD de "
              f"produccion ({DB_PATH}).")

    print("\nListo. Verificar en el frontend que el reporte de "
          f"{CANONICO!r} muestre {despues_can['n']} conduces.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
