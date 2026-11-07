# by a_oller
"""
recuperar_nombres.py — Reconstruye los escaneos cuyo nombre no sigue la
convencion MM-DD-Mx-NNNNN.pdf y emite copias renombradas a la convencion,
para que entren por el flujo normal de scripts/importar_puente.py.

Issue #78: el lote OneDrive 09-2026 trae ~20 PDFs con nombres sin convencion
(recuperables). La reconstruccion cruza dos datos contra el Excel:

  - el NUMERO FINAL del nombre del archivo (el ultimo grupo de digitos del
    nombre sin extension), y
  - la PLANTA que dice la carpeta contenedora (un token `M#` en la ruta
    dentro del ZIP), si lo hay.

Con planta de carpeta, el candidato es unico: planta + numero con ceros a 8
digitos contra la columna Conduce del Excel. Sin planta en la ruta se prueba
contra todas las plantas del Excel: un solo match es un recuperado; mas de
uno es AMBIGUO y queda listado, no adivinado. Lo que no matchea con nada
queda listado como NO HALLADO.

El nombre nuevo sale de la fila del Excel: la columna Codigo si la trae
(que es exactamente el nombre que el import matchea directo), y si no, se
arma `MM-DD-Mx-NNNNN.pdf` con la fecha y el id de la fila. Los originales no
se tocan: se emiten COPIAS a una carpeta staging.

OJO: la carpeta de la ruta NO se usa para decidir la fase ni el cliente —
solo para elegir la planta del id. La fase la decide el Excel al importar,
como siempre (hay archivos rotulados M3 con numeros de la serie M4).

Uso:
    python scripts/recuperar_nombres.py <zip> <excel> [carpeta_staging]

Sin carpeta_staging, las copias van a conduces/data/recuperados_staging/.
No escribe en ninguna base y no llama a ninguna API.
"""

import os
import re
import sys
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "scripts"))

import importar_puente  # noqa: E402  — load_excel por cabecera (issue #78)

STAGING_DEFAULT = BASE_DIR / "conduces" / "data" / "recuperados_staging"

# La convencion buena: esos NO se tocan, ya entran solos por el import.
RE_CONVENCION = re.compile(r"^\d{2}-\d{2}-M\d-\d+\.pdf$", re.IGNORECASE)
# Un token de planta (M3, M4, ...) en un tramo de carpeta como `19-8-2026-M4`.
RE_PLANTA = re.compile(r"(?<![A-Z0-9])(M\d)(?![0-9])", re.IGNORECASE)
# El ultimo grupo de digitos del nombre sin extension ("numero final").
RE_NUMERO_FINAL = re.compile(r"(\d+)(?!.*\d)")


def _plantas_de_la_ruta(nombre_zip):
    """Tokens de planta que aparecen en las CARPETAS de la entrada del ZIP
    (no en el nombre del archivo), en orden y sin repetir."""
    carpetas = Path(nombre_zip.replace("\\", "/")).parent.parts
    vistas, plantas = set(), []
    for tramo in carpetas:
        for m in RE_PLANTA.finditer(tramo):
            planta = m.group(1).upper()
            if planta not in vistas:
                vistas.add(planta)
                plantas.append(planta)
    return plantas


def _nombre_convencion(fila, numero):
    """El nombre a la convencion para esta fila del Excel: su Codigo si lo
    trae; si no, MM-DD-Mx-NNNNN.pdf armado con fecha (YYYY-MM-DD) e id."""
    if fila.get("codigo"):
        return fila["codigo"]
    fecha = fila.get("fecha") or ""
    partes = fecha.split("-")
    if len(partes) != 3:
        return None
    planta = (fila.get("id_documento") or "")[:2]
    return f"{partes[1]}-{partes[2]}-{planta}-{int(numero)}.pdf"


def reconstruir(nombre_zip, por_id):
    """Un intento de reconstruccion para UNA entrada del ZIP fuera de
    convencion. Devuelve una de:

      ("ok",        fila, nombre_nuevo)
      ("ambiguo",   candidatos:list[fila], None)   — mas de una planta matchea
      ("no_hallado", motivo:str, None)

    Nunca adivina: con cero candidatos es no_hallado, con mas de uno es
    ambiguo — los dos quedan listados para resolver a mano.
    """
    fn = os.path.basename(nombre_zip.replace("\\", "/"))
    stem = fn[:-4] if fn.lower().endswith(".pdf") else fn
    m = RE_NUMERO_FINAL.search(stem)
    if not m:
        return ("no_hallado", "el nombre no trae ningun numero", None)
    numero = int(m.group(1))

    plantas = _plantas_de_la_ruta(nombre_zip)
    if not plantas:
        # Sin planta en la ruta: se prueba contra todas las del Excel.
        plantas = sorted({id_doc[:2] for id_doc in por_id})

    candidatos = []
    for planta in plantas:
        fila = por_id.get(f"{planta}{numero:08d}")
        if fila is not None and fila not in candidatos:
            candidatos.append(fila)

    if not candidatos:
        return ("no_hallado",
                f"numero {numero} sin fila en el Excel para planta(s) "
                f"{'/'.join(plantas)}", None)
    if len(candidatos) > 1:
        return ("ambiguo", candidatos, None)

    fila = candidatos[0]
    nombre_nuevo = _nombre_convencion(fila, numero)
    if nombre_nuevo is None:
        return ("no_hallado",
                f"fila {fila['id_documento']} sin Codigo ni fecha valida para "
                "armar el nombre", None)
    return ("ok", fila, nombre_nuevo)


def main(zip_path, excel_path, staging_dir=None):
    zip_path = Path(zip_path)
    staging = Path(staging_dir) if staging_dir else STAGING_DEFAULT

    _por_codigo, por_id = importar_puente.load_excel(excel_path)

    recuperados, ambiguos, no_hallados = [], [], []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            fn = os.path.basename(info.filename)
            if not fn.lower().endswith(".pdf") or RE_CONVENCION.match(fn):
                continue  # no es PDF, o ya viene a la convencion
            resultado, dato, nombre_nuevo = reconstruir(info.filename, por_id)
            if resultado == "ok":
                staging.mkdir(parents=True, exist_ok=True)
                destino = staging / nombre_nuevo
                if destino.exists():
                    ambiguos.append(
                        (info.filename,
                         f"el staging ya tiene {nombre_nuevo} (otra entrada "
                         "del ZIP resolvio al mismo conduce)"))
                    continue
                destino.write_bytes(zf.read(info.filename))
                recuperados.append((info.filename, nombre_nuevo))
            elif resultado == "ambiguo":
                ids = ", ".join(f["id_documento"] for f in dato)
                ambiguos.append((info.filename, f"matchea {ids}"))
            else:
                no_hallados.append((info.filename, dato))

    print("\n" + "=" * 40)
    print("RECUPERACION DE NOMBRES")
    print("=" * 40)
    print(f"Recuperados: {len(recuperados)} (copias en {staging})")
    for original, nuevo in recuperados:
        print(f"  {original}  ->  {nuevo}")
    print(f"Ambiguos: {len(ambiguos)} (a resolver a mano, no se adivina)")
    for original, motivo in ambiguos:
        print(f"  {original}  ({motivo})")
    print(f"No hallados: {len(no_hallados)}")
    for original, motivo in no_hallados:
        print(f"  {original}  ({motivo})")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python scripts/recuperar_nombres.py <zip> <excel> [carpeta_staging]")
        sys.exit(2)
    sys.exit(main(*sys.argv[1:4]))
