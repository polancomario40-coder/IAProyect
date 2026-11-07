@echo off
cd /d "%~dp0"
title VMO - Actualizacion de Servidor

echo ==========================================================
echo        VMO - APLICAR ACTUALIZACION EN SERVIDOR
echo ==========================================================
echo.

echo [1/4] Deteniendo servicio en puerto 8000 si esta activo...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo Deteniendo proceso previo PID: %%a...
    taskkill /f /pid %%a >nul 2>&1
)

echo.
echo [2/4] Actualizando librerias en el entorno virtual existente (.venv)...
if exist ".venv\Scripts\python.exe" (
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
) else (
    echo [AVISO] Usando python del sistema...
    python -m pip install -r requirements.txt
)

echo.
echo [3/4] Actualizando esquemas de bases de datos existentes...
if exist ".venv\Scripts\python.exe" (
    .\.venv\Scripts\python.exe scripts\setup_db.py
    .\.venv\Scripts\python.exe -c "import core; core.setup_est_db()"
    .\.venv\Scripts\python.exe -c "import core; core.setup_logistica_db()"
    .\.venv\Scripts\python.exe -c "import core; core.setup_comercial_db()"
) else (
    python scripts\setup_db.py
    python -c "import core; core.setup_est_db()"
    python -c "import core; core.setup_logistica_db()"
    python -c "import core; core.setup_comercial_db()"
)

echo.
echo [4/4] Reiniciando servicio VMO en segundo plano...
wscript.exe iniciar_oculto.vbs
timeout /t 3 /nobreak >nul

echo.
echo ==========================================================
echo  Comprobando estado del servicio:
echo ==========================================================
netstat -aon | findstr :8000 | findstr LISTENING >nul
if %errorlevel% equ 0 (
    echo  [OK] Servicio VMO actualizado y funcionando en puerto 8000.
) else (
    echo  [AVISO] Verifique si el servicio inicio correctamente con ver_estado.bat
)
echo ==========================================================
echo.
pause