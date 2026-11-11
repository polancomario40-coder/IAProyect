@echo off
chcp 65001 >nul
cd /d "%~dp0"
title VMO - Instalar Servicio Persistente 24/7 (Independiente de RDP)

echo ==========================================================
echo    VMO - INSTALAR SERVICIO PERSISTENTE 24/7 EN WINDOWS
echo ==========================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar_servicio_persistente.ps1"

echo.
echo ==========================================================
echo Presione cualquier tecla para cerrar esta ventana...
pause >nul
