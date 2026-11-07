# by a_oller
"""
cierre.py — El protocolo de cierre de sesion, en un comando.

Existe porque el ritual largo se saltea. El cierre del proyecto pedia tocar
cinco `.md` a mano, y el 2026-09-03 se salteo `AGENDA.md`: al dia siguiente
decia 483 tests cuando eran 626, y mandaba a un agente nuevo a leerlo primero.
La leccion no fue "acordarse mejor", fue **que un cierre caro no se hace**.

Comprueba seis cosas y las reporta. **No arregla nada solo** salvo dos, que
son las que no tienen criterio: el respaldo, y cerrar los servidores de
desarrollo que quedaron corriendo. No commitea, no mergea, no escribe en el
log, no borra ramas y **no borra nada del dropoff**. Decir que falta es el
trabajo; hacerlo es del que cierra.

Por que el dropoff se reporta y NUNCA se borra: ahi conviven archivos ya
procesados con otros que son copia unica. Hoy mismo tiene
`OneDrive_1_9-8-2026.zip`, 889 MB sin respaldo en ningun lado, que el log del
2026-09-28 decidio conservar a proposito. Un borrado automatico ahi repite
exactamente la perdida del `Puente 2.zip`.

Por que los servidores si se cierran solos: un uvicorn que sobrevive a la
sesion no le sirve a nadie y volver a levantarlo es un comando. Cuando se
agrego este paso habia uno corriendo desde hacia 21 horas, de la sesion
anterior, que nadie sabia que estaba. Solo se matan los que se prueba que son
ESTE proyecto (ver `servidores_del_proyecto`).

Sale con codigo 1 si algo quedo pendiente, para que se note en una automatizacion.

Uso:
    python scripts/cierre.py
    python scripts/cierre.py --sin-backup    # sin respaldar (mas rapido)
"""

import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

import backup_db  # noqa: E402  — se reusa su _resolver_memoria() y su main()
import estado  # noqa: E402  — se reusa su lectura de git; no se duplica


PASOS = 6


def _paso(n, nombre, ok, detalle):
    marca = "OK   " if ok else "AVISO"
    print(f"[{n}/{PASOS}] {nombre:<11} {marca} {detalle}")
    return ok


def revisar_main():
    """main mergeada, limpia, sincronizada y sin ramas ni worktrees colgando."""
    problemas = []

    rama, err = estado._git("rev-parse", "--abbrev-ref", "HEAD")
    if err:
        return False, f"no se pudo leer git ({err})"
    if rama != "main":
        problemas.append(f"estas en '{rama}', no en main")

    sucio, _ = estado._git("status", "--porcelain")
    if sucio:
        problemas.append(f"{len(sucio.splitlines())} archivo(s) sin commitear")

    seguimiento, _ = estado._git("status", "-sb")
    if seguimiento and ("[ahead" in seguimiento or "[behind" in seguimiento):
        problemas.append("main no esta sincronizada con origin")

    ramas, _ = estado._git("branch", "--format=%(refname:short)")
    otras = [b.strip() for b in (ramas or "").splitlines() if b.strip() and b.strip() != "main"]
    if otras:
        problemas.append("rama(s) sin borrar: " + ", ".join(otras))

    wt, _ = estado._git("worktree", "list")
    extra = (wt or "").splitlines()[1:]
    if extra:
        problemas.append(f"{len(extra)} worktree(s) colgando")

    abiertos, err = estado._correr(
        ["gh", "pr", "list", "--state", "open", "--json", "number", "--jq", "length"]
    )
    if not err and abiertos and abiertos.strip() not in ("0", ""):
        problemas.append(f"{abiertos.strip()} PR(s) abierto(s)")

    if problemas:
        return False, "; ".join(problemas)
    return True, "limpia, sincronizada, sin ramas ni worktrees"


def revisar_log(hoy=None):
    """Que el log tenga al menos una entrada de hoy.

    No se puede comprobar que las entradas sean BUENAS, solo que existan. Una
    entrada por decision tomada, no una por sesion: el 2026-09-04 fueron diez
    y estaba bien, porque fueron diez decisiones.
    """
    hoy = hoy or datetime.now().strftime("%Y-%m-%d")
    memoria = backup_db.MEMORIA_DIR
    if memoria is None:
        return False, "no se encontro la carpeta de memoria (se fuerza con MEMORIA_DIR)"
    log = Path(memoria) / "log.md"
    if not log.exists():
        return False, f"no existe {log}"
    cuantas = sum(1 for l in log.read_text(encoding="utf-8").splitlines()
                  if l.startswith(f"| {hoy}"))
    if cuantas == 0:
        return False, f"sin entradas de {hoy} — agrega una por cada decision tomada"
    return True, f"{cuantas} entrada(s) de {hoy}"


# Archivos del dropoff que NO son basura: estan ahi a proposito y alguien lo
# decidio por escrito. Se listan aparte para que el reporte no los confunda con
# sobras de una sesion. El motivo va al lado porque dentro de seis meses nadie
# se va a acordar.
DROPOFF_DECLARADOS = {
    ".gitkeep": "marca la carpeta en git",
    "OneDrive_1_9-8-2026.zip": "copia UNICA, 889 MB sin respaldo (log 2026-09-28)",
    "preguntas_para_X.md": "lo referencia HANDOFF.md",
    "ejemplo_*.pdf": "los referencia HANDOFF.md",
}


# Prefijos de ruta que existen SOLO en esta app. Son la huella con la que se
# comprueba que un uvicorn cualquiera es este proyecto antes de matarlo: la
# linea de comando (`python -m uvicorn main:app`) es identica en cualquier otro
# proyecto FastAPI de la misma maquina.
#
# Tienen que ser prefijos VIEJOS y estables, no la ruta nueva de moda. La
# primera version de este chequeo usaba `/api/logistica/dias` y dejo vivo un
# servidor de la sesion anterior que era este mismo proyecto de antes de que
# Logistica tuviera rutas — o sea que la huella nueva salvaba justo a los
# servidores viejos, que son los que este paso existe para cerrar.
HUELLAS_APP = ("/api/estimaciones/", "/api/conduces/", "/api/logistica/")


def servidores_del_proyecto():
    """Los uvicorn corriendo que SON este proyecto, con su puerto y su PID.

    Dos filtros, y los dos hacen falta. Primero se buscan procesos de python
    que mencionen uvicorn; despues se le pide `/openapi.json` a su puerto y se
    comprueba que exponga HUELLA_APP. Sin el segundo, cerrar el servidor del
    proyecto de al lado seria cuestion de que se llame igual.

    Devuelve (lista, avisos). Un proceso que no contesta o que contesta otra
    cosa entra en `avisos` y NO se toca.
    """
    import json
    import re
    import urllib.error
    import urllib.request

    try:
        ps = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object { $_.CommandLine -like '*uvicorn*' } | "
             "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=60)
    except Exception:
        return [], ["no se pudieron listar los procesos"]
    salida = (ps.stdout or "").strip()
    if not salida:
        return [], []
    try:
        datos = json.loads(salida)
    except json.JSONDecodeError:
        return [], ["no se pudo leer la lista de procesos"]
    if isinstance(datos, dict):
        datos = [datos]

    mios, avisos = [], []
    for proc in datos:
        linea = proc.get("CommandLine") or ""
        m = re.search(r"--port[= ](\d+)", linea)
        puerto = int(m.group(1)) if m else 8000
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{puerto}/openapi.json", timeout=3) as r:
                cuerpo = r.read().decode("utf-8", "replace")
        except (urllib.error.URLError, OSError):
            avisos.append(f"pid {proc.get('ProcessId')} en :{puerto} no contesta — no se toca")
            continue
        if not any(h in cuerpo for h in HUELLAS_APP):
            avisos.append(f"pid {proc.get('ProcessId')} en :{puerto} es OTRA app — no se toca")
            continue
        mios.append({"pid": proc.get("ProcessId"), "puerto": puerto})
    return mios, avisos


def cerrar_servidores():
    """Cierra los servidores de desarrollo de ESTE proyecto que quedaron vivos.

    Es de las dos cosas que el cierre hace solo, junto con el respaldo, y por la
    misma razon: no tiene criterio. Un uvicorn que sobrevive a la sesion no le
    sirve a nadie, y volver a levantarlo es un comando. Cuando se agrego este
    paso habia uno corriendo desde hacia 21 horas, de la sesion anterior, que
    nadie sabia que estaba.
    """
    mios, avisos = servidores_del_proyecto()
    for aviso in avisos:
        print(f"         {aviso}")
    if not mios:
        return True, "ninguno corriendo" if not avisos else f"ninguno de este proyecto ({len(avisos)} ajeno/s)"

    cerrados, fallados = [], []
    for srv in mios:
        try:
            subprocess.run(["taskkill", "/PID", str(srv["pid"]), "/F"],
                           capture_output=True, timeout=30, check=True)
            cerrados.append(srv)
        except Exception:
            fallados.append(srv)
    for srv in cerrados:
        print(f"         cerrado el servidor del puerto {srv['puerto']} (pid {srv['pid']})")
    for srv in fallados:
        print(f"         NO se pudo cerrar el del puerto {srv['puerto']} (pid {srv['pid']})")
    if fallados:
        return False, f"{len(cerrados)} cerrado(s), {len(fallados)} sin cerrar"
    return True, f"{len(cerrados)} cerrado(s)"


def revisar_dropoff():
    """Reporta que quedo en dropoff/. **Nunca borra nada**, y eso es el punto.

    Ahi conviven archivos ya procesados con copias unicas, y no hay forma de
    distinguirlos mirando el nombre. Borrar es una decision y se consulta, como
    commitear o mergear: la regla del proyecto es que nada se borra sin probar
    antes que existe en otro lado, y nacio de haber perdido `Puente 2.zip`
    recien importado.

    Devuelve (True, detalle) siempre: es informativo, no bloquea el cierre.
    """
    import fnmatch

    carpeta = BASE_DIR / "dropoff"
    if not carpeta.is_dir():
        return True, "no existe dropoff/"

    declarados, sueltos, total_bytes = [], [], 0
    for f in sorted(carpeta.iterdir()):
        if not f.is_file():
            continue
        tam = f.stat().st_size
        total_bytes += tam
        motivo = next((m for patron, m in DROPOFF_DECLARADOS.items()
                       if fnmatch.fnmatch(f.name, patron)), None)
        dias = (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).days
        (declarados if motivo else sueltos).append((f.name, tam, dias, motivo))

    if not declarados and not sueltos:
        return True, "vacio"

    mb = total_bytes / (1024 * 1024)
    detalle = f"{len(declarados) + len(sueltos)} archivo(s), {mb:,.0f} MB"
    if sueltos:
        detalle += f" — {len(sueltos)} sin declarar"
    print(f"         dropoff/: no se borra nada solo, la decision es tuya")
    for nombre, tam, dias, motivo in declarados:
        print(f"           conservar  {nombre[:46]:<46} {motivo}")
    for nombre, tam, dias, _ in sueltos:
        print(f"           revisar    {nombre[:46]:<46} {tam/(1024*1024):>7,.1f} MB, {dias} dia(s)")
    return True, detalle


def revisar_libro_mayor():
    """Issue #96 — el libro mayor no puede tener el mismo dia cerrado con dos
    numeros. Bloquea el cierre de sesion: es plata del documento siguiente."""
    if not estado.DB_ESTIMACIONES.exists():
        return True, "sin base de estimaciones"
    con = sqlite3.connect("file:" + estado.DB_ESTIMACIONES.as_posix() + "?mode=ro", uri=True)
    try:
        solapes = estado.solapes_libro_mayor(con)
    except sqlite3.OperationalError:
        return True, "sin tabla estimacion_cerrada"
    finally:
        con.close()
    if solapes:
        return False, "{} par(es) de cierres solapados (ver estado)".format(len(solapes))
    return True, "sin periodos cerrados dos veces"


def correr_backup():
    try:
        backup_db.main()
        return True, "bases, memoria y escaneos"
    except Exception as e:
        return False, f"fallo el respaldo ({type(e).__name__}: {e})"


def main():
    print("=" * 64)
    print("CIERRE DE SESION")
    print("=" * 64)

    ok_main, detalle_main = revisar_main()
    _paso(1, "main", ok_main, detalle_main)

    ok_log, detalle_log = revisar_log()
    _paso(2, "log.md", ok_log, detalle_log)

    ok_dropoff, detalle_dropoff = revisar_dropoff()
    _paso(3, "dropoff", ok_dropoff, detalle_dropoff)

    ok_servidores, detalle_servidores = cerrar_servidores()
    _paso(4, "servidores", ok_servidores, detalle_servidores)

    if "--sin-backup" in sys.argv:
        _paso(5, "backup", True, "omitido por --sin-backup")
        ok_backup = True
    else:
        print(f"[5/{PASOS}] backup      ...")
        ok_backup, detalle_backup = correr_backup()
        _paso(5, "backup", ok_backup, detalle_backup)

    print(f"[6/{PASOS}] estado")
    print("-" * 64)
    estado.bloque_git()
    estado.bloque_datos()
    estado.bloque_issues()
    print("-" * 64)

    ok_libro, detalle_libro = revisar_libro_mayor()
    print(f"libro mayor: {'OK' if ok_libro else 'FALLA'}  {detalle_libro}")

    # El dropoff no entra a esta lista a proposito: es informativo y no bloquea.
    # Que queden archivos ahi no es un cierre incompleto, es una decision que
    # alguien tiene que tomar mirando cuales son.
    faltan = [n for n, ok in [("main limpia", ok_main),
                              ("la entrada en log.md", ok_log),
                              ("cerrar algun servidor", ok_servidores),
                              ("el respaldo", ok_backup),
                              ("sacar los cierres solapados del libro mayor", ok_libro)] if not ok]
    print()
    if faltan:
        print("FALTA: " + ", ".join(faltan))
        return 1
    print("Cerrado. Nada pendiente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
