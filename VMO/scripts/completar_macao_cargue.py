# by a_oller
"""
completar_macao_cargue.py — Agrega a los dias ya guardados los viajes de Macao
que el Excel de cargue traia y la app descartaba al leerlo (hasta el
2026-10-28). Los necesita el indicador de camiones; el cumplimiento no los ve
(restaurarDia los separa), asi que no cambia ningun porcentaje.

Lee los "Tiempo de Carga por ficha DD-MM-AAAA.xls" de una carpeta con el mismo
lector de la app (parseCargueSheets, via node) y, por cada dia guardado que
todavia no tenga viajes de Macao, los agrega al final de logistica_cargue.
Es idempotente: un dia que ya los tiene no se toca.

Uso:
    python scripts/completar_macao_cargue.py <base.db> <carpeta_excels>            (solo muestra)
    python scripts/completar_macao_cargue.py <base.db> <carpeta_excels> --aplicar   (escribe)

Correrlo primero sobre una COPIA de la base; con --aplicar sobre la real
deja antes un respaldo al lado (logistica.db.antes-macao-AAAAMMDD-HHMMSS).
"""
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LEER_JS = r"""
const fs = require('fs');
const XLSX = require(process.argv[1] + '/static/vendor/xlsx-0.20.3.full.min.js');
const L = require(process.argv[1] + '/static/logistica.logic.js');
const out = {};
for (const f of process.argv.slice(2)) {
  const wb = XLSX.read(fs.readFileSync(f), {type: 'array', cellDates: false});
  const p = L.parseCargueSheets(wb.SheetNames.map(nombre => ({nombre,
    rows: XLSX.utils.sheet_to_json(wb.Sheets[nombre], {header: 1, defval: null, raw: true})})));
  if (p.fecha) out[p.fecha] = p.macao;
}
process.stdout.write(JSON.stringify(out));
"""


def leer_macao(carpeta):
    archivos = sorted(os.path.join(carpeta, f) for f in os.listdir(carpeta)
                      if re.fullmatch(r"Tiempo de Carga por ficha \d\d-\d\d-\d{4}\.xls", f))
    if not archivos:
        return {}
    res = subprocess.run(["node", "-e", LEER_JS, REPO, *archivos], capture_output=True, text=True,
                         encoding="utf-8", check=True)
    return json.loads(res.stdout)


def es_macao(cliente, obra):
    return any("MACAO" in re.sub(r"[^A-Z0-9 ]", " ", str(t or "").upper()) for t in (cliente, obra))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    base, carpeta, aplicar = sys.argv[1], sys.argv[2], "--aplicar" in sys.argv
    macao = leer_macao(carpeta)
    conn = sqlite3.connect(base)
    guardados = [f[0] for f in conn.execute("SELECT fecha FROM logistica_dia ORDER BY fecha")]
    plan = []
    for fecha in guardados:
        filas = conn.execute("SELECT cliente, obra FROM logistica_cargue WHERE fecha = ?", (fecha,)).fetchall()
        ya = sum(1 for c, o in filas if es_macao(c, o))
        nuevos = macao.get(fecha)
        if nuevos is None:
            estado = "sin Excel en la carpeta"
        elif ya:
            estado = f"ya tiene {ya} viajes de Macao"
        elif not nuevos:
            estado = "el Excel no trae Macao"
        else:
            estado = f"agrega {len(nuevos)} viajes, {sum(v.get('cantidad') or 0 for v in nuevos):g} m3"
            plan.append((fecha, nuevos))
        print(f"{fecha}: {estado}")
    print(f"\n{len(plan)} dia(s) para completar, {sum(len(n) for _, n in plan)} viajes.")
    if not aplicar or not plan:
        if plan:
            print("Solo se mostro. Con --aplicar se escribe.")
        return
    respaldo = f"{base}.antes-macao-{datetime.now():%Y%m%d-%H%M%S}"
    conn.close()
    shutil.copy2(base, respaldo)
    print(f"Respaldo: {respaldo}")
    conn = sqlite3.connect(base)
    with conn:
        for fecha, nuevos in plan:
            orden = conn.execute("SELECT COALESCE(MAX(orden), -1) FROM logistica_cargue WHERE fecha = ?",
                                 (fecha,)).fetchone()[0]
            conn.executemany(
                "INSERT INTO logistica_cargue (fecha, orden, ficha, hora_min, cliente, conduce, "
                "elemento, planta, obra, cantidad) VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(fecha, orden + 1 + i, v.get("ficha"), v.get("horaMin"), v.get("cliente"),
                  None if v.get("conduce") is None else str(v.get("conduce")),
                  None if v.get("elemento") is None else str(v.get("elemento")),
                  v.get("planta"), v.get("obra"), v.get("cantidad")) for i, v in enumerate(nuevos)])
    print("Listo.")


if __name__ == "__main__":
    main()
