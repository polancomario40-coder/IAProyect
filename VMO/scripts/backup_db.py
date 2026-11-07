# by a_oller
"""
backup_db.py — Respaldo de conduces.db, estimaciones.db, logistica.db, comercial.db y la memoria.

Usa la API de backup de sqlite3 (segura para copiar una base de datos que
puede estar en uso — no es una simple copia de archivo). Guarda copias con
timestamp en backups/db/, borra las mas viejas (se quedan las ultimas
RETENCION_DIAS), y si esta configurada la variable de entorno
GDRIVE_BACKUP_DIR (carpeta sincronizada de Google Drive para escritorio),
copia ahi tambien las mas recientes — sin eso, esa parte simplemente se
salta, no falla.

Ademas respalda la carpeta de memoria del proyecto (`~/.claude/projects/<slug>/
memory`), que vive FUERA del repo y no la versiona git: ahi estan `log.md`,
`MEMORY.md` y los archivos de feedback/proyecto/referencia, o sea todo el
historial de decisiones. Como son .md y no una base, va como .zip con timestamp,
con la misma retencion y la misma copia a Drive que las bases. Si no se
encuentra la carpeta, avisa y sigue — no rompe el respaldo de las bases.

Ademas espeja los escaneos de los conduces (`conduces/archivos/`, ~1,5 GB) a
Drive. Esos van con otra logica: se copia solo lo que falta y no se rota nunca,
porque son append-only y porque para los lotes importados antes del 2026-08-24
ese directorio es la UNICA copia que existe — no hay respaldo de esos PDFs en
`estimaciones/facturas/procesadas/`. La primera corrida sube ~1,5 GB; las
siguientes no suben nada.

Uso:
    python scripts/backup_db.py            # respaldo manual, a mano
    python scripts/backup_db.py --solo-bases   # sin los escaneos (rapido)
    (tambien se corre solo, una vez al dia, via el Programador de Tareas
    de Windows — ver AGENDA.md/CLAUDE.md para el nombre de la tarea)
"""

import os
import shutil
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

FUENTES = {
    "conduces": BASE_DIR / "conduces" / "db" / "conduces.db",
    "estimaciones": BASE_DIR / "estimaciones" / "db" / "estimaciones.db",
    # Agregada el 2026-09-30, con el historial de Logistica. Es la unica copia
    # que existe de los dias guardados: los dos Excel de origen no quedan en
    # ningun lado (el dashboard los lee en el navegador y no los sube), asi
    # que si se pierde esta base, ese dia no se puede reconstruir de nada.
    "logistica": BASE_DIR / "logistica" / "db" / "logistica.db",
    # Agregada el 2026-10-19, con el modulo Comercial: los despachos y el plan
    # que alimentan el dashboard comercial. Hasta la primera carga no existe y
    # se salta con un aviso, como cualquier otra.
    "comercial": BASE_DIR / "comercial" / "db" / "comercial.db",
}

# Los escaneos de los conduces. Van aparte de todo lo demas y con otra logica:
# son ~1,5 GB append-only, asi que se ESPEJAN (se copia solo lo que falta y no
# se rota nunca), en vez de sacarles una copia fechada por dia. Importa porque
# para los lotes importados antes del 2026-08-24 este directorio es la unica
# copia que existe: no hay respaldo en estimaciones/facturas/procesadas/.
ESCANEOS_DIR = BASE_DIR / "conduces" / "archivos"
ESCANEOS_SUELTOS = ESCANEOS_DIR / "escaneos"

BACKUP_DIR = BASE_DIR / "backups" / "db"
LOG_PATH = BASE_DIR / "backups" / "backup_log.txt"
RETENCION_DIAS = 30

GDRIVE_BACKUP_DIR = os.getenv("GDRIVE_BACKUP_DIR")  # carpeta de Google Drive para escritorio, opcional


def _resolver_memoria():
    """Ubica la carpeta memory/ de Claude Code para este proyecto.

    Se puede forzar con la variable de entorno MEMORIA_DIR. Si no, se arma por
    la convencion de Claude Code (la ruta del proyecto con los separadores
    vueltos guiones) y, como ultimo recurso, se busca por el nombre de la
    carpeta del repo — util si la ruta cambio de mayusculas/minusculas.
    """
    forzada = os.getenv("MEMORIA_DIR")
    if forzada:
        ruta = Path(forzada)
        return ruta if ruta.is_dir() else None

    proyectos = Path.home() / ".claude" / "projects"
    if not proyectos.is_dir():
        return None

    slug = str(BASE_DIR).replace(":", "-").replace("\\", "-").replace("/", "-")
    candidata = proyectos / slug / "memory"
    if candidata.is_dir():
        return candidata

    for encontrada in sorted(proyectos.glob(f"*{BASE_DIR.name}*/memory")):
        if encontrada.is_dir():
            return encontrada
    return None


MEMORIA_DIR = _resolver_memoria()


def _log(linea: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {linea}\n")
    print(linea)


def respaldar_uno(nombre: str, origen: Path, timestamp: str) -> Path | None:
    if not origen.exists():
        _log(f"AVISO: {origen} no existe, se salta.")
        return None

    destino = BACKUP_DIR / f"{nombre}_{timestamp}.db"
    origen_conn = sqlite3.connect(str(origen))
    destino_conn = sqlite3.connect(str(destino))
    try:
        origen_conn.backup(destino_conn)
    finally:
        destino_conn.close()
        origen_conn.close()

    tamano_kb = destino.stat().st_size / 1024
    _log(f"OK: {nombre} -> {destino.name} ({tamano_kb:.1f} KB)")
    return destino


def limpiar_viejos(nombre: str, sufijo: str = ".db"):
    limite = datetime.now().timestamp() - (RETENCION_DIAS * 86400)
    borrados = 0
    for archivo in BACKUP_DIR.glob(f"{nombre}_*{sufijo}"):
        if archivo.stat().st_mtime < limite:
            archivo.unlink()
            borrados += 1
    if borrados:
        _log(f"Limpieza {nombre}: {borrados} backup(s) de mas de {RETENCION_DIAS} dias borrados.")


def respaldar_memoria(timestamp: str) -> Path | None:
    """Comprime la carpeta de memoria a backups/db/memoria_<timestamp>.zip."""
    if MEMORIA_DIR is None:
        _log("AVISO: no se encontro la carpeta de memoria del proyecto — se salta "
             "(se puede forzar con la variable de entorno MEMORIA_DIR).")
        return None

    base = BACKUP_DIR / f"memoria_{timestamp}"
    try:
        creado = Path(shutil.make_archive(str(base), "zip", root_dir=str(MEMORIA_DIR)))
    except Exception as e:
        _log(f"AVISO: fallo el respaldo de la memoria ({type(e).__name__}: {e}) — se salta.")
        return None

    cuantos = sum(1 for f in MEMORIA_DIR.rglob("*") if f.is_file())
    tamano_kb = creado.stat().st_size / 1024
    _log(f"OK: memoria -> {creado.name} ({cuantos} archivos, {tamano_kb:.1f} KB)")
    return creado


def _origenes_de_escaneos():
    """Los archivos de escaneos a espejar: los .zip de lotes y los .pdf sueltos."""
    if not ESCANEOS_DIR.is_dir():
        return []
    origenes = sorted(ESCANEOS_DIR.glob("*.zip"))
    if ESCANEOS_SUELTOS.is_dir():
        origenes += sorted(ESCANEOS_SUELTOS.glob("*.pdf"))
    return origenes


def espejar_escaneos():
    """Espeja los escaneos a <GDRIVE_BACKUP_DIR>/escaneos/.

    No rota y no borra nada: un escaneo viejo sigue siendo el respaldo del
    conduce de ese dia. Copia solo lo que falta o cambio de tamano, asi que
    la primera corrida sube ~1,5 GB y las siguientes no suben nada.

    Va a Drive y no a backups/ local a proposito: una copia en el mismo disco
    no protege de perder el disco, y el modo de falla que ya ocurrio —borrar
    la carpeta despues de importar, el 2026-08-24— tambien lo cubre Drive.
    """
    origenes = _origenes_de_escaneos()
    if not origenes:
        _log(f"AVISO: no hay escaneos que espejar en {ESCANEOS_DIR} — se salta.")
        return
    if not GDRIVE_BACKUP_DIR:
        _log(f"AVISO: {len(origenes)} archivo(s) de escaneos SIN respaldar — "
             "GDRIVE_BACKUP_DIR no esta configurado. Para los lotes viejos este "
             "directorio es la unica copia que existe.")
        return

    destino_dir = Path(GDRIVE_BACKUP_DIR) / "escaneos"
    try:
        destino_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        _log(f"AVISO: no se pudo crear {destino_dir} ({e}) — escaneos sin respaldar.")
        return

    copiados = omitidos = 0
    bytes_copiados = 0
    for origen in origenes:
        destino = destino_dir / origen.name
        # mismo nombre y mismo tamano = ya esta. No se compara hash: son
        # archivos de cientos de MB y estos lotes no se reescriben, se agregan.
        if destino.exists() and destino.stat().st_size == origen.stat().st_size:
            omitidos += 1
            continue
        try:
            shutil.copy2(origen, destino)
            copiados += 1
            bytes_copiados += origen.stat().st_size
        except Exception as e:
            _log(f"AVISO: fallo el respaldo de {origen.name} ({type(e).__name__}: {e}).")

    _log(f"OK: escaneos -> {destino_dir} ({copiados} copiado(s), "
         f"{bytes_copiados / 1e6:.0f} MB; {omitidos} ya estaban)")


def copiar_a_gdrive(archivos: list[Path]):
    if not GDRIVE_BACKUP_DIR:
        _log("GDRIVE_BACKUP_DIR no configurado — se salta la copia a Google Drive (solo local por ahora).")
        return
    destino_dir = Path(GDRIVE_BACKUP_DIR)
    if not destino_dir.exists():
        _log(f"AVISO: GDRIVE_BACKUP_DIR ({destino_dir}) no existe — se salta la copia a Google Drive.")
        return
    for archivo in archivos:
        if archivo is None:
            continue
        shutil.copy2(archivo, destino_dir / archivo.name)
    _log(f"Copiado a Google Drive: {destino_dir}")


def main():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    _log(f"--- Backup iniciado ({timestamp}) ---")

    resultados = []
    for nombre, origen in FUENTES.items():
        resultados.append(respaldar_uno(nombre, origen, timestamp))
        limpiar_viejos(nombre)

    resultados.append(respaldar_memoria(timestamp))
    limpiar_viejos("memoria", ".zip")

    copiar_a_gdrive(resultados)

    # Los escaneos van al final: son lo mas pesado y lo menos urgente, asi que
    # si algo falla ahi las bases y la memoria ya estan a salvo.
    if "--solo-bases" in sys.argv:
        _log("Escaneos omitidos por --solo-bases.")
    else:
        espejar_escaneos()

    _log("--- Backup terminado ---")


if __name__ == "__main__":
    main()
