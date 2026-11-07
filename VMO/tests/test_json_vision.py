"""
Tests del issue #69 — el parseo de la respuesta de Vision y su reintento.

El bug: `_procesar_pdf_sync()` fallaba ~12% de las veces (4 de 32 llamadas
medidas el 2026-09-07) porque el modelo devuelve la descripcion con las
comillas de pulgada SIN escapar —`Agg 3/8", Temp. 32C`— y eso corta el string.
Encima el error que se veia era `Expecting value: line 1 column 1 (char 0)`,
que no es el error real: salia de parsear el texto CON la cerca de markdown
despues de tragarse el error de adentro en un `except: pass`.

Estos tests no llaman a la API: arman la respuesta a mano y le pasan un cliente
falso a _procesar_pdf_sync().

Correr con: python -m pytest tests/test_json_vision.py -v
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402


CERCA = "```"

# La descripcion real que rompe, tal cual la devolvio el modelo en
# 06-27-M3-55948.pdf: las comillas de 3/8" y 6" sin escapar.
JSON_ROTO = (
    '{\n  "id_documento": "M300055948",\n'
    '  "descripcion": "Hormigón fc350 kg/cm2, AME IIIA (EHE), Agg 3/8", Temp. 32C, rev. 6"+/- 1".",\n'
    '  "cantidad": 8\n}'
)
JSON_SANO = '{\n  "id_documento": "M300055948",\n  "cantidad": 8\n}'


def _cercado(cuerpo):
    return CERCA + "json\n" + cuerpo + "\n" + CERCA


# --------------------------------------------------------------------------
# _json_de_respuesta
# --------------------------------------------------------------------------

def test_parsea_con_cerca_de_markdown():
    assert core._json_de_respuesta(_cercado(JSON_SANO))["cantidad"] == 8


def test_parsea_sin_cerca():
    assert core._json_de_respuesta(JSON_SANO)["cantidad"] == 8


def test_el_error_es_el_de_adentro_y_no_el_de_la_cerca():
    """REGRESION, y es el corazon del issue #69.

    Con el JSON roto DENTRO de una cerca, la version vieja levantaba
    `Expecting value: line 1 column 1 (char 0)` — el error de toparse con el
    backtick — y mandaba a investigar el lugar equivocado. El error util es el
    de la comilla sin escapar, que esta en medio del objeto.
    """
    with pytest.raises(ValueError) as exc:
        core._json_de_respuesta(_cercado(JSON_ROTO))
    mensaje = str(exc.value)
    assert "line 1 column 1" not in mensaje, (
        "se filtro el error de la cerca en vez del error real: " + mensaje)
    assert "double quotes" in mensaje


def test_un_json_roto_sin_cerca_tambien_levanta_su_propio_error():
    with pytest.raises(ValueError) as exc:
        core._json_de_respuesta(JSON_ROTO)
    assert "double quotes" in str(exc.value)


# --------------------------------------------------------------------------
# el reintento de _procesar_pdf_sync
# --------------------------------------------------------------------------

class _Bloque:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Respuesta:
    def __init__(self, text):
        self.content = [_Bloque(text)]


class _ClienteFalso:
    """Devuelve los textos que le pasen, uno por llamada. Cuenta las llamadas."""

    def __init__(self, textos):
        self.textos = list(textos)
        self.llamadas = 0
        self.messages = self

    def create(self, **kwargs):
        self.llamadas += 1
        return _Respuesta(self.textos.pop(0))


@pytest.fixture
def cliente_falso(monkeypatch):
    def instalar(textos):
        falso = _ClienteFalso(textos)
        monkeypatch.setattr(core, "client", falso)
        return falso
    return instalar


def test_una_respuesta_rota_se_reintenta_y_la_siguiente_salva(cliente_falso):
    """REGRESION: sin reintento, el ~12% de fallo aleatorio por llamada llegaba
    entero al usuario. Como el fallo NO es propiedad del documento —el mismo
    PDF fallo 2 veces y paso 6— volver a preguntar alcanza."""
    falso = cliente_falso([_cercado(JSON_ROTO), _cercado(JSON_SANO)])
    assert core._procesar_pdf_sync(b"%PDF-falso")["cantidad"] == 8
    assert falso.llamadas == 2


def test_si_la_primera_sale_bien_no_hay_segunda_llamada(cliente_falso):
    """Reintentar no puede costar una llamada de mas en el camino feliz: se
    paga por llamada a Vision y el 88% de las veces la primera alcanza."""
    falso = cliente_falso([_cercado(JSON_SANO)])
    core._procesar_pdf_sync(b"%PDF-falso")
    assert falso.llamadas == 1


def test_agotados_los_intentos_levanta_el_error_util(cliente_falso):
    """Si las tres fallan, lo que sube tiene que ser el error de la comilla, no
    el de la cerca — el diagnostico es todo lo que queda."""
    falso = cliente_falso([_cercado(JSON_ROTO)] * core.EST_VISION_INTENTOS)
    with pytest.raises(ValueError) as exc:
        core._procesar_pdf_sync(b"%PDF-falso")
    assert falso.llamadas == core.EST_VISION_INTENTOS
    assert "double quotes" in str(exc.value)
    assert "line 1 column 1" not in str(exc.value)


def test_una_respuesta_sin_bloque_de_texto_tambien_se_reintenta(cliente_falso):
    """Una respuesta sin texto (solo thinking u otro bloque) es tan transitoria
    como un JSON roto: antes cortaba en seco."""
    class _SinTexto:
        content = []

    falso = cliente_falso([_cercado(JSON_SANO)])
    llamadas = {"n": 0}
    original_create = falso.create

    def create(**kwargs):
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            falso.llamadas += 1
            return _SinTexto()
        return original_create(**kwargs)

    falso.create = create
    assert core._procesar_pdf_sync(b"%PDF-falso")["cantidad"] == 8
    assert llamadas["n"] == 2
