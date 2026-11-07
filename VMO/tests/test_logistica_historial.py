"""
El historial de Logistica, por HTTP.

Van por la ruta y no contra las primitivas de core a proposito: es la leccion
del issue #31 —un campo que existe en core pero no viaja por la ruta no le
llega a nadie— y aca casi todo lo que puede fallar esta en el borde (el
aviso de reemplazo, los codigos de estado, que el dia vuelva completo).

Ninguna prueba toca la base real: `core.LOG_DB_PATH` se apunta a tmp_path.

El calculo del cumplimiento NO se prueba aca porque no esta aca: vive en
static/logistica.logic.js y lo cubren tests/logistica/.

Correr solo estas:  python -m pytest tests/test_logistica_historial.py -v
"""
import os
import sys
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import main  # noqa: E402


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    """TestClient con base aislada y un token valido."""
    monkeypatch.setattr(core, "LOG_DB_PATH", str(tmp_path / "logistica.db"))
    token = f"test-{uuid.uuid4().hex}"
    core.active_tokens[token] = datetime.now()
    yield TestClient(main.app), {"Authorization": f"Bearer {token}"}
    core.active_tokens.pop(token, None)


def dia(fecha="2026-09-29", **cambios):
    base = {
        "fecha": fecha, "cargue": 15, "calidad": 10, "tolerancia": 30,
        "toleranciaAdelanto": 60,
        "plantas": [{"planta": "Movil II", "trayecto": 30, "zona": "Santo Domingo"},
                    {"planta": "Planta Nueva", "trayecto": 25, "zona": None}],
        "programacion": [
            {"cliente": "ACME", "obra": "TORRE ALFA", "horaMin": 480, "cantidad": 10, "pedido": 4417},
            {"cliente": "BETA", "obra": "NAVE BETA", "horaMin": 540, "cantidad": 20, "pedido": 4418},
        ],
        "cargue_rows": [
            {"ficha": "F-1", "horaMin": 420, "cliente": "ACME", "obra": "TORRE ALFA",
             "planta": "Movil II", "cantidad": 7, "conduce": 98765},
            {"ficha": "F-2", "horaMin": 500, "cliente": "BETA", "obra": "NAVE BETA",
             "planta": "Movil II", "cantidad": 8, "conduce": 98766},
        ],
        "trayectoOverrides": {"ACME||TORRE ALFA": 45},
        "observaciones": {"ACME||TORRE ALFA": "salio tarde de planta"},
    }
    base.update(cambios)
    return base


def test_guardar_un_dia_y_verlo_en_el_historial(cliente):
    c, h = cliente
    res = c.post("/api/logistica/dias", json=dia(), headers=h)
    assert res.status_code == 200, res.text
    assert res.json() == {"fecha": "2026-09-29", "pedidos": 2, "cargues": 2, "reemplazado": False}

    filas = c.get("/api/logistica/dias", headers=h).json()["dias"]
    assert len(filas) == 1
    d = filas[0]
    assert d["fecha"] == "2026-09-29"
    assert (d["pedidos"], d["cargues"], d["m3"], d["clientes"], d["camiones"]) == (2, 2, 15.0, 2, 2)
    assert d["guardado_en"], "el listado tiene que decir cuando se guardo"


def test_el_listado_NO_trae_el_porcentaje_de_cumplimiento(cliente):
    """Es derivado del cruce, y el cruce vive en el JavaScript. Si alguna vez
    aparece en esta respuesta es que se reimplemento el calculo en Python, que
    es justo lo que el diseno de esta base evita."""
    c, h = cliente
    c.post("/api/logistica/dias", json=dia(), headers=h)
    d = c.get("/api/logistica/dias", headers=h).json()["dias"][0]
    assert not [k for k in d if "cumpl" in k.lower() or "pct" in k.lower()], d


def test_el_dia_vuelve_completo_y_en_orden(cliente):
    c, h = cliente
    c.post("/api/logistica/dias", json=dia(), headers=h)
    d = c.get("/api/logistica/dias/2026-09-29", headers=h).json()

    assert d["supuestos"]["cargue"] == 15
    assert d["supuestos"]["calidad"] == 10
    assert d["supuestos"]["tolerancia"] == 30
    assert d["supuestos"]["toleranciaAdelanto"] == 60
    assert d["supuestos"]["plantas"] == [
        {"planta": "Movil II", "trayecto": 30.0, "zona": "Santo Domingo"},
        {"planta": "Planta Nueva", "trayecto": 25.0, "zona": None},
    ], "una planta sin zona tiene que volver igual, no desaparecer"

    assert [p["cliente"] for p in d["programacion"]] == ["ACME", "BETA"]
    assert [r["ficha"] for r in d["cargue"]] == ["F-1", "F-2"]
    assert d["trayectoOverrides"] == {"ACME||TORRE ALFA": 45.0}
    assert d["observaciones"] == {"ACME||TORRE ALFA": "salio tarde de planta"}
    assert d["guardado_en"]


def test_las_columnas_que_solo_se_muestran_vuelven_como_texto(cliente):
    """`pedido` y `conduce` vienen numero un dia y texto al otro. Se guardan
    TEXT a proposito: para mostrarlos da igual, y asi no hay que adivinar."""
    c, h = cliente
    c.post("/api/logistica/dias", json=dia(), headers=h)
    d = c.get("/api/logistica/dias/2026-09-29", headers=h).json()
    assert d["programacion"][0]["pedido"] == "4417"
    assert d["cargue"][0]["conduce"] == "98765"
    assert d["cargue"][0]["cantidad"] == 7.0, "lo que entra a una cuenta sigue siendo numero"


def test_despachado_y_pendiente_sobreviven_el_viaje(cliente):
    """Los dos no son derivables de nada que se guarde, asi que si se caen en
    el camino se pierden: `pendiente` es lo unico que dice que un renglon
    quedo sin despachar sin deducirlo del cruce, y `despachado` es la cuota
    con la que repartirCamiones() parte los camiones entre las horas de una
    misma obra.

    Ya se cayeron una vez, y en cuatro lugares a la vez: no estaban en el
    modelo pydantic de la fila (que descarta en silencio lo que no declara),
    ni en la tabla, ni en el INSERT, ni en el SELECT. El dia 29-09-2026
    reabierto mostraba el panel de no despachado vacio, cuando su Excel tenia
    42 m3 pendientes en 2 renglones.

    El test de ida y vuelta en JS no podia verlo: payloadDelDia() y
    restaurarDia() pasan las filas tal cual, y la perdida estaba del lado del
    servidor. Por eso este va por HTTP."""
    c, h = cliente
    prog = [
        {"cliente": "ACME", "obra": "TORRE ALFA", "horaMin": 480, "cantidad": 35,
         "despachado": 28, "pendiente": 7},
        {"cliente": "BETA", "obra": "NAVE BETA", "horaMin": 540, "cantidad": 20,
         "despachado": 0, "pendiente": 20},
        # Sin las dos claves: es el caso "la planilla no trae la columna".
        {"cliente": "GAMMA", "obra": "GALPON", "horaMin": 600, "cantidad": 12},
    ]
    c.post("/api/logistica/dias", json=dia(programacion=prog), headers=h)
    vuelta = c.get("/api/logistica/dias/2026-09-29", headers=h).json()["programacion"]

    assert [(f["despachado"], f["pendiente"]) for f in vuelta] == [
        (28.0, 7.0),
        # 0 tiene que volver 0 y no None: "no se despacho nada" es un dato.
        (0.0, 20.0),
        # None y no 0: sin columna, repartirCamiones() cae a la cantidad
        # programada a proposito, y un 0 aca le daria cero camiones a la hora.
        (None, None),
    ]


def test_una_base_vieja_sin_esas_columnas_se_migra_sola(cliente, tmp_path):
    """CREATE TABLE IF NOT EXISTS no toca una tabla que ya existe, asi que sin
    la migracion el INSERT revienta en cualquier base guardada antes del
    arreglo — que son justamente las que tienen los dias reales."""
    import sqlite3
    conn = sqlite3.connect(core.LOG_DB_PATH)
    conn.executescript("""
        CREATE TABLE logistica_dia (
            fecha TEXT PRIMARY KEY, guardado_en TEXT NOT NULL,
            cargue_min REAL, calidad_min REAL, tolerancia_min REAL);
        CREATE TABLE logistica_programacion (
            fecha TEXT NOT NULL, orden INTEGER NOT NULL,
            cliente TEXT, obra TEXT, hora_min REAL, pedido TEXT, cantidad REAL,
            elemento TEXT, producto TEXT, prioridad TEXT, zona_hoja TEXT,
            PRIMARY KEY (fecha, orden));
    """)
    conn.commit()
    conn.close()

    c, h = cliente
    prog = [{"cliente": "ACME", "obra": "TORRE ALFA", "horaMin": 480,
             "cantidad": 35, "despachado": 28, "pendiente": 7}]
    res = c.post("/api/logistica/dias", json=dia(programacion=prog), headers=h)
    assert res.status_code == 200, res.text
    vuelta = c.get("/api/logistica/dias/2026-09-29", headers=h).json()["programacion"]
    assert (vuelta[0]["despachado"], vuelta[0]["pendiente"]) == (28.0, 7.0)


def test_un_dia_guardado_sin_tolerancia_de_adelanto_vuelve_en_None(cliente):
    """Los dias anteriores al 2026-10-02 no tienen ese supuesto, y la columna
    queda en NULL. Tiene que volver como None y NO como un numero inventado:
    el navegador distingue "este dia no tenia el supuesto" —y aplica su
    default— de "este dia decidio esto"."""
    c, h = cliente
    sin = dia()
    del sin["toleranciaAdelanto"]
    assert c.post("/api/logistica/dias", json=sin, headers=h).status_code == 200

    d = c.get("/api/logistica/dias/2026-09-29", headers=h).json()
    assert "toleranciaAdelanto" in d["supuestos"], "la clave viaja aunque sea None"
    assert d["supuestos"]["toleranciaAdelanto"] is None


def test_la_tolerancia_de_adelanto_sobrevive_la_vuelta_completa(cliente):
    """El campo nuevo pasa por cuatro lugares —modelo pydantic, tabla, INSERT y
    SELECT— y pydantic descarta en silencio lo que no declara. Asi se perdieron
    `despachado` y `pendiente` el 2026-10-01 sin que fallara nada, y por eso
    cada supuesto nuevo entra con su prueba de ida y vuelta."""
    c, h = cliente
    assert c.post("/api/logistica/dias", json=dia(toleranciaAdelanto=15),
                  headers=h).status_code == 200
    d = c.get("/api/logistica/dias/2026-09-29", headers=h).json()
    assert d["supuestos"]["toleranciaAdelanto"] == 15

    # Un 0 explicito es una configuracion legitima ("cualquier adelanto
    # incumple") y no puede confundirse con ausencia.
    c2 = c.post("/api/logistica/dias",
                json=dia(fecha="2026-09-30", toleranciaAdelanto=0), headers=h)
    assert c2.status_code == 200
    d2 = c.get("/api/logistica/dias/2026-09-30", headers=h).json()
    assert d2["supuestos"]["toleranciaAdelanto"] == 0


def test_reguardar_el_mismo_dia_avisa_y_NO_escribe(cliente):
    """El patron del aviso de re-cierre de Estimaciones. Existe porque guardar
    es DELETE + INSERT, y un DELETE + INSERT silencioso sobre algo que alguien
    ya reporto ya costo caro una vez en este proyecto."""
    c, h = cliente
    c.post("/api/logistica/dias", json=dia(), headers=h)
    antes = c.get("/api/logistica/dias/2026-09-29", headers=h).json()

    otro = dia(programacion=[{"cliente": "OTRO", "obra": "X", "horaMin": 600, "cantidad": 99}])
    res = c.post("/api/logistica/dias", json=otro, headers=h)

    assert res.status_code == 409
    aviso = res.json()["avisos"][0]
    assert aviso["tipo"] == "reemplazo"
    assert (aviso["fecha"], aviso["pedidos"], aviso["cargues"], aviso["m3"]) == \
           ("2026-09-29", 2, 2, 15.0)
    assert aviso["observaciones"] == 1
    assert aviso["guardado_en"], "el aviso tiene que decir de cuando es lo que se va a pisar"

    despues = c.get("/api/logistica/dias/2026-09-29", headers=h).json()
    assert despues == antes, "con 409 no se escribe NADA"


def test_confirmando_el_aviso_si_reemplaza(cliente):
    c, h = cliente
    c.post("/api/logistica/dias", json=dia(), headers=h)
    otro = dia(confirmar_aviso=True,
               programacion=[{"cliente": "OTRO", "obra": "X", "horaMin": 600, "cantidad": 99}],
               observaciones={})
    res = c.post("/api/logistica/dias", json=otro, headers=h)
    assert res.status_code == 200
    assert res.json()["reemplazado"] is True

    d = c.get("/api/logistica/dias/2026-09-29", headers=h).json()
    assert [p["cliente"] for p in d["programacion"]] == ["OTRO"]
    assert d["observaciones"] == {}, "reemplazar no deja colgando las observaciones viejas"
    assert len(c.get("/api/logistica/dias", headers=h).json()["dias"]) == 1, "sigue siendo UN dia"


def test_reemplazar_un_dia_no_toca_los_otros(cliente):
    c, h = cliente
    c.post("/api/logistica/dias", json=dia("2026-09-28"), headers=h)
    c.post("/api/logistica/dias", json=dia("2026-09-29"), headers=h)
    intacto = c.get("/api/logistica/dias/2026-09-28", headers=h).json()

    c.post("/api/logistica/dias", json=dia("2026-09-29", confirmar_aviso=True,
                                           observaciones={}), headers=h)
    assert c.get("/api/logistica/dias/2026-09-28", headers=h).json() == intacto


def test_los_dias_se_listan_del_mas_nuevo_al_mas_viejo(cliente):
    c, h = cliente
    for f in ("2026-09-28", "2026-09-30", "2026-09-29"):
        c.post("/api/logistica/dias", json=dia(f), headers=h)
    fechas = [d["fecha"] for d in c.get("/api/logistica/dias", headers=h).json()["dias"]]
    assert fechas == ["2026-09-30", "2026-09-29", "2026-09-28"]


def test_las_tres_rutas_piden_token(cliente):
    c, _ = cliente
    assert c.post("/api/logistica/dias", json=dia()).status_code == 401
    assert c.get("/api/logistica/dias").status_code == 401
    assert c.get("/api/logistica/dias/2026-09-29").status_code == 401


def test_un_dia_que_no_existe_da_404(cliente):
    c, h = cliente
    assert c.get("/api/logistica/dias/2020-01-01", headers=h).status_code == 404


def test_una_fecha_que_no_es_fecha_se_rechaza(cliente):
    """Sin esto, un 'ayer' o un '29/09/2026' entraria como clave primaria y el
    historial quedaria con dias que no se pueden ordenar."""
    c, h = cliente
    for mala in ("ayer", "29/09/2026", "2026-9-29", ""):
        assert c.post("/api/logistica/dias", json=dia(mala), headers=h).status_code == 422, mala


def test_un_dia_sin_ninguna_fila_no_se_guarda(cliente):
    c, h = cliente
    res = c.post("/api/logistica/dias",
                 json=dia(programacion=[], cargue_rows=[]), headers=h)
    assert res.status_code == 400
    assert res.json()["detail"] == "dia_vacio"


def test_hay_un_tope_de_filas_por_dia(cliente):
    """Tope de cordura: el lote real mas grande medido ronda las 2.000 filas.
    No es una restriccion de negocio, es que un POST equivocado no llene la
    base."""
    c, h = cliente
    fila = {"ficha": "F", "horaMin": 420, "cliente": "A", "obra": "B", "cantidad": 1}
    res = c.post("/api/logistica/dias",
                 json=dia(cargue_rows=[fila] * (core.LOG_MAX_FILAS + 1)), headers=h)
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "demasiadas_filas"


def test_la_base_se_crea_sola_en_un_checkout_limpio(cliente, tmp_path):
    """Mismo criterio que setup_est_db(): ninguna ruta puede exigir un paso
    manual previo. El directorio ni siquiera existe antes de la primera
    llamada."""
    c, h = cliente
    assert not os.path.exists(core.LOG_DB_PATH)
    assert c.get("/api/logistica/dias", headers=h).status_code == 200
    assert os.path.exists(core.LOG_DB_PATH)


def test_bomba_vendedor_y_zona_sobreviven_el_viaje(cliente):
    """2026-10-06: los tres entran por los cuatro lugares a la vez — modelo,
    columna, INSERT y SELECT. Si falta uno, pydantic o el SQL los tiran en
    silencio y el dia reabierto los muestra vacios."""
    c, h = cliente
    prog = [{"cliente": "ACME", "obra": "TORRE ALFA", "horaMin": 480, "cantidad": 35,
             "bomba": "45", "vendedor": "Ana", "zonaProg": "Bavaro"},
            {"cliente": "BETA", "obra": "NAVE", "horaMin": 540, "cantidad": 7,
             "bomba": "Directo"}]
    assert c.post("/api/logistica/dias", json=dia(programacion=prog), headers=h).status_code == 200
    vuelta = c.get("/api/logistica/dias/2026-09-29", headers=h).json()["programacion"]
    assert [(f["bomba"], f["vendedor"], f["zonaProg"]) for f in vuelta] == [
        ("45", "Ana", "Bavaro"), ("Directo", None, None)]


def test_una_base_sin_las_columnas_de_bomba_se_migra_sola(cliente):
    import sqlite3
    conn = sqlite3.connect(core.LOG_DB_PATH)
    conn.executescript("""
        CREATE TABLE logistica_dia (
            fecha TEXT PRIMARY KEY, guardado_en TEXT NOT NULL,
            cargue_min REAL, calidad_min REAL, tolerancia_min REAL);
        CREATE TABLE logistica_programacion (
            fecha TEXT NOT NULL, orden INTEGER NOT NULL,
            cliente TEXT, obra TEXT, hora_min REAL, pedido TEXT, cantidad REAL,
            elemento TEXT, producto TEXT, prioridad TEXT, zona_hoja TEXT,
            despachado REAL, pendiente REAL,
            PRIMARY KEY (fecha, orden));
    """)
    conn.commit()
    conn.close()
    c, h = cliente
    prog = [{"cliente": "ACME", "obra": "X", "horaMin": 480, "cantidad": 7, "bomba": "45"}]
    assert c.post("/api/logistica/dias", json=dia(programacion=prog), headers=h).status_code == 200
    vuelta = c.get("/api/logistica/dias/2026-09-29", headers=h).json()["programacion"]
    assert vuelta[0]["bomba"] == "45"


def test_responsable_y_espaciamiento_sobreviven_el_viaje(cliente):
    """2026-10-06: el responsable por fila y el espaciamiento maximo entran por
    los cuatro lugares (modelo, tabla/columna, INSERT, SELECT)."""
    c, h = cliente
    res = c.post("/api/logistica/dias", headers=h, json=dia(
        espaciamiento=45, responsables={"ACME||TORRE ALFA||DIRECTO||||480": "VMO",
                                        "BETA||NAVE BETA||DIRECTO||||540": "Externo"}))
    assert res.status_code == 200, res.text
    d = c.get("/api/logistica/dias/2026-09-29", headers=h).json()
    assert d["supuestos"]["espaciamiento"] == 45
    assert d["responsables"] == {"ACME||TORRE ALFA||DIRECTO||||480": "VMO",
                                 "BETA||NAVE BETA||DIRECTO||||540": "Externo"}


def test_un_responsable_fuera_de_la_lista_se_rechaza_sin_escribir(cliente):
    c, h = cliente
    res = c.post("/api/logistica/dias", headers=h, json=dia(responsables={"K": "Nadie"}))
    assert res.status_code == 422
    assert c.get("/api/logistica/dias/2026-09-29", headers=h).status_code == 404


def test_un_dia_sin_espaciamiento_vuelve_en_None(cliente):
    c, h = cliente
    base = dia()
    base.pop("espaciamiento", None)
    assert c.post("/api/logistica/dias", headers=h, json=base).status_code == 200
    d = c.get("/api/logistica/dias/2026-09-29", headers=h).json()
    assert d["supuestos"]["espaciamiento"] is None
    assert d["responsables"] == {}


def test_el_motivo_sobrevive_el_viaje(cliente):
    c, h = cliente
    res = c.post("/api/logistica/dias", headers=h, json=dia(
        motivos={"ACME||TORRE ALFA||DIRECTO||||480": "AVERIA DE BOMBA"}))
    assert res.status_code == 200, res.text
    d = c.get("/api/logistica/dias/2026-09-29", headers=h).json()
    assert d["motivos"] == {"ACME||TORRE ALFA||DIRECTO||||480": "AVERIA DE BOMBA"}


def test_el_cumplido_manual_sobrevive_el_viaje(cliente):
    """2026-10-26: las incumplidas pasadas a cumplido a mano vuelven al abrir
    el dia, y un dia guardado sin ninguna trae la lista vacia."""
    c, h = cliente
    k = "ACME||TORRE ALFA||40||ESCALERA||480"
    res = c.post("/api/logistica/dias", headers=h, json=dia(
        motivos={k: "PRIORIDAD OTRO ELEMENTO"}, cumplidosManuales=[k]))
    assert res.status_code == 200, res.text
    d = c.get("/api/logistica/dias/2026-09-29", headers=h).json()
    assert d["cumplidosManuales"] == [k]
    res = c.post("/api/logistica/dias", headers=h, json=dia(confirmar_aviso=True))
    assert res.status_code == 200, res.text
    assert c.get("/api/logistica/dias/2026-09-29", headers=h).json()["cumplidosManuales"] == []


def test_un_motivo_fuera_de_la_lista_se_rechaza_sin_escribir(cliente):
    c, h = cliente
    res = c.post("/api/logistica/dias", headers=h, json=dia(motivos={"K": "LLOVIO"}))
    assert res.status_code == 422
    assert res.json()["detail"]["detalle"] == ["LLOVIO"]
    assert c.get("/api/logistica/dias/2026-09-29", headers=h).status_code == 404


def test_la_lista_de_motivos_es_la_misma_en_el_navegador_y_en_el_backend():
    """Viven en dos idiomas (MOTIVOS en logistica.logic.js, LOG_MOTIVOS en la
    ruta). Si alguien agrega un motivo en uno solo, el navegador lo ofrece y
    el backend lo rechaza al guardar — o al reves. Este test lo ataja."""
    import os
    import re
    import routes_logistica
    ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "static", "logistica.logic.js")
    js = open(ruta, encoding="utf-8").read()
    bloque = re.search(r"const MOTIVOS = \[(.*?)\];", js, re.S).group(1)
    assert tuple(re.findall(r"'([^']+)'", bloque)) == routes_logistica.LOG_MOTIVOS


# ── Borrar un dia (2026-10-12) ──────────────────────────────────────────────

def test_borrar_un_dia_lo_saca_del_historial_y_deja_los_otros(cliente):
    c, h = cliente
    c.post("/api/logistica/dias", json=dia(), headers=h)
    c.post("/api/logistica/dias", json=dia(fecha="2026-09-30"), headers=h)
    res = c.delete("/api/logistica/dias/2026-09-29", headers=h)
    assert res.status_code == 200, res.text
    assert res.json()["fecha"] == "2026-09-29"
    assert [d["fecha"] for d in c.get("/api/logistica/dias", headers=h).json()["dias"]] == ["2026-09-30"]
    assert c.get("/api/logistica/dias/2026-09-29", headers=h).status_code == 404
    # Las tablas hijas se fueron con el dia, no quedaron huerfanas.
    conn = core._log_conn()
    try:
        for tabla in ("logistica_programacion", "logistica_cargue", "logistica_observacion",
                      "logistica_trayecto_override", "logistica_dia_planta"):
            n = conn.execute(f"SELECT COUNT(*) FROM {tabla} WHERE fecha = '2026-09-29'").fetchone()[0]
            assert n == 0, tabla
    finally:
        conn.close()


def test_antes_de_borrar_queda_una_copia_completa_del_dia(cliente):
    """Lo cargado a mano —observaciones, motivos, responsables— no esta en
    ningun Excel: si se borra por error, la copia es lo unico que queda."""
    c, h = cliente
    c.post("/api/logistica/dias", json=dia(responsables={"ACME||TORRE ALFA": "VMO"},
                                            motivos={"ACME||TORRE ALFA": "AVERIA DE BOMBA"}), headers=h)
    respaldo = c.delete("/api/logistica/dias/2026-09-29", headers=h).json()["respaldo"]
    ruta = os.path.join(os.path.dirname(core.LOG_DB_PATH), "borrados", respaldo)
    import json
    copia = json.load(open(ruta, encoding="utf-8"))
    assert copia["fecha"] == "2026-09-29"
    assert copia["observaciones"] == {"ACME||TORRE ALFA": "salio tarde de planta"}
    assert copia["responsables"] == {"ACME||TORRE ALFA": "VMO"}
    assert copia["motivos"] == {"ACME||TORRE ALFA": "AVERIA DE BOMBA"}
    assert len(copia["programacion"]) == 2 and len(copia["cargue"]) == 2


def test_borrar_pide_sesion_y_un_dia_que_exista(cliente):
    c, h = cliente
    c.post("/api/logistica/dias", json=dia(), headers=h)
    assert c.delete("/api/logistica/dias/2026-09-29").status_code == 401
    assert c.delete("/api/logistica/dias/2026-01-01", headers=h).status_code == 404
    assert c.delete("/api/logistica/dias/29-09-2026", headers=h).status_code == 422
    assert len(c.get("/api/logistica/dias", headers=h).json()["dias"]) == 1, "no se borro nada"
