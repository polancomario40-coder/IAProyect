@echo off
title Publicacion Completa Control de Puerta a IIS
echo ====================================================================
echo      PUBLICACION COMPLETA: CONTROL DE PUERTA (FRONTEND + BACKEND)
echo ====================================================================

call "%~dp0COMPILAR_FRONTEND.bat"
call "%~dp0COMPILAR_BACKEND.bat"

echo.
echo ====================================================================
echo Proceso finalizado. Revise la carpeta ControlPuerta\publish
echo ====================================================================
pause
