"""
sync_erp_logistica.py — Sincronizador desacoplado ERP SQL Server -> VMO Logistica.

Extrae directamente de SQL Server los dos Stored Procedures que alimentan el
modulo de Logistica de VMO:
  1. Programacion y Despacho: EXEC dbo.rsOrdCompProgDespExt @Fecha, @idPlanta=NULL, @todo=0
     (Unidad Delphi: \\Transporte Almanzar\\Ventas\\uOrdCompList.pas -> uDespacho.pas)
  2. Tiempo de Cargue:        EXEC dbo.biTiempoCargaCamion @desde, @hasta

Aplica exactamente las mismas reglas de normalizacion de `static/logistica.logic.js`
y guarda el resultado en `logistica/db/logistica.db` (preservando observaciones,
responsables, motivos, overrides de trayecto y cumplidos manuales si el dia ya
existia). Opcionalmente genera tambien los archivos Excel (.xlsx) equivalentes.

Por diseno vive en un archivo independiente: NO modifica `core.py`,
`routes_logistica.py` ni el frontend (`static/logistica.html`), evitando
cualquier conflicto de Git cuando el desarrollador externo actualice su repo.

Uso:
    python scripts/sync_erp_logistica.py                        # Sincroniza hoy
    python scripts/sync_erp_logistica.py 2026-09-29             # Sincroniza una fecha
    python scripts/sync_erp_logistica.py 2026-09-25 2026-09-30  # Sincroniza un rango
    python scripts/sync_erp_logistica.py 2026-09-29 --excel     # Tambien genera los 2 Excel
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import unicodedata
from datetime import datetime, date, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass

# Configuracion de conexion SQL Server (lee de .env o usa el usuario blindado 'test' en cbsvmo)
ERP_SQL_SERVER   = os.getenv("ERP_SQL_SERVER", "vmo.ddns.net,1440")
ERP_SQL_DB       = os.getenv("ERP_SQL_DB", "cbsvmo")
ERP_SQL_USER     = os.getenv("ERP_SQL_USER", "test")
ERP_SQL_PASSWORD = os.getenv("ERP_SQL_PASSWORD", "P@$$w0rd")

LOG_DB_PATH = os.path.join(BASE_DIR, "logistica", "db", "logistica.db")

# Constantes identicas a static/logistica.logic.js y static/logistica.html
AJUSTE_HORA_PROGRAMADA_MIN = 60
CARGUE_POR_DEFECTO         = 15
CALIDAD_POR_DEFECTO        = 5
TOLERANCIA_POR_DEFECTO     = 15
ADELANTO_POR_DEFECTO       = 60
ESPACIAMIENTO_POR_DEFECTO  = 30

TRAYECTO_POR_DEFECTO = {
    "Movil II": 30, "SDN": 20, "SanIsidro": 60, "Movil VI": 20,
    "Movil III": 15, "Movil IX": 30, "Movil VII": 15, "Movil VIII": 15, "Movil IV": 20,
}
ZONA_PLANTA_POR_DEFECTO = {
    "Movil II": "Santo Domingo", "SDN": "Santo Domingo", "SanIsidro": "Santo Domingo", "Movil VI": "Santo Domingo",
    "Movil III": "Punta Cana", "Movil IX": "Punta Cana", "Movil VII": "Punta Cana", "Movil VIII": "Punta Cana", "Movil IV": "Punta Cana",
}


# ================= REGLAS DE NEGOCIO (espejo de static/logistica.logic.js) =================

def normalize(s) -> str:
    if s is None:
        return ""
    s = str(s).upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalizar_bomba(v) -> str:
    if v is None:
        return "Directo"
    txt = str(v).strip()
    if txt.endswith(".0"):
        txt = txt[:-2]
    n = normalize(txt)
    if n in ("", "0", "NO", "N A", "NA", "N/A", "SIN BOMBA", "NINGUNA", "NINGUNO", "DIRECTO"):
        return "Directo"
    return txt


def es_producto_que_cuenta(producto) -> bool:
    if producto is None or str(producto).strip() == "":
        return True
    p = unicodedata.normalize("NFD", str(producto))
    p = "".join(c for c in p if unicodedata.category(c) != "Mn").upper()
    return bool(re.search(r"HORMIG.?N|MORTERO", p))


def es_cliente_interno(cliente) -> bool:
    return normalize(cliente).startswith("VMO CONCRETOS")


def es_macao(cliente, obra) -> bool:
    return any("MACAO" in normalize(t) for t in (cliente, obra))


def hora_a_minutos(val) -> float | None:
    if val is None or val == "":
        return None
    if isinstance(val, datetime):
        return val.hour * 60 + val.minute + val.second / 60.0
    if isinstance(val, (int, float)):
        frac = float(val) - int(float(val))
        return round(frac * 24 * 60)
    s = str(val).strip()
    m = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp][Mm])?", s)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        ampm = m.group(4)
        if ampm:
            is_pm = ampm.lower().startswith("p")
            if h == 12:
                h = 12 if is_pm else 0
            elif is_pm:
                h += 12
        return float(h * 60 + mn)
    return None


def _texto_o_none(v) -> str | None:
    if v is None:
        return None
    t = str(v).strip()
    if t.endswith(".0") and t[:-2].isdigit():
        t = t[:-2]
    return t if t != "" else None


def _float_o_none(v) -> float | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


# ================= EXTRACCION DESDE SQL SERVER =================

def consultar_sps_sqlserver(fecha_str: str) -> tuple[list[dict], list[dict]]:
    """Ejecuta `rsOrdCompProgDespExt` y `biTiempoCargaCamion` en SQL Server.
    Intenta primero con `pyodbc` y, si no esta instalado, usa el cliente nativo
    .NET SqlClient de Windows via PowerShell (sin requerir dependencias extra).
    """
    try:
        import pyodbc
        drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
        if drivers:
            driver = sorted(drivers)[-1]
            conn_str = (
                f"DRIVER={{{driver}}};SERVER={ERP_SQL_SERVER};DATABASE={ERP_SQL_DB};"
                f"UID={ERP_SQL_USER};PWD={ERP_SQL_PASSWORD};Encrypt=no;TrustServerCertificate=yes;"
            )
            with pyodbc.connect(conn_str, timeout=15) as conn:
                cur = conn.cursor()
                cur.execute(
                    "EXEC dbo.rsOrdCompProgDespExt @Fecha=?, @idPlanta=NULL, @todo=0",
                    (fecha_str,)
                )
                cols_prog = [c[0] for c in cur.description]
                prog_raw = [dict(zip(cols_prog, row)) for row in cur.fetchall()]

                cur.execute(
                    "EXEC dbo.biTiempoCargaCamion @desde=?, @hasta=?",
                    (fecha_str, fecha_str)
                )
                cols_carg = [c[0] for c in cur.description]
                carg_raw = [dict(zip(cols_carg, row)) for row in cur.fetchall()]
                return prog_raw, carg_raw
    except ImportError:
        pass
    except Exception as e:
        print(f"[Aviso pyodbc] {e} -> usando .NET SqlClient...")

    # Fallback universal en Windows via .NET System.Data.SqlClient
    ps_runner = f"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$server = {json.dumps(ERP_SQL_SERVER)}
$db = {json.dumps(ERP_SQL_DB)}
$user = {json.dumps(ERP_SQL_USER)}
$pwd = {json.dumps(ERP_SQL_PASSWORD)}
$fecha = {json.dumps(fecha_str)}
$connStr = "Server=$server;Database=$db;User Id=$user;Password=$pwd;Connect Timeout=15;Encrypt=False;"
$conn = New-Object System.Data.SqlClient.SqlConnection($connStr)
$conn.Open()
function Run-Sp($sql) {{
    $cmd = $conn.CreateCommand()
    $cmd.CommandTimeout = 60
    $cmd.CommandText = $sql
    $da = New-Object System.Data.SqlClient.SqlDataAdapter($cmd)
    $dt = New-Object System.Data.DataTable
    [void]$da.Fill($dt)
    $rows = New-Object System.Collections.Generic.List[object]
    foreach ($r in $dt.Rows) {{
        $obj = @{{}}
        foreach ($c in $dt.Columns) {{
            $val = $r[$c.ColumnName]
            if ($val -is [System.DBNull]) {{ $obj[$c.ColumnName] = $null }}
            elseif ($val -is [DateTime]) {{ $obj[$c.ColumnName] = $val.ToString("yyyy-MM-dd HH:mm:ss") }}
            else {{ $obj[$c.ColumnName] = $val }}
        }}
        $rows.Add($obj)
    }}
    return ,$rows
}}
try {{
    $prog = @(Run-Sp "EXEC dbo.rsOrdCompProgDespExt @Fecha='$fecha', @idPlanta=NULL, @todo=0")
    $carg = @(Run-Sp "EXEC dbo.biTiempoCargaCamion @desde='$fecha', @hasta='$fecha'")
}} finally {{
    $conn.Close()
}}
$out = @{{ programacion = $prog; cargue = $carg }}
Write-Output ($out | ConvertTo-Json -Depth 5 -Compress)
"""
    res = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", "-"],
        input=ps_runner,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=True,
    )
    data = json.loads(res.stdout.strip())
    return data.get("programacion") or [], data.get("cargue") or []


# ================= TRANSFORMACION AL FORMATO VMO =================

def transformar_programacion(prog_raw: list[dict]) -> list[dict]:
    normales = []
    macao = []
    for row in prog_raw:
        cliente = _texto_o_none(row.get("Cliente"))
        if not cliente or es_cliente_interno(cliente):
            continue
        producto = _texto_o_none(row.get("Producto"))
        if producto and not es_producto_que_cuenta(producto):
            continue
        obra = _texto_o_none(row.get("idClienteObra") or row.get("Obra")) or ""
        hora_leida = hora_a_minutos(row.get("Hora"))
        hora_min = (hora_leida + AJUSTE_HORA_PROGRAMADA_MIN) if hora_leida is not None else None
        cantidad = _float_o_none(row.get("Cantidad")) or 0.0
        planta = _texto_o_none(row.get("idPlanta"))
        zona = ZONA_PLANTA_POR_DEFECTO.get(planta or "", None)
        if not zona and es_macao(cliente, obra):
            zona = "Punta Cana"

        item = {
            "cliente": cliente,
            "obra": obra,
            "horaMin": hora_min,
            "pedido": _texto_o_none(row.get("OrdComp") or row.get("Pedido")),
            "cantidad": cantidad,
            "elemento": _texto_o_none(row.get("Elemento")),
            "producto": producto,
            "prioridad": _texto_o_none(row.get("Prioridad")),
            "despachado": _float_o_none(row.get("Despachado")),
            "pendiente": _float_o_none(row.get("Pendiente")),
            "bomba": normalizar_bomba(row.get("GrupoTrabajo") if "GrupoTrabajo" in row else row.get("Bomba")),
            "vendedor": _texto_o_none(row.get("Vendedor")),
            "zonaProg": zona,
            "zonaSheet": zona,
        }
        if es_macao(cliente, obra):
            macao.append(item)
        else:
            normales.append(item)
    return normales + macao


def transformar_cargue(carg_raw: list[dict]) -> list[dict]:
    normales = []
    macao = []
    for row in carg_raw:
        ficha = _texto_o_none(row.get("Ficha"))
        if not ficha or normalize(ficha) == "CARGA VACIA":
            continue
        cliente = _texto_o_none(row.get("Cliente"))
        if not cliente or es_cliente_interno(cliente):
            continue
        direccion = str(row.get("Direccion") or "")
        obra = re.sub(r"^OBRA:\s*", "", direccion, flags=re.IGNORECASE).strip()
        hora_min = hora_a_minutos(row.get("Hora"))
        cantidad = _float_o_none(row.get("Cantidad")) or 0.0
        planta = _texto_o_none(row.get("Planta")) or ""

        item = {
            "ficha": ficha,
            "horaMin": hora_min,
            "cliente": cliente,
            "conduce": _texto_o_none(row.get("Conduce")),
            "elemento": _texto_o_none(row.get("Elemento")),
            "planta": planta,
            "obra": obra,
            "cantidad": cantidad,
        }
        if es_macao(cliente, obra):
            macao.append(item)
        else:
            normales.append(item)
    return normales + macao


# ================= GUARDADO EN SQLITE DE VMO =================

def guardar_en_vmo_db(fecha_str: str, programacion: list[dict], cargue_rows: list[dict], db_path: str = LOG_DB_PATH) -> dict:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        # Asegurar esquema completo de logistica
        try:
            import core
            core.setup_logistica_db(conn)
        except Exception:
            pass

        # Si el dia ya existia, conservar supuestos personalizados, observaciones, motivos y responsables
        cargue_min = CARGUE_POR_DEFECTO
        calidad_min = CALIDAD_POR_DEFECTO
        tolerancia_min = TOLERANCIA_POR_DEFECTO
        adelanto_min = ADELANTO_POR_DEFECTO
        espaciamiento_min = ESPACIAMIENTO_POR_DEFECTO

        trayecto_map = dict(TRAYECTO_POR_DEFECTO)
        zona_map = dict(ZONA_PLANTA_POR_DEFECTO)
        overrides = {}
        observaciones = {}
        responsables = {}
        motivos = {}
        cumplidos_manuales = []

        cab = conn.execute(
            "SELECT cargue_min, calidad_min, tolerancia_min, tolerancia_adelanto_min, espaciamiento_min "
            "FROM logistica_dia WHERE fecha = ?", (fecha_str,)
        ).fetchone()
        if cab:
            cargue_min, calidad_min, tolerancia_min = cab[0], cab[1], cab[2]
            adelanto_min = cab[3] if cab[3] is not None else ADELANTO_POR_DEFECTO
            espaciamiento_min = cab[4] if cab[4] is not None else ESPACIAMIENTO_POR_DEFECTO
            for p, tr, zn in conn.execute("SELECT planta, trayecto_min, zona FROM logistica_dia_planta WHERE fecha = ?", (fecha_str,)):
                if tr is not None:
                    trayecto_map[p] = tr
                if zn:
                    zona_map[p] = zn
            overrides = dict(conn.execute("SELECT clave, minutos FROM logistica_trayecto_override WHERE fecha = ?", (fecha_str,)).fetchall())
            observaciones = dict(conn.execute("SELECT clave, texto FROM logistica_observacion WHERE fecha = ?", (fecha_str,)).fetchall())
            responsables = dict(conn.execute("SELECT clave, valor FROM logistica_responsable WHERE fecha = ?", (fecha_str,)).fetchall())
            motivos = dict(conn.execute("SELECT clave, valor FROM logistica_motivo WHERE fecha = ?", (fecha_str,)).fetchall())
            cumplidos_manuales = [r[0] for r in conn.execute("SELECT clave FROM logistica_cumplido_manual WHERE fecha = ?", (fecha_str,)).fetchall()]

        # Registrar cualquier planta nueva que haya aparecido en el cargue del dia
        for r in cargue_rows:
            p = r.get("planta")
            if p and p not in trayecto_map:
                trayecto_map[p] = 30
                zona_map[p] = "Santo Domingo"

        plantas_list = [
            {"planta": p, "trayecto": trayecto_map.get(p), "zona": zona_map.get(p)}
            for p in sorted(trayecto_map.keys())
        ]

        conn.execute("BEGIN")
        try:
            conn.execute("DELETE FROM logistica_dia WHERE fecha = ?", (fecha_str,))
            conn.execute(
                "INSERT INTO logistica_dia (fecha, guardado_en, cargue_min, calidad_min, "
                "tolerancia_min, tolerancia_adelanto_min, espaciamiento_min) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (fecha_str, datetime.now().isoformat(timespec="seconds"),
                 cargue_min, calidad_min, tolerancia_min, adelanto_min, espaciamiento_min)
            )
            conn.executemany(
                "INSERT INTO logistica_dia_planta (fecha, planta, trayecto_min, zona) VALUES (?, ?, ?, ?)",
                [(fecha_str, p["planta"], p["trayecto"], p["zona"]) for p in plantas_list]
            )
            conn.executemany(
                "INSERT INTO logistica_programacion (fecha, orden, cliente, obra, hora_min, "
                "pedido, cantidad, elemento, producto, prioridad, zona_hoja, "
                "despachado, pendiente, bomba, vendedor, zona_prog) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(fecha_str, i, r["cliente"], r["obra"], r["horaMin"], r["pedido"],
                  r["cantidad"], r["elemento"], r["producto"], r["prioridad"],
                  r["zonaSheet"], r["despachado"], r["pendiente"],
                  r["bomba"], r["vendedor"], r["zonaProg"])
                 for i, r in enumerate(programacion)]
            )
            conn.executemany(
                "INSERT INTO logistica_cargue (fecha, orden, ficha, hora_min, cliente, conduce, "
                "elemento, planta, obra, cantidad) VALUES (?,?,?,?,?,?,?,?,?,?)",
                [(fecha_str, i, r["ficha"], r["horaMin"], r["cliente"], r["conduce"],
                  r["elemento"], r["planta"], r["obra"], r["cantidad"])
                 for i, r in enumerate(cargue_rows)]
            )
            if overrides:
                conn.executemany(
                    "INSERT INTO logistica_trayecto_override (fecha, clave, minutos) VALUES (?,?,?)",
                    [(fecha_str, k, v) for k, v in overrides.items()]
                )
            if observaciones:
                conn.executemany(
                    "INSERT INTO logistica_observacion (fecha, clave, texto) VALUES (?,?,?)",
                    [(fecha_str, k, v) for k, v in observaciones.items() if (v or "").strip()]
                )
            if responsables:
                conn.executemany(
                    "INSERT INTO logistica_responsable (fecha, clave, valor) VALUES (?,?,?)",
                    [(fecha_str, k, v) for k, v in responsables.items()]
                )
            if motivos:
                conn.executemany(
                    "INSERT INTO logistica_motivo (fecha, clave, valor) VALUES (?,?,?)",
                    [(fecha_str, k, v) for k, v in motivos.items()]
                )
            if cumplidos_manuales:
                conn.executemany(
                    "INSERT OR IGNORE INTO logistica_cumplido_manual (fecha, clave) VALUES (?,?)",
                    [(fecha_str, k) for k in cumplidos_manuales]
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        return {
            "fecha": fecha_str,
            "pedidos": len(programacion),
            "cargues": len(cargue_rows),
            "m3": round(sum(r["cantidad"] or 0 for r in cargue_rows), 2),
        }
    finally:
        conn.close()


def exportar_excels_respaldo(fecha_str: str, prog_raw: list[dict], carg_raw: list[dict]):
    """Genera los 2 archivos Excel (.xlsx) con el formato exacto de Delphi
    (`Grid2Excel` de uDespacho.pas y `biTiempoCargaCamion`) en `logistica/archivos/`.
    """
    import openpyxl
    carpeta = os.path.join(BASE_DIR, "logistica", "archivos")
    os.makedirs(carpeta, exist_ok=True)
    dt = datetime.strptime(fecha_str, "%Y-%m-%d")
    fecha_ddmmaaaa = dt.strftime("%d-%m-%Y")

    # 1. Programa DD-MM-AAAA.xlsx (estructura identica a Grid2Excel de uDespacho.dfm)
    wb_prog = openpyxl.Workbook()
    ws_prog = wb_prog.active
    ws_prog.title = f"programa {fecha_ddmmaaaa}"
    ws_prog.append([
        "Prioridad", "Cliente", "Obra", "Mangueras", "Bomba", "Brigada",
        "Supervisor", "Elemento", "Producto", "Cantidad", "Despachado",
        "Pendiente", "Hora Inicio", "Hora Final"
    ])
    for r in prog_raw:
        ws_prog.append([
            r.get("Prioridad"), r.get("Cliente"), r.get("idClienteObra"),
            r.get("Mangueras"), r.get("GrupoTrabajo"), r.get("idBrigada"),
            r.get("Empleado"), r.get("Elemento"), r.get("Producto"),
            r.get("Cantidad"), r.get("Despachado"), r.get("Pendiente"),
            r.get("Hora"), r.get("HoraFin")
        ])
    ruta_prog = os.path.join(carpeta, f"programa {fecha_ddmmaaaa}.xlsx")
    wb_prog.save(ruta_prog)

    # 2. Tiempo de Carga por ficha DD-MM-AAAA.xlsx (estructura identica a biTiempoCargaCamion)
    wb_carg = openpyxl.Workbook()
    ws_carg = wb_carg.active
    ws_carg.title = "Hoja1"
    ws_carg.append([
        "Ficha", "Hora", "Tiempo", "Cliente", "Conduce",
        "Elemento", "Planta", "Direccion", "Cantidad"
    ])
    for r in carg_raw:
        ws_carg.append([
            r.get("Ficha"), r.get("Hora"), r.get("Tiempo"),
            r.get("Cliente"), r.get("Conduce"), r.get("Elemento"),
            r.get("Planta"), r.get("Direccion"), r.get("Cantidad")
        ])
    ruta_carg = os.path.join(carpeta, f"Tiempo de Carga por ficha {fecha_ddmmaaaa}.xlsx")
    wb_carg.save(ruta_carg)
    return ruta_prog, ruta_carg


def sincronizar_fecha(fecha_str: str, generar_excel: bool = False) -> dict:
    prog_raw, carg_raw = consultar_sps_sqlserver(fecha_str)
    programacion = transformar_programacion(prog_raw)
    cargue_rows = transformar_cargue(carg_raw)

    if not programacion and not cargue_rows:
        return {"fecha": fecha_str, "omitido": True, "motivo": "Sin registros en SQL Server para esta fecha"}

    res = guardar_en_vmo_db(fecha_str, programacion, cargue_rows, LOG_DB_PATH)
    # Si tambien existe data/logistica/db/logistica.db, mantenerla sincronizada
    alt_db = os.path.join(BASE_DIR, "data", "logistica", "db", "logistica.db")
    if os.path.exists(alt_db):
        guardar_en_vmo_db(fecha_str, programacion, cargue_rows, alt_db)

    if generar_excel:
        try:
            r_prog, r_carg = exportar_excels_respaldo(fecha_str, prog_raw, carg_raw)
            res["excel_prog"] = r_prog
            res["excel_carg"] = r_carg
        except Exception as e:
            res["excel_aviso"] = str(e)
    return res


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    generar_excel = "--excel" in sys.argv

    if len(args) == 0:
        fechas = [date.today().strftime("%Y-%m-%d")]
    elif len(args) == 1:
        fechas = [args[0]]
    elif len(args) == 2:
        d1 = datetime.strptime(args[0], "%Y-%m-%d").date()
        d2 = datetime.strptime(args[1], "%Y-%m-%d").date()
        fechas = [(d1 + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((d2 - d1).days + 1)]
    else:
        print(__doc__)
        sys.exit(1)

    print(f"Conectando a ERP SQL Server ({ERP_SQL_SERVER} / DB: {ERP_SQL_DB} / Usuario: {ERP_SQL_USER})...")
    for f in fechas:
        res = sincronizar_fecha(f, generar_excel=generar_excel)
        if res.get("omitido"):
            print(f"  [{f}] Omitido: {res['motivo']}")
        else:
            print(f"  [{f}] OK -> {res['pedidos']} pedidos programados | {res['cargues']} viajes de cargue | {res['m3']} m3")
            if res.get("excel_prog"):
                print(f"         Excels generados en logistica/archivos/")


if __name__ == "__main__":
    main()
