# by a_oller
"""
migrar_solo_ppact_a_principal.py — mueve las filas de las 3 fases solo-PPACT de
serie='ppact' a serie='principal' en estimacion_acumulado_base (issue #14).

Contexto: el seed del issue #13 sembro DOMICEM/VIVIENDAS, VMO/PODIUM-1-2-3 y
VMO/EXTERIORES bajo serie='ppact' con la serie principal vacia. Eso las dejaba
INERTES: _est_clasificar_series() (core.py) hace `continue` cuando un producto
no tiene fila serie='principal', asi que nunca leia la fila 'ppact' sembrada y
devolvia ppact.calculado=None. Verificado contra la BD real: el resultado de
vista-previa salia identico antes y despues de sembrar.

En esas 3 fases el PPACT ES el contrato (EST_OC_CONTRATO ya devuelve el texto
"PPACT" para ellas) — o sea que es su serie PRINCIPAL, no una serie de
desborde: no hay ningun contrato numerado del cual desbordar. Con los datos en
serie='principal' y cantidad_proyecto_principal=NULL (PPACT nunca tiene techo)
funciona sin ningun cambio de codigo.

Verificado antes de escribir este script, contra una copia de la BD real:
- Las 3 fases pasan a devolver principal.calculado real (2/9, 1/3 y 13/15
  productos respectivamente) con tope=None.
- Las 6 fases con contrato principal quedan IDENTICAS (sin regresion).
- La clasificacion de facturas NO se mueve: siguen yendo todas a 'principal'
  (VMO/EXTERIORES: 53 facturas, 345.0 m3, mismo hash de ids antes y despues),
  asi que estimaciones_generar() queda intacto.

Idempotente: si no queda ninguna fila serie='ppact' de esas 3 fases, no hace
nada. Transaccional: si algo falla a mitad, no queda nada a medias.

Uso:
    python scripts/migrar_solo_ppact_a_principal.py
    python scripts/migrar_solo_ppact_a_principal.py <ruta_db>
"""

import argparse
import os
import sqlite3
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "estimaciones", "db", "estimaciones.db")

FASES_SOLO_PPACT = [
    ("DOMICEM", "VIVIENDAS"),
    ("VMO", "PODIUM-1-2-3"),
    ("VMO", "EXTERIORES"),
]

# cuantas filas esperamos mover por fase (sembradas por el issue #13)
FILAS_ESPERADAS = {
    ("DOMICEM", "VIVIENDAS"): 2,
    ("VMO", "PODIUM-1-2-3"): 1,
    ("VMO", "EXTERIORES"): 13,
}


def _contar(conn, empresa, fase, serie):
    return conn.execute(
        "SELECT COUNT(*) FROM estimacion_acumulado_base "
        "WHERE empresa = ? AND fase = ? AND serie = ?",
        (empresa, fase, serie),
    ).fetchone()[0]


def migrar(db_path=DEFAULT_DB_PATH):
    """Devuelve {(empresa, fase): (movidas, ya_estaban)}."""
    conn = sqlite3.connect(db_path)
    try:
        # Validacion previa: nunca migrar sobre un estado que no reconocemos.
        # Si una fase ya tiene filas 'principal' Y todavia tiene 'ppact', algo
        # quedo a medias o alguien toco la tabla a mano — abortar sin escribir.
        for empresa, fase in FASES_SOLO_PPACT:
            n_ppact = _contar(conn, empresa, fase, "ppact")
            n_principal = _contar(conn, empresa, fase, "principal")
            esperadas = FILAS_ESPERADAS[(empresa, fase)]
            if n_ppact and n_principal:
                print(
                    f"ERROR {empresa}/{fase}: tiene {n_ppact} filas 'ppact' Y "
                    f"{n_principal} filas 'principal' al mismo tiempo — estado "
                    "inesperado, no se migro nada.",
                    file=sys.stderr,
                )
                sys.exit(1)
            if n_ppact and n_ppact != esperadas:
                print(
                    f"ERROR {empresa}/{fase}: tiene {n_ppact} filas 'ppact', se "
                    f"esperaban {esperadas} (las que sembro el issue #13) — no se "
                    "migro nada.",
                    file=sys.stderr,
                )
                sys.exit(1)

        resultado = {}
        conn.execute("BEGIN")
        try:
            for empresa, fase in FASES_SOLO_PPACT:
                antes_ppact = _contar(conn, empresa, fase, "ppact")
                antes_principal = _contar(conn, empresa, fase, "principal")
                if antes_ppact:
                    # cantidad_proyecto_principal se deja explicitamente en NULL:
                    # PPACT nunca tiene techo. Las filas ya venian con NULL (el
                    # seed del #13 nunca lo escribia para serie='ppact'), pero se
                    # fuerza igual para que el resultado no dependa de eso.
                    conn.execute(
                        "UPDATE estimacion_acumulado_base "
                        "SET serie = 'principal', cantidad_proyecto_principal = NULL "
                        "WHERE empresa = ? AND fase = ? AND serie = 'ppact'",
                        (empresa, fase),
                    )
                resultado[(empresa, fase)] = (antes_ppact, antes_principal)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return resultado
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Mueve las 3 fases solo-PPACT de serie='ppact' a serie='principal' (issue #14)"
    )
    parser.add_argument("db_path", nargs="?", default=DEFAULT_DB_PATH, help="Ruta de estimaciones.db")
    args = parser.parse_args()
    resultado = migrar(args.db_path)
    total = 0
    for (empresa, fase), (movidas, ya_estaban) in resultado.items():
        total += movidas
        estado = f"movidas={movidas}" if movidas else f"ya migrada ({ya_estaban} filas principal)"
        print(f"{empresa}/{fase:<16} {estado}")
    print(f"RESUMEN: {total} filas movidas de 'ppact' a 'principal'")


if __name__ == "__main__":
    main()
