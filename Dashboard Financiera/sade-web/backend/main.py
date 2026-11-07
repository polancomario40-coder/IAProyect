"""
main.py — Punto de entrada de la API FastAPI para SADE Financiera
Sirve tanto los endpoints /api/* como el frontend React compilado (SPA).
"""
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

from database import test_connection
from routers import dashboard, prestamos, clientes, reportes, auth

load_dotenv()

app = FastAPI(
    title="SADE Financiera API",
    description="API Backend para el Dashboard Financiero, Cartera de Clientes e Informes Oficiales de SADE",
    version="2.0.0",
)

origins_raw = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = ["*"] if origins_raw.strip() == "*" else [o.strip() for o in origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(prestamos.router)
app.include_router(clientes.router)
app.include_router(reportes.router)


@app.get("/health", tags=["Health"])
async def health_check():
    ok = test_connection()
    return {
        "status": "ok" if ok else "degraded",
        "database": "conectado" if ok else "desconectado",
    }


# Detectar carpeta del frontend compilado (03_Frontend_SitioWeb o ../frontend/dist)
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_CANDIDATES = [
    BASE_DIR.parent / "03_Frontend_SitioWeb",
    BASE_DIR.parent / "frontend" / "dist",
    BASE_DIR.parent / "PUBLICACION_IIS" / "03_Frontend_SitioWeb",
]
FRONTEND_DIR = next((p for p in FRONTEND_CANDIDATES if (p / "index.html").exists()), None)

if FRONTEND_DIR:
    assets_dir = FRONTEND_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        target = FRONTEND_DIR / full_path
        if full_path and target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(FRONTEND_DIR / "index.html"))
