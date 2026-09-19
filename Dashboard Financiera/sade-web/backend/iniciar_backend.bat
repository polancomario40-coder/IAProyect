@echo off
title SADE Web Backend API
cd /d "%~dp0"

echo ========================================================
echo   Iniciando Backend API - SADE Web (ERP Financiera)
echo ========================================================
echo.

:: Verificar si existe entorno virtual local
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

:: Iniciar Uvicorn en localhost:8000
%PYTHON_EXE% -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2

pause
