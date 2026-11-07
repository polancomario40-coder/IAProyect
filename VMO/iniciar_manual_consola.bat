@echo off
chcp 65001 >nul
title VMO - Servidor FastAPI/Uvicorn (Puerto 8000)
cd /d "%~dp0"

echo ==========================================================
echo       VMO - INICIO MANUAL EN CONSOLA (Puerto 8000)
echo ==========================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] No se encuentra el entorno virtual .venv.
    echo Ejecute primero instalar_dependencias.bat
    pause
    exit /b 1
)

for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo [AVISO] Liberando puerto 8000 del proceso anterior PID: %%a...
    taskkill /f /pid %%a >nul 2>&1
)

echo Iniciando Uvicorn en http://127.0.0.1:8000...
echo (Presione Ctrl+C para detener el servidor)
echo.
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
