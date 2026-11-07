@echo off
title SADE Web - Servidor API y Aplicacion Web
cd /d "%~dp0"
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8080
) else if exist "%LOCALAPPDATA%\sade-web-runtime\venv\Scripts\python.exe" (
    "%LOCALAPPDATA%\sade-web-runtime\venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8080
) else (
    python -m uvicorn main:app --host 0.0.0.0 --port 8080
)