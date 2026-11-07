# Verificacion manual del issue #16 (criterios 1 y 2): corre
# _est_clasificar_series() en MODO LECTURA sobre la BD de produccion para el
# periodo 2026-07-17..2026-08-16, las 9 fases, y dumpea un JSON comparable.
# Correrlo en el commit anterior al cambio y en este, y diffear los JSON:
# la unica diferencia esperada es VMO/CEDIS clave 2 (5/2 -> 0/7).
# Uso: python scripts/verificar_issue16_clasificador.py salida.json
import json
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402

DB_RO = "file:C:/Users/axelo/vmo/conduces/estimaciones/db/estimaciones.db?mode=ro"
DESDE, HASTA = "2026-07-17", "2026-08-16"

conn = sqlite3.connect(DB_RO, uri=True)
fases = conn.execute(
    "SELECT DISTINCT empresa, fase FROM catalogo_estimacion ORDER BY empresa, fase"
).fetchall()

salida = {}
for empresa, fase in fases:
    catalogo = core._est_catalogo_fase(conn, empresa, fase)
    r = core._est_clasificar_series(conn, empresa, fase, catalogo, DESDE, HASTA)
    lote = {}
    for id_doc, clave, serie, fecha, cantidad, pu, desc in r["facturas_periodo"]:
        d = lote.setdefault(clave, {"principal": 0.0, "ppact": 0.0})
        d[serie] += cantidad
    salida[f"{empresa}/{fase}"] = {
        "por_clave": r["por_clave"],
        "lote_por_clave_y_serie": lote,
        "facturas_periodo": [list(f) for f in r["facturas_periodo"]],
        "sin_resolver": r["sin_resolver"],
        "aviso": r.get("aviso_acumulado_por_factura", "NO_EXISTE_TODAVIA"),
    }
conn.close()

with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(salida, f, ensure_ascii=False, indent=1, sort_keys=True)
print(f"escrito {sys.argv[1]} ({len(salida)} fases)")
