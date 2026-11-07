"""
Issue #25 — aviso pasivo: `facturas.clave_resuelta` le gana al catalogo para
siempre y nada la revalida contra un alias agregado despues. Es el defecto que
dejo 56 conduces / 370 m3 de CAVERNAS en la clave 3 ($122) cuando iban en la 2
($111) — $4,070 de mas.

Cubre `core._est_revisar_claves_resueltas()` y el endpoint
GET /api/estimaciones/claves-resueltas: los tres desenlaces (discrepa / sin
auto-match / coincide), el caso borde de la clave que ya no existe en el
catalogo (que el generador ya absorbe por otro lado), el escopeo por fase de
los alias, la colision de catalogo, y la garantia de solo-lectura.

Todo sobre BDs temporales — nunca la BD real.

Correr con: python -m pytest tests/test_claves_resueltas.py -v
"""
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import main  # noqa: E402


def _crear_bd(ruta, catalogo, facturas):
    """BD minima con solo lo que mira el detector: catalogo_estimacion y
    facturas. `catalogo` = [(empresa, fase, orden, clave, descripcion, pu)],
    `facturas` = [(id_documento, empresa, fase, descripcion, cantidad,
    clave_resuelta)]."""
    conn = sqlite3.connect(str(ruta))
    conn.execute("""CREATE TABLE catalogo_estimacion (
        empresa TEXT, fase TEXT, orden INTEGER, clave TEXT,
        descripcion TEXT, precio_unitario REAL,
        PRIMARY KEY (empresa, fase, orden)
    )""")
    conn.execute("""CREATE TABLE facturas (
        id_documento TEXT PRIMARY KEY, fecha DATE, empresa TEXT, fase TEXT,
        descripcion TEXT, cantidad REAL, precio_unitario REAL, clave_resuelta TEXT
    )""")
    conn.executemany("INSERT INTO catalogo_estimacion VALUES (?,?,?,?,?,?)", catalogo)
    conn.executemany(
        "INSERT INTO facturas (id_documento, fecha, empresa, fase, descripcion, "
        "cantidad, precio_unitario, clave_resuelta) VALUES (?,'2026-07-01',?,?,?,?,NULL,?)",
        facturas)
    conn.commit()
    conn.close()
    return ruta


def _conectar_ro(ruta):
    """Igual que el endpoint: solo lectura de verdad, no por convencion."""
    return sqlite3.connect(Path(ruta).absolute().as_uri() + "?mode=ro", uri=True)


def _revisar(ruta, **kwargs):
    conn = _conectar_ro(ruta)
    try:
        return core._est_revisar_claves_resueltas(conn, **kwargs)
    finally:
        conn.close()


def _solo(lista):
    assert len(lista) == 1, f"se esperaba 1 fila, hay {len(lista)}"
    return lista[0]


# ── El caso que dolio: alias agregado despues, resolucion manual vieja ──

# Texto real de las facturas de CAVERNAS. El alias por fase de
# _EST_ALIAS_DESCRIPCION_FACTURA lo mapea a la clave "2"; antes de que ese alias
# existiera el sistema pidio resolver a mano y se eligio la clave "3".
DESC_150_CAVERNAS = 'Hormigón 150 kg/cm2, Ag 3/4",T 35C, rev. 7" +/- 1"'

CATALOGO_CAVERNAS = [
    ("DOMICEM", "CAVERNAS", 1, "1", "Concreto f'c=100 kg/cm2", 109.0),
    ("DOMICEM", "CAVERNAS", 2, "2", "Concreto f'c=150 kg/cm2", 111.0),
    ("DOMICEM", "CAVERNAS", 3, "3", "Concreto f'c=210 kg/cm2", 122.0),
]


@pytest.fixture
def bd_cavernas(tmp_path):
    return _crear_bd(
        tmp_path / "est.db", CATALOGO_CAVERNAS,
        # 56 conduces / 370 m3 resueltos a la clave 3, como el caso real
        [(f"M30000{i:04d}", "DOMICEM", "CAVERNAS", DESC_150_CAVERNAS, 370.0 / 56, "3")
         for i in range(56)],
    )


def test_discrepa_reporta_las_dos_claves_con_su_precio_y_el_dinero_en_juego(bd_cavernas):
    datos = _revisar(bd_cavernas)
    assert datos["sin_auto_match"] == [] and datos["coinciden"] == []
    fila = _solo(datos["discrepan"])

    assert fila["clave_resuelta"] == "3"
    assert fila["descripcion_resuelta"] == "Concreto f'c=210 kg/cm2"
    assert fila["precio_resuelta"] == 122.0
    assert fila["clave_auto"] == "2"
    assert fila["descripcion_auto"] == "Concreto f'c=150 kg/cm2"
    assert fila["precio_auto"] == 111.0

    assert fila["facturas"] == 56
    assert fila["cantidad"] == pytest.approx(370.0)
    assert fila["importe_resuelta"] == pytest.approx(370.0 * 122.0)   # 45,140
    assert fila["importe_auto"] == pytest.approx(370.0 * 111.0)       # 41,070
    # los $4,070 exactos del incidente historico
    assert fila["diferencia"] == pytest.approx(4070.0)
    assert fila["clave_resuelta_obsoleta"] is False
    assert len(fila["ids"]) == 56

    assert datos["resumen"]["facturas_discrepan"] == 56
    assert datos["resumen"]["diferencia_total"] == pytest.approx(4070.0)
    assert datos["resumen"]["discrepan_sin_precio"] == 0


def test_sin_auto_match_no_es_discrepancia(tmp_path):
    bd = _crear_bd(tmp_path / "est.db", CATALOGO_CAVERNAS,
                   [("M300000001", "DOMICEM", "CAVERNAS",
                     "Hormigon inventado que no matchea nada", 12.0, "3")])
    datos = _revisar(bd)
    assert datos["discrepan"] == [] and datos["coinciden"] == []
    fila = _solo(datos["sin_auto_match"])
    assert fila["clave_auto"] is None
    assert fila["descripcion_auto"] is None and fila["precio_auto"] is None
    assert fila["importe_auto"] is None
    # sin las dos puntas no se puede afirmar cuanta plata hay en juego
    assert fila["diferencia"] is None
    assert fila["clave_resuelta"] == "3" and fila["precio_resuelta"] == 122.0
    assert fila["clave_resuelta_obsoleta"] is False
    assert datos["resumen"]["facturas_sin_auto_match"] == 1


def test_coincide_marca_la_resolucion_como_redundante(tmp_path):
    bd = _crear_bd(tmp_path / "est.db", CATALOGO_CAVERNAS,
                   [("M300000001", "DOMICEM", "CAVERNAS",
                     "Concreto f'c=210 kg/cm2", 12.0, "3")])
    datos = _revisar(bd)
    assert datos["discrepan"] == [] and datos["sin_auto_match"] == []
    fila = _solo(datos["coinciden"])
    assert fila["clave_auto"] == "3" == fila["clave_resuelta"]
    assert fila["diferencia"] == 0
    assert datos["resumen"]["facturas_coinciden"] == 1


def test_los_tres_desenlaces_salen_separados_en_la_misma_corrida(tmp_path):
    bd = _crear_bd(tmp_path / "est.db", CATALOGO_CAVERNAS, [
        ("M300000001", "DOMICEM", "CAVERNAS", DESC_150_CAVERNAS, 10.0, "3"),      # discrepa
        ("M300000002", "DOMICEM", "CAVERNAS", "Nada parecido a un producto", 5.0, "1"),  # sin match
        ("M300000003", "DOMICEM", "CAVERNAS", "Concreto f'c=210 kg/cm2", 7.0, "3"),      # coincide
        ("M300000004", "DOMICEM", "CAVERNAS", "Concreto f'c=210 kg/cm2", 9.0, None),     # sin resolver: no se mira
    ])
    datos = _revisar(bd)
    assert len(datos["discrepan"]) == 1
    assert len(datos["sin_auto_match"]) == 1
    assert len(datos["coinciden"]) == 1
    # la factura sin clave_resuelta no entra en ninguno de los tres
    assert datos["resumen"]["facturas_revisadas"] == 3
    todos_ids = [i for g in ("discrepan", "sin_auto_match", "coinciden")
                 for f in datos[g] for i in f["ids"]]
    assert "M300000004" not in todos_ids


# ── Caso borde: la clave guardada ya no existe en el catalogo ──
# El generador ya lo absorbe (routes_estimaciones: `if clave not in
# claves_validas: clave = None`), pero pasa invisible: el detector lo marca.

def test_clave_resuelta_que_ya_no_existe_en_el_catalogo_se_marca_obsoleta(tmp_path):
    bd = _crear_bd(tmp_path / "est.db", CATALOGO_CAVERNAS,
                   [("M300000001", "DOMICEM", "CAVERNAS", DESC_150_CAVERNAS, 20.0, "99")])
    datos = _revisar(bd)
    fila = _solo(datos["discrepan"])
    assert fila["clave_resuelta"] == "99"
    assert fila["clave_resuelta_obsoleta"] is True
    # no hay producto detras de la clave guardada: ni descripcion, ni P.U., ni importe
    assert fila["descripcion_resuelta"] is None and fila["precio_resuelta"] is None
    assert fila["importe_resuelta"] is None and fila["diferencia"] is None
    # el auto-match si tiene precio y se muestra igual
    assert fila["clave_auto"] == "2" and fila["importe_auto"] == pytest.approx(20.0 * 111.0)
    assert datos["resumen"]["claves_obsoletas"] == 1
    # una discrepancia sin las dos puntas no puede sumar 0 a la plata en juego
    assert datos["resumen"]["diferencia_total"] == 0
    assert datos["resumen"]["discrepan_sin_precio"] == 1


def test_clave_obsoleta_y_sin_auto_match_queda_en_sin_auto_match_pero_marcada(tmp_path):
    bd = _crear_bd(tmp_path / "est.db", CATALOGO_CAVERNAS,
                   [("M300000001", "DOMICEM", "CAVERNAS", "Descripcion sin match", 20.0, "99")])
    datos = _revisar(bd)
    assert datos["discrepan"] == []
    fila = _solo(datos["sin_auto_match"])
    assert fila["clave_resuelta_obsoleta"] is True
    assert datos["resumen"]["claves_obsoletas"] == 1


def test_fase_sin_catalogo_no_se_declara_obsoleta(tmp_path):
    """Sin catalogo cargado no hay con que afirmar que la clave sea obsoleta —
    la fila cae en sin_auto_match, pero sin la marca roja."""
    bd = _crear_bd(tmp_path / "est.db", CATALOGO_CAVERNAS,
                   [("M300000001", "VMO", "CANCHAS", "Lo que sea", 20.0, "3")])
    datos = _revisar(bd)
    fila = _solo(datos["sin_auto_match"])
    assert fila["clave_resuelta_obsoleta"] is False
    assert datos["resumen"]["claves_obsoletas"] == 0


# ── Alias y colisiones: el detector usa exactamente el mismo mapa que el generador ──

def test_el_alias_de_una_fase_no_alcanza_a_otra_fase(tmp_path):
    """Regresion del arreglo de fe8e260: el alias de CAVERNAS no debe aplicarse
    a otra fase aunque esa fase tenga una clave con el mismo numero."""
    catalogo = CATALOGO_CAVERNAS + [
        ("DOMICEM", "VIVIENDAS", 1, "2", "Otro producto totalmente distinto", 200.0),
    ]
    bd = _crear_bd(tmp_path / "est.db", catalogo,
                   [("M300000001", "DOMICEM", "VIVIENDAS", DESC_150_CAVERNAS, 20.0, "2")])
    datos = _revisar(bd)
    # en VIVIENDAS ese texto no matchea nada: nunca debe leerse como "coincide"
    assert datos["discrepan"] == [] and datos["coinciden"] == []
    assert _solo(datos["sin_auto_match"])["clave_auto"] is None


def test_colision_de_catalogo_cuenta_como_sin_auto_match_nunca_como_discrepancia(tmp_path):
    """_est_catalogo_norm_a_clave() marca None a proposito cuando 2 productos
    normalizan al mismo texto (MACAO 2: 'CIMENTACION TORRES' vs 'TORRE GRUA').
    Ese None significa 'no matcheo', no 'matcheo a nada' — si se leyera mal, el
    aviso diria que toda factura de un producto colisionado discrepa."""
    catalogo = [
        ("DOMICEM", "MACAO 2", 1, "5", "Concreto especial CIMENTACION TORRES", 150.0),
        ("DOMICEM", "MACAO 2", 2, "6", "Concreto especial TORRE GRUA", 160.0),
    ]
    bd = _crear_bd(tmp_path / "est.db", catalogo,
                   [("M300000001", "DOMICEM", "MACAO 2", "Concreto especial", 20.0, "5")])
    datos = _revisar(bd)
    assert datos["discrepan"] == [] and datos["coinciden"] == []
    assert _solo(datos["sin_auto_match"])["clave_auto"] is None


# ── Agrupacion, filtros y orden ──

def test_agrupa_por_descripcion_y_clave_sin_mezclar_fases(tmp_path):
    catalogo = CATALOGO_CAVERNAS + [
        ("DOMICEM", "VIVIENDAS", 1, "3", "Concreto f'c=210 kg/cm2", 130.0),
    ]
    bd = _crear_bd(tmp_path / "est.db", catalogo, [
        ("M300000001", "DOMICEM", "CAVERNAS", "Concreto f'c=210 kg/cm2", 5.0, "3"),
        ("M300000002", "DOMICEM", "CAVERNAS", "Concreto f'c=210 kg/cm2", 7.0, "3"),
        ("M300000003", "DOMICEM", "VIVIENDAS", "Concreto f'c=210 kg/cm2", 9.0, "3"),
    ])
    datos = _revisar(bd)
    assert len(datos["coinciden"]) == 2  # una fila por fase, no una sola mezclada
    por_fase = {f["fase"]: f for f in datos["coinciden"]}
    assert por_fase["CAVERNAS"]["facturas"] == 2
    assert por_fase["CAVERNAS"]["cantidad"] == pytest.approx(12.0)
    assert por_fase["VIVIENDAS"]["facturas"] == 1
    assert datos["resumen"]["grupos"] == 2


def test_filtro_por_empresa_y_fase(tmp_path):
    catalogo = CATALOGO_CAVERNAS + [
        ("VMO", "CEDIS", 1, "1", "Producto Uno", 100.0),
    ]
    bd = _crear_bd(tmp_path / "est.db", catalogo, [
        ("M300000001", "DOMICEM", "CAVERNAS", DESC_150_CAVERNAS, 10.0, "3"),
        ("M300000002", "VMO", "CEDIS", "Producto Uno", 10.0, "1"),
    ])
    assert _revisar(bd)["resumen"]["facturas_revisadas"] == 2
    solo_vmo = _revisar(bd, empresa="VMO")
    assert solo_vmo["resumen"]["facturas_revisadas"] == 1
    assert solo_vmo["discrepan"] == []
    solo_cavernas = _revisar(bd, fase="CAVERNAS")
    assert solo_cavernas["resumen"]["facturas_revisadas"] == 1
    assert len(solo_cavernas["discrepan"]) == 1


def test_las_discrepancias_salen_ordenadas_por_plata_en_juego(tmp_path):
    catalogo = CATALOGO_CAVERNAS + [
        ("DOMICEM", "VIVIENDAS", 1, "2", "Concreto f'c=150 kg/cm2", 111.0),
        ("DOMICEM", "VIVIENDAS", 2, "3", "Concreto f'c=210 kg/cm2", 122.0),
    ]
    bd = _crear_bd(tmp_path / "est.db", catalogo, [
        # CAVERNAS: 100 m3 x $11 de diferencia = $1,100
        ("M300000001", "DOMICEM", "CAVERNAS", DESC_150_CAVERNAS, 100.0, "3"),
        # VIVIENDAS: 10 m3 x $11 = $110 (la descripcion del catalogo, resuelta a la otra clave)
        ("M300000002", "DOMICEM", "VIVIENDAS", "Concreto f'c=150 kg/cm2", 10.0, "3"),
    ])
    datos = _revisar(bd)
    assert [f["fase"] for f in datos["discrepan"]] == ["CAVERNAS", "VIVIENDAS"]
    assert datos["resumen"]["diferencia_total"] == pytest.approx(1210.0)


# ── Solo lectura, de verdad ──

def test_el_detector_no_escribe_nada_en_la_bd(bd_cavernas):
    """Corre sobre una conexion abierta en mode=ro: si intentara escribir,
    sqlite tira 'attempt to write a readonly database'."""
    antes = Path(bd_cavernas).read_bytes()
    datos = _revisar(bd_cavernas)
    assert datos["discrepan"]  # se corrio de verdad
    assert Path(bd_cavernas).read_bytes() == antes


# ── Endpoint ──

@pytest.fixture
def token_y_bd(bd_cavernas, monkeypatch):
    monkeypatch.setattr(core, "EST_DB_PATH", str(bd_cavernas))
    token = "test-token-claves-resueltas"
    core.active_tokens[token] = datetime.now()
    yield token
    core.active_tokens.pop(token, None)


def test_endpoint_exige_token(token_y_bd):
    res = TestClient(main.app).get("/api/estimaciones/claves-resueltas")
    assert res.status_code == 401


def test_endpoint_devuelve_los_tres_grupos_y_el_resumen(token_y_bd):
    res = TestClient(main.app).get("/api/estimaciones/claves-resueltas",
                                   headers={"Authorization": f"Bearer {token_y_bd}"})
    assert res.status_code == 200
    d = res.json()
    assert set(d) == {"discrepan", "sin_auto_match", "coinciden", "resumen"}
    assert d["resumen"]["facturas_discrepan"] == 56
    assert d["resumen"]["diferencia_total"] == pytest.approx(4070.0)
    assert d["discrepan"][0]["clave_auto"] == "2"


def test_endpoint_acepta_filtros(token_y_bd):
    client = TestClient(main.app)
    headers = {"Authorization": f"Bearer {token_y_bd}"}
    res = client.get("/api/estimaciones/claves-resueltas?empresa=VMO", headers=headers)
    assert res.status_code == 200
    assert res.json()["resumen"]["facturas_revisadas"] == 0


def test_endpoint_no_crea_la_bd_si_no_existe(tmp_path, monkeypatch):
    """Es un endpoint de aviso: nunca escribe, ni siquiera para bootstrapear la
    BD como hacen los demas. Sin BD responde 503, no la crea."""
    ruta = tmp_path / "no_existe.db"
    monkeypatch.setattr(core, "EST_DB_PATH", str(ruta))
    token = "test-token-claves-sin-bd"
    core.active_tokens[token] = datetime.now()
    try:
        res = TestClient(main.app).get("/api/estimaciones/claves-resueltas",
                                       headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 503
        assert not ruta.exists()
    finally:
        core.active_tokens.pop(token, None)
