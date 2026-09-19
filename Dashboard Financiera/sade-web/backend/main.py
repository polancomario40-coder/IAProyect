"""
main.py — Entry point de la API SADE Web (FastAPI)

Arranque:
    uvicorn main:app --reload --port 8000

Docs interactivas: http://localhost:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import settings
from routers import dashboard, prestamos, clientes

# ─── Aplicación ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="SADE Web API — Cartera de Préstamos",
    description=(
        "API REST para el módulo de Cuentas por Cobrar (CXC) del ERP SADE.\n\n"
        "Conecta con la base de datos **Financiera** en SQL Server y expone:\n"
        "- Dashboard con KPIs de la cartera activa\n"
        "- Estado detallado de cada préstamo (cuotas, pagos, balances)"
    ),
    version="1.0.0",
    contact={"name": "Desarrollo SADE"},
    license_info={"name": "Privado"},
)

# ─── CORS ─────────────────────────────────────────────────────────────────────
origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET"],          # Solo lectura por ahora
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(dashboard.router)
app.include_router(prestamos.router)
app.include_router(clientes.router)


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "ok",
        "app": "SADE Web API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Verifica la conexión a la base de datos."""
    try:
        from database import execute_sp
        execute_sp("cxcDashboardKPIs")
        return {"status": "ok", "database": "conectado"}
    except Exception as e:
        return {"status": "error", "database": str(e)}
