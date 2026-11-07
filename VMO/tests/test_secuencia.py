"""
Tests de scripts/secuencia.py — la logica de secuencia, huecos y corte.

Se prueban las cuatro piezas con logica propia: `partir_id()`,
`calcular_huecos()`, `buscar_inversiones()` y `clasificar_por_corte()`. El
resto del script son consultas SQL, lectura de ZIP e impresion, y probarlas
seria probar sqlite y zipfile. Nada de esto toca las bases ni abre un ZIP.

Correr con: python -m pytest tests/test_secuencia.py -v
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import secuencia  # noqa: E402


# --------------------------------------------------------------------------
# partir_id: la premisa de todo el script
# --------------------------------------------------------------------------

def test_parte_el_id_en_planta_y_secuencia():
    assert secuencia.partir_id("M800012024") == ("M8", 12024)
    assert secuencia.partir_id("M300055455") == ("M3", 55455)


def test_un_id_con_otra_forma_devuelve_none_en_vez_de_reventar():
    """Un id raro es un dato a REPORTAR, no una excepcion que corte el reporte.

    Si esto levantara, una sola fila mal leida por Vision dejaria sin
    reconciliacion a las otras 4.224.
    """
    assert secuencia.partir_id("") is None
    assert secuencia.partir_id(None) is None
    assert secuencia.partir_id("M8001202") is None       # corto
    assert secuencia.partir_id("M8000120245") is None    # largo
    assert secuencia.partir_id("M8ABCDEFGH") is None     # la secuencia no es numerica


def test_los_ceros_a_la_izquierda_no_cambian_el_numero():
    """'00012024' y '12024' son el mismo conduce: la comparacion es numerica.

    Si se comparara como texto, el escaneo (`06-01-M8-12024.pdf`, sin ceros) y
    la base (`M800012024`, con ceros) nunca cruzarian y los 4.224 apareceirian
    todos como huerfanos.
    """
    assert secuencia.partir_id("M800000001") == ("M8", 1)


# --------------------------------------------------------------------------
# calcular_huecos
# --------------------------------------------------------------------------

def test_encuentra_el_numero_ausente_y_le_pone_la_fecha_del_anterior():
    presentes = {
        ("M8", 100): "2026-08-01",
        # falta el 101
        ("M8", 102): "2026-08-02",
    }
    assert secuencia.calcular_huecos(presentes) == [("M8", 101, "2026-08-01")]


def test_una_racha_de_ausentes_arrastra_la_fecha_del_ultimo_presente():
    """REGRESION: buscando solo `numero - 1` el segundo hueco de una racha se
    quedaba sin fecha, y sin fecha no se puede ubicar contra el corte."""
    presentes = {("M3", 10): "2026-08-01", ("M3", 14): "2026-08-03"}
    huecos = secuencia.calcular_huecos(presentes)
    assert huecos == [
        ("M3", 11, "2026-08-01"),
        ("M3", 12, "2026-08-01"),
        ("M3", 13, "2026-08-01"),
    ]


def test_no_inventa_huecos_fuera_del_rango_observado():
    """El rango es lo que se vio, no lo que existe. Un conduce anterior al
    minimo o posterior al maximo no es un hueco: es algo que todavia no entro,
    y contarlo llenaria el reporte de faltantes imaginarios."""
    presentes = {("M8", 500): "2026-08-01", ("M8", 501): "2026-08-01"}
    assert secuencia.calcular_huecos(presentes) == []


def test_las_plantas_no_se_mezclan_entre_si():
    """Cada planta lleva su propia secuencia. Si se contaran juntas, el salto
    de M3 55455 a M8 12024 seria un 'hueco' de 43.431 conduces."""
    presentes = {("M3", 55455): "2026-08-01", ("M8", 12024): "2026-08-01"}
    assert secuencia.calcular_huecos(presentes) == []


# --------------------------------------------------------------------------
# buscar_inversiones
# --------------------------------------------------------------------------

def test_sin_inversiones_cuando_la_fecha_acompana_al_numero():
    presentes = {("M8", 1): "2026-08-01", ("M8", 2): "2026-08-01", ("M8", 3): "2026-08-02"}
    assert secuencia.buscar_inversiones(presentes) == []


def test_detecta_que_un_numero_mayor_tenga_fecha_anterior():
    """Numero y fecha los lee Vision por separado del mismo papel. Que se
    contradigan es una lectura mala de alguno de los dos, y mientras eso pase
    un hueco deja de significar algo."""
    presentes = {("M8", 1): "2026-08-05", ("M8", 2): "2026-08-01"}
    inversiones = secuencia.buscar_inversiones(presentes)
    assert inversiones == [("M8", (1, "2026-08-05"), (2, "2026-08-01"))]


def test_una_fecha_nula_no_se_reporta_como_inversion():
    """Un conduce sin fecha no contradice nada: no se sabe cuando fue. Si
    contara como inversion, cada fecha faltante ensuciaria el chequeo que hace
    confiable al resto del reporte."""
    presentes = {("M8", 1): "2026-08-01", ("M8", 2): None, ("M8", 3): "2026-08-02"}
    assert secuencia.buscar_inversiones(presentes) == []


# --------------------------------------------------------------------------
# clasificar_por_corte: la regla que decide si un hueco es plata
# --------------------------------------------------------------------------

CORTE = "2026-08-16"


def test_debajo_del_corte_va_a_abajo_y_encima_va_a_arriba():
    huecos = [
        ("M8", 10, "2026-06-02"),   # ya contado en el acumulado base
        ("M8", 20, "2026-08-20"),   # todavia no se conto en ningun lado
    ]
    arriba, abajo, sin_ubicar = secuencia.clasificar_por_corte(huecos, CORTE)
    assert arriba == [("M8", 20, "2026-08-20")]
    assert abajo == [("M8", 10, "2026-06-02")]
    assert sin_ubicar == []


def test_la_fecha_igual_al_corte_cuenta_como_debajo():
    """`_est_calcular_acumulados()` saltea con `fecha <= corte`, asi que el dia
    del corte YA esta contado. Usar `>=` aca marcaria como plata en riesgo algo
    que ya esta en el documento entregado."""
    arriba, abajo, _ = secuencia.clasificar_por_corte([("M8", 1, CORTE)], CORTE)
    assert arriba == []
    assert len(abajo) == 1


def test_sin_fecha_previa_no_se_ubica_en_ninguno_de_los_dos():
    huecos = [("M8", 1, None)]
    arriba, abajo, sin_ubicar = secuencia.clasificar_por_corte(huecos, CORTE)
    assert arriba == [] and abajo == []
    assert sin_ubicar == huecos


def test_sin_corte_todo_faltante_cuenta():
    """Corte None es 'no hay ni seed ni cierres', o sea que no se conto nada
    todavia. Mandar todo a `abajo` en ese caso reportaria cero plata en riesgo
    en una base donde justamente TODO esta en riesgo."""
    huecos = [("M8", 1, "2026-06-02"), ("M8", 2, None)]
    arriba, abajo, sin_ubicar = secuencia.clasificar_por_corte(huecos, None)
    assert arriba == huecos
    assert abajo == [] and sin_ubicar == []


# --------------------------------------------------------------------------
# Issue #78: pendiente_descartado tambien es "estar en la base"
# --------------------------------------------------------------------------

def _bd_tres_tablas():
    """BD en memoria con las tres tablas minimas que lee leer_base()."""
    import sqlite3
    con = sqlite3.connect(":memory:")
    for tabla in ("facturas", "pendientes_revision", "pendiente_descartado"):
        con.execute(f"CREATE TABLE {tabla} (id_documento TEXT, fecha DATE)")
    con.execute("INSERT INTO facturas VALUES ('M800000001', '2026-08-01')")
    con.execute("INSERT INTO pendientes_revision VALUES ('M800000002', '2026-08-02')")
    con.execute("INSERT INTO pendiente_descartado VALUES ('M800000003', '2026-08-03')")
    return con


def test_leer_base_incluye_pendiente_descartado():
    """REGRESION (issue #78): leer_base() consultaba solo facturas y
    pendientes_revision. Con la tabla vacia no mordia, pero el primer
    descarte real apareceria como huerfano — "el import lo perdio" — cuando
    en realidad alguien decidio no facturarlo."""
    en_facturas, en_pendientes, en_descartados, ids_raros = secuencia.leer_base(_bd_tres_tablas())
    assert en_facturas == {("M8", 1): "2026-08-01"}
    assert en_pendientes == {("M8", 2): "2026-08-02"}
    assert en_descartados == {("M8", 3): "2026-08-03"}
    assert ids_raros == []


def test_descartado_no_aparece_como_huerfano(capsys):
    """Criterio 7 del issue #78: un escaneo cuyo id esta en
    pendiente_descartado NO es un huerfano."""
    _f, _p, _d, _r = secuencia.leer_base(_bd_tres_tablas())
    escaneos = {
        ("M8", 1): "06-01-M8-1.pdf",
        ("M8", 2): "06-02-M8-2.pdf",
        ("M8", 3): "06-03-M8-3.pdf",   # el descartado, escaneado
        ("M8", 4): "06-04-M8-4.pdf",   # este SI es huerfano de verdad
    }
    secuencia.bloque_reconciliacion(escaneos, _f, _p, _d, avisos=[])
    salida = capsys.readouterr().out
    assert "1 ESCANEADO(S) Y EN NINGUNA TABLA" in salida
    assert "M800000004" in salida        # el huerfano real se reporta
    assert "M800000003" not in salida    # el descartado NO


def test_leer_base_sin_tabla_descartados_no_revienta():
    """Una base anterior a la migracion del issue #38 no tiene
    pendiente_descartado: vale como vacia, no como excepcion."""
    import sqlite3
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE facturas (id_documento TEXT, fecha DATE)")
    con.execute("CREATE TABLE pendientes_revision (id_documento TEXT, fecha DATE)")
    con.execute("INSERT INTO facturas VALUES ('M800000001', '2026-08-01')")
    en_facturas, _p, en_descartados, _r = secuencia.leer_base(con)
    assert en_facturas == {("M8", 1): "2026-08-01"}
    assert en_descartados == {}
