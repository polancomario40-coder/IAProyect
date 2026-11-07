@echo off
chcp 65001 >nul
title VMO - Estado del Servicio
cd /d "%~dp0"

echo ==========================================================
echo        VMO - ESTADO DEL SERVICIO (Puerto 8000)
echo ==========================================================
echo.

netstat -aon | findstr :8000 | findstr LISTENING
if %errorlevel% equ 0 (
    echo.
    echo [OK] El puerto 8000 est? ACTIVO y ESCUCHANDO.
    echo Probando respuesta HTTP local...
    powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/' -UseBasicParsing -TimeoutSec 5; Write-Host ('[OK] Servidor responde con c?digo HTTP: ' + $r.StatusCode) -ForegroundColor Green } catch { Write-Host ('[AVISO] ' + $_.Exception.Message) -ForegroundColor Yellow }"
) else (
    echo.
    echo [ALERTA] El puerto 8000 NO est? en escucha.
    echo El servicio VMO est? detenido. Ejecute habilitar_servicio.bat para iniciar.
)

echo.
pause
