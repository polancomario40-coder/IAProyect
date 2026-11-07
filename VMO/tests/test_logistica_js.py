"""
La logica del dashboard de Logistica, corrida desde la misma suite que todo
lo demas.

Por que un test de Python que lanza node: el modulo de Logistica es 100%
cliente —no tiene backend, ni router, ni BD— asi que su logica es JavaScript y
no se puede probar con pytest directamente. Pero el proyecto tiene UNA sola
puerta (`python -m pytest tests/ -q`, que es lo que corre el CI), y un segundo
comando que alguien tiene que acordarse de correr es un comando que no se
corre. Asi que las pruebas se escriben con el runner que trae node —sin
dependencias ni package.json— y este archivo las mete adentro de la suite.

Las pruebas de verdad estan en `tests/logistica/*.test.js`.

Correr solo estas:  python -m pytest tests/test_logistica_js.py -v
O directo:          node --test tests/logistica/helpers.test.js
"""
import os
import re
import shutil
import subprocess
import sys

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_JS = os.path.join(BASE_DIR, "tests", "logistica")
LOGICA_JS = os.path.join(BASE_DIR, "static", "logistica.logic.js")
DASHBOARD = os.path.join(BASE_DIR, "static", "logistica.html")

node = shutil.which("node")
requiere_node = pytest.mark.skipif(
    node is None,
    reason="node no esta instalado — se saltan las pruebas de la logica de Logistica",
)


def _archivos_de_prueba():
    # Se pasan los archivos uno por uno: node 22 no acepta un directorio como
    # argumento de --test (intenta cargarlo como modulo y revienta).
    return sorted(
        os.path.join(DIR_JS, n) for n in os.listdir(DIR_JS) if n.endswith(".test.js")
    )


def test_hay_pruebas_de_logistica_para_correr():
    """Sin esto, renombrar los archivos dejaria la suite en verde probando
    nada: `node --test` sin archivos sale con codigo 0."""
    archivos = _archivos_de_prueba()
    assert len(archivos) >= 3, f"se esperaban al menos 3 archivos .test.js, hay {len(archivos)}"


def test_el_dashboard_carga_la_logica_que_se_prueba():
    """La logica vive en un archivo aparte para poder probarla; si el HTML
    dejara de cargarlo, estos tests seguirian en verde y el dashboard estaria
    roto. Es la misma leccion del issue #31: probar la pieza no prueba que
    llegue a destino."""
    with open(DASHBOARD, encoding="utf-8") as f:
        html = f.read()
    assert re.search(r'src="/logistica\.logic\.js(\?v=[^"]*)?"', html)
    assert os.path.exists(LOGICA_JS)


@requiere_node
def test_la_logica_del_dashboard_pasa_sus_pruebas():
    # `--test-reporter=tap` se pasa a proposito: node elige el reporter segun
    # si la salida es una terminal, y este envoltorio lee el resumen. Sin
    # fijarlo, el mismo comando imprime "# fail 0" o "ℹ fail 0" segun donde
    # corra, y la comprobacion de abajo depende de cual toco.
    proc = subprocess.run(
        [node, "--test", "--test-reporter=tap", *_archivos_de_prueba()],
        cwd=BASE_DIR, capture_output=True, text=True, timeout=180,
    )
    salida = proc.stdout + proc.stderr
    if proc.returncode != 0:
        # La salida de node va entera al reporte: un "fallo en node" sin el
        # detalle obliga a reproducirlo a mano, que es exactamente lo que este
        # envoltorio existe para evitar.
        print(salida, file=sys.stderr)
        fallidos = [l for l in salida.splitlines() if l.startswith("not ok")]
        pytest.fail("las pruebas de Logistica fallaron:\n" + "\n".join(fallidos or [salida]))

    # No alcanza con el codigo de salida: se comprueba que realmente corrio algo.
    assert "# fail 0" in salida, salida
    pasados = next((l for l in salida.splitlines() if l.startswith("# pass ")), "# pass 0")
    assert int(pasados.split()[-1]) >= 30, f"corrieron muy pocas pruebas: {pasados}"


def test_la_logica_se_sirve_por_HTTP_donde_el_dashboard_la_busca():
    """El HTML la pide como `/logistica.logic.js`. Que el archivo exista en
    disco no prueba que el mount de `main.py` lo entregue en esa ruta, y si no
    lo entrega el dashboard queda sin ninguna de sus funciones."""
    from fastapi.testclient import TestClient
    import main

    res = TestClient(main.app).get("/logistica.logic.js")
    assert res.status_code == 200, res.status_code
    assert "computeCumplimiento" in res.text


def test_la_pagina_de_estadisticas_se_sirve_y_carga_la_misma_logica():
    """La página de estadísticas no recalcula nada por su cuenta: usa el mismo
    `logistica.logic.js` que el dashboard del día. Si dejara de cargarlo,
    tendría que reimplementar el cruce, que es justo lo que el diseño evita."""
    from fastapi.testclient import TestClient
    import main

    c = TestClient(main.app)
    res = c.get("/logistica-estadisticas.html")
    assert res.status_code == 200, res.status_code
    assert re.search(r'src="/logistica\.logic\.js(\?v=[^"]*)?"', res.text)
    # Y usa las funciones que se prueban, no copias propias.
    for fn in ("computeCumplimiento", "restaurarDia", "plantasOatYDelDia",
               "acumuladoDeCumplimiento", "serieDeCumplimiento"):
        assert fn in res.text, fn


def test_las_tres_paginas_de_logistica_comparten_logica_y_api():
    """Las tres son archivos separados a propósito, pero el cálculo y el
    hablarle al servidor tienen que seguir viniendo de un solo lado. Tres
    copias de la misma función de fetch se separan sin que nadie lo note."""
    from fastapi.testclient import TestClient
    import main

    c = TestClient(main.app)
    for pagina in ("/logistica.html", "/logistica-historial.html",
                   "/logistica-estadisticas.html", "/logistica-comparacion.html",
                   "/logistica-cancelados.html", "/logistica-reporte-dia.html",
                   "/logistica-indicadores.html"):
        html = c.get(pagina).text
        assert re.search(r'src="/logistica\.logic\.js(\?v=[^"]*)?"', html), pagina
        assert re.search(r'src="/logistica\.api\.js(\?v=[^"]*)?"', html), pagina
        assert "function apiLogistica" not in html, (
            f"{pagina} redefine apiLogistica en vez de usar el compartido")
    assert c.get("/logistica.api.js").status_code == 200


def test_el_portal_tiene_las_tres_secciones_de_logistica_en_el_sidebar():
    """El módulo se navega desde el sidebar del portal, como Estimaciones. Si
    un panel o su nav-item desaparece, la sección queda inalcanzable."""
    from fastapi.testclient import TestClient
    import main

    portal = TestClient(main.app).get("/index.html").text
    for seccion in ("dia", "historial", "estadisticas", "indicadores", "comparacion", "cancelados", "reporte-dia"):
        assert f"mostrarPanelLog('{seccion}'" in portal, seccion
        assert f'id="panel-log-{seccion}"' in portal, seccion
        assert f'id="iframe-log-{seccion}"' in portal, seccion
    for etiqueta in ("Cumplimiento del día", "Historial", "Estadísticas", "Comparación",
                     "Reporte cancelados", "Reporte del día", "Indicadores"):
        assert etiqueta in portal, etiqueta


def test_los_iframes_de_logistica_no_cargan_hasta_que_se_entra():
    """Cada sección pide datos al servidor y la del día baja una librería de un
    CDN: los tres src van en data-src y se asignan al entrar, no al abrir el
    portal."""
    from fastapi.testclient import TestClient
    import main

    portal = TestClient(main.app).get("/index.html").text
    for pagina in ("/logistica.html", "/logistica-historial.html",
                   "/logistica-estadisticas.html", "/logistica-comparacion.html",
                   "/logistica-cancelados.html", "/logistica-reporte-dia.html",
                   "/logistica-indicadores.html"):
        assert f'data-src="{pagina}"' in portal, pagina
        # El espacio de adelante importa: sin el, `data-src="..."` contiene
        # `src="..."` y la comprobacion pasa siempre.
        assert f' src="{pagina}"' not in portal, (
            f"{pagina} tiene src fijo: se cargaria al abrir el portal")


def test_la_comparacion_usa_el_mismo_calculo_que_el_resto():
    """La pestaña Comparación reemplaza el HTML aparte que leía los Excel
    consolidados. Tiene que recalcular con las funciones probadas del logic.js
    y no leer ningún Excel: si volviera a leerlos, los porcentajes saldrían de
    otro cálculo que el del dashboard."""
    from fastapi.testclient import TestClient
    import main

    html = TestClient(main.app).get("/logistica-comparacion.html").text
    for fn in ("restaurarDia", "computeCumplimiento", "comparacionPorDia",
               "acumuladoDeCumplimiento"):
        assert fn in html, fn
    assert "XLSX" not in html and 'type="file"' not in html


def test_el_reporte_de_cancelados_usa_la_misma_funcion_que_el_excel_del_dia():
    """Cada fila del reporte sale de filasCancelados(), la del Excel de un día,
    a través de reporteCancelados(). Si la página armara las filas por su
    cuenta, un pedido podría salir distinto en los dos Excel."""
    from fastapi.testclient import TestClient
    import main

    html = TestClient(main.app).get("/logistica-cancelados.html").text
    for fn in ("restaurarDia", "reporteCancelados", "/api/logistica/reporte-cancelados"):
        assert fn in html, fn
    assert "XLSX" not in html


def test_el_reporte_del_dia_usa_el_mismo_calculo_que_la_pantalla():
    """Los números del PDF salen de reporteDelPeriodo() (un día es un rango de
    un día), que llama a computeCumplimiento() como la pantalla del día. Si la
    página los armara por su cuenta, el PDF podría decir otro porcentaje que el
    dashboard."""
    from fastapi.testclient import TestClient
    import main

    html = TestClient(main.app).get("/logistica-reporte-dia.html").text
    for fn in ("restaurarDia", "reporteDelPeriodo", "/api/logistica/reporte-dia"):
        assert fn in html, fn
    assert "XLSX" not in html


def test_el_dashboard_del_dia_ya_no_tiene_pestana_de_historial():
    """El Historial subió al sidebar del portal. Si la pestaña volviera,
    habría dos caminos al mismo lugar y dos listados que mantener."""
    from fastapi.testclient import TestClient
    import main

    html = TestClient(main.app).get("/logistica.html").text
    assert 'data-tab="historial"' not in html
    assert "renderHistorial" not in html
