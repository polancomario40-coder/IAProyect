# by a_oller
"""
avisar_pendientes.py — Manda por correo el listado de conduces pendientes por revisar.

Pensado para correr una vez al dia con el Programador de Tareas de Windows, igual
que backup_db.py.

**El asunto lleva la senal, no solo el numero.** Al 2026-09-04 los 39 pendientes
son todos `falta sello`, todos de MACAO 2, y no se mueven desde el 2026-08-20. Un
correo diario identico se vuelve ruido y se filtra en una semana — y el dia que
aparezca uno nuevo, ya nadie lo abre. Por eso cada envio compara contra el anterior
y dice en el asunto si entraron o se resolvieron pendientes, o si no cambio nada.

El estado del envio anterior vive en `estimaciones/data/pendientes_ultimo_envio.json`.
Si no existe (primera corrida), el correo lo dice en vez de inventar un "sin cambios"
que no puede saber.

Configuracion, toda por .env — sin ella el script NO manda nada y explica que falta:

    SMTP_HOST           servidor (ej. smtp.gmail.com)
    SMTP_PORT           puerto (587 STARTTLS, 465 SSL). Default 587
    SMTP_USER           usuario
    SMTP_PASS           contrasena (en Gmail, una contrasena de aplicacion)
    MAIL_REMITENTE      de quien sale. Default: SMTP_USER
    MAIL_DESTINATARIOS  a quienes va, separados por coma

Uso:
    python scripts/avisar_pendientes.py              # calcula y manda
    python scripts/avisar_pendientes.py --dry-run    # lo imprime y NO manda
                                                     # (no toca el estado guardado)
"""

import base64
import html
import json
import os
import smtplib
import sqlite3
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

EST_DB_PATH = BASE_DIR / "estimaciones" / "db" / "estimaciones.db"
ESTADO_PATH = BASE_DIR / "estimaciones" / "data" / "pendientes_ultimo_envio.json"


def leer_pendientes(db_path=None):
    """Los pendientes por revisar, ordenados por fecha del conduce."""
    ruta = Path(db_path or EST_DB_PATH)
    if not ruta.exists():
        raise FileNotFoundError(f"no existe la base {ruta}")
    con = sqlite3.connect(f"file:{ruta.as_posix()}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        filas = con.execute(
            "SELECT id_documento, fecha, empresa, fase, motivo, cantidad, "
            "descripcion, archivo_pdf FROM pendientes_revision "
            "ORDER BY fecha, id_documento"
        ).fetchall()
        return [dict(f) for f in filas]
    finally:
        con.close()


def leer_estado(ruta=None):
    ruta = Path(ruta or ESTADO_PATH)
    if not ruta.exists():
        return None
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # un estado ilegible es lo mismo que no tenerlo: se avisa "primera
        # corrida" en vez de mentir un "sin cambios" que no se puede saber
        return None


def guardar_estado(pendientes, ruta=None, ahora=None):
    ruta = Path(ruta or ESTADO_PATH)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps({
        "fecha": ahora or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ids": sorted(p["id_documento"] for p in pendientes),
    }, indent=2), encoding="utf-8")


def comparar(pendientes, estado):
    """Que entro y que se resolvio desde el envio anterior.

    Con `estado` en None (primera corrida, o archivo ilegible) devuelve
    `primera_vez`: no se puede afirmar que no hubo cambios cuando no hay contra
    que comparar.
    """
    ids = {p["id_documento"] for p in pendientes}
    if estado is None:
        return {"primera_vez": True, "nuevos": [], "resueltos": [], "desde": None}
    previos = set(estado.get("ids", []))
    return {
        "primera_vez": False,
        "nuevos": sorted(ids - previos),
        "resueltos": sorted(previos - ids),
        "desde": estado.get("fecha"),
    }


def armar_asunto(pendientes, cambios):
    n = len(pendientes)
    if n == 0:
        return "Conduces pendientes por revisar: ninguno"
    base = f"{n} conduce{'s' if n != 1 else ''} pendiente{'s' if n != 1 else ''} por revisar"
    if cambios["primera_vez"]:
        return f"{base} (primer aviso)"
    partes = []
    if cambios["nuevos"]:
        partes.append(f"{len(cambios['nuevos'])} nuevo{'s' if len(cambios['nuevos']) != 1 else ''}")
    if cambios["resueltos"]:
        partes.append(f"{len(cambios['resueltos'])} resuelto{'s' if len(cambios['resueltos']) != 1 else ''}")
    if not partes:
        return f"{base} — sin cambios"
    return f"{base} — {', '.join(partes)}"


def _agrupar(pendientes, campo):
    conteo = {}
    for p in pendientes:
        conteo[p.get(campo) or "(sin dato)"] = conteo.get(p.get(campo) or "(sin dato)", 0) + 1
    return sorted(conteo.items(), key=lambda kv: (-kv[1], kv[0]))


def armar_cuerpo(pendientes, cambios):
    """El cuerpo en texto plano. Sin HTML a proposito: se lee en cualquier
    cliente, no se rompe, y el contenido es una lista."""
    L = []
    if not pendientes:
        L.append("No hay conduces pendientes por revisar.")
        if cambios["resueltos"]:
            L.append("")
            L.append(f"Se resolvieron {len(cambios['resueltos'])} desde el aviso anterior:")
            L += [f"  {i}" for i in cambios["resueltos"]]
        return "\n".join(L) + "\n"

    L.append(f"{len(pendientes)} conduce(s) pendiente(s) por revisar.")
    L.append("")

    if cambios["primera_vez"]:
        L.append("Primer aviso: no hay envio anterior contra el cual comparar,")
        L.append("asi que no se puede decir que cambio desde ayer.")
        L.append("")
    else:
        if cambios["nuevos"]:
            L.append(f"NUEVOS desde el aviso anterior ({cambios['desde']}):")
            L += [f"  {i}" for i in cambios["nuevos"]]
            L.append("")
        if cambios["resueltos"]:
            L.append("RESUELTOS desde el aviso anterior:")
            L += [f"  {i}" for i in cambios["resueltos"]]
            L.append("")
        if not cambios["nuevos"] and not cambios["resueltos"]:
            L.append(f"Sin cambios desde el aviso anterior ({cambios['desde']}).")
            L.append("")

    L.append("Por motivo:")
    L += [f"  {m:<24} {n}" for m, n in _agrupar(pendientes, "motivo")]
    L.append("")
    L.append("Por fase:")
    L += [f"  {f:<24} {n}" for f, n in _agrupar(pendientes, "fase")]
    L.append("")

    fechas = [p["fecha"] for p in pendientes if p.get("fecha")]
    if fechas:
        L.append(f"Fechas de los conduces: {min(fechas)} a {max(fechas)}")
        L.append("")

    L.append("Detalle:")
    L.append(f"  {'CONDUCE':<14} {'FECHA':<12} {'FASE':<14} {'CANT':>7}  MOTIVO")
    for p in pendientes:
        cant = f"{p['cantidad']:.2f}" if p.get("cantidad") is not None else "-"
        L.append(f"  {p['id_documento']:<14} {p.get('fecha') or '-':<12} "
                 f"{(p.get('fase') or '-')[:14]:<14} {cant:>7}  {p.get('motivo') or '-'}")
    L.append("")
    L.append("Se aprueban o descartan desde el panel 'Pendientes por Revision'.")
    L.append("Aviso automatico de avisar_pendientes.py — no se responde.")
    return "\n".join(L) + "\n"


LOGO_PATH = BASE_DIR / "static" / "logo.png"
LOGO_CID = "logovmo"

# Paleta sacada del propio logo: el rojo es el que usa la marca.
C_MARCA = "#ec4035"
C_TINTA = "#16181d"
C_SUAVE = "#6b7280"
C_BORDE = "#e2e5ea"
C_PAGINA = "#eef0f3"
C_PANEL = "#f7f8fa"
C_TARJETA = "#ffffff"
C_RESUELTO = "#047857"

_FUENTE = ("-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif")
_MONO = "'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace"


def armar_html(pendientes, cambios, hoy=None, con_logo=True):
    """La version HTML del aviso. El texto plano de armar_cuerpo() sigue yendo
    como alternativa, asi que un cliente que no renderice HTML no se queda sin
    el contenido.

    Todo con estilos EN LINEA y maquetado con <table>: es lo unico que Gmail y
    Outlook respetan de forma confiable. Sin <style> en el head y sin CSS
    externo.

    **Nada de texto suelto sobre el fondo**: cada bloque —el numero, los
    resumenes, la tabla, el pie— vive en un panel con fondo y borde propios.
    Ademas los fondos van explicitos en cada celda para que el modo oscuro de
    algunos clientes no invierta la mitad y deje gris sobre gris.

    El logo va como adjunto CID (`cid:logovmo`), no como URL: una imagen remota
    se bloquea por defecto y deja un hueco. Con `con_logo=False` cae a la marca
    en texto, que es lo que corresponde si el archivo no esta.
    """
    hoy = hoy or datetime.now().strftime("%d/%m/%Y")
    n = len(pendientes)

    def esc(v):
        return html.escape("" if v is None else str(v))

    def panel(contenido, relleno="18px 20px", fondo=C_PANEL, borde=C_BORDE):
        return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                f'style="background:{fondo};border:1px solid {borde};border-radius:8px;">'
                f'<tr><td style="padding:{relleno};">{contenido}</td></tr></table>')

    def rotulo(t):
        return (f'<div style="font-size:11px;color:{C_SUAVE};text-transform:uppercase;'
                f'letter-spacing:.8px;font-weight:700;padding-bottom:8px;">{t}</div>')

    # ── la linea de estado: es lo primero que se mira ──
    if cambios["primera_vez"]:
        estado_txt, estado_color, estado_fondo = (
            "Primer aviso — no hay envío anterior con el que comparar", C_SUAVE, "#eceef1")
    elif cambios["nuevos"] or cambios["resueltos"]:
        trozos = []
        if cambios["nuevos"]:
            trozos.append(f"{len(cambios['nuevos'])} nuevo(s)")
        if cambios["resueltos"]:
            trozos.append(f"{len(cambios['resueltos'])} resuelto(s)")
        estado_txt = " · ".join(trozos) + f" desde el aviso del {esc(cambios['desde'])}"
        if cambios["nuevos"]:
            estado_color, estado_fondo = C_MARCA, "#fdecea"
        else:
            estado_color, estado_fondo = C_RESUELTO, "#e7f5f0"
    else:
        estado_txt, estado_color, estado_fondo = (
            f"Sin cambios desde el aviso del {esc(cambios['desde'])}", C_SUAVE, "#eceef1")

    P = []
    P.append(f'<!doctype html><html><body style="margin:0;padding:0;'
             f'background:{C_PAGINA};font-family:{_FUENTE};color:{C_TINTA};">')
    P.append(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
             f'style="background:{C_PAGINA};padding:28px 12px;"><tr><td align="center">')
    P.append(f'<table role="presentation" width="640" cellpadding="0" cellspacing="0" '
             f'style="width:640px;max-width:100%;background:{C_TARJETA};'
             f'border:1px solid {C_BORDE};border-radius:12px;overflow:hidden;">')

    # ── cabecera: el logo vive sobre blanco, que es su fondo ──
    marca = (f'<img src="cid:{LOGO_CID}" width="132" alt="VMO Concretos" '
             f'style="display:block;width:132px;height:auto;border:0;">'
             if con_logo else
             f'<div style="font-size:20px;font-weight:800;letter-spacing:-.5px;">'
             f'VMO<span style="color:{C_MARCA};">.</span>'
             f'<span style="font-weight:400;color:{C_SUAVE};font-size:13px;'
             f'padding-left:6px;">CONCRETOS</span></div>')
    P.append(f'<tr><td style="background:{C_TARJETA};padding:22px 24px 18px 24px;">'
             f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
             f'<td valign="middle">{marca}</td>'
             f'<td valign="middle" align="right" style="font-size:12px;color:{C_SUAVE};">'
             f'{esc(hoy)}</td></tr></table></td></tr>')
    P.append(f'<tr><td style="background:{C_MARCA};font-size:0;line-height:0;height:4px;">'
             f'&nbsp;</td></tr>')
    P.append(f'<tr><td style="background:{C_PANEL};padding:16px 24px;'
             f'border-bottom:1px solid {C_BORDE};">'
             f'<div style="font-size:17px;font-weight:700;">Conduces pendientes por revisar</div>'
             f'</td></tr>')

    if n == 0:
        P.append(f'<tr><td style="padding:24px;">' + panel(
            f'<div style="font-size:16px;font-weight:600;">No hay conduces pendientes por revisar.</div>'
            + (f'<div style="color:{C_RESUELTO};font-size:13px;padding-top:6px;">'
               f'Se resolvieron {len(cambios["resueltos"])} desde el aviso anterior.</div>'
               if cambios["resueltos"] else ""),
            fondo="#e7f5f0", borde="#bfe3d6") + '</td></tr>')
    else:
        # ── el numero, adentro de un panel ──
        P.append(f'<tr><td style="padding:24px 24px 0 24px;">' + panel(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
            f'<td valign="middle" style="width:1%;white-space:nowrap;padding-right:16px;">'
            f'<span style="font-size:44px;font-weight:800;line-height:1;color:{C_TINTA};">{n}</span>'
            f'</td><td valign="middle">'
            f'<div style="font-size:14px;color:{C_SUAVE};padding-bottom:6px;">'
            f'conduce{"s" if n != 1 else ""} esperando revisión</div>'
            f'<span style="display:inline-block;background:{estado_fondo};color:{estado_color};'
            f'font-size:12px;font-weight:700;border-radius:20px;padding:5px 12px;">'
            f'{estado_txt}</span></td></tr></table>') + '</td></tr>')

        # ── los nuevos, en su propio panel tintado ──
        if cambios["nuevos"]:
            chips = " ".join(
                f'<span style="display:inline-block;font-family:{_MONO};font-size:12px;'
                f'background:{C_TARJETA};color:{C_MARCA};border:1px solid #f5b8b2;'
                f'border-radius:4px;padding:4px 8px;margin:0 5px 5px 0;">{esc(i)}</span>'
                for i in cambios["nuevos"])
            P.append(f'<tr><td style="padding:14px 24px 0 24px;">'
                     + panel(rotulo("Nuevos desde el aviso anterior") + chips,
                             fondo="#fdecea", borde="#f5b8b2") + '</td></tr>')

        # ── resumenes, dos tarjetas ──
        def tarjeta(titulo, filas):
            cuerpo = "".join(
                f'<tr><td style="font-size:13px;padding:4px 0;color:{C_TINTA};">{esc(k)}</td>'
                f'<td align="right" style="font-size:13px;padding:4px 0;font-weight:700;">{v}</td></tr>'
                for k, v in filas)
            return panel(rotulo(titulo) +
                         f'<table role="presentation" width="100%" cellpadding="0" '
                         f'cellspacing="0">{cuerpo}</table>', relleno="14px 16px")

        P.append(f'<tr><td style="padding:14px 24px 0 24px;">'
                 f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
                 f'<td valign="top" width="50%" style="padding-right:7px;">'
                 + tarjeta("Por motivo", _agrupar(pendientes, "motivo")) + '</td>'
                 f'<td valign="top" width="50%" style="padding-left:7px;">'
                 + tarjeta("Por fase", _agrupar(pendientes, "fase")) + '</td>'
                 '</tr></table></td></tr>')

        fechas = [p["fecha"] for p in pendientes if p.get("fecha")]
        if fechas:
            P.append(f'<tr><td style="padding:14px 24px 0 24px;">'
                     + panel(f'<span style="font-size:12px;color:{C_SUAVE};">Fechas de los '
                             f'conduces</span> &nbsp; <strong style="font-size:13px;">'
                             f'{esc(min(fechas))} &nbsp;→&nbsp; {esc(max(fechas))}</strong>',
                             relleno="12px 16px") + '</td></tr>')

        # ── el detalle, con marco y encabezado con fondo ──
        nuevos = set(cambios["nuevos"])
        filas = []
        for i, p in enumerate(pendientes):
            fondo = C_TARJETA if i % 2 == 0 else "#fafbfc"
            marca_n = (f'<span style="color:{C_MARCA};font-weight:800;">&#9679;</span>&nbsp;'
                       if p["id_documento"] in nuevos else "")
            cant = f"{p['cantidad']:.2f}" if p.get("cantidad") is not None else "—"
            filas.append(
                f'<tr style="background:{fondo};">'
                f'<td style="padding:8px 12px;font-family:{_MONO};font-size:12px;'
                f'border-top:1px solid {C_BORDE};white-space:nowrap;">{marca_n}{esc(p["id_documento"])}</td>'
                f'<td style="padding:8px 12px;font-size:12px;color:{C_SUAVE};'
                f'border-top:1px solid {C_BORDE};white-space:nowrap;">{esc(p.get("fecha"))}</td>'
                f'<td style="padding:8px 12px;font-size:12px;border-top:1px solid {C_BORDE};">'
                f'{esc(p.get("fase"))}</td>'
                f'<td align="right" style="padding:8px 12px;font-family:{_MONO};font-size:12px;'
                f'font-weight:700;border-top:1px solid {C_BORDE};white-space:nowrap;">{cant}</td>'
                f'<td style="padding:8px 12px;font-size:12px;color:{C_SUAVE};'
                f'border-top:1px solid {C_BORDE};">{esc(p.get("motivo"))}</td></tr>')

        encabezados = "".join(
            f'<th align="{a}" style="background:{C_PANEL};padding:9px 12px;font-size:11px;'
            f'color:{C_SUAVE};text-transform:uppercase;letter-spacing:.7px;font-weight:700;">'
            f'{t}</th>'
            for t, a in (("Conduce", "left"), ("Fecha", "left"), ("Fase", "left"),
                         ("Cant.", "right"), ("Motivo", "left")))
        P.append(f'<tr><td style="padding:18px 24px 0 24px;">'
                 f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                 f'style="border-collapse:collapse;border:1px solid {C_BORDE};'
                 f'border-radius:8px;overflow:hidden;">'
                 f'<tr>{encabezados}</tr>{"".join(filas)}</table></td></tr>')

    # ── pie, con su propia banda ──
    P.append(f'<tr><td style="padding:22px 24px 0 24px;"></td></tr>')
    P.append(f'<tr><td style="background:{C_PANEL};border-top:1px solid {C_BORDE};'
             f'padding:16px 24px;font-size:12px;color:{C_SUAVE};line-height:1.6;">'
             f'Se aprueban o descartan desde el panel <strong style="color:{C_TINTA};">'
             f'Pendientes por Revisión</strong>.<br>'
             f'Aviso automático — no hace falta responder a este correo.</td></tr>')
    P.append('</table></td></tr></table></body></html>')
    return "".join(P)


def _config_smtp():
    """La config de envio, o (None, que falta)."""
    faltan = [k for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "MAIL_DESTINATARIOS")
              if not os.getenv(k)]
    if faltan:
        return None, faltan
    destinatarios = [d.strip() for d in os.getenv("MAIL_DESTINATARIOS", "").split(",") if d.strip()]
    if not destinatarios:
        return None, ["MAIL_DESTINATARIOS"]
    return {
        "host": os.getenv("SMTP_HOST"),
        "puerto": int(os.getenv("SMTP_PORT", "587")),
        "usuario": os.getenv("SMTP_USER"),
        "clave": os.getenv("SMTP_PASS"),
        "remitente": os.getenv("MAIL_REMITENTE") or os.getenv("SMTP_USER"),
        "destinatarios": destinatarios,
    }, []


def enviar(asunto, cuerpo, cfg, cuerpo_html=None, logo=None):
    """Manda el aviso. Con `cuerpo_html` va multipart/alternative: el cliente
    muestra el HTML si puede y cae al texto plano si no. El texto plano NO es
    un relleno — es lo que ven los clientes que bloquean HTML y lo que queda
    legible si el maquetado se rompe."""
    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = cfg["remitente"]
    msg["To"] = ", ".join(cfg["destinatarios"])
    msg.set_content(cuerpo)
    if cuerpo_html:
        msg.add_alternative(cuerpo_html, subtype="html")
        # El logo va DENTRO del correo, con Content-ID, no como URL: una imagen
        # remota la bloquea el cliente por defecto y deja un hueco. Si el
        # archivo no esta, el HTML ya vino con la marca en texto (con_logo).
        if logo:
            msg.get_payload()[1].add_related(
                logo, maintype="image", subtype="png", cid=f"<{LOGO_CID}>")

    if cfg["puerto"] == 465:
        with smtplib.SMTP_SSL(cfg["host"], cfg["puerto"], timeout=30) as s:
            s.login(cfg["usuario"], cfg["clave"])
            s.send_message(msg)
    else:
        with smtplib.SMTP(cfg["host"], cfg["puerto"], timeout=30) as s:
            s.starttls()
            s.login(cfg["usuario"], cfg["clave"])
            s.send_message(msg)


def main():
    seco = "--dry-run" in sys.argv

    pendientes = leer_pendientes()
    cambios = comparar(pendientes, leer_estado())
    asunto = armar_asunto(pendientes, cambios)
    cuerpo = armar_cuerpo(pendientes, cambios)
    logo = None
    if LOGO_PATH.exists():
        try:
            logo = LOGO_PATH.read_bytes()
        except OSError as e:
            print(f"(no se pudo leer el logo, va la marca en texto: {e})")
    cuerpo_html = armar_html(pendientes, cambios, con_logo=logo is not None)

    if seco:
        print(f"Asunto: {asunto}\n")
        print(cuerpo)
        salida_html = BASE_DIR / "dropoff" / "aviso_pendientes_preview.html"
        try:
            salida_html.parent.mkdir(parents=True, exist_ok=True)
            # En el correo el logo va por Content-ID, que un navegador no
            # resuelve. Solo para la muestra se cambia por un data: URI, asi
            # lo que se ve en el navegador es lo mismo que llega al buzon.
            muestra = cuerpo_html
            if logo:
                b64 = base64.b64encode(logo).decode("ascii")
                muestra = muestra.replace(f"cid:{LOGO_CID}",
                                          f"data:image/png;base64,{b64}")
            salida_html.write_text(muestra, encoding="utf-8")
            print(f"HTML de muestra escrito en: {salida_html}")
        except OSError as e:
            print(f"(no se pudo escribir la muestra HTML: {e})")
        print("(--dry-run: no se envio nada y el estado guardado no se toco)")
        return 0

    cfg, faltan = _config_smtp()
    if cfg is None:
        print(f"Asunto: {asunto}\n")
        print(cuerpo)
        print(f"NO SE ENVIO: falta configurar en .env -> {', '.join(faltan)}")
        print("El listado de arriba es el que se habria mandado.")
        return 1

    try:
        enviar(asunto, cuerpo, cfg, cuerpo_html, logo)
    except Exception as e:
        # Sale con 1 y NO guarda el estado: si se guardara, el aviso de manana
        # diria "sin cambios" comparando contra un envio que nunca llego.
        print(f"NO SE ENVIO: fallo el correo ({type(e).__name__}: {e})")
        return 1

    guardar_estado(pendientes)
    print(f"Enviado a {', '.join(cfg['destinatarios'])}: {asunto}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
