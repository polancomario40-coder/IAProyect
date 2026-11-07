"""
Tests de scripts/avisar_pendientes.py — el aviso diario de conduces pendientes.

Lo que mas se prueba acá no es el listado, es **la comparacion contra el aviso
anterior**. Al 2026-09-04 los 39 pendientes son todos `falta sello`, todos de
MACAO 2, y no se mueven desde el 2026-08-20: un correo diario identico se filtra
en una semana, y el dia que entre uno nuevo ya nadie lo abre. El asunto tiene que
distinguir "39 sin cambios" de "39, 2 nuevos".

Ninguna prueba manda un correo ni toca la base real: BDs sqlite temporales y el
envio monkeypatcheado.

Correr con: python -m pytest tests/test_avisar_pendientes.py -v
"""
import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import avisar_pendientes as ap  # noqa: E402


def _bd(tmp_path, filas):
    ruta = tmp_path / "est.db"
    con = sqlite3.connect(str(ruta))
    con.execute("""CREATE TABLE pendientes_revision (
        id_documento TEXT, fecha DATE, empresa TEXT, fase TEXT, motivo TEXT,
        cantidad REAL, descripcion TEXT, archivo_pdf TEXT)""")
    con.executemany("INSERT INTO pendientes_revision VALUES (?,?,?,?,?,?,?,?)", filas)
    con.commit()
    con.close()
    return ruta


def _fila(id_doc, fecha="2026-06-01", motivo="falta sello", fase="MACAO 2", cant=7.0):
    return (id_doc, fecha, "DOMICEM", fase, motivo, cant, "Hormigon", f"{id_doc}.pdf")


def _p(*ids):
    return [{"id_documento": i, "fecha": "2026-06-01", "fase": "MACAO 2",
             "motivo": "falta sello", "cantidad": 7.0} for i in ids]


# ── lectura ──

def test_lee_los_pendientes_ordenados_por_fecha(tmp_path):
    ruta = _bd(tmp_path, [_fila("MB", "2026-06-05"), _fila("MA", "2026-06-01")])
    assert [p["id_documento"] for p in ap.leer_pendientes(ruta)] == ["MA", "MB"]


def test_sin_base_avisa_cual_falta(tmp_path):
    with pytest.raises(FileNotFoundError, match="no existe la base"):
        ap.leer_pendientes(tmp_path / "no-existe.db")


# ── la comparacion, que es el corazon ──

def test_primera_corrida_no_afirma_que_no_hubo_cambios():
    """Sin estado previo no se puede decir "sin cambios": no hay contra que
    comparar. Afirmarlo seria inventar tranquilidad."""
    c = ap.comparar(_p("M1", "M2"), None)
    assert c["primera_vez"] is True
    assert c["nuevos"] == [] and c["resueltos"] == []


def test_detecta_los_nuevos():
    c = ap.comparar(_p("M1", "M2", "M3"), {"fecha": "ayer", "ids": ["M1", "M2"]})
    assert c["nuevos"] == ["M3"] and c["resueltos"] == []


def test_detecta_los_resueltos():
    c = ap.comparar(_p("M1"), {"fecha": "ayer", "ids": ["M1", "M2"]})
    assert c["resueltos"] == ["M2"] and c["nuevos"] == []


def test_un_estado_ilegible_se_trata_como_primera_vez(tmp_path):
    ruta = tmp_path / "estado.json"
    ruta.write_text("{esto no es json", encoding="utf-8")
    assert ap.leer_estado(ruta) is None, (
        "un estado corrupto no puede dar pie a un 'sin cambios' que no se sabe"
    )


# ── el asunto: es lo unico que se lee cuando el correo es diario ──

def test_el_asunto_dice_sin_cambios_cuando_no_cambio_nada():
    c = ap.comparar(_p("M1", "M2"), {"fecha": "ayer", "ids": ["M1", "M2"]})
    assert ap.armar_asunto(_p("M1", "M2"), c) == "2 conduces pendientes por revisar — sin cambios"


def test_el_asunto_pone_los_nuevos_adelante():
    c = ap.comparar(_p("M1", "M2", "M3"), {"fecha": "ayer", "ids": ["M1"]})
    assert ap.armar_asunto(_p("M1", "M2", "M3"), c) == "3 conduces pendientes por revisar — 2 nuevos"


def test_el_asunto_distingue_la_primera_vez():
    assert "primer aviso" in ap.armar_asunto(_p("M1"), ap.comparar(_p("M1"), None))


def test_sin_pendientes_el_asunto_lo_dice_derecho():
    assert ap.armar_asunto([], ap.comparar([], None)) == "Conduces pendientes por revisar: ninguno"


def test_singular_y_plural():
    c = ap.comparar(_p("M1"), {"fecha": "ayer", "ids": ["M1"]})
    assert "1 conduce pendiente por revisar" in ap.armar_asunto(_p("M1"), c)


# ── el cuerpo ──

def test_el_cuerpo_lista_los_nuevos_con_su_numero():
    c = ap.comparar(_p("M1", "M2"), {"fecha": "2026-09-03", "ids": ["M1"]})
    cuerpo = ap.armar_cuerpo(_p("M1", "M2"), c)
    assert "NUEVOS desde el aviso anterior (2026-09-03):" in cuerpo
    assert "M2" in cuerpo


def test_el_cuerpo_agrupa_por_motivo_y_por_fase():
    pend = _p("M1", "M2")
    pend[1]["motivo"] = "falta firma"
    pend[1]["fase"] = "CEDIS"
    cuerpo = ap.armar_cuerpo(pend, ap.comparar(pend, None))
    assert "falta sello" in cuerpo and "falta firma" in cuerpo
    assert "MACAO 2" in cuerpo and "CEDIS" in cuerpo


def test_sin_pendientes_el_cuerpo_no_arma_una_tabla_vacia():
    cuerpo = ap.armar_cuerpo([], ap.comparar([], {"fecha": "ayer", "ids": ["M1"]}))
    assert "No hay conduces pendientes" in cuerpo
    assert "Se resolvieron 1" in cuerpo
    assert "Detalle:" not in cuerpo


# ── el estado ──

def test_guardar_y_releer_el_estado(tmp_path):
    ruta = tmp_path / "estado.json"
    ap.guardar_estado(_p("M2", "M1"), ruta, ahora="2026-09-04 10:00:00")
    leido = json.loads(ruta.read_text(encoding="utf-8"))
    assert leido["ids"] == ["M1", "M2"] and leido["fecha"] == "2026-09-04 10:00:00"
    assert ap.comparar(_p("M1", "M2"), ap.leer_estado(ruta))["nuevos"] == []


# ── el flujo completo ──

def test_si_el_envio_falla_el_estado_NO_se_guarda(tmp_path, monkeypatch, capsys):
    """El caso que mas importa: si se guardara igual, el aviso de manana diria
    "sin cambios" comparando contra un correo que nunca llego, y un pendiente
    nuevo pasaria invisible para siempre."""
    ruta_bd = _bd(tmp_path, [_fila("M1")])
    estado = tmp_path / "estado.json"
    monkeypatch.setattr(ap, "EST_DB_PATH", ruta_bd)
    monkeypatch.setattr(ap, "ESTADO_PATH", estado)
    for k, v in [("SMTP_HOST", "smtp.test"), ("SMTP_USER", "u"),
                 ("SMTP_PASS", "p"), ("MAIL_DESTINATARIOS", "a@b.c")]:
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(ap, "enviar", lambda *a: (_ for _ in ()).throw(OSError("sin red")))
    monkeypatch.setattr(sys, "argv", ["avisar_pendientes.py"])

    assert ap.main() == 1
    assert not estado.exists(), "un envio fallido no puede dejar estado"
    assert "NO SE ENVIO" in capsys.readouterr().out


def test_envio_ok_guarda_el_estado(tmp_path, monkeypatch):
    ruta_bd = _bd(tmp_path, [_fila("M1")])
    estado = tmp_path / "estado.json"
    monkeypatch.setattr(ap, "EST_DB_PATH", ruta_bd)
    monkeypatch.setattr(ap, "ESTADO_PATH", estado)
    for k, v in [("SMTP_HOST", "smtp.test"), ("SMTP_USER", "u"),
                 ("SMTP_PASS", "p"), ("MAIL_DESTINATARIOS", "a@b.c")]:
        monkeypatch.setenv(k, v)
    enviados = []
    # *a: enviar() recibe ahora un cuarto argumento con el HTML
    monkeypatch.setattr(ap, "enviar", lambda *a: enviados.append(a[0]))
    monkeypatch.setattr(sys, "argv", ["avisar_pendientes.py"])

    assert ap.main() == 0
    assert json.loads(estado.read_text(encoding="utf-8"))["ids"] == ["M1"]
    assert len(enviados) == 1


def test_dry_run_no_manda_ni_toca_el_estado(tmp_path, monkeypatch, capsys):
    ruta_bd = _bd(tmp_path, [_fila("M1")])
    estado = tmp_path / "estado.json"
    monkeypatch.setattr(ap, "EST_DB_PATH", ruta_bd)
    monkeypatch.setattr(ap, "ESTADO_PATH", estado)
    monkeypatch.setattr(ap, "enviar", lambda *a: pytest.fail("--dry-run no puede mandar"))
    monkeypatch.setattr(sys, "argv", ["avisar_pendientes.py", "--dry-run"])

    assert ap.main() == 0
    assert not estado.exists()
    assert "no se envio nada" in capsys.readouterr().out


def test_sin_configurar_imprime_el_listado_y_dice_que_falta(tmp_path, monkeypatch, capsys):
    """Degrada mostrando el contenido: el que lo corre a mano igual ve el
    listado, y sabe exactamente que variable le falta."""
    ruta_bd = _bd(tmp_path, [_fila("M1")])
    monkeypatch.setattr(ap, "EST_DB_PATH", ruta_bd)
    monkeypatch.setattr(ap, "ESTADO_PATH", tmp_path / "estado.json")
    for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "MAIL_DESTINATARIOS"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(sys, "argv", ["avisar_pendientes.py"])

    assert ap.main() == 1
    salida = capsys.readouterr().out
    assert "NO SE ENVIO" in salida and "SMTP_HOST" in salida
    assert "M1" in salida, "el listado se imprime igual, no se pierde"


# ── la version HTML ──

def test_el_html_trae_el_numero_y_el_estado():
    c = ap.comparar(_p("M1", "M2"), {"fecha": "2026-09-03", "ids": ["M1", "M2"]})
    h = ap.armar_html(_p("M1", "M2"), c, hoy="04/09/2026")
    assert ">2<" in h and "Sin cambios desde el aviso del 2026-09-03" in h
    assert "04/09/2026" in h


def test_el_html_escapa_lo_que_viene_de_la_base():
    """Los datos traen comillas (`rev. 8\"`) y podrian traer < o &. Sin escapar,
    un dato rompe el maquetado o inyecta etiquetas."""
    pend = _p("M1")
    pend[0]["motivo"] = 'falta sello <b>&"'
    pend[0]["fase"] = "A & B"
    h = ap.armar_html(pend, ap.comparar(pend, None))
    assert "<b>" not in h.split("<body")[1].replace("<br>", ""), "no puede colarse una etiqueta del dato"
    assert "&lt;b&gt;" in h and "A &amp; B" in h


def test_el_html_marca_los_nuevos():
    c = ap.comparar(_p("M1", "M2"), {"fecha": "ayer", "ids": ["M1"]})
    h = ap.armar_html(_p("M1", "M2"), c)
    assert "Nuevos" in h and "M2" in h


def test_el_html_sin_pendientes_no_dibuja_tabla():
    h = ap.armar_html([], ap.comparar([], None))
    assert "No hay conduces pendientes por revisar." in h
    # "Conduce" a secas no sirve de aserto: sale en la cabecera "VMO . Conduces".
    # Lo que no tiene que existir es la tabla, o sea ninguna celda de encabezado.
    assert "<th" not in h


def test_el_html_no_usa_style_ni_recursos_remotos():
    """Gmail y Outlook no respetan CSS externo ni <style> de forma confiable, y
    una imagen REMOTA se bloquea por defecto y deja un hueco. El logo si va,
    pero por Content-ID, o sea dentro del propio correo."""
    h = ap.armar_html(_p("M1"), ap.comparar(_p("M1"), None))
    assert "<style" not in h
    assert "http://" not in h and "https://" not in h
    assert f'src="cid:{ap.LOGO_CID}"' in h, "el logo va por CID, no por URL"


def test_sin_logo_cae_a_la_marca_en_texto():
    """Si el archivo del logo no esta, no puede quedar un <img> roto."""
    h = ap.armar_html(_p("M1"), ap.comparar(_p("M1"), None), con_logo=False)
    assert "<img" not in h
    assert "VMO" in h and "CONCRETOS" in h


def test_el_logo_viaja_adjunto_con_su_content_id(monkeypatch):
    capturado = {}

    class SMTPFalso:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, u, c): pass
        def send_message(self, msg): capturado["msg"] = msg

    monkeypatch.setattr(ap.smtplib, "SMTP", SMTPFalso)
    cfg = {"host": "h", "puerto": 587, "usuario": "u", "clave": "c",
           "remitente": "de@x.com", "destinatarios": ["a@b.c"]}
    ap.enviar("asunto", "texto", cfg, "<html><body>x</body></html>", logo=b"PNG-falso")

    msg = capturado["msg"]
    imagenes = [p for p in msg.walk() if p.get_content_type() == "image/png"]
    assert len(imagenes) == 1
    assert imagenes[0].get("Content-ID") == f"<{ap.LOGO_CID}>"
    assert imagenes[0].get_payload(decode=True) == b"PNG-falso"


def test_el_correo_va_multipart_con_texto_y_html(monkeypatch):
    """El texto plano no es relleno: es lo que ve un cliente que bloquea HTML."""
    capturado = {}

    class SMTPFalso:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, u, c): pass
        def send_message(self, msg): capturado["msg"] = msg

    monkeypatch.setattr(ap.smtplib, "SMTP", SMTPFalso)
    cfg = {"host": "h", "puerto": 587, "usuario": "u", "clave": "c",
           "remitente": "de@x.com", "destinatarios": ["a@b.c"]}
    ap.enviar("asunto", "texto plano", cfg, "<html><body>hola</body></html>")

    msg = capturado["msg"]
    tipos = [p.get_content_type() for p in msg.walk()]
    assert "text/plain" in tipos and "text/html" in tipos
    assert msg.get_body(("plain",)).get_content().strip() == "texto plano"


def test_sin_html_el_correo_sigue_siendo_solo_texto(monkeypatch):
    capturado = {}

    class SMTPFalso:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, u, c): pass
        def send_message(self, msg): capturado["msg"] = msg

    monkeypatch.setattr(ap.smtplib, "SMTP", SMTPFalso)
    cfg = {"host": "h", "puerto": 587, "usuario": "u", "clave": "c",
           "remitente": "de@x.com", "destinatarios": ["a@b.c"]}
    ap.enviar("asunto", "solo texto", cfg)
    assert capturado["msg"].get_content_type() == "text/plain"
