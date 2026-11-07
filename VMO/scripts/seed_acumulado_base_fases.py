"""Siembra el "acumulado anterior" y los contratos paralelos (principal/PPACT)
de las 8 fases restantes (issue #13).

Los issues #11 (Acumulado Anterior en vivo) y #12 (contratos paralelos) dejaron
el mecanismo completo construido, pero solo DOMICEM/MACAO 2 tenia datos
sembrados (scripts/seed_acumulado_base_macao2.py y
scripts/seed_contrato_principal_macao2.py). Este script siembra las otras 8
fases, con los valores reales extraidos de los 14 documentos de estimacion que
entrego el jefe (hoja CD-COAF-REO-01: fin de periodo en H12, columna D =
"Cant. Proyecto" = tope del contrato principal, columna N = "Acumulado
Actual" = cantidad_base).

MACAO 2 queda deliberadamente FUERA de la tabla de abajo — sigue sembrado por
sus 2 scripts viejos. Unificarlos es limpieza futura, fuera del alcance del
issue #13.

Reglas de negocio confirmadas por el usuario (2026-08-26):

1. La columna D de un documento PPACT se ignora SIEMPRE. En los documentos
   reales trae valores inconsistentes (a veces igual a N, a veces distinto, a
   veces vacia). La serie PPACT nunca tiene tope propio:
   cantidad_proyecto_principal queda NULL en toda fila serie='ppact', igual
   que ya hace MACAO 2.
2. Un principal que no llega exacto a su tope es normal, no un dato malo
   (ej. TRB clave 2 = 2300.5 de 2301). Es la regla "la factura nunca se
   divide" funcionando: si un pedido no cabe entero en lo que queda del tope,
   la factura completa se va a PPACT y el principal se queda pegado justo por
   debajo. Se siembra tal cual, sin reconstruir historial.
3. VMO/CEDIS PPACT tiene un typo en el documento real del jefe: la celda H12
   dice "16/07/206" (texto, ano incompleto). Se siembra como 2026-07-16 — el
   archivo del jefe no se toca, el typo queda documentado aca.
4. VMO/CEDIS principal, claves 4 a 10, tienen la celda N vacia (no cero). Se
   siembran como cantidad_base = 0 con su tope real: vacio significa "nunca se
   entrego nada de este producto".
5. DOMICEM/VIVIENDAS, claves 1 2 3 4 6 7 9, traen N = 0 EXPLICITO en el
   documento (filas 17-25 de CD-COAF-REO-01, verificadas una por una contra la
   descripcion del catalogo). La primera version del seed las omitio y solo
   sembro las dos con acumulado distinto de cero (clave 5 = 207, clave 8 =
   228). Eso era incoherente con la regla 4: alli una celda VACIA se siembra
   como 0, y aca un CERO ESCRITO se estaba salteando, siendo evidencia mas
   fuerte. Una clave sin fila de base cae en el camino degradado de
   estimaciones_calcular() — se clasifica igual pero entra con calculado None,
   asi que su linea del documento sale sin acumulado. Le pasaba a la clave 2,
   la unica de las siete con facturas (5, todas posteriores a fecha_base).
   Las otras seis no tienen ninguna factura: se siembran igual para que la
   tabla refleje el documento entero y no una seleccion.

Fases solo-PPACT (DOMICEM/VIVIENDAS, VMO/PODIUM-1-2-3, VMO/EXTERIORES): sus
datos van en "principal" con tope None, NO en "ppact" (corregido 2026-08-26,
issue #14). En esas fases el PPACT ES el contrato (EST_OC_CONTRATO ya devuelve
el texto PPACT para ellas) — o sea que es su serie PRINCIPAL, no una serie de
desborde: no hay ningun contrato numerado del cual desbordar. La columna
"serie" distingue "serie principal del contrato" de "serie de desborde", asi
que 'principal' es el valor correcto y `tope=None` es semanticamente exacto
(PPACT nunca tiene techo).

La primera version de este script (issue #13) las sembraba como serie='ppact'
con "principal" vacio. Eso las dejaba INERTES: _est_clasificar_series() hace
`continue` cuando un producto no tiene fila 'principal' (core.py, rama
"if principal not in series"), asi que nunca leia la fila 'ppact' sembrada y
devolvia ppact.calculado=None. Verificado contra la BD real: el JSON de
vista-previa salia identico antes y despues de sembrar. Con los datos en
'principal' funciona sin ningun cambio de codigo, y la clasificacion de
facturas no se mueve (siguen yendo todas a 'principal'), asi que la generacion
de estas 3 fases queda intacta.

Uso:
    python scripts/seed_acumulado_base_fases.py --list
    python scripts/seed_acumulado_base_fases.py --todas
    python scripts/seed_acumulado_base_fases.py --fase "VMO/CEDIS" --fase "VMO/CANCHAS"
"""
import argparse
import os
import sqlite3
import sys


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "estimaciones", "db", "estimaciones.db")

# (empresa, fase) -> {
#     "fecha_base":       fecha de corte del documento del contrato principal,
#     "principal":        {clave: (cantidad_base, tope_del_contrato_principal)},
#     "ppact":            {clave: cantidad_base}   (solo claves con actividad PPACT real),
#     "fecha_base_ppact": fecha de corte del documento PPACT,
# }
# El orden de este diccionario es el orden en que se siembra y se imprime.
FASES = {
    ("DOMICEM", "CAVERNAS"): {
        "fecha_base": "2026-07-16",
        "principal": {
            "1": (4522.0, 7452.0), "2": (1903.0, 9705.0), "3": (2285.0, 2720.0),
            "4": (0.0, 2.0), "5": (0.0, 366.0), "6": (0.0, 51.0),
            "7": (148.0, 580.0), "8": (1795.0, 1795.0), "9": (1785.5, 1786.0),
            "10": (1643.5, 2695.0), "11": (2688.0, 2694.0), "12": (685.0, 685.0),
            "13": (975.5, 1620.0),
        },
        "ppact": {"4": 11.0, "8": 212.0, "11": 105.0},
        "fecha_base_ppact": "2026-07-16",
    },
    ("DOMICEM", "PATIO DE MANIOBRAS-TRB"): {
        "fecha_base": "2026-07-16",
        "principal": {
            "1": (141.0, 146.0), "2": (2300.5, 2301.0),
            "3": (591.0, 1193.0), "4": (4469.5, 4476.0),
        },
        "ppact": {"2": 333.0, "4": 501.0},
        "fecha_base_ppact": "2026-07-16",
    },
    # solo-PPACT: el PPACT es su unico contrato, o sea su serie principal
    # (tope None — PPACT nunca tiene techo). Ver el docstring de arriba.
    ("DOMICEM", "VIVIENDAS"): {
        "fecha_base": "2026-07-16",
        # las siete en cero traen N = 0 escrito en el documento, no la celda
        # vacia: se siembran tal cual (regla 5). Tope None por ser solo-PPACT.
        "principal": {
            "1": (0.0, None), "2": (0.0, None), "3": (0.0, None),
            "4": (0.0, None), "5": (207.0, None), "6": (0.0, None),
            "7": (0.0, None), "8": (228.0, None), "9": (0.0, None),
        },
        "ppact": {},
        "fecha_base_ppact": "2026-07-16",
    },
    # sin ningun documento PPACT — esta fase nunca agoto su contrato principal
    ("VMO", "CANCHAS"): {
        "fecha_base": "2026-07-16",
        "principal": {"1": (68.0, 461.0), "2": (0.0, 751.0), "3": (936.0, 1272.0)},
        "ppact": {},
        "fecha_base_ppact": "2026-07-16",
    },
    ("VMO", "CEDIS"): {
        "fecha_base": "2026-07-16",
        "principal": {
            "1": (2274.5, 3039.0), "2": (23.0, 29.0), "3": (21.0, 57.0),
            # claves 4-10: celda N vacia en el documento real -> base 0 (regla 4)
            "4": (0.0, 7.0), "5": (0.0, 7.0), "6": (0.0, 43.0), "7": (0.0, 7.0),
            "8": (0.0, 7.0), "9": (0.0, 7.0), "10": (0.0, 7.0),
            "11": (165.0, 165.0), "12": (32.5, 167.0),
            # 2026-10-20: renglon agregado por nosotros (MR-42), no esta en el
            # documento. Base 0: la primera entrega es del 2026-09-22. Tope 0:
            # no es del contrato original, asi que todo va a PPACT (decision
            # del usuario; el tope de 128 del primer dia lo mandaba al principal).
            "13": (0.0, 0.0),
        },
        "ppact": {"11": 1626.0},
        # typo del documento real ("16/07/206") normalizado — regla 3
        "fecha_base_ppact": "2026-07-16",
    },
    ("VMO", "PATIO DE MANIOBRAS-TRA"): {
        "fecha_base": "2026-07-16",
        "principal": {
            "1": (32.5, 44.0), "2": (192.5, 227.0),
            "3": (517.0, 663.0), "4": (1451.0, 1451.0),
        },
        "ppact": {"4": 83.0},
        "fecha_base_ppact": "2026-07-16",
    },
    # solo-PPACT (ver docstring)
    ("VMO", "PODIUM-1-2-3"): {
        "fecha_base": "2026-07-16",
        "principal": {"3": (3701.0, None)},
        "ppact": {},
        "fecha_base_ppact": "2026-07-16",
    },
    # solo-PPACT (ver docstring)
    ("VMO", "EXTERIORES"): {
        "fecha_base": "2026-07-16",
        "principal": {
            "1": (1872.0, None), "2": (670.0, None), "3": (14.0, None),
            "5": (207.0, None), "6": (348.0, None), "8": (7071.0, None),
            "9": (17150.5, None), "10": (5324.0, None), "11": (9332.0, None),
            "12": (521.0, None), "13": (70.0, None), "14": (280.0, None),
            "15": (667.0, None),
            # 2026-10-05: renglon agregado por nosotros, no esta en el
            # documento. 0 es exacto: la primera entrega es del 2026-09-05,
            # posterior a fecha_base.
            "16": (0.0, None),
        },
        "ppact": {},
        "fecha_base_ppact": "2026-07-16",
    },
}


def _orden_claves(claves):
    """Ordena claves numericas como numeros ('10' despues de '9') — solo para
    que los mensajes de error salgan legibles y deterministas."""
    return sorted(claves, key=lambda c: (0, int(c)) if c.isdigit() else (1, c))


def _contar(conn, empresa, fase, serie):
    return conn.execute(
        "SELECT COUNT(*) FROM estimacion_acumulado_base "
        "WHERE empresa = ? AND fase = ? AND serie = ?",
        (empresa, fase, serie),
    ).fetchone()[0]


def _validar(conn, empresa, fase, datos):
    """Devuelve None si la fase esta lista para sembrar, o el motivo del fallo
    (texto, sin el prefijo 'ERROR empresa/fase:' que arma main())."""
    principal = datos["principal"]
    ppact = datos["ppact"]

    claves_catalogo = {
        r[0] for r in conn.execute(
            "SELECT clave FROM catalogo_estimacion WHERE empresa = ? AND fase = ?",
            (empresa, fase),
        ).fetchall()
    }
    ausentes = (set(principal) | set(ppact)) - claves_catalogo
    if ausentes:
        # el catalogo cambio (o la fase no existe en esta BD) — sembrar igual
        # escribiria el acumulado en la fila equivocada de un documento oficial
        return f"claves ausentes en catalogo_estimacion: {_orden_claves(ausentes)}"

    # una clave de ppact sin su correspondiente en principal significa "cruzo un
    # tope que no sabemos cual es". Desde el issue #14 esta regla es
    # INCONDICIONAL: ya no hay fases con "principal" vacio — las 3 solo-PPACT
    # llevan sus datos en principal con tope None (ver docstring), asi que una
    # fila de ppact huerfana siempre es un error de datos.
    huerfanas = set(ppact) - set(principal)
    if huerfanas:
        return f"claves de ppact sin su correspondiente en principal: {_orden_claves(huerfanas)}"

    invalidos = []
    for clave, (base, tope) in principal.items():
        if not isinstance(base, (int, float)) or base < 0:
            invalidos.append(f"principal/{clave} cantidad_base={base!r}")
        # tope None es valido y esperado en las fases solo-PPACT (issue #14):
        # PPACT nunca tiene techo. Solo se rechaza un tope que exista y sea
        # negativo o no numerico.
        if tope is not None and (not isinstance(tope, (int, float)) or tope < 0):
            invalidos.append(f"principal/{clave} tope={tope!r}")
    for clave, base in ppact.items():
        if not isinstance(base, (int, float)) or base < 0:
            invalidos.append(f"ppact/{clave} cantidad_base={base!r}")
    if invalidos:
        return f"valores invalidos (deben ser numeros >= 0): {sorted(invalidos)}"

    return None


def seed(db_path=DEFAULT_DB_PATH, fases=None):
    """Siembra estimacion_acumulado_base para las fases pedidas.

    fases=None -> las 8 de FASES. Devuelve, por fase:
        {(empresa, fase): {
            "principal": (antes, despues),   # filas serie='principal'
            "ppact":     (antes, despues),   # filas serie='ppact'
            "error":     None | "texto del error",
        }}

    NUNCA llama sys.exit() ni levanta excepcion por una fase invalida: la fase
    queda con su "error" y ambos contadores sin cambio. Solo propaga
    excepciones reales de sqlite3 (BD corrupta, disco lleno).
    main() es quien traduce el dict a stdout/stderr y al exit code.

    `fases`: lista de tuplas (empresa, fase). Una tupla que no este en FASES
    devuelve su entrada con error="fase desconocida" (no levanta). Duplicados
    se deduplican. fases=None significa "las 8" — el guard de "nunca sembrar
    las 8 sin pedirlo" vive SOLO en el CLI (argparse), no aca: los tests
    necesitan poder llamar seed(tmp_db) sin flags.

    Cada fase es su propia transaccion: si la fase N falla la validacion, las
    fases ya comiteadas se conservan, la fase N no escribe NINGUNA fila, y el
    proceso sigue con las siguientes.
    """
    if fases is None:
        pedidas = list(FASES.keys())
    else:
        pedidas = []
        for f in fases:  # dedup preservando el orden en que las pidieron
            f = tuple(f)
            if f not in pedidas:
                pedidas.append(f)

    resultado = {}
    conn = sqlite3.connect(db_path)
    conn.isolation_level = None  # transacciones explicitas, una por fase
    try:
        for empresa, fase in pedidas:
            datos = FASES.get((empresa, fase))
            if datos is None:
                resultado[(empresa, fase)] = {
                    "principal": (0, 0), "ppact": (0, 0), "error": "fase desconocida"
                }
                continue

            antes_p = _contar(conn, empresa, fase, "principal")
            antes_q = _contar(conn, empresa, fase, "ppact")

            motivo = _validar(conn, empresa, fase, datos)
            if motivo:
                resultado[(empresa, fase)] = {
                    "principal": (antes_p, antes_p), "ppact": (antes_q, antes_q), "error": motivo
                }
                continue

            conn.execute("BEGIN")
            try:
                # UPSERT explicito, NUNCA "INSERT OR REPLACE": REPLACE borra la
                # fila en conflicto y la vuelve a insertar solo con las columnas
                # listadas — cualquier columna no listada vuelve a su default
                # (NULL). Ese fue un bug real de perdida de datos en el issue
                # #12 (los topes del contrato principal desaparecian en
                # silencio al re-correr el seed del issue #11). Aca la serie
                # principal SI escribe cantidad_proyecto_principal, asi que el
                # UPSERT la lista explicitamente; la serie ppact NUNCA la toca.
                conn.executemany(
                    "INSERT INTO estimacion_acumulado_base "
                    "(empresa, fase, clave, serie, fecha_base, cantidad_base, cantidad_proyecto_principal) "
                    "VALUES (?,?,?,'principal',?,?,?) "
                    "ON CONFLICT(empresa, fase, clave, serie) DO UPDATE SET "
                    "fecha_base = excluded.fecha_base, "
                    "cantidad_base = excluded.cantidad_base, "
                    "cantidad_proyecto_principal = excluded.cantidad_proyecto_principal",
                    # tope None (fases solo-PPACT, issue #14) va como NULL —
                    # float(None) reventaria con TypeError
                    [(empresa, fase, clave, datos["fecha_base"], float(base),
                      None if tope is None else float(tope))
                     for clave, (base, tope) in datos["principal"].items()],
                )
                # serie ppact: cantidad_proyecto_principal SIEMPRE NULL (regla 1)
                conn.executemany(
                    "INSERT INTO estimacion_acumulado_base "
                    "(empresa, fase, clave, serie, fecha_base, cantidad_base, cantidad_proyecto_principal) "
                    "VALUES (?,?,?,'ppact',?,?,NULL) "
                    "ON CONFLICT(empresa, fase, clave, serie) DO UPDATE SET "
                    "fecha_base = excluded.fecha_base, "
                    "cantidad_base = excluded.cantidad_base",
                    [(empresa, fase, clave, datos["fecha_base_ppact"], float(base))
                     for clave, base in datos["ppact"].items()],
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

            resultado[(empresa, fase)] = {
                "principal": (antes_p, _contar(conn, empresa, fase, "principal")),
                "ppact": (antes_q, _contar(conn, empresa, fase, "ppact")),
                "error": None,
            }
    finally:
        conn.close()
    return resultado


def _parse_fase(texto):
    """'VMO/CEDIS' -> ('VMO', 'CEDIS'). Ninguna fase real tiene '/' en el
    nombre, asi que partir por el primero alcanza."""
    if "/" not in texto:
        return None
    empresa, fase = texto.split("/", 1)
    return empresa.strip(), fase.strip()


def _imprimir_tabla():
    print("Fases sembrables por este script (issue #13) — MACAO 2 NO esta aca, "
          "la siembran sus 2 scripts viejos:")
    for (empresa, fase), datos in FASES.items():
        etiqueta = f"{empresa}/{fase}"
        # solo-PPACT: el PPACT es su unico contrato, asi que sus productos van
        # en 'principal' SIN tope (issue #14) — se detecta por eso, no por
        # tener el diccionario 'principal' vacio como antes
        solo_ppact = " (solo-PPACT)" if datos["principal"] and all(
            tope is None for _, tope in datos["principal"].values()
        ) else ""
        print(f"  {etiqueta:<34} principal={len(datos['principal']):<3} "
              f"ppact={len(datos['ppact']):<3} fecha_base={datos['fecha_base']}{solo_ppact}")


def main():
    parser = argparse.ArgumentParser(
        description="Siembra estimacion_acumulado_base (principal + PPACT) de las 8 fases restantes (issue #13)"
    )
    parser.add_argument("db_path", nargs="?", default=DEFAULT_DB_PATH, help="Ruta de estimaciones.db")
    # required=True: sin --todas ni --fase no se hace nada. Sembrar las 8 por
    # default seria escribir en la BD real por accidente.
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--todas", action="store_true", help="Siembra las 8 fases")
    grupo.add_argument("--fase", action="append", metavar="EMPRESA/FASE",
                       help="Siembra solo esta fase (repetible)")
    grupo.add_argument("--list", action="store_true", help="Imprime la tabla de fases sin tocar la BD")
    args = parser.parse_args()

    if args.list:
        _imprimir_tabla()
        return

    fases = None
    if args.fase:
        fases = []
        for texto in args.fase:
            par = _parse_fase(texto)
            if par is None or par not in FASES:
                validas = ", ".join(f"{e}/{f}" for e, f in FASES)
                parser.error(f"fase desconocida: {texto!r}. Validas: {validas}")
            if par not in fases:  # dedup silencioso
                fases.append(par)

    resultado = seed(args.db_path, fases)

    con_error = 0
    for (empresa, fase), info in resultado.items():
        etiqueta = f"{empresa}/{fase}"
        if info["error"]:
            con_error += 1
            print(f"ERROR {etiqueta}: {info['error']} — no se sembro nada de esta fase",
                  file=sys.stderr)
            continue
        pa, pd = info["principal"]
        qa, qd = info["ppact"]
        print(f"{etiqueta:<34}principal antes={pa} despues={pd:<5}ppact antes={qa} despues={qd}")

    ok = len(resultado) - con_error
    print(f"RESUMEN: {ok} fases OK, {con_error} con error")
    if con_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
