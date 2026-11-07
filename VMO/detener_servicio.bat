@echo off
chcp 65001 >nul
title VMO - Detener Servicio
cd /d "%~dp0"

echo ==========================================================
echo        VMO - DETENER SERVICIO (Puerto 8000)
echo ==========================================================
echo.

set FOUND=0
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    set FOUND=1
    echo [INFO] Terminando proceso PID: %%a en puerto 8000...
    taskkill /f /pid %%a
)

if "%FOUND%"=="0" (
    echo [INFO] No hab?a ning?n proceso escuchando en el puerto 8000.
) else (
    echo [OK] El servicio VMO ha sido detenido exitosamente.
)

echo.
pause
