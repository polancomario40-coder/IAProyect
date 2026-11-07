"""
Cubre la logica de validacion que esta un nivel arriba de las plantillas
Excel — hallazgo del audit de cobertura corrido antes de /ship 2026-08-20:
`_est_plantilla_de_fase()` y el orden de validacion de `estimaciones_generar`
(campos_faltantes / facturas_sin_resolver / reasignaciones) no tenian ningun
test directo, solo se probaban indirectamente contra el estado real de la
BD/plantillas en disco.

Correr con: python -m pytest tests/test_estimaciones_validacion.py -v
"""
import asyncio
import io
import os
import shutil
import sqlite3
import sys
import zipfile
from datetime import datetime

import openpyxl
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
import main  # noqa: E402 (solo para main.app — TestClient necesita la app con los routers ya incluidos)
from scripts import seed_acumulado_base_macao2  # noqa: E402
from scripts import seed_contrato_principal_macao2  # noqa: E402
from scripts import seed_acumulado_base_fases  # noqa: E402


# ── Issue #15 — helpers compartidos para el Excel de conduces (lookup) ──

EXCEL_LOOKUP_HEADERS = ["Conduce", "Fecha", "Cliente", "Producto", "Cant.", "Planta", "Codigo"]


def _construir_excel_bytes(filas, headers=None):
    """Construye un .xlsx en memoria con el mismo formato que
    `archivos/CONDUCES 18-08-2026.xlsx` (Conduce/Fecha/Cliente/Producto/
    Cant./Planta/Codigo) — nunca el Excel real de produccion. `filas` es una
    lista de tuplas de 7 elementos en ese orden."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "COnduces"
    ws.append(headers or EXCEL_LOOKUP_HEADERS)
    for fila in filas:
        ws.append(list(fila))
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


# ── _est_plantilla_de_fase() — las ramas de error ──

def _catalogo_contiguo(n):
    """Catalogo sintetico con orden contiguo 1..n — suficiente para los
    tests que no les importa el contenido real de cada producto."""
    return [{"orden": i, "clave": str(i), "descripcion": f"P{i}", "precio_unitario": 1.0}
            for i in range(1, n + 1)]


def test_plantilla_no_registrada():
    with pytest.raises(HTTPException) as exc:
        core._est_plantilla_de_fase("EMPRESA_QUE_NO_EXISTE", "FASE_QUE_NO_EXISTE", _catalogo_contiguo(1))
    assert exc.value.status_code == 500
    assert exc.value.detail["error"] == "plantilla_no_encontrada"


def test_plantilla_registrada_pero_archivo_faltante(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "EST_DATA_DIR", str(tmp_path))  # directorio vacio a proposito
    with pytest.raises(HTTPException) as exc:
        core._est_plantilla_de_fase("VMO", "CEDIS", _catalogo_contiguo(1))
    assert exc.value.status_code == 500
    assert exc.value.detail["error"] == "plantilla_no_encontrada"


def test_catalogo_excede_capacidad_de_la_plantilla():
    capacidad = core.EST_PLANTILLAS[("VMO", "CEDIS")]["capacidad"]
    with pytest.raises(HTTPException) as exc:
        core._est_plantilla_de_fase("VMO", "CEDIS", _catalogo_contiguo(capacidad + 1))
    assert exc.value.status_code == 422
    assert exc.value.detail["error"] == "catalogo_desincronizado"


def test_catalogo_dentro_de_capacidad_no_lanza():
    capacidad = core.EST_PLANTILLAS[("VMO", "CEDIS")]["capacidad"]
    ruta = core._est_plantilla_de_fase("VMO", "CEDIS", _catalogo_contiguo(capacidad))  # no debe lanzar
    assert ruta.endswith(core.EST_PLANTILLAS[("VMO", "CEDIS")]["archivo"])


def test_catalogo_con_hueco_en_orden_lanza_desincronizado():
    # orden 1, 2, 4 — hueco en el 3, mismo total que _catalogo_contiguo(3)
    catalogo = [
        {"orden": 1, "clave": "1", "descripcion": "P1", "precio_unitario": 1.0},
        {"orden": 2, "clave": "2", "descripcion": "P2", "precio_unitario": 1.0},
        {"orden": 4, "clave": "4", "descripcion": "P4", "precio_unitario": 1.0},
    ]
    with pytest.raises(HTTPException) as exc:
        core._est_plantilla_de_fase("VMO", "CEDIS", catalogo)
    assert exc.value.status_code == 422
    assert exc.value.detail["error"] == "catalogo_desincronizado"


# ── _est_oc_contrato() — issue #9, OC/Contrato fijo por fase ──

def test_est_oc_contrato_devuelve_el_valor_correcto_para_las_9_fases():
    esperado = {
        ("DOMICEM", "CAVERNAS"): "4800029676",
        ("DOMICEM", "MACAO 2"): "4800029677",
        ("DOMICEM", "PATIO DE MANIOBRAS-TRB"): "4800032854",
        ("DOMICEM", "VIVIENDAS"): "PPACT",
        ("VMO", "CANCHAS"): "4800037426",
        ("VMO", "CEDIS"): "4800036588",
        ("VMO", "PATIO DE MANIOBRAS-TRA"): "4800025583",
        ("VMO", "PODIUM-1-2-3"): "PPACT",
        ("VMO", "EXTERIORES"): "PPACT",
    }
    for (empresa, fase), valor in esperado.items():
        assert core._est_oc_contrato(empresa, fase) == valor


def test_est_oc_contrato_combinacion_inexistente_lanza_500():
    with pytest.raises(HTTPException) as exc:
        core._est_oc_contrato("EMPRESA_QUE_NO_EXISTE", "FASE_QUE_NO_EXISTE")
    assert exc.value.status_code == 500
    assert exc.value.detail["error"] == "oc_contrato_no_definido"


# ── estimaciones_generar — orden de validacion, con una BD sintetica ──

@pytest.fixture
def bd_sintetica(tmp_path, monkeypatch):
    """BD sqlite minima con 2 productos de catalogo y facturas de prueba —
    aisla estos tests de los datos reales de produccion."""
    db_path = tmp_path / "estimaciones_test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE catalogo_estimacion (
        empresa TEXT, fase TEXT, orden INTEGER, clave TEXT,
        descripcion TEXT, precio_unitario REAL,
        PRIMARY KEY (empresa, fase, orden)
    )""")
    conn.execute("""CREATE TABLE facturas (
        id_documento TEXT PRIMARY KEY, fecha DATE, empresa TEXT, fase TEXT,
        descripcion TEXT, cantidad REAL, precio_unitario REAL, clave_resuelta TEXT
    )""")
    conn.execute("""CREATE TABLE estimacion_acumulado_base (
        empresa TEXT, fase TEXT, clave TEXT,
        serie TEXT NOT NULL CHECK (serie IN ('principal','ppact')),
        fecha_base DATE, cantidad_base REAL, cantidad_proyecto_principal REAL,
        PRIMARY KEY (empresa, fase, clave, serie)
    )""")
    conn.execute(
        "INSERT INTO catalogo_estimacion VALUES ('VMO','CEDIS',1,'1','Producto Uno',100.0)"
    )
    conn.execute(
        "INSERT INTO catalogo_estimacion VALUES ('VMO','CEDIS',2,'2','Producto Dos',200.0)"
    )
    conn.execute(
        "INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,cantidad,precio_unitario) "
        "VALUES ('F001','2026-06-01','VMO','CEDIS','Producto Uno',10,100.0)"
    )
    conn.execute(
        "INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,cantidad,precio_unitario) "
        "VALUES ('F002','2026-06-02','VMO','CEDIS','Descripcion Rara Sin Match',5,50.0)"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))

    token = "test-token-estimaciones"
    core.active_tokens[token] = datetime.now()
    yield token
    core.active_tokens.pop(token, None)


def _payload_base(token, **overrides):
    body = {
        "empresa": "VMO", "fase": "CEDIS",
        "fecha_desde": "2026-06-01", "fecha_hasta": "2026-06-30",
        "numero_estimacion": "N01",
        "fecha_estimacion": "2026-08-20", "semana": 1,
        "productos": [
            {"clave": "1", "cantidad_proyecto": 100, "acumulado_anterior_cantidad": 0},
            {"clave": "2", "cantidad_proyecto": 100, "acumulado_anterior_cantidad": 0},
        ],
        "reasignaciones": {},
        "serie": "principal",
    }
    body.update(overrides)
    return body


def test_campos_faltantes_si_falta_un_producto_del_catalogo(bd_sintetica):
    client = TestClient(main.app)
    payload = _payload_base(bd_sintetica)
    payload["productos"] = [payload["productos"][0]]  # falta la clave "2"
    res = client.post(
        "/api/estimaciones/generar", json=payload,
        headers={"Authorization": f"Bearer {bd_sintetica}"},
    )
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "campos_faltantes"
    assert "2" in res.json()["detail"]["detalle"]


def test_facturas_sin_resolver_si_no_hay_reasignacion(bd_sintetica):
    client = TestClient(main.app)
    payload = _payload_base(bd_sintetica)  # F002 no matchea ningun producto y no hay reasignacion
    res = client.post(
        "/api/estimaciones/generar", json=payload,
        headers={"Authorization": f"Bearer {bd_sintetica}"},
    )
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "facturas_sin_resolver"
    assert "Descripcion Rara Sin Match" in res.json()["detail"]["detalle"]


def test_periodo_sin_facturas_da_error_no_excel_vacio(bd_sintetica):
    client = TestClient(main.app)
    payload = _payload_base(bd_sintetica, fecha_desde="2020-01-01", fecha_hasta="2020-01-31")
    res = client.post(
        "/api/estimaciones/generar", json=payload,
        headers={"Authorization": f"Bearer {bd_sintetica}"},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "sin_facturas_en_periodo"


def test_reasignacion_resuelve_la_factura_sin_match(bd_sintetica, tmp_path, monkeypatch):
    # EST_REPORTES_DIR aislado a tmp_path — este endpoint SI genera un
    # archivo real (no solo lee/valida como los demas tests de este
    # archivo). Mismo patron de riesgo que ya causo perdida de datos real
    # en tests/test_conduces.py (ver CLAUDE.md 2026-08-21): sin aislar el
    # directorio de salida, un fallo del test antes de la linea de limpieza
    # dejaba el .xlsx de prueba en la carpeta real del proyecto.
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    client = TestClient(main.app)
    payload = _payload_base(
        bd_sintetica,
        reasignaciones={"Descripcion Rara Sin Match": "2"},
    )
    res = client.post(
        "/api/estimaciones/generar", json=payload,
        headers={"Authorization": f"Bearer {bd_sintetica}"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total_facturas"] == 2  # F001 (match directo) + F002 (reasignada)
    assert data["productos_con_entregas"] == 2


# ── Hijo 6(a) — fase no reconocida va a pendientes_revision, no VMO a ciegas ──

def test_normalizar_fase_reconoce_las_3_fases_vmo_nuevas():
    assert core._normalizar_fase("Obra: Campo de Golf") == "CAMPO DE GOLF"
    assert core._normalizar_fase("PUENTES DE MANGLAR - tramo 2") == "PUENTES DE MANGLAR"
    assert core._normalizar_fase("Salon Ballroom Norte") == "BALLROOM"
    assert "CAMPO DE GOLF" in core.FASES_VMO
    assert "PUENTES DE MANGLAR" in core.FASES_VMO
    assert "BALLROOM" in core.FASES_VMO


def test_normalizar_fase_desconocida_devuelve_none():
    assert core._normalizar_fase("OBRA INVENTADA QUE NO EXISTE") is None
    assert core._normalizar_fase("") is None


def test_normalizar_fase_tolera_macao_11_leido_por_vision():
    """Vision confunde los numeros romanos "II" con dos unos. Caso real:
    M800012439 (2026-08-26) llego con cliente "(MACAO 11, ESTRUCTURA)" y obra
    "MALESPIN MACAO 11", y quedo bloqueado como "fase no reconocida" siendo un
    documento valido de MACAO 2. No existe ninguna fase llamada "MACAO 11"."""
    assert core._normalizar_fase("MACAO ALTO RESORT S.R.L., (MACAO 11, ESTRUCTURA)") == "MACAO 2"
    assert core._normalizar_fase("MALESPIN MACAO 11") == "MACAO 2"
    # Las variantes que ya funcionaban siguen igual.
    assert core._normalizar_fase("MACAO ALTO RESORT S.R.L, (MACAO II, ESTRUCTURA)") == "MACAO 2"
    assert core._normalizar_fase("CIMENTACIONES MACAO II") == "MACAO 2"


def _lookup_con_fila(nombre_archivo, id_documento, descripcion, cliente):
    """Lookup minimo (1 sola fila) para tests que no les importa el resto del
    Excel — misma forma que devuelve cargar_lookup_excel()."""
    fila = {"id_documento": id_documento, "descripcion": descripcion, "cliente": cliente}
    return {
        "por_archivo": {core._excel_norm_archivo(nombre_archivo): fila},
        "por_id": {core._excel_norm_id(id_documento): fila},
        "conflictos": {},
        "filas": 1,
    }


def _lookup_vacio():
    return {"por_archivo": {}, "por_id": {}, "conflictos": {}, "filas": 0}


def _enriquecer_para_probar_fase(cliente_excel, obra_vision, con_fila=True):
    # Issue #15: la fase sale EXCLUSIVAMENTE del Cliente del Excel (lookup) —
    # cliente/obra que devuelve Vision ya no participan en la decision de
    # fase en absoluto (ni siquiera como respaldo). `obra_vision` se pasa
    # igual a `datos["obra"]` para probar justamente que se ignora.
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE precios_vmo (descripcion TEXT, fase TEXT, precio_unitario REAL)")
    conn.execute("CREATE TABLE precios_domicem (descripcion TEXT, fase TEXT, precio_unitario REAL)")
    nombre_base = "07-24-M8-14137.pdf"
    info = {"fecha": "2026-07-24", "planta": "M8", "id_documento": "M800014137"}
    datos = {
        "cliente": "CLIENTE QUE LEYO VISION (siempre irrelevante para la fase)",
        "obra": obra_vision, "descripcion": "Concreto", "cantidad": 10,
    }
    lookup = (
        _lookup_con_fila(nombre_base, info["id_documento"], "Concreto", cliente_excel)
        if con_fila else _lookup_vacio()
    )
    resultado = core._enriquecer_y_matchear(conn, datos, info, nombre_base, lookup)
    conn.close()
    return resultado


def test_enriquecer_saca_fase_del_cliente_del_excel_no_de_vision():
    # obra_vision="CEDIS" matchearia CEDIS si todavia se usara de respaldo —
    # el Cliente del Excel (CANCHAS) es el que manda.
    resultado = _enriquecer_para_probar_fase("MACAO ALTO RESORT S.R.L  CANCHAS", "CEDIS")
    assert resultado["fase"] == "CANCHAS"
    assert resultado["empresa"] == "VMO"


def test_enriquecer_no_cae_a_obra_de_vision_si_cliente_excel_no_matchea():
    # Issue #15: sin respaldo a obra/cliente de Vision cuando SI hay fila en
    # el Excel pero su Cliente no matchea ninguna fase conocida — antes de
    # este issue esto habria caido a "OBRA CEDIS" y clasificado VMO/CEDIS.
    resultado = _enriquecer_para_probar_fase("CLIENTE DEL EXCEL ILEGIBLE", "OBRA CEDIS")
    assert resultado["fase"] is None
    assert resultado["empresa"] is None


def test_enriquecer_deja_fase_y_empresa_none_si_ningun_campo_matchea():
    resultado = _enriquecer_para_probar_fase("CLIENTE ILEGIBLE", "PARMOL")
    assert resultado["fase"] is None
    assert resultado["empresa"] is None


def test_enriquecer_caso_real_m800014137_clasifica_macao2_domicem():
    # Mismo caso real que motivo el fix de "fase desde cliente" — ahora el
    # cliente viene del Excel, no de Vision, y obra="PARMOL" (lo que leyo
    # Vision en ese documento real) se ignora por completo.
    resultado = _enriquecer_para_probar_fase(
        "MACAO ALTO RESORT S.R.L. (MACAO II. ESTRUCTURA)", "PARMOL"
    )
    assert resultado["fase"] == "MACAO 2"
    assert resultado["empresa"] == "DOMICEM"


def test_enriquecer_caso_real_macao_11_clasifica_macao2():
    # Caso real M800012439 (2026-08-26): Vision leyo "MACAO 11" (numeros
    # romanos II mal leidos) — ahora la fase ni siquiera pasa por Vision, y
    # si el Cliente del Excel trae la variante "MACAO 11" igual se reconoce.
    resultado = _enriquecer_para_probar_fase(
        "MACAO ALTO RESORT S.R.L., (MACAO 11, ESTRUCTURA)", "MALESPIN MACAO 11"
    )
    assert resultado["fase"] == "MACAO 2"
    assert resultado["empresa"] == "DOMICEM"


def test_enriquecer_acceptance_7_vision_lee_macao_11_excel_dice_macao_2_correcto():
    # Acceptance criterion #7, literal: el Cliente del EXCEL dice
    # "MACAO ALTO RESORT S.R.L., (MACAO II, ESTRUCTURA)" (correcto) mientras
    # que Vision leyo "MACAO 11" tanto en cliente como en obra — el
    # documento se clasifica MACAO 2 de todas formas, porque cliente/obra de
    # Vision no participan en absoluto en la decision de fase.
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE precios_vmo (descripcion TEXT, fase TEXT, precio_unitario REAL)")
    conn.execute("CREATE TABLE precios_domicem (descripcion TEXT, fase TEXT, precio_unitario REAL)")
    nombre_base = "08-26-M8-00012439.pdf"
    info = {"fecha": "2026-08-26", "planta": "M8", "id_documento": "M800012439"}
    datos = {
        "cliente": "MACAO ALTO RESORT S.R.L., (MACAO 11, ESTRUCTURA)",  # error real de Vision
        "obra": "MALESPIN MACAO 11",                                    # error real de Vision
        "descripcion": "Concreto", "cantidad": 5,
    }
    lookup = _lookup_con_fila(
        nombre_base, info["id_documento"], "Concreto",
        "MACAO ALTO RESORT S.R.L., (MACAO II, ESTRUCTURA)",  # correcto, del Excel
    )
    resultado = core._enriquecer_y_matchear(conn, datos, info, nombre_base, lookup)
    conn.close()
    assert resultado["fase"] == "MACAO 2"
    assert resultado["empresa"] == "DOMICEM"


def test_enriquecer_y_matchear_sin_fila_excel_deja_fase_none(tmp_path):
    db_path = tmp_path / "est.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE precios_vmo (descripcion TEXT, fase TEXT, precio_unitario REAL)")
    conn.execute("CREATE TABLE precios_domicem (descripcion TEXT, fase TEXT, precio_unitario REAL)")
    datos = {"obra": "OBRA INVENTADA QUE NO EXISTE", "descripcion": "Concreto", "cantidad": 10}
    info = {"fecha": "2026-06-01", "planta": "M1", "id_documento": "M100000001"}
    resultado = core._enriquecer_y_matchear(conn, datos, info, "archivo.pdf", _lookup_vacio())
    conn.close()
    assert resultado["empresa"] is None
    assert resultado["fase"] is None
    assert resultado["precio_unitario"] is None  # nunca intenta matchear precio sin empresa
    assert resultado["_sin_fila_excel"] is True
    assert resultado["_motivo_excel"] == "sin fila en el Excel"


def test_enriquecer_descripcion_siempre_viene_del_excel():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE precios_vmo (descripcion TEXT, fase TEXT, precio_unitario REAL)")
    conn.execute("CREATE TABLE precios_domicem (descripcion TEXT, fase TEXT, precio_unitario REAL)")
    nombre_base = "06-01-M1-00000001.pdf"
    info = {"fecha": "2026-06-01", "planta": "M1", "id_documento": "M100000001"}
    datos = {"cliente": "x", "obra": "CEDIS", "descripcion": "AM0. IIIA (OCR sucio)", "cantidad": 10}
    lookup = _lookup_con_fila(nombre_base, info["id_documento"], "Hormigon 350kg/cm2", "MACAO ALTO RESORT S.R.L CANCHAS")
    resultado = core._enriquecer_y_matchear(conn, datos, info, nombre_base, lookup)
    conn.close()
    assert resultado["descripcion"] == "Hormigon 350kg/cm2"
    assert resultado["_correccion_excel"] == {
        "campo": "descripcion", "vision": "AM0. IIIA (OCR sucio)", "excel": "Hormigon 350kg/cm2",
    }


def test_enriquecer_no_marca_correccion_si_descripcion_coincide():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE precios_vmo (descripcion TEXT, fase TEXT, precio_unitario REAL)")
    conn.execute("CREATE TABLE precios_domicem (descripcion TEXT, fase TEXT, precio_unitario REAL)")
    nombre_base = "06-01-M1-00000002.pdf"
    info = {"fecha": "2026-06-01", "planta": "M1", "id_documento": "M100000002"}
    datos = {"cliente": "x", "obra": "CEDIS", "descripcion": "Hormigon 350kg/cm2", "cantidad": 10}
    lookup = _lookup_con_fila(nombre_base, info["id_documento"], "Hormigon 350kg/cm2", "MACAO ALTO RESORT S.R.L CANCHAS")
    resultado = core._enriquecer_y_matchear(conn, datos, info, nombre_base, lookup)
    conn.close()
    assert "_correccion_excel" not in resultado


def test_enriquecer_indices_contradictorios_bloquea_documento():
    # por_archivo y por_id apuntan a filas DISTINTAS para el mismo documento
    # (mismo escenario que produce _resolver_fila_excel al detectar
    # contradiccion) — el documento queda bloqueado, ninguna de las 2 filas
    # se usa en silencio.
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE precios_vmo (descripcion TEXT, fase TEXT, precio_unitario REAL)")
    conn.execute("CREATE TABLE precios_domicem (descripcion TEXT, fase TEXT, precio_unitario REAL)")
    nombre_base = "06-01-M1-00000003.pdf"
    info = {"fecha": "2026-06-01", "planta": "M1", "id_documento": "M100000003"}
    fila_por_archivo = {"id_documento": "M100000003", "descripcion": "Producto A", "cliente": "CANCHAS"}
    fila_por_id       = {"id_documento": "M100000003", "descripcion": "Producto B", "cliente": "CEDIS"}
    lookup = {
        "por_archivo": {core._excel_norm_archivo(nombre_base): fila_por_archivo},
        "por_id": {core._excel_norm_id("M100000003"): fila_por_id},
        "conflictos": {}, "filas": 2,
    }
    datos = {"cliente": "x", "obra": "y", "descripcion": "lo que sea", "cantidad": 1}
    resultado = core._enriquecer_y_matchear(conn, datos, info, nombre_base, lookup)
    conn.close()
    assert resultado["fase"] is None
    assert resultado["empresa"] is None
    assert resultado["_sin_fila_excel"] is True
    assert resultado["_motivo_excel"] == "el Excel se contradice para este documento"


def test_motivo_sello_firma_prioriza_fase_no_reconocida():
    # fase no reconocida Y sin sello — un solo motivo, el de fase primero
    datos = {"fase": None, "tiene_sello": False, "tiene_firma": False}
    assert core._motivo_sello_firma(datos) == "fase no reconocida"


def test_motivo_sello_firma_normal_cuando_fase_reconocida():
    # fase MACAO 2 -> regla de sello (issue #7/#8). Un "CEDIS" real ya usa la
    # regla de firma (issue #8) — cubierto en los tests de mas abajo.
    datos = {"fase": "MACAO 2", "tiene_sello": False, "tiene_firma": True}
    assert core._motivo_sello_firma(datos) == "falta sello"
    datos_ok = {"fase": "MACAO 2", "tiene_sello": True, "tiene_firma": True}
    assert core._motivo_sello_firma(datos_ok) is None


# ── Hijo 6(c) — _confirmar_registros: rowcount real + PDF antes del INSERT ──

def _crear_tabla_facturas(conn):
    # Espejo del esquema real — las 5 columnas de aprobacion manual (issue
    # #20), obra_papel (issue #67) y obra_familia (issue #72) entran en
    # produccion por la migracion de setup_est_db(), y _est_insertar_factura()
    # las escribe siempre, asi que el fixture las necesita aunque estos tests
    # no las usen.
    conn.execute("""CREATE TABLE facturas (
        id_documento TEXT PRIMARY KEY, fecha DATE, planta TEXT, orden_compra TEXT,
        referencia TEXT, distancia TEXT, cliente TEXT, obra TEXT, obra_papel TEXT,
        obra_familia TEXT, bomba TEXT,
        id_producto TEXT, descripcion TEXT, cantidad REAL, precio_unitario REAL,
        total REAL, ficha TEXT, chofer TEXT, hora_salida TEXT, observaciones TEXT,
        archivo_pdf TEXT, empresa TEXT, fase TEXT, sin_firma INTEGER DEFAULT 0,
        fecha_importacion DATETIME, aprobado_manual INTEGER DEFAULT 0,
        aprobado_por TEXT, aprobado_motivo TEXT, aprobado_fecha TEXT,
        motivo_bloqueo TEXT
    )""")
    # _confirmar_registros() ahora llama a _resolver_pendiente_si_existe(),
    # que necesita esta tabla — sin ella, sqlite3.OperationalError: no such
    # table (encontrado corriendo la suite real tras el cambio, no a mano).
    conn.execute("""CREATE TABLE pendientes_revision (
        archivo_pdf TEXT PRIMARY KEY, id_documento TEXT, fecha DATE, planta TEXT,
        orden_compra TEXT, referencia TEXT, distancia TEXT, cliente TEXT, obra TEXT,
        obra_papel TEXT, obra_familia TEXT,
        bomba TEXT, id_producto TEXT, descripcion TEXT, cantidad REAL,
        precio_unitario REAL, total REAL, ficha TEXT, chofer TEXT, hora_salida TEXT,
        observaciones TEXT, empresa TEXT, fase TEXT, motivo TEXT, fecha_pendiente DATETIME
    )""")


def test_confirmar_registros_resuelve_pendiente_solo_si_se_confirma(tmp_path, monkeypatch):
    # Codex encontro esto en la 3ra ronda: antes, un documento corregido que
    # resolvia un pendiente se borraba de pendientes_revision en cuanto
    # Vision lo aprobaba — ANTES de que el usuario confirmara la
    # importacion. Si el usuario apretaba "Cancelar", el pendiente original
    # ya estaba borrado y la version corregida nunca se guardaba en ningun
    # lado: perdida silenciosa real. Ahora _resolver_pendiente_si_existe()
    # solo se llama dentro de _confirmar_registros(), tras un INSERT real.
    db_path = tmp_path / "est.db"
    pendientes_dir = tmp_path / "pendientes_revision"
    pendientes_dir.mkdir()
    monkeypatch.setattr(core, "EST_PENDIENTES", str(pendientes_dir))
    conn = sqlite3.connect(str(db_path))
    _crear_tabla_facturas(conn)
    (pendientes_dir / "M100000005.pdf").write_bytes(b"pdf viejo sin sello")
    conn.execute(
        "INSERT INTO pendientes_revision (archivo_pdf, id_documento, motivo) "
        "VALUES ('M100000005.pdf', 'M100000005', 'falta sello')"
    )
    conn.commit()

    # Simula "el usuario cancelo" — nunca se llama a _confirmar_registros()
    # con la version corregida. El pendiente original NO debe tocarse.
    fila = conn.execute("SELECT 1 FROM pendientes_revision WHERE id_documento='M100000005'").fetchone()
    assert fila is not None
    assert (pendientes_dir / "M100000005.pdf").exists()

    # Ahora si se confirma de verdad — recien ahi debe resolverse el pendiente.
    registro = {"id_documento": "M100000005", "descripcion": "Concreto"}
    confirmados = core._confirmar_registros(conn, [registro])
    fila_despues = conn.execute("SELECT 1 FROM pendientes_revision WHERE id_documento='M100000005'").fetchone()
    conn.close()
    assert len(confirmados) == 1
    assert fila_despues is None  # ahora si se resolvio, tras la confirmacion real
    assert not (pendientes_dir / "M100000005.pdf").exists()


def test_confirmar_registros_duplicado_no_incrementa_total(tmp_path):
    db_path = tmp_path / "est.db"
    conn = sqlite3.connect(str(db_path))
    _crear_tabla_facturas(conn)
    registro = {"id_documento": "M100000001", "descripcion": "Concreto"}
    confirmados_1 = core._confirmar_registros(conn, [registro])
    confirmados_2 = core._confirmar_registros(conn, [registro])  # mismo id_documento otra vez
    conn.close()
    assert len(confirmados_1) == 1
    assert len(confirmados_2) == 0  # INSERT OR IGNORE no inserto nada — no debe contarse


def test_confirmar_registros_devuelve_solo_los_realmente_confirmados(tmp_path, monkeypatch):
    # Codex encontro esto en la 3ra ronda: los 3 llamadores de
    # _confirmar_registros() pasaban la lista ORIGINAL completa a
    # actualizar_excel_main(), no lo que realmente se inserto — un
    # duplicado en el mismo lote quedaba una vez en SQLite pero dos veces
    # en el Excel maestro.
    db_path = tmp_path / "est.db"
    procesadas_dir = tmp_path / "procesadas"
    procesadas_dir.mkdir()
    monkeypatch.setattr(core, "EST_PROCESADAS", str(procesadas_dir))
    conn = sqlite3.connect(str(db_path))
    _crear_tabla_facturas(conn)
    r1 = {"id_documento": "M100000010", "descripcion": "Concreto A"}
    r2_duplicado = {"id_documento": "M100000010", "descripcion": "Concreto A (dup)"}
    r3 = {"id_documento": "M100000011", "descripcion": "Concreto B"}
    confirmados = core._confirmar_registros(conn, [r1, r2_duplicado, r3])
    conn.close()
    ids_confirmados = [r["id_documento"] for r in confirmados]
    assert ids_confirmados == ["M100000010", "M100000011"]  # el duplicado nunca aparece


def test_confirmar_registros_duplicado_no_escribe_pdf(tmp_path, monkeypatch):
    # Codex encontro esto en la verificacion de Fase 1: si el duplicado
    # escribe el PDF de todas formas, queda un archivo huerfano/sobreescrito
    # sin que el INSERT realmente haya insertado nada nuevo.
    db_path = tmp_path / "est.db"
    procesadas_dir = tmp_path / "procesadas"
    procesadas_dir.mkdir()
    monkeypatch.setattr(core, "EST_PROCESADAS", str(procesadas_dir))
    conn = sqlite3.connect(str(db_path))
    _crear_tabla_facturas(conn)
    registro = {
        "id_documento": "M100000003", "descripcion": "Concreto",
        "archivo_pdf": "M100000003.pdf", "_pdf_bytes": b"version original",
    }
    core._confirmar_registros(conn, [registro])
    os.remove(procesadas_dir / "M100000003.pdf")  # simula que ya se movio/limpio

    registro_duplicado = {**registro, "_pdf_bytes": b"version duplicada, no debe escribirse"}
    confirmados = core._confirmar_registros(conn, [registro_duplicado])
    conn.close()
    assert confirmados == []
    assert not (procesadas_dir / "M100000003.pdf").exists()  # nunca se re-escribio


def test_confirmar_registros_e_inserta_correctamente(tmp_path, monkeypatch):
    db_path = tmp_path / "est.db"
    procesadas_dir = tmp_path / "procesadas"
    procesadas_dir.mkdir()
    monkeypatch.setattr(core, "EST_PROCESADAS", str(procesadas_dir))
    conn = sqlite3.connect(str(db_path))
    _crear_tabla_facturas(conn)
    registro = {
        "id_documento": "M100000002", "descripcion": "Concreto",
        "archivo_pdf": "M100000002.pdf", "_pdf_bytes": b"contenido falso del pdf",
    }
    confirmados = core._confirmar_registros(conn, [registro])
    fila = conn.execute("SELECT id_documento FROM facturas WHERE id_documento='M100000002'").fetchone()
    conn.close()
    assert len(confirmados) == 1
    assert confirmados[0]["id_documento"] == "M100000002"
    assert fila is not None
    assert (procesadas_dir / "M100000002.pdf").read_bytes() == b"contenido falso del pdf"


def test_confirmar_registros_revierte_insert_si_falla_escribir_pdf(tmp_path, monkeypatch):
    # Codex tambien encontro esto: si el INSERT tiene exito pero falla
    # escribir el PDF despues, sin revertir quedaria una factura "exitosa"
    # en la BD sin su documento fisico de respaldo.
    db_path = tmp_path / "est.db"
    # EST_PROCESADAS apunta a un archivo (no un directorio) — cualquier
    # intento de escribir un PDF ahi dentro lanza OSError/NotADirectoryError.
    ruta_invalida = tmp_path / "esto_es_un_archivo_no_un_directorio"
    ruta_invalida.write_text("no soy un directorio", encoding="utf-8")
    monkeypatch.setattr(core, "EST_PROCESADAS", str(ruta_invalida))
    conn = sqlite3.connect(str(db_path))
    _crear_tabla_facturas(conn)
    registro = {
        "id_documento": "M100000004", "descripcion": "Concreto",
        "archivo_pdf": "M100000004.pdf", "_pdf_bytes": b"contenido falso del pdf",
    }
    confirmados = core._confirmar_registros(conn, [registro])
    fila = conn.execute("SELECT id_documento FROM facturas WHERE id_documento='M100000004'").fetchone()
    conn.close()
    assert confirmados == []
    assert fila is None  # el INSERT se revirtio — no queda huerfano en la BD


# ── Limite de tamano DESCOMPRIMIDO por PDF (zip bomb) ──

def test_procesar_pdfs_rechaza_pdf_que_excede_tamano_descomprimido(tmp_path, monkeypatch):
    # Codex encontro esto en la 3ra ronda: el limite de 50MB en
    # procesar_zip() es sobre el ZIP COMPRIMIDO completo — un solo PDF muy
    # comprimible (ej. paginas en blanco repetidas) podia declarar un
    # tamano descomprimido enorme sin que el tope del ZIP lo detectara.
    # Un patron muy compresible (ceros) simula esto sin necesitar un
    # archivo real de 25MB en disco de prueba.
    monkeypatch.setattr(core, "EST_PDF_MAX_BYTES_DESCOMPRIMIDO", 1024)  # 1KB, para no crear un fixture gigante

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("06-01-M1-00000001.pdf", b"\x00" * 5000)  # 5000 bytes > 1024
    buf.seek(0)
    zf_leido = zipfile.ZipFile(buf)

    db_path = tmp_path / "est.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE facturas (id_documento TEXT PRIMARY KEY)")

    # Con fila en el Excel para que el chequeo de "sin fila" no gane primero
    # y de verdad se llegue a leer los bytes y disparar el tope de tamano.
    lookup = _lookup_con_fila("06-01-M1-00000001.pdf", "M100000001", "Concreto", "CEDIS")

    importadas, errores_vision, pendientes, duplicadas, corregidas = asyncio.run(
        core._procesar_pdfs(zf_leido, ["06-01-M1-00000001.pdf"], conn, core.VISION_MODEL_STD, lookup)
    )
    conn.close()

    assert importadas == []
    assert len(errores_vision) == 1
    assert "descomprimido" in errores_vision[0]["motivo"]


def test_confirmar_registros_limpia_pdf_si_falla_un_paso_posterior_a_escribirlo(tmp_path, monkeypatch):
    # El PDF se escribe completo con exito, pero un paso DESPUES (resolver
    # el pendiente asociado) falla — debe revertir el INSERT via SAVEPOINT
    # Y borrar el PDF ya escrito, no solo cuando falla la escritura misma.
    db_path = tmp_path / "est.db"
    procesadas_dir = tmp_path / "procesadas"
    procesadas_dir.mkdir()
    monkeypatch.setattr(core, "EST_PROCESADAS", str(procesadas_dir))
    conn = sqlite3.connect(str(db_path))
    _crear_tabla_facturas(conn)
    conn.execute("DROP TABLE pendientes_revision")  # fuerza que _resolver_pendiente_si_existe falle

    registro = {
        "id_documento": "M100000006", "descripcion": "Concreto",
        "archivo_pdf": "M100000006.pdf", "_pdf_bytes": b"contenido del pdf",
    }
    confirmados = core._confirmar_registros(conn, [registro])
    fila = conn.execute("SELECT id_documento FROM facturas WHERE id_documento='M100000006'").fetchone()
    conn.close()

    assert confirmados == []
    assert fila is None  # el INSERT se revirtio via SAVEPOINT
    assert not (procesadas_dir / "M100000006.pdf").exists()  # el PDF ya escrito se limpio


class _ConnRollbackBloqueado:
    """Envuelve una conexion real de sqlite3 pero hace que ROLLBACK TO
    SAVEPOINT falle a proposito — reproduce el hallazgo del subagente en la
    4ta ronda: si el propio rollback falla, la fila puede sobrevivir y
    comitearse igual cuando el llamador haga conn.commit() mas adelante
    (SQLite no exige savepoints cerrados para commitear). Antes del fix,
    _confirmar_registros() borraba el PDF de todas formas en ese caso,
    dejando la fila-que-podria-sobrevivir sin su respaldo fisico."""
    def __init__(self, conn_real):
        self._conn = conn_real

    def execute(self, sql, params=()):
        if sql.strip().upper().startswith("ROLLBACK TO SAVEPOINT"):
            raise sqlite3.OperationalError("simulado: rollback bloqueado")
        return self._conn.execute(sql, params)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def test_confirmar_registros_no_borra_pdf_si_el_rollback_mismo_falla(tmp_path, monkeypatch):
    db_path = tmp_path / "est.db"
    procesadas_dir = tmp_path / "procesadas"
    procesadas_dir.mkdir()
    monkeypatch.setattr(core, "EST_PROCESADAS", str(procesadas_dir))
    conn_real = sqlite3.connect(str(db_path))
    _crear_tabla_facturas(conn_real)
    conn_real.execute("DROP TABLE pendientes_revision")  # fuerza que el paso posterior a escribir el PDF falle

    conn = _ConnRollbackBloqueado(conn_real)
    registro = {
        "id_documento": "M100000007", "descripcion": "Concreto",
        "archivo_pdf": "M100000007.pdf", "_pdf_bytes": b"contenido del pdf",
    }
    confirmados = core._confirmar_registros(conn, [registro])
    conn_real.close()

    assert confirmados == []
    # El PDF SI se escribio (el fallo fue despues, en resolver_pendiente) y
    # el rollback del savepoint fallo — no debe borrarse, porque la fila
    # correspondiente podria sobrevivir sin que este codigo pueda saberlo.
    assert (procesadas_dir / "M100000007.pdf").exists()


# ── 4ta ronda de verificacion (Codex) — 3 hallazgos reales, corregidos ──

class _ConnReleaseBloqueado:
    """Envuelve una conexion real de sqlite3 pero hace que RELEASE SAVEPOINT
    falle a proposito (ROLLBACK TO SAVEPOINT si funciona) — Codex encontro
    esto revisando el fix anterior: rollback_ok solo se ponia en True si
    AMBOS pasos (ROLLBACK TO + RELEASE) tenian exito en una sola llamada, asi
    que un RELEASE fallido dejaba el PDF huerfano sin necesidad aunque el
    ROLLBACK TO ya habia revertido los datos de verdad (RELEASE solo es
    bookkeeping del stack de savepoints, no vuelve a aplicar cambios)."""
    def __init__(self, conn_real):
        self._conn = conn_real

    def execute(self, sql, params=()):
        if sql.strip().upper().startswith("RELEASE SAVEPOINT"):
            raise sqlite3.OperationalError("simulado: release bloqueado")
        return self._conn.execute(sql, params)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def test_confirmar_registros_borra_pdf_si_solo_release_falla(tmp_path, monkeypatch):
    db_path = tmp_path / "est.db"
    procesadas_dir = tmp_path / "procesadas"
    procesadas_dir.mkdir()
    monkeypatch.setattr(core, "EST_PROCESADAS", str(procesadas_dir))
    conn_real = sqlite3.connect(str(db_path))
    _crear_tabla_facturas(conn_real)
    conn_real.execute("DROP TABLE pendientes_revision")  # fuerza que el paso posterior a escribir el PDF falle

    conn = _ConnReleaseBloqueado(conn_real)
    registro = {
        "id_documento": "M100000008", "descripcion": "Concreto",
        "archivo_pdf": "M100000008.pdf", "_pdf_bytes": b"contenido del pdf",
    }
    confirmados = core._confirmar_registros(conn, [registro])
    fila = conn_real.execute("SELECT id_documento FROM facturas WHERE id_documento='M100000008'").fetchone()
    conn_real.close()

    assert confirmados == []
    assert fila is None  # el ROLLBACK TO SI funciono, los datos quedaron revertidos de verdad
    # El PDF SI debe borrarse — el ROLLBACK TO (que revierte los datos) tuvo
    # exito, solo el RELEASE (bookkeeping del savepoint) fallo despues.
    assert not (procesadas_dir / "M100000008.pdf").exists()


def test_procesar_pdfs_rechaza_bomba_zip_agregada(tmp_path, monkeypatch):
    # Codex encontro esto verificando el fix del zip bomb: el tope POR-PDF
    # (EST_PDF_MAX_BYTES_DESCOMPRIMIDO) no alcanzaba solo — con
    # EST_ZIP_MAX_PDFS=1000 PDFs de hasta 20MB cada uno, validos
    # individualmente, la suma podia agotar la memoria del proceso completo
    # (~20GB en el peor caso) aunque el ZIP comprimido pesara poco. Cada PDF
    # de este test queda bajo el tope individual, pero la suma no.
    monkeypatch.setattr(core, "EST_PDF_MAX_BYTES_DESCOMPRIMIDO", 10_000)  # no dispara el limite individual
    monkeypatch.setattr(core, "EST_ZIP_TOTAL_DESCOMPRIMIDO_MAX_BYTES", 3_000)  # pero si el agregado

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("06-01-M1-00000001.pdf", b"\x00" * 2000)
        zf.writestr("06-01-M1-00000002.pdf", b"\x00" * 2000)
    buf.seek(0)
    zf_leido = zipfile.ZipFile(buf)

    db_path = tmp_path / "est.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE facturas (id_documento TEXT PRIMARY KEY)")

    lookup = {
        "por_archivo": {
            core._excel_norm_archivo("06-01-M1-00000001.pdf"): {
                "id_documento": "M100000001", "descripcion": "Concreto", "cliente": "CEDIS"},
            core._excel_norm_archivo("06-01-M1-00000002.pdf"): {
                "id_documento": "M100000002", "descripcion": "Concreto", "cliente": "CEDIS"},
        },
        "por_id": {}, "conflictos": {}, "filas": 2,
    }

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            core._procesar_pdfs(
                zf_leido,
                ["06-01-M1-00000001.pdf", "06-01-M1-00000002.pdf"],
                conn,
                core.VISION_MODEL_STD,
                lookup,
            )
        )
    conn.close()
    assert exc.value.status_code == 413


def test_incorporar_y_reprocesar_sin_reproceso_no_lanza_nameerror(tmp_path, monkeypatch):
    # Codex encontro esto verificando el fix del SAVEPOINT: al devolver
    # 'confirmados' en vez de la lista original, las dos respuestas JSON de
    # este endpoint (sin reproceso pendiente y con reproceso pendiente)
    # quedaron referenciando 'incorporados_ahora', una variable que ya no
    # existia — NameError real en TODA llamada a este endpoint, sin ningun
    # test end-to-end que lo cazara antes.
    db_path = tmp_path / "est.db"
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))

    token = "test-token-incorporar"
    core.active_tokens[token] = datetime.now()
    session_id = "sesion-test-incorporar"
    core.est_sessions[session_id] = {"importadas": [], "errores_vision": []}

    client = TestClient(main.app)
    try:
        resp = client.post(
            "/api/estimaciones/incorporar-y-reprocesar",
            json={"session_id": session_id},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)
        core.est_sessions.pop(session_id, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["incorporados_ahora"] == 0
    assert body["reprocesando"] is False


def test_incorporar_y_reprocesar_devuelve_los_errores_que_opus_no_puede_arreglar(tmp_path, monkeypatch):
    # 2026-10-15, Puentesillo: 4 errores, el boton decia "reprocesar con Opus
    # (4)" y Opus leyo 1 — los otros 3 eran "Scan_....pdf", nombre invalido,
    # sin bytes guardados. En el segundo clic el endpoint no tenia nada que
    # reintentar y la pantalla, sin la lista, daba el lote por terminado.
    db_path = tmp_path / "est.db"
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))

    token = "test-token-no-reprocesables"
    core.active_tokens[token] = datetime.now()
    session_id = "sesion-test-no-reprocesables"
    core.est_sessions[session_id] = {"importadas": [], "errores_vision": [
        {"nombre": "Scan_19-09-2026052649578.pdf", "motivo": "nombre de archivo inválido", "_pdf_bytes": None},
    ]}

    client = TestClient(main.app)
    try:
        resp = client.post(
            "/api/estimaciones/incorporar-y-reprocesar",
            json={"session_id": session_id},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)
        core.est_sessions.pop(session_id, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["reprocesando"] is False
    assert body["errores_vision_lista"] == [{
        "nombre": "Scan_19-09-2026052649578.pdf", "motivo": "nombre de archivo inválido",
        "reprocesable": False,
    }]


def test_lista_errores_vision_marca_reprocesable_solo_lo_que_tiene_bytes():
    from routes_estimaciones import _lista_errores_vision
    lista = _lista_errores_vision([
        {"nombre": "09-17-M4-34514.pdf", "motivo": "error al leer el documento (x)", "_pdf_bytes": b"%PDF"},
        {"nombre": "Scan_1.pdf", "motivo": "nombre de archivo inválido", "_pdf_bytes": None},
        {"nombre": "09-17-M4-34515.pdf", "motivo": "el PDF tiene 3 páginas", "_pdf_bytes": None},
    ])
    assert [e["reprocesable"] for e in lista] == [True, False, False]
    assert "_pdf_bytes" not in lista[0], "los bytes del PDF nunca salen en la respuesta"


# ── Issue #7 (2026-08-24) — MACAO 2: sello obligatorio, firma ya NO bloquea ──
# (issue #8 confirmo que esta regla es especifica de MACAO 2, no general —
# estos 4 tests se actualizaron de fase "CEDIS" a fase "MACAO 2" para seguir
# probando la regla correcta; los 4 de mas abajo cubren la regla nueva para
# cualquier otra fase.)

def test_motivo_sello_firma_sello_true_firma_true_no_bloquea():
    datos = {"fase": "MACAO 2", "tiene_sello": True, "tiene_firma": True}
    assert core._motivo_sello_firma(datos) is None


def test_motivo_sello_firma_sello_true_firma_false_ya_no_bloquea():
    # Cambio de comportamiento del issue #7: antes esto devolvia "falta firma"
    # y mandaba el documento a pendientes_revision. Ahora se importa igual
    # (solo para MACAO 2 — issue #8).
    datos = {"fase": "MACAO 2", "tiene_sello": True, "tiene_firma": False}
    assert core._motivo_sello_firma(datos) is None


def test_motivo_sello_firma_sello_false_firma_true_bloquea():
    datos = {"fase": "MACAO 2", "tiene_sello": False, "tiene_firma": True}
    assert core._motivo_sello_firma(datos) == "falta sello"


def test_motivo_sello_firma_sello_false_firma_false_bloquea():
    # El motivo ya no distingue "falta sello y firma" de "falta sello" — la
    # firma dejo de ser parte del chequeo para MACAO 2, sea cual sea su valor
    # cuando no hay sello el resultado es el mismo.
    datos = {"fase": "MACAO 2", "tiene_sello": False, "tiene_firma": False}
    assert core._motivo_sello_firma(datos) == "falta sello"


# ── Issue #8 (2026-08-24) — cualquier otra fase: firma obligatoria, sello NO bloquea ──

def test_motivo_sello_firma_no_macao2_firma_true_sello_true_no_bloquea():
    datos = {"fase": "CEDIS", "tiene_sello": True, "tiene_firma": True}
    assert core._motivo_sello_firma(datos) is None


def test_motivo_sello_firma_no_macao2_firma_true_sello_false_no_bloquea():
    # El sello ya no bloquea para fases distintas de MACAO 2.
    datos = {"fase": "CEDIS", "tiene_sello": False, "tiene_firma": True}
    assert core._motivo_sello_firma(datos) is None


def test_motivo_sello_firma_no_macao2_firma_false_sello_true_bloquea():
    datos = {"fase": "CEDIS", "tiene_sello": True, "tiene_firma": False}
    assert core._motivo_sello_firma(datos) == "falta firma"


def test_motivo_sello_firma_no_macao2_firma_false_sello_false_bloquea():
    datos = {"fase": "CEDIS", "tiene_sello": False, "tiene_firma": False}
    assert core._motivo_sello_firma(datos) == "falta firma"


def test_procesar_pdfs_no_macao2_sin_firma_va_a_pendientes(tmp_path, monkeypatch):
    # Integration test del Testing Plan del issue #8: un documento de fase
    # distinta de MACAO 2, con sello pero sin firma, va a pendientes_revision
    # con motivo "falta firma" (en vez de importarse, que es lo que pasaria
    # si fuera MACAO 2 — issue #7).
    def fake_vision(pdf_bytes, model=core.VISION_MODEL_STD):
        return {
            "tiene_sello": True, "tiene_firma": False,
            "obra": "CEDIS", "descripcion": "Concreto Fc250", "cantidad": 5,
        }
    monkeypatch.setattr(core, "_procesar_pdf_sync", fake_vision)
    # Doble-chequeo no se dispara aca porque el motivo ya esta determinado
    # (falta firma) desde la primera pasada — igual que MACAO 2 no dispara
    # el doble-chequeo cuando ya falta el sello desde la primera pasada.
    monkeypatch.setattr(
        core, "_verificar_sello_firma_opus",
        lambda pdf_bytes: (_ for _ in ()).throw(AssertionError("no deberia llamarse"))
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("06-01-M1-00000099.pdf", b"contenido falso")
    buf.seek(0)
    zf_leido = zipfile.ZipFile(buf)

    db_path = tmp_path / "est.db"
    conn = sqlite3.connect(str(db_path))
    _crear_tabla_facturas(conn)
    conn.execute("CREATE TABLE precios_vmo (descripcion TEXT, fase TEXT, precio_unitario REAL)")
    conn.execute("CREATE TABLE precios_domicem (descripcion TEXT, fase TEXT, precio_unitario REAL)")

    lookup = _lookup_con_fila("06-01-M1-00000099.pdf", "M100000099", "Concreto Fc250", "CEDIS")
    importadas, errores_vision, pendientes, duplicadas, corregidas = asyncio.run(
        core._procesar_pdfs(zf_leido, ["06-01-M1-00000099.pdf"], conn, core.VISION_MODEL_STD, lookup)
    )
    conn.close()

    assert importadas == []
    assert len(pendientes) == 1
    assert pendientes[0]["motivo"] == "falta firma"


def test_procesar_pdfs_sello_sin_firma_se_importa_marcado(tmp_path, monkeypatch):
    # Acceptance criterion #2 del issue: documento con sello, sin firma -> se
    # importa, con datos["sin_firma"]=True.
    def fake_vision(pdf_bytes, model=core.VISION_MODEL_STD):
        return {
            "tiene_sello": True, "tiene_firma": False,
            "obra": "MACAO 2", "descripcion": "Concreto Fc250", "cantidad": 5,
        }
    monkeypatch.setattr(core, "_procesar_pdf_sync", fake_vision)
    # Doble-chequeo se sigue disparando con sello=true (independiente de
    # firma) — confirma el mismo resultado, sigue sin firma.
    monkeypatch.setattr(
        core, "_verificar_sello_firma_opus",
        lambda pdf_bytes: {"tiene_sello": True, "tiene_firma": False}
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("06-01-M1-00000001.pdf", b"contenido falso")
    buf.seek(0)
    zf_leido = zipfile.ZipFile(buf)

    db_path = tmp_path / "est.db"
    conn = sqlite3.connect(str(db_path))
    _crear_tabla_facturas(conn)
    conn.execute("CREATE TABLE precios_vmo (descripcion TEXT, fase TEXT, precio_unitario REAL)")
    conn.execute("CREATE TABLE precios_domicem (descripcion TEXT, fase TEXT, precio_unitario REAL)")

    lookup = _lookup_con_fila("06-01-M1-00000001.pdf", "M100000001", "Concreto Fc250", "MACAO 2")
    importadas, errores_vision, pendientes, duplicadas, corregidas = asyncio.run(
        core._procesar_pdfs(zf_leido, ["06-01-M1-00000001.pdf"], conn, core.VISION_MODEL_STD, lookup)
    )
    conn.close()

    assert pendientes == []
    assert len(importadas) == 1
    assert importadas[0]["sin_firma"] is True


def test_procesar_zip_endpoint_separa_importadas_sin_firma(tmp_path, monkeypatch):
    # Acceptance criterion #2 del issue, a nivel HTTP: la respuesta JSON de
    # /procesar-zip separa importadas_lista (con firma) de
    # importadas_sin_firma_lista (sello si, firma no) — el conteo total
    # "importadas" sigue siendo la suma de ambas.
    db_path = tmp_path / "est.db"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    monkeypatch.setattr(core, "EST_DATA_DIR", str(data_dir))

    def fake_vision(pdf_bytes, model=core.VISION_MODEL_STD):
        return {
            "tiene_sello": True, "tiene_firma": False,
            "obra": "MACAO 2", "descripcion": "Concreto Fc250", "cantidad": 5,
        }
    monkeypatch.setattr(core, "_procesar_pdf_sync", fake_vision)
    monkeypatch.setattr(
        core, "_verificar_sello_firma_opus",
        lambda pdf_bytes: {"tiene_sello": True, "tiene_firma": False}
    )

    token = "test-token-procesar-zip-sin-firma"
    core.active_tokens[token] = datetime.now()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("06-01-M1-00000002.pdf", b"contenido falso")
    buf.seek(0)
    excel_bytes = _construir_excel_bytes([
        ("M100000002", "2026-06-01", "MACAO ALTO RESORT S.R.L (MACAO II)", "Concreto Fc250", 5, "M1", "06-01-M1-00000002.pdf"),
    ])

    client = TestClient(main.app)
    res = None
    try:
        res = client.post(
            "/api/estimaciones/procesar-zip",
            files={
                "archivo": ("lote.zip", buf.getvalue(), "application/zip"),
                "excel": ("conduces.xlsx", excel_bytes,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)
        if res is not None and res.status_code == 200:
            core.est_sessions.pop(res.json().get("session_id"), None)

    assert res.status_code == 200, res.text
    data = res.json()
    assert data["importadas"] == 1
    assert data["importadas_lista"] == []
    assert data["importadas_sin_firma_lista"] == ["06-01-M1-00000002.pdf"]


def test_reprocesar_en_background_marca_sin_firma_en_progreso(tmp_path, monkeypatch):
    # Acceptance criterion #2, en la rama de reproceso con Opus: un documento
    # que sale de _reprocesar_en_background() con sello pero sin firma
    # aparece en prog["importadas_sin_firma_lista"], que /reprocesar-progreso
    # expone en su rama final.
    db_path = tmp_path / "est.db"
    procesadas_dir = tmp_path / "procesadas"
    procesadas_dir.mkdir()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    monkeypatch.setattr(core, "EST_PROCESADAS", str(procesadas_dir))
    monkeypatch.setattr(core, "EST_EXCEL_MAIN", str(tmp_path / "estimaciones_main.xlsx"))

    conn = sqlite3.connect(str(db_path))
    _crear_tabla_facturas(conn)
    conn.execute("CREATE TABLE precios_vmo (descripcion TEXT, fase TEXT, precio_unitario REAL)")
    conn.execute("CREATE TABLE precios_domicem (descripcion TEXT, fase TEXT, precio_unitario REAL)")
    conn.commit()
    conn.close()

    def fake_vision(pdf_bytes, model=core.VISION_MODEL_PRO):
        return {
            "tiene_sello": True, "tiene_firma": False,
            "obra": "MACAO 2", "descripcion": "Concreto Fc250", "cantidad": 5,
        }
    monkeypatch.setattr(core, "_procesar_pdf_sync", fake_vision)

    session_id = "sesion-reproceso-sin-firma"
    info = core.parsear_nombre_pdf("06-01-M1-00000003.pdf")
    core.est_sessions[session_id] = {
        "errores_vision": [{
            "nombre": "06-01-M1-00000003.pdf",
            "motivo": "error al leer el documento (previo)",
            "_pdf_bytes": b"contenido falso", "_info": info,
        }],
        "reprocess_progress": {
            "activo": True, "actual": 0, "total": 1,
            "modelo": "opus", "pendientes_nuevos": [],
        },
        "lookup": _lookup_con_fila("06-01-M1-00000003.pdf", "M100000003", "Concreto Fc250", "MACAO 2"),
    }

    try:
        asyncio.run(core._reprocesar_en_background(session_id))
        prog = core.est_sessions[session_id]["reprocess_progress"]
        assert prog["activo"] is False
        assert prog["importadas_sin_firma_lista"] == ["06-01-M1-00000003.pdf"]
    finally:
        core.est_sessions.pop(session_id, None)


def test_confirmar_registros_resuelve_pendiente_con_sello_pero_sin_firma(tmp_path, monkeypatch):
    # Acceptance criterion #4 del issue: un documento en pendientes_revision
    # por falta de sello se resube con sello (pero sigue sin firma) -> se
    # importa con sin_firma=1 y sale de pendientes automaticamente.
    db_path = tmp_path / "est.db"
    pendientes_dir = tmp_path / "pendientes_revision"
    pendientes_dir.mkdir()
    monkeypatch.setattr(core, "EST_PENDIENTES", str(pendientes_dir))
    conn = sqlite3.connect(str(db_path))
    _crear_tabla_facturas(conn)
    (pendientes_dir / "M100000009.pdf").write_bytes(b"pdf viejo sin sello")
    conn.execute(
        "INSERT INTO pendientes_revision (archivo_pdf, id_documento, motivo) "
        "VALUES ('M100000009.pdf', 'M100000009', 'falta sello')"
    )
    conn.commit()

    registro = {"id_documento": "M100000009", "descripcion": "Concreto", "sin_firma": True}
    confirmados = core._confirmar_registros(conn, [registro])
    fila_pendiente = conn.execute(
        "SELECT 1 FROM pendientes_revision WHERE id_documento='M100000009'"
    ).fetchone()
    fila_factura = conn.execute(
        "SELECT sin_firma FROM facturas WHERE id_documento='M100000009'"
    ).fetchone()
    conn.close()

    assert len(confirmados) == 1
    assert fila_pendiente is None  # se resolvio automaticamente
    assert not (pendientes_dir / "M100000009.pdf").exists()
    assert fila_factura[0] == 1  # sin_firma persistido


def test_pendientes_revision_separa_macao2_de_otras_fases(tmp_path, monkeypatch):
    # Acceptance criterion #6 del issue #8: GET /pendientes-revision agrupa
    # en 2 listas segun fase, en vez de una sola lista mezclada.
    db_path = tmp_path / "est.db"
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    core.setup_est_db()
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO pendientes_revision (archivo_pdf, id_documento, fase, motivo) "
        "VALUES ('a.pdf', 'DOC-A', 'MACAO 2', 'falta sello')"
    )
    conn.execute(
        "INSERT INTO pendientes_revision (archivo_pdf, id_documento, fase, motivo) "
        "VALUES ('b.pdf', 'DOC-B', 'CEDIS', 'falta firma')"
    )
    conn.commit()
    conn.close()

    token = "test-token-pendientes-revision"
    core.active_tokens[token] = datetime.now()
    try:
        client = TestClient(main.app)
        res = client.get(
            "/api/estimaciones/pendientes-revision",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert [f["id_documento"] for f in data["macao2"]] == ["DOC-A"]
    assert [f["id_documento"] for f in data["otras_fases"]] == ["DOC-B"]


def test_setup_est_db_migra_columna_sin_firma_si_falta(tmp_path, monkeypatch):
    db_path = tmp_path / "est_migracion.db"
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    # Simula una BD con la tabla facturas vieja, SIN la columna sin_firma
    # (mismo escenario que una instalacion real hecha antes del issue #7).
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE facturas (
        id_documento TEXT PRIMARY KEY, fecha DATE, planta TEXT, orden_compra TEXT,
        referencia TEXT, distancia TEXT, cliente TEXT, obra TEXT, bomba TEXT,
        id_producto TEXT, descripcion TEXT, cantidad REAL, precio_unitario REAL,
        total REAL, ficha TEXT, chofer TEXT, hora_salida TEXT, observaciones TEXT,
        archivo_pdf TEXT, empresa TEXT, fase TEXT, fecha_importacion DATETIME
    )""")
    conn.commit()
    conn.close()

    core.setup_est_db()

    conn = sqlite3.connect(str(db_path))
    columnas = {c[1] for c in conn.execute("PRAGMA table_info(facturas)").fetchall()}
    conn.close()
    assert "sin_firma" in columnas


def test_setup_est_db_migracion_de_sin_firma_es_idempotente(tmp_path, monkeypatch):
    db_path = tmp_path / "est_migracion2.db"
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    core.setup_est_db()
    core.setup_est_db()  # segunda corrida — no debe fallar (ALTER TABLE duplicado)

    conn = sqlite3.connect(str(db_path))
    columnas = {c[1] for c in conn.execute("PRAGMA table_info(facturas)").fetchall()}
    conn.close()
    assert "sin_firma" in columnas


def test_confirmar_registros_persiste_sin_firma_default_y_explicito(tmp_path):
    db_path = tmp_path / "est.db"
    conn = sqlite3.connect(str(db_path))
    _crear_tabla_facturas(conn)
    r_normal    = {"id_documento": "M100000020", "descripcion": "Concreto A"}  # sin la clave -> default 0
    r_sin_firma = {"id_documento": "M100000021", "descripcion": "Concreto B", "sin_firma": True}
    core._confirmar_registros(conn, [r_normal, r_sin_firma])
    fila_normal    = conn.execute("SELECT sin_firma FROM facturas WHERE id_documento='M100000020'").fetchone()
    fila_sin_firma = conn.execute("SELECT sin_firma FROM facturas WHERE id_documento='M100000021'").fetchone()
    conn.close()
    assert fila_normal[0] == 0
    assert fila_sin_firma[0] == 1


# ── issue #10 — separar CIMENTACION TORRES / TORRE GRUA, fix de colision ──
#
# Antes de este issue, catalogo_norm = {texto_normalizado: producto} pisaba
# silenciosamente un producto con otro si 2 normalizaban al mismo texto —
# caso real: "...CIMENTACION TORRES" y "...TORRE GRUA" (mismo concreto
# exacto, MACAO 2/DOMICEM, sin ninguna forma de distinguirlos desde la
# factura fisica). _est_catalogo_norm_a_clave() corrige esto devolviendo
# None para el texto colisionado, forzando revision manual siempre.

def test_est_catalogo_norm_a_clave_sin_colisiones_devuelve_mapeo_correcto():
    catalogo = [
        {"clave": "1", "descripcion": "Concreto Uno TIPO A"},
        {"clave": "2", "descripcion": "Concreto Dos TIPO B"},
        {"clave": "3", "descripcion": "Concreto Tres TIPO C"},
    ]
    # empresa/fase inexistentes a proposito — no tienen alias, asi que el
    # mapeo no debe traer nada extra de _EST_ALIAS_DESCRIPCION_FACTURA.
    resultado = core._est_catalogo_norm_a_clave(catalogo, "FASE_SIN_ALIAS", "FASE_SIN_ALIAS")
    assert len(resultado) == 3
    assert resultado[core._est_normalizar_catalogo("Concreto Uno TIPO A")] == "1"
    assert resultado[core._est_normalizar_catalogo("Concreto Dos TIPO B")] == "2"
    assert resultado[core._est_normalizar_catalogo("Concreto Tres TIPO C")] == "3"


def test_est_catalogo_norm_a_clave_colision_da_none_sin_perder_el_no_colisionado():
    desc_torres = 'Hormigón Fc350 kg/cm2, rev. 8" CIMENTACION TORRES'
    desc_grua = 'Hormigón Fc350 kg/cm2, rev. 8" TORRE GRUA'
    desc_columnas = 'Hormigón Fc350 kg/cm2, rev. 6" COLUMNAS MUROS'
    catalogo = [
        {"clave": "3", "descripcion": desc_torres},
        {"clave": "4", "descripcion": desc_grua},
        {"clave": "6", "descripcion": desc_columnas},
    ]
    resultado = core._est_catalogo_norm_a_clave(catalogo, "FASE_SIN_ALIAS", "FASE_SIN_ALIAS")
    norm_colision = core._est_normalizar_catalogo(desc_torres)
    assert core._est_normalizar_catalogo(desc_grua) == norm_colision  # confirma que de verdad colisionan
    norm_columnas = core._est_normalizar_catalogo(desc_columnas)
    assert resultado[norm_colision] is None
    assert resultado[norm_columnas] == "6"


def test_est_catalogo_norm_a_clave_alias_no_se_filtra_a_otra_fase():
    # Regresion del bug real encontrado en la auditoria de 2026-08-27: los
    # alias de CAVERNAS (clave "2") NO deben aplicarse a un catalogo de otra
    # fase que tambien tenga una clave "2", aunque sea para un producto
    # totalmente distinto. Antes de escopear por (empresa, fase), este
    # catalogo sintetico heredaba el alias de CAVERNAS por el solo hecho de
    # tener clave "2" — descubierto porque rompio
    # test_est_catalogo_norm_a_clave_sin_colisiones_devuelve_mapeo_correcto.
    texto_alias_cavernas = 'HORMIGÓN 150 KG/CM2, AG 3/4",T 35C, REV. 7" +/- 1"'
    catalogo_otra_fase = [
        {"clave": "2", "descripcion": "Un producto cualquiera de otra fase"},
    ]
    resultado_otra_fase = core._est_catalogo_norm_a_clave(catalogo_otra_fase, "VMO", "CANCHAS")
    assert texto_alias_cavernas not in resultado_otra_fase
    assert len(resultado_otra_fase) == 1

    catalogo_cavernas = [
        {"clave": "1", "descripcion": "Hormigón 100 kg/cm2, Ag 3/4\", T35C, REV. 6\" +/-1\""},
        {"clave": "2", "descripcion": 'Hormigón 150 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1"'},
        {"clave": "3", "descripcion": "Hormigón 210 kg/cm2, Ag 3/4\",T 35C, rev. 6\" +/- 1\""},
    ]
    resultado_cavernas = core._est_catalogo_norm_a_clave(catalogo_cavernas, "DOMICEM", "CAVERNAS")
    assert resultado_cavernas[texto_alias_cavernas] == "2"


# ── Issues #23 y #26 (2026-09-02): los 5 alias verificados contra el CODIGO
# DE PRODUCTO impreso en el conduce fisico, no por parecido de texto. Cada uno
# de estos tests tiene que fallar si se saca su alias de
# _EST_ALIAS_DESCRIPCION_FACTURA.

def test_alias_exteriores_280_rev7_imp_resuelve_a_clave_9():
    # 75 facturas / 479.0 m3 de junio 2026. Codigo 44522 impreso en el conduce
    # 06-01-M8-12024 = $147.00 en la lista de precios = clave 9. El catalogo
    # escribe el mismo producto como '...rev. Imp', sin el revenimiento, y por
    # eso el texto no matcheaba.
    catalogo = [
        {"clave": "8", "descripcion": 'Hormigón 280 kg/cm2, Ag 3/4",T 32C, rev. 6"+/- 1".'},
        {"clave": "9", "descripcion": 'Hormigón 280 kg/cm2, Ag 3/4",T 32C, rev. Imp'},
    ]
    resultado = core._est_catalogo_norm_a_clave(catalogo, "VMO", "EXTERIORES")
    factura = 'Hormigón 280 kg/cm2, Ag 3/4",T 32C, rev. 7" +/- 1", imp'
    assert resultado[core._est_normalizar(factura)] == "9"


def test_alias_exteriores_fc280_rev6_resuelve_a_clave_8():
    # 22 facturas / 119.0 m3 del 1 al 13 de junio 2026. Codigo 4415 impreso en
    # el conduce 06-01-M8-12025 = $136.00 = clave 8. Misma especificacion que
    # la clave 8, escrita con las abreviaturas largas.
    catalogo = [
        {"clave": "8", "descripcion": 'Hormigón 280 kg/cm2, Ag 3/4",T 32C, rev. 6"+/- 1".'},
        {"clave": "9", "descripcion": 'Hormigón 280 kg/cm2, Ag 3/4",T 32C, rev. Imp'},
    ]
    resultado = core._est_catalogo_norm_a_clave(catalogo, "VMO", "EXTERIORES")
    factura = 'Hormigón Fc280 kg/cm2, Agg 3/4", Temp. 32C, rev. 6"+/- 1"'
    assert resultado[core._est_normalizar(factura)] == "8"


def test_alias_tra_350_imp_resuelve_a_clave_4():
    # 3 facturas / 20.0 m3 del 2026-07-13. Codigo 4477 impreso en el conduce
    # 07-13-M8-13751; la lista de precios tiene una fila explicita para
    # "(PATIO DE MANIOBRA TRA)" con ese codigo a $186.98 = clave 4. TRA es la
    # unica fase donde orden != clave (orden 2 -> clave 3, orden 3 -> clave 2);
    # el catalogo de abajo respeta esa numeracion real.
    catalogo = [
        {"clave": "1", "descripcion": 'Hormigón Fc100 kg/cm2, Agg 3/4", Temp. 35C, rev. 6"+/- 1".'},
        {"clave": "3", "descripcion": 'Hormigón Fc350 kg/cm2, AMB. S1 (ACI), Agg 3/4", Temp. 32C, a/c=0.50, Silice 10%, rev. 6"+/- 1".'},
        {"clave": "2", "descripcion": 'Hormigón Fc350 kg/cm2, AMB. IIIA (EHE), Agg 3/8", Temp. 32C, a/c=0.50, rev. 6"+/- 1".'},
        {"clave": "4", "descripcion": 'Hormigon 350kg/cm2, AMB IIIA (EHE), Ag 3/8",T 32C, a/c= 0.45, Min. C: 300kg, rev. 6" +/- 1'},
    ]
    resultado = core._est_catalogo_norm_a_clave(catalogo, "VMO", "PATIO DE MANIOBRAS-TRA")
    factura = 'Hormigón 350kg/cm2, AMB IIIA (EHE), Ag 3/8",T 32C, a/c= 0.45, Min. C: 300kg, rev. 6" +/- 1", Imp'
    assert resultado[core._est_normalizar(factura)] == "4"


def test_alias_cavernas_150_rev8_resuelve_a_clave_2():
    # 1 factura / 7.0 m3 del 2026-06-30 (issue #26). Codigo 44510 impreso en el
    # conduce 06-30-M8-13172 = $111.00 = clave 2. El 8" del texto libre es un
    # tipeo de la planta: el mismo papel trae el codigo del producto de 7".
    catalogo = [
        {"clave": "1", "descripcion": 'Hormigón 100 kg/cm2, Ag 3/4", T35C, REV. 6" +/-1"'},
        {"clave": "2", "descripcion": 'Hormigón 150 kg/cm2, Ag 3/4",T 35C, rev. 6" +/- 1"'},
    ]
    resultado = core._est_catalogo_norm_a_clave(catalogo, "DOMICEM", "CAVERNAS")
    factura = 'Hormigón 150 kg/cm2, Ag 3/4",T 35C, rev. 8" +/- 1"'
    assert resultado[core._est_normalizar(factura)] == "2"


def test_alias_macao2_ambiiia_con_espacios_resuelve_a_clave_6():
    # 1 factura / 1.5 m3 del 2026-07-24. Codigo 4419 impreso en el conduce
    # 07-24-M8-14137 = $154.02 = clave 6. Del texto del catalogo lo separan
    # solo espacios ("AMB. III A" vs "AMB. IIIA", 'REV. 6"+ / -1"' vs
    # 'REV. 6"+/- 1"'): _est_normalizar colapsa espacios repetidos pero no los
    # inserta ni los borra.
    catalogo = [
        {"clave": "6", "descripcion": 'Hormigón Fc350 kg/cm2, AMB. IIIA (EHE), Agg 3/8", Temp. 32C, a/c=0.50, rev. 6"+/- 1".'},
    ]
    resultado = core._est_catalogo_norm_a_clave(catalogo, "DOMICEM", "MACAO 2")
    factura = 'Hormigón Fc350 kg/cm2, AMB. III A (EHE), Agg 3/8", Temp. 32C, a/c=0.50, rev. 6"+ / -1"'
    assert resultado[core._est_normalizar(factura)] == "6"


def test_alias_350_imp_apunta_a_claves_distintas_en_tra_y_macao2():
    # El texto de factura del alias de TRA es IDENTICO al de MACAO 2, pero va a
    # la clave 4 en TRA y a la 7 en MACAO 2 — el mismo producto en contratos
    # distintos. Este es el caso que mas duele si el escopeo por (empresa,
    # fase) se rompe: el alias se filtraria y mandaria 20 m3 al renglon
    # equivocado sin que nada falle ruidoso.
    factura = core._est_normalizar(
        'Hormigón 350kg/cm2, AMB IIIA (EHE), Ag 3/8",T 32C, a/c= 0.45, Min. C: 300kg, rev. 6" +/- 1", Imp'
    )
    cat_tra = [{"clave": "4", "descripcion": "Producto propio de TRA"}]
    cat_macao = [{"clave": "7", "descripcion": "Producto propio de MACAO 2"}]
    assert core._est_catalogo_norm_a_clave(cat_tra, "VMO", "PATIO DE MANIOBRAS-TRA")[factura] == "4"
    assert core._est_catalogo_norm_a_clave(cat_macao, "DOMICEM", "MACAO 2")[factura] == "7"
    # y no alcanza a una tercera fase que tambien tiene clave "4"
    cat_otra = [{"clave": "4", "descripcion": "Producto de otra fase"}]
    assert factura not in core._est_catalogo_norm_a_clave(cat_otra, "VMO", "CANCHAS")


def test_alias_nuevos_de_exteriores_no_se_filtran_a_otra_fase():
    textos = [
        core._est_normalizar('Hormigón 280 kg/cm2, Ag 3/4",T 32C, rev. 7" +/- 1", imp'),
        core._est_normalizar('Hormigón Fc280 kg/cm2, Agg 3/4", Temp. 32C, rev. 6"+/- 1"'),
    ]
    catalogo_otra_fase = [
        {"clave": "8", "descripcion": "Un producto cualquiera de otra fase"},
        {"clave": "9", "descripcion": "Otro producto cualquiera de otra fase"},
    ]
    resultado = core._est_catalogo_norm_a_clave(catalogo_otra_fase, "DOMICEM", "VIVIENDAS")
    for t in textos:
        assert t not in resultado


_CATALOGO_MACAO2_TORRES_GRUA = [
    (1, "3", 'Hormigón Fc350 kg/cm2, rev. 8" CIMENTACION TORRES', 191.27),
    (2, "4", 'Hormigón Fc350 kg/cm2, rev. 8" TORRE GRUA', 191.27),
    (3, "6", 'Hormigón Fc350 kg/cm2, rev. 6" COLUMNAS MUROS', 154.02),
]


def _bd_macao2_colision(tmp_path, monkeypatch, facturas):
    """BD sqlite minima para DOMICEM/MACAO 2 con la colision real Torres/Grua
    (mismo texto normalizado para clave 3 y 4) + clave 6 sin colision, para
    el test de regresion — aisla estos tests de la BD real de produccion.
    Mismo patron que bd_sintetica()/_bd_sintetica() de arriba/de
    test_generar_pdf_estimacion.py."""
    db_path = tmp_path / "estimaciones_test_torres_grua.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE catalogo_estimacion (
        empresa TEXT, fase TEXT, orden INTEGER, clave TEXT,
        descripcion TEXT, precio_unitario REAL,
        PRIMARY KEY (empresa, fase, orden)
    )""")
    conn.execute("""CREATE TABLE facturas (
        id_documento TEXT PRIMARY KEY, fecha DATE, empresa TEXT, fase TEXT,
        descripcion TEXT, cantidad REAL, precio_unitario REAL, clave_resuelta TEXT
    )""")
    conn.execute("""CREATE TABLE estimacion_acumulado_base (
        empresa TEXT, fase TEXT, clave TEXT,
        serie TEXT NOT NULL CHECK (serie IN ('principal','ppact')),
        fecha_base DATE, cantidad_base REAL, cantidad_proyecto_principal REAL,
        PRIMARY KEY (empresa, fase, clave, serie)
    )""")
    for orden, clave, desc, precio in _CATALOGO_MACAO2_TORRES_GRUA:
        conn.execute(
            "INSERT INTO catalogo_estimacion VALUES ('DOMICEM','MACAO 2',?,?,?,?)",
            (orden, clave, desc, precio),
        )
    for f in facturas:
        conn.execute(
            "INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,cantidad,precio_unitario,clave_resuelta) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (f["id_documento"], f["fecha"], "DOMICEM", "MACAO 2",
             f["descripcion"], f["cantidad"], f.get("precio_unitario", 191.27),
             f.get("clave_resuelta")),
        )
    conn.commit()
    conn.close()

    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))

    token = "test-token-torres-grua"
    core.active_tokens[token] = datetime.now()
    return token


def test_vista_previa_colision_torres_grua_queda_en_sin_match(tmp_path, monkeypatch):
    # Reproduce el caso real (Acceptance Criteria #2 del issue #10):
    # factura M800013294, fecha 2026-07-02, texto identico al de los 2
    # productos fusionados — no debe auto-asignarse a ninguno de los 2.
    facturas = [{
        "id_documento": "M800013294", "fecha": "2026-07-02",
        "descripcion": 'Hormigón Fc350 kg/cm2, rev. 8"', "cantidad": 5.0,
    }]
    token = _bd_macao2_colision(tmp_path, monkeypatch, facturas)
    client = TestClient(main.app)
    try:
        res = client.get(
            "/api/estimaciones/vista-previa",
            params={"empresa": "DOMICEM", "fase": "MACAO 2",
                    "fecha_desde": "2026-07-01", "fecha_hasta": "2026-07-31"},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data["sin_match"]) == 1
    assert data["sin_match"][0]["descripcion"] == 'Hormigón Fc350 kg/cm2, rev. 8"'
    assert data["sin_match"][0]["cantidad_facturas"] == 1
    por_clave = {c["clave"]: c for c in data["catalogo"]}
    assert por_clave["3"]["facturas_matcheadas"] is None
    assert por_clave["4"]["facturas_matcheadas"] is None


def test_generar_colision_torres_grua_sin_reasignacion_da_facturas_sin_resolver(tmp_path, monkeypatch):
    facturas = [{
        "id_documento": "M800013294", "fecha": "2026-07-02",
        "descripcion": 'Hormigón Fc350 kg/cm2, rev. 8"', "cantidad": 5.0,
    }]
    token = _bd_macao2_colision(tmp_path, monkeypatch, facturas)
    client = TestClient(main.app)
    payload = {
        "empresa": "DOMICEM", "fase": "MACAO 2",
        "fecha_desde": "2026-07-01", "fecha_hasta": "2026-07-31",
        "numero_estimacion": "N01", "fecha_estimacion": "2026-08-25", "semana": 1,
        "productos": [
            {"clave": "3", "cantidad_proyecto": 100, "acumulado_anterior_cantidad": 0},
            {"clave": "4", "cantidad_proyecto": 100, "acumulado_anterior_cantidad": 0},
            {"clave": "6", "cantidad_proyecto": 100, "acumulado_anterior_cantidad": 0},
        ],
        "reasignaciones": {},  # no resuelve la colision a proposito
        "serie": "principal",
    }
    try:
        res = client.post(
            "/api/estimaciones/generar", json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "facturas_sin_resolver"
    assert 'Hormigón Fc350 kg/cm2, rev. 8"' in res.json()["detail"]["detalle"]


def test_generar_colision_torres_grua_reasignada_a_clave_3_termina_en_su_hoja_rgo(tmp_path, monkeypatch):
    # Mismo patron de aislamiento que test_reasignacion_resuelve_la_factura_sin_match:
    # este endpoint SI genera un archivo real, EST_REPORTES_DIR tiene que
    # apuntar a tmp_path.
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    desc = 'Hormigón Fc350 kg/cm2, rev. 8"'
    facturas = [{"id_documento": "M800013294", "fecha": "2026-07-02", "descripcion": desc, "cantidad": 5.0}]
    token = _bd_macao2_colision(tmp_path, monkeypatch, facturas)
    client = TestClient(main.app)
    payload = {
        "empresa": "DOMICEM", "fase": "MACAO 2",
        "fecha_desde": "2026-07-01", "fecha_hasta": "2026-07-31",
        "numero_estimacion": "N01", "fecha_estimacion": "2026-08-25", "semana": 1,
        "productos": [
            {"clave": "3", "cantidad_proyecto": 100, "acumulado_anterior_cantidad": 0},
            {"clave": "4", "cantidad_proyecto": 100, "acumulado_anterior_cantidad": 0},
            {"clave": "6", "cantidad_proyecto": 100, "acumulado_anterior_cantidad": 0},
        ],
        "reasignaciones": {desc: "3"},
        "serie": "principal",
    }
    try:
        res = client.post(
            "/api/estimaciones/generar", json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 200, res.text
    data = res.json()
    nombre = data["download_url"].rsplit("/", 1)[-1]
    wb = openpyxl.load_workbook(os.path.join(str(tmp_path), nombre))
    # La hoja RGO usa la clave real del producto, no su posicion secuencial.
    ws = wb["CD-COAF-RGO-03"]
    assert ws.cell(15, 2).value == "3"
    assert ws.cell(core.EST_RGO_FIRST_ROW, 2).value == "M800013294"  # columna B = id_documento
    assert ws.cell(core.EST_RGO_FIRST_ROW, 7).value == 5.0  # columna G = cantidad


def test_vista_previa_producto_sin_colision_sigue_matcheando_automatico(tmp_path, monkeypatch):
    # Regresion: el fix no debe romper el matching normal de un producto
    # que nunca tuvo colision (clave 6, "COLUMNAS MUROS").
    facturas = [{
        "id_documento": "M800099999", "fecha": "2026-07-05",
        "descripcion": 'Hormigón Fc350 kg/cm2, rev. 6"', "cantidad": 8.0,
    }]
    token = _bd_macao2_colision(tmp_path, monkeypatch, facturas)
    client = TestClient(main.app)
    try:
        res = client.get(
            "/api/estimaciones/vista-previa",
            params={"empresa": "DOMICEM", "fase": "MACAO 2",
                    "fecha_desde": "2026-07-01", "fecha_hasta": "2026-07-31"},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 200, res.text
    data = res.json()
    assert data["sin_match"] == []
    por_clave = {c["clave"]: c for c in data["catalogo"]}
    assert por_clave["6"]["facturas_matcheadas"]["cantidad_facturas"] == 1
    assert por_clave["6"]["facturas_matcheadas"]["cantidad_total"] == 8.0
    assert por_clave["3"]["facturas_matcheadas"] is None
    assert por_clave["4"]["facturas_matcheadas"] is None


# ── Issue #11 — Acumulado Anterior en vivo (base fija + facturas reales) ──
# Issue #12 extendio _est_calcular_acumulado_anterior() (borrada) a
# _est_clasificar_series() — mismo comportamiento para fases sin ninguna
# fila de PPACT (fecha_hasta=None se comporta igual que la funcion vieja),
# mas la clasificacion principal/ppact nueva cuando si hay datos sembrados.

def _conn_acumulado(tmp_path, nombre="acumulado_test.db"):
    """Conexion sqlite minima con solo estimacion_acumulado_base y facturas —
    suficiente para probar _est_clasificar_series() de forma aislada, sin
    pasar por HTTP."""
    db_path = tmp_path / nombre
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE estimacion_acumulado_base (
        empresa TEXT, fase TEXT, clave TEXT,
        serie TEXT NOT NULL CHECK (serie IN ('principal','ppact')),
        fecha_base DATE, cantidad_base REAL, cantidad_proyecto_principal REAL,
        PRIMARY KEY (empresa, fase, clave, serie)
    )""")
    conn.execute("""CREATE TABLE facturas (
        id_documento TEXT PRIMARY KEY, fecha DATE, empresa TEXT, fase TEXT,
        descripcion TEXT, cantidad REAL, precio_unitario REAL, clave_resuelta TEXT
    )""")
    return conn


def test_acumulado_suma_facturas_dentro_de_la_ventana(tmp_path):
    conn = _conn_acumulado(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-07-16',1000.0,NULL)"
    )
    conn.execute("INSERT INTO facturas VALUES ('F1','2026-07-20','DOMICEM','MACAO 2','Producto A',50.0,100.0,NULL)")
    conn.execute("INSERT INTO facturas VALUES ('F2','2026-07-25','DOMICEM','MACAO 2','Producto A',30.0,100.0,NULL)")
    conn.commit()
    catalogo = [{"clave": "1", "descripcion": "Producto A"}]
    resultado = core._est_clasificar_series(conn, "DOMICEM", "MACAO 2", catalogo, "2026-08-01")
    assert resultado["por_clave"]["1"]["principal"]["calculado"] == 1080.0
    assert resultado["sin_resolver"] == []


def test_acumulado_producto_sin_fila_base_devuelve_none(tmp_path):
    conn = _conn_acumulado(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-07-16',1000.0,NULL)"
    )
    conn.commit()
    catalogo = [
        {"clave": "1", "descripcion": "Producto A"},
        {"clave": "2", "descripcion": "Producto B"},
    ]
    resultado = core._est_clasificar_series(conn, "DOMICEM", "MACAO 2", catalogo, "2026-08-01")
    assert resultado["por_clave"]["2"]["principal"]["calculado"] is None
    assert resultado["por_clave"]["2"]["ppact"]["calculado"] is None


def test_acumulado_factura_sin_match_va_a_sin_resolver_y_no_se_suma(tmp_path):
    conn = _conn_acumulado(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-07-16',1000.0,NULL)"
    )
    conn.execute("INSERT INTO facturas VALUES ('F1','2026-07-20','DOMICEM','MACAO 2','Descripcion Rara',50.0,100.0,NULL)")
    conn.commit()
    catalogo = [{"clave": "1", "descripcion": "Producto A"}]
    resultado = core._est_clasificar_series(conn, "DOMICEM", "MACAO 2", catalogo, "2026-08-01")
    assert resultado["por_clave"]["1"]["principal"]["calculado"] == 1000.0  # no se le suma nada
    assert resultado["sin_resolver"] == ["Descripcion Rara"]


def test_acumulado_respeta_clave_resuelta_sobre_el_automatch(tmp_path):
    conn = _conn_acumulado(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-06-01',100.0,NULL)"
    )
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','2','principal','2026-06-01',200.0,NULL)"
    )
    # la descripcion matchea "Producto A" (clave 1) por texto, pero clave_resuelta
    # fue guardada manualmente apuntando a la clave 2 (resolucion de una colision
    # historica) — debe respetarse clave_resuelta, no el auto-match por texto
    conn.execute("INSERT INTO facturas VALUES ('F1','2026-06-15','DOMICEM','MACAO 2','Producto A',5.0,100.0,'2')")
    conn.commit()
    catalogo = [
        {"clave": "1", "descripcion": "Producto A"},
        {"clave": "2", "descripcion": "Producto B"},
    ]
    resultado = core._est_clasificar_series(conn, "DOMICEM", "MACAO 2", catalogo, "2026-08-01")
    assert resultado["por_clave"]["1"]["principal"]["calculado"] == 100.0   # no le suma nada
    assert resultado["por_clave"]["2"]["principal"]["calculado"] == 205.0   # se la lleva la clave 2


def test_acumulado_cada_producto_usa_su_propia_fecha_base(tmp_path):
    conn = _conn_acumulado(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-06-01',100.0,NULL)"
    )
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','2','principal','2026-07-16',200.0,NULL)"
    )
    # factura del producto B, fechada ANTES de la base propia de B (pero
    # despues de la base minima global de A) -> no debe sumarse a B, y
    # tampoco debe aparecer en sin_resolver (matcheo, solo que es de antes
    # de su propia base)
    conn.execute("INSERT INTO facturas VALUES ('F1','2026-06-15','DOMICEM','MACAO 2','Producto B',5.0,100.0,NULL)")
    conn.commit()
    catalogo = [
        {"clave": "1", "descripcion": "Producto A"},
        {"clave": "2", "descripcion": "Producto B"},
    ]
    resultado = core._est_clasificar_series(conn, "DOMICEM", "MACAO 2", catalogo, "2026-08-01")
    assert resultado["por_clave"]["2"]["principal"]["calculado"] == 200.0
    assert resultado["sin_resolver"] == []


def test_acumulado_factura_exactamente_en_fecha_base_no_se_suma(tmp_path):
    conn = _conn_acumulado(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-06-01',100.0,NULL)"
    )
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','2','principal','2026-07-16',200.0,NULL)"
    )
    conn.execute("INSERT INTO facturas VALUES ('F1','2026-07-16','DOMICEM','MACAO 2','Producto B',5.0,100.0,NULL)")
    conn.commit()
    catalogo = [
        {"clave": "1", "descripcion": "Producto A"},
        {"clave": "2", "descripcion": "Producto B"},
    ]
    resultado = core._est_clasificar_series(conn, "DOMICEM", "MACAO 2", catalogo, "2026-08-01")
    assert resultado["por_clave"]["2"]["principal"]["calculado"] == 200.0  # no 205 -- fecha > fecha_base es estricto


# ── Issue #12 — contratos paralelos (principal vs PPACT) por producto ──

def test_migracion_estimacion_acumulado_base_a_serie_es_idempotente(tmp_path, monkeypatch):
    """AC #1 / Testing Plan fila 1 — tabla vieja (formato issue #11, sin
    'serie') se migra a serie='principal', cantidad_proyecto_principal=NULL,
    datos intactos. Correr setup_est_db() 2 veces seguidas no rompe nada
    (la columna ya existe la segunda vez, se salta la migracion)."""
    db_path = tmp_path / "est_migracion_serie.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE estimacion_acumulado_base (
        empresa TEXT, fase TEXT, clave TEXT, fecha_base DATE, cantidad_base REAL,
        PRIMARY KEY (empresa, fase, clave)
    )""")
    conn.execute("INSERT INTO estimacion_acumulado_base VALUES ('DOMICEM','MACAO 2','1','2026-07-16',1000.0)")
    conn.execute("INSERT INTO estimacion_acumulado_base VALUES ('DOMICEM','MACAO 2','2','2026-07-16',2000.0)")
    conn.commit()
    conn.close()

    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    core.setup_est_db()

    conn = sqlite3.connect(str(db_path))
    columnas = [c[1] for c in conn.execute("PRAGMA table_info(estimacion_acumulado_base)").fetchall()]
    assert "serie" in columnas
    assert "cantidad_proyecto_principal" in columnas
    filas = conn.execute(
        "SELECT clave, serie, fecha_base, cantidad_base, cantidad_proyecto_principal "
        "FROM estimacion_acumulado_base ORDER BY clave"
    ).fetchall()
    conn.close()
    assert filas == [
        ("1", "principal", "2026-07-16", 1000.0, None),
        ("2", "principal", "2026-07-16", 2000.0, None),
    ]

    core.setup_est_db()  # segunda corrida: columna ya existe, no debe fallar ni duplicar
    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM estimacion_acumulado_base").fetchone()[0]
    conn.close()
    assert count == 2


def test_clasificar_series_no_cruza_tope_todo_va_a_principal(tmp_path):
    conn = _conn_acumulado(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-07-16',90.0,100.0)"
    )
    conn.execute("INSERT INTO facturas VALUES ('F1','2026-07-20','DOMICEM','MACAO 2','Producto A',5.0,100.0,NULL)")
    conn.commit()
    catalogo = [{"clave": "1", "descripcion": "Producto A"}]
    resultado = core._est_clasificar_series(conn, "DOMICEM", "MACAO 2", catalogo, "2026-07-01", "2026-07-31")
    assert resultado["por_clave"]["1"]["principal"]["calculado"] == 90.0
    assert resultado["por_clave"]["1"]["principal"]["tope"] == 100.0
    assert resultado["por_clave"]["1"]["ppact"]["calculado"] is None
    assert resultado["facturas_periodo"] == [("F1", "1", "principal", "2026-07-20", 5.0, 100.0, "Producto A")]
    assert resultado["sin_resolver"] == []


def test_clasificar_series_ya_cruzado_desde_la_base_todo_va_a_ppact(tmp_path):
    """Reproduce el caso real de la clave 7: contrato principal ya al 100%
    desde la base sembrada — cualquier factura nueva clasifica ppact,
    principal.calculado nunca cambia."""
    conn = _conn_acumulado(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','7','principal','2026-07-16',10445.0,10445.0)"
    )
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','7','ppact','2026-07-16',1767.0,NULL)"
    )
    conn.execute("INSERT INTO facturas VALUES ('F1','2026-07-20','DOMICEM','MACAO 2','Losas y Vigas',20.0,191.27,NULL)")
    conn.commit()
    catalogo = [{"clave": "7", "descripcion": "Losas y Vigas"}]
    resultado = core._est_clasificar_series(conn, "DOMICEM", "MACAO 2", catalogo, "2026-07-01", "2026-07-31")
    assert resultado["por_clave"]["7"]["principal"]["calculado"] == 10445.0
    # 'calculado' es SIEMPRE el acumulado ANTERIOR al periodo -- F1 cae
    # DENTRO del periodo (2026-07-20, entre fecha_desde y fecha_hasta), asi
    # que no se suma a ppact.calculado (eso es "esta estimacion", solo
    # aparece en facturas_periodo)
    assert resultado["por_clave"]["7"]["ppact"]["calculado"] == 1767.0
    assert resultado["facturas_periodo"] == [("F1", "7", "ppact", "2026-07-20", 20.0, 191.27, "Losas y Vigas")]


def test_clasificar_series_factura_que_cruzaria_el_tope_va_entera_a_ppact(tmp_path):
    """Reescrito 2026-09-25 (decision de Axel, caso real del 210 de
    CAVERNAS): el lote del periodo SE PARTE factura por factura, pero cada
    factura sigue yendo ENTERA a una serie. Base a 2 unidades del tope:
    F1 (1) cabe -> principal; F2 (5) ya no cabe -> entera a ppact, sin
    dividirse. El acumulado ANTERIOR del principal no cambia (el lote es
    de este periodo)."""
    conn = _conn_acumulado(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-06-30',98.0,100.0)"
    )
    conn.execute("INSERT INTO facturas VALUES ('F1','2026-07-05','DOMICEM','MACAO 2','Producto A',1.0,100.0,NULL)")
    conn.execute("INSERT INTO facturas VALUES ('F2','2026-07-10','DOMICEM','MACAO 2','Producto A',5.0,100.0,NULL)")
    conn.commit()
    catalogo = [{"clave": "1", "descripcion": "Producto A"}]
    resultado = core._est_clasificar_series(conn, "DOMICEM", "MACAO 2", catalogo, "2026-07-01", "2026-07-31")
    facturas = {f[0]: f for f in resultado["facturas_periodo"]}
    assert facturas["F1"][2] == "principal"
    assert facturas["F2"][2] == "ppact"
    assert facturas["F1"][4] == 1.0 and facturas["F2"][4] == 5.0  # cada factura entera, sin dividirse
    assert resultado["por_clave"]["1"]["principal"]["calculado"] == 98.0  # acumulado ANTERIOR intacto
    assert resultado["por_clave"]["1"]["ppact"]["calculado"] == 0.0


# ── Issue #16 — reparto principal/PPACT por lote, el principal no se cierra ──

def test_clasificar_series_lote_que_cabe_entero_va_todo_a_principal(tmp_path):
    """AC #3 (parte lote) — el lote del periodo se evalua UNA vez: base 90
    de tope 100, lote = 4 + 6 = 10 -> 90 + 10 <= 100, TODO a principal."""
    conn = _conn_acumulado(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-06-30',90.0,100.0)"
    )
    conn.execute("INSERT INTO facturas VALUES ('F1','2026-07-05','DOMICEM','MACAO 2','Producto A',4.0,100.0,NULL)")
    conn.execute("INSERT INTO facturas VALUES ('F2','2026-07-10','DOMICEM','MACAO 2','Producto A',6.0,100.0,NULL)")
    conn.commit()
    catalogo = [{"clave": "1", "descripcion": "Producto A"}]
    resultado = core._est_clasificar_series(conn, "DOMICEM", "MACAO 2", catalogo, "2026-07-01", "2026-07-31")
    facturas = {f[0]: f[2] for f in resultado["facturas_periodo"]}
    assert facturas == {"F1": "principal", "F2": "principal"}
    assert resultado["por_clave"]["1"]["principal"]["calculado"] == 90.0
    assert resultado["por_clave"]["1"]["ppact"]["calculado"] is None
    assert resultado["aviso_acumulado_por_factura"] is None


def test_clasificar_series_lote_que_no_cabe_va_entero_a_ppact_y_no_toca_principal(tmp_path):
    """Reescrito 2026-09-25 (decision de Axel) — el lote que no cabe entero
    ya NO va todo a ppact: se parte factura por factura. Acumulado anterior
    95 (90 base + 5 del hueco), 5 libres: F2 (3) cabe -> principal; F3 (4)
    ya no cabe (98 + 4 > 100) -> ppact. El acumulado ANTERIOR queda en 95."""
    conn = _conn_acumulado(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-06-01',90.0,100.0)"
    )
    conn.execute("INSERT INTO facturas VALUES ('F1','2026-06-10','DOMICEM','MACAO 2','Producto A',5.0,100.0,NULL)")
    conn.execute("INSERT INTO facturas VALUES ('F2','2026-07-05','DOMICEM','MACAO 2','Producto A',3.0,100.0,NULL)")
    conn.execute("INSERT INTO facturas VALUES ('F3','2026-07-10','DOMICEM','MACAO 2','Producto A',4.0,100.0,NULL)")
    conn.commit()
    catalogo = [{"clave": "1", "descripcion": "Producto A"}]
    resultado = core._est_clasificar_series(conn, "DOMICEM", "MACAO 2", catalogo, "2026-07-01", "2026-07-31")
    facturas = {f[0]: f[2] for f in resultado["facturas_periodo"]}
    assert facturas == {"F2": "principal", "F3": "ppact"}
    assert resultado["por_clave"]["1"]["principal"]["calculado"] == 95.0
    assert resultado["por_clave"]["1"]["ppact"]["calculado"] == 0.0
    # F1 esta en el hueco fecha_base..fecha_desde -> aviso del AC #6
    assert resultado["aviso_acumulado_por_factura"] == {"facturas": 1}


def test_clasificar_series_principal_no_se_cierra_tras_desborde_anterior(tmp_path):
    """AC #3 — el flag 'crossed' pegajoso murio: en el hueco, F1 (15) no
    cabe y va a ppact, pero F2 (5) posterior SI cabe y vuelve a entrar al
    principal. El lote del periodo (5) tambien cabe (95 + 5 <= 100) y va a
    principal. Con la regla vieja F2 y F3 quedaban condenadas a ppact."""
    conn = _conn_acumulado(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-06-01',90.0,100.0)"
    )
    conn.execute("INSERT INTO facturas VALUES ('F1','2026-06-10','DOMICEM','MACAO 2','Producto A',15.0,100.0,NULL)")
    conn.execute("INSERT INTO facturas VALUES ('F2','2026-06-20','DOMICEM','MACAO 2','Producto A',5.0,100.0,NULL)")
    conn.execute("INSERT INTO facturas VALUES ('F3','2026-07-05','DOMICEM','MACAO 2','Producto A',5.0,100.0,NULL)")
    conn.commit()
    catalogo = [{"clave": "1", "descripcion": "Producto A"}]
    resultado = core._est_clasificar_series(conn, "DOMICEM", "MACAO 2", catalogo, "2026-07-01", "2026-07-31")
    assert resultado["por_clave"]["1"]["principal"]["calculado"] == 95.0  # 90 + F2
    assert resultado["por_clave"]["1"]["ppact"]["calculado"] == 15.0      # solo F1
    assert {f[0]: f[2] for f in resultado["facturas_periodo"]} == {"F3": "principal"}
    assert resultado["aviso_acumulado_por_factura"] == {"facturas": 2}


def test_clasificar_series_sin_tope_todo_sigue_yendo_a_principal(tmp_path):
    """AC #5 — cantidad_proyecto_principal NULL: sin tope no hay reparto,
    hueco y lote enteros al principal, ppact.calculado sigue None."""
    conn = _conn_acumulado(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-06-01',90.0,NULL)"
    )
    conn.execute("INSERT INTO facturas VALUES ('F1','2026-06-10','DOMICEM','MACAO 2','Producto A',1000.0,100.0,NULL)")
    conn.execute("INSERT INTO facturas VALUES ('F2','2026-07-10','DOMICEM','MACAO 2','Producto A',500.0,100.0,NULL)")
    conn.commit()
    catalogo = [{"clave": "1", "descripcion": "Producto A"}]
    resultado = core._est_clasificar_series(conn, "DOMICEM", "MACAO 2", catalogo, "2026-07-01", "2026-07-31")
    assert resultado["por_clave"]["1"]["principal"]["calculado"] == 1090.0
    assert resultado["por_clave"]["1"]["ppact"]["calculado"] is None
    assert {f[0]: f[2] for f in resultado["facturas_periodo"]} == {"F2": "principal"}
    # hay 1 factura en el hueco: el aviso aplica igual (avisa sobre el
    # calculo factura-por-factura del acumulado, tenga o no tope la clave)
    assert resultado["aviso_acumulado_por_factura"] == {"facturas": 1}


def test_clasificar_series_empate_de_fecha_decide_id_documento(tmp_path):
    """Decision fijada en el issue #16: ORDER BY fecha ASC, id_documento
    ASC. Con el replay no pegajoso el orden decide cual factura del hueco
    entra al principal en un empate de fecha: F1 (7) entra primero y F2
    (6) ya no cabe — aunque F2 se haya insertado antes en la BD."""
    conn = _conn_acumulado(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-06-01',0.0,10.0)"
    )
    # F2 insertada ANTES que F1, misma fecha: el orden que manda es id_documento
    conn.execute("INSERT INTO facturas VALUES ('F2','2026-06-10','DOMICEM','MACAO 2','Producto A',6.0,100.0,NULL)")
    conn.execute("INSERT INTO facturas VALUES ('F1','2026-06-10','DOMICEM','MACAO 2','Producto A',7.0,100.0,NULL)")
    conn.commit()
    catalogo = [{"clave": "1", "descripcion": "Producto A"}]
    resultado = core._est_clasificar_series(conn, "DOMICEM", "MACAO 2", catalogo, "2026-07-01", "2026-07-31")
    assert resultado["por_clave"]["1"]["principal"]["calculado"] == 7.0  # F1 (id menor) entro
    assert resultado["por_clave"]["1"]["ppact"]["calculado"] == 6.0      # F2 no cupo


def test_clasificar_series_factura_sin_match_no_se_suma_a_ninguna_serie(tmp_path):
    conn = _conn_acumulado(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-07-16',1000.0,NULL)"
    )
    conn.execute("INSERT INTO facturas VALUES ('F1','2026-07-20','DOMICEM','MACAO 2','Descripcion Rara',50.0,100.0,NULL)")
    conn.commit()
    catalogo = [{"clave": "1", "descripcion": "Producto A"}]
    resultado = core._est_clasificar_series(conn, "DOMICEM", "MACAO 2", catalogo, "2026-07-01", "2026-07-31")
    assert resultado["por_clave"]["1"]["principal"]["calculado"] == 1000.0
    assert resultado["facturas_periodo"] == []
    assert resultado["sin_resolver"] == ["Descripcion Rara"]


def test_vista_previa_devuelve_principal_y_ppact_caso_real_clave7(tmp_path, monkeypatch):
    """AC #3/#4 — integration: replica el caso real (base principal=tope=100,
    base ppact=50, 1 factura nueva de 20 despues de la fecha base) ->
    principal.calculado=100, ppact.calculado=70."""
    db_path = tmp_path / "est_ppact_vista.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE catalogo_estimacion (
        empresa TEXT, fase TEXT, orden INTEGER, clave TEXT,
        descripcion TEXT, precio_unitario REAL,
        PRIMARY KEY (empresa, fase, orden)
    )""")
    conn.execute("""CREATE TABLE facturas (
        id_documento TEXT PRIMARY KEY, fecha DATE, empresa TEXT, fase TEXT,
        descripcion TEXT, cantidad REAL, precio_unitario REAL, clave_resuelta TEXT
    )""")
    conn.execute("""CREATE TABLE estimacion_acumulado_base (
        empresa TEXT, fase TEXT, clave TEXT,
        serie TEXT NOT NULL CHECK (serie IN ('principal','ppact')),
        fecha_base DATE, cantidad_base REAL, cantidad_proyecto_principal REAL,
        PRIMARY KEY (empresa, fase, clave, serie)
    )""")
    conn.execute("INSERT INTO catalogo_estimacion VALUES ('DOMICEM','MACAO 2',1,'7','Losas y Vigas Hidrofugo',191.27)")
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','7','principal','2026-07-16',100.0,100.0)"
    )
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','7','ppact','2026-07-16',50.0,NULL)"
    )
    conn.execute(
        "INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,cantidad,precio_unitario) "
        "VALUES ('F1','2026-07-20','DOMICEM','MACAO 2','Losas y Vigas Hidrofugo',20.0,191.27)"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))

    token = "test-token-ppact-vista"
    core.active_tokens[token] = datetime.now()
    try:
        client = TestClient(main.app)
        res = client.get(
            "/api/estimaciones/vista-previa",
            params={"empresa": "DOMICEM", "fase": "MACAO 2",
                    "fecha_desde": "2026-08-01", "fecha_hasta": "2026-08-31"},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 200, res.text
    data = res.json()
    por_clave = {c["clave"]: c for c in data["catalogo"]}
    assert por_clave["7"]["principal"]["calculado"] == 100.0
    assert por_clave["7"]["principal"]["tope"] == 100.0
    assert por_clave["7"]["ppact"]["calculado"] == 70.0


def _bd_macao2_ppact_generar(tmp_path, monkeypatch, facturas):
    """BD MACAO 2 (catalogo torres/grua, reusa _bd_macao2_colision) + clave 6
    (sin colision) a 2 unidades de su tope de contrato principal — para
    probar POST /generar con serie=principal/ppact."""
    token = _bd_macao2_colision(tmp_path, monkeypatch, facturas)
    conn = sqlite3.connect(core.EST_DB_PATH)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','6','principal','2026-06-30',98.0,100.0)"
    )
    conn.commit()
    conn.close()
    return token


def _payload_generar_ppact_macao2(serie):
    return {
        "empresa": "DOMICEM", "fase": "MACAO 2",
        "fecha_desde": "2026-07-01", "fecha_hasta": "2026-07-31",
        "numero_estimacion": "N01", "fecha_estimacion": "2026-08-25", "semana": 1,
        "productos": [
            {"clave": "3", "cantidad_proyecto": 100, "acumulado_anterior_cantidad": 0},
            {"clave": "4", "cantidad_proyecto": 100, "acumulado_anterior_cantidad": 0},
            {"clave": "6", "cantidad_proyecto": 100, "acumulado_anterior_cantidad": 0},
        ],
        "reasignaciones": {},
        "serie": serie,
    }


def test_generar_excluir_producto_deja_el_renglon_con_su_acumulado(tmp_path, monkeypatch):
    """Excluir un producto en la pantalla de revision NO lo saca del documento:
    el renglon sale completo en REO-01 con su clave, concepto, U.M., Cant.
    Proyecto, P.U. y sobre todo su Acumulado Anterior (columna H) — el usuario
    fue explicito: "lo acumulado se tiene que quedar". Lo unico que se omite es
    la columna "Esta Estimacion" (K) y su hoja de generadores."""
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    desc = 'Hormigón Fc350 kg/cm2, rev. 6"'
    facturas = [
        {"id_documento": "M1", "fecha": "2026-07-05", "descripcion": desc, "cantidad": 1.0},
    ]
    token = _bd_macao2_ppact_generar(tmp_path, monkeypatch, facturas)
    payload = _payload_generar_ppact_macao2("principal")
    # clave 6 es la que matchea `desc` (ver el test de al lado); se excluye
    payload["excluidos"] = ["6"]
    payload["productos"] = [
        {"clave": p["clave"], "cantidad_proyecto": 100, "acumulado_anterior_cantidad": 77.5}
        for p in payload["productos"]
    ]
    client = TestClient(main.app)
    try:
        res = client.post("/api/estimaciones/generar", json=payload,
                          headers={"Authorization": f"Bearer {token}"})
    finally:
        core.active_tokens.pop(token, None)

    # todas las facturas del periodo eran del producto excluido -> 422 claro
    assert res.status_code == 422, res.text
    assert res.json()["detail"]["error"] == "sin_facturas_en_periodo"
    assert "excluidas" in res.json()["detail"]["detalle"]


def test_generar_excluir_uno_de_dos_productos(tmp_path, monkeypatch):
    """Con 2 productos con entregas y 1 excluido: el excluido conserva su
    Acumulado Anterior y su Cant. Proyecto en REO-01 pero queda SIN valor en
    "Esta Estimacion" (K) y SIN hoja de generadores; el otro sale entero."""
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    desc6 = 'Hormigón Fc350 kg/cm2, rev. 6"'
    facturas = [
        {"id_documento": "M1", "fecha": "2026-07-05", "descripcion": desc6, "cantidad": 1.0},
    ]
    token = _bd_macao2_ppact_generar(tmp_path, monkeypatch, facturas)
    # 2do producto con entregas: la clave 3 arrastra la colision real
    # Torres/Grua (mismo texto normalizado que la 4), asi que no puede
    # auto-matchear — se le pone clave_resuelta, que es como se resuelve en la
    # realidad una vez que alguien la asigno a mano una vez (issue #11)
    conn = sqlite3.connect(core.EST_DB_PATH)
    conn.execute(
        "INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,cantidad,precio_unitario,clave_resuelta) "
        "VALUES ('M9','2026-07-06','DOMICEM','MACAO 2',?,4.0,191.27,'3')",
        ('Hormigón Fc350 kg/cm2, rev. 8"',),
    )
    conn.commit()
    conn.close()
    payload = _payload_generar_ppact_macao2("principal")
    payload["excluidos"] = ["6"]
    payload["productos"] = [
        {"clave": p["clave"], "cantidad_proyecto": 100, "acumulado_anterior_cantidad": 77.5}
        for p in payload["productos"]
    ]
    client = TestClient(main.app)
    try:
        res = client.post("/api/estimaciones/generar", json=payload,
                          headers={"Authorization": f"Bearer {token}"})
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 200, res.text
    nombre = res.json()["download_url"].rsplit("/", 1)[-1]
    wb = openpyxl.load_workbook(os.path.join(str(tmp_path), nombre))
    reo = wb["CD-COAF-REO-01"]

    conn = sqlite3.connect(core.EST_DB_PATH)
    orden = {c["clave"]: c["orden"] for c in core._est_catalogo_fase(conn, "DOMICEM", "MACAO 2")}
    conn.close()
    fila_excl = core.EST_REO_FIRST_ROW + (orden["6"] - 1)
    fila_ok = core.EST_REO_FIRST_ROW + (orden["3"] - 1)

    # el renglon EXCLUIDO conserva todo lo que no es "esta estimacion"
    # La columna A lleva la CLAVE, no el orden. Esta fase las tiene iguales,
    # asi que la asercion pasaba con las dos; el caso que las distingue esta
    # en test_reo_columna_a_lleva_la_clave_no_el_orden (VMO/PATIO DE
    # MANIOBRAS-TRA es la unica fase real con orden != clave).
    assert reo.cell(fila_excl, 1).value == int("6")
    assert reo.cell(fila_excl, 2).value  # concepto presente
    assert reo.cell(fila_excl, 3).value == "m3"
    assert reo.cell(fila_excl, 4).value == 100          # Cant. Proyecto
    assert reo.cell(fila_excl, 8).value == 77.5         # Acumulado Anterior — lo que el usuario pidio conservar
    assert reo.cell(fila_excl, 11).value is None        # "Esta Estimacion" vacia

    # el renglon NO excluido si trae su formula a la hoja de generadores
    assert reo.cell(fila_ok, 8).value == 77.5
    assert str(reo.cell(fila_ok, 11).value or "").startswith("='CD-COAF-RGO-")

    # solo se creo la hoja del producto NO excluido, y con su factura
    hojas_rgo = [s for s in wb.sheetnames if s.startswith("CD-COAF-RGO-")]
    assert len(hojas_rgo) == 1
    ws = wb[hojas_rgo[0]]
    assert ws.cell(15, 2).value == "3"
    assert ws.cell(core.EST_RGO_FIRST_ROW, 2).value == "M9"


def test_generar_excluir_clave_inexistente_da_400(tmp_path, monkeypatch):
    """Excluir una clave que no existe en el catalogo de la fase falla claro en
    vez de ignorarse en silencio (generaria un documento oficial distinto al
    que el usuario creyo pedir)."""
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    desc = 'Hormigón Fc350 kg/cm2, rev. 6"'
    facturas = [{"id_documento": "M1", "fecha": "2026-07-05", "descripcion": desc, "cantidad": 1.0}]
    token = _bd_macao2_ppact_generar(tmp_path, monkeypatch, facturas)
    payload = _payload_generar_ppact_macao2("principal")
    payload["excluidos"] = ["999"]
    client = TestClient(main.app)
    try:
        res = client.post("/api/estimaciones/generar", json=payload,
                          headers={"Authorization": f"Bearer {token}"})
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 400, res.text
    assert res.json()["detail"]["error"] == "excluidos_desconocidos"
    assert res.json()["detail"]["detalle"] == ["999"]


def test_generar_sin_excluidos_es_identico_a_antes(tmp_path, monkeypatch):
    """Regresion: no mandar `excluidos` (o mandarlo vacio) tiene que dar
    exactamente el mismo resultado que antes de esta feature — el campo tiene
    default [] y no cambia nada del flujo existente."""
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    desc = 'Hormigón Fc350 kg/cm2, rev. 6"'
    facturas = [{"id_documento": "M1", "fecha": "2026-07-05", "descripcion": desc, "cantidad": 1.0}]
    token = _bd_macao2_ppact_generar(tmp_path, monkeypatch, facturas)
    client = TestClient(main.app)
    try:
        sin_campo = client.post("/api/estimaciones/generar",
                                json=_payload_generar_ppact_macao2("principal"),
                                headers={"Authorization": f"Bearer {token}"})
        payload_vacio = _payload_generar_ppact_macao2("principal")
        payload_vacio["excluidos"] = []
        con_vacio = client.post("/api/estimaciones/generar", json=payload_vacio,
                                headers={"Authorization": f"Bearer {token}"})
    finally:
        core.active_tokens.pop(token, None)

    assert sin_campo.status_code == 200, sin_campo.text
    assert con_vacio.status_code == 200, con_vacio.text
    assert sin_campo.json()["total_facturas"] == con_vacio.json()["total_facturas"] == 1


def test_generar_serie_principal_usa_oc_contrato_y_solo_facturas_principal(tmp_path, monkeypatch):
    """AC #5 del issue #12 — POST /generar con serie='principal' escribe M9
    con el valor existente de EST_OC_CONTRATO y solo incluye facturas
    principal. Adaptado por el issue #16: la clasificacion ahora es por
    LOTE por clave, asi que la mezcla principal/ppact viene de DOS claves
    (el lote de la 6 cabe -> principal; el de la 3 no -> ppact), ya no de
    dos facturas de la misma clave."""
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    # descripcion de FACTURA real (sin la etiqueta de elemento estructural
    # en mayusculas — Vision no la puede leer, no esta en el documento
    # fisico; _est_normalizar_catalogo() la quita del lado del catalogo
    # para poder matchear, ver test_vista_previa_producto_sin_colision_...)
    desc = 'Hormigón Fc350 kg/cm2, rev. 6"'
    facturas = [
        {"id_documento": "M1", "fecha": "2026-07-05", "descripcion": desc, "cantidad": 1.0},
        {"id_documento": "M2", "fecha": "2026-07-10", "descripcion": desc, "cantidad": 1.0},
        # clave 3 (via clave_resuelta, su descripcion colisiona con la 4):
        # su base ya esta al tope -> el lote de la clave 3 va a ppact
        {"id_documento": "M3", "fecha": "2026-07-08", "descripcion": "Torres", "cantidad": 4.0,
         "clave_resuelta": "3"},
    ]
    token = _bd_macao2_ppact_generar(tmp_path, monkeypatch, facturas)
    conn = sqlite3.connect(core.EST_DB_PATH)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','3','principal','2026-06-30',100.0,100.0)"
    )
    conn.commit()
    conn.close()
    client = TestClient(main.app)
    try:
        res = client.post(
            "/api/estimaciones/generar", json=_payload_generar_ppact_macao2("principal"),
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 200, res.text
    data = res.json()
    # lote clave 6 = 1 + 1 = 2, base 98 de tope 100 -> cabe justo, las DOS
    # a principal; M3 (clave 3, ppact) queda afuera de esta serie
    assert data["total_facturas"] == 2
    assert data["aviso_acumulado_por_factura"] is None  # sin facturas en el hueco
    nombre = data["download_url"].rsplit("/", 1)[-1]
    wb = openpyxl.load_workbook(os.path.join(str(tmp_path), nombre))
    assert wb["CD-COAF-REO-01"]["M9"].value == int(core.EST_OC_CONTRATO[("DOMICEM", "MACAO 2")])
    ws = wb["CD-COAF-RGO-06"]
    assert ws.cell(15, 2).value == "6"
    assert ws.cell(core.EST_RGO_FIRST_ROW, 2).value == "M1"
    assert ws.cell(core.EST_RGO_FIRST_ROW, 7).value == 1.0
    assert ws.cell(core.EST_RGO_FIRST_ROW + 1, 2).value == "M2"


def test_generar_serie_ppact_usa_oc_ppact_y_solo_facturas_ppact(tmp_path, monkeypatch):
    """AC #6 del issue #12 — POST /generar con serie='ppact' escribe
    M9='PPACT' y solo incluye facturas clasificadas como ppact. Adaptado
    2026-09-25 (decision de Axel, lote partido por factura): de la clave 6
    con 2 libres, M1 (1) cabe y va a principal; M2 (5) no cabe y va a
    ppact — el documento ppact lleva SOLO a M2."""
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    # descripcion de FACTURA real (sin la etiqueta de elemento estructural
    # en mayusculas — Vision no la puede leer, no esta en el documento
    # fisico; _est_normalizar_catalogo() la quita del lado del catalogo
    # para poder matchear, ver test_vista_previa_producto_sin_colision_...)
    desc = 'Hormigón Fc350 kg/cm2, rev. 6"'
    facturas = [
        {"id_documento": "M1", "fecha": "2026-07-05", "descripcion": desc, "cantidad": 1.0},
        {"id_documento": "M2", "fecha": "2026-07-10", "descripcion": desc, "cantidad": 5.0},
        # clave 3 con margen de sobra -> su lote va a principal, queda
        # afuera de la serie ppact
        {"id_documento": "M3", "fecha": "2026-07-08", "descripcion": "Torres", "cantidad": 4.0,
         "clave_resuelta": "3"},
    ]
    token = _bd_macao2_ppact_generar(tmp_path, monkeypatch, facturas)
    conn = sqlite3.connect(core.EST_DB_PATH)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','3','principal','2026-06-30',0.0,100.0)"
    )
    conn.commit()
    conn.close()
    client = TestClient(main.app)
    try:
        res = client.post(
            "/api/estimaciones/generar", json=_payload_generar_ppact_macao2("ppact"),
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total_facturas"] == 1  # solo M2 (M1 cupo en el principal)
    nombre = data["download_url"].rsplit("/", 1)[-1]
    wb = openpyxl.load_workbook(os.path.join(str(tmp_path), nombre))
    assert wb["CD-COAF-REO-01"]["M9"].value == "PPACT"
    ws = wb["CD-COAF-RGO-06"]
    assert ws.cell(15, 2).value == "6"
    assert ws.cell(core.EST_RGO_FIRST_ROW, 2).value == "M2"
    assert ws.cell(core.EST_RGO_FIRST_ROW, 7).value == 5.0
    assert ws.cell(core.EST_RGO_FIRST_ROW + 1, 2).value is None


# ── Issue #16 — integracion: caso real VMO/CEDIS clave 2 (N06) y aviso AC #6 ──

_CEDIS_DESC_FC100 = 'Hormigón Fc100 kg/cm2, Agg 3/4", Temp. 35C, rev. 6"+/- 1".'


def _bd_cedis_clave2(tmp_path, monkeypatch):
    """Replica el caso real del issue #16: VMO/CEDIS clave 2 sembrada del
    documento de la empresa (fecha_base 2026-07-16, cantidad_base 23,
    tope 29 -> 6 m3 libres) y las dos entregas reales del 17-jul-2026:
    M800013832 (5.0 m3) y M800013843 (2.0 m3)."""
    db_path = tmp_path / "est_cedis_clave2.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE catalogo_estimacion (
        empresa TEXT, fase TEXT, orden INTEGER, clave TEXT,
        descripcion TEXT, precio_unitario REAL,
        PRIMARY KEY (empresa, fase, orden)
    )""")
    conn.execute("""CREATE TABLE facturas (
        id_documento TEXT PRIMARY KEY, fecha DATE, empresa TEXT, fase TEXT,
        descripcion TEXT, cantidad REAL, precio_unitario REAL, clave_resuelta TEXT
    )""")
    conn.execute("""CREATE TABLE estimacion_acumulado_base (
        empresa TEXT, fase TEXT, clave TEXT,
        serie TEXT NOT NULL CHECK (serie IN ('principal','ppact')),
        fecha_base DATE, cantidad_base REAL, cantidad_proyecto_principal REAL,
        PRIMARY KEY (empresa, fase, clave, serie)
    )""")
    conn.execute(
        "INSERT INTO catalogo_estimacion VALUES ('VMO','CEDIS',1,'2',?,109.0)",
        (_CEDIS_DESC_FC100,),
    )
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('VMO','CEDIS','2','principal','2026-07-16',23.0,29.0)"
    )
    for id_doc, cantidad in (("M800013832", 5.0), ("M800013843", 2.0)):
        conn.execute(
            "INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,cantidad,precio_unitario) "
            "VALUES (?,'2026-07-17','VMO','CEDIS',?,?,106.7)",
            (id_doc, _CEDIS_DESC_FC100, cantidad),
        )
    conn.commit()
    conn.close()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    token = "test-token-cedis-clave2"
    core.active_tokens[token] = datetime.now()
    return token


def test_vista_previa_cedis_clave_2_lote_entero_a_ppact(tmp_path, monkeypatch):
    """Reescrito 2026-09-25 (decision de Axel, lote partido por factura).
    OJO: el N06 REAL de la empresa habia mandado los 7.0 enteros a ppact
    (la regla vieja del issue #16 salia de ese documento); con la regla
    nueva el mismo caso da M800013832 (5) a principal (23+5 <= 29) y
    M800013843 (2) a ppact (28+2 > 29). El acumulado ANTERIOR queda en
    23/29."""
    token = _bd_cedis_clave2(tmp_path, monkeypatch)
    client = TestClient(main.app)
    try:
        res = client.get(
            "/api/estimaciones/vista-previa",
            params={"empresa": "VMO", "fase": "CEDIS",
                    "fecha_desde": "2026-07-17", "fecha_hasta": "2026-08-16"},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 200, res.text
    data = res.json()
    por_clave = {c["clave"]: c for c in data["catalogo"]}
    assert por_clave["2"]["principal"]["calculado"] == 23.0  # acumulado ANTERIOR en 23/29
    assert por_clave["2"]["principal"]["tope"] == 29.0
    series = {f["id_documento"]: f["serie"] for f in data["facturas_periodo"]}
    assert series == {"M800013832": "principal", "M800013843": "ppact"}
    assert sum(f["cantidad"] for f in data["facturas_periodo"] if f["serie"] == "ppact") == 2.0
    # sin facturas en el hueco (fecha_base 16-jul, desde 17-jul) -> sin aviso
    assert data["aviso_acumulado_por_factura"] is None


def test_generar_cedis_clave_2_ppact_lleva_las_dos_facturas_y_principal_queda_vacio(tmp_path, monkeypatch):
    """Reescrito 2026-09-25 (decision de Axel, lote partido por factura):
    serie='ppact' genera solo con M800013843 (2.0 m3, la que no cupo);
    serie='principal' ahora SI tiene una factura (M800013832, 5.0) y
    genera 200."""
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    token = _bd_cedis_clave2(tmp_path, monkeypatch)
    payload = {
        "empresa": "VMO", "fase": "CEDIS",
        "fecha_desde": "2026-07-17", "fecha_hasta": "2026-08-16",
        "numero_estimacion": "N06", "fecha_estimacion": "2026-08-20", "semana": 1,
        "productos": [{"clave": "2", "cantidad_proyecto": 29, "acumulado_anterior_cantidad": 23}],
        "reasignaciones": {},
        "serie": "ppact",
    }
    client = TestClient(main.app)
    try:
        res_ppact = client.post(
            "/api/estimaciones/generar", json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        res_principal = client.post(
            "/api/estimaciones/generar", json={**payload, "serie": "principal"},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)

    assert res_ppact.status_code == 200, res_ppact.text
    data = res_ppact.json()
    assert data["total_facturas"] == 1  # solo M800013843 (2.0 m3)
    assert data["aviso_acumulado_por_factura"] is None
    nombre = data["download_url"].rsplit("/", 1)[-1]
    wb = openpyxl.load_workbook(os.path.join(str(tmp_path), nombre))
    assert wb["CD-COAF-REO-01"]["M9"].value == "PPACT"

    assert res_principal.status_code == 200, res_principal.text
    assert res_principal.json()["total_facturas"] == 1  # M800013832 (5.0 m3)


def test_vista_previa_aviso_acumulado_por_factura_agrega_por_fase(tmp_path, monkeypatch):
    """AC #6 — con facturas en el hueco fecha_base..fecha_desde el aviso
    aparece con el TOTAL de la fase (2 claves con 1 factura cada una ->
    {"facturas": 2}, un solo aviso por pantalla, no por clave)."""
    db_path = tmp_path / "est_aviso_hueco.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE catalogo_estimacion (
        empresa TEXT, fase TEXT, orden INTEGER, clave TEXT,
        descripcion TEXT, precio_unitario REAL,
        PRIMARY KEY (empresa, fase, orden)
    )""")
    conn.execute("""CREATE TABLE facturas (
        id_documento TEXT PRIMARY KEY, fecha DATE, empresa TEXT, fase TEXT,
        descripcion TEXT, cantidad REAL, precio_unitario REAL, clave_resuelta TEXT
    )""")
    conn.execute("""CREATE TABLE estimacion_acumulado_base (
        empresa TEXT, fase TEXT, clave TEXT,
        serie TEXT NOT NULL CHECK (serie IN ('principal','ppact')),
        fecha_base DATE, cantidad_base REAL, cantidad_proyecto_principal REAL,
        PRIMARY KEY (empresa, fase, clave, serie)
    )""")
    conn.execute("INSERT INTO catalogo_estimacion VALUES ('DOMICEM','MACAO 2',1,'6','Hormigón Fc350 kg/cm2, rev. 6\"',191.27)")
    conn.execute("INSERT INTO catalogo_estimacion VALUES ('DOMICEM','MACAO 2',2,'7','Losas y Vigas Hidrofugo',191.27)")
    for clave in ("6", "7"):
        conn.execute(
            "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
            "VALUES ('DOMICEM','MACAO 2',?, 'principal','2026-06-30',10.0,NULL)", (clave,)
        )
    # 1 factura de cada clave en el hueco (2026-06-30 < fecha < 2026-08-01)
    conn.execute("INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,cantidad,precio_unitario) "
                 "VALUES ('H1','2026-07-10','DOMICEM','MACAO 2','Hormigón Fc350 kg/cm2, rev. 6\"',3.0,191.27)")
    conn.execute("INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,cantidad,precio_unitario) "
                 "VALUES ('H2','2026-07-12','DOMICEM','MACAO 2','Losas y Vigas Hidrofugo',4.0,191.27)")
    # y 1 dentro del periodo, para que la vista tenga algo que mostrar
    conn.execute("INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,cantidad,precio_unitario) "
                 "VALUES ('P1','2026-08-05','DOMICEM','MACAO 2','Losas y Vigas Hidrofugo',1.0,191.27)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    token = "test-token-aviso-hueco"
    core.active_tokens[token] = datetime.now()
    client = TestClient(main.app)
    try:
        res = client.get(
            "/api/estimaciones/vista-previa",
            params={"empresa": "DOMICEM", "fase": "MACAO 2",
                    "fecha_desde": "2026-08-01", "fecha_hasta": "2026-08-31"},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 200, res.text
    assert res.json()["aviso_acumulado_por_factura"] == {"facturas": 2}


def test_generar_aviso_acumulado_por_factura_con_y_sin_hueco(tmp_path, monkeypatch):
    """AC #6 en /generar — con una factura en el hueco el JSON trae
    {"facturas": 1}; sin hueco (mismo fixture, periodo que arranca en la
    fecha de la primera factura) trae None. El aviso no bloquea: ambas
    generaciones devuelven 200."""
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    desc = 'Hormigón Fc350 kg/cm2, rev. 6"'
    facturas = [
        {"id_documento": "H1", "fecha": "2026-07-03", "descripcion": desc, "cantidad": 1.0},
        {"id_documento": "M1", "fecha": "2026-07-10", "descripcion": desc, "cantidad": 1.0},
    ]
    token = _bd_macao2_ppact_generar(tmp_path, monkeypatch, facturas)
    client = TestClient(main.app)
    try:
        # H1 (03-jul) queda en el hueco 2026-06-30..2026-07-08 -> aviso
        payload_con_hueco = {**_payload_generar_ppact_macao2("principal"), "fecha_desde": "2026-07-08"}
        res_con = client.post(
            "/api/estimaciones/generar", json=payload_con_hueco,
            headers={"Authorization": f"Bearer {token}"},
        )
        # periodo desde 2026-07-01: no hay fechas posibles entre la
        # fecha_base (2026-06-30) y fecha_desde -> hueco vacio, sin aviso
        res_sin = client.post(
            "/api/estimaciones/generar", json=_payload_generar_ppact_macao2("principal"),
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)

    assert res_con.status_code == 200, res_con.text
    assert res_con.json()["aviso_acumulado_por_factura"] == {"facturas": 1}
    assert res_con.json()["total_facturas"] == 1  # solo M1; H1 es acumulado anterior

    assert res_sin.status_code == 200, res_sin.text
    assert res_sin.json()["aviso_acumulado_por_factura"] is None
    assert res_sin.json()["total_facturas"] == 2  # H1 y M1 caen en el periodo


def test_generar_serie_invalida_o_ausente_da_422(bd_sintetica):
    """AC #7 — serie con un valor que no sea 'principal'/'ppact', o
    ausente, responde 422 (validacion de Pydantic)."""
    client = TestClient(main.app)

    payload_invalida = _payload_base(bd_sintetica, serie="otra")
    res_invalida = client.post(
        "/api/estimaciones/generar", json=payload_invalida,
        headers={"Authorization": f"Bearer {bd_sintetica}"},
    )
    assert res_invalida.status_code == 422

    payload_sin_serie = _payload_base(bd_sintetica)
    del payload_sin_serie["serie"]
    res_sin_serie = client.post(
        "/api/estimaciones/generar", json=payload_sin_serie,
        headers={"Authorization": f"Bearer {bd_sintetica}"},
    )
    assert res_sin_serie.status_code == 422


def test_generar_serie_ppact_sin_facturas_da_sin_facturas_en_periodo(bd_sintetica):
    """POST /generar con serie='ppact' para un periodo donde nada cruzo
    todavia (fase sintetica sin ninguna fila de PPACT -> todo es 'principal')
    responde el mismo error 422 sin_facturas_en_periodo ya existente."""
    client = TestClient(main.app)
    payload = _payload_base(
        bd_sintetica,
        reasignaciones={"Descripcion Rara Sin Match": "2"},
        serie="ppact",
    )
    res = client.post(
        "/api/estimaciones/generar", json=payload,
        headers={"Authorization": f"Bearer {bd_sintetica}"},
    )
    assert res.status_code == 422
    assert res.json()["detail"]["error"] == "sin_facturas_en_periodo"


def test_vista_previa_incluye_principal_calculado(tmp_path, monkeypatch):
    db_path = tmp_path / "est_acumulado_vista.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE catalogo_estimacion (
        empresa TEXT, fase TEXT, orden INTEGER, clave TEXT,
        descripcion TEXT, precio_unitario REAL,
        PRIMARY KEY (empresa, fase, orden)
    )""")
    conn.execute("""CREATE TABLE facturas (
        id_documento TEXT PRIMARY KEY, fecha DATE, empresa TEXT, fase TEXT,
        descripcion TEXT, cantidad REAL, precio_unitario REAL, clave_resuelta TEXT
    )""")
    conn.execute("""CREATE TABLE estimacion_acumulado_base (
        empresa TEXT, fase TEXT, clave TEXT,
        serie TEXT NOT NULL CHECK (serie IN ('principal','ppact')),
        fecha_base DATE, cantidad_base REAL, cantidad_proyecto_principal REAL,
        PRIMARY KEY (empresa, fase, clave, serie)
    )""")
    conn.execute("INSERT INTO catalogo_estimacion VALUES ('VMO','CEDIS',1,'1','Producto Uno',100.0)")
    conn.execute("INSERT INTO catalogo_estimacion VALUES ('VMO','CEDIS',2,'2','Producto Dos',200.0)")
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('VMO','CEDIS','1','principal','2026-07-16',1000.0,NULL)"
    )
    conn.execute(
        "INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,cantidad,precio_unitario) "
        "VALUES ('F1','2026-07-20','VMO','CEDIS','Producto Uno',50.0,100.0)"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))

    token = "test-token-acumulado-vista"
    core.active_tokens[token] = datetime.now()
    try:
        client = TestClient(main.app)
        res = client.get(
            "/api/estimaciones/vista-previa",
            params={"empresa": "VMO", "fase": "CEDIS",
                    "fecha_desde": "2026-08-01", "fecha_hasta": "2026-08-31"},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 200, res.text
    data = res.json()
    por_clave = {c["clave"]: c for c in data["catalogo"]}
    assert por_clave["1"]["principal"]["calculado"] == 1050.0  # 1000 base + 50 factura
    assert por_clave["1"]["ppact"]["calculado"] is None
    assert por_clave["2"]["principal"]["calculado"] is None
    assert por_clave["2"]["ppact"]["calculado"] is None
    assert data["sin_resolver"] == []


def test_generar_persiste_clave_resuelta_solo_para_facturas_del_periodo(tmp_path, monkeypatch):
    desc = 'Hormigón Fc350 kg/cm2, rev. 8"'
    facturas = [
        {"id_documento": "M800013294", "fecha": "2026-07-02", "descripcion": desc, "cantidad": 5.0},
        {"id_documento": "M800013295", "fecha": "2026-07-10", "descripcion": desc, "cantidad": 3.0},
        # misma descripcion, fecha FUERA del periodo que se va a generar --
        # no debe quedar resuelta (prueba que la persistencia es por
        # id_documento de esta generacion, nunca un UPDATE por descripcion)
        {"id_documento": "M800013296", "fecha": "2026-05-01", "descripcion": desc, "cantidad": 9.0},
    ]
    token = _bd_macao2_colision(tmp_path, monkeypatch, facturas)
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    client = TestClient(main.app)
    payload = {
        "empresa": "DOMICEM", "fase": "MACAO 2",
        "fecha_desde": "2026-07-01", "fecha_hasta": "2026-07-31",
        "numero_estimacion": "N01", "fecha_estimacion": "2026-08-25", "semana": 1,
        "productos": [
            {"clave": "3", "cantidad_proyecto": 100, "acumulado_anterior_cantidad": 0},
            {"clave": "4", "cantidad_proyecto": 100, "acumulado_anterior_cantidad": 0},
            {"clave": "6", "cantidad_proyecto": 100, "acumulado_anterior_cantidad": 0},
        ],
        "reasignaciones": {desc: "3"},
        "serie": "principal",
    }
    try:
        res = client.post(
            "/api/estimaciones/generar", json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 200, res.text

    conn = sqlite3.connect(core.EST_DB_PATH)
    filas = {r[0]: r[1] for r in conn.execute("SELECT id_documento, clave_resuelta FROM facturas").fetchall()}
    conn.close()
    assert filas["M800013294"] == "3"
    assert filas["M800013295"] == "3"
    assert filas["M800013296"] is None  # fuera del periodo generado -- nunca se toco


def test_generar_clave_resuelta_obsoleta_cae_a_reasignaciones_o_bloquea(bd_sintetica, tmp_path, monkeypatch):
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    # simula un catalogo que cambio despues de guardar la resolucion: F002
    # quedo con clave_resuelta='99', una clave que ya no existe en el catalogo
    conn = sqlite3.connect(core.EST_DB_PATH)
    conn.execute("UPDATE facturas SET clave_resuelta = '99' WHERE id_documento = 'F002'")
    conn.commit()
    conn.close()

    client = TestClient(main.app)

    # sin reasignacion nueva -> la clave_resuelta obsoleta no cuenta como
    # resuelta, cae a sin_resolver igual que si nunca se hubiera resuelto
    payload_sin = _payload_base(bd_sintetica)
    res_sin = client.post(
        "/api/estimaciones/generar", json=payload_sin,
        headers={"Authorization": f"Bearer {bd_sintetica}"},
    )
    assert res_sin.status_code == 400
    assert res_sin.json()["detail"]["error"] == "facturas_sin_resolver"
    assert "Descripcion Rara Sin Match" in res_sin.json()["detail"]["detalle"]

    # con una reasignacion nueva -> se usa esa, no la clave_resuelta vieja/invalida
    payload_con = _payload_base(bd_sintetica, reasignaciones={"Descripcion Rara Sin Match": "2"})
    res_con = client.post(
        "/api/estimaciones/generar", json=payload_con,
        headers={"Authorization": f"Bearer {bd_sintetica}"},
    )
    assert res_con.status_code == 200, res_con.text

    conn = sqlite3.connect(core.EST_DB_PATH)
    clave = conn.execute("SELECT clave_resuelta FROM facturas WHERE id_documento='F002'").fetchone()[0]
    conn.close()
    assert clave == "2"


def test_migracion_y_seed_acumulado_idempotentes_y_valida_catalogo(tmp_path, monkeypatch):
    db_path = tmp_path / "est_migracion_acumulado.db"
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    core.setup_est_db()
    core.setup_est_db()  # segunda corrida no debe fallar (ALTER TABLE/CREATE TABLE duplicado)

    conn = sqlite3.connect(str(db_path))
    columnas = {c[1] for c in conn.execute("PRAGMA table_info(facturas)").fetchall()}
    tablas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "clave_resuelta" in columnas
    assert "estimacion_acumulado_base" in tablas

    # el catalogo todavia esta vacio -> el seed debe abortar sin insertar nada
    with pytest.raises(SystemExit):
        seed_acumulado_base_macao2.seed(str(db_path))
    conn = sqlite3.connect(str(db_path))
    assert conn.execute("SELECT COUNT(*) FROM estimacion_acumulado_base").fetchone()[0] == 0
    conn.close()

    # ahora con las 9 claves reales del catalogo de MACAO 2 (issue #10 aplicado)
    conn = sqlite3.connect(str(db_path))
    for i in range(1, 10):
        conn.execute(
            "INSERT INTO catalogo_estimacion (empresa, fase, orden, clave, descripcion, precio_unitario) "
            "VALUES ('DOMICEM','MACAO 2',?,?,?,100.0)",
            (i, str(i), f"Producto {i}"),
        )
    conn.commit()
    conn.close()

    antes, despues = seed_acumulado_base_macao2.seed(str(db_path))
    assert (antes, despues) == (0, 9)
    antes2, despues2 = seed_acumulado_base_macao2.seed(str(db_path))  # segunda corrida no duplica
    assert (antes2, despues2) == (9, 9)


def test_reseeder_acumulado_base_no_pisa_topes_del_contrato_principal(tmp_path, monkeypatch):
    """Bug real encontrado verificando el issue #12 a mano contra la BD real
    de produccion de este worktree: scripts/seed_acumulado_base_macao2.py
    (issue #11) usaba INSERT OR REPLACE, que en SQLite borra la fila en
    conflicto y la reinserta solo con las columnas listadas — cualquier
    columna no listada (cantidad_proyecto_principal, issue #12) volvia a su
    default (NULL). Si alguien corria ese script DESPUES de
    scripts/seed_contrato_principal_macao2.py (orden perfectamente
    razonable — el primero es idempotente y "seguro" de re-correr), se
    perdian los 9 topes de contrato principal en silencio. Fix: UPSERT
    explicito que solo toca fecha_base/cantidad_base."""
    db_path = tmp_path / "est_reseed_no_pisa_topes.db"
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    core.setup_est_db()

    conn = sqlite3.connect(str(db_path))
    for i in range(1, 10):
        conn.execute(
            "INSERT INTO catalogo_estimacion (empresa, fase, orden, clave, descripcion, precio_unitario) "
            "VALUES ('DOMICEM','MACAO 2',?,?,?,100.0)",
            (i, str(i), f"Producto {i}"),
        )
    conn.commit()
    conn.close()

    seed_acumulado_base_macao2.seed(str(db_path))  # issue #11: siembra las 9 bases
    seed_contrato_principal_macao2.seed(str(db_path))  # issue #12: siembra los 9 topes + fila ppact

    conn = sqlite3.connect(str(db_path))
    topes_antes = dict(conn.execute(
        "SELECT clave, cantidad_proyecto_principal FROM estimacion_acumulado_base "
        "WHERE empresa='DOMICEM' AND fase='MACAO 2' AND serie='principal'"
    ).fetchall())
    conn.close()
    assert all(v is not None for v in topes_antes.values())

    # re-correr el seed VIEJO (issue #11) despues del NUEVO (issue #12) --
    # los topes no deben perderse
    seed_acumulado_base_macao2.seed(str(db_path))

    conn = sqlite3.connect(str(db_path))
    topes_despues = dict(conn.execute(
        "SELECT clave, cantidad_proyecto_principal FROM estimacion_acumulado_base "
        "WHERE empresa='DOMICEM' AND fase='MACAO 2' AND serie='principal'"
    ).fetchall())
    conn.close()
    assert topes_despues == topes_antes


def test_vista_previa_fase_sin_acumulado_base_no_cambia_comportamiento(bd_sintetica):
    # Regresion (AC #9 / Testing Plan fila 12) — VMO/CEDIS (sintetico) sin
    # ninguna fila en estimacion_acumulado_base -> principal.calculado y
    # ppact.calculado son null en todos los productos, matching/sin_match
    # sin ningun cambio. Nota: "sin_resolver" (a diferencia del viejo
    # "acumulado_sin_resolver" del issue #11, que quedaba [] a proposito
    # cuando la fase no tenia ninguna base sembrada) ahora SI lista la
    # factura sin match, porque _est_clasificar_series matchea el rango
    # completo siempre (el fix critico del issue #12 que evita que
    # facturas_periodo quede vacio para las fases sin PPACT) — duplica lo
    # que "sin_match" ya reporta, no es un campo nuevo que bloquee nada;
    # el AC #9 (documentado en el issue) solo garantiza identico
    # comportamiento en calculado/matching/sin_match, no en este campo.
    client = TestClient(main.app)
    res = client.get(
        "/api/estimaciones/vista-previa",
        params={"empresa": "VMO", "fase": "CEDIS",
                "fecha_desde": "2026-06-01", "fecha_hasta": "2026-06-30"},
        headers={"Authorization": f"Bearer {bd_sintetica}"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["sin_resolver"] == ["Descripcion Rara Sin Match"]
    por_clave = {c["clave"]: c for c in data["catalogo"]}
    assert por_clave["1"]["principal"]["calculado"] is None
    assert por_clave["1"]["ppact"]["calculado"] is None
    assert por_clave["2"]["principal"]["calculado"] is None
    assert por_clave["2"]["ppact"]["calculado"] is None
    assert len(data["sin_match"]) == 1
    assert data["sin_match"][0]["descripcion"] == "Descripcion Rara Sin Match"


# ── issue #13: seed de las 8 fases restantes (scripts/seed_acumulado_base_fases.py) ──

# tamano real del catalogo de cada fase en la BD de produccion (verificado
# 2026-08-26) — las claves son '1'..'N', igual que en la BD real
_CATALOGO_REAL = {
    ("DOMICEM", "CAVERNAS"): 13,
    ("DOMICEM", "MACAO 2"): 9,
    ("DOMICEM", "PATIO DE MANIOBRAS-TRB"): 4,
    ("DOMICEM", "VIVIENDAS"): 9,
    ("VMO", "CANCHAS"): 3,
    ("VMO", "CEDIS"): 13,  # 12 del documento + el MR-42 (2026-10-20)
    ("VMO", "EXTERIORES"): 16,  # 15 del documento + el Mortero fc250 (2026-10-05)
    ("VMO", "PATIO DE MANIOBRAS-TRA"): 4,
    ("VMO", "PODIUM-1-2-3"): 3,
}


def _bd_con_catalogo_de_las_9_fases(tmp_path, monkeypatch, nombre="est_seed_fases.db", omitir=()):
    """BD temporal con el esquema real (core.setup_est_db) y el catalogo de las
    9 fases reales. `omitir`: iterable de (empresa, fase, clave) que NO se
    insertan — para simular un catalogo desincronizado."""
    db_path = tmp_path / nombre
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    core.setup_est_db()
    conn = sqlite3.connect(str(db_path))
    omitir = set(omitir)
    for (empresa, fase), n in _CATALOGO_REAL.items():
        for i in range(1, n + 1):
            if (empresa, fase, str(i)) in omitir:
                continue
            conn.execute(
                "INSERT INTO catalogo_estimacion (empresa, fase, orden, clave, descripcion, precio_unitario) "
                "VALUES (?,?,?,?,?,100.0)",
                (empresa, fase, i, str(i), f"{fase} Producto {i}"),
            )
    conn.commit()
    conn.close()
    return str(db_path)


def _filas_acumulado(db_path, empresa=None, fase=None):
    conn = sqlite3.connect(db_path)
    try:
        sql = ("SELECT empresa, fase, clave, serie, fecha_base, cantidad_base, cantidad_proyecto_principal "
               "FROM estimacion_acumulado_base")
        params = ()
        if empresa is not None:
            sql += " WHERE empresa = ? AND fase = ?"
            params = (empresa, fase)
        return sorted(conn.execute(sql, params).fetchall())
    finally:
        conn.close()


def test_seed_fases_catalogo_desincronizado_no_escribe_nada_de_esa_fase(tmp_path, monkeypatch):
    """AC #5 — si el catalogo de una fase perdio claves, esa fase no escribe
    NINGUNA fila (su transaccion nunca se abre) pero las demas si se siembran
    (semantica de fallo por fase, no aborta todo el proceso)."""
    db_path = _bd_con_catalogo_de_las_9_fases(
        tmp_path, monkeypatch,
        omitir=[("DOMICEM", "CAVERNAS", "12"), ("DOMICEM", "CAVERNAS", "13")],
    )
    resultado = seed_acumulado_base_fases.seed(db_path)

    info = resultado[("DOMICEM", "CAVERNAS")]
    assert info["error"] == "claves ausentes en catalogo_estimacion: ['12', '13']"
    assert info["principal"] == (0, 0) and info["ppact"] == (0, 0)
    assert _filas_acumulado(db_path, "DOMICEM", "CAVERNAS") == []  # ni una fila

    # las otras 7 fases si se sembraron
    assert all(resultado[k]["error"] is None for k in resultado if k != ("DOMICEM", "CAVERNAS"))
    assert resultado[("VMO", "CEDIS")]["principal"] == (0, 13)
    assert len(_filas_acumulado(db_path)) == 68 - 16  # 68 filas totales menos las 13+3 de CAVERNAS


def test_seed_fases_ppact_sin_principal_siempre_falla(tmp_path, monkeypatch):
    """Una clave de ppact sin su correspondiente en principal significa "cruzo
    un tope que no sabemos cual es" -> se rechaza SIEMPRE. Issue #14: la vieja
    excepcion para las 3 fases solo-PPACT desaparecio, porque esas fases ya no
    tienen 'principal' vacio — sus datos van en 'principal' con tope None."""
    db_path = _bd_con_catalogo_de_las_9_fases(tmp_path, monkeypatch)

    monkeypatch.setattr(seed_acumulado_base_fases, "FASES", {
        ("VMO", "CANCHAS"): {  # ppact clave 2 sin principal clave 2 -> invalida
            "fecha_base": "2026-07-16",
            "principal": {"1": (10.0, 20.0)},
            "ppact": {"2": 5.0},
            "fecha_base_ppact": "2026-07-16",
        },
        ("VMO", "EXTERIORES"): {  # solo-PPACT: ahora en principal con tope None -> valida
            "fecha_base": "2026-07-16",
            "principal": {"1": (100.0, None)},
            "ppact": {},
            "fecha_base_ppact": "2026-07-16",
        },
    })
    resultado = seed_acumulado_base_fases.seed(db_path)

    assert resultado[("VMO", "CANCHAS")]["error"] == (
        "claves de ppact sin su correspondiente en principal: ['2']"
    )
    assert _filas_acumulado(db_path, "VMO", "CANCHAS") == []
    assert resultado[("VMO", "EXTERIORES")]["error"] is None
    assert resultado[("VMO", "EXTERIORES")]["principal"] == (0, 1)


def test_seed_fases_solo_ppact_con_principal_vacio_ahora_falla(tmp_path, monkeypatch):
    """Regresion del issue #14: la forma VIEJA de sembrar una fase solo-PPACT
    (datos en 'ppact', 'principal' vacio) tiene que ser rechazada ahora — era
    justamente lo que dejaba esas 3 fases inertes."""
    db_path = _bd_con_catalogo_de_las_9_fases(tmp_path, monkeypatch)

    monkeypatch.setattr(seed_acumulado_base_fases, "FASES", {
        ("VMO", "EXTERIORES"): {
            "fecha_base": "2026-07-16",
            "principal": {},
            "ppact": {"1": 100.0},
            "fecha_base_ppact": "2026-07-16",
        },
    })
    resultado = seed_acumulado_base_fases.seed(db_path)

    assert resultado[("VMO", "EXTERIORES")]["error"] == (
        "claves de ppact sin su correspondiente en principal: ['1']"
    )
    assert _filas_acumulado(db_path, "VMO", "EXTERIORES") == []


def test_seed_fases_solo_ppact_se_leen_de_verdad(tmp_path, monkeypatch):
    """El corazon del issue #14: con los datos en 'principal' + tope None,
    _est_clasificar_series() SI devuelve el acumulado real. Con la forma vieja
    (serie='ppact', sin principal) devolvia None — la fila sembrada nunca se
    leia porque la funcion hace `continue` para un producto sin 'principal'."""
    db_path = _bd_con_catalogo_de_las_9_fases(tmp_path, monkeypatch)

    monkeypatch.setattr(seed_acumulado_base_fases, "FASES", {
        ("VMO", "EXTERIORES"): {
            "fecha_base": "2026-07-16",
            "principal": {"1": (1872.0, None)},
            "ppact": {},
            "fecha_base_ppact": "2026-07-16",
        },
    })
    seed_acumulado_base_fases.seed(db_path)

    conn = sqlite3.connect(db_path)
    try:
        catalogo = core._est_catalogo_fase(conn, "VMO", "EXTERIORES")
        r = core._est_clasificar_series(conn, "VMO", "EXTERIORES", catalogo,
                                        "2026-07-17", "2026-08-31")
    finally:
        conn.close()

    assert r["por_clave"]["1"]["principal"]["calculado"] == 1872.0
    assert r["por_clave"]["1"]["principal"]["tope"] is None  # PPACT no tiene techo
    assert r["por_clave"]["1"]["ppact"]["calculado"] is None


def test_seed_fases_ppact_siempre_con_cantidad_proyecto_principal_null(tmp_path, monkeypatch):
    """AC #4 (regla de negocio 1 del issue #13): la columna D de un documento
    PPACT se ignora siempre — la serie ppact NUNCA tiene tope propio.

    Issue #14: las 3 fases solo-PPACT ahora escriben en serie='principal' (con
    tope NULL, porque PPACT no tiene techo) en vez de serie='ppact'. Antes eran
    16 filas ppact + 0 principal; ahora son 16 filas principal sin tope."""
    db_path = _bd_con_catalogo_de_las_9_fases(tmp_path, monkeypatch)
    seed_acumulado_base_fases.seed(db_path)

    conn = sqlite3.connect(db_path)
    try:
        con_tope = conn.execute(
            "SELECT COUNT(*) FROM estimacion_acumulado_base "
            "WHERE serie = 'ppact' AND cantidad_proyecto_principal IS NOT NULL"
        ).fetchone()[0]
        principal_sin_tope = conn.execute(
            "SELECT COUNT(*) FROM estimacion_acumulado_base "
            "WHERE serie = 'principal' AND cantidad_proyecto_principal IS NULL"
        ).fetchone()[0]
        por_serie = dict(conn.execute(
            "SELECT serie, COUNT(*) FROM estimacion_acumulado_base GROUP BY serie"
        ).fetchall())
    finally:
        conn.close()

    assert con_tope == 0
    # las 24 filas sin tope son exactamente las de las 3 fases solo-PPACT:
    # VIVIENDAS 9 + PODIUM-1-2-3 1 + EXTERIORES 14 (13 + el Mortero fc250
    # agregado el 2026-10-05). Eran 16 cuando VIVIENDAS
    # tenia sembradas solo sus 2 claves con acumulado distinto de cero; sus
    # otras 7 traen N = 0 escrito en el documento y ahora se siembran (regla 5)
    assert principal_sin_tope == 24
    assert por_serie == {"principal": 61, "ppact": 7}  # 59 + EXTERIORES 16 + CEDIS 13

    for empresa, fase in [("DOMICEM", "VIVIENDAS"), ("VMO", "PODIUM-1-2-3"), ("VMO", "EXTERIORES")]:
        filas = _filas_acumulado(db_path, empresa, fase)
        assert filas, f"{empresa}/{fase} deberia tener filas sembradas"
        assert all(f[3] == "principal" for f in filas), (
            f"{empresa}/{fase} debe sembrar en 'principal', no en 'ppact' (issue #14)"
        )


def test_seed_fases_idempotente(tmp_path, monkeypatch):
    """AC #2 — correrlo 2 veces deja exactamente las mismas filas; lo unico que
    cambia es el 'antes=' del reporte."""
    db_path = _bd_con_catalogo_de_las_9_fases(tmp_path, monkeypatch)

    primera = seed_acumulado_base_fases.seed(db_path)
    filas_1 = _filas_acumulado(db_path)
    segunda = seed_acumulado_base_fases.seed(db_path)
    filas_2 = _filas_acumulado(db_path)

    assert filas_1 == filas_2
    assert len(filas_1) == 68  # 66 + EXTERIORES 16 (2026-10-05) + CEDIS 13 (2026-10-20)
    assert primera[("DOMICEM", "CAVERNAS")]["principal"] == (0, 13)
    assert segunda[("DOMICEM", "CAVERNAS")]["principal"] == (13, 13)
    assert segunda[("DOMICEM", "CAVERNAS")]["ppact"] == (3, 3)
    assert all(i["error"] is None for i in segunda.values())


def test_seed_fases_no_pisa_macao2_en_ninguno_de_los_dos_ordenes(tmp_path, monkeypatch):
    """AC #3 — el script nuevo y los 2 viejos de MACAO 2 conviven: ninguno pisa
    los datos del otro, se corran en el orden que se corran. Mismo riesgo que
    ya causo una perdida real de topes en el issue #12 (INSERT OR REPLACE)."""
    db_path = _bd_con_catalogo_de_las_9_fases(tmp_path, monkeypatch)

    # orden A: MACAO 2 primero, fases nuevas despues
    seed_acumulado_base_macao2.seed(db_path)
    seed_contrato_principal_macao2.seed(db_path)
    macao2_esperado = _filas_acumulado(db_path, "DOMICEM", "MACAO 2")
    assert len(macao2_esperado) == 10  # 9 principal + 1 ppact
    assert all(f[6] is not None for f in macao2_esperado if f[3] == "principal")

    seed_acumulado_base_fases.seed(db_path)
    assert _filas_acumulado(db_path, "DOMICEM", "MACAO 2") == macao2_esperado
    nuevas_esperadas = [f for f in _filas_acumulado(db_path) if f[1] != "MACAO 2"]
    assert len(nuevas_esperadas) == 68

    # orden B: re-correr los 2 viejos DESPUES del nuevo no toca lo nuevo
    seed_acumulado_base_macao2.seed(db_path)
    seed_contrato_principal_macao2.seed(db_path)
    assert _filas_acumulado(db_path, "DOMICEM", "MACAO 2") == macao2_esperado
    assert [f for f in _filas_acumulado(db_path) if f[1] != "MACAO 2"] == nuevas_esperadas


def test_seed_fases_end_to_end_con_clasificar_series(tmp_path, monkeypatch):
    """Integracion con el consumidor real (_est_clasificar_series, sin tocarla):
    DOMICEM/PATIO DE MANIOBRAS-TRB clave 2 tiene el caso que valida la regla
    "la factura nunca se divide" — base 2300.5 de un tope 2301, asi que una
    factura de 5 m3 posterior no cabe entera y se va COMPLETA a PPACT, que
    arranca de su base sembrada 333 (AC #7)."""
    db_path = _bd_con_catalogo_de_las_9_fases(tmp_path, monkeypatch)
    seed_acumulado_base_fases.seed(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO facturas (id_documento, fecha, empresa, fase, descripcion, cantidad, precio_unitario) "
        "VALUES ('M900000001','2026-07-20','DOMICEM','PATIO DE MANIOBRAS-TRB',"
        "'PATIO DE MANIOBRAS-TRB Producto 2',5.0,900.0)"
    )
    conn.execute(
        "INSERT INTO facturas (id_documento, fecha, empresa, fase, descripcion, cantidad, precio_unitario) "
        "VALUES ('M900000002','2026-07-20','DOMICEM','PATIO DE MANIOBRAS-TRB',"
        "'PATIO DE MANIOBRAS-TRB Producto 3',6.0,900.0)"
    )
    conn.commit()

    catalogo = core._est_catalogo_fase(conn, "DOMICEM", "PATIO DE MANIOBRAS-TRB")
    clasificacion = core._est_clasificar_series(
        conn, "DOMICEM", "PATIO DE MANIOBRAS-TRB", catalogo, "2026-07-17", "2026-08-31"
    )
    conn.close()

    por_clave = clasificacion["por_clave"]
    # calculado = acumulado ANTERIOR a fecha_desde; con fecha_base 2026-07-16 y
    # fecha_desde 2026-07-17 la ventana intermedia es vacia -> identico a la base
    assert por_clave["2"]["principal"] == {"calculado": 2300.5, "tope": 2301.0}
    assert por_clave["2"]["ppact"]["calculado"] == 333.0
    assert por_clave["4"]["principal"] == {"calculado": 4469.5, "tope": 4476.0}
    assert por_clave["4"]["ppact"]["calculado"] == 501.0
    # clave 3 tiene margen de sobra (591 de 1193) -> su factura sigue en principal
    assert por_clave["3"]["principal"] == {"calculado": 591.0, "tope": 1193.0}
    assert por_clave["3"]["ppact"]["calculado"] is None

    series_por_documento = {f[0]: f[2] for f in clasificacion["facturas_periodo"]}
    assert series_por_documento == {"M900000001": "ppact", "M900000002": "principal"}
    assert clasificacion["sin_resolver"] == []


def test_clasificar_series_criterio_2_issue_16_las_9_fases_reales(tmp_path, monkeypatch):
    """Issue #16, criterio 2 — fixture sintetico con las 9 fases y sus
    bases/topes REALES (los 3 scripts de seed reproducen exactamente las
    69 filas de estimacion_acumulado_base de produccion, verificado
    2026-08-28) mas los lotes reales del periodo 2026-07-17..2026-08-16
    (un total por clave). Esperado: todas las claves clasifican IGUAL que
    antes del issue #16, salvo VMO/CEDIS clave 2 que pasa de 5/2 a 0/7
    (criterio 1). Si cualquier otra clave se mueve, el cambio se fue de
    alcance."""
    db_path = _bd_con_catalogo_de_las_9_fases(tmp_path, monkeypatch)
    seed_acumulado_base_macao2.seed(db_path)
    seed_contrato_principal_macao2.seed(db_path)
    seed_acumulado_base_fases.seed(db_path)

    # lote real del periodo por (empresa, fase, clave) -> (cantidad_total,
    # serie esperada). Medido contra la BD de produccion el 2026-08-28:
    # identico a la salida del sistema ANTES de este issue en todas las
    # claves menos CEDIS 2.
    lotes_esperados = {
        ("DOMICEM", "CAVERNAS"): {"1": (52.0, "principal"), "2": (370.0, "principal"),
                                   "3": (173.0, "principal"), "8": (21.0, "ppact"),
                                   "10": (11.5, "principal")},
        ("DOMICEM", "MACAO 2"): {"6": (2028.0, "principal"), "7": (57.0, "ppact"),
                                  "8": (6271.0, "principal"), "9": (62.5, "principal")},
        ("DOMICEM", "PATIO DE MANIOBRAS-TRB"): {"3": (12.5, "principal")},
        ("DOMICEM", "VIVIENDAS"): {"2": (30.0, "principal"), "5": (66.5, "principal"),
                                    "8": (12.0, "principal")},
        ("VMO", "CANCHAS"): {},
        # CEDIS clave 2 va aparte, con sus 2 facturas reales (criterio 1)
        ("VMO", "CEDIS"): {"1": (6.0, "principal"), "11": (48.0, "ppact")},
        ("VMO", "EXTERIORES"): {"6": (316.0, "principal"), "15": (29.0, "principal")},
        ("VMO", "PATIO DE MANIOBRAS-TRA"): {"2": (21.0, "principal")},
        ("VMO", "PODIUM-1-2-3"): {"3": (935.0, "principal")},
    }

    conn = sqlite3.connect(db_path)
    i = 0
    for (empresa, fase), lotes in lotes_esperados.items():
        for clave, (cantidad, _) in lotes.items():
            i += 1
            conn.execute(
                "INSERT INTO facturas (id_documento, fecha, empresa, fase, descripcion, cantidad, precio_unitario) "
                "VALUES (?, '2026-07-20', ?, ?, ?, ?, 100.0)",
                (f"MLOTE{i:04d}", empresa, fase, f"{fase} Producto {clave}", cantidad),
            )
    # VMO/CEDIS clave 2: las dos entregas reales del 17-jul (5.0 y 2.0)
    for id_doc, cantidad in (("M800013832", 5.0), ("M800013843", 2.0)):
        conn.execute(
            "INSERT INTO facturas (id_documento, fecha, empresa, fase, descripcion, cantidad, precio_unitario) "
            "VALUES (?, '2026-07-17', 'VMO', 'CEDIS', 'CEDIS Producto 2', ?, 106.7)",
            (id_doc, cantidad),
        )
    conn.commit()

    for (empresa, fase), lotes in lotes_esperados.items():
        catalogo = core._est_catalogo_fase(conn, empresa, fase)
        r = core._est_clasificar_series(conn, empresa, fase, catalogo, "2026-07-17", "2026-08-16")
        assert r["sin_resolver"] == [], (empresa, fase)
        assert r["aviso_acumulado_por_factura"] is None, (empresa, fase)
        # cada lote clasifica en la serie esperada (la de antes del cambio)
        por_clave_series = {}
        for _, clave, serie, _, cantidad, _, _ in r["facturas_periodo"]:
            acumulado = por_clave_series.setdefault(clave, {"principal": 0.0, "ppact": 0.0})
            acumulado[serie] += cantidad
        for clave, (cantidad, serie) in lotes.items():
            assert por_clave_series[clave][serie] == cantidad, (empresa, fase, clave)
            otra = "ppact" if serie == "principal" else "principal"
            assert por_clave_series[clave][otra] == 0.0, (empresa, fase, clave)
        if (empresa, fase) == ("VMO", "CEDIS"):
            # 2026-09-25 (decision de Axel, lote partido por factura): la
            # clave 2 da principal=5.0 (M800013832 cabe: 23+5 <= 29) /
            # ppact=2.0 (M800013843 ya no cabe). OJO: el N06 real de la
            # empresa habia mandado los 7.0 enteros a ppact — la regla
            # nueva NO reproduce ese documento historico.
            assert por_clave_series["2"] == {"principal": 5.0, "ppact": 2.0}
            assert r["por_clave"]["2"]["principal"] == {"calculado": 23.0, "tope": 29.0}
    conn.close()


def test_seed_fases_fase_desconocida_no_levanta_y_deduplica(tmp_path, monkeypatch):
    """seed() nunca levanta ni llama sys.exit() por una fase invalida: la deja
    con su 'error' y sigue. Pedir la misma fase 2 veces la siembra 1 sola."""
    db_path = _bd_con_catalogo_de_las_9_fases(tmp_path, monkeypatch)
    resultado = seed_acumulado_base_fases.seed(
        db_path,
        [("VMO", "CEDIS"), ("VMO", "CAMPO DE GOLF"), ("VMO", "CEDIS")],
    )

    assert list(resultado.keys()) == [("VMO", "CEDIS"), ("VMO", "CAMPO DE GOLF")]
    assert resultado[("VMO", "CAMPO DE GOLF")]["error"] == "fase desconocida"
    assert resultado[("VMO", "CEDIS")]["error"] is None
    assert resultado[("VMO", "CEDIS")]["principal"] == (0, 13)
    # solo se sembro CEDIS, ninguna otra fase
    assert {(f[0], f[1]) for f in _filas_acumulado(db_path)} == {("VMO", "CEDIS")}


def test_cli_seed_fases_exige_flag_valida_fase_y_reporta(tmp_path, monkeypatch, capsys):
    """El guard de "nunca sembrar las 8 sin pedirlo" vive en el CLI: sin
    --todas/--fase argparse falla (exit 2), igual que con una fase inexistente.
    Y main() traduce el dict de seed() a la salida/exit code documentados."""
    db_path = _bd_con_catalogo_de_las_9_fases(
        tmp_path, monkeypatch, omitir=[("VMO", "CANCHAS", "3")]
    )

    # sin ningun flag -> argparse exige uno del grupo mutuamente excluyente
    monkeypatch.setattr(sys, "argv", ["seed_acumulado_base_fases.py", db_path])
    with pytest.raises(SystemExit) as exc:
        seed_acumulado_base_fases.main()
    assert exc.value.code == 2

    # --todas y --fase juntos -> error del grupo
    monkeypatch.setattr(sys, "argv", ["x", db_path, "--todas", "--fase", "VMO/CEDIS"])
    with pytest.raises(SystemExit) as exc:
        seed_acumulado_base_fases.main()
    assert exc.value.code == 2

    # fase que no esta en la tabla -> error sin tocar la BD
    monkeypatch.setattr(sys, "argv", ["x", db_path, "--fase", "VMO/CAMPO DE GOLF"])
    with pytest.raises(SystemExit) as exc:
        seed_acumulado_base_fases.main()
    assert exc.value.code == 2
    assert _filas_acumulado(db_path) == []

    # --list no toca la BD
    monkeypatch.setattr(sys, "argv", ["x", db_path, "--list"])
    seed_acumulado_base_fases.main()
    assert _filas_acumulado(db_path) == []

    # corrida real: CANCHAS falla la validacion (le falta la clave 3 en el
    # catalogo), las demas se siembran -> exit 1 y mensaje exacto en stderr
    capsys.readouterr()
    monkeypatch.setattr(sys, "argv", ["x", db_path, "--todas"])
    with pytest.raises(SystemExit) as exc:
        seed_acumulado_base_fases.main()
    assert exc.value.code == 1
    salida = capsys.readouterr()
    assert (
        "ERROR VMO/CANCHAS: claves ausentes en catalogo_estimacion: ['3'] "
        "— no se sembro nada de esta fase"
    ) in salida.err
    assert "RESUMEN: 7 fases OK, 1 con error" in salida.out
    assert "DOMICEM/CAVERNAS" in salida.out
    assert _filas_acumulado(db_path, "VMO", "CANCHAS") == []
    assert len(_filas_acumulado(db_path)) == 68 - 3


# ─────────────────────────────────────────────
# Issue #15 — el Excel de conduces es la fuente de verdad tambien en el
# sitio web (descripcion y, via el Cliente, la fase)
# ─────────────────────────────────────────────

# ── cargar_lookup_excel() ──

def test_cargar_lookup_excel_headers_ok_indexa_filas():
    excel_bytes = _construir_excel_bytes([
        ("M100000001", "2026-06-01", "MACAO ALTO RESORT S.R.L CANCHAS",
         "Hormigon 350kg/cm2", 7, "M1", "06-01-M1-00000001.pdf"),
    ])
    lookup = core.cargar_lookup_excel(excel_bytes)
    assert lookup["filas"] == 1
    assert lookup["conflictos"] == {}
    esperado = {
        "id_documento": "M100000001", "descripcion": "Hormigon 350kg/cm2",
        "cliente": "MACAO ALTO RESORT S.R.L CANCHAS", "cantidad": 7.0,
    }
    assert lookup["por_archivo"]["06-01-m1-00000001.pdf"] == esperado
    assert lookup["por_id"]["M100000001"] == esperado


def test_cargar_lookup_excel_encabezado_invalido_lanza_formato_error():
    excel_bytes = _construir_excel_bytes(
        [("M100000001", "2026-06-01", "cliente", "producto", 1, "M1", "x.pdf")],
        headers=["Conduce", "Fecha", "CLIENTE_MAL", "Producto", "Cant.", "Planta", "Codigo"],
    )
    with pytest.raises(core.ExcelFormatoError):
        core.cargar_lookup_excel(excel_bytes)


def test_cargar_lookup_excel_xlsx_corrupto_lanza_ilegible_error():
    # Nunca deja escapar la excepcion cruda de openpyxl (BadZipFile, etc.)
    with pytest.raises(core.ExcelIlegibleError):
        core.cargar_lookup_excel(b"esto no es un archivo Excel valido")


def test_cargar_lookup_excel_fila_sin_campo_obligatorio_se_salta():
    excel_bytes = _construir_excel_bytes([
        (None, "2026-06-01", "CLIENTE", "Producto", 1, "M1", "a.pdf"),   # sin Conduce
        ("M2", "2026-06-01", "CLIENTE", None, 1, "M1", "b.pdf"),          # sin Producto
        ("M3", "2026-06-01", None, "Producto", 1, "M1", "c.pdf"),         # sin Cliente
        ("M4", "2026-06-01", "CLIENTE", "Producto", 1, "M1", "d.pdf"),    # OK
    ])
    lookup = core.cargar_lookup_excel(excel_bytes)
    assert lookup["filas"] == 4
    assert list(lookup["por_id"].keys()) == ["M4"]
    assert "a.pdf" not in lookup["por_archivo"]
    assert "b.pdf" not in lookup["por_archivo"]
    assert "c.pdf" not in lookup["por_archivo"]


def test_cargar_lookup_excel_llave_duplicada_datos_distintos_es_conflicto():
    excel_bytes = _construir_excel_bytes([
        ("M100000005", "2026-06-01", "CLIENTE A", "Producto A", 1, "M1", "05.pdf"),
        ("M100000005", "2026-06-02", "CLIENTE B", "Producto B", 2, "M1", "05.pdf"),
    ])
    lookup = core.cargar_lookup_excel(excel_bytes)
    assert "M100000005" not in lookup["por_id"]
    assert core._excel_norm_archivo("05.pdf") not in lookup["por_archivo"]
    assert len(lookup["conflictos"]) >= 1


def test_cargar_lookup_excel_duplicado_identico_no_es_conflicto():
    excel_bytes = _construir_excel_bytes([
        ("M100000006", "2026-06-01", "CLIENTE A", "Producto A", 1, "M1", "06.pdf"),
        ("M100000006", "2026-06-15", "CLIENTE A", "Producto A", 1, "M1", "06.pdf"),
    ])
    lookup = core.cargar_lookup_excel(excel_bytes)
    assert lookup["conflictos"] == {}
    assert lookup["por_id"]["M100000006"]["descripcion"] == "Producto A"


def test_cargar_lookup_excel_normaliza_llaves_mayusculas_espacios_sin_pdf():
    excel_bytes = _construir_excel_bytes([
        ("  m100000007  ", "2026-06-01", "CLIENTE", "Producto", 1, "M1", "  07-M1  "),
    ])
    lookup = core.cargar_lookup_excel(excel_bytes)
    assert "M100000007" in lookup["por_id"]
    assert "07-m1.pdf" in lookup["por_archivo"]


def test_acceptance_12_match_nombre_archivo_insensible_a_mayusculas_y_espacios():
    # Acceptance criterion #12, literal: "  04-18-M3-54578.PDF " (Excel) casa
    # con "04-18-m3-54578.pdf" (nombre real del PDF en el ZIP).
    assert core._excel_norm_archivo("  04-18-M3-54578.PDF ") == core._excel_norm_archivo("04-18-m3-54578.pdf")
    assert core._excel_norm_archivo("  04-18-M3-54578.PDF ") == "04-18-m3-54578.pdf"


def test_cargar_lookup_excel_invalidacion_cruzada_conflicto_por_codigo_invalida_por_id():
    # Mismo Codigo, Conduce distinto, datos distintos -> conflicto detectado
    # por Codigo. Los 2 Conduce involucrados deben quedar invalidados
    # tambien en por_id — sin esto, el conflicto seria resoluble via el
    # indice de Conduce.
    excel_bytes = _construir_excel_bytes([
        ("M1", "2026-06-01", "CLIENTE A", "Producto A", 1, "M1", "mismo.pdf"),
        ("M2", "2026-06-02", "CLIENTE B", "Producto B", 2, "M1", "mismo.pdf"),
    ])
    lookup = core.cargar_lookup_excel(excel_bytes)
    assert core._excel_norm_archivo("mismo.pdf") not in lookup["por_archivo"]
    assert "M1" not in lookup["por_id"]
    assert "M2" not in lookup["por_id"]


def test_cargar_lookup_excel_invalidacion_cruzada_conflicto_por_conduce_invalida_por_archivo():
    # Mismo Conduce, Codigo distinto en cada fila, datos distintos ->
    # conflicto detectado por Conduce. Las 2 entradas de por_archivo (una
    # por cada Codigo) deben quedar invalidadas tambien — sin esto, el
    # conflicto seria resoluble via el indice de archivo.
    excel_bytes = _construir_excel_bytes([
        ("M9", "2026-06-01", "CLIENTE A", "Producto A", 1, "M1", "a.pdf"),
        ("M9", "2026-06-02", "CLIENTE B", "Producto B", 2, "M1", "b.pdf"),
    ])
    lookup = core.cargar_lookup_excel(excel_bytes)
    assert "M9" not in lookup["por_id"]
    assert core._excel_norm_archivo("a.pdf") not in lookup["por_archivo"]
    assert core._excel_norm_archivo("b.pdf") not in lookup["por_archivo"]


# ── _motivo_sello_firma() — motivo nuevo, gana sobre fase no reconocida ──

def test_motivo_sello_firma_sin_fila_excel_gana_sobre_fase_no_reconocida():
    datos = {"_sin_fila_excel": True, "_motivo_excel": "sin fila en el Excel", "fase": None}
    assert core._motivo_sello_firma(datos) == "sin fila en el Excel"


def test_motivo_sello_firma_conflicto_excel_usa_su_propio_motivo():
    datos = {
        "_sin_fila_excel": True,
        "_motivo_excel": "el Excel se contradice para este documento",
        "fase": None,
    }
    assert core._motivo_sello_firma(datos) == "el Excel se contradice para este documento"


# ── orden de evaluacion en _procesar_pdfs() ──

def test_procesar_pdfs_duplicado_sin_fila_reporta_duplicado(tmp_path, monkeypatch):
    # Acceptance criterion #11d: duplicado gana sobre "sin fila en el Excel".
    db_path = tmp_path / "est.db"
    conn = sqlite3.connect(str(db_path))
    _crear_tabla_facturas(conn)
    conn.execute(
        "INSERT INTO facturas (id_documento, descripcion) VALUES ('M100000020', 'ya existe')"
    )
    conn.commit()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("06-01-M1-00000020.pdf", b"contenido falso")
    buf.seek(0)
    zf_leido = zipfile.ZipFile(buf)

    monkeypatch.setattr(
        core, "_procesar_pdf_sync",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("Vision no deberia llamarse"))
    )

    importadas, errores_vision, pendientes, duplicadas, corregidas = asyncio.run(
        core._procesar_pdfs(zf_leido, ["06-01-M1-00000020.pdf"], conn, core.VISION_MODEL_STD, _lookup_vacio())
    )
    conn.close()

    assert duplicadas == ["06-01-M1-00000020.pdf"]
    assert pendientes == []
    assert errores_vision == []


def test_procesar_pdfs_nombre_invalido_gana_sobre_todo():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE facturas (id_documento TEXT PRIMARY KEY)")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("nombre-invalido.pdf", b"contenido falso")
    buf.seek(0)
    zf_leido = zipfile.ZipFile(buf)

    importadas, errores_vision, pendientes, duplicadas, corregidas = asyncio.run(
        core._procesar_pdfs(zf_leido, ["nombre-invalido.pdf"], conn, core.VISION_MODEL_STD, _lookup_vacio())
    )
    conn.close()

    assert len(errores_vision) == 1
    assert errores_vision[0]["motivo"] == "nombre de archivo inválido"
    assert pendientes == []
    assert duplicadas == []


# ── POST /api/estimaciones/procesar-zip — integracion HTTP ──

def test_procesar_zip_endpoint_sin_excel_no_procesa_nada(tmp_path, monkeypatch):
    # Acceptance criterion #1: sin el campo `excel`, FastAPI responde 422
    # (campo requerido faltante) antes de que el handler corra una linea —
    # cero llamadas a Vision.
    db_path = tmp_path / "est.db"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    monkeypatch.setattr(core, "EST_DATA_DIR", str(data_dir))
    monkeypatch.setattr(
        core, "_procesar_pdf_sync",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("Vision no deberia llamarse"))
    )

    token = "test-token-sin-excel"
    core.active_tokens[token] = datetime.now()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("06-01-M1-00000001.pdf", b"contenido falso")
    buf.seek(0)

    client = TestClient(main.app)
    try:
        res = client.post(
            "/api/estimaciones/procesar-zip",
            files={"archivo": ("lote.zip", buf.getvalue(), "application/zip")},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 422
    assert isinstance(res.json()["detail"], list)  # 422 de FastAPI = array, no dict


def test_procesar_zip_endpoint_excel_mal_formado_da_400(tmp_path, monkeypatch):
    db_path = tmp_path / "est.db"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    monkeypatch.setattr(core, "EST_DATA_DIR", str(data_dir))
    monkeypatch.setattr(
        core, "_procesar_pdf_sync",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("Vision no deberia llamarse"))
    )

    token = "test-token-excel-mal-formado"
    core.active_tokens[token] = datetime.now()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("06-01-M1-00000001.pdf", b"contenido falso")
    buf.seek(0)
    excel_bytes = _construir_excel_bytes(
        [("M1", "2026-06-01", "c", "p", 1, "M1", "x.pdf")],
        headers=["Conduce", "Fecha", "MAL", "Producto", "Cant.", "Planta", "Codigo"],
    )

    client = TestClient(main.app)
    try:
        res = client.post(
            "/api/estimaciones/procesar-zip",
            files={
                "archivo": ("lote.zip", buf.getvalue(), "application/zip"),
                "excel": ("conduces.xlsx", excel_bytes,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "excel_formato_invalido"


def test_procesar_zip_endpoint_excel_excede_tope_da_413(tmp_path, monkeypatch):
    db_path = tmp_path / "est.db"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    monkeypatch.setattr(core, "EST_DATA_DIR", str(data_dir))
    monkeypatch.setattr(core, "EST_EXCEL_MAX_BYTES", 1024)  # 1KB, no crear un fixture gigante
    monkeypatch.setattr(
        core, "_procesar_pdf_sync",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("Vision no deberia llamarse"))
    )

    token = "test-token-excel-grande"
    core.active_tokens[token] = datetime.now()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("06-01-M1-00000001.pdf", b"contenido falso")
    buf.seek(0)

    client = TestClient(main.app)
    try:
        res = client.post(
            "/api/estimaciones/procesar-zip",
            files={
                "archivo": ("lote.zip", buf.getvalue(), "application/zip"),
                "excel": ("conduces.xlsx", b"\x00" * 2000,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 413


def test_procesar_zip_endpoint_caso_feliz_resuelve_precio(tmp_path, monkeypatch):
    db_path = tmp_path / "est.db"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    procesadas_dir = tmp_path / "procesadas"
    procesadas_dir.mkdir()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    monkeypatch.setattr(core, "EST_DATA_DIR", str(data_dir))
    monkeypatch.setattr(core, "EST_PROCESADAS", str(procesadas_dir))
    core.setup_est_db()

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO precios_vmo (codigo, fase, descripcion, precio_unitario) VALUES (?,?,?,?)",
        ("X", "CANCHAS", "Hormigon 350kg/cm2", 100.0),
    )
    conn.commit()
    conn.close()

    def fake_vision(pdf_bytes, model=core.VISION_MODEL_STD):
        return {
            "tiene_sello": True, "tiene_firma": True,
            "descripcion": "OCR sucio ilegible", "cantidad": 7,
        }
    monkeypatch.setattr(core, "_procesar_pdf_sync", fake_vision)
    monkeypatch.setattr(
        core, "_verificar_sello_firma_opus",
        lambda pdf_bytes: {"tiene_sello": True, "tiene_firma": True}
    )

    token = "test-token-caso-feliz"
    core.active_tokens[token] = datetime.now()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("06-01-M1-00000010.pdf", b"contenido falso")
    buf.seek(0)
    excel_bytes = _construir_excel_bytes([
        ("M100000010", "2026-06-01", "MACAO ALTO RESORT S.R.L CANCHAS",
         "Hormigon 350kg/cm2", 7, "M1", "06-01-M1-00000010.pdf"),
    ])

    client = TestClient(main.app)
    res = None
    try:
        res = client.post(
            "/api/estimaciones/procesar-zip",
            files={
                "archivo": ("lote.zip", buf.getvalue(), "application/zip"),
                "excel": ("conduces.xlsx", excel_bytes,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        session_id = data["session_id"]
        registro = core.est_sessions[session_id]["importadas"][0]
    finally:
        core.active_tokens.pop(token, None)
        if res is not None and res.status_code == 200:
            core.est_sessions.pop(res.json().get("session_id"), None)

    assert data["importadas"] == 1
    assert data["importadas_lista"] == ["06-01-M1-00000010.pdf"]
    assert registro["descripcion"] == "Hormigon 350kg/cm2"
    assert registro["precio_unitario"] == 100.0
    assert registro["total"] == 700.0


def test_procesar_zip_endpoint_pdf_sin_fila_no_llama_vision(tmp_path, monkeypatch):
    # Acceptance criterion #9: sin fila -> pendientes_revision, sin llamar a
    # Vision (el mock lanza AssertionError si se llega a invocar).
    db_path = tmp_path / "est.db"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pendientes_dir = tmp_path / "pendientes_revision"
    pendientes_dir.mkdir()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    monkeypatch.setattr(core, "EST_DATA_DIR", str(data_dir))
    monkeypatch.setattr(core, "EST_PENDIENTES", str(pendientes_dir))
    monkeypatch.setattr(
        core, "_procesar_pdf_sync",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("Vision no deberia llamarse"))
    )

    token = "test-token-sin-fila"
    core.active_tokens[token] = datetime.now()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("06-01-M1-00000011.pdf", b"contenido falso")
    buf.seek(0)
    # El Excel no tiene ninguna fila para este documento.
    excel_bytes = _construir_excel_bytes([
        ("M999999999", "2026-06-01", "CLIENTE", "Producto", 1, "M1", "no-coincide.pdf"),
    ])

    client = TestClient(main.app)
    res = None
    try:
        res = client.post(
            "/api/estimaciones/procesar-zip",
            files={
                "archivo": ("lote.zip", buf.getvalue(), "application/zip"),
                "excel": ("conduces.xlsx", excel_bytes,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)
        if res is not None and res.status_code == 200:
            core.est_sessions.pop(res.json().get("session_id"), None)

    assert res.status_code == 200, res.text
    data = res.json()
    assert data["importadas"] == 0
    assert data["pendientes"] == 1
    assert data["pendientes_lista"][0]["motivo"] == "sin fila en el Excel"


def test_procesar_zip_endpoint_corregidas_lista_poblada(tmp_path, monkeypatch):
    # Acceptance criterion #13: la descripcion de Vision difiere de la del
    # Excel -> aparece en corregidas_lista con ambos textos.
    db_path = tmp_path / "est.db"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    monkeypatch.setattr(core, "EST_DATA_DIR", str(data_dir))

    def fake_vision(pdf_bytes, model=core.VISION_MODEL_STD):
        return {
            "tiene_sello": True, "tiene_firma": True,
            "descripcion": "AM0. IIIA (OCR sucio)", "cantidad": 5,
        }
    monkeypatch.setattr(core, "_procesar_pdf_sync", fake_vision)
    monkeypatch.setattr(
        core, "_verificar_sello_firma_opus",
        lambda pdf_bytes: {"tiene_sello": True, "tiene_firma": True}
    )

    token = "test-token-corregidas"
    core.active_tokens[token] = datetime.now()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("06-01-M1-00000012.pdf", b"contenido falso")
    buf.seek(0)
    excel_bytes = _construir_excel_bytes([
        ("M100000012", "2026-06-01", "MACAO ALTO RESORT S.R.L CANCHAS",
         "Hormigon 350kg/cm2", 5, "M1", "06-01-M1-00000012.pdf"),
    ])

    client = TestClient(main.app)
    res = None
    try:
        res = client.post(
            "/api/estimaciones/procesar-zip",
            files={
                "archivo": ("lote.zip", buf.getvalue(), "application/zip"),
                "excel": ("conduces.xlsx", excel_bytes,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)
        if res is not None and res.status_code == 200:
            core.est_sessions.pop(res.json().get("session_id"), None)

    assert res.status_code == 200, res.text
    data = res.json()
    assert data["corregidas_lista"] == [{
        "nombre": "06-01-M1-00000012.pdf", "campo": "descripcion",
        "vision": "AM0. IIIA (OCR sucio)", "excel": "Hormigon 350kg/cm2",
    }]
    # criterion #16: corregidas_lista no altera importadas
    assert data["importadas"] == 1
    assert data["importadas_lista"] == ["06-01-M1-00000012.pdf"]


def test_procesar_zip_endpoint_conflictos_excel_filtrados_al_zip(tmp_path, monkeypatch):
    # Acceptance criterion #11c: solo se reportan conflictos de filas que
    # corresponden a PDFs de ESTE ZIP.
    db_path = tmp_path / "est.db"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    monkeypatch.setattr(core, "EST_DATA_DIR", str(data_dir))
    monkeypatch.setattr(
        core, "_procesar_pdf_sync",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("Vision no deberia llamarse"))
    )

    token = "test-token-conflictos"
    core.active_tokens[token] = datetime.now()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("06-01-M1-00000013.pdf", b"contenido falso")
    buf.seek(0)
    excel_bytes = _construir_excel_bytes([
        # conflicto real por Codigo, afecta al PDF de este ZIP
        ("M100000013", "2026-06-01", "CLIENTE A", "Producto A", 1, "M1", "06-01-M1-00000013.pdf"),
        ("M100000014", "2026-06-02", "CLIENTE B", "Producto B", 2, "M1", "06-01-M1-00000013.pdf"),
        # conflicto de otras filas del Excel, ningun PDF de este ZIP las usa
        ("M900000001", "2026-06-01", "CLIENTE C", "Producto C", 1, "M1", "otro-no-en-el-zip.pdf"),
        ("M900000001", "2026-06-02", "CLIENTE D", "Producto D", 2, "M1", "otro-no-en-el-zip-2.pdf"),
    ])

    client = TestClient(main.app)
    res = None
    try:
        res = client.post(
            "/api/estimaciones/procesar-zip",
            files={
                "archivo": ("lote.zip", buf.getvalue(), "application/zip"),
                "excel": ("conduces.xlsx", excel_bytes,
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)
        if res is not None and res.status_code == 200:
            core.est_sessions.pop(res.json().get("session_id"), None)

    assert res.status_code == 200, res.text
    data = res.json()
    llaves = {c["llave"] for c in data["conflictos_excel"]}
    assert core._excel_norm_archivo("06-01-M1-00000013.pdf") in llaves
    assert "M900000001" not in llaves  # conflicto ajeno al ZIP, no se reporta
    # Acceptance criterion #10: el documento en conflicto queda bloqueado
    # (pendientes_revision), nunca resuelto en silencio ni importado.
    assert data["importadas"] == 0
    assert data["pendientes"] == 1


# ── Reproceso con Opus (issue #15: usa el lookup de la sesion) ──

def test_reprocesar_en_background_usa_lookup_de_sesion_corregidas_via_progreso(tmp_path, monkeypatch):
    db_path = tmp_path / "est.db"
    procesadas_dir = tmp_path / "procesadas"
    procesadas_dir.mkdir()
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    monkeypatch.setattr(core, "EST_PROCESADAS", str(procesadas_dir))
    monkeypatch.setattr(core, "EST_EXCEL_MAIN", str(tmp_path / "estimaciones_main.xlsx"))
    core.setup_est_db()

    def fake_vision(pdf_bytes, model=core.VISION_MODEL_PRO):
        return {"tiene_sello": True, "tiene_firma": True, "descripcion": "OCR sucio", "cantidad": 5}
    monkeypatch.setattr(core, "_procesar_pdf_sync", fake_vision)

    token = "test-token-reprocesar-corregidas"
    core.active_tokens[token] = datetime.now()
    session_id = "sesion-reprocesar-corregidas"
    info = core.parsear_nombre_pdf("06-01-M1-00000030.pdf")
    lookup = _lookup_con_fila("06-01-M1-00000030.pdf", "M100000030", "Descripcion limpia del Excel", "CEDIS")
    core.est_sessions[session_id] = {
        "importadas": [],
        "errores_vision": [{
            "nombre": "06-01-M1-00000030.pdf",
            "motivo": "error al leer el documento (previo)",
            "_pdf_bytes": b"contenido falso", "_info": info,
        }],
        "reprocess_progress": {"activo": True, "actual": 0, "total": 1, "modelo": "opus", "pendientes_nuevos": []},
        "lookup": lookup,
    }

    try:
        asyncio.run(core._reprocesar_en_background(session_id))

        client = TestClient(main.app)
        res = client.get(
            f"/api/estimaciones/reprocesar-progreso/{session_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["activo"] is False
        assert data["corregidas_lista"] == [{
            "nombre": "06-01-M1-00000030.pdf", "campo": "descripcion",
            "vision": "OCR sucio", "excel": "Descripcion limpia del Excel",
        }]
    finally:
        core.active_tokens.pop(token, None)
        core.est_sessions.pop(session_id, None)


def test_incorporar_y_reprocesar_respuesta_no_incluye_corregidas_lista(tmp_path, monkeypatch):
    # corregidas_lista NUNCA sale en la respuesta de /incorporar-y-reprocesar
    # — este endpoint responde antes de que el trabajo de reproceso exista.
    db_path = tmp_path / "est.db"
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    core.setup_est_db()

    token = "test-token-incorporar-sin-corregidas"
    core.active_tokens[token] = datetime.now()
    session_id = "sesion-incorporar-sin-corregidas"
    info = core.parsear_nombre_pdf("06-01-M1-00000031.pdf")
    core.est_sessions[session_id] = {
        "importadas": [],
        "errores_vision": [{
            "nombre": "06-01-M1-00000031.pdf",
            "motivo": "error al leer el documento (previo)",
            "_pdf_bytes": b"contenido falso", "_info": info,
        }],
        "lookup": _lookup_con_fila("06-01-M1-00000031.pdf", "M100000031", "Concreto", "CEDIS"),
    }

    client = TestClient(main.app)
    try:
        res = client.post(
            "/api/estimaciones/incorporar-y-reprocesar",
            json={"session_id": session_id},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert "corregidas_lista" not in data
        assert data["reprocesando"] is True
    finally:
        core.active_tokens.pop(token, None)
        core.est_sessions.pop(session_id, None)


# ── Regresion: descripcion OCR-sucia igual resuelve precio y catalogo correctos ──

def test_regresion_descripcion_ocr_sucia_resuelve_precio_y_catalogo_correcto():
    # Regresion directa del incidente real (2026-08-26): Vision confundio
    # Fc250 con Fc350 y leyo descripciones sucias. Con el Excel como fuente
    # de verdad, la factura queda con la descripcion limpia, el precio
    # correcto, Y matchea el renglon CORRECTO del catalogo — no el de al
    # lado, que es el riesgo mas serio senalado en el issue.
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE precios_domicem (fase TEXT, codigo TEXT, descripcion TEXT, precio_unitario REAL)")
    conn.execute("CREATE TABLE precios_vmo (codigo TEXT, fase TEXT, descripcion TEXT, precio_unitario REAL)")
    conn.execute(
        "INSERT INTO precios_domicem (fase, codigo, descripcion, precio_unitario) VALUES (?,?,?,?)",
        ("MACAO 2", "4418", 'Hormigon Fc350 revenimiento 6"+/-1"', 159.10),
    )
    conn.commit()

    catalogo = [
        {"orden": 1, "clave": "6", "descripcion": 'Hormigon Fc250 revenimiento 6"+/-1"', "precio_unitario": 100.0},
        {"orden": 2, "clave": "9", "descripcion": 'Hormigon Fc350 revenimiento 6"+/-1"', "precio_unitario": 159.10},
    ]

    nombre_base = "06-12-M8-00012439.pdf"
    info = {"fecha": "2026-06-12", "planta": "M8", "id_documento": "M800012439"}
    datos = {
        "cliente": "algo que leyo Vision, irrelevante",
        "obra": "MALESPIN MACAO 11",  # error real de Vision — se ignora por completo
        "descripcion": "fc250", "cantidad": 10,  # Vision confundio Fc250 con Fc350
    }
    lookup = _lookup_con_fila(
        nombre_base, info["id_documento"], 'Hormigon Fc350 revenimiento 6"+/-1"',
        "MACAO ALTO RESORT S.R.L (MACAO II, ESTRUCTURA)",
    )
    resultado = core._enriquecer_y_matchear(conn, datos, info, nombre_base, lookup)
    conn.close()

    assert resultado["fase"] == "MACAO 2"
    assert resultado["descripcion"] == 'Hormigon Fc350 revenimiento 6"+/-1"'
    assert resultado["precio_unitario"] == 159.10
    assert resultado["total"] == 1591.0

    catalogo_norm_a_clave = core._est_catalogo_norm_a_clave(catalogo, "DOMICEM", "MACAO 2")
    clave = catalogo_norm_a_clave.get(core._est_normalizar(resultado["descripcion"]))
    assert clave == "9"  # el renglon CORRECTO — no el de Fc250 (clave 6)


# ── Issue #17 — libro mayor de estimaciones cerradas (cerrar / reabrir) ──
#
# El seed (estimacion_acumulado_base) queda inmutable; cerrar registra en
# estimacion_cerrada en que quedo cada estimacion por (clave, serie) y el
# acumulado anterior pasa a ser seed + cerradas, sin replayar las facturas
# cubiertas por los cierres.

_DDL_ESTIMACION_CERRADA = """CREATE TABLE estimacion_cerrada (
    empresa            TEXT NOT NULL,
    fase               TEXT NOT NULL,
    clave              TEXT NOT NULL,
    serie              TEXT NOT NULL CHECK (serie IN ('principal','ppact')),
    numero_estimacion  TEXT NOT NULL,
    fecha_desde        DATE NOT NULL,
    fecha_hasta        DATE NOT NULL,
    cantidad           REAL NOT NULL CHECK (cantidad > 0),
    cerrada_en         TEXT NOT NULL,
    PRIMARY KEY (empresa, fase, clave, serie, numero_estimacion)
)"""


def _conn_cerrada(tmp_path, nombre="cerrada_test.db"):
    """_conn_acumulado() + la tabla estimacion_cerrada, en autocommit
    (isolation_level=None) porque _est_cerrar_estimacion() maneja su propia
    transaccion con BEGIN IMMEDIATE explicito."""
    conn = _conn_acumulado(tmp_path, nombre)
    conn.execute(_DDL_ESTIMACION_CERRADA)
    conn.commit()
    conn.isolation_level = None
    return conn


# Testing plan fila 1 (+2): migracion idempotente de estimacion_cerrada

def test_migracion_estimacion_cerrada_crea_tabla_y_es_idempotente(tmp_path, monkeypatch):
    """Criterio 9 — setup_est_db() crea estimacion_cerrada con el esquema del
    issue (PK compuesta, CHECK de serie y de cantidad > 0) y correrla dos
    veces no falla ni duplica."""
    db_path = tmp_path / "est_cerrada_mig.db"
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    core.setup_est_db()
    core.setup_est_db()  # segunda corrida: CREATE TABLE IF NOT EXISTS, no falla

    conn = sqlite3.connect(str(db_path))
    columnas = [c[1] for c in conn.execute("PRAGMA table_info(estimacion_cerrada)").fetchall()]
    assert columnas == ["empresa", "fase", "clave", "serie", "numero_estimacion",
                        "fecha_desde", "fecha_hasta", "cantidad", "cerrada_en"]
    # CHECK de serie: solo 'principal'/'ppact'
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO estimacion_cerrada VALUES "
                     "('VMO','CEDIS','1','otra','N01','2026-07-17','2026-08-16',5.0,'x')")
    # CHECK de cantidad: cero o negativa es un error, no una fila
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO estimacion_cerrada VALUES "
                     "('VMO','CEDIS','1','principal','N01','2026-07-17','2026-08-16',0.0,'x')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO estimacion_cerrada VALUES "
                     "('VMO','CEDIS','1','principal','N01','2026-07-17','2026-08-16',-1.0,'x')")
    conn.close()


def test_migracion_estimacion_cerrada_no_pisa_filas_existentes(tmp_path, monkeypatch):
    """Criterio 9 — re-correr la migracion con la tabla ya poblada deja las
    filas exactamente como estaban (CREATE TABLE IF NOT EXISTS no toca una
    tabla existente)."""
    db_path = tmp_path / "est_cerrada_mig2.db"
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    core.setup_est_db()
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO estimacion_cerrada VALUES "
                 "('VMO','CEDIS','1','principal','N01','2026-07-17','2026-08-16',15.0,'2026-08-28T00:00:00Z')")
    conn.commit()
    conn.close()

    core.setup_est_db()

    conn = sqlite3.connect(str(db_path))
    filas = conn.execute("SELECT * FROM estimacion_cerrada").fetchall()
    conn.close()
    assert filas == [("VMO", "CEDIS", "1", "principal", "N01",
                      "2026-07-17", "2026-08-16", 15.0, "2026-08-28T00:00:00Z")]


# Testing plan fila 2 (+3): acumulado = seed + cerradas, con 0, 1 y 2 cerradas

def test_acumulado_cero_cerradas_identico_con_tabla_ausente_o_vacia(tmp_path):
    """Sin nada cerrado el calculo es el replay de siempre desde el seed —
    y da EXACTAMENTE lo mismo con la tabla estimacion_cerrada vacia que sin
    la tabla (BD de antes de la migracion): el comportamiento previo al
    issue no cambia (criterio 5 en chico)."""
    conn = _conn_acumulado(tmp_path)  # sin tabla estimacion_cerrada
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-07-16',1000.0,NULL)"
    )
    conn.execute("INSERT INTO facturas VALUES ('H1','2026-07-20','DOMICEM','MACAO 2','Producto A',50.0,100.0,NULL)")
    conn.execute("INSERT INTO facturas VALUES ('P1','2026-08-20','DOMICEM','MACAO 2','Producto A',30.0,100.0,NULL)")
    conn.commit()
    catalogo = [{"clave": "1", "descripcion": "Producto A"}]

    r_sin_tabla = core._est_clasificar_series(conn, "DOMICEM", "MACAO 2", catalogo, "2026-08-17", "2026-09-16")
    assert r_sin_tabla["por_clave"]["1"]["principal"]["calculado"] == 1050.0
    assert r_sin_tabla["aviso_acumulado_por_factura"] == {"facturas": 1}

    conn.execute(_DDL_ESTIMACION_CERRADA)
    conn.commit()
    r_tabla_vacia = core._est_clasificar_series(conn, "DOMICEM", "MACAO 2", catalogo, "2026-08-17", "2026-09-16")
    assert r_sin_tabla == r_tabla_vacia


def test_acumulado_una_cerrada_suma_directa_sin_replayar_el_medio(tmp_path):
    """Criterio 4 — con la estimacion anterior cerrada, el acumulado es
    seed + cerrada: la factura del medio (H1, cubierta por el cierre) NO se
    replaya — si se replayara el acumulado daria 1999 en vez de 1050. Un
    cierre con cantidad en ppact ademas hace visible el acumulado de ppact
    aunque no haya base sembrada de esa serie."""
    conn = _conn_cerrada(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-07-16',1000.0,NULL)"
    )
    # factura DENTRO del periodo cerrado, con una cantidad absurda a proposito:
    # si el calculo la replayara, el resultado se iria a 1999
    conn.execute("INSERT INTO facturas VALUES ('H1','2026-07-20','DOMICEM','MACAO 2','Producto A',999.0,100.0,NULL)")
    conn.execute("INSERT INTO facturas VALUES ('P1','2026-08-20','DOMICEM','MACAO 2','Producto A',30.0,100.0,NULL)")
    conn.execute("INSERT INTO estimacion_cerrada VALUES "
                 "('DOMICEM','MACAO 2','1','principal','N01','2026-07-17','2026-08-16',50.0,'x')")
    conn.execute("INSERT INTO estimacion_cerrada VALUES "
                 "('DOMICEM','MACAO 2','1','ppact','N01','2026-07-17','2026-08-16',7.0,'x')")

    r = core._est_clasificar_series(conn, "DOMICEM", "MACAO 2",
                                    [{"clave": "1", "descripcion": "Producto A"}],
                                    "2026-08-17", "2026-09-16")
    assert r["por_clave"]["1"]["principal"]["calculado"] == 1050.0
    assert r["por_clave"]["1"]["ppact"]["calculado"] == 7.0
    assert r["aviso_acumulado_por_factura"] is None  # criterio 10: cerrada => sin aviso
    assert [f[0] for f in r["facturas_periodo"]] == ["P1"]


def test_acumulado_dos_cerradas_y_hueco_posterior_a_la_ultima(tmp_path):
    """Dos cierres consecutivos se suman ambos; una factura POSTERIOR a la
    ultima cerrada (hueco todavia no cerrado) si se replaya factura por
    factura, con su aviso — cerrar solo elimina el replay de lo cubierto."""
    conn = _conn_cerrada(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-07-16',1000.0,NULL)"
    )
    conn.execute("INSERT INTO estimacion_cerrada VALUES "
                 "('DOMICEM','MACAO 2','1','principal','N01','2026-07-17','2026-08-16',50.0,'x')")
    conn.execute("INSERT INTO estimacion_cerrada VALUES "
                 "('DOMICEM','MACAO 2','1','principal','N02','2026-08-17','2026-09-16',20.0,'x')")
    conn.execute("INSERT INTO facturas VALUES ('H1','2026-09-20','DOMICEM','MACAO 2','Producto A',5.0,100.0,NULL)")
    conn.execute("INSERT INTO facturas VALUES ('P1','2026-10-05','DOMICEM','MACAO 2','Producto A',30.0,100.0,NULL)")

    r = core._est_clasificar_series(conn, "DOMICEM", "MACAO 2",
                                    [{"clave": "1", "descripcion": "Producto A"}],
                                    "2026-10-01", "2026-10-31")
    assert r["por_clave"]["1"]["principal"]["calculado"] == 1075.0  # 1000 + 50 + 20 + 5
    assert r["aviso_acumulado_por_factura"] == {"facturas": 1}  # solo H1, lo cerrado no
    assert [f[0] for f in r["facturas_periodo"]] == ["P1"]


# Testing plan fila 3 (+2): cerrar es idempotente por numero_estimacion

def test_cerrar_dos_veces_mismo_numero_deja_los_valores_de_la_segunda(tmp_path):
    """Criterio 3 — re-cerrar el mismo numero reemplaza por completo: misma
    cantidad de filas, valores de la segunda corrida."""
    conn = _conn_cerrada(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-07-16',100.0,NULL)"
    )
    conn.execute("INSERT INTO facturas VALUES ('P1','2026-07-20','DOMICEM','MACAO 2','Producto A',10.0,100.0,NULL)")
    catalogo = [{"clave": "1", "descripcion": "Producto A"}]

    n1 = core._est_cerrar_estimacion(conn, "DOMICEM", "MACAO 2", catalogo, "N01", "2026-07-17", "2026-08-16")
    assert n1 == 1
    assert conn.execute("SELECT clave, serie, cantidad FROM estimacion_cerrada").fetchall() == [("1", "principal", 10.0)]

    conn.execute("UPDATE facturas SET cantidad = 12.0 WHERE id_documento = 'P1'")
    n2 = core._est_cerrar_estimacion(conn, "DOMICEM", "MACAO 2", catalogo, "N01", "2026-07-17", "2026-08-16")
    assert n2 == 1
    assert conn.execute("SELECT clave, serie, cantidad FROM estimacion_cerrada").fetchall() == [("1", "principal", 12.0)]


def test_recerrar_con_clave_en_cero_no_deja_viva_la_fila_vieja(tmp_path):
    """Criterio 11 — el cierre es DELETE + INSERT en una transaccion, no
    INSERT OR REPLACE: si al re-cerrar una clave quedo en cero, su fila
    vieja desaparece (con OR REPLACE sobreviviria y el acumulado quedaria
    inflado para siempre)."""
    conn = _conn_cerrada(tmp_path)
    conn.execute("INSERT INTO facturas VALUES ('P1','2026-07-20','DOMICEM','MACAO 2','Producto A',10.0,100.0,NULL)")
    conn.execute("INSERT INTO facturas VALUES ('P2','2026-07-21','DOMICEM','MACAO 2','Producto B',5.0,100.0,NULL)")
    catalogo = [{"clave": "1", "descripcion": "Producto A"},
                {"clave": "2", "descripcion": "Producto B"}]

    n1 = core._est_cerrar_estimacion(conn, "DOMICEM", "MACAO 2", catalogo, "N01", "2026-07-17", "2026-08-16")
    assert n1 == 2

    # correccion: la factura de la clave 2 se saca del periodo — al re-cerrar
    # la clave 2 queda en cero y su fila NO debe sobrevivir
    conn.execute("DELETE FROM facturas WHERE id_documento = 'P2'")
    n2 = core._est_cerrar_estimacion(conn, "DOMICEM", "MACAO 2", catalogo, "N01", "2026-07-17", "2026-08-16")
    assert n2 == 1
    assert conn.execute("SELECT clave, serie, cantidad FROM estimacion_cerrada").fetchall() == [("1", "principal", 10.0)]


# Testing plan fila 4 (+2): deteccion de solapamiento y de hueco

def test_avisos_cierre_solapamiento_inclusive_y_excluye_el_propio_numero(tmp_path):
    """Criterio 7 — solapamiento a nivel (empresa, fase) con ambos extremos
    inclusive; re-cerrar una estimacion no se solapa consigo misma."""
    conn = _conn_cerrada(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-07-16',100.0,NULL)"
    )
    conn.execute("INSERT INTO estimacion_cerrada VALUES "
                 "('DOMICEM','MACAO 2','1','principal','N01','2026-07-17','2026-08-16',10.0,'x')")

    # comparte exactamente 1 dia (el ultimo de N01): desde el issue #96 eso ya
    # no es un aviso sino un bloqueo (ver _est_cierres_solapados), asi que la
    # lista de avisos no lo trae
    assert core._est_avisos_cierre(conn, "DOMICEM", "MACAO 2", "N02", "2026-08-16", "2026-08-31") == []

    # arranca justo el dia siguiente: ni solapa ni deja hueco
    assert core._est_avisos_cierre(conn, "DOMICEM", "MACAO 2", "N02", "2026-08-17", "2026-08-31") == []

    # re-cerrar N01 con su mismo periodo: no se solapa consigo misma ni deja
    # hueco (excluida N01, la referencia vuelve a ser fecha_base 2026-07-16),
    # pero SI avisa re_cierre — hasta este cambio la lista salia vacia y el
    # DELETE + INSERT corria sin confirmacion sobre un documento entregado
    avisos = core._est_avisos_cierre(conn, "DOMICEM", "MACAO 2", "N01", "2026-07-17", "2026-08-16")
    assert [a["tipo"] for a in avisos] == ["re_cierre"]


def test_avisos_cierre_re_cierre_trae_lo_que_se_va_a_reemplazar(tmp_path):
    """El aviso re_cierre existe para que la decision se tome viendo el
    numero, no de memoria: trae el rango cerrado, cuando se cerro, cuantas
    filas y cuanta cantidad se van a borrar. Caso real: MACAO 2 tiene
    2.028,0 m3 cerrados en la clave 6 y la clasificacion de hoy daria
    2.032,5 — sin este aviso el re-cierre metia 4,5 m3 sin sello en un
    documento entregado, sin error y sin aviso."""
    conn = _conn_cerrada(tmp_path)
    conn.execute("INSERT INTO estimacion_cerrada VALUES "
                 "('DOMICEM','MACAO 2','6','principal','N01','2026-07-17','2026-08-16',2028.0,'2026-08-28T16:40:48Z')")
    conn.execute("INSERT INTO estimacion_cerrada VALUES "
                 "('DOMICEM','MACAO 2','7','ppact','N01','2026-07-17','2026-08-16',57.0,'2026-08-28T16:40:48Z')")

    avisos = core._est_avisos_cierre(conn, "DOMICEM", "MACAO 2", "N01", "2026-07-17", "2026-08-16")
    assert avisos == [{"tipo": "re_cierre", "numero_estimacion": "N01",
                       "fecha_desde": "2026-07-17", "fecha_hasta": "2026-08-16",
                       "cerrada_en": "2026-08-28T16:40:48Z", "filas": 2,
                       "cantidad_total": 2085.0}]

    # escopeado por (empresa, fase, numero): otra fase con el mismo numero no
    # dispara el aviso, igual que el resto de los chequeos de esta funcion
    assert core._est_avisos_cierre(conn, "DOMICEM", "CAVERNAS", "N01", "2026-07-17", "2026-08-16") == []
    assert core._est_avisos_cierre(conn, "VMO", "MACAO 2", "N01", "2026-07-17", "2026-08-16") == []

    # un numero que nunca se cerro es un cierre normal, sin aviso
    assert core._est_avisos_cierre(conn, "DOMICEM", "MACAO 2", "N02", "2026-08-17", "2026-09-16") == []


def test_avisos_cierre_hueco_primer_cierre_referencia_fecha_base(tmp_path):
    """Criterio 7 — hueco si fecha_desde > dia siguiente de lo ultimo
    cubierto: para el primer cierre la referencia es la fecha_base del seed,
    despues la fecha_hasta de la ultima cerrada."""
    conn = _conn_cerrada(tmp_path)
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-07-16',100.0,NULL)"
    )
    # primer cierre arrancando el dia siguiente a fecha_base: sin hueco
    assert core._est_avisos_cierre(conn, "DOMICEM", "MACAO 2", "N01", "2026-07-17", "2026-08-16") == []
    # primer cierre arrancando 2 dias despues: hueco
    avisos = core._est_avisos_cierre(conn, "DOMICEM", "MACAO 2", "N01", "2026-07-19", "2026-08-16")
    assert avisos == [{"tipo": "hueco", "ultima_cubierta": "2026-07-16", "desde_esperado": "2026-07-17"}]

    conn.execute("INSERT INTO estimacion_cerrada VALUES "
                 "('DOMICEM','MACAO 2','1','principal','N01','2026-07-17','2026-08-16',10.0,'x')")
    # el siguiente se referencia contra la ultima cerrada, no contra el seed
    avisos = core._est_avisos_cierre(conn, "DOMICEM", "MACAO 2", "N02", "2026-09-01", "2026-09-16")
    assert avisos == [{"tipo": "hueco", "ultima_cubierta": "2026-08-16", "desde_esperado": "2026-08-17"}]
    assert core._est_avisos_cierre(conn, "DOMICEM", "MACAO 2", "N02", "2026-08-17", "2026-09-16") == []


# Testing plan fila 5 (+3): generar no cierra; cerrar si escribe; reabrir revierte

def _bd_cierre_http(tmp_path, monkeypatch):
    """BD con el esquema real completo (setup_est_db, incluida
    estimacion_cerrada) + catalogo VMO/CEDIS de 2 productos, seed de la
    clave 1 (fecha_base 2026-07-16) y 3 facturas: 2 del periodo julio-agosto
    y 1 de despues."""
    db_path = tmp_path / "est_cierre_http.db"
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    core.setup_est_db()
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO catalogo_estimacion VALUES ('VMO','CEDIS',1,'1','Producto Uno',100.0)")
    conn.execute("INSERT INTO catalogo_estimacion VALUES ('VMO','CEDIS',2,'2','Producto Dos',200.0)")
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('VMO','CEDIS','1','principal','2026-07-16',100.0,500.0)"
    )
    for id_doc, fecha, cantidad in (("F1", "2026-07-20", 10.0), ("F2", "2026-07-25", 5.0),
                                    ("F3", "2026-08-20", 7.0)):
        conn.execute(
            "INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,cantidad,precio_unitario) "
            "VALUES (?,?,'VMO','CEDIS','Producto Uno',?,100.0)",
            (id_doc, fecha, cantidad),
        )
    conn.commit()
    conn.close()
    token = "test-token-cierre-http"
    core.active_tokens[token] = datetime.now()
    return token


def _filas_cerradas():
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        return conn.execute(
            "SELECT numero_estimacion, clave, serie, cantidad, fecha_desde, fecha_hasta "
            "FROM estimacion_cerrada ORDER BY numero_estimacion, clave, serie"
        ).fetchall()
    finally:
        conn.close()


def test_generar_no_escribe_en_estimacion_cerrada(tmp_path, monkeypatch):
    """Criterio 1 — generar el archivo NO cierra: se genera varias veces
    mientras se revisa, y la tabla estimacion_cerrada queda vacia."""
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    desc = 'Hormigón Fc350 kg/cm2, rev. 6"'
    facturas = [{"id_documento": "M1", "fecha": "2026-07-10", "descripcion": desc, "cantidad": 1.0}]
    token = _bd_macao2_ppact_generar(tmp_path, monkeypatch, facturas)
    conn = sqlite3.connect(core.EST_DB_PATH)
    conn.execute(_DDL_ESTIMACION_CERRADA)
    conn.commit()
    conn.close()

    client = TestClient(main.app)
    try:
        res = client.post(
            "/api/estimaciones/generar", json=_payload_generar_ppact_macao2("principal"),
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 200, res.text
    assert _filas_cerradas() == []


def test_cerrar_endpoint_escribe_y_409_con_aviso_no_escribe_nada(tmp_path, monkeypatch):
    """Criterios 2, 7 y 13 — POST /cerrar sin avisos escribe una fila por
    (clave, serie) con cantidad > 0 y su periodo; con aviso de solapamiento
    y confirmar_aviso=False responde 409 SIN escribir; re-enviado con
    confirmar_aviso=True escribe y devuelve los avisos. El seed no se toca
    en ningun caso (criterio 8)."""
    token = _bd_cierre_http(tmp_path, monkeypatch)
    client = TestClient(main.app)
    try:
        seed_antes = _filas_acumulado(core.EST_DB_PATH)

        # cierre sin avisos: arranca el dia siguiente a fecha_base
        res = client.post("/api/estimaciones/cerrar", json={
            "empresa": "VMO", "fase": "CEDIS", "numero_estimacion": "N01",
            "fecha_desde": "2026-07-17", "fecha_hasta": "2026-08-16",
            "confirmar_aviso": False,
        }, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200, res.text
        assert res.json() == {"cerradas": 1, "avisos": []}
        assert _filas_cerradas() == [("N01", "1", "principal", 15.0, "2026-07-17", "2026-08-16")]

        # GET /cerradas lo lista con su periodo y sus totales
        res = client.get("/api/estimaciones/cerradas",
                         params={"empresa": "VMO", "fase": "CEDIS"},
                         headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200, res.text
        cierres = res.json()["cerradas"]
        assert len(cierres) == 1
        assert cierres[0]["numero_estimacion"] == "N01"
        assert cierres[0]["fecha_desde"] == "2026-07-17"
        assert cierres[0]["fecha_hasta"] == "2026-08-16"
        assert cierres[0]["total_principal"] == 15.0
        assert cierres[0]["total_ppact"] == 0.0
        assert cierres[0]["filas"] == [{"clave": "1", "serie": "principal", "cantidad": 15.0}]

        # N02 con hueco (arranca el 2026-08-18, lo cubierto llega al 16):
        # 409 y NO escribe nada (criterio 13). Era un solapamiento hasta el
        # issue #96; el solapamiento ahora bloquea, asi que el aviso que se
        # prueba aca es el hueco.
        payload_hueco = {
            "empresa": "VMO", "fase": "CEDIS", "numero_estimacion": "N02",
            "fecha_desde": "2026-08-18", "fecha_hasta": "2026-08-31",
            "confirmar_aviso": False,
        }
        res = client.post("/api/estimaciones/cerrar", json=payload_hueco,
                          headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 409, res.text
        detail = res.json()["detail"]
        assert detail["error"] == "cierre_requiere_confirmacion"
        assert [a["tipo"] for a in detail["avisos"]] == ["hueco"]
        assert _filas_cerradas() == [("N01", "1", "principal", 15.0, "2026-07-17", "2026-08-16")]

        # el aviso no bloquea: con confirmacion explicita se cierra igual
        res = client.post("/api/estimaciones/cerrar",
                          json={**payload_hueco, "confirmar_aviso": True},
                          headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200, res.text
        assert res.json()["cerradas"] == 1
        assert [a["tipo"] for a in res.json()["avisos"]] == ["hueco"]
        assert _filas_cerradas() == [
            ("N01", "1", "principal", 15.0, "2026-07-17", "2026-08-16"),
            ("N02", "1", "principal", 7.0, "2026-08-18", "2026-08-31"),
        ]

        # criterio 8: el seed quedo intacto en todo el flujo
        assert _filas_acumulado(core.EST_DB_PATH) == seed_antes
    finally:
        core.active_tokens.pop(token, None)


def test_reabrir_devuelve_el_calculo_al_estado_previo_al_cierre(tmp_path, monkeypatch):
    """Criterio 6 — reabrir borra todas las filas del numero y el calculo
    vuelve EXACTAMENTE al estado previo (replay del hueco, aviso incluido).
    Reabrir algo no cerrado responde 404."""
    token = _bd_cierre_http(tmp_path, monkeypatch)
    client = TestClient(main.app)
    catalogo_cedis = [{"clave": "1", "descripcion": "Producto Uno"},
                      {"clave": "2", "descripcion": "Producto Dos"}]

    def clasificar_siguiente_periodo():
        conn = sqlite3.connect(core.EST_DB_PATH)
        try:
            return core._est_clasificar_series(conn, "VMO", "CEDIS", catalogo_cedis,
                                               "2026-08-17", "2026-09-16")
        finally:
            conn.close()

    try:
        antes = clasificar_siguiente_periodo()
        assert antes["por_clave"]["1"]["principal"]["calculado"] == 115.0
        assert antes["aviso_acumulado_por_factura"] == {"facturas": 2}

        res = client.post("/api/estimaciones/cerrar", json={
            "empresa": "VMO", "fase": "CEDIS", "numero_estimacion": "N01",
            "fecha_desde": "2026-07-17", "fecha_hasta": "2026-08-16",
            "confirmar_aviso": False,
        }, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200, res.text

        cerrado = clasificar_siguiente_periodo()
        # mismo acumulado, ahora como seed + cerrada y sin aviso (criterio 10)
        assert cerrado["por_clave"] == antes["por_clave"]
        assert cerrado["aviso_acumulado_por_factura"] is None

        # reabrir algo que no existe: 404
        res = client.post("/api/estimaciones/reabrir", json={
            "empresa": "VMO", "fase": "CEDIS", "numero_estimacion": "N99",
        }, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 404

        res = client.post("/api/estimaciones/reabrir", json={
            "empresa": "VMO", "fase": "CEDIS", "numero_estimacion": "N01",
        }, headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200, res.text
        assert res.json() == {"borradas": 1}
        assert _filas_cerradas() == []

        despues = clasificar_siguiente_periodo()
        assert despues == antes  # identico, aviso incluido
    finally:
        core.active_tokens.pop(token, None)


# Testing plan fila 6 (+1): regresion sobre datos reales — seed + cerrada
# equivale al replay, y el resultado ya no depende de las facturas del medio

def test_cerrar_las_9_fases_reales_equivale_al_replay_y_no_depende_del_medio(tmp_path, monkeypatch):
    """Criterios 4, 5, 8, 10 y 12 sobre el fixture de datos reales del issue
    #16 (bases/topes reales de las 9 fases + lotes reales del periodo
    2026-07-17..2026-08-16). El periodo siguiente clasifica IDENTICO por
    replay (sin cerrar) que por seed + cerrada (cerrado); tras cerrar, el
    aviso desaparece y BORRAR las facturas anteriores al periodo no cambia
    nada; el seed queda byte a byte igual."""
    db_path = _bd_con_catalogo_de_las_9_fases(tmp_path, monkeypatch)
    seed_acumulado_base_macao2.seed(db_path)
    seed_contrato_principal_macao2.seed(db_path)
    seed_acumulado_base_fases.seed(db_path)

    lotes_periodo1 = {
        ("DOMICEM", "CAVERNAS"): {"1": 52.0, "2": 370.0, "3": 173.0, "8": 21.0, "10": 11.5},
        ("DOMICEM", "MACAO 2"): {"6": 2028.0, "7": 57.0, "8": 6271.0, "9": 62.5},
        ("DOMICEM", "PATIO DE MANIOBRAS-TRB"): {"3": 12.5},
        ("DOMICEM", "VIVIENDAS"): {"2": 30.0, "5": 66.5, "8": 12.0},
        ("VMO", "CANCHAS"): {},
        ("VMO", "CEDIS"): {"1": 6.0, "11": 48.0},
        ("VMO", "EXTERIORES"): {"6": 316.0, "15": 29.0},
        ("VMO", "PATIO DE MANIOBRAS-TRA"): {"2": 21.0},
        ("VMO", "PODIUM-1-2-3"): {"3": 935.0},
    }
    conn = sqlite3.connect(db_path)
    i = 0
    for (empresa, fase), lotes in lotes_periodo1.items():
        for clave, cantidad in lotes.items():
            i += 1
            conn.execute(
                "INSERT INTO facturas (id_documento, fecha, empresa, fase, descripcion, cantidad, precio_unitario) "
                "VALUES (?, '2026-07-20', ?, ?, ?, ?, 100.0)",
                (f"MLOTE{i:04d}", empresa, fase, f"{fase} Producto {clave}", cantidad),
            )
        # y una entrega chica del PERIODO SIGUIENTE por fase (para que el
        # periodo 2 tenga lote propio que clasificar)
        if lotes:
            clave_p2 = sorted(lotes)[0]
            conn.execute(
                "INSERT INTO facturas (id_documento, fecha, empresa, fase, descripcion, cantidad, precio_unitario) "
                "VALUES (?, '2026-08-20', ?, ?, ?, 1.5, 100.0)",
                (f"P2-{empresa}-{fase}", empresa, fase, f"{fase} Producto {clave_p2}"),
            )
    for id_doc, cantidad in (("M800013832", 5.0), ("M800013843", 2.0)):
        conn.execute(
            "INSERT INTO facturas (id_documento, fecha, empresa, fase, descripcion, cantidad, precio_unitario) "
            "VALUES (?, '2026-07-17', 'VMO', 'CEDIS', 'CEDIS Producto 2', ?, 106.7)",
            (id_doc, cantidad),
        )
    conn.commit()
    conn.close()

    seed_antes = _filas_acumulado(db_path)

    def clasificar_periodo2(conn):
        out = {}
        for (empresa, fase) in lotes_periodo1:
            catalogo = core._est_catalogo_fase(conn, empresa, fase)
            r = core._est_clasificar_series(conn, empresa, fase, catalogo, "2026-08-17", "2026-09-16")
            out[(empresa, fase)] = r
        return out

    conn = sqlite3.connect(db_path)
    por_replay = clasificar_periodo2(conn)
    # antes de cerrar: el acumulado del periodo 2 se replaya factura por
    # factura — 1478 seria el numero real, aca es el total sintetico del lote
    total_hueco = sum((r["aviso_acumulado_por_factura"] or {}).get("facturas", 0)
                      for r in por_replay.values())
    assert total_hueco > 0
    conn.close()

    # cerrar el periodo 1 en las 9 fases con facturas
    conn = sqlite3.connect(db_path, isolation_level=None)
    for (empresa, fase), lotes in lotes_periodo1.items():
        if not lotes and (empresa, fase) != ("VMO", "CEDIS"):
            continue
        catalogo = core._est_catalogo_fase(conn, empresa, fase)
        core._est_cerrar_estimacion(conn, empresa, fase, catalogo, "NREG", "2026-07-17", "2026-08-16")
    conn.close()

    conn = sqlite3.connect(db_path)
    por_cerrada = clasificar_periodo2(conn)
    conn.close()
    for kf in por_replay:
        # criterio 4: clave por clave y serie por serie, identico acumulado.
        # 2026-09-25 (decision de Axel, lote partido por factura): el cierre
        # y el replay usan ahora LA MISMA regla, asi que la divergencia
        # historica de VMO/CEDIS clave 2 (cerrada 0/7 vs replay 28/2)
        # desaparecio — ambos dan principal 28/29 y ppact 2.0.
        replay_pc = dict(por_replay[kf]["por_clave"])
        cerrada_pc = dict(por_cerrada[kf]["por_clave"])
        if kf == ("VMO", "CEDIS"):
            assert replay_pc["2"] == {"principal": {"calculado": 28.0, "tope": 29.0},
                                      "ppact": {"calculado": 2.0}}
        assert cerrada_pc == replay_pc, kf
        assert por_cerrada[kf]["facturas_periodo"] == por_replay[kf]["facturas_periodo"], kf
        # criterio 10: cerrada la estimacion anterior, el aviso del #16 se va
        assert por_cerrada[kf]["aviso_acumulado_por_factura"] is None, kf

    # criterio 12: borrar TODAS las facturas anteriores al periodo no cambia
    # el resultado — la prueba verificable de "sin recorrer las facturas"
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM facturas WHERE fecha < '2026-08-17'")
    conn.commit()
    por_sin_medio = clasificar_periodo2(conn)
    conn.close()
    for kf in por_cerrada:
        assert por_sin_medio[kf]["por_clave"] == por_cerrada[kf]["por_clave"], kf
        assert por_sin_medio[kf]["facturas_periodo"] == por_cerrada[kf]["facturas_periodo"], kf

    # criterio 8: el seed no se movio en ningun flujo
    assert _filas_acumulado(db_path) == seed_antes


# Testing plan fila 7 (+1): E2E — generar, cerrar y volver a generar el
# periodo siguiente por los endpoints del sitio

def test_e2e_generar_cerrar_y_generar_el_periodo_siguiente(tmp_path, monkeypatch):
    """Flujo completo por HTTP: vista-previa + generar julio (no cierra),
    cerrar julio, vista-previa agosto (acumulado = seed + cerrada, sin
    aviso) y generar agosto."""
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    desc = 'Hormigón Fc350 kg/cm2, rev. 6"'
    facturas = [
        {"id_documento": "J1", "fecha": "2026-07-10", "descripcion": desc, "cantidad": 1.0},
        {"id_documento": "A1", "fecha": "2026-08-10", "descripcion": desc, "cantidad": 1.0},
    ]
    token = _bd_macao2_ppact_generar(tmp_path, monkeypatch, facturas)
    conn = sqlite3.connect(core.EST_DB_PATH)
    conn.execute(_DDL_ESTIMACION_CERRADA)
    conn.commit()
    conn.close()
    client = TestClient(main.app)
    auth = {"Authorization": f"Bearer {token}"}
    try:
        # 1) revisar y generar julio — se puede generar n veces, nada cierra
        res = client.get("/api/estimaciones/vista-previa",
                         params={"empresa": "DOMICEM", "fase": "MACAO 2",
                                 "fecha_desde": "2026-07-01", "fecha_hasta": "2026-07-31"},
                         headers=auth)
        assert res.status_code == 200, res.text
        res = client.post("/api/estimaciones/generar",
                          json=_payload_generar_ppact_macao2("principal"), headers=auth)
        assert res.status_code == 200, res.text
        assert res.json()["total_facturas"] == 1  # solo J1
        assert _filas_cerradas() == []

        # 2) cerrar julio (fecha_base del seed 2026-06-30 -> sin avisos)
        res = client.post("/api/estimaciones/cerrar", json={
            "empresa": "DOMICEM", "fase": "MACAO 2", "numero_estimacion": "N01",
            "fecha_desde": "2026-07-01", "fecha_hasta": "2026-07-31",
            "confirmar_aviso": False,
        }, headers=auth)
        assert res.status_code == 200, res.text
        assert res.json() == {"cerradas": 1, "avisos": []}

        # 3) el periodo siguiente arranca del cierre: acumulado 98 + 1 = 99,
        #    sin aviso de calculo por factura
        res = client.get("/api/estimaciones/vista-previa",
                         params={"empresa": "DOMICEM", "fase": "MACAO 2",
                                 "fecha_desde": "2026-08-01", "fecha_hasta": "2026-08-31"},
                         headers=auth)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["aviso_acumulado_por_factura"] is None
        clave6 = next(c for c in data["catalogo"] if c["clave"] == "6")
        assert clave6["principal"]["calculado"] == 99.0

        # 4) generar agosto
        payload = {**_payload_generar_ppact_macao2("principal"),
                   "fecha_desde": "2026-08-01", "fecha_hasta": "2026-08-31",
                   "numero_estimacion": "N02"}
        res = client.post("/api/estimaciones/generar", json=payload, headers=auth)
        assert res.status_code == 200, res.text
        assert res.json()["total_facturas"] == 1  # solo A1
    finally:
        core.active_tokens.pop(token, None)


# ── Issue #20 — aprobación manual de pendientes (falta sello / falta firma) ──
#
# Todos los tests son aislados y reproducibles: BD temporal construida por el
# mismo setup_est_db() de producción (sobre tmp_path) y PDFs de bytes
# cualquiera en directorios de tmp_path — nunca la BD ni los PDFs reales.
# Los 41 pendientes reales de MACAO 2 (todos debajo del corte 2026-08-16)
# son la motivación de varios casos, no el fixture.

def _bd_aprobacion(tmp_path, monkeypatch, nombre="est_aprobacion.db"):
    """BD con el esquema real completo (setup_est_db, incluidas las 5
    columnas del issue #20) + directorios de PDFs aislados en tmp_path."""
    db_path = tmp_path / nombre
    pendientes_dir = tmp_path / "pendientes_revision"
    procesadas_dir = tmp_path / "procesadas"
    pendientes_dir.mkdir(exist_ok=True)
    procesadas_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    monkeypatch.setattr(core, "EST_PENDIENTES", str(pendientes_dir))
    monkeypatch.setattr(core, "EST_PROCESADAS", str(procesadas_dir))
    core.setup_est_db()
    return db_path, pendientes_dir, procesadas_dir


# Valores representativos en las 25 columnas de pendientes_revision — todos
# distintos entre sí, para que el test de reconstrucción de la reversa
# detecte cualquier columna cruzada o perdida.
_PENDIENTE_BASE = {
    "archivo_pdf": "07-21-M8-13968.pdf", "id_documento": "M800013968",
    "fecha": "2026-07-21", "planta": "M8", "orden_compra": "OC-77",
    "referencia": "REF-5", "distancia": "12 km", "cliente": "DOMICEM SA",
    # Issue #67 — `obra` y `obra_papel` llevan valores DISTINTOS a propósito:
    # si alguna de las dos se pierde o se cruza al aprobar / revertir /
    # descartar / reponer, el bucle sobre _EST_COLUMNAS_COMPARTIDAS lo ve.
    # Issue #72 — `obra_familia` también con valor propio, por el mismo motivo
    # (las primitivas transportan lo guardado, no lo re-derivan).
    "obra": "MACAO", "obra_papel": "CONCAVA", "obra_familia": "FAMILIA-72",
    "bomba": "no", "id_producto": "D-350",
    "descripcion": "Hormigon Industrial 350 Kg/cm2", "cantidad": 3.0,
    "precio_unitario": 191.27, "total": 573.81, "ficha": "F-9",
    "chofer": "J. Perez", "hora_salida": "08:15", "observaciones": "obs x",
    "empresa": "DOMICEM", "fase": "MACAO 2", "motivo": "falta sello",
    "fecha_pendiente": "2026-07-22T09:00:00.000001",
}


def _insertar_pendiente(conn, pendientes_dir=None, **overrides):
    """Inserta un pendiente sintético (con PDF de bytes cualquiera si se
    pasa pendientes_dir) y devuelve la fila como dict."""
    fila = {**_PENDIENTE_BASE, **overrides}
    columnas = ",".join(fila)
    conn.execute(
        f"INSERT INTO pendientes_revision ({columnas}) VALUES ({','.join('?' * len(fila))})",
        tuple(fila.values()),
    )
    conn.commit()
    if pendientes_dir is not None and fila["archivo_pdf"]:
        (pendientes_dir / fila["archivo_pdf"]).write_bytes(b"%PDF-prueba issue20")
    return fila


def _conteos(conn):
    return (conn.execute("SELECT COUNT(*) FROM pendientes_revision").fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM facturas").fetchone()[0])


# ── _est_corte_de_conteo ──

def test_corte_de_conteo_sin_seed_ni_cerradas_devuelve_none(tmp_path, monkeypatch):
    _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        assert core._est_corte_de_conteo(conn, "DOMICEM", "MACAO 2") is None
    finally:
        conn.close()


def test_corte_de_conteo_solo_seed_usa_el_max_de_fecha_base(tmp_path, monkeypatch):
    _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        conn.executemany(
            "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base) "
            "VALUES (?,?,?,?,?,?)",
            [("DOMICEM", "MACAO 2", "1", "principal", "2026-06-30", 10.0),
             ("DOMICEM", "MACAO 2", "2", "principal", "2026-07-15", 5.0),
             ("VMO", "CEDIS", "1", "principal", "2026-08-01", 1.0)],  # otra fase, no cuenta
        )
        conn.commit()
        assert core._est_corte_de_conteo(conn, "DOMICEM", "MACAO 2") == "2026-07-15"
    finally:
        conn.close()


def test_corte_de_conteo_cerrada_posterior_al_seed_gana(tmp_path, monkeypatch):
    # Espejo del caso real: seed de junio, última cerrada hasta 2026-08-16 —
    # el corte vigente es el de la cerrada, igual que en _est_calcular_acumulados.
    _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        conn.execute(
            "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base) "
            "VALUES ('DOMICEM','MACAO 2','1','principal','2026-06-30',10.0)")
        conn.execute(
            "INSERT INTO estimacion_cerrada VALUES "
            "('DOMICEM','MACAO 2','1','principal','N01','2026-07-01','2026-08-16',20.0,'2026-08-28T12:00:00Z')")
        conn.commit()
        assert core._est_corte_de_conteo(conn, "DOMICEM", "MACAO 2") == "2026-08-16"
    finally:
        conn.close()


# ── _est_aprobar_pendiente: los 2 motivos aprobables, los 2 rechazados,
#    entrada vacía, id duplicado ──

def test_aprobar_falta_sello_mueve_a_facturas_con_rastro_completo(tmp_path, monkeypatch):
    _, pendientes_dir, _ = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        _insertar_pendiente(conn, pendientes_dir)
        r = core._est_aprobar_pendiente(conn, "07-21-M8-13968.pdf", "A. Oller",
                                        "el papel está bien, solo falta el timbre",
                                        ahora="2026-08-31T10:22:41.123456")
        conn.commit()
        assert r["id_documento"] == "M800013968"
        fila = conn.execute(
            "SELECT aprobado_manual, aprobado_por, aprobado_motivo, aprobado_fecha, "
            "motivo_bloqueo, sin_firma, fecha, cantidad FROM facturas WHERE id_documento='M800013968'"
        ).fetchone()
        assert fila == (1, "A. Oller", "el papel está bien, solo falta el timbre",
                        "2026-08-31T10:22:41.123456", "falta sello", 0, "2026-07-21", 3.0)
        assert conn.execute("SELECT COUNT(*) FROM pendientes_revision").fetchone()[0] == 0
    finally:
        conn.close()


def test_aprobar_falta_firma_marca_sin_firma(tmp_path, monkeypatch):
    _, pendientes_dir, _ = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        _insertar_pendiente(conn, pendientes_dir, motivo="falta firma",
                            empresa="VMO", fase="CEDIS")
        core._est_aprobar_pendiente(conn, "07-21-M8-13968.pdf", "A. Oller", "ok igual")
        conn.commit()
        fila = conn.execute(
            "SELECT sin_firma, motivo_bloqueo, aprobado_manual FROM facturas "
            "WHERE id_documento='M800013968'").fetchone()
        assert fila == (1, "falta firma", 1)
    finally:
        conn.close()


def test_aprobar_motivos_no_aprobables_rechaza_sin_cambios(tmp_path, monkeypatch):
    # La restricción central del issue: sin fila en el Excel / fase no
    # reconocida NUNCA se aprueban — se arreglan con el documento o el Excel.
    _, pendientes_dir, _ = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        for i, motivo in enumerate(("sin fila en el Excel", "fase no reconocida")):
            archivo = f"bloqueado-{i}.pdf"
            _insertar_pendiente(conn, pendientes_dir, archivo_pdf=archivo,
                                id_documento=f"DOC-BLOQ-{i}", motivo=motivo,
                                fase=None)
            antes = _conteos(conn)
            with pytest.raises(ValueError) as exc:
                core._est_aprobar_pendiente(conn, archivo, "A. Oller", "da igual")
            assert motivo in str(exc.value)
            assert _conteos(conn) == antes
            assert (pendientes_dir / archivo).exists()
    finally:
        conn.close()


def test_aprobar_entrada_vacia_o_solo_espacios_rechaza(tmp_path, monkeypatch):
    _, pendientes_dir, _ = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        _insertar_pendiente(conn, pendientes_dir)
        antes = _conteos(conn)
        for quien, motivo in (("", "ok"), ("   ", "ok"), ("yo", ""), ("yo", "   "),
                              (None, "ok"), ("yo", None)):
            with pytest.raises(ValueError):
                core._est_aprobar_pendiente(conn, "07-21-M8-13968.pdf", quien, motivo)
            assert _conteos(conn) == antes
    finally:
        conn.close()


def test_aprobar_pendiente_inexistente_rechaza(tmp_path, monkeypatch):
    _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        with pytest.raises(ValueError) as exc:
            core._est_aprobar_pendiente(conn, "no-esta.pdf", "yo", "motivo")
        assert "no existe" in str(exc.value)
    finally:
        conn.close()


def test_aprobar_id_duplicado_no_borra_el_pendiente(tmp_path, monkeypatch):
    # Criterio 9: si el INSERT falla porque el id ya existe, la fila sigue
    # en pendientes_revision y no se aprueba encima de la factura existente.
    _, pendientes_dir, _ = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        _insertar_pendiente(conn, pendientes_dir)
        conn.execute("INSERT INTO facturas (id_documento, descripcion) VALUES ('M800013968','ya estaba')")
        conn.commit()
        with pytest.raises(ValueError) as exc:
            core._est_aprobar_pendiente(conn, "07-21-M8-13968.pdf", "yo", "motivo")
        assert "M800013968" in str(exc.value)
        assert conn.execute("SELECT COUNT(*) FROM pendientes_revision").fetchone()[0] == 1
        fila = conn.execute(
            "SELECT descripcion, aprobado_manual FROM facturas WHERE id_documento='M800013968'").fetchone()
        assert fila == ("ya estaba", 0)  # la factura original quedó intacta
        assert (pendientes_dir / "07-21-M8-13968.pdf").exists()
    finally:
        conn.close()


# ── archivos: origen ausente, destino ocupado, fallo de copia con rollback,
#    orden copiar → COMMIT → borrar ──

def test_aprobar_origen_ausente_rechaza_sin_tocar_bd(tmp_path, monkeypatch):
    _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        _insertar_pendiente(conn, pendientes_dir=None)  # fila sin PDF en disco
        antes = _conteos(conn)
        with pytest.raises(ValueError) as exc:
            core._est_aprobar_pendiente(conn, "07-21-M8-13968.pdf", "yo", "motivo")
        assert "no está en pendientes_revision" in str(exc.value)
        assert _conteos(conn) == antes
    finally:
        conn.close()


def test_aprobar_destino_ocupado_rechaza_sin_tocar_bd(tmp_path, monkeypatch):
    # Nunca se sobrescribe un PDF ya procesado.
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        _insertar_pendiente(conn, pendientes_dir)
        (procesadas_dir / "07-21-M8-13968.pdf").write_bytes(b"otro pdf ya procesado")
        antes = _conteos(conn)
        with pytest.raises(ValueError) as exc:
            core._est_aprobar_pendiente(conn, "07-21-M8-13968.pdf", "yo", "motivo")
        assert "procesadas" in str(exc.value)
        assert _conteos(conn) == antes
        assert (procesadas_dir / "07-21-M8-13968.pdf").read_bytes() == b"otro pdf ya procesado"
    finally:
        conn.close()


def _token_issue20(nombre):
    token = f"test-token-issue20-{nombre}"
    core.active_tokens[token] = datetime.now()
    return token, {"Authorization": f"Bearer {token}"}


def test_endpoint_aprobar_fallo_de_copia_revierte_la_bd(tmp_path, monkeypatch):
    # Criterio 10: si la copia del PDF falla, ROLLBACK — la BD queda como
    # antes y no queda ningún archivo a medias en el destino.
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn, pendientes_dir)
    conn.close()

    def copia_que_falla(origen, destino):
        raise OSError("disco lleno simulado")
    monkeypatch.setattr(shutil, "copy2", copia_que_falla)

    token, auth = _token_issue20("copia-falla")
    try:
        client = TestClient(main.app)
        res = client.post("/api/estimaciones/pendientes-revision/aprobar",
                          json={"archivo_pdf": "07-21-M8-13968.pdf",
                                "aprobado_por": "yo", "motivo": "motivo"},
                          headers=auth)
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 500
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        assert _conteos(conn) == (1, 0)  # la BD quedó como antes
    finally:
        conn.close()
    assert (pendientes_dir / "07-21-M8-13968.pdf").exists()
    assert not (procesadas_dir / "07-21-M8-13968.pdf").exists()


def test_endpoint_aprobar_borra_el_origen_recien_despues_del_commit(tmp_path, monkeypatch):
    # El orden copiar → COMMIT → borrar origen: si el borrado final falla, la
    # BD ya está consistente y el destino ya tiene su copia — solo queda un
    # huérfano detectable en pendientes_revision/ (criterio 13). Si el orden
    # estuviera invertido, este test vería la aprobación fallar o el destino
    # vacío.
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn, pendientes_dir)
    conn.close()

    def borrado_que_falla(ruta):
        raise OSError("archivo bloqueado simulado")
    monkeypatch.setattr(os, "remove", borrado_que_falla)

    token, auth = _token_issue20("borrado-falla")
    try:
        client = TestClient(main.app)
        res = client.post("/api/estimaciones/pendientes-revision/aprobar",
                          json={"archivo_pdf": "07-21-M8-13968.pdf",
                                "aprobado_por": "yo", "motivo": "motivo"},
                          headers=auth)
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 200, res.text  # la aprobación YA quedó firme
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        assert _conteos(conn) == (0, 1)
    finally:
        conn.close()
    assert (procesadas_dir / "07-21-M8-13968.pdf").exists()   # la copia llegó
    assert (pendientes_dir / "07-21-M8-13968.pdf").exists()   # huérfano detectable


# ── fecha NULL: aprueba, cuenta_para_estimaciones=false, reversa permitida ──

def test_aprobar_fecha_null_aprueba_y_no_cuenta(tmp_path, monkeypatch):
    # pendientes_revision.fecha es nullable — el caso se resuelve del lado
    # conservador: sin fecha no se puede afirmar que vaya a contar.
    _, pendientes_dir, _ = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        _insertar_pendiente(conn, pendientes_dir, fecha=None)
        r = core._est_aprobar_pendiente(conn, "07-21-M8-13968.pdf", "yo", "motivo")
        conn.commit()
        assert r["cuenta_para_estimaciones"] is False
        assert conn.execute("SELECT fecha FROM facturas WHERE id_documento='M800013968'").fetchone()[0] is None
    finally:
        conn.close()


def test_revertir_fecha_null_procede_pese_a_cerrada_posterior(tmp_path, monkeypatch):
    # Criterio 12: NULL BETWEEN ... es NULL en SQL — la guarda del libro
    # mayor nunca matchea con fecha NULL, y es correcto: un conduce sin fecha
    # tampoco pudo entrar en ningún cierre, que se delimita por fechas.
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        _insertar_pendiente(conn, pendientes_dir, fecha=None)
        core._est_aprobar_pendiente(conn, "07-21-M8-13968.pdf", "yo", "motivo",
                                    ahora="2026-08-31T10:00:00.000000")
        shutil.move(str(pendientes_dir / "07-21-M8-13968.pdf"),
                    str(procesadas_dir / "07-21-M8-13968.pdf"))
        # cerrada que cubre "todo" y cerrada DESPUÉS de la aprobación
        conn.execute(
            "INSERT INTO estimacion_cerrada VALUES "
            "('DOMICEM','MACAO 2','1','principal','N09','2000-01-01','2099-12-31',5.0,'2026-09-01T00:00:00Z')")
        conn.commit()
        r = core._est_revertir_aprobacion(conn, "M800013968")
        conn.commit()
        assert r["archivo_pdf"] == "07-21-M8-13968.pdf"
        assert conn.execute("SELECT motivo, fecha FROM pendientes_revision").fetchone() == ("falta sello", None)
    finally:
        conn.close()


def test_endpoint_fecha_null_aprueba_avisa_y_revierte(tmp_path, monkeypatch):
    # Criterio 12 punta a punta por HTTP: cuenta_para_estimaciones=false al
    # aprobar (el frontend usa eso + fecha null para el aviso de "sin fecha
    # legible") y la reversa después funciona.
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn, pendientes_dir, fecha=None)
    conn.close()
    token, auth = _token_issue20("fecha-null")
    try:
        client = TestClient(main.app)
        res = client.post("/api/estimaciones/pendientes-revision/aprobar",
                          json={"archivo_pdf": "07-21-M8-13968.pdf",
                                "aprobado_por": "yo", "motivo": "papel ok"},
                          headers=auth)
        assert res.status_code == 200, res.text
        assert res.json()["cuenta_para_estimaciones"] is False
        res = client.post("/api/estimaciones/pendientes-revision/revertir",
                          json={"id_documento": "M800013968"}, headers=auth)
        assert res.status_code == 200, res.text
        assert res.json() == {"ok": True, "archivo_pdf": "07-21-M8-13968.pdf"}
    finally:
        core.active_tokens.pop(token, None)
    assert (pendientes_dir / "07-21-M8-13968.pdf").exists()
    assert not (procesadas_dir / "07-21-M8-13968.pdf").exists()


# ── _est_revertir_aprobacion ──

def _aprobar_y_mover(conn, pendientes_dir, procesadas_dir,
                     ahora="2026-08-31T10:00:00.000000", **overrides):
    """Aprueba el pendiente base y simula el movimiento del PDF que en
    producción hace el endpoint (copiar → commit → borrar origen)."""
    fila = _insertar_pendiente(conn, pendientes_dir, **overrides)
    core._est_aprobar_pendiente(conn, fila["archivo_pdf"], "A. Oller", "papel ok", ahora=ahora)
    conn.commit()
    shutil.move(str(pendientes_dir / fila["archivo_pdf"]),
                str(procesadas_dir / fila["archivo_pdf"]))
    return fila


def test_revertir_reconstruye_el_pendiente_completo(tmp_path, monkeypatch):
    # Criterio 6 + "las 21 columnas se reconstruyen": la reconstrucción es
    # completa, no parcial — cualquier columna cruzada o perdida se ve acá.
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        original = _aprobar_y_mover(conn, pendientes_dir, procesadas_dir)
        core._est_revertir_aprobacion(conn, "M800013968", ahora="2026-08-31T11:00:00.000000")
        conn.commit()
        cur = conn.execute("SELECT * FROM pendientes_revision")
        fila = dict(zip([c[0] for c in cur.description], cur.fetchone()))
        for col in core._EST_COLUMNAS_COMPARTIDAS:
            assert fila[col] == original[col], f"columna {col} mal reconstruida"
        assert fila["motivo"] == "falta sello"  # el motivo original, intacto
        assert fila["fecha_pendiente"] == "2026-08-31T11:00:00.000000"
        assert conn.execute("SELECT COUNT(*) FROM facturas").fetchone()[0] == 0
    finally:
        conn.close()


def test_revertir_bloqueado_por_cerrada_posterior(tmp_path, monkeypatch):
    # Criterio 7: cerrada que cubre la fecha del conduce y cerrada_en
    # POSTERIOR al aprobado_fecha → el conduce pudo haber entrado en ese
    # número, sacarlo desincronizaría el libro mayor.
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        _aprobar_y_mover(conn, pendientes_dir, procesadas_dir,
                         ahora="2026-08-31T10:00:00.000000")
        conn.execute(
            "INSERT INTO estimacion_cerrada VALUES "
            "('DOMICEM','MACAO 2','1','principal','N05','2026-07-01','2026-07-31',9.0,'2026-09-01T08:00:00Z')")
        conn.commit()
        with pytest.raises(ValueError) as exc:
            core._est_revertir_aprobacion(conn, "M800013968")
        assert "libro mayor" in str(exc.value)
        assert conn.execute("SELECT COUNT(*) FROM facturas").fetchone()[0] == 1  # nada cambió
    finally:
        conn.close()


def test_revertir_permitido_con_cerrada_anterior_o_simultanea(tmp_path, monkeypatch):
    # Criterio 7, la otra mitad: cerrada ANTES de la aprobación → el conduce
    # nunca formó parte de ese cierre, la reversa procede. La igualdad
    # exacta de instantes tampoco bloquea (`>` estricto, no `>=`) — con `>=`
    # las 41 pendientes reales quedarían irreversibles sin motivo real.
    # Marcas con offset explícito para no depender del huso de la máquina.
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        ahora = "2026-08-31T10:00:00-04:00"  # instante 2026-08-31T14:00:00Z
        _aprobar_y_mover(conn, pendientes_dir, procesadas_dir, ahora=ahora)
        conn.execute(  # 3 días antes, en cualquier huso
            "INSERT INTO estimacion_cerrada VALUES "
            "('DOMICEM','MACAO 2','1','principal','N04','2026-07-01','2026-07-31',9.0,'2026-08-28T08:00:00Z')")
        conn.execute(  # el MISMO instante que aprobado_fecha: tampoco bloquea
            "INSERT INTO estimacion_cerrada VALUES "
            "('DOMICEM','MACAO 2','2','principal','N04','2026-07-01','2026-07-31',4.0,'2026-08-31T14:00:00Z')")
        conn.commit()
        core._est_revertir_aprobacion(conn, "M800013968")
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM pendientes_revision").fetchone()[0] == 1
    finally:
        conn.close()


def test_revertir_cierre_dos_horas_antes_en_hora_local_no_bloquea(tmp_path, monkeypatch):
    # El bug que la comparación por instantes fija: cerrada_en se guarda en
    # UTC con 'Z' (issue #17) y aprobado_fecha en hora local — comparados
    # como TEXTO, un cierre hecho 2 horas ANTES de la aprobación
    # ("2026-08-31T12:00:00Z" == 08:00-04:00) tiene un string MAYOR que
    # "2026-08-31T10:00:00-04:00" y bloqueaba la reversa sin motivo real.
    # Comparados como instantes: 12:00Z < 14:00Z → la reversa procede.
    # Offsets explícitos: el resultado no depende del huso de la máquina.
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        ahora = "2026-08-31T10:00:00-04:00"  # instante 2026-08-31T14:00:00Z
        _aprobar_y_mover(conn, pendientes_dir, procesadas_dir, ahora=ahora)
        conn.execute(
            "INSERT INTO estimacion_cerrada VALUES "
            "('DOMICEM','MACAO 2','1','principal','N10','2026-07-01','2026-07-31',9.0,'2026-08-31T12:00:00Z')")
        conn.commit()
        core._est_revertir_aprobacion(conn, "M800013968")  # antes: ValueError espuria
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM pendientes_revision").fetchone()[0] == 1
    finally:
        conn.close()


def test_revertir_cierre_realmente_posterior_bloquea_como_instante(tmp_path, monkeypatch):
    # El inverso, y en la dirección PELIGROSA del bug de texto: con un huso
    # local adelantado a UTC, "2026-08-31T14:00:00Z" es un string MENOR que
    # "2026-08-31T23:00:00+10:00" (instante 13:00Z) y la comparación de
    # texto dejaría pasar la reversa de un conduce que entró en ese cierre.
    # Como instantes, 14:00Z > 13:00Z → bloquea, que es lo correcto.
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        ahora = "2026-08-31T23:00:00+10:00"  # instante 2026-08-31T13:00:00Z
        _aprobar_y_mover(conn, pendientes_dir, procesadas_dir, ahora=ahora)
        conn.execute(
            "INSERT INTO estimacion_cerrada VALUES "
            "('DOMICEM','MACAO 2','1','principal','N11','2026-07-01','2026-07-31',9.0,'2026-08-31T14:00:00Z')")
        conn.commit()
        with pytest.raises(ValueError) as exc:
            core._est_revertir_aprobacion(conn, "M800013968")
        assert "libro mayor" in str(exc.value)
        assert conn.execute("SELECT COUNT(*) FROM facturas").fetchone()[0] == 1
    finally:
        conn.close()


def test_revertir_cerrada_en_ilegible_bloquea_lado_seguro(tmp_path, monkeypatch):
    # Filas de estimacion_cerrada anteriores al issue #17 (o editadas a
    # mano) podrían traer cerrada_en en otro formato: si no parsea como
    # instante, ese cierre bloquea en vez de reventar con una excepción.
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        _aprobar_y_mover(conn, pendientes_dir, procesadas_dir,
                         ahora="2026-08-31T10:00:00-04:00")
        conn.execute(
            "INSERT INTO estimacion_cerrada VALUES "
            "('DOMICEM','MACAO 2','1','principal','N12','2026-07-01','2026-07-31',9.0,'28/08/2026 12:00')")
        conn.commit()
        with pytest.raises(ValueError) as exc:
            core._est_revertir_aprobacion(conn, "M800013968")
        assert "lado seguro" in str(exc.value)
    finally:
        conn.close()


def test_revertir_aprobado_fecha_null_o_ilegible_bloquea_lado_seguro(tmp_path, monkeypatch):
    # aprobado_fecha NULL (o ilegible) en una fila aprobado_manual=1 solo es
    # posible por edición manual — con un cierre que cubre la fecha del
    # conduce no se puede ordenar la aprobación contra ese cierre, así que
    # se bloquea por el lado seguro.
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        _aprobar_y_mover(conn, pendientes_dir, procesadas_dir)
        conn.execute(
            "INSERT INTO estimacion_cerrada VALUES "
            "('DOMICEM','MACAO 2','1','principal','N13','2026-07-01','2026-07-31',9.0,'2026-08-28T08:00:00Z')")
        for marca in (None, "no-es-una-fecha"):
            conn.execute("UPDATE facturas SET aprobado_fecha = ? WHERE id_documento='M800013968'",
                         (marca,))
            conn.commit()
            with pytest.raises(ValueError) as exc:
                core._est_revertir_aprobacion(conn, "M800013968")
            assert "lado seguro" in str(exc.value)
        assert conn.execute("SELECT COUNT(*) FROM facturas").fetchone()[0] == 1
    finally:
        conn.close()


def test_revertir_rechaza_factura_no_aprobada_a_mano(tmp_path, monkeypatch):
    _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        conn.execute("INSERT INTO facturas (id_documento, descripcion) VALUES ('F-NORMAL','importada')")
        conn.commit()
        with pytest.raises(ValueError):
            core._est_revertir_aprobacion(conn, "F-NORMAL")
        with pytest.raises(ValueError):
            core._est_revertir_aprobacion(conn, "NO-EXISTE")
        assert conn.execute("SELECT COUNT(*) FROM facturas").fetchone()[0] == 1
    finally:
        conn.close()


def test_revertir_rechaza_motivo_bloqueo_null(tmp_path, monkeypatch):
    # Solo posible por migración incompleta o edición manual — se prefiere
    # fallar ruidoso a reinsertar un pendiente sin motivo.
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        _aprobar_y_mover(conn, pendientes_dir, procesadas_dir)
        conn.execute("UPDATE facturas SET motivo_bloqueo = NULL WHERE id_documento='M800013968'")
        conn.commit()
        with pytest.raises(ValueError) as exc:
            core._est_revertir_aprobacion(conn, "M800013968")
        assert "motivo_bloqueo" in str(exc.value)
        assert conn.execute("SELECT COUNT(*) FROM facturas").fetchone()[0] == 1
    finally:
        conn.close()


# ── migración idempotente y BD vieja ──

def test_migracion_issue20_es_idempotente(tmp_path, monkeypatch):
    # Criterio 14: correr setup_est_db() dos veces sobre una BD que ya tiene
    # las 5 columnas no falla ni las duplica.
    db_path = tmp_path / "est_migracion_20.db"
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    core.setup_est_db()
    core.setup_est_db()
    conn = sqlite3.connect(str(db_path))
    columnas = [c[1] for c in conn.execute("PRAGMA table_info(facturas)").fetchall()]
    conn.close()
    for col in ("aprobado_manual", "aprobado_por", "aprobado_motivo",
                "aprobado_fecha", "motivo_bloqueo"):
        assert columnas.count(col) == 1


def test_migracion_issue20_bd_vieja_conserva_datos_y_defaults(tmp_path, monkeypatch):
    # Criterio 15: una BD anterior migra sin perder datos; las filas viejas
    # quedan con aprobado_manual=0 y el resto en NULL.
    db_path = tmp_path / "est_migracion_20_vieja.db"
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE facturas (
        id_documento TEXT PRIMARY KEY, fecha DATE, planta TEXT, orden_compra TEXT,
        referencia TEXT, distancia TEXT, cliente TEXT, obra TEXT, bomba TEXT,
        id_producto TEXT, descripcion TEXT, cantidad REAL, precio_unitario REAL,
        total REAL, ficha TEXT, chofer TEXT, hora_salida TEXT, observaciones TEXT,
        archivo_pdf TEXT, empresa TEXT, fase TEXT, fecha_importacion DATETIME
    )""")
    conn.execute(
        "INSERT INTO facturas (id_documento, fecha, cantidad, descripcion) "
        "VALUES ('F-VIEJA','2026-05-01',8.0,'de antes del issue 20')")
    conn.commit()
    conn.close()

    core.setup_est_db()

    conn = sqlite3.connect(str(db_path))
    fila = conn.execute(
        "SELECT fecha, cantidad, descripcion, aprobado_manual, aprobado_por, "
        "aprobado_motivo, aprobado_fecha, motivo_bloqueo FROM facturas "
        "WHERE id_documento='F-VIEJA'").fetchone()
    conn.close()
    assert fila == ("2026-05-01", 8.0, "de antes del issue 20", 0, None, None, None, None)


# ── endpoints: los 3 nuevos + pendientes-revision ampliado ──

def test_endpoint_aprobar_caso_feliz_mueve_bd_y_pdf(tmp_path, monkeypatch):
    # Criterio 1 por HTTP: la fila pasa a facturas con el rastro completo y
    # el PDF queda en procesadas/ y ya no está en pendientes_revision/.
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn, pendientes_dir)
    conn.close()
    token, auth = _token_issue20("caso-feliz")
    try:
        client = TestClient(main.app)
        res = client.post("/api/estimaciones/pendientes-revision/aprobar",
                          json={"archivo_pdf": "07-21-M8-13968.pdf",
                                "aprobado_por": "  A. Oller  ",  # se recorta
                                "motivo": "el papel está bien"},
                          headers=auth)
    finally:
        core.active_tokens.pop(token, None)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["ok"] is True
    assert data["id_documento"] == "M800013968"
    assert data["cuenta_para_estimaciones"] is True  # sin seed ni cerradas no hay corte
    assert data["corte"] is None
    conn = sqlite3.connect(core.EST_DB_PATH)
    fila = conn.execute(
        "SELECT aprobado_manual, aprobado_por, motivo_bloqueo FROM facturas "
        "WHERE id_documento='M800013968'").fetchone()
    conn.close()
    assert fila == (1, "A. Oller", "falta sello")
    assert (procesadas_dir / "07-21-M8-13968.pdf").exists()
    assert not (pendientes_dir / "07-21-M8-13968.pdf").exists()


def test_endpoint_aprobar_motivo_no_aprobable_da_400_sin_cambios(tmp_path, monkeypatch):
    # Criterio 3: HTTP 400, ninguna tabla modificada, ningún archivo movido —
    # verificado con conteos antes y después.
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn, pendientes_dir, motivo="sin fila en el Excel", fase=None)
    antes = _conteos(conn)
    conn.close()
    token, auth = _token_issue20("no-aprobable")
    try:
        client = TestClient(main.app)
        res = client.post("/api/estimaciones/pendientes-revision/aprobar",
                          json={"archivo_pdf": "07-21-M8-13968.pdf",
                                "aprobado_por": "yo", "motivo": "da igual"},
                          headers=auth)
    finally:
        core.active_tokens.pop(token, None)
    assert res.status_code == 400
    assert "sin fila en el Excel" in res.json()["detail"]
    conn = sqlite3.connect(core.EST_DB_PATH)
    assert _conteos(conn) == antes
    conn.close()
    assert (pendientes_dir / "07-21-M8-13968.pdf").exists()
    assert not (procesadas_dir / "07-21-M8-13968.pdf").exists()


def test_endpoint_aprobar_entrada_invalida_da_400_y_cero_cambios(tmp_path, monkeypatch):
    # Criterio 4 (vacío / solo espacios) + límites de entrada (120/500).
    _, pendientes_dir, _ = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn, pendientes_dir)
    antes = _conteos(conn)
    conn.close()
    token, auth = _token_issue20("entrada-vacia")
    casos = [
        {"aprobado_por": "", "motivo": "ok"},
        {"aprobado_por": "   ", "motivo": "ok"},
        {"aprobado_por": "yo", "motivo": ""},
        {"aprobado_por": "yo", "motivo": "   "},
        {"aprobado_por": "x" * 121, "motivo": "ok"},
        {"aprobado_por": "yo", "motivo": "x" * 501},
    ]
    try:
        client = TestClient(main.app)
        for caso in casos:
            res = client.post("/api/estimaciones/pendientes-revision/aprobar",
                              json={"archivo_pdf": "07-21-M8-13968.pdf", **caso},
                              headers=auth)
            assert res.status_code == 400, caso
    finally:
        core.active_tokens.pop(token, None)
    conn = sqlite3.connect(core.EST_DB_PATH)
    assert _conteos(conn) == antes
    conn.close()


def test_endpoint_revertir_devuelve_el_conduce_con_su_motivo(tmp_path, monkeypatch):
    # Criterio 6 por HTTP: aprobar y revertir punta a punta — el pendiente
    # vuelve con su motivo original y el PDF regresa a pendientes_revision/.
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn, pendientes_dir, motivo="falta firma", empresa="VMO", fase="CEDIS")
    conn.close()
    token, auth = _token_issue20("revertir-feliz")
    try:
        client = TestClient(main.app)
        res = client.post("/api/estimaciones/pendientes-revision/aprobar",
                          json={"archivo_pdf": "07-21-M8-13968.pdf",
                                "aprobado_por": "yo", "motivo": "papel ok"},
                          headers=auth)
        assert res.status_code == 200, res.text
        res = client.post("/api/estimaciones/pendientes-revision/revertir",
                          json={"id_documento": "M800013968"}, headers=auth)
        assert res.status_code == 200, res.text
        assert res.json() == {"ok": True, "archivo_pdf": "07-21-M8-13968.pdf"}
    finally:
        core.active_tokens.pop(token, None)
    conn = sqlite3.connect(core.EST_DB_PATH)
    fila = conn.execute("SELECT motivo, fase FROM pendientes_revision").fetchone()
    total_facturas = conn.execute("SELECT COUNT(*) FROM facturas").fetchone()[0]
    conn.close()
    assert fila == ("falta firma", "CEDIS")
    assert total_facturas == 0
    assert (pendientes_dir / "07-21-M8-13968.pdf").exists()
    assert not (procesadas_dir / "07-21-M8-13968.pdf").exists()


def test_endpoint_revertir_bloqueado_por_cerrada_posterior_da_400(tmp_path, monkeypatch):
    # Criterio 7 por HTTP — /revertir revalida la guarda aunque el listado
    # la haya precalculado: alguien pudo cerrar con la pantalla abierta.
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _aprobar_y_mover(conn, pendientes_dir, procesadas_dir, ahora="2026-08-31T10:00:00.000000")
    conn.execute(
        "INSERT INTO estimacion_cerrada VALUES "
        "('DOMICEM','MACAO 2','1','principal','N06','2026-07-01','2026-07-31',9.0,'2026-09-02T00:00:00Z')")
    conn.commit()
    conn.close()
    token, auth = _token_issue20("revertir-bloqueado")
    try:
        client = TestClient(main.app)
        res = client.post("/api/estimaciones/pendientes-revision/revertir",
                          json={"id_documento": "M800013968"}, headers=auth)
    finally:
        core.active_tokens.pop(token, None)
    assert res.status_code == 400
    assert "libro mayor" in res.json()["detail"]
    assert (procesadas_dir / "07-21-M8-13968.pdf").exists()  # el PDF no se movió


def test_endpoint_aprobados_manualmente_esquema_y_orden(tmp_path, monkeypatch):
    # El esquema exacto de 16 campos por fila, orden aprobado_fecha DESC, y
    # la elegibilidad de la reversa precalculada (reversible +
    # motivo_no_reversible, null cuando reversible es true).
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _aprobar_y_mover(conn, pendientes_dir, procesadas_dir, ahora="2026-08-31T09:00:00.000000")
    _aprobar_y_mover(conn, pendientes_dir, procesadas_dir, ahora="2026-08-31T11:00:00.000000",
                     archivo_pdf="07-22-M8-14000.pdf", id_documento="M800014000",
                     fecha="2026-07-22")
    # bloquea la reversa SOLO del primero (cerrada posterior que cubre 07-21
    # pero no 07-22)
    conn.execute(
        "INSERT INTO estimacion_cerrada VALUES "
        "('DOMICEM','MACAO 2','1','principal','N07','2026-07-21','2026-07-21',3.0,'2026-09-01T00:00:00Z')")
    # y un corte para cuenta_para_estimaciones/corte
    conn.execute(
        "INSERT INTO estimacion_acumulado_base (empresa,fase,clave,serie,fecha_base,cantidad_base) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-08-16',10.0)")
    conn.commit()
    conn.close()
    token, auth = _token_issue20("listado-aprobados")
    try:
        client = TestClient(main.app)
        res = client.get("/api/estimaciones/aprobados-manualmente", headers=auth)
    finally:
        core.active_tokens.pop(token, None)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total"] == 2
    campos_esperados = {
        "id_documento", "archivo_pdf", "fecha", "cliente", "empresa", "fase",
        "descripcion", "cantidad", "motivo_bloqueo", "aprobado_por",
        "aprobado_motivo", "aprobado_fecha", "cuenta_para_estimaciones",
        "corte", "reversible", "motivo_no_reversible",
    }
    for fila in data["filas"]:
        assert set(fila) == campos_esperados
    # orden: aprobado_fecha DESC — el de las 11:00 primero
    assert [f["id_documento"] for f in data["filas"]] == ["M800014000", "M800013968"]
    por_id = {f["id_documento"]: f for f in data["filas"]}
    assert por_id["M800013968"]["reversible"] is False
    assert "libro mayor" in por_id["M800013968"]["motivo_no_reversible"]
    assert por_id["M800014000"]["reversible"] is True
    assert por_id["M800014000"]["motivo_no_reversible"] is None
    # ambos debajo del corte 2026-08-16 → no cuentan
    for fila in data["filas"]:
        assert fila["cuenta_para_estimaciones"] is False
        assert fila["corte"] == "2026-08-16"


def test_endpoint_pendientes_revision_incluye_aprobable_cuenta_y_corte(tmp_path, monkeypatch):
    # El GET existente se amplía sin cambiar la separación macao2/otras_fases.
    _, pendientes_dir, _ = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn, pendientes_dir)  # falta sello, MACAO 2, 2026-07-21
    _insertar_pendiente(conn, pendientes_dir, archivo_pdf="08-20-M8-15000.pdf",
                        id_documento="M800015000", fecha="2026-08-20")
    _insertar_pendiente(conn, pendientes_dir, archivo_pdf="07-23-M8-14999.pdf",
                        id_documento="M800014999", motivo="sin fila en el Excel", fase=None)
    conn.execute(
        "INSERT INTO estimacion_cerrada VALUES "
        "('DOMICEM','MACAO 2','1','principal','N08','2026-07-01','2026-08-16',9.0,'2026-08-28T12:00:00Z')")
    conn.commit()
    conn.close()
    token, auth = _token_issue20("pendientes-ampliado")
    try:
        client = TestClient(main.app)
        res = client.get("/api/estimaciones/pendientes-revision", headers=auth)
    finally:
        core.active_tokens.pop(token, None)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    por_id = {f["id_documento"]: f for f in data["macao2"] + data["otras_fases"]}
    # el de julio: aprobable pero debajo del corte (el caso de los 41 reales)
    assert por_id["M800013968"]["aprobable"] is True
    assert por_id["M800013968"]["cuenta_para_estimaciones"] is False
    assert por_id["M800013968"]["corte"] == "2026-08-16"
    # el de agosto: aprobable y por encima del corte
    assert por_id["M800015000"]["aprobable"] is True
    assert por_id["M800015000"]["cuenta_para_estimaciones"] is True
    # sin fila en el Excel: nunca aprobable
    assert por_id["M800014999"]["aprobable"] is False


def test_endpoint_pendientes_revision_escaneo_vertical_es_aprobable(tmp_path, monkeypatch):
    # El flag tiene que llegarle a la pantalla: si la ruta no lo marca
    # aprobable, el boton no aparece aunque core lo acepte.
    _, pendientes_dir, _ = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn, pendientes_dir, archivo_pdf="09-04-M8-15683.pdf",
                        id_documento="M800015683", fecha="2026-09-04",
                        motivo=core.EST_MOTIVO_PAGINA_VERTICAL)
    conn.commit()
    conn.close()
    token, auth = _token_issue20("pendientes-vertical")
    try:
        res = TestClient(main.app).get("/api/estimaciones/pendientes-revision", headers=auth)
    finally:
        core.active_tokens.pop(token, None)
    assert res.status_code == 200
    data = res.json()
    fila = next(f for f in data["macao2"] + data["otras_fases"]
                if f["id_documento"] == "M800015683")
    assert fila["motivo"] == core.EST_MOTIVO_PAGINA_VERTICAL
    assert fila["aprobable"] is True


def test_endpoint_aprobar_debajo_del_corte_devuelve_cuenta_false(tmp_path, monkeypatch):
    # Criterio 5 con un espejo sintético de los 41 pendientes reales de
    # MACAO 2 (fecha 2026-07-21, corte 2026-08-16 por la estimación cerrada
    # el 2026-08-28): se aprueba igual, pero la respuesta avisa que no va a
    # sumar a ninguna estimación — sin ese aviso el botón mentiría.
    _, pendientes_dir, _ = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn, pendientes_dir)
    conn.execute(
        "INSERT INTO estimacion_cerrada VALUES "
        "('DOMICEM','MACAO 2','1','principal','N03','2026-08-01','2026-08-16',9.0,'2026-08-28T12:00:00Z')")
    conn.commit()
    conn.close()
    token, auth = _token_issue20("debajo-del-corte")
    try:
        client = TestClient(main.app)
        res = client.post("/api/estimaciones/pendientes-revision/aprobar",
                          json={"archivo_pdf": "07-21-M8-13968.pdf",
                                "aprobado_por": "yo", "motivo": "papel ok"},
                          headers=auth)
    finally:
        core.active_tokens.pop(token, None)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["cuenta_para_estimaciones"] is False
    assert data["corte"] == "2026-08-16"
    conn = sqlite3.connect(core.EST_DB_PATH)
    # el libro mayor NO se toca al aprobar
    assert conn.execute("SELECT COUNT(*) FROM estimacion_cerrada").fetchone()[0] == 1
    conn.close()


# ── regresión (criterio 8): el documento generado no cambia ──

_DESC_CATALOGO_20 = "Hormigon Industrial 350 Kg/cm2"


def _bd_regresion_documento(tmp_path, monkeypatch):
    """BD sintética DOMICEM/MACAO 2 con 1 producto de catálogo, 1 factura en
    el período de generación (2026-08-17..31), una estimación cerrada que
    fija el corte en 2026-08-16 y un pendiente `falta sello` DEBAJO del
    corte — el espejo del inventario real. Devuelve el dir de reportes."""
    _, pendientes_dir, _ = _bd_aprobacion(tmp_path, monkeypatch)
    reportes_dir = tmp_path / "reportes"
    reportes_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(reportes_dir))
    monkeypatch.setattr(core, "EST_SOFFICE", None)  # sin conversión a PDF
    conn = sqlite3.connect(core.EST_DB_PATH)
    conn.execute(
        "INSERT INTO catalogo_estimacion VALUES ('DOMICEM','MACAO 2',1,'1',?,191.27)",
        (_DESC_CATALOGO_20,))
    conn.execute(
        "INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,cantidad,precio_unitario) "
        "VALUES ('F-PERIODO','2026-08-20','DOMICEM','MACAO 2',?,7.0,191.27)",
        (_DESC_CATALOGO_20,))
    conn.execute(
        "INSERT INTO estimacion_cerrada VALUES "
        "('DOMICEM','MACAO 2','1','principal','N01','2026-06-01','2026-08-16',100.0,'2026-08-28T12:00:00Z')")
    conn.commit()
    _insertar_pendiente(conn, pendientes_dir, descripcion=_DESC_CATALOGO_20)
    conn.close()
    return reportes_dir


_PAYLOAD_REGRESION_20 = {
    "empresa": "DOMICEM", "fase": "MACAO 2",
    "fecha_desde": "2026-08-17", "fecha_hasta": "2026-08-31",
    "numero_estimacion": "N02", "fecha_estimacion": "2026-08-31", "semana": 35,
    "productos": [{"clave": "1", "cantidad_proyecto": 1000, "acumulado_anterior_cantidad": 100}],
    "reasignaciones": {}, "serie": "principal",
}


def _generar_y_copiar(client, auth, reportes_dir, destino):
    res = client.post("/api/estimaciones/generar", json=_PAYLOAD_REGRESION_20, headers=auth)
    assert res.status_code == 200, res.text
    nombre = res.json()["download_url"].rsplit("/", 1)[-1]
    # dos generaciones en el mismo segundo comparten timestamp de nombre —
    # se copia a un nombre propio para poder comparar ambas
    shutil.copyfile(os.path.join(str(reportes_dir), nombre), destino)
    return destino


def test_aprobar_debajo_del_corte_no_cambia_el_documento_generado(tmp_path, monkeypatch):
    # Criterio 8: se genera la estimación de la fase antes y después de
    # aprobar un conduce debajo del corte, y se comparan los .xlsx celda por
    # celda con openpyxl sobre TODAS las hojas: cero celdas distintas.
    reportes_dir = _bd_regresion_documento(tmp_path, monkeypatch)
    token, auth = _token_issue20("regresion-documento")
    try:
        client = TestClient(main.app)
        antes = _generar_y_copiar(client, auth, reportes_dir, str(tmp_path / "antes.xlsx"))
        res = client.post("/api/estimaciones/pendientes-revision/aprobar",
                          json={"archivo_pdf": "07-21-M8-13968.pdf",
                                "aprobado_por": "PRUEBA-QUIEN-ISSUE20",
                                "motivo": "PRUEBA-MOTIVO-ISSUE20"},
                          headers=auth)
        assert res.status_code == 200, res.text
        assert res.json()["cuenta_para_estimaciones"] is False
        despues = _generar_y_copiar(client, auth, reportes_dir, str(tmp_path / "despues.xlsx"))
    finally:
        core.active_tokens.pop(token, None)

    def _valor_comparable(v):
        # ArrayFormula no define __eq__ — dos cargas del MISMO contenido
        # nunca comparan iguales por objeto; se compara por (ref, texto)
        if isinstance(v, openpyxl.worksheet.formula.ArrayFormula):
            return ("ArrayFormula", v.ref, v.text)
        return v

    wb_antes = openpyxl.load_workbook(antes, data_only=False)
    wb_despues = openpyxl.load_workbook(despues, data_only=False)
    assert wb_antes.sheetnames == wb_despues.sheetnames
    distintas = []
    for nombre in wb_antes.sheetnames:
        ws_a, ws_d = wb_antes[nombre], wb_despues[nombre]
        for r in range(1, max(ws_a.max_row, ws_d.max_row) + 1):
            for c in range(1, max(ws_a.max_column, ws_d.max_column) + 1):
                va = _valor_comparable(ws_a.cell(r, c).value)
                vd = _valor_comparable(ws_d.cell(r, c).value)
                if va != vd:
                    distintas.append((nombre, r, c, va, vd))
    assert distintas == [], f"{len(distintas)} celdas cambiaron: {distintas[:5]}"


def test_documento_generado_no_contiene_rastro_de_aprobacion(tmp_path, monkeypatch):
    # Criterio 8, segunda mitad: en el documento generado ninguna celda de
    # ninguna hoja contiene aprobado_por, aprobado_motivo, ni las cadenas
    # "aprobado"/"aprobación manual" (insensible a mayúsculas). La marca es
    # solo interna.
    reportes_dir = _bd_regresion_documento(tmp_path, monkeypatch)
    token, auth = _token_issue20("sin-rastro")
    try:
        client = TestClient(main.app)
        res = client.post("/api/estimaciones/pendientes-revision/aprobar",
                          json={"archivo_pdf": "07-21-M8-13968.pdf",
                                "aprobado_por": "PRUEBA-QUIEN-ISSUE20",
                                "motivo": "PRUEBA-MOTIVO-ISSUE20"},
                          headers=auth)
        assert res.status_code == 200, res.text
        generado = _generar_y_copiar(client, auth, reportes_dir, str(tmp_path / "generado.xlsx"))
    finally:
        core.active_tokens.pop(token, None)

    prohibidas = ("prueba-quien-issue20", "prueba-motivo-issue20", "aprobado", "aprobación manual")
    wb = openpyxl.load_workbook(generado, data_only=False)
    halladas = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for celda in row:
                if isinstance(celda.value, str):
                    texto = celda.value.lower()
                    for cadena in prohibidas:
                        if cadena in texto:
                            halladas.append((ws.title, celda.coordinate, celda.value))
    assert halladas == [], halladas


# ══════════════════════════════════════════════════════════════════════════
# Issue #38 — el cierre no miraba pendientes_revision: los conduces del
# período que quedaban ahí se perdían para siempre (fuera del libro mayor Y
# detrás del corte). Guarda bloqueante en el cierre + descartar/reponer como
# salida legítima.
# ══════════════════════════════════════════════════════════════════════════

def _bd_descarte(tmp_path, monkeypatch, nombre="est_descarte.db"):
    """BD con el esquema real completo + los TRES directorios de PDFs
    aislados (pendientes / procesadas / descartadas) + catálogo y seed de
    DOMICEM·MACAO 2, la fase del incidente."""
    db_path = tmp_path / nombre
    pendientes_dir  = tmp_path / "pendientes_revision"
    procesadas_dir  = tmp_path / "procesadas"
    descartados_dir = tmp_path / "descartadas"
    for d in (pendientes_dir, procesadas_dir, descartados_dir):
        d.mkdir(exist_ok=True)
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    monkeypatch.setattr(core, "EST_PENDIENTES", str(pendientes_dir))
    monkeypatch.setattr(core, "EST_PROCESADAS", str(procesadas_dir))
    monkeypatch.setattr(core, "EST_DESCARTADOS", str(descartados_dir))
    core.setup_est_db()
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO catalogo_estimacion VALUES "
                 "('DOMICEM','MACAO 2',1,'1','Hormigon Industrial 350 Kg/cm2',191.27)")
    conn.execute(
        "INSERT INTO estimacion_acumulado_base "
        "(empresa,fase,clave,serie,fecha_base,cantidad_base,cantidad_proyecto_principal) "
        "VALUES ('DOMICEM','MACAO 2','1','principal','2026-07-16',100.0,99999.0)")
    for id_doc, fecha, cantidad in (("F1", "2026-07-20", 10.0), ("F2", "2026-08-10", 5.0)):
        conn.execute(
            "INSERT INTO facturas (id_documento,fecha,empresa,fase,descripcion,cantidad,precio_unitario) "
            "VALUES (?,?,'DOMICEM','MACAO 2','Hormigon Industrial 350 Kg/cm2',?,191.27)",
            (id_doc, fecha, cantidad))
    conn.commit()
    conn.close()
    return db_path, pendientes_dir, procesadas_dir, descartados_dir


_CATALOGO_MACAO2 = [{"clave": "1", "descripcion": "Hormigon Industrial 350 Kg/cm2",
                     "precio_unitario": 191.27, "orden": 1}]


def _conn_auto():
    """Conexión en autocommit — _est_cerrar_estimacion() maneja su propia
    transacción con BEGIN IMMEDIATE explícito."""
    return sqlite3.connect(core.EST_DB_PATH, isolation_level=None)


def _cerrar_macao2(conn, numero="N07", desde="2026-07-17", hasta="2026-08-16"):
    return core._est_cerrar_estimacion(conn, "DOMICEM", "MACAO 2", _CATALOGO_MACAO2,
                                       numero, desde, hasta)


def _descartados(conn):
    return conn.execute("SELECT COUNT(*) FROM pendiente_descartado").fetchone()[0]


# ── Testing plan fila 1 (+4): la guarda del cierre ──

def test_cerrar_bloquea_con_pendiente_dentro_del_periodo(tmp_path, monkeypatch):
    """Criterios 1 y 2 — un pendiente de la fase con fecha dentro del período
    frena el cierre con 400 pendientes_en_el_periodo, y estimacion_cerrada
    queda vacía. El detalle trae los 5 campos."""
    _bd_descarte(tmp_path, monkeypatch)
    conn = _conn_auto()
    try:
        _insertar_pendiente(conn)  # 2026-07-21, MACAO 2, 3.0 m³, falta sello
        with pytest.raises(HTTPException) as exc:
            _cerrar_macao2(conn)
        assert exc.value.status_code == 400
        assert exc.value.detail["error"] == "pendientes_en_el_periodo"
        assert exc.value.detail["detalle"] == [{
            "id_documento": "M800013968", "fecha": "2026-07-21", "cantidad": 3.0,
            "motivo": "falta sello", "archivo_pdf": "07-21-M8-13968.pdf"}]
        assert conn.execute("SELECT COUNT(*) FROM estimacion_cerrada").fetchone()[0] == 0
    finally:
        conn.close()


def test_cerrar_no_bloquea_con_pendiente_fuera_del_periodo(tmp_path, monkeypatch):
    """Criterio 3 — el alcance es el período, no el backlog: un pendiente de
    junio (anterior a fecha_desde) y uno de septiembre (posterior a
    fecha_hasta) no frenan nada."""
    _bd_descarte(tmp_path, monkeypatch)
    conn = _conn_auto()
    try:
        _insertar_pendiente(conn, archivo_pdf="06-05-M8-11111.pdf",
                            id_documento="M800011111", fecha="2026-06-05")
        _insertar_pendiente(conn, archivo_pdf="09-05-M8-22222.pdf",
                            id_documento="M800022222", fecha="2026-09-05")
        assert _cerrar_macao2(conn) == 1
        assert conn.execute("SELECT COUNT(*) FROM estimacion_cerrada").fetchone()[0] == 1
    finally:
        conn.close()


def test_cerrar_no_bloquea_con_pendiente_sin_fecha_ni_de_otra_fase(tmp_path, monkeypatch):
    """Criterio 4 — fecha NULL no matchea el BETWEEN y no bloquea (mismo lado
    conservador que cuenta_para_estimaciones). Un pendiente de otra fase, con
    fecha dentro del período, tampoco: la guarda es por (empresa, fase)."""
    _bd_descarte(tmp_path, monkeypatch)
    conn = _conn_auto()
    try:
        _insertar_pendiente(conn, archivo_pdf="sin-fecha.pdf",
                            id_documento="M800033333", fecha=None)
        _insertar_pendiente(conn, archivo_pdf="otra-fase.pdf", id_documento="M800044444",
                            fecha="2026-07-30", empresa="VMO", fase="CEDIS")
        assert _cerrar_macao2(conn) == 1
    finally:
        conn.close()


def test_cerrar_sin_pendientes_cierra_igual_que_antes(tmp_path, monkeypatch):
    """Criterio 18 — sin ninguna fila en pendientes_revision el cierre
    escribe exactamente lo de siempre: la guarda es un no-op."""
    _bd_descarte(tmp_path, monkeypatch)
    conn = _conn_auto()
    try:
        assert _cerrar_macao2(conn) == 1
        assert conn.execute(
            "SELECT clave, serie, cantidad FROM estimacion_cerrada"
        ).fetchall() == [("1", "principal", 15.0)]
    finally:
        conn.close()


# ── Testing plan fila 2 (+1): orden determinístico del detalle ──

def test_detalle_pendientes_ordenado_por_fecha_y_id(tmp_path, monkeypatch):
    """Criterio 15 — fecha ASC, y con empate de fecha decide id_documento
    ASC. Sin ORDER BY el detalle depende del orden de inserción y los tests
    que lo comparan entero serían intermitentes."""
    _bd_descarte(tmp_path, monkeypatch)
    conn = _conn_auto()
    try:
        # insertados a propósito en el orden inverso al esperado
        _insertar_pendiente(conn, archivo_pdf="c.pdf", id_documento="M3", fecha="2026-08-01")
        _insertar_pendiente(conn, archivo_pdf="b.pdf", id_documento="M2", fecha="2026-07-20")
        _insertar_pendiente(conn, archivo_pdf="a.pdf", id_documento="M1", fecha="2026-07-20")
        detalle = core._est_pendientes_del_periodo(
            conn, "DOMICEM", "MACAO 2", "2026-07-17", "2026-08-16")
        assert [d["id_documento"] for d in detalle] == ["M1", "M2", "M3"]
    finally:
        conn.close()


# ── Testing plan fila 3 (+4): _est_descartar_pendiente / _est_reponer_descartado ──

def test_descartar_mueve_la_fila_completa_y_no_toca_facturas(tmp_path, monkeypatch):
    """Criterio 7 (lado BD) — las 21 columnas compartidas viajan enteras a
    pendiente_descartado con el motivo original, el rastro de quién/por
    qué/cuándo y la fecha_pendiente original; facturas queda intacta."""
    _, pendientes_dir, _, _ = _bd_descarte(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        fila = _insertar_pendiente(conn, pendientes_dir)
        r = core._est_descartar_pendiente(conn, "07-21-M8-13968.pdf", "A. Oller",
                                          "sin sello, no corresponde facturar",
                                          ahora="2026-09-02T11:00:00.000001")
        conn.commit()
        assert r == {"archivo_pdf": "07-21-M8-13968.pdf", "id_documento": "M800013968"}
        cur = conn.execute("SELECT * FROM pendiente_descartado")
        guardada = dict(zip([c[0] for c in cur.description], cur.fetchone()))
        for col in core._EST_COLUMNAS_COMPARTIDAS:
            assert guardada[col] == fila[col], col
        assert guardada["motivo_bloqueo"] == "falta sello"
        assert guardada["fecha_pendiente"] == fila["fecha_pendiente"]
        assert guardada["descartado_por"] == "A. Oller"
        assert guardada["descartado_motivo"] == "sin sello, no corresponde facturar"
        assert guardada["descartado_fecha"] == "2026-09-02T11:00:00.000001"
        # el descarte NO factura: facturas queda como estaba (las 2 del fixture)
        assert _conteos(conn) == (0, 2)
    finally:
        conn.close()


def test_descartar_entrada_vacia_o_pendiente_inexistente_rechaza(tmp_path, monkeypatch):
    """Criterio 12 — quién y motivo son obligatorios (no solo espacios), y no
    se puede descartar algo que no está en pendientes_revision. Sin cambios."""
    _, pendientes_dir, _, _ = _bd_descarte(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        _insertar_pendiente(conn, pendientes_dir)
        for quien, motivo in (("   ", "ok"), ("A. Oller", "  ")):
            with pytest.raises(ValueError):
                core._est_descartar_pendiente(conn, "07-21-M8-13968.pdf", quien, motivo)
        with pytest.raises(ValueError, match="no existe ese pendiente"):
            core._est_descartar_pendiente(conn, "no-existe.pdf", "A. Oller", "motivo")
        assert _conteos(conn)[0] == 1
        assert _descartados(conn) == 0
    finally:
        conn.close()


def test_reponer_reconstruye_el_pendiente_con_su_motivo_original(tmp_path, monkeypatch):
    """Criterio 9 — el ida y vuelta devuelve la fila EXACTA: las 21 columnas,
    el motivo original y la fecha_pendiente original, y el descarte se borra."""
    _, pendientes_dir, _, descartados_dir = _bd_descarte(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        fila = _insertar_pendiente(conn, pendientes_dir)
        antes = conn.execute("SELECT * FROM pendientes_revision").fetchone()
        core._est_descartar_pendiente(conn, "07-21-M8-13968.pdf", "A. Oller", "motivo")
        conn.commit()
        # el PDF lo mueve el endpoint, no la primitiva — se simula acá
        (pendientes_dir / fila["archivo_pdf"]).rename(descartados_dir / fila["archivo_pdf"])

        core._est_reponer_descartado(conn, "07-21-M8-13968.pdf")
        conn.commit()
        assert conn.execute("SELECT * FROM pendientes_revision").fetchone() == antes
        assert _descartados(conn) == 0
    finally:
        conn.close()


def test_reponer_inexistente_o_lugar_ocupado_rechaza(tmp_path, monkeypatch):
    """Criterio 14 (lado BD) — no hay descarte con ese archivo_pdf, o su
    lugar en pendientes_revision ya lo ocupa otra fila."""
    _, pendientes_dir, _, descartados_dir = _bd_descarte(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        with pytest.raises(ValueError, match="no hay ningún descarte"):
            core._est_reponer_descartado(conn, "07-21-M8-13968.pdf")

        fila = _insertar_pendiente(conn, pendientes_dir)
        core._est_descartar_pendiente(conn, "07-21-M8-13968.pdf", "A. Oller", "motivo")
        conn.commit()
        (pendientes_dir / fila["archivo_pdf"]).rename(descartados_dir / fila["archivo_pdf"])
        # alguien resubió el mismo documento: el lugar volvió a estar ocupado
        _insertar_pendiente(conn, pendientes_dir)
        with pytest.raises(ValueError, match="ya hay un pendiente de revisión"):
            core._est_reponer_descartado(conn, "07-21-M8-13968.pdf")
        assert _descartados(conn) == 1
    finally:
        conn.close()


# ── Testing plan fila 4 (+1): doble descarte ──

def test_descartar_dos_veces_choca_contra_la_pk(tmp_path, monkeypatch):
    """Criterio 13 — el segundo descarte del mismo archivo_pdf se niega. Ojo
    con los DOS caminos: descartar dos veces seguidas falla ya por "no existe
    ese pendiente" (la fila se fue en el primero); el choque de PK real solo
    aparece si alguien resube el documento y vuelve a haber un pendiente vivo
    con el mismo archivo. Los dos son ValueError → 400."""
    _, pendientes_dir, _, descartados_dir = _bd_descarte(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        fila = _insertar_pendiente(conn, pendientes_dir)
        core._est_descartar_pendiente(conn, "07-21-M8-13968.pdf", "A. Oller", "motivo")
        conn.commit()
        (pendientes_dir / fila["archivo_pdf"]).rename(descartados_dir / fila["archivo_pdf"])

        with pytest.raises(ValueError, match="no existe ese pendiente"):
            core._est_descartar_pendiente(conn, "07-21-M8-13968.pdf", "A. Oller", "otra vez")

        # resubido: hay pendiente vivo otra vez, y ahora sí choca el archivo
        _insertar_pendiente(conn, pendientes_dir)
        with pytest.raises(ValueError, match="ya existe un PDF con ese nombre en descartadas"):
            core._est_descartar_pendiente(conn, "07-21-M8-13968.pdf", "A. Oller", "otra vez")
        # y sin el PDF de por medio, el que corta es el registro de la PK
        (descartados_dir / fila["archivo_pdf"]).unlink()
        with pytest.raises(ValueError, match="ya hay un descarte registrado"):
            core._est_descartar_pendiente(conn, "07-21-M8-13968.pdf", "A. Oller", "otra vez")
        assert _descartados(conn) == 1
    finally:
        conn.close()


# ── Testing plan fila 5 (+2): el 400 por HTTP ──

def _token_issue38(nombre):
    token = f"test-token-issue38-{nombre}"
    core.active_tokens[token] = datetime.now()
    return token, {"Authorization": f"Bearer {token}"}


_PAYLOAD_CERRAR_MACAO2 = {
    "empresa": "DOMICEM", "fase": "MACAO 2", "numero_estimacion": "N07",
    "fecha_desde": "2026-07-17", "fecha_hasta": "2026-08-16",
}


def test_endpoint_cerrar_400_pendientes_en_el_periodo_no_escribe_nada(tmp_path, monkeypatch):
    """Criterios 1, 2 y 5 — POST /cerrar responde 400 con el detalle completo
    y NO escribe en estimacion_cerrada; confirmar_aviso=true NO lo saltea (no
    es un aviso, es un bloqueo)."""
    _, pendientes_dir, _, _ = _bd_descarte(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn, pendientes_dir)
    conn.close()

    token, auth = _token_issue38("cerrar-400")
    try:
        client = TestClient(main.app)
        for confirmar in (False, True):
            res = client.post("/api/estimaciones/cerrar",
                              json={**_PAYLOAD_CERRAR_MACAO2, "confirmar_aviso": confirmar},
                              headers=auth)
            assert res.status_code == 400, res.text
            detail = res.json()["detail"]
            assert detail["error"] == "pendientes_en_el_periodo"
            assert detail["detalle"] == [{
                "id_documento": "M800013968", "fecha": "2026-07-21", "cantidad": 3.0,
                "motivo": "falta sello", "archivo_pdf": "07-21-M8-13968.pdf"}]
            assert _filas_cerradas() == []
    finally:
        core.active_tokens.pop(token, None)


def test_endpoint_cerrar_lista_los_dos_pendientes_en_orden(tmp_path, monkeypatch):
    """Criterios 2 y 15 por HTTP — el detalle lista TODOS los que bloquean,
    en orden de fecha."""
    _, pendientes_dir, _, _ = _bd_descarte(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn, pendientes_dir, archivo_pdf="07-24-M8-14137.pdf",
                        id_documento="M800014137", fecha="2026-07-24", cantidad=1.5)
    _insertar_pendiente(conn, pendientes_dir)
    conn.close()

    token, auth = _token_issue38("cerrar-orden")
    try:
        client = TestClient(main.app)
        res = client.post("/api/estimaciones/cerrar",
                          json={**_PAYLOAD_CERRAR_MACAO2, "confirmar_aviso": False},
                          headers=auth)
    finally:
        core.active_tokens.pop(token, None)
    assert res.status_code == 400, res.text
    detalle = res.json()["detail"]["detalle"]
    assert [d["id_documento"] for d in detalle] == ["M800013968", "M800014137"]
    assert [d["cantidad"] for d in detalle] == [3.0, 1.5]
    assert _filas_cerradas() == []


# ── Testing plan fila 6 (+2): descartar destraba, reponer vuelve a trabar ──

def test_endpoint_descartar_destraba_el_cierre(tmp_path, monkeypatch):
    """Criterios 7 y 8 — descartar mueve fila y PDF, no inserta en facturas,
    y el MISMO cierre que se negaba ahora pasa."""
    _, pendientes_dir, procesadas_dir, descartados_dir = _bd_descarte(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn, pendientes_dir)
    conn.close()

    token, auth = _token_issue38("descartar-destraba")
    try:
        client = TestClient(main.app)
        assert client.post("/api/estimaciones/cerrar",
                           json={**_PAYLOAD_CERRAR_MACAO2, "confirmar_aviso": False},
                           headers=auth).status_code == 400

        res = client.post("/api/estimaciones/pendientes-revision/descartar",
                          json={"archivo_pdf": "07-21-M8-13968.pdf",
                                "descartado_por": "A. Oller",
                                "motivo": "sin sello, no corresponde facturar"},
                          headers=auth)
        assert res.status_code == 200, res.text
        assert res.json() == {"ok": True, "archivo_pdf": "07-21-M8-13968.pdf",
                              "id_documento": "M800013968"}
        assert (descartados_dir / "07-21-M8-13968.pdf").exists()
        assert not (pendientes_dir / "07-21-M8-13968.pdf").exists()
        assert not (procesadas_dir / "07-21-M8-13968.pdf").exists()

        res = client.post("/api/estimaciones/cerrar",
                          json={**_PAYLOAD_CERRAR_MACAO2, "confirmar_aviso": False},
                          headers=auth)
        assert res.status_code == 200, res.text
        assert res.json()["cerradas"] == 1
    finally:
        core.active_tokens.pop(token, None)

    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        assert _conteos(conn) == (0, 2)  # el descartado NO entró a facturas
        assert _descartados(conn) == 1
    finally:
        conn.close()


def test_endpoint_reponer_vuelve_a_bloquear_el_cierre(tmp_path, monkeypatch):
    """Criterio 9 por HTTP — reponer devuelve fila y PDF a pendientes con su
    motivo y su fecha_pendiente originales, y el cierre vuelve a negarse.
    Descartar no es una puerta de una sola dirección."""
    _, pendientes_dir, _, descartados_dir = _bd_descarte(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn, pendientes_dir)
    conn.close()

    token, auth = _token_issue38("reponer")
    try:
        client = TestClient(main.app)
        client.post("/api/estimaciones/pendientes-revision/descartar",
                    json={"archivo_pdf": "07-21-M8-13968.pdf",
                          "descartado_por": "A. Oller", "motivo": "me equivoqué"},
                    headers=auth)
        res = client.post("/api/estimaciones/pendientes-revision/reponer",
                          json={"archivo_pdf": "07-21-M8-13968.pdf"}, headers=auth)
        assert res.status_code == 200, res.text
        assert (pendientes_dir / "07-21-M8-13968.pdf").exists()
        assert not (descartados_dir / "07-21-M8-13968.pdf").exists()

        res = client.post("/api/estimaciones/cerrar",
                          json={**_PAYLOAD_CERRAR_MACAO2, "confirmar_aviso": False},
                          headers=auth)
        assert res.status_code == 400, res.text
        assert res.json()["detail"]["error"] == "pendientes_en_el_periodo"
    finally:
        core.active_tokens.pop(token, None)

    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        assert conn.execute("SELECT motivo, fecha_pendiente FROM pendientes_revision"
                            ).fetchone() == ("falta sello", "2026-07-22T09:00:00.000001")
        assert _descartados(conn) == 0
    finally:
        conn.close()


# ── Testing plan fila 7 (+4): guardas de archivo y límites de entrada ──

def test_endpoint_descartar_path_traversal_da_400(tmp_path, monkeypatch):
    """Criterio 10 — un archivo_pdf con `../` se rechaza con 400 antes de
    tocar disco, misma guarda (_nombre_archivo_seguro) que /aprobar."""
    _, pendientes_dir, _, descartados_dir = _bd_descarte(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn, pendientes_dir)
    conn.close()
    afuera = tmp_path / "objetivo.pdf"
    afuera.write_bytes(b"%PDF-no-tocar")

    token, auth = _token_issue38("traversal")
    try:
        client = TestClient(main.app)
        for ruta in ("../objetivo.pdf", "..\\objetivo.pdf"):
            for endpoint in ("descartar", "reponer"):
                cuerpo = {"archivo_pdf": ruta}
                if endpoint == "descartar":
                    cuerpo.update({"descartado_por": "x", "motivo": "y"})
                res = client.post(f"/api/estimaciones/pendientes-revision/{endpoint}",
                                  json=cuerpo, headers=auth)
                assert res.status_code == 400, res.text
    finally:
        core.active_tokens.pop(token, None)
    assert afuera.read_bytes() == b"%PDF-no-tocar"
    assert list(descartados_dir.iterdir()) == []
    assert (pendientes_dir / "07-21-M8-13968.pdf").exists()


def test_endpoint_descartar_origen_ausente_o_destino_ocupado_da_400(tmp_path, monkeypatch):
    """Criterio 12 — las dos guardas de archivo del descarte: el PDF tiene
    que estar en pendientes_revision/ y su lugar en descartadas/ tiene que
    estar libre. En los dos casos, cero cambios."""
    _, pendientes_dir, _, descartados_dir = _bd_descarte(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn)  # fila sin PDF: el origen no existe
    conn.close()

    token, auth = _token_issue38("guardas-descartar")
    cuerpo = {"archivo_pdf": "07-21-M8-13968.pdf", "descartado_por": "x", "motivo": "y"}
    try:
        client = TestClient(main.app)
        res = client.post("/api/estimaciones/pendientes-revision/descartar",
                          json=cuerpo, headers=auth)
        assert res.status_code == 400, res.text
        assert "pendientes_revision" in res.json()["detail"]

        # ahora el origen existe pero el destino está ocupado
        (pendientes_dir / "07-21-M8-13968.pdf").write_bytes(b"%PDF-origen")
        (descartados_dir / "07-21-M8-13968.pdf").write_bytes(b"%PDF-ocupando")
        res = client.post("/api/estimaciones/pendientes-revision/descartar",
                          json=cuerpo, headers=auth)
        assert res.status_code == 400, res.text
        assert "descartadas" in res.json()["detail"]
    finally:
        core.active_tokens.pop(token, None)

    assert (descartados_dir / "07-21-M8-13968.pdf").read_bytes() == b"%PDF-ocupando"
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        assert _conteos(conn)[0] == 1
        assert _descartados(conn) == 0
    finally:
        conn.close()


def test_endpoint_descartar_limites_de_entrada_dan_400_no_422(tmp_path, monkeypatch):
    """Criterio 11 — >120 en quién y >500 en motivo responden 400 (entrada
    que el operador puede corregir), no el 422 genérico de pydantic."""
    _, pendientes_dir, _, _ = _bd_descarte(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn, pendientes_dir)
    conn.close()

    token, auth = _token_issue38("limites")
    try:
        client = TestClient(main.app)
        for cuerpo in ({"archivo_pdf": "07-21-M8-13968.pdf",
                        "descartado_por": "x" * 121, "motivo": "ok"},
                       {"archivo_pdf": "07-21-M8-13968.pdf",
                        "descartado_por": "ok", "motivo": "y" * 501},
                       {"archivo_pdf": "07-21-M8-13968.pdf",
                        "descartado_por": "   ", "motivo": "ok"}):
            res = client.post("/api/estimaciones/pendientes-revision/descartar",
                              json=cuerpo, headers=auth)
            assert res.status_code == 400, res.text
    finally:
        core.active_tokens.pop(token, None)

    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        assert _conteos(conn)[0] == 1
        assert _descartados(conn) == 0
    finally:
        conn.close()


def test_endpoint_reponer_guardas_de_archivo_dan_400(tmp_path, monkeypatch):
    """Criterio 14 — reponer sin descarte registrado, y con el PDF ausente de
    descartadas/ (fila viva pero archivo perdido): 400 en los dos casos, sin
    reinsertar nada en pendientes_revision."""
    _, pendientes_dir, _, descartados_dir = _bd_descarte(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn, pendientes_dir)
    conn.close()

    token, auth = _token_issue38("guardas-reponer")
    try:
        client = TestClient(main.app)
        res = client.post("/api/estimaciones/pendientes-revision/reponer",
                          json={"archivo_pdf": "no-existe.pdf"}, headers=auth)
        assert res.status_code == 400, res.text
        assert "descarte" in res.json()["detail"]

        client.post("/api/estimaciones/pendientes-revision/descartar",
                    json={"archivo_pdf": "07-21-M8-13968.pdf",
                          "descartado_por": "x", "motivo": "y"}, headers=auth)
        (descartados_dir / "07-21-M8-13968.pdf").unlink()  # PDF perdido a mano
        res = client.post("/api/estimaciones/pendientes-revision/reponer",
                          json={"archivo_pdf": "07-21-M8-13968.pdf"}, headers=auth)
        assert res.status_code == 400, res.text
        assert "descartadas" in res.json()["detail"]
    finally:
        core.active_tokens.pop(token, None)

    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        assert _conteos(conn)[0] == 0
        assert _descartados(conn) == 1  # el rastro sobrevive: no se pierde el dato
    finally:
        conn.close()


# ── Testing plan fila 8 (+1): la carrera ──

def test_cerrar_chequea_pendientes_dentro_del_begin_immediate(tmp_path, monkeypatch):
    """Criterio 16 — la consulta de pendientes corre DENTRO del BEGIN
    IMMEDIATE: mientras el cierre está en curso, una segunda conexión no
    puede insertar en pendientes_revision (la base está bloqueada), así que
    no hay ventana entre el chequeo y el INSERT donde colarse.

    Si el chequeo volviera afuera de la transacción, el INSERT de la segunda
    conexión pasaría sin error y este test fallaría en el pytest.raises."""
    _bd_descarte(tmp_path, monkeypatch)
    intruso = {"resultado": None}
    original = core._est_pendientes_del_periodo

    def con_intruso(conn, *args, **kwargs):
        salida = original(conn, *args, **kwargs)
        otra = sqlite3.connect(core.EST_DB_PATH, timeout=0.2)
        try:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                otra.execute(
                    "INSERT INTO pendientes_revision (archivo_pdf,id_documento,fecha,"
                    "empresa,fase,cantidad,motivo) VALUES "
                    "('tarde.pdf','M9','2026-07-30','DOMICEM','MACAO 2',9.0,'falta sello')")
                otra.commit()
            intruso["resultado"] = "bloqueado"
        finally:
            otra.close()
        return salida

    monkeypatch.setattr(core, "_est_pendientes_del_periodo", con_intruso)
    conn = _conn_auto()
    try:
        assert _cerrar_macao2(conn) == 1
        assert intruso["resultado"] == "bloqueado"
        # y el intruso nunca llegó a la tabla
        assert conn.execute("SELECT COUNT(*) FROM pendientes_revision").fetchone()[0] == 0
        assert conn.execute(
            "SELECT clave, cantidad FROM estimacion_cerrada").fetchall() == [("1", 15.0)]
    finally:
        conn.close()


def test_cerrar_clasifica_las_facturas_dentro_del_begin_immediate(tmp_path, monkeypatch):
    """Las sumas que se escriben en estimacion_cerrada salen de
    _est_clasificar_series(). Si esa lectura corre FUERA de la transaccion,
    mover el chequeo de pendientes adentro no cierra la carrera, solo la
    achica: entre la clasificacion y el INSERT alguien puede aprobar un
    pendiente del periodo, el chequeo de pendientes pasa limpio (la fila ya
    salio de pendientes_revision) y el cierre escribe sumas viejas que no
    incluyen esa factura — exactamente la perdida del issue #38, por una
    ventana mas chica.

    El hermano de arriba hookea _est_pendientes_del_periodo, que corre bajo el
    lock en las dos disposiciones, asi que no puede detectar esto. Este hookea
    _est_clasificar_series: si volviera afuera del BEGIN IMMEDIATE, el INSERT
    de la segunda conexion pasaria y el pytest.raises fallaria.
    """
    _bd_descarte(tmp_path, monkeypatch)
    intruso = {"resultado": None}
    original = core._est_clasificar_series

    def con_intruso(conn, *args, **kwargs):
        salida = original(conn, *args, **kwargs)
        otra = sqlite3.connect(core.EST_DB_PATH, timeout=0.2)
        try:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                otra.execute(
                    "INSERT INTO pendientes_revision (archivo_pdf,id_documento,fecha,"
                    "empresa,fase,cantidad,motivo) VALUES "
                    "('tarde2.pdf','M99','2026-07-30','DOMICEM','MACAO 2',9.0,'falta sello')")
                otra.commit()
            intruso["resultado"] = "bloqueado"
        finally:
            otra.close()
        return salida

    monkeypatch.setattr(core, "_est_clasificar_series", con_intruso)
    conn = _conn_auto()
    try:
        assert _cerrar_macao2(conn) == 1
        assert intruso["resultado"] == "bloqueado", (
            "_est_clasificar_series corrio fuera del BEGIN IMMEDIATE — la "
            "segunda conexion pudo escribir mientras el cierre decidia"
        )
        assert conn.execute("SELECT COUNT(*) FROM pendientes_revision").fetchone()[0] == 0
        assert conn.execute(
            "SELECT clave, cantidad FROM estimacion_cerrada").fetchall() == [("1", 15.0)]
    finally:
        conn.close()


# ── Testing plan fila 9 (+1): el incidente real ──

def test_regresion_incidente_macao2_los_dos_conduces_frenan_el_cierre(tmp_path, monkeypatch):
    """Criterio 6 — reproducción del incidente que motivó el issue: el cierre
    de MACAO 2 del 2026-07-17 al 2026-08-16 se hizo con M800013968 (3,0 m³) y
    M800014137 (1,5 m³) todavía en pendientes_revision. Se aprobaron tres
    días después y esos 4,5 m³ hoy no se le facturan a nadie: quedaron fuera
    del libro mayor Y detrás del corte 2026-08-16.

    Con la guarda, ese cierre no se puede hacer."""
    _, pendientes_dir, _, _ = _bd_descarte(tmp_path, monkeypatch)
    conn = _conn_auto()
    try:
        _insertar_pendiente(conn, pendientes_dir)  # M800013968, 2026-07-21, 3.0
        _insertar_pendiente(conn, pendientes_dir, archivo_pdf="07-24-M8-14137.pdf",
                            id_documento="M800014137", fecha="2026-07-24",
                            cantidad=1.5, precio_unitario=None, total=None)
        with pytest.raises(HTTPException) as exc:
            _cerrar_macao2(conn)
        detalle = exc.value.detail["detalle"]
        assert [d["id_documento"] for d in detalle] == ["M800013968", "M800014137"]
        assert sum(d["cantidad"] for d in detalle) == 4.5
        assert conn.execute("SELECT COUNT(*) FROM estimacion_cerrada").fetchone()[0] == 0

        # el corte de la fase NO se movió: los 4,5 m³ siguen siendo alcanzables
        assert core._est_corte_de_conteo(conn, "DOMICEM", "MACAO 2") == "2026-07-16"
    finally:
        conn.close()


# ── Migración y listado del rastro ──

def test_migracion_pendiente_descartado_es_idempotente(tmp_path, monkeypatch):
    """setup_est_db() crea pendiente_descartado con su PK y su índice, y
    correrla dos veces no falla ni pierde filas."""
    _, pendientes_dir, _, _ = _bd_descarte(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn, pendientes_dir)
    core._est_descartar_pendiente(conn, "07-21-M8-13968.pdf", "A. Oller", "motivo")
    conn.commit()
    conn.close()

    core.setup_est_db()
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        assert _descartados(conn) == 1
        cols = [r[1] for r in conn.execute("PRAGMA table_info(pendiente_descartado)")]
        assert cols[0] == "archivo_pdf"
        assert set(core._EST_COLUMNAS_COMPARTIDAS).issubset(cols)
        assert {"motivo_bloqueo", "descartado_por", "descartado_motivo",
                "descartado_fecha", "fecha_pendiente"}.issubset(cols)
        assert conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='index' "
            "AND name='idx_pendiente_descartado_id'").fetchone()[0] == 1
    finally:
        conn.close()


def test_endpoint_descartados_lista_el_rastro(tmp_path, monkeypatch):
    """GET /descartados — el rastro permanente y la única forma de llegar al
    botón Reponer desde el panel."""
    _, pendientes_dir, _, _ = _bd_descarte(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    _insertar_pendiente(conn, pendientes_dir)
    conn.close()

    token, auth = _token_issue38("listado")
    try:
        client = TestClient(main.app)
        assert client.get("/api/estimaciones/descartados",
                          headers=auth).json() == {"total": 0, "filas": []}
        client.post("/api/estimaciones/pendientes-revision/descartar",
                    json={"archivo_pdf": "07-21-M8-13968.pdf",
                          "descartado_por": "A. Oller", "motivo": "sin sello"},
                    headers=auth)
        data = client.get("/api/estimaciones/descartados", headers=auth).json()
    finally:
        core.active_tokens.pop(token, None)

    assert data["total"] == 1
    fila = data["filas"][0]
    assert fila["archivo_pdf"] == "07-21-M8-13968.pdf"
    assert fila["id_documento"] == "M800013968"
    assert fila["motivo_bloqueo"] == "falta sello"
    assert fila["descartado_por"] == "A. Oller"
    assert fila["descartado_motivo"] == "sin sello"
    assert fila["cantidad"] == 3.0


# ── Issue #67 — obra_papel: la línea `OBRA:` del papel ────────────────────
#
# El conduce trae impresa una línea `OBRA:` con la obra real de destino
# (DIMECA, CONCAVA, LIDOMI). Es un dato distinto de `Cliente:` —que en las
# tres dice lo mismo— y no se guardaba en ninguna columna: medido el
# 2026-09-07, esos tres valores no aparecen ni una vez en `obra`, `cliente`,
# `referencia` ni `observaciones` de las 4.185 filas de `facturas`.
#
# `obra` NO se toca: hoy tiene dos semánticas según el camino (por el import
# masivo vale la fase, por el individual lo que devuelva Vision) y unificarlas
# no es este issue. Los tests de más abajo afirman las dos cosas a la vez:
# obra_papel llega, y `obra` sigue valiendo lo de siempre.

def _token_issue67(nombre):
    token = f"test-token-issue67-{nombre}"
    core.active_tokens[token] = datetime.now()
    return token, {"Authorization": f"Bearer {token}"}


def test_setup_est_db_migra_obra_papel_en_las_tres_tablas(tmp_path, monkeypatch):
    """Una BD anterior al issue #67 —las tres tablas SIN obra_papel y con
    filas dentro— gana la columna sin perder nada, y correr la migración dos
    veces no falla. Es la migración de una instalación real: las 4.185 filas
    de producción quedan con obra_papel NULL y su `obra` intacta."""
    db_path = tmp_path / "est_obra_papel.db"
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE facturas (
        id_documento TEXT PRIMARY KEY, fecha DATE, planta TEXT, orden_compra TEXT,
        referencia TEXT, distancia TEXT, cliente TEXT, obra TEXT, bomba TEXT,
        id_producto TEXT, descripcion TEXT, cantidad REAL, precio_unitario REAL,
        total REAL, ficha TEXT, chofer TEXT, hora_salida TEXT, observaciones TEXT,
        archivo_pdf TEXT, empresa TEXT, fase TEXT, fecha_importacion DATETIME
    )""")
    conn.execute("""CREATE TABLE pendientes_revision (
        archivo_pdf TEXT PRIMARY KEY, id_documento TEXT, fecha DATE, planta TEXT,
        orden_compra TEXT, referencia TEXT, distancia TEXT, cliente TEXT, obra TEXT,
        bomba TEXT, id_producto TEXT, descripcion TEXT, cantidad REAL,
        precio_unitario REAL, total REAL, ficha TEXT, chofer TEXT, hora_salida TEXT,
        observaciones TEXT, empresa TEXT, fase TEXT, motivo TEXT, fecha_pendiente DATETIME
    )""")
    conn.execute("""CREATE TABLE pendiente_descartado (
        archivo_pdf TEXT PRIMARY KEY, id_documento TEXT, fecha DATE, planta TEXT,
        orden_compra TEXT, referencia TEXT, distancia TEXT, cliente TEXT, obra TEXT,
        bomba TEXT, id_producto TEXT, descripcion TEXT, cantidad REAL,
        precio_unitario REAL, total REAL, ficha TEXT, chofer TEXT, hora_salida TEXT,
        observaciones TEXT, empresa TEXT, fase TEXT, fecha_pendiente DATETIME,
        motivo_bloqueo TEXT, descartado_por TEXT NOT NULL,
        descartado_motivo TEXT NOT NULL, descartado_fecha TEXT NOT NULL
    )""")
    conn.execute("INSERT INTO facturas (id_documento, obra, cantidad) "
                 "VALUES ('F-VIEJA','CAVERNAS',8.0)")
    conn.execute("INSERT INTO pendientes_revision (archivo_pdf, obra) "
                 "VALUES ('p.pdf','CAVERNAS')")
    conn.execute("INSERT INTO pendiente_descartado (archivo_pdf, obra, descartado_por, "
                 "descartado_motivo, descartado_fecha) "
                 "VALUES ('d.pdf','CAVERNAS','A. Oller','x','2026-09-07T00:00:00')")
    conn.commit()
    conn.close()

    core.setup_est_db()
    core.setup_est_db()  # idempotente: el ALTER TABLE no se repite

    conn = sqlite3.connect(str(db_path))
    try:
        for tabla in ("facturas", "pendientes_revision", "pendiente_descartado"):
            columnas = {c[1] for c in conn.execute(f"PRAGMA table_info({tabla})")}
            assert "obra_papel" in columnas, tabla
            assert "obra" in columnas, f"{tabla}: la columna obra NO se toca"
            assert conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0] == 1, tabla
        # las filas viejas: obra intacta, obra_papel NULL (la rellena
        # scripts/backfill_obra_papel.py, no la migración)
        assert conn.execute("SELECT obra, obra_papel, cantidad FROM facturas").fetchone() \
            == ("CAVERNAS", None, 8.0)
        assert conn.execute("SELECT obra, obra_papel FROM pendientes_revision").fetchone() \
            == ("CAVERNAS", None)
        assert conn.execute("SELECT obra, obra_papel FROM pendiente_descartado").fetchone() \
            == ("CAVERNAS", None)
    finally:
        conn.close()


def test_aprobar_y_revertir_preservan_obra_papel(tmp_path, monkeypatch):
    """El test que agarra el olvido en _EST_COLUMNAS_COMPARTIDAS: aprobar
    reconstruye el registro de `facturas` con esa tupla y revertir rehace el
    pendiente con la misma. Si obra_papel no está en la tupla, el dato se
    pierde EN SILENCIO en el primer clic de Aprobar — nada falla.

    `obra` y `obra_papel` llevan valores distintos (MACAO / CONCAVA) para
    que un cruce entre las dos columnas también se vea."""
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        _aprobar_y_mover(conn, pendientes_dir, procesadas_dir)
        assert conn.execute(
            "SELECT obra, obra_papel FROM facturas WHERE id_documento='M800013968'"
        ).fetchone() == ("MACAO", "CONCAVA")

        core._est_revertir_aprobacion(conn, "M800013968",
                                      ahora="2026-08-31T11:00:00.000000")
        conn.commit()
        assert conn.execute(
            "SELECT obra, obra_papel FROM pendientes_revision"
        ).fetchone() == ("MACAO", "CONCAVA")
    finally:
        conn.close()


def test_descartar_y_reponer_preservan_obra_papel(tmp_path, monkeypatch):
    """La otra pareja que se arma con _EST_COLUMNAS_COMPARTIDAS: descartar
    archiva la fila y reponer la devuelve. Ida y vuelta sin perder el dato."""
    _, pendientes_dir, _, descartados_dir = _bd_descarte(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        _insertar_pendiente(conn, pendientes_dir)
        core._est_descartar_pendiente(conn, "07-21-M8-13968.pdf", "A. Oller", "no va")
        conn.commit()
        assert conn.execute(
            "SELECT obra, obra_papel FROM pendiente_descartado"
        ).fetchone() == ("MACAO", "CONCAVA")

        # el endpoint mueve el PDF; acá se simula para que reponer pase sus guardas
        shutil.move(str(pendientes_dir / "07-21-M8-13968.pdf"),
                    str(descartados_dir / "07-21-M8-13968.pdf"))
        core._est_reponer_descartado(conn, "07-21-M8-13968.pdf")
        conn.commit()
        assert conn.execute(
            "SELECT obra, obra_papel FROM pendientes_revision"
        ).fetchone() == ("MACAO", "CONCAVA")
    finally:
        conn.close()


def test_enriquecer_guarda_la_obra_del_papel_sin_tocar_obra(tmp_path, monkeypatch):
    """Camino individual: lo que Vision leyó en `obra` (la línea `OBRA:`)
    también queda en obra_papel, y `obra` sigue recibiendo lo mismo que
    siempre. La fase se sigue derivando del Cliente del EXCEL, no de la obra
    — tocar obra_papel no puede mover ninguna clasificación."""
    monkeypatch.setattr(core, "EST_DB_PATH", str(tmp_path / "est.db"))
    core.setup_est_db()
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        lookup = {
            "por_archivo": {"06-30-m8-13170.pdf": {
                "id_documento": "M800013170",
                "descripcion": "Hormigon Industrial 350 Kg/cm2",
                "cliente": "MACAO ALTO RESORT SRL (CIUDAD PALACE - CAVERNAS Y EXT)"}},
            "por_id": {}, "conflictos": {}, "filas": 1,
        }
        datos = core._enriquecer_y_matchear(
            conn, {"obra": "CONCAVA", "cantidad": 7.0},
            {"fecha": "2026-06-30", "planta": "M8", "id_documento": "M800013170"},
            "06-30-M8-13170.pdf", lookup)
        assert datos["obra_papel"] == "CONCAVA"
        assert datos["obra"] == "CONCAVA"   # `obra` recibe lo de siempre
        assert datos["fase"] == "CAVERNAS"  # sale del Cliente del Excel, no de la obra
    finally:
        conn.close()


def test_insertar_factura_persiste_obra_papel(tmp_path, monkeypatch):
    """_est_insertar_factura() es la primitiva compartida por los dos caminos
    de escritura: si no escribe la columna, ni el import masivo ni el
    individual la pueblan nunca."""
    monkeypatch.setattr(core, "EST_DB_PATH", str(tmp_path / "est.db"))
    core.setup_est_db()
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        assert core._est_insertar_factura(conn, {
            "id_documento": "M800013170", "fecha": "2026-06-30",
            "obra": "CAVERNAS", "obra_papel": "CONCAVA", "cantidad": 7.0,
        }) == 1
        assert conn.execute(
            "SELECT obra, obra_papel FROM facturas WHERE id_documento='M800013170'"
        ).fetchone() == ("CAVERNAS", "CONCAVA")
    finally:
        conn.close()


def test_guardar_pendiente_persiste_obra_papel(tmp_path, monkeypatch):
    """El espejo de arriba para pendientes_revision."""
    monkeypatch.setattr(core, "EST_DB_PATH", str(tmp_path / "est.db"))
    monkeypatch.setattr(core, "EST_PENDIENTES", str(tmp_path))
    core.setup_est_db()
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        core._guardar_pendiente_revision(conn, {
            "archivo_pdf": "06-30-M8-13170.pdf", "id_documento": "M800013170",
            "obra": "CAVERNAS", "obra_papel": "CONCAVA",
        }, "falta sello", b"%PDF-x")
        conn.commit()
        assert conn.execute(
            "SELECT obra, obra_papel FROM pendientes_revision"
        ).fetchone() == ("CAVERNAS", "CONCAVA")
    finally:
        conn.close()


def test_endpoint_pendientes_revision_devuelve_obra_papel(tmp_path, monkeypatch):
    """POR HTTP, no llamando a la primitiva de core. La trampa del issue #31:
    la ruta arma su respuesta con un SELECT de columnas explícitas, así que
    una columna nueva NO llega sola aunque la BD la tenga y todos los tests
    de core estén en verde."""
    db_path = tmp_path / "est.db"
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    core.setup_est_db()
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO pendientes_revision (archivo_pdf, id_documento, fase, motivo, "
        "obra, obra_papel) VALUES ('a.pdf','M800013170','CAVERNAS','falta firma',"
        "'CAVERNAS','CONCAVA')")
    conn.commit()
    conn.close()

    token, auth = _token_issue67("http-pendientes")
    try:
        res = TestClient(main.app).get("/api/estimaciones/pendientes-revision",
                                       headers=auth)
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 200, res.text
    fila = res.json()["otras_fases"][0]
    assert fila["obra_papel"] == "CONCAVA"
    assert fila["obra"] == "CAVERNAS"  # las dos, no una en lugar de la otra


def test_extraer_obra_papel_pide_la_etiqueta_y_descarta_el_cliente():
    """El contrato del prompt del backfill, sin gastar una llamada real: pide
    la etiqueta OBRA: y le dice explícitamente que NO use el campo Cliente:,
    cuyo paréntesis dice siempre lo mismo en las tres obras y es el
    distractor. Medido el 2026-09-07 sobre los 10 fixtures reales: 10/10."""
    llamadas = []

    class _Msg:
        def create(self, **kw):
            llamadas.append(kw)

            class _R:
                content = [type("B", (), {"type": "text",
                                          "text": '{"obra": "  CONCAVA  "}'})()]
            return _R()

    class _Cli:
        messages = _Msg()

    original = core.client
    core.client = _Cli()
    try:
        assert core._extraer_obra_papel(b"%PDF-fake") == "CONCAVA"  # se recorta
    finally:
        core.client = original

    prompt = llamadas[-1]["messages"][0]["content"][1]["text"]
    assert "OBRA:" in prompt
    assert "Cliente:" in prompt and "NO uses" in prompt
    assert '"obra"' in prompt
    # barato a propósito: un rellenado pide UN campo, no los 16 del pipeline
    assert llamadas[-1]["max_tokens"] < 500
    for campo in ("descripcion", "tiene_sello", "chofer", "observaciones"):
        assert campo not in prompt, f"_extraer_obra_papel pide de mas: {campo}"


# ── Issue #72 — obra_familia: la forma normalizada/agrupada de obra_papel ──
#
# facturas.obra_papel guarda la línea `OBRA:` tal cual la leyó Vision (issue
# #67) y NO se toca: es la evidencia. Sobre 4.449 filas había 146 valores
# crudos / 117 normalizados que en realidad son ~20 obras. obra_familia los
# agrupa con una normalización mecánica + el mapa EQUIVALENCIAS_OBRA,
# confirmado A MANO el 2026-09-14 — el mapeo automático por similitud se
# prototipó y se DESCARTÓ (BAHUWER/BAHUUER: misma obra; GOBA LADO A/B: obras
# distintas, y ambas parejas difieren en una letra). obra_familia es SOLO
# para auditar/agrupar: no entra en clasificación, precios ni documentos.

def _token_issue72(nombre):
    token = f"test-token-issue72-{nombre}"
    core.active_tokens[token] = datetime.now()
    return token, {"Authorization": f"Bearer {token}"}


def test_normalizar_obra_papel_mecanica_tildes_puntuacion_espacios():
    assert core.normalizar_obra_papel("PÁRMOL") == "PARMOL"
    assert core.normalizar_obra_papel("RABELCA, CANCHAS") == "RABELCA CANCHAS"
    assert core.normalizar_obra_papel("  parmol  ") == "PARMOL"
    assert core.normalizar_obra_papel("goba   lado  a") == "GOBA LADO A"


def test_normalizar_obra_papel_aplica_el_mapa_confirmado():
    assert core.normalizar_obra_papel("BAHUUER") == "BAHUWER"
    assert core.normalizar_obra_papel("MALESPIN") == "MALESPIN MACAO II"
    # la mecánica corre ANTES del mapa: minúsculas y espacios también entran
    assert core.normalizar_obra_papel("  bahuuer ") == "BAHUWER"
    assert core.normalizar_obra_papel("GORA LADO B") == "GOBA LADO B"


def test_normalizar_obra_papel_respeta_las_separaciones_confirmadas():
    # Decisiones confirmadas, no olvidos del mapa: NUNCA se fusiona por
    # parecido. DIMAX != DIMECA, EXTERIORES != EXTERIORES1111, y el LADO de
    # GOBA se respeta SIEMPRE.
    assert core.normalizar_obra_papel("DIMAX") == "DIMAX"
    assert core.normalizar_obra_papel("GOBA LADO A") == "GOBA LADO A"
    assert core.normalizar_obra_papel("GOBA LADO B") == "GOBA LADO B"
    assert core.normalizar_obra_papel("EXTERIORES") == "EXTERIORES"
    assert core.normalizar_obra_papel("DIMECA") == "DIMECA"


def test_normalizar_obra_papel_desconocido_none_y_vacio():
    # Un valor desconocido devuelve su forma mecánica (familia propia).
    assert core.normalizar_obra_papel("OBRA NUEVA XY") == "OBRA NUEVA XY"
    assert core.normalizar_obra_papel(None) is None
    assert core.normalizar_obra_papel("") is None
    assert core.normalizar_obra_papel(" ¡¡ - ,, !! ") is None  # solo puntuación


def test_setup_est_db_migra_obra_familia_en_las_tres_tablas(tmp_path, monkeypatch):
    """Una BD anterior al issue #72 —las tres tablas CON obra_papel pero SIN
    obra_familia y con filas dentro— gana la columna sin perder nada, y correr
    la migración dos veces no falla. Las filas viejas quedan con obra_familia
    NULL (las rellena scripts/backfill_obra_familia.py, no la migración) y su
    obra_papel intacta."""
    db_path = tmp_path / "est_obra_familia.db"
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    conn = sqlite3.connect(str(db_path))
    conn.execute("""CREATE TABLE facturas (
        id_documento TEXT PRIMARY KEY, fecha DATE, planta TEXT, orden_compra TEXT,
        referencia TEXT, distancia TEXT, cliente TEXT, obra TEXT, obra_papel TEXT,
        bomba TEXT, id_producto TEXT, descripcion TEXT, cantidad REAL,
        precio_unitario REAL, total REAL, ficha TEXT, chofer TEXT, hora_salida TEXT,
        observaciones TEXT, archivo_pdf TEXT, empresa TEXT, fase TEXT,
        fecha_importacion DATETIME
    )""")
    conn.execute("""CREATE TABLE pendientes_revision (
        archivo_pdf TEXT PRIMARY KEY, id_documento TEXT, fecha DATE, planta TEXT,
        orden_compra TEXT, referencia TEXT, distancia TEXT, cliente TEXT, obra TEXT,
        obra_papel TEXT, bomba TEXT, id_producto TEXT, descripcion TEXT, cantidad REAL,
        precio_unitario REAL, total REAL, ficha TEXT, chofer TEXT, hora_salida TEXT,
        observaciones TEXT, empresa TEXT, fase TEXT, motivo TEXT, fecha_pendiente DATETIME
    )""")
    conn.execute("""CREATE TABLE pendiente_descartado (
        archivo_pdf TEXT PRIMARY KEY, id_documento TEXT, fecha DATE, planta TEXT,
        orden_compra TEXT, referencia TEXT, distancia TEXT, cliente TEXT, obra TEXT,
        obra_papel TEXT, bomba TEXT, id_producto TEXT, descripcion TEXT, cantidad REAL,
        precio_unitario REAL, total REAL, ficha TEXT, chofer TEXT, hora_salida TEXT,
        observaciones TEXT, empresa TEXT, fase TEXT, fecha_pendiente DATETIME,
        motivo_bloqueo TEXT, descartado_por TEXT NOT NULL,
        descartado_motivo TEXT NOT NULL, descartado_fecha TEXT NOT NULL
    )""")
    conn.execute("INSERT INTO facturas (id_documento, obra_papel, cantidad) "
                 "VALUES ('F-VIEJA','BAHUUER',8.0)")
    conn.execute("INSERT INTO pendientes_revision (archivo_pdf, obra_papel) "
                 "VALUES ('p.pdf','BAHUUER')")
    conn.execute("INSERT INTO pendiente_descartado (archivo_pdf, obra_papel, "
                 "descartado_por, descartado_motivo, descartado_fecha) "
                 "VALUES ('d.pdf','BAHUUER','A. Oller','x','2026-09-14T00:00:00')")
    conn.commit()
    conn.close()

    core.setup_est_db()
    core.setup_est_db()  # idempotente: el ALTER TABLE no se repite

    conn = sqlite3.connect(str(db_path))
    try:
        for tabla in ("facturas", "pendientes_revision", "pendiente_descartado"):
            columnas = {c[1] for c in conn.execute(f"PRAGMA table_info({tabla})")}
            assert "obra_familia" in columnas, tabla
            assert "obra_papel" in columnas, f"{tabla}: obra_papel NO se toca"
            assert conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0] == 1, tabla
            # filas viejas: obra_papel intacta, obra_familia NULL (el backfill
            # la deriva, no la migración)
            assert conn.execute(
                f"SELECT obra_papel, obra_familia FROM {tabla}").fetchone() \
                == ("BAHUUER", None), tabla
    finally:
        conn.close()


def test_aprobar_y_revertir_preservan_obra_familia(tmp_path, monkeypatch):
    """El test que agarra el olvido en _EST_COLUMNAS_COMPARTIDAS (mismo
    mecanismo que el del issue #67 para obra_papel): si obra_familia no viaja
    en la tupla, aprobar un pendiente pierde el dato EN SILENCIO."""
    _, pendientes_dir, procesadas_dir = _bd_aprobacion(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        _aprobar_y_mover(conn, pendientes_dir, procesadas_dir)
        assert conn.execute(
            "SELECT obra_papel, obra_familia FROM facturas WHERE id_documento='M800013968'"
        ).fetchone() == ("CONCAVA", "FAMILIA-72")

        core._est_revertir_aprobacion(conn, "M800013968",
                                      ahora="2026-08-31T11:00:00.000000")
        conn.commit()
        assert conn.execute(
            "SELECT obra_papel, obra_familia FROM pendientes_revision"
        ).fetchone() == ("CONCAVA", "FAMILIA-72")
    finally:
        conn.close()


def test_descartar_y_reponer_preservan_obra_familia(tmp_path, monkeypatch):
    """La otra pareja armada con _EST_COLUMNAS_COMPARTIDAS: ida y vuelta por
    pendiente_descartado sin perder el dato."""
    _, pendientes_dir, _, descartados_dir = _bd_descarte(tmp_path, monkeypatch)
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        _insertar_pendiente(conn, pendientes_dir)
        core._est_descartar_pendiente(conn, "07-21-M8-13968.pdf", "A. Oller", "no va")
        conn.commit()
        assert conn.execute(
            "SELECT obra_papel, obra_familia FROM pendiente_descartado"
        ).fetchone() == ("CONCAVA", "FAMILIA-72")

        # el endpoint mueve el PDF; acá se simula para que reponer pase sus guardas
        shutil.move(str(pendientes_dir / "07-21-M8-13968.pdf"),
                    str(descartados_dir / "07-21-M8-13968.pdf"))
        core._est_reponer_descartado(conn, "07-21-M8-13968.pdf")
        conn.commit()
        assert conn.execute(
            "SELECT obra_papel, obra_familia FROM pendientes_revision"
        ).fetchone() == ("CONCAVA", "FAMILIA-72")
    finally:
        conn.close()


def test_enriquecer_deriva_obra_familia_sin_tocar_obra_ni_obra_papel(tmp_path, monkeypatch):
    """Camino individual: obra_papel recibe la lectura cruda de Vision y
    obra_familia su forma normalizada por el mapa — sin tocar `obra` ni la
    clasificación (la fase sigue saliendo del Cliente del Excel)."""
    monkeypatch.setattr(core, "EST_DB_PATH", str(tmp_path / "est.db"))
    core.setup_est_db()
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        lookup = {
            "por_archivo": {"06-30-m8-13170.pdf": {
                "id_documento": "M800013170",
                "descripcion": "Hormigon Industrial 350 Kg/cm2",
                "cliente": "MACAO ALTO RESORT SRL (CIUDAD PALACE - CAVERNAS Y EXT)"}},
            "por_id": {}, "conflictos": {}, "filas": 1,
        }
        datos = core._enriquecer_y_matchear(
            conn, {"obra": "Bahuuer", "cantidad": 7.0},
            {"fecha": "2026-06-30", "planta": "M8", "id_documento": "M800013170"},
            "06-30-M8-13170.pdf", lookup)
        assert datos["obra_papel"] == "Bahuuer"      # crudo: la evidencia, tal cual
        assert datos["obra_familia"] == "BAHUWER"    # normalizado + mapa
        assert datos["obra"] == "Bahuuer"            # `obra` recibe lo de siempre
        assert datos["fase"] == "CAVERNAS"           # la clasificación no se mueve
    finally:
        conn.close()


def test_insertar_factura_persiste_obra_familia(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "EST_DB_PATH", str(tmp_path / "est.db"))
    core.setup_est_db()
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        assert core._est_insertar_factura(conn, {
            "id_documento": "M800013170", "fecha": "2026-06-30",
            "obra_papel": "BAHUUER", "obra_familia": "BAHUWER", "cantidad": 7.0,
        }) == 1
        assert conn.execute(
            "SELECT obra_papel, obra_familia FROM facturas WHERE id_documento='M800013170'"
        ).fetchone() == ("BAHUUER", "BAHUWER")
    finally:
        conn.close()


def test_guardar_pendiente_persiste_obra_familia(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "EST_DB_PATH", str(tmp_path / "est.db"))
    monkeypatch.setattr(core, "EST_PENDIENTES", str(tmp_path))
    core.setup_est_db()
    conn = sqlite3.connect(core.EST_DB_PATH)
    try:
        core._guardar_pendiente_revision(conn, {
            "archivo_pdf": "06-30-M8-13170.pdf", "id_documento": "M800013170",
            "obra_papel": "BAHUUER", "obra_familia": "BAHUWER",
        }, "falta sello", b"%PDF-x")
        conn.commit()
        assert conn.execute(
            "SELECT obra_papel, obra_familia FROM pendientes_revision"
        ).fetchone() == ("BAHUUER", "BAHUWER")
    finally:
        conn.close()


def test_endpoint_pendientes_revision_devuelve_obra_familia(tmp_path, monkeypatch):
    """POR HTTP, no llamando a la primitiva — regla de la casa (issue #31/#67):
    el SELECT de la ruta es de columnas explícitas, así que una columna nueva
    NO llega sola aunque la BD la tenga y los tests de core estén en verde."""
    db_path = tmp_path / "est.db"
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_path))
    core.setup_est_db()
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO pendientes_revision (archivo_pdf, id_documento, fase, motivo, "
        "obra, obra_papel, obra_familia) VALUES ('a.pdf','M800013170','CAVERNAS',"
        "'falta firma','CAVERNAS','BAHUUER','BAHUWER')")
    conn.commit()
    conn.close()

    token, auth = _token_issue72("http-pendientes")
    try:
        res = TestClient(main.app).get("/api/estimaciones/pendientes-revision",
                                       headers=auth)
    finally:
        core.active_tokens.pop(token, None)

    assert res.status_code == 200, res.text
    fila = res.json()["otras_fases"][0]
    assert fila["obra_familia"] == "BAHUWER"
    assert fila["obra_papel"] == "BAHUUER"  # las dos: cruda y agrupada


# ── el nombre del entregable (issue #83) ──
#
# Hasta el 2026-09-30 el nombre no llevaba la serie y el timestamp tenia
# resolucion de un segundo, asi que generar el principal y el ppact del mismo
# periodo escribia DOS VECES el mismo archivo y el segundo pisaba al primero.
# Estos tests fuerzan `EST_SOFFICE = None` a proposito: con LibreOffice la
# conversion a PDF mete segundos entre una generacion y la siguiente y el
# choque no se reproduce — por eso el defecto solo se veia en el runner de CI,
# disfrazado de test flaky.

def _generar_las_dos_series(tmp_path, monkeypatch):
    """Genera ppact y principal del mismo periodo, seguidos, sin LibreOffice."""
    monkeypatch.setattr(core, "EST_SOFFICE", None)
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    token = _bd_cedis_clave2(tmp_path, monkeypatch)
    payload = {
        "empresa": "VMO", "fase": "CEDIS",
        "fecha_desde": "2026-07-17", "fecha_hasta": "2026-08-16",
        "numero_estimacion": "N06", "fecha_estimacion": "2026-08-20", "semana": 1,
        "productos": [{"clave": "2", "cantidad_proyecto": 29, "acumulado_anterior_cantidad": 23}],
        "reasignaciones": {}, "serie": "ppact",
    }
    client = TestClient(main.app)
    cab = {"Authorization": f"Bearer {token}"}
    try:
        res_ppact = client.post("/api/estimaciones/generar", json=payload, headers=cab)
        res_principal = client.post("/api/estimaciones/generar",
                                    json={**payload, "serie": "principal"}, headers=cab)
    finally:
        core.active_tokens.pop(token, None)
    assert res_ppact.status_code == 200, res_ppact.text
    assert res_principal.status_code == 200, res_principal.text
    return (res_ppact.json()["download_url"].rsplit("/", 1)[-1],
            res_principal.json()["download_url"].rsplit("/", 1)[-1])


def test_las_dos_series_del_mismo_periodo_no_se_pisan(tmp_path, monkeypatch):
    """El defecto del #83, en su forma exacta: dos download_url distintos
    apuntando al mismo archivo, con el del ppact entregando el documento del
    principal."""
    n_ppact, n_principal = _generar_las_dos_series(tmp_path, monkeypatch)
    assert n_ppact != n_principal, "principal y ppact no pueden compartir archivo"
    assert len(sorted(tmp_path.glob("*.xlsx"))) == 2, "tienen que quedar los DOS en disco"

    # Y cada uno tiene que ser el suyo: M9 lleva el OC/Contrato, que para
    # ppact es el literal "PPACT" y para principal el numero de VMO/CEDIS.
    assert openpyxl.load_workbook(tmp_path / n_ppact)["CD-COAF-REO-01"]["M9"].value == "PPACT"
    # str(): Excel guarda el OC como numero, el catalogo lo tiene como texto.
    assert (str(openpyxl.load_workbook(tmp_path / n_principal)["CD-COAF-REO-01"]["M9"].value)
            == core.EST_OC_CONTRATO[("VMO", "CEDIS")])


def test_el_nombre_dice_de_que_serie_es(tmp_path, monkeypatch):
    n_ppact, n_principal = _generar_las_dos_series(tmp_path, monkeypatch)
    assert "_PPACT_" in n_ppact, n_ppact
    assert "_PRINCIPAL_" in n_principal, n_principal


def test_el_timestamp_llega_al_milisegundo(tmp_path, monkeypatch):
    """Sin esto, dos generaciones de la MISMA serie en el mismo segundo
    dependerian del sufijo para no chocar."""
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    nombre = core._est_nombre_entregable("VMO", "CEDIS", "ppact",
                                         "2026-07-17", "2026-08-16")
    marca = nombre[:-len(".xlsx")].rsplit("_", 3)[-3:]
    assert len(marca[0]) == 8 and len(marca[1]) == 6 and len(marca[2]) == 3, nombre


def test_si_el_nombre_ya_existe_se_le_agrega_sufijo(tmp_path, monkeypatch):
    """La red que convierte el choque de improbable en imposible. Se congela el
    reloj para forzar el mismo nombre dos veces: con milisegundos reales no
    habria forma de provocarlo."""
    monkeypatch.setattr(core, "EST_REPORTES_DIR", str(tmp_path))
    congelado = datetime(2026, 9, 30, 9, 48, 44, 123000)

    class RelojQuieto(datetime):
        @classmethod
        def now(cls, tz=None):
            return congelado

    monkeypatch.setattr(core, "datetime", RelojQuieto)

    primero = core._est_nombre_entregable("VMO", "CEDIS", "ppact",
                                          "2026-07-17", "2026-08-16")
    (tmp_path / primero).write_bytes(b"el primero")
    segundo = core._est_nombre_entregable("VMO", "CEDIS", "ppact",
                                          "2026-07-17", "2026-08-16")
    assert segundo != primero
    assert segundo.endswith("_2.xlsx"), segundo

    (tmp_path / segundo).write_bytes(b"el segundo")
    tercero = core._est_nombre_entregable("VMO", "CEDIS", "ppact",
                                          "2026-07-17", "2026-08-16")
    assert tercero.endswith("_3.xlsx"), tercero


# ── Issue #96 — cerrar con OTRO numero un rango ya cerrado se bloquea ──────

def test_cierres_solapados_detecta_parcial_exacto_y_excluye_el_propio(tmp_path):
    conn = _conn_cerrada(tmp_path)
    conn.execute("INSERT INTO estimacion_cerrada VALUES "
                 "('DOMICEM','MACAO 2','1','principal','N01','2026-07-17','2026-08-16',10.0,'x')")
    # un solo dia en comun ya cuenta dos veces
    assert [s["numero_estimacion"] for s in core._est_cierres_solapados(
        conn, "DOMICEM", "MACAO 2", "N02", "2026-08-16", "2026-08-31")] == ["N01"]
    # el caso del 2026-10-05: mismo rango exacto, otro numero
    assert [s["numero_estimacion"] for s in core._est_cierres_solapados(
        conn, "DOMICEM", "MACAO 2", "N40", "2026-07-17", "2026-08-16")] == ["N01"]
    # el propio numero no se solapa consigo mismo (eso es re_cierre)
    assert core._est_cierres_solapados(conn, "DOMICEM", "MACAO 2", "N01", "2026-07-17", "2026-08-16") == []
    # el dia siguiente no toca, y otra fase tampoco
    assert core._est_cierres_solapados(conn, "DOMICEM", "MACAO 2", "N02", "2026-08-17", "2026-08-31") == []
    assert core._est_cierres_solapados(conn, "DOMICEM", "CAVERNAS", "N02", "2026-07-17", "2026-08-16") == []


def test_cerrar_estimacion_bloquea_el_solape_bajo_el_lock_y_no_escribe(tmp_path):
    """El bloqueo vive DENTRO de _est_cerrar_estimacion(), no solo en la
    ruta: si alguien llama a la primitiva directo, o cierra el mismo rango
    entre el chequeo de la ruta y el INSERT, igual no entra."""
    from fastapi import HTTPException
    conn = _conn_cerrada(tmp_path)
    conn.execute("INSERT INTO estimacion_cerrada VALUES "
                 "('DOMICEM','MACAO 2','1','principal','N01','2026-07-17','2026-08-16',10.0,'x')")
    antes = conn.execute("SELECT * FROM estimacion_cerrada").fetchall()
    with pytest.raises(HTTPException) as exc:
        core._est_cerrar_estimacion(conn, "DOMICEM", "MACAO 2", [], "N40", "2026-07-17", "2026-08-16")
    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "cierre_solapado"
    assert conn.execute("SELECT * FROM estimacion_cerrada").fetchall() == antes
    # y la conexion quedo usable: el ROLLBACK corrio
    assert not conn.in_transaction


def test_endpoint_cerrar_mismo_rango_con_otro_numero_da_400_aun_confirmando(tmp_path, monkeypatch):
    """REGRESION del 2026-10-05, por HTTP: N01 cerrado, el mismo rango como
    N40 da 400 cierre_solapado aunque venga confirmar_aviso=True, y no escribe
    nada. El camino legitimo para corregir un numero —reabrir el viejo y
    cerrar con el nuevo— sigue andando."""
    token = _bd_cierre_http(tmp_path, monkeypatch)
    client = TestClient(main.app)
    auth = {"Authorization": f"Bearer {token}"}
    base = {"empresa": "VMO", "fase": "CEDIS", "fecha_desde": "2026-07-17", "fecha_hasta": "2026-08-16"}
    try:
        res = client.post("/api/estimaciones/cerrar", json={**base, "numero_estimacion": "N01"}, headers=auth)
        assert res.status_code == 200, res.text
        cerradas = _filas_cerradas()

        for confirmar in (False, True):
            res = client.post("/api/estimaciones/cerrar", headers=auth, json={
                **base, "numero_estimacion": "N40", "confirmar_aviso": confirmar})
            assert res.status_code == 400, res.text
            detail = res.json()["detail"]
            assert detail["error"] == "cierre_solapado"
            assert detail["detalle"] == [{"numero_estimacion": "N01", "fecha_desde": "2026-07-17",
                                          "fecha_hasta": "2026-08-16"}]
            assert _filas_cerradas() == cerradas

        res = client.post("/api/estimaciones/reabrir", headers=auth,
                          json={"empresa": "VMO", "fase": "CEDIS", "numero_estimacion": "N01"})
        assert res.status_code == 200, res.text
        res = client.post("/api/estimaciones/cerrar", json={**base, "numero_estimacion": "N40"}, headers=auth)
        assert res.status_code == 200, res.text
        assert [f[0] for f in _filas_cerradas()] == ["N40"]
    finally:
        core.active_tokens.pop(token, None)


def test_endpoint_cerrar_el_solape_se_dice_antes_que_los_avisos(tmp_path, monkeypatch):
    """Con un solape Y un aviso de hueco a la vez, la respuesta es el 400 del
    solape, no el 409 del hueco: si no, el operador confirma un aviso y
    recien despues se entera de que no se puede cerrar."""
    token = _bd_cierre_http(tmp_path, monkeypatch)
    client = TestClient(main.app)
    auth = {"Authorization": f"Bearer {token}"}
    try:
        conn = sqlite3.connect(core.EST_DB_PATH)
        conn.execute("INSERT INTO estimacion_cerrada VALUES "
                     "('VMO','CEDIS','1','principal','N05','2026-08-20','2026-08-31',7.0,'x')")
        conn.commit()
        conn.close()
        # 2026-08-25 deja hueco desde fecha_base (2026-07-16) y toca N05
        res = client.post("/api/estimaciones/cerrar", headers=auth, json={
            "empresa": "VMO", "fase": "CEDIS", "numero_estimacion": "N06",
            "fecha_desde": "2026-08-25", "fecha_hasta": "2026-09-10"})
        assert res.status_code == 400, res.text
        assert res.json()["detail"]["error"] == "cierre_solapado"
    finally:
        core.active_tokens.pop(token, None)
