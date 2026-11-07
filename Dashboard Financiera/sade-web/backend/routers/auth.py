"""
routers/auth.py — Autenticación nativa integrada para SADE Web
Valida credenciales directamente contra la base de datos SQL Server local (CBSRepository / segusergrp)
y gestiona empresas asignadas (cfgempresa).
"""
import os
import json
import base64
import hmac
import hashlib
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from database import get_db

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])

JWT_SECRET = os.getenv(
    "JWT_SECRET",
    "super-secret-key-for-jwt-token-generation-that-should-be-long-enough"
).encode("utf-8")


class LoginRequest(BaseModel):
    usuario: str
    clave: str


def encrypt_sade_password(password: str) -> str:
    """Algoritmo de cifrado oficial de SADE (Delphi/C#)"""
    if not password:
        return ""
    c1 = 52845
    c2 = 22719
    key = 2000
    res = bytearray()
    for ch in password:
        b = (ord(ch) ^ (key >> 8)) & 0xFF
        res.append(b)
        key = ((b + key) * c1 + c2) % 65536
    return "".join(f"{b:02X}" for b in res)


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def create_jwt_token(payload: dict) -> str:
    header = b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode("utf-8"))
    payload_copy = {**payload, "iat": int(time.time()), "exp": int(time.time()) + 8 * 3600}
    body = b64url_encode(json.dumps(payload_copy).encode("utf-8"))
    sig = b64url_encode(hmac.new(JWT_SECRET, f"{header}.{body}".encode("utf-8"), hashlib.sha256).digest())
    return f"{header}.{body}.{sig}"


def verify_jwt_token(token: str) -> Optional[dict]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, body, sig = parts
        expected_sig = b64url_encode(hmac.new(JWT_SECRET, f"{header}.{body}".encode("utf-8"), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload = json.loads(b64url_decode(body))
        if payload.get("exp") and payload["exp"] < int(time.time()):
            return None
        return payload
    except Exception:
        return None


@router.post("/login")
async def login(req: LoginRequest):
    usuario_str = req.usuario.strip()
    clave_str = req.clave.strip()

    if not usuario_str or not clave_str:
        raise HTTPException(status_code=400, detail="Debe ingresar usuario y contraseña.")

    with get_db() as conn:
        cur = conn.cursor()

        # 1. Verificar si existe la base de datos CBSRepository en este servidor
        cur.execute("SELECT 1 FROM sys.databases WHERE name = 'CBSRepository'")
        has_cbs = cur.fetchone() is not None

        user_data = None
        empresas = []

        if has_cbs:
            # Buscar usuario en CBSRepository.dbo.segusergrp
            cur.execute("""
                SELECT idSegUserGrp, Nombre, Clave, Encriptada, Activo, Nivel
                FROM CBSRepository.dbo.segusergrp
                WHERE RTRIM(LTRIM(idSegUserGrp)) = ? AND (esGrupo = 0 OR esGrupo IS NULL)
            """, usuario_str)
            row = cur.fetchone()

            if row:
                db_user, nombre, db_clave, encriptada, activo, nivel = row
                if not activo:
                    raise HTTPException(status_code=403, detail="El usuario está inactivo en el sistema.")

                db_clave = (db_clave or "").strip()
                is_valid = False
                if encriptada:
                    is_valid = (db_clave == encrypt_sade_password(clave_str))
                else:
                    is_valid = (db_clave == clave_str)

                if is_valid:
                    user_data = {
                        "username": db_user.strip(),
                        "nombre": (nombre or db_user).strip(),
                        "nivel": nivel or 0,
                    }

                    # Obtener empresas asignadas al usuario
                    cur.execute("""
                        SELECT c.IdEmpresa, c.Empresa, ISNULL(c.RNC, '') AS RNC
                        FROM CBSRepository.dbo.cfgempresa c
                        INNER JOIN CBSRepository.dbo.segusergrpempresa ue ON c.IdEmpresa = ue.idEmpresa
                        WHERE RTRIM(LTRIM(ue.idSegUserGrp)) = ? AND c.Activa = 1
                        ORDER BY c.Empresa
                    """, usuario_str)
                    empresas = [
                        {"idEmpresa": str(r[0]), "empresa": str(r[1]).strip(), "rnc": str(r[2]).strip()}
                        for r in cur.fetchall()
                    ]

                    # Si no tiene empresas específicas asignadas, obtener todas las activas
                    if not empresas:
                        cur.execute("""
                            SELECT TOP 10 IdEmpresa, Empresa, ISNULL(RNC, '') AS RNC
                            FROM CBSRepository.dbo.cfgempresa
                            WHERE Activa = 1
                            ORDER BY Empresa
                        """)
                        empresas = [
                            {"idEmpresa": str(r[0]), "empresa": str(r[1]).strip(), "rnc": str(r[2]).strip()}
                            for r in cur.fetchall()
                        ]

        # 2. Si no se encontró en CBSRepository o no existe CBSRepository (fallback de emergencia)
        if not user_data:
            if usuario_str.lower() in ("admin", "sade") and clave_str in ("admin", "123", "sade", "123456"):
                user_data = {"username": usuario_str, "nombre": "Administrador Local", "nivel": 1}
                empresas = [{"idEmpresa": "01", "empresa": "SADE Financiera", "rnc": ""}]
            else:
                raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")

        # Si aún no hay empresas, proveer la empresa por defecto
        if not empresas:
            empresas = [{"idEmpresa": "01", "empresa": "SADE Financiera", "rnc": ""}]

        token = create_jwt_token({
            "sub": user_data["username"],
            "nombre": user_data["nombre"],
            "unique_name": user_data["username"],
        })

        return {
            "success": True,
            "token": token,
            "usuario": user_data,
            "empresas": empresas,
        }


@router.get("/me")
async def get_me(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token no suministrado.")
    token = authorization.split(" ")[1]
    payload = verify_jwt_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado.")
    return {"success": True, "usuario": payload}
