# by a_oller
"""
corregir_clave_resuelta_cavernas_150.py — Corrige los 56 conduces (370 m3) de
CAVERNAS que quedaron apuntando al renglon equivocado de la estimacion.

Contexto (encontrado 2026-08-27, corregido 2026-08-28): antes de que existiera
el alias de descripcion del commit fe8e260, el sistema pedia resolver a mano
las descripciones que no matcheaban ningun producto del catalogo. Esas
resoluciones quedan guardadas PARA SIEMPRE en `facturas.clave_resuelta`, y
`/generar` les da prioridad sobre el catalogo:

    clave = clave_resuelta or catalogo_norm_a_clave.get(_est_normalizar(desc))
    (core.py:2207 y routes_estimaciones.py:422)

En una de esas resoluciones se eligio mal: 56 conduces cuya descripcion dice
`Hormigon 150 kg/cm2` quedaron resueltos a la clave 3 (`Hormigon 210`, $122)
cuando van en la clave 2 (`Hormigon 150`, $111). Generar CAVERNAS asi daria
370 x $122 = $45,140 en vez de 370 x $111 = $41,070 — $4,070 de mas, y en el
renglon equivocado de un documento oficial de CONFOTUR.

Tres pruebas independientes de que van en la clave 2:
  - la descripcion de la propia factura dice 150, no 210
  - el alias de fe8e260 (verificado contra el documento real N44) mapea esa
    descripcion exacta a la clave 2
  - el N44 de la empresa pone exactamente 370.00 m3 = $41,070.00 en la clave 2

Dos modos, porque son dos arreglos distintos:

  --modo limpiar    (por defecto) borra la resolucion manual (clave_resuelta
                    -> NULL) y deja que mande el catalogo + alias, que es la
                    fuente verificada. Recomendado: `_est_vista_previa()`
                    IGNORA clave_resuelta, asi que mientras el campo tenga
                    algo, la vista previa puede mostrar una cosa y el
                    documento generado salir con otra — que es exactamente
                    por lo que este error paso desapercibido. Con NULL los dos
                    caminos coinciden. Si algun dia el alias se rompiera,
                    estas facturas saldrian marcadas como sin_match (falla
                    ruidosa) en vez de irse calladas al renglon equivocado.

  --modo reasignar  escribe clave_resuelta = '2'. Mas explicito, pero deja
                    viva la divergencia vista-previa/generar y una correccion
                    futura del alias no llegaria nunca a estas 56 filas.

Guardas (si alguna falla no se escribe NADA):
  - solo toca filas con empresa=DOMICEM, fase=CAVERNAS, la descripcion exacta
    de abajo y clave_resuelta='3' — cualquier otra combinacion queda afuera
  - exige que el matcher vigente (catalogo + alias, importado de core.py)
    mapee esa descripcion a la clave 2; si no, aborta. El arreglo solo tiene
    sentido si el catalogo esta de acuerdo
  - exige encontrar exactamente ESPERADO_N filas y ESPERADO_M3 m3; si el
    universo cambio, aborta y hay que volver a auditar (se puede saltar con
    --forzar, a proposito incomodo)
  - idempotente: despues de aplicar no quedan candidatas, correrlo de nuevo
    no hace nada
  - transaccional: un solo UPDATE, con rollback ante cualquier problema
  - hace una copia de seguridad de la BD (API de backup de sqlite3) antes de
    escribir

No toca ningun otro campo, ni el acumulado base. Las 56 filas son del
2026-07-17 al 2026-08-14, posteriores al `fecha_base` 2026-07-16 de
`estimacion_acumulado_base`, asi que el acumulado sembrado no esta afectado y
no hay que resembrarlo.

Uso:
    python scripts/corregir_clave_resuelta_cavernas_150.py --check
    python scripts/corregir_clave_resuelta_cavernas_150.py --aplicar
    python scripts/corregir_clave_resuelta_cavernas_150.py --aplicar --modo reasignar
"""

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import core  # noqa: E402  (necesita BASE_DIR en el path)

DB_PATH     = BASE_DIR / "estimaciones" / "db" / "estimaciones.db"
BACKUP_DIR  = BASE_DIR / "backups" / "db"

EMPRESA = "DOMICEM"
FASE    = "CAVERNAS"
# Descripcion exacta tal como esta guardada en `facturas` (viene del Excel de
# conduces, fuente de verdad desde el issue #15). Se compara literal: si el
# texto cambiara, el script no encuentra nada y aborta, que es lo que se quiere.
DESCRIPCION = 'Hormigón 150 kg/cm2, Ag 3/4",T 35C, rev. 7" +/- 1"'

CLAVE_MALA     = "3"   # Hormigon 210 kg/cm2, $122 — donde quedaron
CLAVE_CORRECTA = "2"   # Hormigon 150 kg/cm2, $111 — donde van

ESPERADO_N  = 56
ESPERADO_M3 = 370.0


def respaldar(db_path: Path) -> Path:
    """Copia segura de la BD con la API de backup de sqlite3 (no copia de
    archivo: sirve aunque la BD este en uso). Devuelve la ruta de la copia."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    sello   = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = BACKUP_DIR / f"estimaciones_pre_fix370_{sello}.db"
    origen = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    copia  = sqlite3.connect(destino)
    with copia:
        origen.backup(copia)
    copia.close()
    origen.close()
    return destino


def precio_de(conn, clave: str):
    fila = conn.execute(
        "SELECT descripcion, precio_unitario FROM catalogo_estimacion "
        "WHERE empresa = ? AND fase = ? AND clave = ?",
        (EMPRESA, FASE, clave),
    ).fetchone()
    return fila


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    grupo = ap.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--check",   action="store_true",
                       help="Solo muestra que haria, sin escribir nada")
    grupo.add_argument("--aplicar", action="store_true",
                       help="Escribe el cambio en la base de datos")
    ap.add_argument("--modo", choices=("limpiar", "reasignar"), default="limpiar",
                    help="limpiar: clave_resuelta -> NULL (por defecto). "
                         "reasignar: clave_resuelta -> '2'")
    ap.add_argument("--db", type=Path, default=DB_PATH,
                    help=f"Ruta de estimaciones.db (por defecto {DB_PATH})")
    ap.add_argument("--forzar", action="store_true",
                    help="Aplica aunque el conteo no sea el esperado (56 / 370.0 m3)")
    args = ap.parse_args()

    if not args.db.exists():
        sys.exit(f"ERROR: no se encuentra la BD: {args.db}")

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    # --- Guarda 1: el catalogo vigente tiene que estar de acuerdo -------------
    cat  = core._est_catalogo_fase(conn, EMPRESA, FASE)
    if not cat:
        sys.exit(f"ERROR: no hay catalogo para {EMPRESA}/{FASE}")
    norm = core._est_catalogo_norm_a_clave(cat, EMPRESA, FASE)
    clave_matcher = norm.get(core._est_normalizar(DESCRIPCION))
    if clave_matcher != CLAVE_CORRECTA:
        sys.exit(
            f"ERROR: el matcher vigente manda esa descripcion a la clave "
            f"{clave_matcher!r}, no a la {CLAVE_CORRECTA!r}. El arreglo solo "
            f"tiene sentido si el catalogo/alias esta de acuerdo — revisar "
            f"_EST_ALIAS_DESCRIPCION_FACTURA antes de seguir."
        )

    mala     = precio_de(conn, CLAVE_MALA)
    correcta = precio_de(conn, CLAVE_CORRECTA)
    print(f"BD        : {args.db}")
    print(f"Matcher   : la descripcion mapea a la clave {clave_matcher} (OK)")
    print(f"  clave {CLAVE_MALA} (donde estan) : ${mala['precio_unitario']:>7} | {mala['descripcion']}")
    print(f"  clave {CLAVE_CORRECTA} (donde van)    : ${correcta['precio_unitario']:>7} | {correcta['descripcion']}\n")

    # --- Universo a tocar ----------------------------------------------------
    filas = conn.execute(
        "SELECT id_documento, fecha, cantidad FROM facturas "
        "WHERE empresa = ? AND fase = ? AND descripcion = ? AND clave_resuelta = ? "
        "ORDER BY fecha, id_documento",
        (EMPRESA, FASE, DESCRIPCION, CLAVE_MALA),
    ).fetchall()

    n  = len(filas)
    m3 = round(sum(float(f["cantidad"] or 0) for f in filas), 2)

    if n == 0:
        print("No hay nada que corregir — ya esta aplicado (o el universo cambio).")
        conn.close()
        return

    print(f"Candidatas: {n} conduces, {m3} m3, del {filas[0]['fecha']} al {filas[-1]['fecha']}")
    print(f"  hoy  : {m3} x ${mala['precio_unitario']} = ${m3 * mala['precio_unitario']:,.2f}  (clave {CLAVE_MALA})")
    print(f"  debe : {m3} x ${correcta['precio_unitario']} = ${m3 * correcta['precio_unitario']:,.2f}  (clave {CLAVE_CORRECTA})")
    print(f"  cobro de mas evitado: ${m3 * (mala['precio_unitario'] - correcta['precio_unitario']):,.2f}\n")

    for f in filas:
        print(f"  {f['id_documento']:14} {f['fecha']}  {f['cantidad']:>6} m3")

    # --- Guarda 2: el universo tiene que ser el auditado ---------------------
    if (n, m3) != (ESPERADO_N, ESPERADO_M3):
        aviso = (f"\nAVISO: se esperaban {ESPERADO_N} conduces / {ESPERADO_M3} m3 "
                 f"y hay {n} / {m3}.")
        if not args.forzar:
            conn.close()
            sys.exit(aviso + " No se escribio nada. Volver a auditar, o usar --forzar.")
        print(aviso + " Se sigue igual por --forzar.")

    if args.check:
        print(f"\n--check: no se escribio nada. Modo que se usaria: --modo {args.modo}.")
        conn.close()
        return

    # --- Aplicar -------------------------------------------------------------
    copia = respaldar(args.db)
    print(f"\nRespaldo previo: {copia}")

    nuevo_valor = None if args.modo == "limpiar" else CLAVE_CORRECTA
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "UPDATE facturas SET clave_resuelta = ? "
            "WHERE empresa = ? AND fase = ? AND descripcion = ? AND clave_resuelta = ?",
            (nuevo_valor, EMPRESA, FASE, DESCRIPCION, CLAVE_MALA),
        )
        if cur.rowcount != n:
            raise RuntimeError(
                f"el UPDATE afecto {cur.rowcount} filas, se esperaban {n}"
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        sys.exit(f"\nERROR — se revirtio todo, la BD quedo intacta: {e}\n"
                 f"El respaldo sigue en {copia}")

    # --- Verificacion posterior, contra la BD --------------------------------
    quedan = conn.execute(
        "SELECT COUNT(*) FROM facturas "
        "WHERE empresa = ? AND fase = ? AND descripcion = ? AND clave_resuelta = ?",
        (EMPRESA, FASE, DESCRIPCION, CLAVE_MALA),
    ).fetchone()[0]
    ahora = conn.execute(
        "SELECT clave_resuelta, COUNT(*), ROUND(SUM(cantidad), 2) FROM facturas "
        "WHERE empresa = ? AND fase = ? AND descripcion = ? "
        "GROUP BY clave_resuelta",
        (EMPRESA, FASE, DESCRIPCION),
    ).fetchall()

    print(f"\nAplicado ({args.modo}): {cur.rowcount} filas.")
    print(f"Quedan en la clave {CLAVE_MALA}: {quedan} (tiene que ser 0)")
    print("Estado de esa descripcion en la BD:")
    for r in ahora:
        print(f"  clave_resuelta={r[0]!r:>6}  n={r[1]:>3}  m3={r[2]}")
    conn.close()

    if quedan:
        sys.exit("ERROR: quedaron filas sin corregir.")
    print("\nListo. Verificar ahora en la vista previa de CAVERNAS que el "
          "renglon de la clave 2 muestre los 370 m3.")


if __name__ == "__main__":
    main()
