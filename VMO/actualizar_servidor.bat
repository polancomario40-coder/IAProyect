@echo off
cd /d "%~dp0"
title VMO - Actualizacion de Servidor (SSO Auth-Center + Conexion Directa ERP cbsvmo)

echo ==========================================================
echo        VMO - APLICAR ACTUALIZACION EN SERVIDOR IIS
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
    .\.venv\Scripts\python.exe -m pip install pyodbc >nul 2>&1
) else (
    echo [AVISO] Usando python del sistema...
    python -m pip install -r requirements.txt
    python -m pip install pyodbc >nul 2>&1
)

if exist ".env" (
    findstr /i "ERP_SQL_DB" ".env" >nul 2>&1
    if errorlevel 1 (
        echo.>> ".env"
        echo # Conexion ERP SQL Server ^(cbsvmo^)>> ".env"
        echo ERP_SQL_SERVER=vmo.ddns.net,1440>> ".env"
        echo ERP_SQL_DB=cbsvmo>> ".env"
        echo ERP_SQL_USER=test>> ".env"
        echo ERP_SQL_PASSWORD=P@$$w0rd>> ".env"
    )
    findstr /i "AUTH_CENTER_URL" ".env" >nul 2>&1
    if errorlevel 1 (
        echo.>> ".env"
        echo # Autenticacion Unificada SSO ^(Auth-Center VMO^)>> ".env"
        echo SSO_AUTH_CENTER_ENABLED=1>> ".env"
        echo AUTH_CENTER_URL=https://auth.vmo.do>> ".env"
        echo AUTH_CENTER_CLIENT_ID=produccion-embarque>> ".env"
        echo JWT_SECRET_KEY=super-secret-key-for-jwt-token-generation-that-should-be-long-enough>> ".env"
        echo JWT_ISSUER=AuthGeneral>> ".env"
        echo JWT_AUDIENCE=AuthClients>> ".env"
    )
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
echo [4/4] Reiniciando servicio VMO (erp_bridge:app -> SSO Auth-Center + cbsvmo) en segundo plano...
wscript.exe iniciar_oculto.vbs
timeout /t 3 /nobreak >nul

echo.
echo ==========================================================
echo  Comprobando estado del servicio:
echo ==========================================================
netstat -aon | findstr :8000 | findstr LISTENING >nul
if %errorlevel% equ 0 (
    echo  [OK] Servicio VMO actualizado y funcionando en puerto 8000.
    echo       - Login unificado via Auth-Center (https://auth.vmo.do)
    echo       - Conectado en vivo a SQL Server (vmo.ddns.net,1440 / cbsvmo)
) else (
    echo  [AVISO] Verifique si el servicio inicio correctamente con ver_estado.bat
)
echo ==========================================================
echo.
pause
