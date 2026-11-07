@echo off
chcp 65001 >nul
title VMO - Habilitar Servicio (Puerto 8000)
cd /d "%~dp0"

echo ==========================================================
echo        VMO - HABILITAR SERVICIO EN SEGUNDO PLANO
echo ==========================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] No se encuentra el entorno virtual .venv.
    echo Ejecutando instalaci?n autom?tica de dependencias...
    call instalar_dependencias.bat
    if errorlevel 1 (
        echo [ERROR] Fall? la instalaci?n.
        pause
        exit /b 1
    )
)

REM Liberar puerto si ya estaba ocupado
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo [INFO] Deteniendo proceso previo en puerto 8000 (PID: %%a)...
    taskkill /f /pid %%a >nul 2>&1
)

echo [INFO] Iniciando Uvicorn en segundo plano...
wscript.exe iniciar_oculto.vbs

REM Esperar 3 segundos para que inicie
timeout /t 3 /nobreak >nul

echo.
echo ==========================================================
echo  Comprobando estado del servicio:
echo ==========================================================
netstat -aon | findstr :8000 | findstr LISTENING >nul
if %errorlevel% equ 0 (
    echo  [OK] Servicio iniciado y escuchando en:
    echo       http://127.0.0.1:8000
    echo.
    echo  IIS (Reverse Proxy) ahora reenv?a el tr?fico a este puerto.
) else (
    echo  [ERROR] El servicio no parece haber iniciado.
    echo  Ejecute iniciar_manual_consola.bat para ver los mensajes de error.
)
echo ==========================================================
echo.
pause
