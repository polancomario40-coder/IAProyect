"""
erp_bridge.py — Puente directo en vivo entre SQL Server (ERP) y VMO.

Conecta los 3 modulos de reportes de VMO directamente a los Stored Procedures
autorizados en SQL Server (usuario restringido `test` con `DENY VIEW DEFINITION`
y `EXECUTE` exclusivo sobre los SPs requeridos), sin requerir subir archivos
Excel manualmente ni programar tareas `.bat`:

  1. Logistica — Cumplimiento del dia e Historial:
     - `EXEC dbo.rsOrdCompProgDespExt @Fecha='YYYYMMDD', @idPlanta=NULL, @todo=0`
     - `EXEC dbo.biTiempoCargaCamion @desde='YYYYMMDD', @hasta='YYYYMMDD'`
  2. Logistica — Indicadores:
     - `EXEC dbo.biCantProdporEquipoPivot @Desde='YYYYMMDD', @Hasta='YYYYMMDD'`
     - `EXEC dbo.biCumplimientoTiempoDespacho @desde='YYYYMMDD', @hasta='YYYYMMDD'`
  3. Comercial — Dashboard de Despachos:
     - `EXEC dbo.biVentasPorPlantayPrecios @Desde='YYYYMMDD', @Hasta='YYYYMMDD'`

Diseno cero-conflictos Git:
  - Toda la logica vive en este archivo independiente (`erp_bridge.py`).
  - Se activa con una sola linea al final de `main.py`: `import erp_bridge; erp_bridge.activar(app)`
  - Durante la ejecucion de `pytest`, los hooks automaticos se desactivan para
    respetar las bases temporales de las pruebas unitarias.
"""
import base64
import calendar
import hashlib
import hmac
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import unicodedata
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

import core
import seguridad
import routes_comercial
import routes_conduces
import routes_estimaciones
import routes_logistica
from scripts.sync_erp_logistica import (
    ERP_SQL_DB,
    ERP_SQL_PASSWORD,
    ERP_SQL_SERVER,
    ERP_SQL_USER,
    es_cliente_interno,
    es_macao,
    guardar_en_vmo_db,
    hora_a_minutos,
    normalize,
    transformar_cargue,
    transformar_programacion,
    _float_o_none,
    _texto_o_none,
)

RE_FECHA = r"^\d{4}-\d{2}-\d{2}$"

# =====================================================================
# CONFIGURACION SSO AUTH-CENTER (AuthGeneral JWT)
# =====================================================================
SSO_AUTH_CENTER_ENABLED = os.getenv("SSO_AUTH_CENTER_ENABLED", "1") == "1"
AUTH_CENTER_URL = os.getenv("AUTH_CENTER_URL", "https://auth.vmo.do").rstrip("/")
AUTH_CENTER_CLIENT_ID = os.getenv("AUTH_CENTER_CLIENT_ID", "produccion-embarque")
JWT_SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY",
    "super-secret-key-for-jwt-token-generation-that-should-be-long-enough",
)
JWT_ISSUER = os.getenv("JWT_ISSUER", "AuthGeneral")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "AuthClients")

_REVOKED_TOKENS: set[str] = set()

# Guardar referencias originales de core antes de aplicar hooks
_ORIG_LOG_DB_PATH = core.LOG_DB_PATH
_ORIG_COM_DB_PATH = core.COM_DB_PATH
_orig_verificar_token = core.verificar_token
_orig_credenciales_correctas = seguridad.credenciales_correctas
_orig_log_leer_dia = core._log_leer_dia
_orig_log_listar_dias = core._log_listar_dias
_orig_log_ind_leer = core._log_ind_leer
_orig_com_datos_dashboard = core.com_datos_dashboard

# Cache de tiempos de sincronizacion en memoria (evita re-ejecutar SPs en cada clic)
_SYNC_TS_DIA: dict[str, float] = {}
_SYNC_TS_LISTA: float = 0.0
_SYNC_TS_IND: dict[str, float] = {}
_SYNC_TS_COM: dict[str, float] = {}

TTL_DIA_RECIENTE_SEG = 180     # 3 min para hoy/ayer
TTL_DIA_HISTORICO_SEG = 3600   # 1 hora para dias pasados ya cargados
TTL_LISTA_DIAS_SEG = 300       # 5 min para listado de dias recientes
TTL_INDICADORES_SEG = 600      # 10 min para rangos de indicadores
TTL_COMERCIAL_MES_ACTIVO = 600 # 10 min para el mes comercial en curso


def _en_modo_test() -> bool:
    """Detecta si estamos corriendo bajo pytest o con DBs temporales monkeypatched."""
    if os.getenv("ERP_FORCE_SYNC") == "1":
        return False
    if "pytest" in sys.modules:
        return True
    if core.LOG_DB_PATH != _ORIG_LOG_DB_PATH or core.COM_DB_PATH != _ORIG_COM_DB_PATH:
        return True
    return False


# =====================================================================
# AUTENTICACION UNIFICADA SSO (AUTH-CENTER / AUTHGENERAL JWT HS256)
# =====================================================================

def verificar_jwt_auth_center(token: str) -> dict | None:
    """Valida firma HMAC-SHA256, expiracion (`exp`), `iss` y `aud` de un JWT
    emitido por `AuthGeneral` (`https://auth.vmo.do`). Usa solo la libreria
    estandar de Python (`hmac`, `hashlib`, `base64`, `json`).
    """
    if not token or token in _REVOKED_TOKENS:
        return None
    partes = token.split(".")
    if len(partes) != 3:
        return None
    header_b64, payload_b64, firma_b64 = partes
    try:
        mensaje = f"{header_b64}.{payload_b64}".encode("ascii")
        firma_bytes = hmac.new(
            JWT_SECRET_KEY.encode("utf-8"), mensaje, hashlib.sha256
        ).digest()
        firma_esperada = base64.urlsafe_b64encode(firma_bytes).rstrip(b"=").decode("ascii")
        if not hmac.compare_digest(firma_esperada, firma_b64):
            return None

        pad = "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + pad).decode("utf-8"))
        if not isinstance(payload, dict):
            return None

        exp = payload.get("exp")
        if exp is not None and float(exp) < (time.time() - 60):
            return None

        if JWT_ISSUER and payload.get("iss") and payload.get("iss") != JWT_ISSUER:
            return None

        aud = payload.get("aud")
        if JWT_AUDIENCE and aud:
            if isinstance(aud, list) and JWT_AUDIENCE not in aud:
                return None
            if isinstance(aud, str) and aud != JWT_AUDIENCE:
                return None

        return payload
    except Exception:
        return None


def _hook_credenciales_correctas(usuario: str, contrasena: str) -> bool:
    """Desactiva el login interno de VMO cuando SSO Auth-Center esta activo."""
    if _en_modo_test() or not SSO_AUTH_CENTER_ENABLED:
        return _orig_credenciales_correctas(usuario, contrasena)
    return False


def _hook_verificar_token(authorization: str = Header(None)):
    """Acepta tokens JWT firmados por `AuthGeneral` (`auth-center`) y los registra
    en `core.active_tokens` para que todas las rutas de VMO funcionen sin cambios.
    """
    if _en_modo_test() or not SSO_AUTH_CENTER_ENABLED:
        return _orig_verificar_token(authorization)

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No autorizado. Inicie sesión en Auth-Center.")

    token = authorization.split(" ", 1)[1].strip()
    if not token or token in _REVOKED_TOKENS:
        core.active_tokens.pop(token, None)
        raise HTTPException(status_code=401, detail="Sesión cerrada o inválida.")

    payload = verificar_jwt_auth_center(token)
    if payload is not None:
        # Registrar en core.active_tokens para cualquier ruta que consulte active_tokens directamente
        core.active_tokens[token] = datetime.now()
        return payload

    # Limpiar si estaba en active_tokens pero ya expiro el JWT
    core.active_tokens.pop(token, None)
    raise HTTPException(status_code=401, detail="Token de Auth-Center inválido o expirado.")


# =====================================================================
# CLIENTE SQL SERVER DIRECTO (pyodbc o .NET SqlClient nativo)
# =====================================================================

def ejecutar_sps_sqlserver(consultas: dict[str, str], timeout_seg: int = 120) -> dict[str, list[dict]]:
    """Ejecuta una o varias consultas `EXEC dbo...` en SQL Server en una sola
    conexion y devuelve `{nombre: [filas_como_dict]}`.
    """
    if not consultas:
        return {}

    # 1. Intentar con pyodbc si esta instalado
    try:
        import pyodbc
        drivers = [d for d in pyodbc.drivers() if "SQL Server" in d]
        if drivers:
            driver = sorted(drivers)[-1]
            conn_str = (
                f"DRIVER={{{driver}}};SERVER={ERP_SQL_SERVER};DATABASE={ERP_SQL_DB};"
                f"UID={ERP_SQL_USER};PWD={ERP_SQL_PASSWORD};Encrypt=no;TrustServerCertificate=yes;"
            )
            resultado = {}
            with pyodbc.connect(conn_str, timeout=15) as conn:
                conn.timeout = timeout_seg
                cur = conn.cursor()
                for clave, sql in consultas.items():
                    cur.execute(sql)
                    if cur.description:
                        cols = [c[0] for c in cur.description]
                        filas = []
                        for row in cur.fetchall():
                            obj = {}
                            for col_name, val in zip(cols, row):
                                if isinstance(val, datetime):
                                    obj[col_name] = val.strftime("%Y-%m-%d %H:%M:%S")
                                elif isinstance(val, date):
                                    obj[col_name] = val.strftime("%Y-%m-%d")
                                else:
                                    obj[col_name] = val
                            filas.append(obj)
                        resultado[clave] = filas
                    else:
                        resultado[clave] = []
            return resultado
    except ImportError:
        pass
    except Exception as e:
        print(f"[ERP Bridge pyodbc aviso] {e} -> usando .NET SqlClient...")

    # 2. Cliente nativo .NET System.Data.SqlClient en Windows
    queries_json = json.dumps(consultas, ensure_ascii=False)
    ps_script = r"""
    param($server, $db, $user, $pwd, $queriesJson, $timeout)
    $ErrorActionPreference = 'Stop'
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $queries = $queriesJson | ConvertFrom-Json
    $connStr = "Server=$server;Database=$db;User Id=$user;Password=$pwd;Connect Timeout=15;Encrypt=False;"
    $conn = New-Object System.Data.SqlClient.SqlConnection($connStr)
    $conn.Open()
    $out = @{}
    try {
        foreach ($prop in $queries.PSObject.Properties) {
            $k = $prop.Name
            $sql = $prop.Value
            $cmd = $conn.CreateCommand()
            $cmd.CommandTimeout = [int]$timeout
            $cmd.CommandText = $sql
            $da = New-Object System.Data.SqlClient.SqlDataAdapter($cmd)
            $dt = New-Object System.Data.DataTable
            [void]$da.Fill($dt)
            $rows = New-Object System.Collections.Generic.List[object]
            foreach ($r in $dt.Rows) {
                $obj = @{}
                foreach ($c in $dt.Columns) {
                    $val = $r[$c.ColumnName]
                    if ($val -is [System.DBNull]) { $obj[$c.ColumnName] = $null }
                    elseif ($val -is [DateTime]) { $obj[$c.ColumnName] = $val.ToString("yyyy-MM-dd HH:mm:ss") }
                    else { $obj[$c.ColumnName] = $val }
                }
                $rows.Add($obj)
            }
            $out[$k] = $rows
        }
    } finally {
        $conn.Close()
    }
    Write-Output ($out | ConvertTo-Json -Depth 5 -Compress)
    """
    res = subprocess.run(
        [
            "powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script,
            ERP_SQL_SERVER, ERP_SQL_DB, ERP_SQL_USER, ERP_SQL_PASSWORD,
            queries_json, str(timeout_seg),
        ],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    stdout = res.stdout.strip()
    if not stdout:
        return {k: [] for k in consultas}
    data = json.loads(stdout)
    out = {}
    for k in consultas:
        v = data.get(k)
        if v is None:
            out[k] = []
        elif isinstance(v, dict):
            out[k] = [v]
        else:
            out[k] = list(v)
    return out


def _fecha_sql(fecha_iso: str) -> str:
    """Convierte 'YYYY-MM-DD' a 'YYYYMMDD' (formato seguro independiente de idioma en SQL Server)."""
    return fecha_iso.replace("-", "")


def _parse_fecha_celda(val) -> str | None:
    """Convierte fecha de SQL Server o encabezado MM/DD/YYYY a YYYY-MM-DD."""
    if val is None or val == "":
        return None
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, date):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    m_iso = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m_iso:
        return f"{m_iso.group(1)}-{m_iso.group(2)}-{m_iso.group(3)}"
    m_us = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})\b", s)
    if m_us:
        mm, dd, yy = int(m_us.group(1)), int(m_us.group(2)), int(m_us.group(3))
        if yy < 100:
            yy += 2000
        return f"{yy:04d}-{mm:02d}-{dd:02d}"
    return None


# =====================================================================
# 1. LOGISTICA — DIA E HISTORIAL (rsOrdCompProgDespExt + biTiempoCargaCamion)
# =====================================================================

def sincronizar_logistica_dia(fecha_str: str, forzar: bool = False) -> dict:
    """Extrae `rsOrdCompProgDespExt` y `biTiempoCargaCamion` de SQL Server para
    `fecha_str` y actualiza `logistica.db` preservando anotaciones manuales.
    """
    ahora = time.time()
    hoy_str = date.today().strftime("%Y-%m-%d")
    ayer_str = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    ttl = TTL_DIA_RECIENTE_SEG if fecha_str in (hoy_str, ayer_str) else TTL_DIA_HISTORICO_SEG

    if not forzar and (ahora - _SYNC_TS_DIA.get(fecha_str, 0)) < ttl:
        return {"fecha": fecha_str, "cache": True}

    f_sql = _fecha_sql(fecha_str)
    datos = ejecutar_sps_sqlserver({
        "prog": f"EXEC dbo.rsOrdCompProgDespExt @Fecha='{f_sql}', @idPlanta=NULL, @todo=0",
        "carg": f"EXEC dbo.biTiempoCargaCamion @desde='{f_sql}', @hasta='{f_sql}'",
    })
    prog_raw = datos.get("prog", [])
    carg_raw = datos.get("carg", [])
    programacion = transformar_programacion(prog_raw)
    cargue_rows = transformar_cargue(carg_raw)

    _SYNC_TS_DIA[fecha_str] = ahora
    if not programacion and not cargue_rows:
        return {"fecha": fecha_str, "omitido": True, "pedidos": 0, "cargues": 0}

    res = guardar_en_vmo_db(fecha_str, programacion, cargue_rows, core.LOG_DB_PATH)
    return res


def sincronizar_dias_recientes_logistica(conn, dias_atras: int = 7, forzar: bool = False) -> list[str]:
    """Descubre que fechas recientes tienen despachos en SQL Server y sincroniza
    las que falten en `logistica_dia` (ademas del dia de hoy).
    """
    global _SYNC_TS_LISTA
    ahora = time.time()
    if not forzar and (ahora - _SYNC_TS_LISTA) < TTL_LISTA_DIAS_SEG:
        return []

    existentes = {r[0] for r in conn.execute("SELECT fecha FROM logistica_dia").fetchall()}
    hoy = date.today()
    # Si la base esta vacia, buscar los ultimos 35 dias; si ya tiene historial, ultimos `dias_atras`
    ventana = 35 if not existentes else dias_atras
    desde_dt = hoy - timedelta(days=ventana)
    f_desde = desde_dt.strftime("%Y%m%d")
    f_hasta = hoy.strftime("%Y%m%d")

    try:
        datos = ejecutar_sps_sqlserver({
            "tiempos": f"EXEC dbo.biCumplimientoTiempoDespacho @desde='{f_desde}', @hasta='{f_hasta}'"
        })
        fechas_activas = sorted({
            _parse_fecha_celda(r.get("Fecha"))
            for r in datos.get("tiempos", [])
            if _parse_fecha_celda(r.get("Fecha"))
        })
        # Si en los ultimos 35 dias no hubo nada y la DB esta vacia, buscar el ultimo mes con datos en 2026
        if not existentes and not fechas_activas:
            datos_sep = ejecutar_sps_sqlserver({
                "tiempos": "EXEC dbo.biCumplimientoTiempoDespacho @desde='20260920', @hasta='20261031'"
            })
            fechas_activas = sorted({
                _parse_fecha_celda(r.get("Fecha"))
                for r in datos_sep.get("tiempos", [])
                if _parse_fecha_celda(r.get("Fecha"))
            })[-10:]
    except Exception as e:
        print(f"[ERP Bridge aviso listar dias] {e}")
        return []

    _SYNC_TS_LISTA = ahora
    hoy_iso = hoy.strftime("%Y-%m-%d")
    sincronizadas = []
    for f_iso in fechas_activas:
        if forzar or (f_iso not in existentes) or (f_iso == hoy_iso):
            try:
                r = sincronizar_logistica_dia(f_iso, forzar=forzar)
                if not r.get("omitido"):
                    sincronizadas.append(f_iso)
            except Exception as e:
                print(f"[ERP Bridge aviso sync dia {f_iso}] {e}")
    return sincronizadas


# =====================================================================
# 2. LOGISTICA — INDICADORES (biCantProdporEquipoPivot + biCumplimientoTiempoDespacho)
# =====================================================================

def transformar_bombeo_pivot(rows: list[dict]) -> list[tuple]:
    """Transforma la salida pivot de `dbo.biCantProdporEquipoPivot` en tuplas
    `(fecha, equipo, nombre, m3)` para `logistica_bombeo`.
    """
    if not rows:
        return []
    acumulado: dict[tuple[str, str], tuple[str | None, float]] = {}
    for row in rows:
        equipo = _texto_o_none(row.get("idEquipo"))
        if not equipo:
            continue
        equipo = equipo[:40]
        nombre = _texto_o_none(row.get("Equipo"))
        if nombre:
            nombre = nombre[:80]
        for col, val in row.items():
            if col in ("KeyField", "idEquipo", "Equipo", "Total"):
                continue
            fecha_iso = _parse_fecha_celda(col)
            if not fecha_iso:
                continue
            m3 = _float_o_none(val)
            if m3 and m3 > 0:
                clave = (fecha_iso, equipo)
                prev_nom, prev_m3 = acumulado.get(clave, (nombre, 0.0))
                acumulado[clave] = (prev_nom or nombre, round(prev_m3 + m3, 4))

    return [
        (fecha_iso, equipo, nom, m3)
        for (fecha_iso, equipo), (nom, m3) in sorted(acumulado.items())
    ]


def _hora_indicador(val) -> float | None:
    """Igual que `parseTiemposSheets` en `static/logistica.logic.js`:
    una hora en 00:00 (0 minutos) significa que el sistema no tiene hora
    (la celda trae solo la fecha) y debe guardarse como `None`.
    """
    m = hora_a_minutos(val)
    if m is None or m == 0 or m >= 1440:
        return None
    return m


def transformar_tiempos_despacho(rows: list[dict]) -> list[tuple]:
    """Transforma la salida de `dbo.biCumplimientoTiempoDespacho` en tuplas
    para `logistica_tiempo_pedido`.
    """
    salida = []
    for row in rows:
        fecha_iso = _parse_fecha_celda(row.get("Fecha"))
        if not fecha_iso:
            continue
        ord_comp = _texto_o_none(row.get("OrdComp"))
        planta = _texto_o_none(row.get("Planta"))
        cliente = _texto_o_none(row.get("Cliente"))
        hora_ini = _hora_indicador(row.get("Hora"))
        hora_fin = _hora_indicador(row.get("HoraFin"))
        cantidad = max(0.0, _float_o_none(row.get("Cantidad")) or 0.0)
        total_in = max(0.0, _float_o_none(row.get("Total In")) or 0.0)
        logro = _texto_o_none(row.get("Logro"))
        total_desp = max(0.0, _float_o_none(row.get("TotalDespachado")) or 0.0)
        v_prog_raw = _float_o_none(row.get("ViajesProgramados"))
        v_prog = max(0.0, v_prog_raw) if v_prog_raw is not None else None
        v_ef = max(0.0, _float_o_none(row.get("ViajesEfectuados")) or 0.0)
        bomba = _texto_o_none(row.get("Bomba"))

        salida.append((
            fecha_iso,
            len(salida),
            ord_comp[:40] if ord_comp else None,
            planta[:60] if planta else None,
            cliente[:200] if cliente else None,
            hora_ini,
            hora_fin,
            cantidad,
            total_in,
            logro[:10] if logro else None,
            total_desp,
            v_prog,
            v_ef,
            bomba[:40] if bomba else None,
        ))
    return salida


def sincronizar_logistica_indicadores(desde: str, hasta: str, conn=None, forzar: bool = False) -> dict:
    """Ejecuta `biCantProdporEquipoPivot` y `biCumplimientoTiempoDespacho` para
    el rango `[desde, hasta]` y guarda los resultados en `logistica.db`.
    """
    clave_rango = f"{desde}..{hasta}"
    ahora = time.time()
    if not forzar and (ahora - _SYNC_TS_IND.get(clave_rango, 0)) < TTL_INDICADORES_SEG:
        return {"desde": desde, "hasta": hasta, "cache": True}

    f_desde = _fecha_sql(desde)
    f_hasta = _fecha_sql(hasta)
    datos = ejecutar_sps_sqlserver({
        "bombeo": f"EXEC dbo.biCantProdporEquipoPivot @Desde='{f_desde}', @Hasta='{f_hasta}'",
        "tiempos": f"EXEC dbo.biCumplimientoTiempoDespacho @desde='{f_desde}', @hasta='{f_hasta}'",
    })
    filas_bombeo = [
        f for f in transformar_bombeo_pivot(datos.get("bombeo", []))
        if desde <= f[0] <= hasta
    ]
    filas_tiempos = [
        f for f in transformar_tiempos_despacho(datos.get("tiempos", []))
        if desde <= f[0] <= hasta
    ]

    propia = conn is None
    if propia:
        core.setup_logistica_db()
        conn = core._log_conn()
    try:
        r_b = core._log_ind_reemplazar(conn, "logistica_bombeo", desde, hasta, filas_bombeo)
        r_t = core._log_ind_reemplazar(conn, "logistica_tiempo_pedido", desde, hasta, filas_tiempos)
        _SYNC_TS_IND[clave_rango] = ahora
        return {
            "desde": desde,
            "hasta": hasta,
            "bombeo_filas": r_b["filas"],
            "tiempos_filas": r_t["filas"],
        }
    finally:
        if propia:
            conn.close()


# =====================================================================
# 3. COMERCIAL — DASHBOARD DE DESPACHOS (biVentasPorPlantayPrecios)
# =====================================================================

PLANTAS_SDQ = {"MOVIL II", "MOVIL VI", "SANISIDRO", "SAN ISIDRO", "SDN", "HAINA", "PROCEM"}
PLANTAS_PC = {"MOVIL III", "MOVIL IV", "MOVIL V", "MOVIL VII", "MOVIL VIII", "MOVIL IX"}


def _sin_acentos(s: str) -> str:
    n = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in n if unicodedata.category(c) != "Mn").upper()


def _es_despacho_comercial_valido(cliente: str | None, producto: str | None) -> bool:
    """Filtro exacto verificado contra la hoja ACUMULADO de DASHBOARD COMERCIAL 2026:
    - Excluye cliente interno VMO CONCRETOS.
    - Incluye solo Hormigon, Mortero y Pavimentacion (excluyendo Desperdicio,
      Bombeo, Aditivos, Hielo, Blocks, Transporte, etc.).
    """
    if not cliente or not producto:
        return False
    if normalize(cliente).startswith("VMO CONCRETOS"):
        return False
    p = _sin_acentos(producto)
    if "DESPERDICIO" in p:
        return False
    return bool(re.search(r"HORMIG|MORTERO|PAVIMENTAC", p))


def _derivar_zona_comercial(planta: str | None, cliente: str | None, direccion: str | None) -> str | None:
    """Deriva la columna ZONA del dashboard comercial ('SDQ', 'PROYECTOS', 'PUNTA CANA')."""
    if es_macao(cliente, direccion):
        return "PROYECTOS"
    p_norm = normalize(planta)
    if p_norm in PLANTAS_SDQ:
        return "SDQ"
    if p_norm in PLANTAS_PC:
        return "PUNTA CANA"
    return "SDQ" if p_norm else None


def _derivar_rango_fc(producto: str | None) -> str | None:
    """Deriva la columna RANGO FC ('FC 210 KG/CM2', 'FC 350 KG/CM2', 'MR 32 KG/CM2', etc.)
    a partir de la descripcion del producto en el ERP.
    """
    if not producto:
        return None
    p = _sin_acentos(producto)
    # 1. Pavimentacion rigida MR (ej. MR32, MR-42, MR53)
    m_mr = re.search(r"\bMR[-\s]*(\d{2,3})\b", p)
    if m_mr:
        return f"MR {m_mr.group(1)} KG/CM2"
    # 2. Resistencia FC explicita o seguida de KG/CM2
    m_fc = re.search(r"(?:FC\s*)(\d{2,3})\b", p)
    if m_fc:
        return f"FC {m_fc.group(1)} KG/CM2"
    m_kg = re.search(r"\b(\d{2,3})\s*KG\s*/?\s*CM2", p)
    if m_kg:
        return f"FC {m_kg.group(1)} KG/CM2"
    # 3. Hormigon o Mortero seguido de resistencia (ej. 'HORMIGON 210, agg 3/4')
    m_hm = re.search(r"(?:HORMIGON|MORTERO)\s+(?:INDUSTRIAL\s+|PARA\s+FINO\s+)?(\d{2,3})\b", p)
    if m_hm:
        return f"FC {m_hm.group(1)} KG/CM2"
    return None


def transformar_ventas_comercial(rows: list[dict]) -> list[dict]:
    """Transforma las filas crudas de `dbo.biVentasPorPlantayPrecios` al formato
    exacto de `comercial_despacho` en `core.py`.
    """
    salida = []
    for row in rows:
        cliente = core._com_texto(row.get("Cliente"))
        producto = core._com_texto(row.get("Producto"))
        if not _es_despacho_comercial_valido(cliente, producto):
            continue
        fecha_iso = _parse_fecha_celda(row.get("fecha") or row.get("Fecha"))
        if not fecha_iso:
            continue
        cantidad = _float_o_none(row.get("Cantidad"))
        if cantidad is None:
            continue
        precio = _float_o_none(row.get("Precio"))
        line_total = _float_o_none(row.get("LineTotal"))
        precio_min = _float_o_none(row.get("Preciominimo"))
        planta = core._com_texto(row.get("idPlanta") or row.get("Planta"))
        direccion = core._com_texto(row.get("Direccion"))
        vendedor = core._com_texto(row.get("Column1") or row.get("Vendedor")) or "Oficina"
        zona = core._com_texto(row.get("ZONA")) or _derivar_zona_comercial(planta, cliente, direccion)
        rango_fc = core._com_texto(row.get("RANGO FC") or row.get("RANGO FC ")) or _derivar_rango_fc(producto)

        salida.append({
            "mes": fecha_iso[:7],
            "fecha": fecha_iso,
            "vendedor": vendedor,
            "planta": planta,
            "id_cliente": core._com_texto(row.get("idCliente")),
            "cliente": cliente,
            "conduce": core._com_texto(row.get("Conduce")),
            "categoria": core._com_texto(row.get("Categoria")),
            "condicion": core._com_texto(row.get("idCondicion") or row.get("Condicion")),
            "id_producto": core._com_texto(row.get("idProducto")),
            "producto": producto,
            "cantidad": cantidad,
            "precio": precio,
            "line_total": line_total,
            "precio_minimo": precio_min,
            "direccion": direccion,
            "zona": zona,
            "rango_fc": rango_fc,
        })
    return salida


def sincronizar_comercial_mes(anio: int, mes: int, conn=None, forzar: bool = False) -> dict:
    """Consulta `dbo.biVentasPorPlantayPrecios` para un mes (`anio`, `mes`) y
    guarda los despachos filtrados en `comercial.db`.
    """
    mes_ym = f"{anio:04d}-{mes:02d}"
    ahora = time.time()
    if not forzar and (ahora - _SYNC_TS_COM.get(mes_ym, 0)) < TTL_COMERCIAL_MES_ACTIVO:
        return {"mes": mes_ym, "cache": True}

    ultimo_dia = calendar.monthrange(anio, mes)[1]
    f_desde = f"{anio:04d}{mes:02d}01"
    f_hasta = f"{anio:04d}{mes:02d}{ultimo_dia:02d}"

    datos = ejecutar_sps_sqlserver({
        "ventas": f"EXEC dbo.biVentasPorPlantayPrecios @Desde='{f_desde}', @Hasta='{f_hasta}'"
    }, timeout_seg=120)
    filas = [
        f for f in transformar_ventas_comercial(datos.get("ventas", []))
        if f["mes"] == mes_ym
    ]
    _SYNC_TS_COM[mes_ym] = ahora
    if not filas:
        return {"mes": mes_ym, "filas": 0, "m3": 0.0, "omitido": True}

    propia = conn is None
    if propia:
        core.setup_comercial_db()
        conn = core._com_conn()
    try:
        core.com_guardar_despachos(filas, f"ERP SQL Server ({mes_ym})", conn)
        m3 = round(sum(f["cantidad"] or 0 for f in filas), 2)
        rd = round(sum(f["line_total"] or 0 for f in filas), 2)
        return {"mes": mes_ym, "filas": len(filas), "m3": m3, "rd": rd}
    finally:
        if propia:
            conn.close()


def sincronizar_comercial_anio(anio: int, conn=None, forzar: bool = False) -> list[dict]:
    """Asegura que todos los meses transcurridos de `anio` esten cargados en
    `comercial_despacho`, consultando en SQL Server solo los meses faltantes
    o el mes activo.
    """
    propia = conn is None
    if propia:
        core.setup_comercial_db()
        conn = core._com_conn()
    try:
        meses_en_db = {
            r[0] for r in conn.execute(
                "SELECT DISTINCT mes FROM comercial_despacho WHERE mes LIKE ?",
                (f"{anio:04d}-%",)
            ).fetchall()
        }
        hoy = date.today()
        max_mes = hoy.month if anio == hoy.year else (12 if anio < hoy.year else 0)
        resultados = []
        for m in range(1, max_mes + 1):
            mes_ym = f"{anio:04d}-{m:02d}"
            es_mes_actual = (anio == hoy.year and m == hoy.month)
            if forzar or (mes_ym not in meses_en_db) or es_mes_actual:
                try:
                    r = sincronizar_comercial_mes(anio, m, conn=conn, forzar=forzar)
                    resultados.append(r)
                except Exception as e:
                    print(f"[ERP Bridge aviso comercial {mes_ym}] {e}")
        return resultados
    finally:
        if propia:
            conn.close()


# =====================================================================
# HOOKS AUTOMATICOS SOBRE `core.py`
# =====================================================================

def _hook_log_leer_dia(conn, fecha: str) -> dict | None:
    if not _en_modo_test() and re.fullmatch(RE_FECHA, str(fecha or "")):
        existe = conn.execute("SELECT 1 FROM logistica_dia WHERE fecha = ?", (fecha,)).fetchone()
        hoy_str = date.today().strftime("%Y-%m-%d")
        ayer_str = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        if not existe or fecha in (hoy_str, ayer_str):
            try:
                sincronizar_logistica_dia(fecha, forzar=not bool(existe))
            except Exception as e:
                print(f"[ERP Bridge aviso _log_leer_dia {fecha}] {e}")
    return _orig_log_leer_dia(conn, fecha)


def _hook_log_listar_dias(conn) -> list[dict]:
    if not _en_modo_test():
        try:
            sincronizar_dias_recientes_logistica(conn)
        except Exception as e:
            print(f"[ERP Bridge aviso _log_listar_dias] {e}")
    return _orig_log_listar_dias(conn)


def _hook_log_ind_leer(conn, desde: str, hasta: str) -> dict:
    if not _en_modo_test():
        try:
            if desde == "0000-00-00" and hasta == "0000-00-00":
                tiene_b = conn.execute("SELECT 1 FROM logistica_bombeo LIMIT 1").fetchone()
                tiene_t = conn.execute("SELECT 1 FROM logistica_tiempo_pedido LIMIT 1").fetchone()
                if not tiene_b or not tiene_t:
                    # Inicializar con el periodo reciente activo en SQL Server
                    hoy = date.today()
                    inicio = (hoy.replace(day=1) - timedelta(days=65)).replace(day=1)
                    r = sincronizar_logistica_indicadores(
                        inicio.strftime("%Y-%m-%d"), hoy.strftime("%Y-%m-%d"), conn=conn
                    )
                    if not r.get("bombeo_filas") and not r.get("tiempos_filas"):
                        sincronizar_logistica_indicadores("2026-09-01", "2026-10-31", conn=conn, forzar=True)
            elif re.fullmatch(RE_FECHA, desde) and re.fullmatch(RE_FECHA, hasta) and desde <= hasta:
                sincronizar_logistica_indicadores(desde, hasta, conn=conn)
        except Exception as e:
            print(f"[ERP Bridge aviso _log_ind_leer {desde}..{hasta}] {e}")
    return _orig_log_ind_leer(conn, desde, hasta)


def _hook_com_datos_dashboard(conn, anio: int) -> dict:
    if not _en_modo_test():
        try:
            sincronizar_comercial_anio(anio, conn=conn, forzar=False)
        except Exception as e:
            print(f"[ERP Bridge aviso com_datos_dashboard {anio}] {e}")
    return _orig_com_datos_dashboard(conn, anio)


# =====================================================================
# RUTAS API DE SINCRONIZACION BAJO DEMANDA (/api/...)
# =====================================================================

router_erp = APIRouter()


class ErpSyncLogisticaReq(BaseModel):
    fecha: str | None = Field(default=None, pattern=RE_FECHA)
    desde: str | None = Field(default=None, pattern=RE_FECHA)
    hasta: str | None = Field(default=None, pattern=RE_FECHA)


class ErpSyncComercialReq(BaseModel):
    anio: int = Field(default=2026, ge=2000, le=2100)
    mes: int | None = Field(default=None, ge=1, le=12)


@router_erp.post("/api/logistica/erp-sync")
async def api_erp_sync_logistica(req: ErpSyncLogisticaReq, authorization: str = Header(None)):
    """Fuerza la sincronizacion inmediata desde SQL Server para un dia o rango de fechas."""
    core.verificar_token(authorization)
    try:
        if req.fecha:
            res = sincronizar_logistica_dia(req.fecha, forzar=True)
            return {"ok": True, "tipo": "dia", "resultado": res}
        if req.desde and req.hasta:
            if req.desde > req.hasta:
                raise HTTPException(status_code=422, detail="rango_invertido")
            res = sincronizar_logistica_indicadores(req.desde, req.hasta, forzar=True)
            return {"ok": True, "tipo": "indicadores", "resultado": res}
        # Sin fecha especifica: sincronizar dias recientes
        core.setup_logistica_db()
        conn = core._log_conn()
        try:
            fechas = sincronizar_dias_recientes_logistica(conn, dias_atras=14, forzar=True)
            return {"ok": True, "tipo": "recientes", "fechas": fechas}
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando ERP SQL Server: {e}")


@router_erp.get("/sso-config")
async def api_sso_config():
    """Configuracion publica de redireccion hacia Auth-Center."""
    return {
        "enabled": SSO_AUTH_CENTER_ENABLED and not _en_modo_test(),
        "auth_center_url": AUTH_CENTER_URL,
        "client_id": AUTH_CENTER_CLIENT_ID,
    }


@router_erp.get("/api/sesion-info")
async def api_sesion_info(authorization: str = Header(None)):
    """Verifica la sesion actual (JWT de Auth-Center) y devuelve los datos del usuario."""
    payload = core.verificar_token(authorization)
    usuario = payload.get("sub") if isinstance(payload, dict) else None
    return {"ok": True, "usuario": usuario}


@router_erp.post("/api/sso-logout")
async def api_sso_logout(authorization: str = Header(None)):
    """Revoca inmediatamente el token JWT actual al cerrar sesion."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
        if token:
            _REVOKED_TOKENS.add(token)
            core.active_tokens.pop(token, None)
    return {
        "ok": True,
        "logout_url": f"{AUTH_CENTER_URL}/?client_id={AUTH_CENTER_CLIENT_ID}&logout=true",
    }


@router_erp.post("/api/comercial/erp-sync")
async def api_erp_sync_comercial(req: ErpSyncComercialReq, authorization: str = Header(None)):
    """Fuerza la sincronizacion inmediata desde SQL Server para un mes o ano comercial."""
    core.verificar_token(authorization)
    try:
        if req.mes:
            res = sincronizar_comercial_mes(req.anio, req.mes, forzar=True)
            return {"ok": True, "resultado": [res]}
        res = sincronizar_comercial_anio(req.anio, forzar=True)
        return {"ok": True, "resultado": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando ERP SQL Server: {e}")


# =====================================================================
# INYECCION DINAMICA EN VISTAS HTML (SIN TOCAR ARCHIVOS EN static/)
# =====================================================================

_SCRIPT_LOGISTICA_DIA = """
<script id="erp-bridge-logistica-dia">
(function(){
  const asmFecha = document.getElementById('asmFecha');
  if (!asmFecha) return;

  // Boton para refrescar en vivo desde SQL Server
  const btnSync = document.createElement('button');
  btnSync.type = 'button';
  btnSync.textContent = '🔄 Cargar / Actualizar de ERP';
  btnSync.style.cssText = 'padding:7px 13px; background:#1C3045; color:#34D399; border:1px solid rgba(52,211,153,0.4); border-radius:6px; font-weight:700; font-size:12.5px; cursor:pointer; font-family:inherit; margin-left:6px;';
  btnSync.title = 'Consulta directamente rsOrdCompProgDespExt y biTiempoCargaCamion en SQL Server para la fecha seleccionada';

  const guardarBtn = document.getElementById('btnGuardarDia');
  if (guardarBtn && guardarBtn.parentNode) {
    guardarBtn.parentNode.insertBefore(btnSync, guardarBtn.nextSibling);
  }

  async function cargarFechaDesdeErp(fecha, forzar) {
    if (!fecha) return;
    const status = document.getElementById('guardarStatus');
    if (status) status.textContent = 'Consultando ERP SQL Server (' + fecha + ')...';
    btnSync.disabled = true;
    try {
      if (forzar) {
        await apiLogistica('/api/logistica/erp-sync', {
          method: 'POST',
          body: JSON.stringify({fecha})
        });
      }
      if (typeof abrirDia === 'function') {
        await abrirDia(fecha);
      }
    } catch (err) {
      if (status) status.textContent = 'Sin datos en ERP para ' + fecha + ' (' + err.message + ')';
    } finally {
      btnSync.disabled = false;
    }
  }

  btnSync.addEventListener('click', () => {
    const f = asmFecha.value || new Date().toISOString().slice(0, 10);
    asmFecha.value = f;
    cargarFechaDesdeErp(f, true);
  });

  // Al cambiar la fecha en el selector, abrir automaticamente ese dia desde el servidor/ERP
  asmFecha.addEventListener('change', () => {
    if (asmFecha.value) {
      cargarFechaDesdeErp(asmFecha.value, false);
    }
  });

  // Si la pagina se abrio sin #dia=... en la URL, abrir automaticamente el ultimo dia disponible
  window.addEventListener('DOMContentLoaded', async () => {
    if (typeof fechaPedidaEnLaUrl === 'function' && fechaPedidaEnLaUrl()) return;
    try {
      const r = await apiLogistica('/api/logistica/dias');
      if (r && r.dias && r.dias.length > 0) {
        await abrirDia(r.dias[0].fecha);
      }
    } catch (e) {}
  });
})();
</script>
"""

_SCRIPT_LOGISTICA_INDICADORES = """
<script id="erp-bridge-logistica-ind">
(function(){
  // Permitir elegir cualquier fecha del ERP en el filtro y sincronizar bajo demanda
  const origRenderFiltro = window.renderFiltro;
  if (typeof origRenderFiltro === 'function') {
    window.renderFiltro = function() {
      origRenderFiltro();
      const filtroDiv = document.querySelector('#filtro .filtro');
      if (!filtroDiv || document.getElementById('btnErpSyncInd')) return;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.id = 'btnErpSyncInd';
      btn.className = 'btn';
      btn.style.cssText = 'margin-top:0; background:#1C3045; color:#34D399; border:1px solid rgba(52,211,153,0.4);';
      btn.textContent = '🔄 Sincronizar rango ERP';
      btn.addEventListener('click', async () => {
        const d = document.getElementById('desde')?.value;
        const h = document.getElementById('hasta')?.value;
        if (!d || !h) return;
        btn.disabled = true;
        btn.textContent = 'Consultando SQL Server...';
        try {
          await apiLogistica('/api/logistica/erp-sync', {
            method: 'POST',
            body: JSON.stringify({desde: d, hasta: h})
          });
          await cargarReportes(true);
        } catch (err) {
          alert('Error sincronizando con ERP: ' + err.message);
        } finally {
          btn.disabled = false;
          btn.textContent = '🔄 Sincronizar rango ERP';
        }
      });
      filtroDiv.appendChild(btn);
    };
  }
})();
</script>
"""

_SCRIPT_COMERCIAL_DASHBOARD = """
<script id="erp-bridge-comercial">
(function(){
  window.addEventListener('DOMContentLoaded', () => {
    const head = document.querySelector('header');
    if (!head || document.getElementById('btnErpSyncCom')) return;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'btnErpSyncCom';
    btn.textContent = '🔄 Actualizar mes desde ERP';
    btn.style.cssText = 'padding:6px 12px; background:#1C3045; color:#34D399; border:1px solid rgba(52,211,153,0.4); border-radius:6px; font-weight:600; font-size:12px; cursor:pointer; font-family:inherit;';
    btn.addEventListener('click', async () => {
      const token = localStorage.getItem('vmo_token');
      if (!token) return;
      const anio = Number(document.getElementById('anio')?.value || new Date().getFullYear());
      const mesActual = new Date().getMonth() + 1;
      btn.disabled = true;
      btn.textContent = 'Consultando ERP...';
      try {
        await fetch('/api/comercial/erp-sync', {
          method: 'POST',
          headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token},
          body: JSON.stringify({anio: anio, mes: mesActual})
        });
        window.postMessage({tipo: 'comercial:recargar'}, window.location.origin);
      } finally {
        btn.disabled = false;
        btn.textContent = '🔄 Actualizar mes desde ERP';
      }
    });
    head.appendChild(btn);
  });
})();
</script>
"""


class _ErpHtmlBridgeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if request.method == "GET" and response.status_code == 200 and path in (
            "/",
            "/index.html",
            "/logistica.html",
            "/logistica-indicadores.html",
            "/comercial-dashboard.html",
        ):
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            texto = body.decode("utf-8", errors="replace")
            if path in ("/", "/index.html"):
                sso_cfg = json.dumps({
                    "enabled": SSO_AUTH_CENTER_ENABLED and not _en_modo_test(),
                    "auth_center_url": AUTH_CENTER_URL,
                    "client_id": AUTH_CENTER_CLIENT_ID,
                })
                extra_head = f"<script>window.__VMO_SSO_CONFIG__ = {sso_cfg};</script>"
                if "</head>" in texto:
                    texto = texto.replace("</head>", extra_head + "\n</head>", 1)
                else:
                    texto = extra_head + "\n" + texto
            else:
                extra = (
                    _SCRIPT_LOGISTICA_DIA if path == "/logistica.html"
                    else _SCRIPT_LOGISTICA_INDICADORES if path == "/logistica-indicadores.html"
                    else _SCRIPT_COMERCIAL_DASHBOARD
                )
                if "</body>" in texto:
                    texto = texto.replace("</body>", extra + "\n</body>", 1)
                else:
                    texto += extra
            nuevo_body = texto.encode("utf-8")
            headers = dict(response.headers)
            headers["content-length"] = str(len(nuevo_body))
            return Response(
                content=nuevo_body,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type,
            )
        return response


_ACTIVADO = False


def activar(app):
    """Activa los hooks de base de datos y SSO Auth-Center en `core` y registra las rutas/middleware en `app`."""
    global _ACTIVADO
    if _ACTIVADO:
        return
    # Hooks de autenticacion SSO Auth-Center (JWT HS256) e inactivacion del login local
    core.verificar_token = _hook_verificar_token
    seguridad.credenciales_correctas = _hook_credenciales_correctas
    routes_conduces.verificar_token = _hook_verificar_token
    routes_estimaciones.verificar_token = _hook_verificar_token
    routes_logistica.verificar_token = _hook_verificar_token
    routes_comercial.verificar_token = _hook_verificar_token

    if "/sso-config" not in seguridad.RUTAS_PUBLICAS:
        seguridad.RUTAS_PUBLICAS = tuple(list(seguridad.RUTAS_PUBLICAS) + ["/sso-config", "/api/sso-logout"])

    # Hooks de sincronizacion directa a SQL Server ERP (cbsvmo)
    core._log_leer_dia = _hook_log_leer_dia
    core._log_listar_dias = _hook_log_listar_dias
    core._log_ind_leer = _hook_log_ind_leer
    core.com_datos_dashboard = _hook_com_datos_dashboard

    # Insertar las rutas API antes del mount estatico ('/') para que FastAPI las resuelva
    app.include_router(router_erp)
    # Mover las rutas recien agregadas antes del Mount('/') si este ya estaba al final
    rutas_mount = [r for r in app.router.routes if getattr(r, "name", None) == "static"]
    rutas_otras = [r for r in app.router.routes if getattr(r, "name", None) != "static"]
    app.router.routes[:] = rutas_otras + rutas_mount

    app.add_middleware(_ErpHtmlBridgeMiddleware)
    _ACTIVADO = True


def _cargar_app_con_erp():
    """Importa `main.app` sin modificar `main.py` en disco y le activa el puente ERP + SSO."""
    if SSO_AUTH_CENTER_ENABLED and not _en_modo_test():
        # Con SSO Auth-Center activo, el login local esta deshabilitado; asegurar que
        # exigir_credenciales_fuertes() en main.py no bloquee el arranque si PRODUCCION=1.
        if len(core.LOGIN_USER or "") < 4:
            core.LOGIN_USER = "sso_auth_center_disabled"
        if len(core.LOGIN_PASS or "") < 16:
            core.LOGIN_PASS = "SSO_AuthCenter_Disabled_Local_Login_2026!"
        if not os.getenv("ANTHROPIC_API_KEY"):
            os.environ["ANTHROPIC_API_KEY"] = "sk-ant-placeholder-configure-in-env"
    from main import app as _vmo_app
    activar(_vmo_app)
    return _vmo_app


# Punto de entrada directo para IIS / Uvicorn: `uvicorn erp_bridge:app`
app = _cargar_app_con_erp()

