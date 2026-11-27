#!/usr/bin/env python3
"""
generador_licencias.py — Generador Oficial de Códigos de Activación SADE Web
Uso interno exclusivo del Desarrollador / Propietario del Software.

Genera códigos criptográficos con firma HMAC-SHA256 válidos para desbloquear
o renovar el sistema SADE Web instalado en los clientes.
"""
import hmac
import hashlib
from datetime import datetime, date, timedelta

MASTER_SECRET = b"SADE-PROPRIETARY-LIC-SECRET-2026-9F82K4M"


def generar_codigo(tipo: str, exp_date: date) -> str:
    exp_str = exp_date.strftime("%Y%m%d")
    payload = f"{tipo}|{exp_str}".encode("utf-8")
    sig = hmac.new(MASTER_SECRET, payload, hashlib.sha256).hexdigest()[:6].upper()
    return f"SADE-{tipo}-{exp_str}-{sig}"


def imprimir_tabla_codigos():
    hoy = date.today()
    print("=" * 72)
    print("      GENERADOR DE CÓDIGOS DE ACTIVACIÓN OFICIALES — SADE WEB")
    print(f"      Fecha de Emisión: {hoy.strftime('%d/%m/%Y')}")
    print("=" * 72)
    print()

    planes = [
        ("30D", "30 Días (1 Mes)", hoy + timedelta(days=30)),
        ("60D", "60 Días (2 Meses)", hoy + timedelta(days=60)),
        ("90D", "90 Días (3 Meses)", hoy + timedelta(days=90)),
        ("180D", "180 Días (6 Meses)", hoy + timedelta(days=180)),
        ("1Y", "1 Año Completo", hoy + timedelta(days=365)),
        ("PERM", "Permanente / Vitalicia", date(9999, 12, 31)),
    ]

    print(f"{'DURACIÓN':<25} {'VENCE EL':<14} {'CÓDIGO DE ACTIVACIÓN OFICIAL'}")
    print("-" * 72)
    for tipo, descr, exp in planes:
        code = generar_codigo(tipo, exp)
        exp_str = "Vitalicia" if exp.year == 9999 else exp.strftime("%d/%m/%Y")
        print(f"{descr:<25} {exp_str:<14} {code}")
    print("-" * 72)
    print()
    print("Guarde estos códigos en su archivo privado de control de clientes.")
    print("Cuando el cliente realice el pago, proporciónale el código correspondiente.")
    print("=" * 72)


if __name__ == "__main__":
    imprimir_tabla_codigos()
