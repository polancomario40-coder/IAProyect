# by a_oller
import os
import sys
import csv
import base64
import json

import fitz  # pymupdf
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

PROMPT = """Eres un asistente de extracción de datos. Esta es una imagen de un conduce (comprobante de entrega de agregados).

Extrae TODOS los conduces que aparezcan en esta página y devuelve un JSON con esta estructura exacta:
{
  "conduces": [
    {
      "id_conduce": "...",
      "fecha": "YYYY-MM-DD",
      "producto": "...",
      "compania": "...",
      "precio": 0.00,
      "cantidad": 0.00
    }
  ]
}

Reglas:
- id_conduce: el número o código impreso en el documento físico (entre 5 y 10 caracteres)
- fecha: en formato YYYY-MM-DD. Si el documento tiene otro formato, conviértelo.
- producto: tipo de material (arena, gravilla, piedra, etc.)
- compania: busca el nombre de la empresa/compañía/suplidor en CUALQUIER parte de la página — encabezado, pie de página, membrete, sello, o cualquier fila de la tabla. Si lo encuentras en algún lugar, úsalo para TODOS los registros de esta página. Nunca dejes compania vacío si el nombre aparece en algún lugar de la página.
- precio: precio unitario como número decimal
- cantidad: cantidad entregada como número decimal
- Si algún campo no está visible en ninguna parte del documento, usa null
- Devuelve SOLO el JSON, sin texto adicional"""


def pdf_a_imagenes(pdf_path: str) -> list[bytes]:
    doc = fitz.open(pdf_path)
    imagenes = []
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        imagenes.append(pix.tobytes("png"))
    doc.close()
    return imagenes


def extraer_conduces_de_imagen(imagen_bytes: bytes, num_pagina: int) -> list[dict]:
    imagen_b64 = base64.standard_b64encode(imagen_bytes).decode("utf-8")

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": imagen_b64,
                        },
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
    )

    texto = response.content[0].text.strip()

    # Limpiar posibles bloques de código markdown
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    texto = texto.strip()

    data = json.loads(texto)
    conduces = data.get("conduces", [])
    print(f"  Página {num_pagina}: {len(conduces)} conduce(s) encontrado(s)")
    return conduces


def main():
    if len(sys.argv) < 2:
        print("Uso: python extraer_pdf.py archivo.pdf [salida.csv]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    csv_path = sys.argv[2] if len(sys.argv) > 2 else pdf_path.rsplit(".", 1)[0] + ".csv"

    if not os.path.exists(pdf_path):
        print(f"Archivo no encontrado: {pdf_path}")
        sys.exit(1)

    print(f"Procesando: {pdf_path}")
    imagenes = pdf_a_imagenes(pdf_path)
    print(f"Total de páginas: {len(imagenes)}")

    todos = []
    for i, imagen in enumerate(imagenes, start=1):
        try:
            conduces = extraer_conduces_de_imagen(imagen, i)
            todos.extend(conduces)
        except Exception as e:
            print(f"  Página {i}: error — {e}")

    if not todos:
        print("No se encontraron conduces.")
        sys.exit(0)

    campos = ["id_conduce", "fecha", "producto", "compania", "precio", "cantidad"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(todos)

    print(f"\nTotal extraídos: {len(todos)}")
    print(f"CSV generado: {csv_path}")
    print(f"\nPara importar: python importar.py {csv_path}")


if __name__ == "__main__":
    main()
