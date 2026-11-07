# by a_oller
"""
reprocesar_errores_vision.py — Reprocesa los PDFs que fallaron con error de
parseo JSON durante la corrida de importar_puente.py, usando el modelo
fallback (Opus) directamente ya que Haiku fallo con ellos.

Uso:
    python scripts/reprocesar_errores_vision.py
"""

import sqlite3
import zipfile
from datetime import datetime

import anthropic
from dotenv import load_dotenv

from importar_puente import (
    BASE_DIR, DB_PATH, ZIP_PATH, VISION_MODEL_FALLBACK,
    load_excel, buscar_fila_excel, vision_extract, insert_factura,
)

load_dotenv(BASE_DIR / ".env")

ARCHIVOS_CON_ERROR = [
    "06-13-M8-12507.pdf", "06-17-M3-55788.pdf", "06-17-M8-12650.pdf",
    "06-19-M8-12735.pdf", "06-24-M8-12966.pdf",
    "07-22-M8-14013.pdf", "07-23-M3-56196.pdf",
]


def main():
    client = anthropic.Anthropic()
    # Issue #78: load_excel() ahora devuelve los DOS indices (por Codigo y
    # por Conduce); el lookup va por buscar_fila_excel, que ademas normaliza
    # mayusculas y cae al indice por id.
    por_codigo, por_id = load_excel()
    now = datetime.now().isoformat()

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    stats = {'ok': 0, 'duplicado': 0, 'sin_excel': 0, 'sin_sello': 0, 'error': 0}

    with zipfile.ZipFile(ZIP_PATH) as zf:
        nombres_zip = {name.split('/')[-1]: name for name in zf.namelist()}

        for fn in ARCHIVOS_CON_ERROR:
            print(f"  {fn}  [opus]", end=' ', flush=True)

            zipname = nombres_zip.get(fn)
            if not zipname:
                print("-> NO ENCONTRADO EN EL ZIP")
                stats['error'] += 1
                continue

            row = buscar_fila_excel(por_codigo, por_id, fn)
            if not row:
                print("-> SIN FILA EN EXCEL")
                stats['sin_excel'] += 1
                continue
            row = dict(row)
            row['archivo_pdf'] = fn

            try:
                pdf_bytes = zf.read(zipname)
                vdata = vision_extract(client, pdf_bytes, model=VISION_MODEL_FALLBACK)

                tiene_sello = vdata.get('tiene_sello', False)
                tiene_firma = vdata.get('tiene_firma', False)

                # Regla fase-condicional (issue #8, 2026-08-24): MACAO 2
                # exige sello (firma no bloquea — issue #7); cualquier otra
                # fase exige firma (sello no bloquea). Mismo cambio de
                # condicion que importar_puente.py. Sin doble-chequeo aca
                # (no lo tenia antes, no es parte de este cambio — script de
                # un lote historico especifico).
                if row['fase'] == 'MACAO 2':
                    bloqueado = not tiene_sello
                    motivo_str = "sin sello"
                else:
                    bloqueado = not tiene_firma
                    motivo_str = "sin firma"

                if bloqueado:
                    print(f"-> RECHAZADO ({motivo_str})")
                    stats['sin_sello'] += 1
                else:
                    inserted = insert_factura(cur, row, vdata, now, pdf_bytes=pdf_bytes, sin_firma=not tiene_firma)
                    if inserted:
                        stats['ok'] += 1
                        print("-> OK" + (" (sin firma)" if not tiene_firma else ""))
                    else:
                        stats['duplicado'] += 1
                        print("-> DUPLICADO")
                    conn.commit()

            except Exception as e:
                print(f"-> ERROR: {e}")
                stats['error'] += 1

    conn.close()

    print("\n" + "=" * 40)
    print("RESUMEN REPROCESO")
    print("=" * 40)
    print(f"Importados:     {stats['ok']}")
    print(f"Duplicados:     {stats['duplicado']}")
    print(f"Sin Excel:      {stats['sin_excel']}")
    print(f"Sin sello/firma:{stats['sin_sello']}")
    print(f"Errores:        {stats['error']}")


if __name__ == '__main__':
    main()
