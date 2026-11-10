@echo off
chcp 65001 >nul
title VMO - Servidor FastAPI/Uvicorn (Puerto 8000)
cd /d "%~dp0"

echo ==========================================================
echo       VMO - INICIO MANUAL EN CONSOLA (Puerto 8000)
echo ==========================================================
echo.

set "PY_CMD=python"
if exist ".venv\Scripts\python.exe" set "PY_CMD=.\.venv\Scripts\python.exe"

for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo [AVISO] Liberando puerto 8000 del proceso anterior PID: %%a...
    taskkill /f /pid %%a >nul 2>&1
)

echo Iniciando Uvicorn en http://127.0.0.1:8000 usando %PY_CMD%...
echo (Presione Ctrl+C para detener el servidor)
echo.
%PY_CMD% -m uvicorn erp_bridge:app --host 127.0.0.1 --port 8000
pause
