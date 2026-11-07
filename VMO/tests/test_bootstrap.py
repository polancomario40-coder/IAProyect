"""Prueba integral del bootstrap reproducible del issue #5."""
import os
import sqlite3
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core  # noqa: E402
import main  # noqa: E402 (solo para main.app — TestClient necesita la app con los routers ya incluidos)
from scripts import seed_precios_catalogo, setup_db  # noqa: E402


def test_bootstrap_desde_cero_crea_esquemas_datos_y_endpoints(tmp_path, monkeypatch):
    db_conduces = tmp_path / "db" / "conduces.db"
    db_estimaciones = tmp_path / "estimaciones" / "db" / "estimaciones.db"
    reportes = tmp_path / "reportes"
    reportes.mkdir()

    setup_db.setup(str(db_conduces))
    monkeypatch.setattr(core, "DB_PATH", str(db_conduces))
    monkeypatch.setattr(core, "EST_DB_PATH", str(db_estimaciones))
    monkeypatch.setattr(core, "REPORTES_DIR", str(reportes))
    core.setup_est_db()

    conteos = seed_precios_catalogo.seed(str(db_estimaciones))
    assert conteos == {
        "catalogo_estimacion": 73,  # 71 + EXTERIORES 16 (2026-10-05) + CEDIS 13 (2026-10-20)
        "precios_vmo": 37,  # + MR-42 de CEDIS (2026-10-20)
        "precios_domicem": 51,
    }
    assert seed_precios_catalogo.seed(str(db_estimaciones)) == conteos

    with sqlite3.connect(db_conduces) as conn:
        columnas = {fila[1] for fila in conn.execute("PRAGMA table_info(conduces)")}
    assert "fecha_pago" in columnas

    monkeypatch.setattr(core, "LOGIN_USER", "bootstrap-user")
    monkeypatch.setattr(core, "LOGIN_PASS", "bootstrap-pass")
    client = TestClient(main.app)
    login = client.post(
        "/login",
        json={"usuario": "bootstrap-user", "contrasena": "bootstrap-pass"},
    )
    assert login.status_code == 200
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    try:
        reporte = client.post("/api/generar-reporte", json={}, headers=headers)
        assert reporte.status_code == 200
        assert reporte.json()["download_url"].startswith("/download/")

        vista = client.get(
            "/api/estimaciones/vista-previa",
            params={
                "empresa": "VMO",
                "fase": "CEDIS",
                "fecha_desde": "2026-01-01",
                "fecha_hasta": "2026-01-31",
            },
            headers=headers,
        )
        assert vista.status_code == 200
        assert vista.json()["sin_match"] == []
        assert all(item["facturas_matcheadas"] is None for item in vista.json()["catalogo"])
    finally:
        core.active_tokens.pop(token, None)


def test_los_estaticos_piden_revalidar_antes_de_usar_el_cache():
    """El navegador cachea el HTML y el JS por separado, y el portal crea sus
    iframes por JavaScript —una carga hecha por script no respeta el bypass de
    Ctrl+Shift+R—. Sin esta cabecera, un cambio en logistica.logic.js le llega
    al usuario como HTML nuevo con JS viejo: la pagina queda colgada en
    "Cargando..." con un ReferenceError y sin nada en pantalla. Paso el
    2026-10-01 con la pagina de estadisticas.

    `no-cache` es "revalida antes de usar", no "no guardes": con el ETag que ya
    manda StaticFiles la respuesta normal es un 304 vacio.
    """
    from fastapi.testclient import TestClient
    import main

    cliente = TestClient(main.app)
    for ruta in ("/logistica.logic.js", "/logistica-estadisticas.html", "/index.html"):
        res = cliente.get(ruta)
        assert res.status_code == 200, ruta
        assert res.headers.get("cache-control") == "no-cache", f"{ruta} sin revalidacion"
        assert res.headers.get("etag"), f"{ruta} sin etag: la revalidacion costaria el archivo entero"
