# by a_oller
"""
completar_macao_programacion.py — Agrega a los dias ya guardados los pedidos
de Macao que el Excel de programacion traia y la app descartaba al leerlo
(hasta el 2026-11-03). Los necesita el Reporte de cancelados; el cumplimiento
no los ve (restaurarDia los separa), asi que no cambia ningun porcentaje.

Lee los "PROGRAMA DD-MM-AAAA.xls" de una carpeta con el mismo lector de la app
(parseProgramacionMacao, via node) y, por cada dia guardado, agrega al final de
logistica_programacion los renglones de Macao del Excel que el dia todavia no
tiene. Es idempotente: un renglon que ya esta no se vuelve a agregar. Asi
tambien completa una base donde ya se corrio la version que solo agregaba
MACAO II.

Un dia sin viajes de Macao en el cargue NO se completa: un pedido de Macao se
da por cancelado cuando ningun camion fue a la obra, y sin esos viajes saldria
todo cancelado. Para esos dias, correr antes completar_macao_cargue.py.

Uso:
    python scripts/completar_macao_programacion.py <base.db> <carpeta_excels>            (solo muestra)
    python scripts/completar_macao_programacion.py <base.db> <carpeta_excels> --aplicar   (escribe)

Correrlo primero sobre una COPIA de la base; con --aplicar sobre la real
deja antes un respaldo al lado (logistica.db.antes-macao-prog-AAAAMMDD-HHMMSS).
"""
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LEER_JS = r"""
const fs = require('fs');
const XLSX = require(process.argv[1] + '/static/vendor/xlsx-0.20.3.full.min.js');
const L = require(process.argv[1] + '/static/logistica.logic.js');
const out = {};
for (const f of process.argv.slice(2)) {
  const m = f.match(/(\d\d)-(\d\d)-(\d{4})\.xls$/i);
  const wb = XLSX.read(fs.readFileSync(f), {type: 'array', cellDates: false});
  out[`${m[3]}-${m[2]}-${m[1]}`] = L.parseProgramacionMacao(wb.SheetNames.map(nombre => ({nombre,
    rows: XLSX.utils.sheet_to_json(wb.Sheets[nombre], {header: 1, defval: null, raw: true})})));
}
process.stdout.write(JSON.stringify(out));
"""

COLUMNAS = ("cliente", "obra", "hora_min", "pedido", "cantidad", "elemento", "producto", "prioridad",
            "zona_hoja", "despachado", "pendiente", "bomba", "vendedor", "zona_prog")
# Del renglon que devuelve el lector de la app a la columna de la base.
CAMPOS = ("cliente", "obra", "horaMin", "pedido", "cantidad", "elemento", "producto", "prioridad",
          "zonaSheet", "despachado", "pendiente", "bomba", "vendedor", "zonaProg")


def leer_macao(carpeta):
    archivos = sorted(os.path.join(carpeta, f) for f in os.listdir(carpeta)
                      if re.fullmatch(r"programa \d\d-\d\d-\d{4}\.xls", f, re.I))
    if not archivos:
        return {}
    res = subprocess.run(["node", "-e", LEER_JS, REPO, *archivos], capture_output=True, text=True,
                         encoding="utf-8", check=True)
    return json.loads(res.stdout)


def _norm(t):
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]", " ", str(t or "").upper())).strip()


def es_macao(cliente, obra):
    return not _norm(cliente).startswith("VMO CONCRETOS") and any("MACAO" in _norm(t) for t in (cliente, obra))


def _valor(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return str(v).strip()


def _clave(valores):
    """El renglon para compararlo con lo guardado. Los numeros van como numero
    y lo vacio como None: la base devuelve '4417' (pedido es TEXT) o 4417.0
    donde el Excel dice 4417."""
    return tuple(_valor(v) for v in valores)


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
        ya = Counter(_clave(f) for f in conn.execute(
            f"SELECT {', '.join(COLUMNAS)} FROM logistica_programacion WHERE fecha = ?", (fecha,))
            if es_macao(f[0], f[1]))
        viajes = sum(1 for c, o in conn.execute(
            "SELECT cliente, obra FROM logistica_cargue WHERE fecha = ?", (fecha,)) if es_macao(c, o))
        excel = macao.get(fecha)
        if excel is None:
            print(f"{fecha}: sin Excel en la carpeta")
            continue
        if not excel:
            print(f"{fecha}: el Excel no trae Macao")
            continue
        nuevos, quedan = [], Counter(ya)
        for r in excel:
            k = _clave(r.get(c) for c in CAMPOS)
            if quedan[k]:
                quedan[k] -= 1
            else:
                nuevos.append(r)
        if not nuevos:
            estado = f"ya tiene sus {len(excel)} pedidos de Macao"
        elif not viajes:
            estado = "NO se completa: el cargue no tiene viajes de Macao (correr antes completar_macao_cargue.py)"
        else:
            estado = f"agrega {len(nuevos)} pedidos, {sum(v.get('cantidad') or 0 for v in nuevos):g} m3"
            plan.append((fecha, nuevos))
        print(f"{fecha}: {estado}")
    print(f"\n{len(plan)} dia(s) para completar, {sum(len(n) for _, n in plan)} pedidos.")
    if not aplicar or not plan:
        if plan:
            print("Solo se mostro. Con --aplicar se escribe.")
        return
    respaldo = f"{base}.antes-macao-prog-{datetime.now():%Y%m%d-%H%M%S}"
    conn.close()
    shutil.copy2(base, respaldo)
    print(f"Respaldo: {respaldo}")
    conn = sqlite3.connect(base)
    with conn:
        for fecha, nuevos in plan:
            orden = conn.execute("SELECT COALESCE(MAX(orden), -1) FROM logistica_programacion WHERE fecha = ?",
                                 (fecha,)).fetchone()[0]
            conn.executemany(
                f"INSERT INTO logistica_programacion (fecha, orden, {', '.join(COLUMNAS)}) "
                f"VALUES ({', '.join('?' * (len(COLUMNAS) + 2))})",
                [(fecha, orden + 1 + i, *(r.get(c) for c in CAMPOS)) for i, r in enumerate(nuevos)])
    print("Listo.")


if __name__ == "__main__":
    main()
