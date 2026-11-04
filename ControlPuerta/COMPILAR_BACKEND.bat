@echo off
title Compilar Backend Control de Puerta
echo ====================================================================
echo        COMPILANDO BACKEND .NET 8 (ControlPuertaAPI) PARA IIS
echo ====================================================================
cd /d "%~dp0backend"

echo [1/2] Verificando SDK de .NET...
where dotnet >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] No se encontro 'dotnet' en el PATH.
    echo Asegurese de ejecutar este script en el servidor o equipo con .NET 8 SDK instalado.
    echo.
    pause
    exit /b 1
)

echo [2/2] Publicando proyecto en modo Release hacia publish\backend...
dotnet publish ControlPuertaAPI.csproj -c Release -o "..\publish\backend"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ====================================================================
    echo [EXITO] Backend compilado y publicado en ControlPuerta\publish\backend
    echo ====================================================================
) else (
    echo.
    echo [ERROR] Ocurrio un error durante la compilacion.
)

pause
