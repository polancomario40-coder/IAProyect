# by a_oller
"""
revisar_copias.py — Copias de las bases para una revision de bugs (/revisar).

La revision corre scripts contra datos reales, y un script de prueba que
escribe por error en la base de verdad es justo lo que no puede pasar. Por eso
la revision nunca abre las bases del repo: este script las copia con la API de
backup de sqlite3 (abiertas en solo lectura, seguro aunque el servidor este
usando la base) a una carpeta FUERA del repo, y la revision trabaja sobre esas
copias.

Tambien dice que Excel de origen hay a mano para cada modulo: la revision
compara los numeros de la app con los del Excel que reemplaza (2026-10-23: el
plan de Comercial en Ene-Jun era el real y no el presupuesto, y solo se vio
leyendo las formulas del dashboard).

Uso:
    python scripts/revisar_copias.py <destino> [modulo ...]
    modulos: conduces, estimaciones, logistica, comercial (sin modulo: todos)
"""

import os
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DESCARGAS = Path.home() / "Downloads"

BASES = {
    "conduces": REPO / "conduces" / "db" / "conduces.db",
    "estimaciones": REPO / "estimaciones" / "db" / "estimaciones.db",
    "logistica": REPO / "logistica" / "db" / "logistica.db",
    "comercial": REPO / "comercial" / "db" / "comercial.db",
}

# Los Excel que cada modulo reemplaza o lee, para comparar contra sus formulas.
# Solo se leen: la revision nunca los modifica.
EXCEL_DE_ORIGEN = {
    "comercial": [DESCARGAS / "DASHBOARD COMERCIAL 2026..xlsx",
                  DESCARGAS / "PLAN COMERCIAL - ROLLING FORECAST.xlsx"],
    "estimaciones": [Path(r"E:\ESTIMACIONES OCTUBRE")],
}


def copiar(destino: Path, modulos: list[str]) -> None:
    destino = destino.resolve()
    if destino == REPO or REPO in destino.parents:
        sys.exit(f"El destino {destino} esta dentro del repo: las copias van afuera.")
    destino.mkdir(parents=True, exist_ok=True)
    for m in modulos:
        origen = BASES[m]
        if not origen.exists():
            print(f"{m}: no hay base en {origen}")
            continue
        copia = destino / origen.name
        src = sqlite3.connect(f"file:{origen.as_posix()}?mode=ro", uri=True)
        dst = sqlite3.connect(copia)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        conn = sqlite3.connect(f"file:{copia.as_posix()}?mode=ro", uri=True)
        try:
            tablas = [t for (t,) in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY 1")]
            filas = ", ".join(f"{t} {conn.execute(f'SELECT COUNT(*) FROM [{t}]').fetchone()[0]}" for t in tablas)
        finally:
            conn.close()
        print(f"{m}: {copia}  ({filas})")
        for x in EXCEL_DE_ORIGEN.get(m, []):
            print(f"    excel de origen: {x}  {'(esta)' if x.exists() else '(NO ESTA)'}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pedidos = sys.argv[2:] or list(BASES)
    malos = [m for m in pedidos if m not in BASES]
    if malos:
        sys.exit(f"Modulo desconocido: {', '.join(malos)}. Son: {', '.join(BASES)}.")
    copiar(Path(sys.argv[1]), pedidos)
