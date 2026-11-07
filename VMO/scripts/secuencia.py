# by a_oller
"""
secuencia.py — Reconcilia los escaneos contra las bases usando la secuencia
que trae impresa cada conduce, y reporta lo que falta.

Por que existe. El numero de conduce no es un identificador opaco: son 10
caracteres, los 2 primeros la PLANTA (M3, M5, M7, M8) y los 8 restantes una
SECUENCIA propia de esa planta, que avanza con el tiempo. Verificado sobre las
4.224 filas de las dos tablas el 2026-09-07: el formato no falla ni una vez, no hay un numero
repetido, y ordenando por numero dentro de cada planta NO hay una sola
inversion de fecha. O sea que numero y fecha —que Vision lee por separado del
mismo papel— se validan entre si.

Eso convierte a la secuencia en un CONTROL DE TOTALIDAD, que es lo que ninguna
otra parte del sistema tiene: la base sabe lo que entro, pero no sabia lo que
falto. Con la secuencia, un conduce ausente deja un agujero visible.

Hay dos preguntas distintas y este script las separa a proposito:

  1. HUERFANOS — escaneado pero en ninguna tabla. Es una respuesta cerrada: el
     PDF esta ahi, el conduce existe, y el import lo perdio en silencio. El
     2026-09-07 habia 9, todos de junio y julio.

  2. HUECOS — un numero que no esta ni escaneado ni en la base. NO es
     concluyente y el script no lo presenta como tal: la planta le sirve a mas
     de un cliente, asi que el numero pudo no ser nuestro nunca. Solo el
     listado de secuencia de la propia planta lo resuelve.

El corte importa y por eso se imprime. `_est_calcular_acumulados()` saltea todo
conduce con `fecha <= corte` (el corte es el MAX entre `fecha_base` del seed y
`fecha_hasta` de las cerradas). Un faltante POR DEBAJO del corte ya esta contado
en el acumulado base, que salio de los documentos del cliente: no es plata que
falte, es fidelidad del import. Uno POR ENCIMA del corte todavia no se conto en
ningun lado y si mueve m3 del proximo documento. Mezclarlos convertiria un
reporte accionable en 400 numeros que nadie mira.

Misma regla de oro que estado.py: nunca imprimir un numero que no se pudo
calcular. Si falta la base o los ZIP, el bloque dice por que no sabe.

Uso:
    python scripts/secuencia.py             # el reporte
    python scripts/secuencia.py --huecos    # ademas, la lista completa de huecos

No escribe nada: abre las bases en modo solo-lectura y de los ZIP lee solo el
indice, sin extraer un byte.
"""

import argparse
import re
import sqlite3
import zipfile
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DB_ESTIMACIONES = BASE_DIR / "estimaciones" / "db" / "estimaciones.db"

# Las mismas dos fuentes que espeja backup_db.py, mas los PDF que el import
# nuevo deja como respaldo propio desde el 2026-08-24.
ESCANEOS_DIR = BASE_DIR / "conduces" / "archivos"
ESCANEOS_SUELTOS = ESCANEOS_DIR / "escaneos"
EST_PROCESADAS = BASE_DIR / "estimaciones" / "facturas" / "procesadas"

# Nombre de escaneo: MM-DD-Mx-NNNNN.pdf. La fecha del nombre no se usa para
# nada que dependa de ella —la de la base manda— pero sirve para ubicar un
# huerfano en el tiempo sin abrir el PDF.
RE_ESCANEO = re.compile(r"(\d{2})-(\d{2})-(M\d)-(\d+)\.pdf$", re.IGNORECASE)

# id_documento: 2 de planta + 8 de secuencia.
LARGO_ID = 10
LARGO_PLANTA = 2


def _titulo(texto):
    print("\n" + texto)
    print("-" * len(texto))


def _no_se(que, motivo):
    print("  " + que + ": NO DISPONIBLE — " + motivo)


def partir_id(id_documento):
    """('M8', 12024) para 'M800012024', o None si no tiene esa forma.

    Devolver None en vez de reventar es deliberado: un id con otra forma es un
    dato a reportar, no una excepcion que corte el reporte entero.
    """
    if not id_documento or len(id_documento) != LARGO_ID:
        return None
    planta, secuencia = id_documento[:LARGO_PLANTA], id_documento[LARGO_PLANTA:]
    if not secuencia.isdigit():
        return None
    return planta.upper(), int(secuencia)


def leer_escaneos():
    """{(planta, numero): nombre de archivo} de los ZIP, los sueltos y procesadas/.

    De los ZIP se lee SOLO el indice central (namelist), que no descomprime
    nada: son ~1,5 GB y el reporte tiene que costar segundos.

    Devuelve (escaneos, avisos). Un ZIP ilegible es un aviso, no una
    excepcion: el resto del reporte sigue valiendo sin el.
    """
    escaneos, avisos = {}, []

    def registrar(nombre):
        m = RE_ESCANEO.search(Path(nombre.replace("\\", "/")).name)
        if m:
            escaneos[(m.group(3).upper(), int(m.group(4)))] = m.group(0)
            return True
        return False

    if not ESCANEOS_DIR.is_dir():
        avisos.append("no existe " + str(ESCANEOS_DIR.relative_to(BASE_DIR)) +
                      " (esta en .gitignore): sin escaneos no hay reconciliacion")
        return escaneos, avisos

    sin_parsear = 0
    for zip_path in sorted(ESCANEOS_DIR.glob("*.zip")):
        try:
            with zipfile.ZipFile(zip_path) as zf:
                nombres = [n for n in zf.namelist() if n.lower().endswith(".pdf")]
        except (zipfile.BadZipFile, OSError) as e:
            avisos.append("no se pudo leer " + zip_path.name + " (" + str(e) + ")")
            continue
        sin_parsear += sum(0 if registrar(n) else 1 for n in nombres)

    for carpeta in (ESCANEOS_SUELTOS, EST_PROCESADAS):
        if carpeta.is_dir():
            sin_parsear += sum(0 if registrar(p.name) else 1
                               for p in carpeta.glob("*.pdf"))

    if sin_parsear:
        avisos.append(str(sin_parsear) + " escaneo(s) con nombre fuera de "
                      "MM-DD-Mx-NNNNN.pdf: no se pueden reconciliar")
    return escaneos, avisos


def leer_base(con):
    """Lo que hay en las TRES tablas, indexado por (planta, numero).

    Devuelve (en_facturas, en_pendientes, en_descartados, ids_raros).
    `ids_raros` son los id_documento que no parten en planta+secuencia: hoy
    son cero, y si algun dia no lo son hay que verlo antes de creerle a los
    huecos.

    pendiente_descartado entra desde el issue #78: un conduce descartado a
    proposito sigue existiendo y esta registrado — sin esta tabla, el primer
    descarte real apareceria como huerfano ("el import lo perdio") cuando en
    realidad alguien decidio no facturarlo. La tabla puede no existir en una
    base anterior a las migraciones del issue #38; en ese caso vale vacia.
    """
    en_facturas, en_pendientes, en_descartados, ids_raros = {}, {}, {}, []
    for tabla, destino in (("facturas", en_facturas),
                           ("pendientes_revision", en_pendientes),
                           ("pendiente_descartado", en_descartados)):
        try:
            filas = con.execute("select id_documento, fecha from " + tabla)
        except sqlite3.OperationalError:
            continue  # base anterior a la migracion que crea la tabla
        for id_doc, fecha in filas:
            partido = partir_id(id_doc)
            if partido is None:
                ids_raros.append((tabla, id_doc))
            else:
                destino[partido] = fecha
    return en_facturas, en_pendientes, en_descartados, ids_raros


def corte_global(con):
    """La fecha hasta la cual los m3 YA estan contados, en cualquier fase.

    Es el MAX entre el `fecha_base` del seed y el `fecha_hasta` de las
    cerradas — la misma nocion que `_est_corte_de_conteo()` de core.py, pero
    agregada sobre todas las fases, porque un numero ausente no tiene fase
    conocida (justamente por eso falta). Tomar el MAX es el criterio
    conservador para ESTE uso: solo se marca como "todavia cuenta" lo que esta
    por encima del corte de TODAS las fases, asi que el bloque de arriba del
    corte no se llena de falsos positivos.

    Devuelve None si no hay ni seed ni cierres, que equivale a "no hay nada
    contado" y hace que todo faltante cuente.
    """
    corte = None
    for sql in ("select max(fecha_base) from estimacion_acumulado_base",
                "select max(fecha_hasta) from estimacion_cerrada"):
        try:
            valor = con.execute(sql).fetchone()[0]
        except sqlite3.OperationalError:
            valor = None  # base minima o anterior a las migraciones
        if valor is not None and (corte is None or valor > corte):
            corte = valor
    return corte


def agrupar_por_planta(claves):
    por_planta = defaultdict(list)
    for planta, numero in claves:
        por_planta[planta].append(numero)
    return {p: sorted(v) for p, v in sorted(por_planta.items())}


def buscar_inversiones(presentes):
    """Pares consecutivos por numero donde la fecha RETROCEDE, por planta.

    Cero inversiones es lo que hace confiable a todo lo demas: si el numero y
    la fecha se contradicen, un hueco deja de significar algo. Por eso esto se
    chequea cada corrida en vez de darlo por sabido.
    """
    inversiones = []
    for planta, numeros in agrupar_por_planta(presentes).items():
        anterior = None
        for numero in numeros:
            fecha = presentes[(planta, numero)]
            if anterior and fecha and anterior[1] and fecha < anterior[1]:
                inversiones.append((planta, anterior, (numero, fecha)))
            if fecha:
                anterior = (numero, fecha)
    return inversiones


def calcular_huecos(presentes):
    """Numeros ausentes dentro del rango observado de cada planta.

    Cada hueco sale como (planta, numero, fecha del ultimo conduce presente
    ANTES). Esa fecha es la que ubica al hueco contra el corte: no se puede
    saber la fecha de un conduce que no esta, pero como la secuencia es
    monotona con la fecha, la del anterior es una cota inferior valida.
    """
    huecos = []
    for planta, numeros in agrupar_por_planta(presentes).items():
        existentes = set(numeros)
        for numero in range(numeros[0], numeros[-1] + 1):
            if numero in existentes:
                continue
            previo = numero - 1
            while previo not in existentes and previo >= numeros[0]:
                previo -= 1
            huecos.append((planta, numero, presentes.get((planta, previo))))
    return huecos


def clasificar_por_corte(huecos, corte):
    """Parte los huecos en (arriba, abajo, sin_ubicar) segun el corte.

    Es la regla que decide si un hueco es plata o no, y por eso vive aparte de
    la impresion. Un hueco POR DEBAJO del corte ya esta contado en el acumulado
    base; uno POR ENCIMA no se conto en ningun lado.

    La comparacion usa la fecha del conduce presente ANTERIOR, que es una cota
    INFERIOR de la fecha real del ausente (la secuencia es monotona con la
    fecha). Eso hace conservador al grupo de arriba: si la cota inferior ya
    supera el corte, la fecha real tambien.

    Tres grupos y no dos: si el conduce anterior no tiene fecha, el hueco no se
    puede ubicar, y meterlo en cualquiera de los dos montones seria inventar.
    """
    arriba, abajo, sin_ubicar = [], [], []
    for hueco in huecos:
        fecha_previa = hueco[2]
        if corte is None:
            arriba.append(hueco)  # nada contado todavia: todo faltante cuenta
        elif fecha_previa is None:
            sin_ubicar.append(hueco)
        elif fecha_previa > corte:
            arriba.append(hueco)
        else:
            abajo.append(hueco)
    return arriba, abajo, sin_ubicar


def bloque_reconciliacion(escaneos, en_facturas, en_pendientes, en_descartados, avisos):
    _titulo("reconciliacion: escaneos contra las bases")

    for aviso in avisos:
        print("  AVISO: " + aviso)
    if not escaneos:
        _no_se("huerfanos", "no se pudo leer ningun escaneo")
        return

    print("  escaneos     : {:,}".format(len(escaneos)))
    print("  en facturas  : {:,}".format(len(en_facturas)))
    print("  pendientes   : {:,}".format(len(en_pendientes)))
    print("  descartados  : {:,}".format(len(en_descartados)))

    en_base = set(en_facturas) | set(en_pendientes) | set(en_descartados)
    huerfanos = sorted(set(escaneos) - en_base)
    sin_escaneo = sorted(en_base - set(escaneos))

    print()
    if huerfanos:
        print("  *** {} ESCANEADO(S) Y EN NINGUNA TABLA — el import los perdio:".format(
            len(huerfanos)))
        for planta, numero in huerfanos:
            print("        {}{:08d}   {}".format(planta, numero, escaneos[(planta, numero)]))
        print("      Un huerfano PUEDE ser un bloqueo por sello que el import viejo")
        print("      anoto solo en puente_progreso.txt y nunca guardo en ninguna")
        print("      tabla (comprobado el 2026-09-08 con los 9 perdidos — la version")
        print("      anterior de este texto afirmaba lo contrario). Abrir el PDF es lo")
        print("      unico que dice si era nuestro, de otro cliente, o un repetido.")
    else:
        print("  huerfanos    : ninguno (todo escaneo esta en alguna tabla)")

    if sin_escaneo:
        print()
        print("  *** {} EN LA BASE SIN ESCANEO con ese nombre:".format(len(sin_escaneo)))
        for planta, numero in sin_escaneo[:20]:
            print("        {}{:08d}".format(planta, numero))
        if len(sin_escaneo) > 20:
            print("        ... y {} mas".format(len(sin_escaneo) - 20))
        print("      El PDF de la estimacion les deja una pagina ESCANEO NO")
        print("      DISPONIBLE, y un documento con esas paginas no es entregable.")
    else:
        print("  sin escaneo  : ninguno (los {:,} de la base tienen su PDF)".format(
            len(en_base)))


def bloque_integridad(presentes, ids_raros):
    _titulo("integridad de la secuencia")

    if ids_raros:
        print("  *** {} id_documento que NO parten en planta+secuencia:".format(len(ids_raros)))
        for tabla, id_doc in ids_raros[:10]:
            print("        {}  ({})".format(id_doc, tabla))
        print("      Mientras esto no sea cero, los huecos de abajo valen menos.")
    else:
        print("  formato      : las {:,} filas parten en planta + 8 digitos".format(
            len(presentes)))

    inversiones = buscar_inversiones(presentes)
    if inversiones:
        print("  *** {} INVERSION(ES) — un numero mayor con fecha anterior:".format(
            len(inversiones)))
        for planta, (n1, f1), (n2, f2) in inversiones[:10]:
            print("        {}: {:08d} ({}) -> {:08d} ({})".format(planta, n1, f1, n2, f2))
        print("      Numero y fecha se leen del mismo papel por separado, asi que")
        print("      una inversion es una lectura mala de alguno de los dos.")
    else:
        print("  monotonia    : sin inversiones de fecha en ninguna planta")


def bloque_huecos(presentes, corte, mostrar_todos):
    _titulo("huecos de secuencia, contra el corte de conteo")

    if corte is None:
        print("  corte        : no hay seed ni cierres — todo faltante todavia cuenta")
    else:
        print("  corte        : " + corte + "  (hasta aca los m3 ya estan contados)")

    huecos = calcular_huecos(presentes)
    if not huecos:
        print("  huecos       : ninguno")
        return

    arriba, abajo, sin_ubicar = clasificar_por_corte(huecos, corte)

    print()
    for planta, numeros in agrupar_por_planta(presentes).items():
        del_planta = [h for h in huecos if h[0] == planta]
        print("  {}: {:08d}..{:08d}   presentes {:,}   ausentes {}".format(
            planta, numeros[0], numeros[-1], len(numeros), len(del_planta)))

    print()
    print("  por debajo del corte : {:,}".format(len(abajo)))
    print("      Ya contados en el acumulado base, que salio de los documentos del")
    print("      cliente. Si faltan, es fidelidad del import, no plata.")
    print("  POR ENCIMA del corte : {}".format(len(arriba)))
    if arriba:
        print("      Estos todavia no se contaron en ningun lado. Si eran nuestros,")
        print("      son m3 que no van a entrar al proximo documento.")
        for planta, numero, fecha_previa in arriba[:40]:
            print("        {}{:08d}   despues del {}".format(planta, numero, fecha_previa))
        if len(arriba) > 40:
            print("        ... y {} mas".format(len(arriba) - 40))
    else:
        print("      Ninguno: nada que se haya entregado despues del corte falta.")

    if sin_ubicar:
        print("  sin ubicar           : {}".format(len(sin_ubicar)))
        print("      El conduce anterior no tiene fecha, asi que no se pueden")
        print("      comparar contra el corte. Mirarlos a mano.")
        for planta, numero, _ in sin_ubicar[:20]:
            print("        {}{:08d}".format(planta, numero))

    if mostrar_todos and abajo:
        print()
        print("  todos los huecos por debajo del corte:")
        por_planta = defaultdict(list)
        for planta, numero, _ in abajo:
            por_planta[planta].append(numero)
        for planta in sorted(por_planta):
            print("    {}: {}".format(
                planta, ", ".join(str(n) for n in sorted(por_planta[planta]))))

    print()
    print("  Un hueco NO prueba que falte un conduce: la planta le sirve a mas de")
    print("  un cliente, asi que el numero pudo no ser nuestro nunca. Eso lo cierra")
    print("  el listado de secuencia de la propia planta para el rango, y nada mas.")


def bloque_punta(presentes):
    """El ultimo numero visto por planta, que es el ancla del proximo import."""
    _titulo("punta de cada planta")
    print("  El numero mas alto que entro. El proximo lote deberia arrancar aca.")
    print()
    for planta, numeros in agrupar_por_planta(presentes).items():
        ultimo = numeros[-1]
        print("  {}: {}{:08d}   {}".format(
            planta, planta, ultimo, presentes[(planta, ultimo)] or "sin fecha"))


def main():
    parser = argparse.ArgumentParser(
        description="Reconcilia escaneos contra las bases usando la secuencia por planta.")
    parser.add_argument("--huecos", action="store_true",
                        help="listar tambien los huecos por debajo del corte")
    args = parser.parse_args()

    print("=" * 64)
    print("SECUENCIA POR PLANTA — control de totalidad, calculado ahora")
    print("=" * 64)

    if not DB_ESTIMACIONES.exists():
        _no_se("todo", "no existe " + str(DB_ESTIMACIONES.relative_to(BASE_DIR)) +
               " (esta en .gitignore)")
        return

    escaneos, avisos = leer_escaneos()
    con = sqlite3.connect("file:" + DB_ESTIMACIONES.as_posix() + "?mode=ro", uri=True)
    try:
        en_facturas, en_pendientes, en_descartados, ids_raros = leer_base(con)
        corte = corte_global(con)
    finally:
        con.close()

    # Los descartados tambien son conduces vistos: cuentan para la
    # integridad de la secuencia y para los huecos igual que los demas.
    presentes = dict(en_facturas)
    presentes.update(en_pendientes)
    presentes.update(en_descartados)

    bloque_reconciliacion(escaneos, en_facturas, en_pendientes, en_descartados, avisos)
    bloque_integridad(presentes, ids_raros)
    bloque_huecos(presentes, corte, args.huecos)
    bloque_punta(presentes)
    print()


if __name__ == "__main__":
    main()
