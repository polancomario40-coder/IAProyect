"""
routers/license.py — Sistema de Protección y Licenciamiento Oficial SADE
Controla la vigencia del software, período de gracia, avisos preventivos y bloqueo total.

Cronograma oficial (contando desde la fecha base 27/11/2026):
  - Días 0 a 5   (hasta 02/12/2026): Operación normal y silenciosa.
  - Días 5 a 10  (02/12 al 07/12/2026): Aviso preventivo en ventana grande (Ámbar).
  - Días 10 a 15 (07/12 al 12/12/2026): Aviso crítico en ventana grande (Rojo).
  - Día 15+      (a partir del 12/12/2026): Bloqueo total (Ventana en Negro) hasta ingresar código válido.
"""
import os
import json
import hmac
import hashlib
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/license", tags=["Licenciamiento"])

# Clave secreta maestra para firma criptográfica HMAC-SHA256
MASTER_LICENSE_SECRET = os.getenv("SADE_LICENSE_SECRET", "SADE-PROPRIETARY-LIC-SECRET-2026-9F82K4M").encode("utf-8")

# Fecha de instalación base (27 de Noviembre de 2026)
FECHA_BASE_DEFAULT = "2026-11-27"

LICENSE_FILE = Path(__file__).resolve().parent.parent / "license_data.json"


class ActivationRequest(BaseModel):
    codigo: str


def _get_storage() -> dict:
    if LICENSE_FILE.exists():
        try:
            with open(LICENSE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception:
            pass
    
    # Inicialización por defecto con fecha base
    init_data = {
        "fechaInstalacion": FECHA_BASE_DEFAULT,
        "ultimoAcceso": FECHA_BASE_DEFAULT,
        "activado": False,
        "codigoActivado": None,
        "tipoLicencia": "TRIAL",
        "expiraEn": None,  # Si está activada, fecha de fin
    }
    _save_storage(init_data)
    return init_data


def _save_storage(data: dict):
    try:
        with open(LICENSE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[!] Error guardando estado de licencia: {e}")


def verify_license_code(code_str: str) -> Optional[dict]:
    """
    Valida un código con formato: SADE-<TIPO>-<FECHA_EXP>-<SIGNATURE>
    Ejemplos:
      SADE-30D-20261227-XXXX
      SADE-1Y-20271127-XXXX
      SADE-PERM-99991231-XXXX
    """
    code_clean = (code_str or "").strip().upper()
    parts = code_clean.split("-")
    if len(parts) != 4 or parts[0] != "SADE":
        return None

    tipo, exp_str, sig = parts[1], parts[2], parts[3]

    # Validar firma HMAC
    payload = f"{tipo}|{exp_str}".encode("utf-8")
    expected_sig = hmac.new(MASTER_LICENSE_SECRET, payload, hashlib.sha256).hexdigest()[:6].upper()

    if not hmac.compare_digest(sig, expected_sig):
        return None

    # Parsear fecha de expiración
    try:
        exp_date = datetime.strptime(exp_str, "%Y%m%d").date()
    except ValueError:
        return None

    return {
        "valido": True,
        "tipo": tipo,
        "expiraEn": exp_date.strftime("%Y-%m-%d"),
        "esPermanente": (tipo == "PERM" or exp_str == "99991231"),
    }


def compute_license_status() -> dict:
    data = _get_storage()
    hoy = date.today()
    hoy_str = hoy.strftime("%Y-%m-%d")

    # Anti-tamper: verificar que no retrasaron el reloj del sistema
    ultimo_acceso = data.get("ultimoAcceso", FECHA_BASE_DEFAULT)
    try:
        ultimo_date = datetime.strptime(ultimo_acceso, "%Y-%m-%d").date()
        if hoy < ultimo_date:
            # Reloj alterado hacia atrás -> Bloqueo preventivo
            return {
                "bloqueado": True,
                "fase": "EXPIRED",
                "color": "BLACK",
                "mensaje": "Se ha detectado una alteración en la fecha y hora del sistema. Ingrese el código de activación para desbloquear.",
                "diasRestantes": 0,
                "diasTranscurridos": 999,
                "activado": False,
                "tipo": "TAMPER_DETECTED"
            }
    except Exception:
        pass

    # Actualizar último acceso
    if hoy_str > ultimo_acceso:
        data["ultimoAcceso"] = hoy_str
        _save_storage(data)

    # 1. Si ya tiene licencia oficial activada
    if data.get("activado"):
        exp_str = data.get("expiraEn")
        tipo = data.get("tipoLicencia", "OFICIAL")

        if tipo == "PERM" or not exp_str or exp_str.startswith("9999"):
            return {
                "bloqueado": False,
                "fase": "ACTIVE_PERMANENT",
                "color": "NONE",
                "mensaje": "Licencia permanente activa",
                "diasRestantes": 99999,
                "diasTranscurridos": 0,
                "activado": True,
                "tipo": "PERMANENTE",
                "expiraEn": "Permanente / Ilimitada"
            }

        try:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
            dias_restantes_lic = (exp_date - hoy).days
            if dias_restantes_lic < 0:
                return {
                    "bloqueado": True,
                    "fase": "EXPIRED",
                    "color": "BLACK",
                    "mensaje": "Su licencia oficial ha expirado. Ingrese un nuevo código para reactivar el sistema.",
                    "diasRestantes": 0,
                    "diasTranscurridos": 0,
                    "activado": False,
                    "tipo": tipo,
                    "expiraEn": exp_str
                }
            elif dias_restantes_lic <= 5:
                return {
                    "bloqueado": False,
                    "fase": "WARNING_RED",
                    "color": "RED",
                    "mensaje": f"Su licencia vencerá en {dias_restantes_lic} días.",
                    "diasRestantes": dias_restantes_lic,
                    "diasTranscurridos": 0,
                    "activado": True,
                    "tipo": tipo,
                    "expiraEn": exp_str
                }
            elif dias_restantes_lic <= 10:
                return {
                    "bloqueado": False,
                    "fase": "WARNING_AMBER",
                    "color": "AMBER",
                    "mensaje": f"Su licencia vencerá en {dias_restantes_lic} días.",
                    "diasRestantes": dias_restantes_lic,
                    "diasTranscurridos": 0,
                    "activado": True,
                    "tipo": tipo,
                    "expiraEn": exp_str
                }
            else:
                return {
                    "bloqueado": False,
                    "fase": "ACTIVE",
                    "color": "NONE",
                    "mensaje": "Licencia activa",
                    "diasRestantes": dias_restantes_lic,
                    "diasTranscurridos": 0,
                    "activado": True,
                    "tipo": tipo,
                    "expiraEn": exp_str
                }
        except Exception:
            pass

    # 2. Período de gracia inicial (Contando desde la fecha base)
    fecha_base_str = data.get("fechaInstalacion", FECHA_BASE_DEFAULT)
    try:
        base_date = datetime.strptime(fecha_base_str, "%Y-%m-%d").date()
    except Exception:
        base_date = datetime.strptime(FECHA_BASE_DEFAULT, "%Y-%m-%d").date()

    dias_transcurridos = (hoy - base_date).days
    if dias_transcurridos < 0:
        dias_transcurridos = 0

    dias_restantes = 15 - dias_transcurridos
    if dias_restantes < 0:
        dias_restantes = 0

    # Clasificación por etapas requeridas:
    # Día 15+: Bloqueo en Negro
    if dias_transcurridos >= 15:
        return {
            "bloqueado": True,
            "fase": "EXPIRED",
            "color": "BLACK",
            "mensaje": "El período de gracia de 15 días ha concluido. El sistema SADE Web se encuentra bloqueado.",
            "diasRestantes": 0,
            "diasTranscurridos": dias_transcurridos,
            "activado": False,
            "tipo": "GRACIA_EXPIRADA",
            "expiraEn": (base_date + timedelta(days=15)).strftime("%Y-%m-%d")
        }

    # Días 10 a 14: Aviso Rojo Crítico
    elif dias_transcurridos >= 10:
        return {
            "bloqueado": False,
            "fase": "WARNING_RED",
            "color": "RED",
            "mensaje": f"¡Atención urgente! Su período de activación vencerá en {dias_restantes} día(s). El sistema se bloqueará definitivamente.",
            "diasRestantes": dias_restantes,
            "diasTranscurridos": dias_transcurridos,
            "activado": False,
            "tipo": "GRACIA_URGENTE",
            "expiraEn": (base_date + timedelta(days=15)).strftime("%Y-%m-%d")
        }

    # Días 5 a 9: Aviso Ámbar Preventivo
    elif dias_transcurridos >= 5:
        return {
            "bloqueado": False,
            "fase": "WARNING_AMBER",
            "color": "AMBER",
            "mensaje": f"Aviso de activación: Restan {dias_restantes} día(s) para registrar la licencia oficial del sistema SADE Web.",
            "diasRestantes": dias_restantes,
            "diasTranscurridos": dias_transcurridos,
            "activado": False,
            "tipo": "GRACIA_PREVENTIVA",
            "expiraEn": (base_date + timedelta(days=15)).strftime("%Y-%m-%d")
        }

    # Días 0 a 4: Operación Normal
    else:
        return {
            "bloqueado": False,
            "fase": "SILENT",
            "color": "NONE",
            "mensaje": "Período regular activo",
            "diasRestantes": dias_restantes,
            "diasTranscurridos": dias_transcurridos,
            "activado": False,
            "tipo": "GRACIA_INICIAL",
            "expiraEn": (base_date + timedelta(days=15)).strftime("%Y-%m-%d")
        }


@router.get("/status")
def get_license_status():
    """Devuelve el estado de licencia actual para el frontend"""
    return compute_license_status()


@router.post("/activate")
def activate_license(req: ActivationRequest):
    """Valida y aplica un código criptográfico de licencia"""
    info = verify_license_code(req.codigo)
    if not info:
        raise HTTPException(
            status_code=400,
            detail="Código de activación no válido o firma incorrecta. Verifique e intente nuevamente."
        )

    data = _get_storage()
    data["activado"] = True
    data["codigoActivado"] = req.codigo.strip().upper()
    data["tipoLicencia"] = info["tipo"]
    data["expiraEn"] = info["expiraEn"]
    _save_storage(data)

    tipo_descr = {
        "30D": "30 días",
        "60D": "60 días",
        "90D": "90 días (3 meses)",
        "180D": "6 meses",
        "1Y": "1 año",
        "PERM": "Permanente / Ilimitada",
    }.get(info["tipo"], info["tipo"])

    return {
        "success": True,
        "mensaje": f"¡Licencia activada con éxito! Tipo: {tipo_descr} (Válida hasta: {info['expiraEn']}).",
        "tipo": info["tipo"],
        "expiraEn": info["expiraEn"],
    }
