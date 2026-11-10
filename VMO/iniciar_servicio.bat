@echo off
chcp 65001 >nul
cd /d "%~dp0"
title VMO - Servidor Backend (Puerto 8000)

echo ==========================================================
echo        VMO - SERVIDOR FASTAPI / UVICORN (Puerto 8000)
echo ==========================================================
echo.

set "PY_CMD=python"
if exist ".venv\Scripts\python.exe" set "PY_CMD=.\.venv\Scripts\python.exe"

for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo [AVISO] Liberando puerto 8000 del proceso anterior PID: %%a...
    taskkill /f /pid %%a >nul 2>&1
)

echo Iniciando Uvicorn en http://127.0.0.1:8000 usando %PY_CMD%...
%PY_CMD% run_server.py
if %errorlevel% neq 0 (
    echo.
    echo ==========================================================
    echo [ERROR] El servidor se detuvo con codigo %errorlevel%.
    echo Revise el mensaje de error anterior.
    echo ==========================================================
    pause
)
