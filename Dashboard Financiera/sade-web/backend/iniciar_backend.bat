@echo off
title SADE Web - Servidor Backend API (Puerto 8000)
cd /d "%~dp0"
echo ==========================================================
echo    INICIANDO SERVICIO BACKEND FASTAPI (PUERTO 8000)
echo ==========================================================
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000
) else if exist "%LOCALAPPDATA%\sade-web-runtime\venv\Scripts\python.exe" (
    "%LOCALAPPDATA%\sade-web-runtime\venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000
) else (
    python -m uvicorn main:app --host 0.0.0.0 --port 8000
)
