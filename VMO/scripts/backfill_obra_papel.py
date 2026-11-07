# by a_oller
"""
backfill_obra_papel.py — Rellena `facturas.obra_papel` (issue #67) corriendo
Vision sobre el PDF ya guardado de cada conduce.

`obra_papel` es la linea `OBRA:` impresa en el papel —DIMECA, CONCAVA,
LIDOMI—, un dato distinto de `obra` (que por el import masivo vale la fase) y
de `cliente` (que en las tres obras dice lo mismo). Hasta el issue #67 no se
guardaba en ninguna columna, asi que las filas importadas antes lo tienen en
NULL y para saber a que obra fue un conduce habia que abrir el escaneo.

Este script NO toca `obra`, `fase`, ni ninguna otra columna: solo escribe
`obra_papel`, y solo donde esta en NULL. Correrlo dos veces no vuelve a pagar
Vision por lo que ya se resolvio.

OJO — CADA FILA ES UNA LLAMADA A VISION Y ESO CUESTA PLATA. Son ~4.185 filas
en la base real. El script NO tiene un modo "todo": sin `--limite` procesa
todo lo que falte, asi que el default seguro para probar es `--dry-run`, que
no llama a Vision ni una vez.

Uso:
    python scripts/backfill_obra_papel.py --dry-run           # que haria, sin gastar
    python scripts/backfill_obra_papel.py --limite 10         # rellena 10 filas
    python scripts/backfill_obra_papel.py --limite 10 --dir dropoff/fixtures_obra

`--dir` apunta a otra carpeta de PDFs (por defecto
estimaciones/facturas/procesadas/, donde los deja el import). Una fila sin PDF
en disco se saltea y se cuenta aparte: no se puede rellenar sin el papel.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

# Los scripts asumen vivir UN NIVEL debajo de la raiz: moverlo de carpeta le
# cambia BASE_DIR sin lanzar ningun error, y pasaria a leer y escribir donde
# no es. Misma convencion que los otros ~22 scripts.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
sys.path.insert(0, str(BASE_DIR))
import core  # noqa: E402  (necesita BASE_DIR en el path)

DB_PATH        = BASE_DIR / "estimaciones" / "db" / "estimaciones.db"
PROCESADAS_DIR = BASE_DIR / "estimaciones" / "facturas" / "procesadas"


def filas_candidatas(conn):
    """Las filas que le faltan obra_papel Y tienen un archivo_pdf que
    referenciar. El orden es por id_documento para que dos corridas con el
    mismo --limite ataquen las mismas filas (reproducible), no un subconjunto
    al azar del que despues no se sabe que entro.

    El LIMIT NO va aca a proposito: --limite es un tope de GASTO (cuantas
    llamadas a Vision), y una fila cuyo PDF no esta en disco no gasta nada.
    Recortando en el SQL, un tramo de filas sin escaneo se comeria el limite
    entero sin rellenar ni una."""
    return conn.execute(
        "SELECT id_documento, archivo_pdf FROM facturas "
        "WHERE obra_papel IS NULL AND archivo_pdf IS NOT NULL AND archivo_pdf <> '' "
        "ORDER BY id_documento").fetchall()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--limite", type=int, default=None,
                    help="tope de llamadas a Vision (sin esto, TODAS las que falten). "
                         "Las filas sin PDF en disco no cuentan contra el tope")
    ap.add_argument("--dry-run", action="store_true",
                    help="lista lo que haria sin llamar a Vision ni escribir en la BD")
    ap.add_argument("--dir", default=None,
                    help=f"carpeta de PDFs (default: {PROCESADAS_DIR})")
    args = ap.parse_args()

    pdf_dir = Path(args.dir) if args.dir else PROCESADAS_DIR
    if not pdf_dir.is_absolute():
        pdf_dir = BASE_DIR / pdf_dir

    # La migracion del issue #67 es idempotente y vive en setup_est_db(): un
    # backfill sobre una BD anterior a la columna tiene que crearla, no
    # reventar con "no such column". core.EST_DB_PATH apunta a la misma BD
    # (mismo BASE_DIR), asi que esto no puede migrar una base distinta de la
    # que despues se escribe.
    core.setup_est_db()

    conn = sqlite3.connect(DB_PATH)
    try:
        total_null = conn.execute(
            "SELECT COUNT(*) FROM facturas WHERE obra_papel IS NULL").fetchone()[0]
        filas = filas_candidatas(conn)
        print(f"BD: {DB_PATH}")
        print(f"PDFs: {pdf_dir}")
        print(f"Filas con obra_papel NULL: {total_null} — candidatas (con archivo_pdf): {len(filas)}")
        print(f"Tope de llamadas a Vision: {args.limite if args.limite is not None else 'sin tope'}")
        if args.dry_run:
            print("\n--dry-run: no se llama a Vision ni se escribe nada.\n")

        stats = {"ok": 0, "sin_lectura": 0, "sin_pdf": 0, "error": 0}
        gastadas = 0
        for id_documento, archivo_pdf in filas:
            if args.limite is not None and gastadas >= args.limite:
                break
            ruta = pdf_dir / archivo_pdf
            if not ruta.exists():
                stats["sin_pdf"] += 1
                continue
            gastadas += 1
            if args.dry_run:
                print(f"  {id_documento:12} {archivo_pdf:24} -> (dry-run) llamaria a Vision")
                continue
            try:
                obra = core._extraer_obra_papel(ruta.read_bytes())
            except Exception as e:
                stats["error"] += 1
                print(f"  {id_documento:12} {archivo_pdf:24} -> ERROR: {e}")
                continue
            if obra is None:
                # Se distingue de "no se proceso": la lectura corrio y el
                # papel no dejo ver la etiqueta. Queda NULL a proposito, para
                # que una corrida futura la reintente.
                stats["sin_lectura"] += 1
                print(f"  {id_documento:12} {archivo_pdf:24} -> sin OBRA legible")
                continue
            # Solo obra_papel, y solo si sigue NULL: si otra corrida (o el
            # import) la lleno mientras tanto, no se pisa.
            conn.execute(
                "UPDATE facturas SET obra_papel = ? WHERE id_documento = ? AND obra_papel IS NULL",
                (obra, id_documento))
            conn.commit()
            stats["ok"] += 1
            print(f"  {id_documento:12} {archivo_pdf:24} -> {obra}")

        print(f"\nRellenadas: {stats['ok']} | sin OBRA legible: {stats['sin_lectura']} | "
              f"sin PDF: {stats['sin_pdf']} | errores: {stats['error']}")
        restantes = conn.execute(
            "SELECT COUNT(*) FROM facturas WHERE obra_papel IS NULL").fetchone()[0]
        print(f"Quedan con obra_papel NULL: {restantes}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
