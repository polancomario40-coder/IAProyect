"""
Tests del issue #73 — los escaneos rotados 180 grados.

El bug no era que Vision devolviera nada: devolvia un documento COMPLETO Y
EQUIVOCADO. Medido el 2026-09-07 sobre `06-17-M7-18862.pdf`, sin rotar contra
rotado: id_documento `M7018882` contra `M700018862`, cantidad **11.0** contra
**7.0** (el papel dice 7,00), una descripcion inventada, y tiene_sello y
tiene_firma en true en los dos casos — asi que el documento malo tampoco caia
en pendientes_revision. Cuatro m3 inventados y nada que avisara.

Por que se le pregunta al modelo en vez de detectarlo:

- Del archivo no se puede: en los cuatro rotados que apareceieron
  `page.rotation` vale 0 (la vuelta esta en la imagen) y no hay capa de texto.
- Comparando el id de Vision contra el del nombre del PDF tampoco: medido,
  6 de 11 documentos SANOS ya traen el id distinto por confusiones de OCR
  (`MS00012229` por `M800012229`). Como detector daria ~55% de falsos
  positivos.

Preguntarselo en el mismo prompt acerto 8 de 8 (4 rotados, 4 sanos) y no
cuesta ninguna llamada extra en el caso normal.

Estos tests no llaman a la API: arman la respuesta a mano.

Correr con: python -m pytest tests/test_escaneos_rotados.py -v
"""
import json
import os
import sys

import fitz
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402


def _pdf_de_una_pagina():
    doc = fitz.open()
    doc.new_page()
    datos = doc.tobytes()
    doc.close()
    return datos


# --------------------------------------------------------------------------
# _rotar_pdf
# --------------------------------------------------------------------------

def test_rotar_deja_la_pagina_a_180():
    doc = fitz.open(stream=core._rotar_pdf(_pdf_de_una_pagina()), filetype="pdf")
    try:
        assert doc[0].rotation == 180
    finally:
        doc.close()


def test_rotar_dos_veces_vuelve_al_principio():
    """La rotacion se SUMA a la que ya tenga la pagina, no la fija. Si la
    pisara, un PDF que ya viniera con rotation=180 en el metadato quedaria
    igual al rotarlo y el arreglo no haria nada."""
    una = core._rotar_pdf(_pdf_de_una_pagina())
    dos = core._rotar_pdf(una)
    doc = fitz.open(stream=dos, filetype="pdf")
    try:
        assert doc[0].rotation == 0
    finally:
        doc.close()


def test_rotar_no_rompe_el_pdf():
    doc = fitz.open(stream=core._rotar_pdf(_pdf_de_una_pagina()), filetype="pdf")
    try:
        assert doc.page_count == 1
    finally:
        doc.close()


# --------------------------------------------------------------------------
# el reintento rotado de _procesar_pdf_sync
# --------------------------------------------------------------------------

class _Bloque:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Respuesta:
    def __init__(self, text):
        self.content = [_Bloque(text)]


class _ClienteFalso:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.llamadas = 0
        self.messages = self

    def create(self, **kwargs):
        self.llamadas += 1
        return _Respuesta(json.dumps(self.payloads.pop(0)))


@pytest.fixture
def cliente_falso(monkeypatch):
    def instalar(payloads):
        falso = _ClienteFalso(payloads)
        monkeypatch.setattr(core, "client", falso)
        return falso
    return instalar


DERECHO = {"al_reves": False, "id_documento": "M700018862", "cantidad": 7.0}
AL_REVES = {"al_reves": True, "id_documento": "M7018882", "cantidad": 11.0}


def test_un_documento_al_reves_se_relee_rotado(cliente_falso):
    """REGRESION: la primera lectura trae 11 m3 y un id mal; la segunda, con
    el PDF rotado, trae los 7 m3 reales. Lo que se devuelve tiene que ser la
    SEGUNDA."""
    falso = cliente_falso([AL_REVES, DERECHO])
    datos = core._procesar_pdf_sync(_pdf_de_una_pagina())
    assert falso.llamadas == 2
    assert datos["cantidad"] == 7.0
    assert datos["id_documento"] == "M700018862"


def test_un_documento_derecho_no_paga_una_segunda_llamada(cliente_falso):
    """Preguntar la orientacion va DENTRO del prompt que ya existia, asi que
    el caso normal —que es casi todo— no puede costar una llamada de mas."""
    falso = cliente_falso([DERECHO])
    datos = core._procesar_pdf_sync(_pdf_de_una_pagina())
    assert falso.llamadas == 1
    assert datos["cantidad"] == 7.0


def test_se_rota_una_sola_vez_aunque_la_segunda_insista(cliente_falso):
    """Si la relectura tambien dice al_reves, algo mas esta pasando: seguir
    girando solo gasta plata. Sin este tope el bucle no termina."""
    falso = cliente_falso([AL_REVES, AL_REVES])
    datos = core._procesar_pdf_sync(_pdf_de_una_pagina())
    assert falso.llamadas == 2
    assert datos["al_reves"] is True


def test_el_prompt_pide_la_orientacion(cliente_falso):
    """Si el campo se cae del esquema, el modelo no lo devuelve, `al_reves`
    queda en None y NUNCA se rota — el arreglo se apaga en silencio y todos
    los demas tests siguen pasando porque arman la respuesta a mano."""
    capturado = {}

    class _Captura(_ClienteFalso):
        def create(self, **kwargs):
            capturado["prompt"] = kwargs["messages"][0]["content"][1]["text"]
            return super().create(**kwargs)

    falso = _Captura([DERECHO])
    import unittest.mock
    with unittest.mock.patch.object(core, "client", falso):
        core._procesar_pdf_sync(_pdf_de_una_pagina())
    esquema = capturado["prompt"].split("}")[0]
    assert '"al_reves"' in esquema, "al_reves se cayo del esquema JSON del prompt"


# --------------------------------------------------------------------------
# el mismo tratamiento en el camino del backfill
# --------------------------------------------------------------------------

OBRA_DERECHA = {"al_reves": False, "obra": "EXTERIORES1111"}
OBRA_AL_REVES = {"al_reves": True, "obra": None}


def test_el_backfill_tambien_relee_rotado(cliente_falso):
    """REGRESION: aca fue donde aparecio el bug. De 4.185 filas, 4 quedaron
    sin obra_papel y las 4 eran escaneos dados vuelta; rotados salieron 4 de
    4. Sin esta relectura esas filas quedan en NULL para siempre."""
    falso = cliente_falso([OBRA_AL_REVES, OBRA_DERECHA])
    assert core._extraer_obra_papel(_pdf_de_una_pagina()) == "EXTERIORES1111"
    assert falso.llamadas == 2


def test_el_backfill_derecho_no_paga_una_segunda_llamada(cliente_falso):
    falso = cliente_falso([OBRA_DERECHA])
    assert core._extraer_obra_papel(_pdf_de_una_pagina()) == "EXTERIORES1111"
    assert falso.llamadas == 1


def test_el_backfill_rota_una_sola_vez(cliente_falso):
    falso = cliente_falso([OBRA_AL_REVES, OBRA_AL_REVES])
    assert core._extraer_obra_papel(_pdf_de_una_pagina()) is None
    assert falso.llamadas == 2


# --------------------------------------------------------------------------
# 90 / 270 grados: se ve en el archivo, no hace falta preguntarle al modelo
# --------------------------------------------------------------------------
#
# Medido el 2026-10-05 sobre los ~6.100 conduces: ninguno con el contenido
# girado 90/270, 118 con /Rotate en el metadato que ya se ven derechos, y
# una sola pagina vertical (M800015683, atascada pero derecha). El conduce
# es apaisado, asi que un contenido girado 90/270 se VE vertical.

def _pdf(ancho, alto, rotacion=0):
    doc = fitz.open()
    pagina = doc.new_page(width=ancho, height=alto)
    if rotacion:
        pagina.set_rotation(rotacion)
    datos = doc.tobytes()
    doc.close()
    return datos


def test_apaisado_no_es_vertical():
    assert core._pagina_vertical(_pdf(800, 600)) is False


def test_vertical_es_vertical():
    assert core._pagina_vertical(_pdf(600, 800)) is True


def test_el_rotate_del_metadato_cuenta():
    """REGRESION del caso real: los 118 escaneos con la imagen vertical y
    /Rotate 90 o 270 se VEN apaisados y Vision los lee bien. Mirar la
    pagina sin aplicar el /Rotate (o mirar la imagen embebida) los
    mandaria a revision a todos."""
    assert core._pagina_vertical(_pdf(600, 800, rotacion=270)) is False
    assert core._pagina_vertical(_pdf(600, 800, rotacion=90)) is False
    # y al reves: apaisado en el mediabox pero girado se ve vertical
    assert core._pagina_vertical(_pdf(800, 600, rotacion=90)) is True


def test_un_pdf_roto_no_es_vertical():
    assert core._pagina_vertical(b"no es un pdf") is False


def test_procesar_anota_la_pagina_vertical(cliente_falso):
    """No paga ninguna llamada extra: es geometria."""
    falso = cliente_falso([DERECHO])
    datos = core._procesar_pdf_sync(_pdf(600, 800))
    assert falso.llamadas == 1
    assert datos["_pagina_vertical"] is True


def test_procesar_apaisado_no_anota(cliente_falso):
    cliente_falso([DERECHO])
    assert core._procesar_pdf_sync(_pdf(800, 600))["_pagina_vertical"] is False


OK_MACAO2 = {"fase": "MACAO 2", "tiene_sello": True, "tiene_firma": True}
OK_OTRA = {"fase": "CAVERNAS", "tiene_sello": True, "tiene_firma": True}


def test_un_vertical_que_iba_a_entrar_va_a_revision():
    """El caso peligroso: con sello y firma afirmados entraba directo."""
    for base in (OK_MACAO2, OK_OTRA):
        assert core._motivo_sello_firma({**base, "_pagina_vertical": True}) ==             core.EST_MOTIVO_PAGINA_VERTICAL
        assert core._motivo_sello_firma({**base, "_pagina_vertical": False}) is None


def test_el_vertical_no_tapa_los_motivos_de_siempre():
    """Va ultimo: si ya faltaba sello o firma, ese sigue siendo el motivo."""
    assert core._motivo_sello_firma(
        {**OK_MACAO2, "tiene_sello": False, "_pagina_vertical": True}) == "falta sello"
    assert core._motivo_sello_firma(
        {**OK_OTRA, "tiene_firma": False, "_pagina_vertical": True}) == "falta firma"
    assert core._motivo_sello_firma(
        {"fase": None, "_pagina_vertical": True}) == "fase no reconocida"


def test_el_vertical_es_aprobable():
    """El unico vertical real es un escaneo atascado pero derecho: si no se
    pudiera aprobar, no tendria ningun camino de entrada."""
    assert core.EST_MOTIVO_PAGINA_VERTICAL in core.EST_MOTIVOS_APROBABLES
