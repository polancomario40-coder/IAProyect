# by a_oller
"""
auditar_sello_macao2.py — Audita las 2,742 facturas ya importadas con fase
'MACAO 2' (procesadas originalmente con Haiku) para detectar falsos positivos
de sello/firma, usando Sonnet + Batch API (50% de descuento).

No modifica nada por si solo: SOLO lee el PDF de dropoff/Puente 1.zip, le
pregunta a Sonnet si de verdad tiene sello y firma, y deja un reporte en
conduces/data/auditoria_macao2_resultado.json con los que hay que revisar. Mover esos
registros de facturas a pendientes_revision es un paso aparte, manual,
despues de confirmar con el usuario.

Resumible: guarda el estado de los batches en conduces/data/auditoria_macao2_batches.json
para poder cortar y retomar sin volver a mandar nada a la API.

Uso:
    python scripts/auditar_sello_macao2.py            # manda batches (o retoma)
    python scripts/auditar_sello_macao2.py --check     # solo revisa estado / recoge resultados
"""

import base64
import json
import sqlite3
import sys
import time
import zipfile
from pathlib import Path

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
from dotenv import load_dotenv

BASE_DIR   = Path(__file__).resolve().parent.parent
DB_PATH    = BASE_DIR / "estimaciones" / "db" / "estimaciones.db"
ZIP_PATH   = BASE_DIR / "dropoff" / "Puente 1.zip"
ZIP_PREFIX = "Puente 1/"
STATE_PATH = BASE_DIR / "conduces" / "data" / "auditoria_macao2_batches.json"
RESULT_PATH = BASE_DIR / "conduces" / "data" / "auditoria_macao2_resultado.json"

MODEL = "claude-sonnet-5"
CHUNK_SIZE = 200  # requests por batch, para no pasarnos del limite de tamano

PROMPT = (
    "Mira este documento con mucho cuidado. Responde UNICAMENTE con JSON:\n"
    '{"tiene_sello": true o false, "tiene_firma": true o false}\n'
    "tiene_sello: true SOLO si hay un sello, timbre o stamp fisico realmente visible "
    "(no cuentan cajas de texto impresas ni recuadros con datos, ni el membrete impreso). "
    "tiene_firma: true SOLO si hay una firma o rubrica a mano realmente visible."
)

load_dotenv(BASE_DIR / ".env")


def cargar_facturas_macao2():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id_documento, archivo_pdf FROM facturas WHERE fase = 'MACAO 2' ORDER BY id_documento"
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def leer_pdf(zf, archivo_pdf):
    return zf.read(ZIP_PREFIX + archivo_pdf)


def cargar_estado():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"batches": []}


def guardar_estado(estado):
    STATE_PATH.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")


def enviar_batches():
    facturas = cargar_facturas_macao2()
    print(f"Facturas MACAO 2 a auditar: {len(facturas)}")

    estado = cargar_estado()
    ya_enviados = set()
    for b in estado["batches"]:
        ya_enviados.update(b["custom_ids"])

    pendientes = [(idd, pdf) for idd, pdf in facturas if idd not in ya_enviados]
    if not pendientes:
        print("Todos los batches ya fueron enviados. Corre con --check para ver el estado.")
        return

    print(f"Pendientes de enviar: {len(pendientes)}")

    client = anthropic.Anthropic()
    zf = zipfile.ZipFile(ZIP_PATH)

    for i in range(0, len(pendientes), CHUNK_SIZE):
        chunk = pendientes[i:i + CHUNK_SIZE]
        requests = []
        custom_ids = []
        for id_documento, archivo_pdf in chunk:
            try:
                pdf_bytes = leer_pdf(zf, archivo_pdf)
            except KeyError:
                print(f"  AVISO: {archivo_pdf} no esta en el zip, se salta")
                continue
            requests.append(
                Request(
                    custom_id=id_documento,
                    params=MessageCreateParamsNonStreaming(
                        model=MODEL,
                        max_tokens=200,
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "document", "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": base64.standard_b64encode(pdf_bytes).decode(),
                                }},
                                {"type": "text", "text": PROMPT},
                            ],
                        }],
                    ),
                )
            )
            custom_ids.append(id_documento)

        if not requests:
            continue

        batch = client.messages.batches.create(requests=requests)
        print(f"  Batch enviado: {batch.id} ({len(requests)} docs)")

        estado["batches"].append({
            "batch_id": batch.id,
            "custom_ids": custom_ids,
            "status": batch.processing_status,
        })
        guardar_estado(estado)

    zf.close()
    print("Todos los batches enviados. Corre con --check para ver el progreso / recoger resultados.")


def revisar_estado():
    estado = cargar_estado()
    if not estado["batches"]:
        print("No hay batches enviados todavia.")
        return

    client = anthropic.Anthropic()
    resultados = {}
    if RESULT_PATH.exists():
        resultados = json.loads(RESULT_PATH.read_text(encoding="utf-8"))

    todos_listos = True
    for b in estado["batches"]:
        info = client.messages.batches.retrieve(b["batch_id"])
        b["status"] = info.processing_status
        counts = info.request_counts
        print(f"  {b['batch_id']}: {info.processing_status} "
              f"(succeeded={counts.succeeded}, errored={counts.errored}, "
              f"processing={counts.processing})")

        if info.processing_status != "ended":
            todos_listos = False
            continue

        if b.get("recogido"):
            continue

        for entry in client.messages.batches.results(b["batch_id"]):
            cid = entry.custom_id
            if entry.result.type == "succeeded":
                msg = entry.result.message
                text_block = next((c for c in msg.content if c.type == "text"), None)
                texto = text_block.text.strip() if text_block else ""
                if texto.startswith("```"):
                    texto = texto.strip("`")
                    if texto.startswith("json"):
                        texto = texto[4:]
                    texto = texto.strip()
                try:
                    parsed = json.loads(texto)
                    resultados[cid] = {
                        "tiene_sello": parsed.get("tiene_sello"),
                        "tiene_firma": parsed.get("tiene_firma"),
                    }
                except Exception as e:
                    resultados[cid] = {"error": f"json invalido: {texto[:200]}"}
            else:
                resultados[cid] = {"error": f"batch error: {entry.result.type}"}

        b["recogido"] = True

    guardar_estado(estado)
    RESULT_PATH.write_text(json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")

    if not todos_listos:
        print("\nTodavia hay batches procesando. Corre --check de nuevo mas tarde.")
        return

    print(f"\nTodos los batches terminaron. Resultados recogidos: {len(resultados)}")

    flagged = {
        cid: r for cid, r in resultados.items()
        if r.get("tiene_sello") is False or r.get("tiene_firma") is False
    }
    errores = {cid: r for cid, r in resultados.items() if "error" in r}

    print(f"Con problema de sello/firma: {len(flagged)}")
    print(f"Errores de lectura: {len(errores)}")
    if flagged:
        print("\nIDs con problema:")
        for cid, r in flagged.items():
            print(f"  {cid}: sello={r.get('tiene_sello')} firma={r.get('tiene_firma')}")


if __name__ == "__main__":
    if "--check" in sys.argv:
        revisar_estado()
    else:
        enviar_batches()
