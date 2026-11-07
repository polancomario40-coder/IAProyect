# by a_oller
"""
sembrar_croquis.py — extrae los croquis (ortofotos) de las hojas RCO de los
documentos reales del cliente y los archiva en estimaciones/data/croquis/,
comprimidos, con nombre normalizado y con un manifiesto auditable.
Issue #27, decision 2: los croquis se extraen una sola vez de los documentos
del cliente — no hay que esperar a que nadie entregue nada.

REGLA DE EXTRACCION (croquis vs logos/sellos/firmas escaneadas)
    Las hojas RCO de DOMICEM traen hasta 4 imagenes flotantes: el banner de
    cabecera (743x39, anclado en las filas 1-2), el sello (200x200, anclado
    arriba de la columna J), a veces una firma escaneada (327x81, anclada
    sobre el bloque de firma) y el croquis. "La imagen mas grande" era la
    heuristica obvia pero nadie la especifico y puede archivar un sello si un
    dia el croquis viene liviano. La regla elegida es ESTRUCTURAL, no de
    tamano de archivo:

        el croquis es la imagen cuya ancla abarca UMBRAL_FILAS_CROQUIS (10)
        o mas filas de alto — es la unica que vive dentro del marco
        A18:J43 (26 filas); los logos abarcan 1-3 filas y la firma
        escaneada 2-3.

    Medido sobre las 156 hojas RCO/RFO de los 15 documentos (2026-09-01):
    todos los croquis abarcan 22+ filas (incluso los de CAVERNAS, que el
    cliente dejo anclados en la fila ~11 pero estirados hasta la ~42) y
    ninguna imagen decorativa pasa de 3. Si aun asi quedara mas de una
    candidata, se toma la de mayor area de ancla y se deja constancia en el
    manifiesto.

COMPRESION (decision D2)
    openpyxl NO deduplica imagenes identicas: 13 hojas con el mismo croquis
    de 1 MB dan un .xlsx de 13,4 MB, contra los ~85 KB que pesa una
    estimacion generada hoy. Cada croquis se reescala a un maximo de
    1200x900 px (el marco A18:J43 en landscape escala 76 no muestra mas de
    ~900x600 px utiles) y se guarda como PNG; si el PNG recomprimido sigue
    pesando mas del tope (300 KB) se guarda como JPEG calidad 85 (y 75 en
    ultima instancia). La extension refleja SIEMPRE el formato real —
    _est_buscar_croquis acepta .png y .jpg.

NOMBRES
    {EMPRESA}_{FASE}.png|.jpg para el croquis dominante de la fase, y
    {EMPRESA}_{FASE}_{clave}.png|.jpg para las claves cuyo croquis difiere
    del dominante (necesario para EXTERIORES y MACAO 2). El slug es el
    MISMO core._est_slug del generador — un criterio de saneo unico, para
    que PODIUM-1-2-3 o PATIO DE MANIOBRAS-TRB no rompan por los espacios,
    comas y guiones.

LOGOS DOMICEM (decision D4)
    Del mismo barrido se archivan el banner de cabecera y el sello que las
    hojas DOMICEM llevan flotando (se extraen de MACAO 2 N33 RCO-02, que
    trae el par dominante: el banner de 743x39 aparece en 86 hojas y el
    sello jpeg de 200x200 en 64). Van en croquis/logos/ y el generador los
    re-estampa en cada hoja DOMICEM.

Uso:
    python scripts/sembrar_croquis.py            # siembra todo + manifiesto
    python scripts/sembrar_croquis.py --dry-run  # solo reporta, no escribe

Los documentos fuente (768 MB, no versionados) se buscan en
estimaciones/data/plantillas_por_fase/ o en $EST_FUENTES_DIR.
"""
import argparse
import hashlib
import io
import os
import re
import sys
from datetime import date

import openpyxl
from PIL import Image as PILImage

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from core import (  # noqa: E402
    EST_CROQUIS_DIR, EST_LOGOS_DIR, EST_PLANTILLAS, _est_id_clave, _est_slug,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from limpiar_plantilla_estimacion import FASES, FUENTES_DIR  # noqa: E402

# umbral de filas de la ancla para que una imagen cuente como croquis
UMBRAL_FILAS_CROQUIS = 10
# tope de peso por croquis archivado (D2)
TOPE_BYTES = 300 * 1024
# reescalado maximo (el marco no muestra mas de ~900x600 px utiles)
MAX_PX = (1200, 900)

# hoja de la que se extraen los logos DOMICEM (par dominante medido)
FUENTE_LOGOS = ("DOMICEM/EST_DOMICEM_MACAO_II_4800029677_N33_22072026_V01.xlsx",
                "CD-COAF-RCO-02")

RE_HOJA_RCO = re.compile(r"^CD-COAF-RCO-(\d+)")


def _filas_de_ancla(ws, img) -> int:
    """Cantidad de filas que abarca la ancla de una imagen (TwoCellAnchor:
    to.row - from.row; OneCellAnchor: alto de ext convertido a filas con el
    alto de fila por defecto de la hoja)."""
    anchor = img.anchor
    desde = anchor._from.row
    hasta = getattr(anchor, "to", None)
    if hasta is not None:
        return hasta.row - desde
    ext = getattr(anchor, "ext", None)
    if ext is not None and ext.cy:
        alto_fila_emu = (ws.sheet_format.defaultRowHeight or 15.0) * (4 / 3) * 9525
        return int(ext.cy / alto_fila_emu)
    return 0


def _area_de_ancla(img) -> int:
    anchor = img.anchor
    hasta = getattr(anchor, "to", None)
    if hasta is None:
        return 0
    return max(1, hasta.row - anchor._from.row) * max(1, hasta.col - anchor._from.col)


def _croquis_de_hoja(ws, contexto: str, notas: list):
    """Aplica la regla de extraccion y devuelve los bytes del croquis de una
    hoja RCO, o None si la hoja no trae ninguno (el cliente tambien entrega
    hojas con el marco vacio)."""
    candidatas = [img for img in ws._images
                  if _filas_de_ancla(ws, img) >= UMBRAL_FILAS_CROQUIS]
    if not candidatas:
        return None
    if len(candidatas) > 1:
        candidatas.sort(key=_area_de_ancla, reverse=True)
        notas.append(f"{contexto}: {len(candidatas)} imagenes con ancla de "
                     f"{UMBRAL_FILAS_CROQUIS}+ filas — se archivo la de mayor "
                     f"area de ancla")
    return candidatas[0]._data()


def _comprimir(data: bytes):
    """(bytes_finales, extension, descripcion) — reescala y recomprime al
    tope de D2. La extension refleja el formato real del archivo."""
    img = PILImage.open(io.BytesIO(data))
    original = f"{img.width}x{img.height} {len(data) // 1024}KB"
    img.thumbnail(MAX_PX, PILImage.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    if buf.tell() <= TOPE_BYTES:
        return buf.getvalue(), ".png", f"{original} -> {img.width}x{img.height} {buf.tell() // 1024}KB png"

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    for calidad in (85, 75):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=calidad, optimize=True, progressive=True)
        if buf.tell() <= TOPE_BYTES or calidad == 75:
            return (buf.getvalue(), ".jpg",
                    f"{original} -> {img.width}x{img.height} {buf.tell() // 1024}KB jpg q{calidad}")
    raise AssertionError("inalcanzable")


def _sembrar_fase(empresa, fase, archivo_rel, dry_run, manifiesto, notas):
    ruta = os.path.join(FUENTES_DIR, archivo_rel)
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"falta el documento fuente {ruta}")
    wb = openpyxl.load_workbook(ruta, data_only=False)
    capacidad = EST_PLANTILLAS[(empresa, fase)]["capacidad"]
    slug = f"{_est_slug(empresa)}_{_est_slug(fase)}"

    manifiesto.append(f"\n{empresa}/{fase} :: {archivo_rel}")
    por_clave = {}   # clave (str normalizada) -> (sha, data, hoja)
    for nombre in wb.sheetnames:
        m = RE_HOJA_RCO.match(nombre)
        if not m:
            continue
        clave = str(int(m.group(1)))
        if int(clave) > capacidad:
            # ej. las RCO-22/23 del documento CAVERNAS_EXTERIORES: numeracion
            # vieja de EXTERIORES-DOMICEM, fuera del catalogo de la fase
            manifiesto.append(f"  {nombre}: clave {clave} fuera del catalogo "
                              f"(capacidad {capacidad}) — se omite")
            continue
        data = _croquis_de_hoja(wb[nombre], f"{empresa}/{fase}::{nombre}", notas)
        if data is None:
            manifiesto.append(f"  {nombre}: sin croquis en el documento fuente "
                              f"(el cliente tambien entrega el marco vacio) — se omite")
            continue
        sha = hashlib.sha256(data).hexdigest()
        if clave in por_clave and por_clave[clave][0] != sha:
            notas.append(f"{empresa}/{fase}::{nombre}: clave {clave} repetida "
                         f"con croquis distinto — se conservo el primero")
            continue
        por_clave[clave] = (sha, data, nombre)

    if not por_clave:
        manifiesto.append("  (ninguna hoja RCO con croquis)")
        return

    # dominante = el hash que cubre mas claves (empate: la clave mas baja)
    conteo = {}
    for clave, (sha, _, _) in por_clave.items():
        conteo.setdefault(sha, []).append(clave)
    dominante = max(conteo.items(), key=lambda kv: (len(kv[1]), -min(int(c) for c in kv[1])))[0]

    archivos = []   # (nombre_archivo, data_comprimida, claves, hoja, sha, desc)
    cache_comprimidos = {}
    for sha, claves in sorted(conteo.items(), key=lambda kv: min(int(c) for c in kv[1])):
        if sha not in cache_comprimidos:
            cache_comprimidos[sha] = _comprimir(por_clave[claves[0]][1])
        data_c, ext, desc = cache_comprimidos[sha]
        if sha == dominante:
            archivos.append((slug + ext, data_c, claves, por_clave[claves[0]][2], sha, desc))
        else:
            for clave in claves:
                archivos.append((f"{slug}_{_est_id_clave(clave)}{ext}", data_c,
                                 [clave], por_clave[clave][2], sha, desc))

    for nombre_archivo, data_c, claves, hoja, sha, desc in archivos:
        destino = os.path.join(EST_CROQUIS_DIR, nombre_archivo)
        if not dry_run:
            with open(destino, "wb") as f:
                f.write(data_c)
        etiqueta = "dominante de la fase" if nombre_archivo.startswith(slug + ".") else "pisa al de fase"
        manifiesto.append(f"  {hoja} (claves {','.join(sorted(claves, key=int))}, {etiqueta}) "
                          f"sha256={sha[:12]} {desc} -> {nombre_archivo}")


def _sembrar_logos(dry_run, manifiesto):
    archivo_rel, hoja = FUENTE_LOGOS
    ruta = os.path.join(FUENTES_DIR, archivo_rel)
    wb = openpyxl.load_workbook(ruta, data_only=False)
    ws = wb[hoja]
    logos = [img for img in ws._images if _filas_de_ancla(ws, img) < UMBRAL_FILAS_CROQUIS]
    if len(logos) != 2:
        raise ValueError(f"{archivo_rel}::{hoja}: se esperaban 2 logos "
                         f"(cabecera y sello) y hay {len(logos)}")
    manifiesto.append(f"\nlogos DOMICEM :: {archivo_rel} :: {hoja}")
    for img in logos:
        data = img._data()
        pil = PILImage.open(io.BytesIO(data))
        # el banner es 19:1; el sello es ~cuadrado — la proporcion los separa
        es_cabecera = pil.width >= pil.height * 5
        nombre = "DOMICEM_cabecera.png" if es_cabecera else "DOMICEM_sello.png"
        if pil.format != "PNG":   # el sello viene JPEG: la extension no miente
            buf = io.BytesIO()
            pil.convert("RGB").save(buf, format="PNG", optimize=True)
            data = buf.getvalue()
        if not dry_run:
            with open(os.path.join(EST_LOGOS_DIR, nombre), "wb") as f:
                f.write(data)
        manifiesto.append(f"  {pil.width}x{pil.height} "
                          f"sha256={hashlib.sha256(data).hexdigest()[:12]} "
                          f"{len(data) // 1024}KB -> logos/{nombre}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.dry_run:
        os.makedirs(EST_CROQUIS_DIR, exist_ok=True)
        os.makedirs(EST_LOGOS_DIR, exist_ok=True)

    manifiesto = [
        "Manifiesto de croquis y logos — generado por scripts/sembrar_croquis.py",
        f"fecha: {date.today().isoformat()}",
        "regenerar con: python scripts/sembrar_croquis.py  (fuentes en",
        "estimaciones/data/plantillas_por_fase/ o $EST_FUENTES_DIR)",
        "",
        "regla de extraccion: el croquis es la imagen cuya ancla abarca",
        f"{UMBRAL_FILAS_CROQUIS}+ filas (vive dentro del marco A18:J43); los logos y las",
        "firmas escaneadas abarcan 1-3. Ver docstring del script.",
        f"compresion: reescalado a {MAX_PX[0]}x{MAX_PX[1]} px max, PNG, y JPEG si el PNG",
        f"pasa el tope de {TOPE_BYTES // 1024} KB (openpyxl no deduplica imagenes: cada",
        "hoja RCO carga su copia completa dentro del .xlsx).",
    ]
    notas = []
    for (empresa, fase), archivo_rel in FASES.items():
        _sembrar_fase(empresa, fase, archivo_rel, args.dry_run, manifiesto, notas)
    _sembrar_logos(args.dry_run, manifiesto)

    if notas:
        manifiesto.append("\nnotas:")
        manifiesto.extend(f"  - {n}" for n in notas)

    texto = "\n".join(manifiesto) + "\n"
    if args.dry_run:
        print(texto)
    else:
        with open(os.path.join(EST_CROQUIS_DIR, "manifiesto.txt"), "w", encoding="utf-8") as f:
            f.write(texto)
        print(texto)
        print(f"OK — archivado en {EST_CROQUIS_DIR}")


if __name__ == "__main__":
    main()
