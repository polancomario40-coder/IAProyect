"""
Tests de scripts/recuperar_nombres.py (issue #78) — la reconstruccion de los
escaneos con nombre fuera de la convencion MM-DD-Mx-NNNNN.pdf, por numero
final + planta de carpeta contra el Excel.

Solo se prueba la logica pura (`reconstruir`, `_plantas_de_la_ruta`,
`_nombre_convencion`) y el main() sobre fixtures chicos: ZIP y Excel armados
en tmp_path. Nunca se toca el lote real ni ninguna base.

Correr con: python -m pytest tests/test_recuperar_nombres.py -v
"""
import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import recuperar_nombres  # noqa: E402


def _fila(id_documento, fecha="2026-08-19", codigo=None):
    return {
        "id_documento": id_documento,
        "fecha": fecha,
        "cliente": "X",
        "descripcion": "Y",
        "cantidad": 1.0,
        "planta": id_documento[:2] + " Macao",
        "fase": "MACAO 2",
        "empresa": "DOMICEM",
        "codigo": codigo,
    }


# ── _plantas_de_la_ruta ──────────────────────────────────────────────────

def test_planta_sale_de_la_carpeta_no_del_archivo():
    assert recuperar_nombres._plantas_de_la_ruta("19-8-2026-M4/IMG_33940.pdf") == ["M4"]
    # El token del NOMBRE del archivo no cuenta como planta de carpeta:
    assert recuperar_nombres._plantas_de_la_ruta("carpeta/08-19-M3-33940.pdf") == []
    # M40 no es una planta (M4 seguido de digito):
    assert recuperar_nombres._plantas_de_la_ruta("lote-M40/x.pdf") == []


# ── reconstruir ──────────────────────────────────────────────────────────

def test_reconstruye_por_numero_final_y_planta_de_carpeta():
    por_id = {"M4" + "33940".zfill(8): _fila("M400033940", codigo="08-19-m4-33940.pdf")}
    resultado, fila, nombre = recuperar_nombres.reconstruir(
        "19-8-2026-M4/IMG_33940.pdf", por_id)
    assert resultado == "ok"
    assert fila["id_documento"] == "M400033940"
    assert nombre == "08-19-m4-33940.pdf"   # el Codigo del Excel manda


def test_sin_codigo_en_el_excel_arma_el_nombre_con_fecha_e_id():
    por_id = {"M800012345": _fila("M800012345", fecha="2026-08-20", codigo=None)}
    resultado, _fila_r, nombre = recuperar_nombres.reconstruir(
        "lote-M8/scan 12345.pdf", por_id)
    assert resultado == "ok"
    assert nombre == "08-20-M8-12345.pdf"


def test_numero_en_dos_plantas_sin_carpeta_es_ambiguo():
    """Sin planta en la ruta y con el mismo numero en dos plantas, NO se
    adivina: queda listado como ambiguo."""
    por_id = {
        "M300033940": _fila("M300033940"),
        "M400033940": _fila("M400033940"),
    }
    resultado, candidatos, nombre = recuperar_nombres.reconstruir(
        "sueltos/IMG_33940.pdf", por_id)
    assert resultado == "ambiguo"
    assert {f["id_documento"] for f in candidatos} == {"M300033940", "M400033940"}
    assert nombre is None


def test_numero_inexistente_es_no_hallado():
    resultado, motivo, _n = recuperar_nombres.reconstruir(
        "19-8-2026-M4/IMG_99999.pdf", {"M400033940": _fila("M400033940")})
    assert resultado == "no_hallado"
    assert "99999" in motivo


def test_nombre_sin_numero_es_no_hallado():
    resultado, motivo, _n = recuperar_nombres.reconstruir(
        "19-8-2026-M4/escaneo_suelto.pdf", {})
    assert resultado == "no_hallado"
    assert "numero" in motivo


# ── main: emite copias renombradas y no toca los que ya estan bien ───────

def test_main_emite_copias_y_lista_el_resto(tmp_path, monkeypatch, capsys):
    import xlwt
    # Excel nuevo minimo (10 columnas, hoja de datos con cabeceras):
    wb = xlwt.Workbook()
    ws = wb.add_sheet("COnduces")
    cabeceras = ("Conduce", "Fecha", "Referencia", "Cliente", "Producto",
                 "Cant.", "Unidad", "Planta", "Anotaciones", "Codigo")
    for c, h in enumerate(cabeceras):
        ws.write(0, c, h)
    ws.write(1, 0, "M400033940")
    ws.write(1, 1, "08/19/26")
    ws.write(1, 3, "CLIENTE M4")
    ws.write(1, 4, "PRODUCTO")
    ws.write(1, 5, 7)
    ws.write(1, 7, "M4 Punta Cana")
    ws.write(1, 9, "08-19-M4-33940.pdf")
    excel = tmp_path / "COnduces.xls"
    wb.save(str(excel))

    zip_path = tmp_path / "lote.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("19-8-2026-M4/IMG_33940.pdf", b"%PDF-recuperable")
        zf.writestr("19-8-2026-M4/08-19-M4-77777.pdf", b"%PDF-convencion")  # ya esta bien: no se toca
        zf.writestr("19-8-2026-M4/IMG_11111.pdf", b"%PDF-sin-fila")          # no hallado
        zf.writestr("19-8-2026-M4/foto.jpeg", b"\xff\xd8")                   # no es PDF: se ignora

    staging = tmp_path / "staging"
    assert recuperar_nombres.main(zip_path, excel, staging) == 0

    # La copia renombrada existe, con los bytes del original:
    assert (staging / "08-19-m4-33940.pdf").read_bytes() == b"%PDF-recuperable"
    # El que ya venia a la convencion NO se copio:
    assert list(p.name for p in staging.iterdir()) == ["08-19-m4-33940.pdf"]
    salida = capsys.readouterr().out
    assert "Recuperados: 1" in salida
    assert "No hallados: 1" in salida
    assert "IMG_11111.pdf" in salida
