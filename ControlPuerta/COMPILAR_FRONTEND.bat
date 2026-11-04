@echo off
title Compilar Frontend ControlPuertaUI
echo ====================================================================
echo        COMPILANDO FRONTEND REACT (ControlPuertaUI) PARA IIS
echo ====================================================================

REM Intentar usar node portable si existe
if exist "%LOCALAPPDATA%\node-portable\node-v20.18.0-win-x64" (
    set "PATH=%LOCALAPPDATA%\node-portable\node-v20.18.0-win-x64;%PATH%"
)

cd /d "%~dp0ControlPuertaUI"

echo [1/3] Verificando Node y NPM...
where npm >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] No se encontro 'npm' ni Node.js.
    pause
    exit /b 1
)

echo [2/3] Compilando produccion con Vite...
call npm run build

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Fallo la compilacion de TypeScript o Vite.
    pause
    exit /b 1
)

echo [3/3] Copiando dist hacia publish\frontend...
if not exist "..\publish\frontend" mkdir "..\publish\frontend"
if not exist "..\publish\frontend\assets" mkdir "..\publish\frontend\assets"

del /q /f "..\publish\frontend\assets\*.*" 2>nul
xcopy /y /e /i "dist\*" "..\publish\frontend\"

echo.
echo ====================================================================
echo [EXITO] Frontend actualizado exitosamente en ControlPuerta\publish\frontend
echo ====================================================================
pause
