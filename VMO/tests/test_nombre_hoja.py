"""
Tests de caracterizacion del nombrado de hojas RGO — issue #27, decision D3.

Contexto: _est_nombre_rgo (core.py) cablea el prefijo "CD-COAF-RGO-" pero el
resto de su logica (saneo de caracteres invalidos de Excel, truncado a 31
caracteres, resolucion de colisiones con sufijo consecutivo) sirve igual para
las familias RCO y RFO. El refactor D3 la parametriza y la renombra a
_est_nombre_hoja. Ninguna de las 483 pruebas existentes afirmaba sobre su
salida, y es codigo que las RGO usan en produccion — asi que ANTES de tocarla
se captura aca su comportamiento exacto, caso por caso, con los valores
literales que devuelve hoy.

Estos tests se escribieron contra el codigo SIN tocar y pasaron en verde antes
del refactor. La regla del issue #27: si el refactor obliga a editar una sola
linea de este archivo, el comportamiento cambio — hay que parar y reportarlo,
no ajustar el test.

Correr con: python -m pytest tests/test_nombre_hoja.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402


def _nombrar(clave, usados):
    """Resuelve la funcion de nombrado vigente para la familia RGO.

    Antes del refactor D3 la funcion es _est_nombre_rgo(clave, usados), con el
    prefijo RGO cableado adentro; despues del refactor es
    _est_nombre_hoja(clave, usados, "CD-COAF-RGO-"). Este helper acepta las
    dos formas a proposito: los tests capturan el COMPORTAMIENTO (que nombre
    sale para las RGO), no la firma, y asi el refactor anunciado no obliga a
    editar ninguna afirmacion de este archivo.
    """
    fn = getattr(core, "_est_nombre_hoja", None)
    if fn is not None:
        return fn(clave, usados, "CD-COAF-RGO-")
    return core._est_nombre_rgo(clave, usados)


# ── claves numericas ──────────────────────────────────────────────────────

def test_clave_de_un_digito_se_rellena_a_dos():
    assert _nombrar("1", set()) == "CD-COAF-RGO-01"


def test_clave_entera_no_string_tambien_se_rellena():
    assert _nombrar(7, set()) == "CD-COAF-RGO-07"


def test_clave_de_dos_digitos_queda_igual():
    assert _nombrar("12", set()) == "CD-COAF-RGO-12"


def test_clave_de_tres_digitos_no_se_recorta():
    assert _nombrar("123", set()) == "CD-COAF-RGO-123"


def test_clave_cero_da_00():
    assert _nombrar("0", set()) == "CD-COAF-RGO-00"


def test_clave_con_ceros_a_la_izquierda_se_normaliza():
    # "007" es digito, pasa por int() y sale como "07"
    assert _nombrar("007", set()) == "CD-COAF-RGO-07"


def test_clave_numerica_con_espacios_alrededor_se_limpia():
    assert _nombrar(" 4 ", set()) == "CD-COAF-RGO-04"


# ── claves no numericas ───────────────────────────────────────────────────

def test_clave_alfanumerica_se_usa_tal_cual():
    assert _nombrar("A1", set()) == "CD-COAF-RGO-A1"


def test_caracteres_invalidos_de_excel_se_reemplazan_por_guion():
    # Excel prohibe \ / * ? : [ ] en nombres de hoja
    assert _nombrar("A/B", set()) == "CD-COAF-RGO-A-B"
    assert _nombrar("x*y?", set()) == "CD-COAF-RGO-x-y-"
    assert _nombrar("[7]", set()) == "CD-COAF-RGO--7-"
    assert _nombrar("a\\b:c", set()) == "CD-COAF-RGO-a-b-c"


def test_clave_vacia_o_solo_espacios_da_sin_clave():
    assert _nombrar("", set()) == "CD-COAF-RGO-SIN-CLAVE"
    assert _nombrar("   ", set()) == "CD-COAF-RGO-SIN-CLAVE"


# ── truncado a 31 caracteres (limite fisico de Excel) ─────────────────────

def test_nombre_largo_se_trunca_a_31_caracteres():
    clave = "ABCDEFGHIJKLMNOPQRSTUVWXYZ12345"   # 31 caracteres de clave
    nombre = _nombrar(clave, set())
    assert nombre == "CD-COAF-RGO-ABCDEFGHIJKLMNOPQRS"
    assert len(nombre) == 31


# ── colisiones ────────────────────────────────────────────────────────────

def test_colision_agrega_sufijo_consecutivo():
    usados = set()
    assert _nombrar("1", usados) == "CD-COAF-RGO-01"
    assert _nombrar("1", usados) == "CD-COAF-RGO-01-2"
    assert _nombrar("1", usados) == "CD-COAF-RGO-01-3"


def test_colision_con_nombre_ya_reservado_de_antemano():
    # el generador siembra nombres_usados con wb.sheetnames: un nombre que ya
    # exista en el libro tambien cuenta como colision
    usados = {"CD-COAF-RGO-05"}
    assert _nombrar("5", usados) == "CD-COAF-RGO-05-2"


def test_colision_de_nombre_truncado_recorta_para_que_quepa_el_sufijo():
    clave = "ABCDEFGHIJKLMNOPQRSTUVWXYZ12345"
    usados = set()
    assert _nombrar(clave, usados) == "CD-COAF-RGO-ABCDEFGHIJKLMNOPQRS"
    segundo = _nombrar(clave, usados)
    assert segundo == "CD-COAF-RGO-ABCDEFGHIJKLMNOPQ-2"
    assert len(segundo) == 31


def test_el_nombre_devuelto_queda_registrado_en_usados():
    usados = set()
    nombre = _nombrar("9", usados)
    assert nombre in usados
    # y los sufijos tambien se registran
    nombre2 = _nombrar("9", usados)
    assert nombre2 in usados
    assert usados == {"CD-COAF-RGO-09", "CD-COAF-RGO-09-2"}
