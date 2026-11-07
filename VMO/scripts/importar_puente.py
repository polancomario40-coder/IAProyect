# by a_oller
"""
importar_puente.py — Importacion masiva de PDFs desde ZIP con Excel de referencia.

Fase 1: procesa los PDFs no-MACAO2. Regla: firma obligatoria, sello no
bloquea (lo opuesto a MACAO 2).
Fase 2: procesa MACAO 2 y valida sello (obligatorio) + firma (no bloquea).

Las dos fases usan vision_extract() y guardan los 12 campos (issue #48,
2026-09-02; el 12º, "obra", entro con el issue #67 el 2026-09-07 y va a la
columna obra_papel). Hasta esa fecha Fase 1 usaba verificar_firma(), un prompt
liviano de solo tiene_sello/tiene_firma, y las 9 columnas que unicamente
Vision puede llenar quedaban en NULL: medido, 0 de 901 facturas en las 8
fases que no son MACAO 2, contra 2.548-3.284 de 3.284 en MACAO 2.

Lo que NO cambio: los datos que estan en el Excel (cantidad, fecha, cliente,
planta, obra, descripcion) siguen viniendo de ahi y Vision no los pisa —
decision explicita del usuario, el Excel es la fuente de verdad y no se
compara contra lo que lea el modelo. Vision solo aporta los campos que el
Excel no tiene, y la decision de sello/firma.

Uso:
    python scripts/importar_puente.py [ruta_al_zip] [ruta_al_excel]

Sin argumentos usa el ZIP original "Puente 1" y el Excel historico (ya
archivados en conduces/archivos/, para reprocesar ese lote especifico). Para
un lote nuevo, pasar el ZIP y su Excel como argumentos.

Issue #78 (2026-09-09), tres cambios de fidelidad:

- El Excel se lee POR CABECERA (no por posicion) y soporta .xls (xlrd) y
  .xlsx (openpyxl). La hoja se elige por sus cabeceras — la planilla real
  `COnduces.xls` trae PRIMERO una hoja de tabla dinamica, asi que "la hoja
  activa" ya no es un criterio valido. Se indexa por Codigo (nombre del PDF)
  Y por Conduce (id), para que los escaneos renombrados por
  scripts/recuperar_nombres.py entren por el flujo normal.

- La fase se decide ANTES de pagar Vision: un documento cuyo cliente no
  normaliza a ninguna fase (p.ej. la planta M4, otro proyecto) se cuenta como
  fase_desconocida y se salta sin ninguna llamada ni fila.

- puente_progreso.txt esta MUERTO: nada lo lee ni lo escribe (el archivo se
  conserva como historico). Anotaba "visto", no "importado", y un rechazado
  no se volvia a mirar nunca — asi se perdieron 9 conduces. Ahora las DOS
  fases hacen el mismo chequeo contra la base antes de pagar Vision: en
  `facturas` es duplicado; en `pendientes_revision` o `pendiente_descartado`
  ya esta registrado y se salta; en ninguna, se procesa. El unico que se
  repaga es el que no esta en ningun lado — exactamente el que hay que
  reintentar (borrar la fila de pendientes_revision = pedir el reintento).

El resumen final RECONCILIA: total de entradas de archivo del ZIP =
ok + duplicado + ya_registrado + sin_excel + fase_desconocida + rechazado +
vision_error + no_pdf, con listado de nombres para toda categoria que no sea
ok/duplicado. Si la suma no cierra, lo dice en mayusculas y el exit code es
distinto de 0.
"""

import zipfile, sqlite3, base64, os, json, sys, time
from datetime import datetime
from pathlib import Path

import openpyxl
import anthropic
from dotenv import load_dotenv

BASE_DIR    = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# Issue #19: la logica de datos compartida (fase/empresa, precios, INSERT de
# facturas, pendientes_revision, decision de sello/firma) vive en core.py —
# este script la importa en vez de mantener su propia copia, que ya habia
# divergido (el caso real "MACAO 11" de OCR). Mismo patron de import que
# scripts/corregir_clave_resuelta_cavernas_150.py. Las 3 funciones de Vision
# (vision_extract, verificar_firma, verificar_sello_firma_opus) NO se
# unifican a proposito: sus prompts difieren de verdad de los de core y
# unificarlas cambiaria que extrae el modelo de los PDFs reales.
sys.path.insert(0, str(BASE_DIR))
import core  # noqa: E402  (necesita BASE_DIR en el path)

DB_PATH        = BASE_DIR / "estimaciones" / "db" / "estimaciones.db"
# Defaults historicos (lote "Puente 1"); un lote nuevo pasa los suyos por CLI.
EXCEL_PATH     = BASE_DIR / "conduces" / "archivos" / "CONDUCES 18-08-2026.xlsx"
ZIP_PATH       = BASE_DIR / "conduces" / "archivos" / "Puente 1.zip"
# Issue #78: puente_progreso.txt ya no existe para este script — el archivo
# viejo queda en conduces/data/ como historico, pero nada lo lee ni lo
# escribe. El "progreso" real es la base: lo que no esta en ninguna de las
# tres tablas es lo que falta procesar.
ERRORES_TXT    = BASE_DIR / "conduces" / "data" / "puente_errores_sello.txt"
PENDIENTES_DIR = BASE_DIR / "estimaciones" / "facturas" / "pendientes_revision"
PENDIENTES_DIR.mkdir(parents=True, exist_ok=True)
PROCESADAS_DIR = BASE_DIR / "estimaciones" / "facturas" / "procesadas"
PROCESADAS_DIR.mkdir(parents=True, exist_ok=True)

VISION_MODEL              = "claude-haiku-4-5-20251001"
VISION_MODEL_FALLBACK     = "claude-opus-5"
VISION_MODEL_VERIFICACION = "claude-sonnet-5"

def get_fase_empresa(cliente):
    """Deriva (fase, empresa) del texto de cliente, o (None, None) si no
    matchea ninguna fase conocida — señal para pendientes_revision. Issue
    #19: usa core._normalizar_fase() + core.FASES_DOMICEM en vez de la vieja
    tabla local CLIENTE_FASE, que ya habia divergido: core aprende errores de
    OCR reales (p.ej. "MACAO 11" por "MACAO II", visto 2026-08-26 en
    M800012439) que la tabla local mandaba a pendientes_revision."""
    fase = core._normalizar_fase(cliente)
    if fase is None:
        return None, None
    return fase, ("DOMICEM" if fase in core.FASES_DOMICEM else "VMO")

# Las columnas sin las cuales el import no puede armar una fila. La planilla
# nueva (COnduces.xls) trae ademas Referencia / Unidad / Anotaciones, que este
# script no usa; la vieja (.xlsx) trae exactamente estas siete.
CABECERAS_REQUERIDAS = ("Conduce", "Fecha", "Cliente", "Producto", "Cant.", "Planta", "Codigo")


def _hojas_del_excel(excel_path):
    """[(nombre_hoja, cabeceras, filas)] con el motor que pida la extension:
    .xls con xlrd (BIFF), el resto con openpyxl. Las celdas de fecha del .xls
    vienen como numero de serie — se convierten a datetime aca (las tipadas
    como fecha siempre, y ademas cualquier numero de la columna Fecha, porque
    un serial sin formato de fecha es el mismo dato con otra etiqueta)."""
    excel_path = Path(excel_path)
    hojas = []
    if excel_path.suffix.lower() == ".xls":
        import xlrd
        wb = xlrd.open_workbook(str(excel_path), on_demand=True)
        for nombre in wb.sheet_names():
            sh = wb.sheet_by_name(nombre)
            if sh.nrows == 0:
                continue
            cabeceras = [str(sh.cell_value(0, c)).strip() for c in range(sh.ncols)]
            i_fecha = cabeceras.index("Fecha") if "Fecha" in cabeceras else None
            filas = []
            for r in range(1, sh.nrows):
                fila = []
                for c in range(sh.ncols):
                    v = sh.cell_value(r, c)
                    if (sh.cell_type(r, c) == xlrd.XL_CELL_DATE or
                            (c == i_fecha and isinstance(v, float) and v > 0)):
                        v = xlrd.xldate.xldate_as_datetime(v, wb.datemode)
                    fila.append(v)
                filas.append(tuple(fila))
            hojas.append((nombre, cabeceras, filas))
    else:
        wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
        for ws in wb.worksheets:
            filas_iter = ws.iter_rows(values_only=True)
            primera = next(filas_iter, None)
            if primera is None:
                continue
            cabeceras = [str(h).strip() if h is not None else "" for h in primera]
            hojas.append((ws.title, cabeceras, list(filas_iter)))
        wb.close()
    return hojas


def load_excel(excel_path=None):
    """Indexa el Excel de referencia POR CABECERA (issue #78 — la planilla
    cambio de forma: el .xls nuevo tiene 10 columnas y las posiciones viejas
    apuntan a Referencia y Unidad, no a Cliente y Codigo). La hoja se elige
    por sus cabeceras, no por ser la primera/activa: COnduces.xls trae una
    hoja de tabla dinamica ANTES de la de datos.

    Devuelve (por_codigo, por_id): el mismo registro indexado por el nombre
    del PDF (columna Codigo, normalizado a minusculas + .pdf) y por el id del
    conduce (columna Conduce, mayusculas). El indice por id es lo que deja
    entrar a los escaneos recuperados de nombres sin convencion, cuyo nombre
    nuevo puede no coincidir letra a letra con el Codigo de la planilla."""
    excel_path = Path(excel_path) if excel_path else EXCEL_PATH
    print(f"Cargando Excel: {excel_path.name}")
    hojas = _hojas_del_excel(excel_path)

    elegida, mas_cercana = None, None
    for nombre, cabeceras, filas in hojas:
        faltantes = [h for h in CABECERAS_REQUERIDAS if h not in cabeceras]
        if not faltantes:
            elegida = (nombre, cabeceras, filas)
            break
        if mas_cercana is None or len(faltantes) < len(mas_cercana[1]):
            mas_cercana = (nombre, faltantes)
    if elegida is None:
        if mas_cercana:
            detalle = (f"a la hoja mas parecida ('{mas_cercana[0]}') le falta(n) "
                       f"la(s) columna(s): {', '.join(mas_cercana[1])}")
        else:
            detalle = "el archivo no tiene hojas con datos"
        raise ValueError(
            f"{excel_path.name}: ninguna hoja tiene las columnas requeridas "
            f"({', '.join(CABECERAS_REQUERIDAS)}) — {detalle}")

    nombre_hoja, cabeceras, filas = elegida
    idx = {h: cabeceras.index(h) for h in CABECERAS_REQUERIDAS}
    por_codigo, por_id = {}, {}
    for fila in filas:
        def val(col, _fila=fila):
            i = idx[col]
            return _fila[i] if i < len(_fila) else None
        conduce  = val("Conduce")
        conduce  = str(conduce).strip().upper() if conduce not in (None, "") else None
        fecha    = val("Fecha")
        cliente  = str(val("Cliente")).strip() if val("Cliente") not in (None, "") else None
        producto = str(val("Producto")).strip() if val("Producto") not in (None, "") else None
        cantidad = float(val("Cant.")) if val("Cant.") not in (None, "") else None
        planta   = str(val("Planta")).strip() if val("Planta") not in (None, "") else None
        codigo   = val("Codigo")
        if codigo in (None, ""):
            codigo = None
        else:
            codigo = str(codigo).strip().lower()
            if not codigo.endswith('.pdf'):
                codigo += '.pdf'
        if conduce is None and codigo is None:
            continue  # fila sin ninguna llave: no hay como matchearla
        fase, empresa = get_fase_empresa(cliente)
        if hasattr(fecha, 'strftime'):
            fecha_str = fecha.strftime('%Y-%m-%d')
        else:
            fecha_str = str(fecha) if fecha not in (None, "") else None
        registro = {
            'id_documento': conduce,
            'fecha':        fecha_str,
            'cliente':      cliente,
            'descripcion':  producto,
            'cantidad':     cantidad,
            'planta':       planta,
            'fase':         fase,
            'empresa':      empresa,
            'codigo':       codigo,
        }
        if codigo is not None:
            por_codigo[codigo] = registro
        if conduce is not None:
            por_id[conduce] = registro
    print(f"Excel cargado: hoja '{nombre_hoja}', {len(por_codigo)} registros "
          f"por Codigo, {len(por_id)} por Conduce")
    return por_codigo, por_id


def buscar_fila_excel(por_codigo, por_id, fn):
    """La fila del Excel para este nombre de PDF: primero por Codigo, y si no
    esta, por el id que se reconstruye del nombre con la convencion
    MM-DD-Mx-NNNNN.pdf (planta + numero con ceros a 8 digitos) — el camino de
    los recuperados. Devuelve None si no hay fila por ninguna de las dos vias."""
    registro = por_codigo.get(fn.strip().lower())
    if registro is not None:
        return registro
    info = core.parsear_nombre_pdf(fn)
    if info:
        return por_id.get(info["id_documento"])
    return None

def vision_extract(client, pdf_bytes, model=VISION_MODEL):
    """Issue #67 (2026-09-07): el prompt suma "obra" — la linea `OBRA:`
    impresa en el conduce, que va a la columna obra_papel. NO estaba en la
    lista de 11 campos y por eso el import masivo nunca la vio (el spec del
    issue asumia que vision_extract() ya la devolvia y el script la tiraba;
    lo que pasaba es que nunca se pedia). El campo `cliente` sigue sin
    pedirse a proposito: el Excel es la fuente de verdad del cliente y de la
    fase, y ese respaldo es justo la puerta por la que entro "MACAO 11"."""
    prompt = (
        "Analiza esta factura de hormigon. Responde SOLO con JSON valido, sin markdown:\n"
        "{\n"
        '  "al_reves": true o false,\n'
        '  "tiene_sello": true o false,\n'
        '  "tiene_firma": true o false,\n'
        '  "orden_compra": "string o null",\n'
        '  "referencia": "string o null",\n'
        '  "distancia": "string o null",\n'
        '  "obra": "string o null",\n'
        '  "bomba": "string o null",\n'
        '  "id_producto": "string o null",\n'
        '  "ficha": "string o null",\n'
        '  "chofer": "string o null",\n'
        '  "hora_salida": "string o null",\n'
        '  "observaciones": "string o null"\n'
        "}\n"
        "al_reves: true SOLO si el documento esta rotado 180 grados, o sea si "
        "el texto se lee de cabeza. Si se lee normal, false.\n"
        + core.EST_OBRA_PAPEL_PROMPT
    )
    datos = _vision_extract_leer(client, pdf_bytes, model, prompt)
    # Issue #73, el mismo tratamiento que core._procesar_pdf_sync(): un
    # escaneo dado vuelta no falla, entra completo y equivocado. Por aca
    # cantidad y numero salen del Excel, pero sello, firma y obra_papel
    # salen de esta lectura — y los 4 dados vuelta conocidos entraron por
    # este camino. Una sola vuelta, por lo mismo que alla.
    #
    # `_rotado` le avisa al llamador que el doble-chequeo de sello/firma
    # tiene que mirar el PDF enderezado: si no, la segunda opinion vuelve a
    # leer de cabeza lo que la primera ya corrigio.
    if datos.get("al_reves"):
        datos = _vision_extract_leer(client, core._rotar_pdf(pdf_bytes), model, prompt)
        datos["_rotado"] = True
    return datos


def _vision_extract_leer(client, pdf_bytes, model, prompt):
    """Una llamada de vision_extract() sobre un PDF ya decidido."""
    resp = client.messages.create(
        model=model,
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": base64.standard_b64encode(pdf_bytes).decode()
                    }
                },
                {"type": "text", "text": prompt}
            ]
        }]
    )
    text_block = next((b for b in resp.content if b.type == "text"), None)
    if text_block is None:
        raise ValueError("Respuesta sin bloque de texto (solo thinking/otros)")
    text = text_block.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def verificar_firma(client, pdf_bytes, model=VISION_MODEL_VERIFICACION):
    """Prompt liviano de sello/firma — generaliza lo que antes vivia
    hardcoded a Sonnet dentro de verificar_sello_firma_opus() (issue #8,
    2026-08-24), para poder llamarlo con cualquier modelo. Usado en 2
    contextos: (a) Fase 2 (MACAO 2) como doble-chequeo barato, siempre con
    Sonnet — Haiku puede dar falso positivo en sello/firma (confirmado con
    pruebas reales); (b) Fase 1 (no-MACAO2) como primer intento con Haiku
    (barato) y como doble-chequeo con Sonnet."""
    prompt = (
        "Mira este documento con mucho cuidado. Responde UNICAMENTE con JSON:\n"
        '{"tiene_sello": true o false, "tiene_firma": true o false}\n'
        "tiene_sello: true SOLO si hay un sello, timbre o stamp fisico realmente visible "
        "(no cuentan cajas de texto impresas ni recuadros con datos). "
        "tiene_firma: true SOLO si hay una firma o rubrica a mano realmente visible."
    )
    resp = client.messages.create(
        model=model,
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": [
                {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": base64.standard_b64encode(pdf_bytes).decode()}},
                {"type": "text", "text": prompt}
            ]
        }]
    )
    text_block = next((b for b in resp.content if b.type == "text"), None)
    if text_block is None:
        raise ValueError("Respuesta sin bloque de texto (solo thinking/otros)")
    text = text_block.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def verificar_sello_firma_opus(client, pdf_bytes):
    """Doble-chequeo barato de Fase 2 (MACAO 2) — alias de verificar_firma()
    con Sonnet fijo (nombre historico: nunca uso Opus realmente, ver
    decision del 2026-08-20 en CLAUDE.md — validado contra Opus, 25/25
    aciertos en auditoria real de 2,742 documentos, ~60% mas barato)."""
    return verificar_firma(client, pdf_bytes, model=VISION_MODEL_VERIFICACION)


def decidir_no_macao2(tiene_firma: bool, doble_chequeo_fallo: bool,
                      pagina_vertical: bool = False) -> str | None:
    """Decision pura para Fase 1 (no-MACAO2, issue #8): firma obligatoria,
    sello no bloquea — lo opuesto a MACAO 2. Si el doble-chequeo de firma
    fallo (error de API, no de contenido) no se confia en el resultado de
    Haiku — mismo criterio conservador que el resto del pipeline — se trata
    igual que si no tuviera firma. Issue #19: la regla en si vive en
    core._motivo_sello_firma() (su rama no-MACAO2); aca solo se traduce el
    doble-chequeo fallido a "sin firma" y se le pasa una fase marcadora
    cualquiera que no sea MACAO 2 ni None, porque este camino de Fase 1 ya
    decidio la rama antes de llamar."""
    return core._motivo_sello_firma({
        "fase": "NO-MACAO-2",  # marcador: fuerza la rama generica (firma obligatoria)
        "tiene_firma": tiene_firma and not doble_chequeo_fallo,
        "_pagina_vertical": pagina_vertical,
    })


def decidir_macao2(tiene_sello: bool, doble_chequeo_fallo: bool,
                   pagina_vertical: bool = False) -> str | None:
    """Decision pura para Fase 2 (MACAO 2): sello obligatorio, firma no
    bloquea (issue #7). Estaba escrita en linea dentro del bucle y por eso
    no tenia test; sale aca para que la guarda de escaneo vertical se pueda
    probar sin un ZIP.

    Escribe "falta sello", el mismo texto que core._motivo_sello_firma().
    Hasta el 2026-10-05 escribia "sin sello", que NO esta en
    EST_MOTIVOS_APROBABLES: los 5 pendientes de MACAO 2 que entraron asi no
    se podian aprobar desde la pantalla. Se migraron a "falta sello" ese
    mismo dia."""
    if doble_chequeo_fallo:
        return "verificación de sello/firma falló"
    if not tiene_sello:
        return "falta sello"
    if pagina_vertical:
        return core.EST_MOTIVO_PAGINA_VERTICAL
    return None


def buscar_precio(cur, empresa, fase, descripcion):
    """Matchea precio por descripcion (viene del Excel, no de Vision) — el
    codigo de producto que extrae Vision no es confiable (VMO nunca lo trae).
    Issue #19: las consultas viven en core._est_buscar_precio(), compartida
    con _enriquecer_y_matchear()."""
    return core._est_buscar_precio(cur, empresa, fase, descripcion)


def insert_factura(cur, row, vision_data, now, pdf_bytes=None, sin_firma=False):
    """Inserta la factura y, si la fila SI se inserto (no era duplicado),
    guarda el PDF en PROCESADAS_DIR — antes de este fix, un documento
    importado con exito no dejaba ningun respaldo fisico en disco (solo
    guardar_pendiente_revision() escribia PDF), a diferencia de main.py.
    Encontrado el 2026-08-24 al intentar reconstruir un ZIP ya borrado desde
    procesadas/ y encontrarlo vacio para 742 documentos recien importados.

    sin_firma (issue #7, 2026-08-24): sello obligatorio, firma ya no bloquea
    el import — se marca 1/0 en la fila para poder distinguirlos despues.

    Issue #19: el INSERT vive en core._est_insertar_factura() (la misma
    primitiva que usa _confirmar_registros() de core); aca solo se arma el
    registro con la semantica historica de este script — obra = la fase (no
    hay campo obra propio en el Excel), fecha_importacion = el `now` unico
    del lote — y se conserva el respaldo fisico del PDF en procesadas/.

    Issue #67: obra_papel = lo que Vision leyo de la linea `OBRA:` del papel
    (DIMECA / CONCAVA / LIDOMI). Es una columna NUEVA, no un cambio de
    `obra`: esa sigue valiendo la fase por este camino, y las 4.185 filas ya
    importadas no se tocan."""
    vd = vision_data or {}
    precio_u = buscar_precio(cur, row['empresa'], row['fase'], row['descripcion'])
    total_v  = round(precio_u * row['cantidad'], 2) if precio_u and row['cantidad'] else None
    archivo_pdf = row.get('archivo_pdf')
    insertadas = core._est_insertar_factura(cur, {
        'id_documento':      row['id_documento'],
        'fecha':             row['fecha'],
        'planta':            row['planta'],
        'orden_compra':      vd.get('orden_compra'),
        'referencia':        vd.get('referencia'),
        'distancia':         vd.get('distancia'),
        'cliente':           row['cliente'],
        'obra':              row['fase'],
        'obra_papel':        vd.get('obra'),
        # Issue #72: la forma normalizada/agrupada de esa misma lectura.
        'obra_familia':      core.normalizar_obra_papel(vd.get('obra')),
        'bomba':             vd.get('bomba'),
        'id_producto':       vd.get('id_producto'),
        'descripcion':       row['descripcion'],
        'cantidad':          row['cantidad'],
        'precio_unitario':   precio_u,
        'total':             total_v,
        'ficha':             vd.get('ficha'),
        'chofer':            vd.get('chofer'),
        'hora_salida':       vd.get('hora_salida'),
        'observaciones':     vd.get('observaciones'),
        'archivo_pdf':       archivo_pdf,
        'empresa':           row['empresa'],
        'fase':              row['fase'],
        'fecha_importacion': now,
        'sin_firma':         sin_firma,
    })
    if insertadas and archivo_pdf and pdf_bytes:
        with open(PROCESADAS_DIR / archivo_pdf, 'wb') as f:
            f.write(pdf_bytes)
    return insertadas


def asegurar_tabla_pendientes(cur):
    """Issue #19: el CREATE TABLE vive en core._est_crear_tabla_pendientes(),
    el mismo que usa setup_est_db()."""
    core._est_crear_tabla_pendientes(cur)


def guardar_pendiente_revision(cur, row, vision_data, motivo, pdf_bytes, now):
    """Igual que en main.py — guarda el PDF + los datos que Vision alcanzo a
    leer en la zona de pendientes por revision (falta sello/firma). Nunca se
    reprocesa con Vision de nuevo automaticamente. Issue #19: delega en
    core._guardar_pendiente_revision(); aca solo se arma el dict con la
    semantica historica del script (obra = la fase, precio/total siempre
    NULL en pendientes, fecha_pendiente = el `now` unico del lote), mas
    obra_papel (issue #67) con la linea `OBRA:` que leyo Vision."""
    vd = vision_data or {}
    core._guardar_pendiente_revision(cur, {
        'archivo_pdf':     row.get('archivo_pdf'),
        'id_documento':    row['id_documento'],
        'fecha':           row['fecha'],
        'planta':          row['planta'],
        'orden_compra':    vd.get('orden_compra'),
        'referencia':      vd.get('referencia'),
        'distancia':       vd.get('distancia'),
        'cliente':         row['cliente'],
        'obra':            row['fase'],
        'obra_papel':      vd.get('obra'),
        # Issue #72: la forma normalizada/agrupada de esa misma lectura.
        'obra_familia':    core.normalizar_obra_papel(vd.get('obra')),
        'bomba':           vd.get('bomba'),
        'id_producto':     vd.get('id_producto'),
        'descripcion':     row['descripcion'],
        'cantidad':        row['cantidad'],
        'precio_unitario': None,
        'total':           None,
        'ficha':           vd.get('ficha'),
        'chofer':          vd.get('chofer'),
        'hora_salida':     vd.get('hora_salida'),
        'observaciones':   vd.get('observaciones'),
        'empresa':         row['empresa'],
        'fase':            row['fase'],
    }, motivo, pdf_bytes, ahora=now)


def resolver_pendiente_si_existe(cur, id_documento):
    """Issue #19: la resolucion (DELETE + borrado del PDF pendiente) vive en
    core._est_resolver_pendiente(). Lo unico propio de este script es tragar
    el OSError del borrado del PDF, sin propagar — este loop no usa SAVEPOINT
    (a diferencia de main.py), asi que una excepcion aca escaparia al except
    de main() SIN marcar el archivo como procesado en progreso.txt. El DELETE
    de pendientes_revision (misma transaccion) igual queda comiteado por el
    conn.commit() de ESTA MISMA iteracion en main(), justo despues de
    insert_factura. Si se reintenta este documento mas adelante,
    insert_factura ya encuentra la fila duplicada y pendientes_revision ya no
    tiene el registro, asi que nunca se reintenta el borrado y el PDF queda
    huerfano para siempre. Mejor un archivo huerfano detectable (se loguea)
    que corromper el flujo del lote completo por un permiso de Windows.

    Issue #78: main() ya NO la llama — con el chequeo pre-Vision contra las
    tres tablas, un documento que sigue en pendientes_revision se salta como
    ya_registrado en vez de reprocesarse, asi que al insertar nunca queda un
    pendiente que resolver. Se conserva como primitiva (delgada sobre core)
    porque el camino web de core sigue resolviendo pendientes al resubir."""
    try:
        core._est_resolver_pendiente(cur, id_documento)
    except OSError as e:
        print(f"No se pudo borrar el PDF pendiente de {id_documento}: {e} (queda huerfano, revisar a mano)")


# Las 8 categorias disyuntas y exhaustivas del contador (issue #78, punto 4).
# NO son las categorias analiticas del spec (esas se solapan): cada entrada de
# archivo del ZIP cae en exactamente una, con esta precedencia por archivo:
# no_pdf -> sin_excel -> fase_desconocida -> duplicado/ya_registrado ->
# resultado del procesamiento (ok / rechazado / vision_error).
CATEGORIAS = ("ok", "duplicado", "ya_registrado", "sin_excel",
              "fase_desconocida", "rechazado", "vision_error", "no_pdf")

# Se listan los nombres de todo lo que NO sea ok/duplicado — un contador sin
# nombres es como el resumen viejo que dijo "0 importados" sin listar uno solo.
CATEGORIAS_SIN_LISTADO = ("ok", "duplicado")


def tabla_donde_esta(cur, id_documento):
    """El chequeo pre-Vision de las DOS fases (issue #78): en que tabla esta
    ya este conduce, o None si no esta en ninguna — que es el unico caso que
    paga Vision. `facturas` significa duplicado; `pendientes_revision` o
    `pendiente_descartado`, ya registrado (un rechazado NO se repaga: para
    reintentarlo se borra su fila de pendientes_revision, y ahi si no esta
    en ningun lado). Esto reemplaza a puente_progreso.txt, que anotaba
    "visto" en vez de "importado" y enterro 9 conduces rechazados."""
    if not id_documento:
        return None
    for tabla in ("facturas", "pendientes_revision", "pendiente_descartado"):
        if cur.execute(f"SELECT 1 FROM {tabla} WHERE id_documento = ? LIMIT 1",
                       (id_documento,)).fetchone():
            return tabla
    return None


def resumen_final(stats, listados, total_archivos):
    """Imprime el resumen y devuelve el exit code. La cuenta tiene que CERRAR:
    total de entradas de archivo del ZIP = suma de las 8 categorias. Si no
    cierra, lo dice en mayusculas y devuelve distinto de 0 — un resumen que
    no reconcilia es exactamente como se perdieron conduces sin que nadie se
    entere (issue #78, punto 4)."""
    print("\n" + "=" * 40)
    print("RESUMEN FINAL")
    print("=" * 40)
    print(f"Entradas de archivo del ZIP: {total_archivos}")
    print(f"  ok:               {stats['ok']} (de los cuales sin firma, solo MACAO 2: {stats['sin_firma_ok']})")
    print(f"  duplicado:        {stats['duplicado']}")
    print(f"  ya_registrado:    {stats['ya_registrado']}")
    print(f"  sin_excel:        {stats['sin_excel']}")
    print(f"  fase_desconocida: {stats['fase_desconocida']}")
    print(f"  rechazado:        {stats['rechazado']}")
    print(f"  vision_error:     {stats['vision_error']}")
    print(f"  no_pdf:           {stats['no_pdf']}")
    for categoria in CATEGORIAS:
        if categoria in CATEGORIAS_SIN_LISTADO:
            continue
        nombres = listados.get(categoria) or []
        if nombres:
            print(f"\n{categoria} ({len(nombres)}):")
            for nombre in nombres:
                print(f"  {nombre}")
    suma = sum(stats[c] for c in CATEGORIAS)
    if suma != total_archivos:
        print(f"\n*** EL RESUMEN NO CIERRA: LAS CATEGORIAS SUMAN {suma} PERO EL "
              f"ZIP TIENE {total_archivos} ENTRADAS DE ARCHIVO. HAY ARCHIVOS SIN "
              f"CONTAR O CONTADOS DOS VECES — NO CONFIAR EN ESTA CORRIDA.")
        return 1
    print(f"\nLa cuenta cierra: {suma} = {total_archivos} entradas de archivo del ZIP.")
    return 0


def main(zip_path=None, excel_path=None, client=None):
    zip_path = Path(zip_path) if zip_path else ZIP_PATH
    client   = client or anthropic.Anthropic()
    por_codigo, por_id = load_excel(excel_path)
    now = datetime.now().isoformat()

    stats = {c: 0 for c in CATEGORIAS}
    stats['sin_firma_ok'] = 0  # informativo, subconjunto de ok — no suma aparte
    listados = {c: [] for c in CATEGORIAS}

    def contar(categoria, nombre):
        stats[categoria] += 1
        listados[categoria].append(nombre)

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    asegurar_tabla_pendientes(cur)
    conn.commit()

    # Clasificacion por archivo, ANTES de cualquier llamada. El universo es
    # toda entrada de archivo del ZIP (los directorios no son archivos).
    total_archivos = 0
    no_macao2 = []
    macao2    = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            total_archivos += 1
            fn = os.path.basename(info.filename)
            if not fn.lower().endswith('.pdf'):
                contar('no_pdf', fn)
                continue
            row = buscar_fila_excel(por_codigo, por_id, fn)
            if row is None:
                contar('sin_excel', fn)
                continue
            if row['fase'] is None:
                # Fase desconocida (p.ej. clientes de la planta M4, otro
                # proyecto): se salta ANTES de pagar Vision — ni llamada ni
                # fila (issue #78, punto 2). El cliente del Excel es el unico
                # discriminador confiable: hay archivos rotulados M3 con
                # numeros de la serie M4.
                contar('fase_desconocida', fn)
                continue
            # Copia por archivo: dos entradas del ZIP pueden resolver a la
            # misma fila del Excel (2do escaneo) y compartir el dict las
            # haria pisarse el archivo_pdf entre si.
            row = dict(row)
            row['archivo_pdf'] = fn
            if row['fase'] == 'MACAO 2':
                macao2.append((info.filename, fn, row))
            else:
                no_macao2.append((info.filename, fn, row))

    # Ya no se pregunta confirmacion (issue #8) — antes se preguntaba porque
    # Fase 1 escribia a la BD sin ninguna revision real. Ahora si hay una
    # revision real (Vision valida firma antes de importar), mismo criterio
    # que el resto del sistema.
    print(f"\n{len(macao2)} son MACAO 2, {len(no_macao2)} no lo son.")

    # FASE 1 — no-MACAO 2: firma obligatoria, sello no bloquea (issue #8).
    # Los campos que estan en el Excel (cliente, planta, obra, descripcion,
    # cantidad) siguen viniendo de ahi, sin cambios: el Excel es la fuente de
    # verdad y Vision no la pisa.
    #
    # Issue #48 (2026-09-02): esta fase pasa a usar vision_extract() igual que
    # Fase 2. Antes usaba verificar_firma(), que solo pide tiene_sello y
    # tiene_firma, asi que las 9 columnas que unicamente Vision puede llenar
    # (orden_compra, referencia, distancia, bomba, id_producto, ficha, chofer,
    # hora_salida, observaciones) quedaban en NULL para las 8 fases que no son
    # MACAO 2 — medido: 0 de 901, contra 2.548-3.284 de 3.284 en MACAO 2.
    # El `{}` que se pasaba antes no perdia nada, era fiel a lo que
    # verificar_firma devuelve; el hueco estaba en cual de las dos funciones se
    # llamaba. El doble-chequeo sigue usando verificar_firma porque solo
    # necesita los booleanos y es mas barato, mismo criterio que Fase 2.
    print(f"\nFASE 1: procesando {len(no_macao2)} PDFs no-MACAO 2 con Vision (firma obligatoria)...")
    with zipfile.ZipFile(zip_path) as zf:
        for zipname, fn, row in no_macao2:
            id_doc = row.get('id_documento')
            # Chequeo contra las TRES tablas ANTES de llamar a Vision — un
            # rerun no debe volver a pagar por documentos ya importados NI
            # por rechazados que siguen registrados (issue #78, punto 3).
            tabla = tabla_donde_esta(cur, id_doc)
            if tabla == 'facturas':
                contar('duplicado', fn)
                print(f"  {fn}  -> DUPLICADO (ya en facturas, se salta Vision)")
                continue
            if tabla is not None:
                contar('ya_registrado', f"{fn} (en {tabla})")
                print(f"  {fn}  -> YA REGISTRADO (en {tabla}, se salta Vision)")
                continue

            print(f"  {fn}  [haiku]", end=' ', flush=True)
            try:
                pdf_bytes = zf.read(zipname)
                try:
                    vdata = vision_extract(client, pdf_bytes, model=VISION_MODEL)
                except Exception as e_haiku:
                    print(f"-> fallo con haiku ({e_haiku}), reintentando con opus...", flush=True)
                    print(f"  {fn}  [opus]", end=' ', flush=True)
                    vdata = vision_extract(client, pdf_bytes, model=VISION_MODEL_FALLBACK)

                tiene_firma = vdata.get('tiene_firma', False)
                pdf_derecho = core._rotar_pdf(pdf_bytes) if vdata.get('_rotado') else pdf_bytes

                doble_chequeo_fallo = False
                if tiene_firma:
                    # Doble-chequeo con Sonnet antes de aprobar — mismo
                    # patron "solo verificar cuando ya parece que pasa" que
                    # Fase 2 usa con el sello.
                    try:
                        verif = verificar_firma(client, pdf_derecho, model=VISION_MODEL_VERIFICACION)
                        tiene_firma = verif.get('tiene_firma', tiene_firma)
                    except Exception as e_verif:
                        print(f"(doble-chequeo fallo: {e_verif}) ", end='', flush=True)
                        doble_chequeo_fallo = True

                motivo = decidir_no_macao2(tiene_firma, doble_chequeo_fallo,
                                           core._pagina_vertical(pdf_bytes))
                if motivo:
                    print(f"-> RECHAZADO ({motivo})")
                    guardar_pendiente_revision(cur, row, vdata, motivo, pdf_bytes, now)
                    conn.commit()
                    contar('rechazado', f"{fn} ({motivo})")
                else:
                    inserted = insert_factura(cur, row, vdata, now, pdf_bytes=pdf_bytes, sin_firma=False)
                    if inserted:
                        contar('ok', fn)
                        print("-> OK")
                    else:
                        contar('duplicado', fn)
                        print("-> DUPLICADO")
                    conn.commit()

            except Exception as e:
                print(f"-> ERROR: {e}")
                contar('vision_error', f"{fn} ({e})")

            time.sleep(0.3)

    print(f"  Fase 1 completa — {stats['ok']} importados hasta ahora "
          f"(incluye lo que traiga Fase 2), {stats['rechazado']} rechazados, "
          f"{stats['duplicado']} duplicados hasta ahora")

    # FASE 2 — MACAO 2 con Vision. El mismo chequeo pre-Vision que Fase 1
    # (issue #78): la base es el unico registro de progreso — nada de
    # puente_progreso.txt, que anotaba "visto" y enterraba rechazados.
    print(f"\nFASE 2: {len(macao2)} MACAO 2 en el ZIP (los ya registrados se saltan contra la base)")
    print(f"Modelo Vision: {VISION_MODEL}\n")

    err_file = open(ERRORES_TXT, 'a', encoding='utf-8')

    total_m2 = len(macao2)
    with zipfile.ZipFile(zip_path) as zf:
        for i, (zipname, fn, row) in enumerate(macao2, 1):
            pct = int(i / total_m2 * 100) if total_m2 else 100
            tabla = tabla_donde_esta(cur, row.get('id_documento'))
            if tabla == 'facturas':
                contar('duplicado', fn)
                print(f"  [{i}/{total_m2}] {pct}%  {fn}  -> DUPLICADO (ya en facturas, se salta Vision)")
                continue
            if tabla is not None:
                contar('ya_registrado', f"{fn} (en {tabla})")
                print(f"  [{i}/{total_m2}] {pct}%  {fn}  -> YA REGISTRADO (en {tabla}, se salta Vision)")
                continue

            print(f"  [{i}/{total_m2}] {pct}%  {fn}  [haiku]", end=' ', flush=True)

            try:
                pdf_bytes = zf.read(zipname)
                try:
                    vdata = vision_extract(client, pdf_bytes, model=VISION_MODEL)
                except Exception as e_haiku:
                    print(f"-> fallo con haiku ({e_haiku}), reprocesando con opus...", flush=True)
                    print(f"  [{i}/{total_m2}] {pct}%  {fn}  [opus]", end=' ', flush=True)
                    vdata = vision_extract(client, pdf_bytes, model=VISION_MODEL_FALLBACK)

                tiene_sello = vdata.get('tiene_sello', False)
                tiene_firma = vdata.get('tiene_firma', False)
                pdf_derecho = core._rotar_pdf(pdf_bytes) if vdata.get('_rotado') else pdf_bytes

                doble_chequeo_fallo = False
                if tiene_sello:
                    # Doble-chequeo con Opus antes de aprobar (Haiku puede dar
                    # falso positivo — confirmado con pruebas reales). Se
                    # dispara con sello solo (issue #7, 2026-08-24: la firma
                    # ya no bloquea el import, pero sigue siendo la unica
                    # defensa contra que Haiku invente un sello que no existe).
                    try:
                        verif = verificar_sello_firma_opus(client, pdf_derecho)
                        tiene_sello = verif.get('tiene_sello', tiene_sello)
                        tiene_firma = verif.get('tiene_firma', tiene_firma)
                    except Exception as e_verif:
                        # Si falla el doble-chequeo NO se confia en Haiku (ya
                        # dio falsos positivos documentados en produccion) —
                        # mismo fix que main.py, el documento queda pendiente.
                        print(f"(doble-chequeo fallo: {e_verif}) ", end='', flush=True)
                        doble_chequeo_fallo = True

                motivo_str = decidir_macao2(tiene_sello, doble_chequeo_fallo,
                                            core._pagina_vertical(pdf_bytes))
                if motivo_str:
                    print(f"-> RECHAZADO ({motivo_str})")
                    err_file.write(f"{fn}\t{motivo_str}\n")
                    err_file.flush()
                    guardar_pendiente_revision(cur, row, vdata, motivo_str, pdf_bytes, now)
                    conn.commit()
                    contar('rechazado', f"{fn} ({motivo_str})")
                else:
                    inserted = insert_factura(cur, row, vdata, now, pdf_bytes=pdf_bytes, sin_firma=not tiene_firma)
                    if inserted:
                        contar('ok', fn)
                        if not tiene_firma:
                            stats['sin_firma_ok'] += 1
                        print("-> OK" + (" (sin firma)" if not tiene_firma else ""))
                    else:
                        contar('duplicado', fn)
                        print("-> DUPLICADO")
                    conn.commit()

            except Exception as e:
                print(f"-> ERROR: {e}")
                contar('vision_error', f"{fn} ({e})")

            # Pausa para no saturar rate limits
            time.sleep(0.3)

    err_file.close()
    conn.close()

    codigo_salida = resumen_final(stats, listados, total_archivos)
    print(f"\nRechazados tambien anotados en: {ERRORES_TXT}")
    # Los vision_error NO dejan fila en ninguna tabla a proposito: son el
    # unico grupo que la proxima corrida reintenta sola (criterio 4 del
    # issue #78). Un rechazado, en cambio, queda en pendientes_revision y no
    # se repaga hasta que alguien borre su fila.
    return codigo_salida


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:3]))
