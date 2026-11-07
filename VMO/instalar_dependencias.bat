@echo off
chcp 65001 >nul
title VMO - Instalaci?n de Entorno y Dependencias
cd /d "%~dp0"

echo ==========================================================
echo        VMO - INSTALACI?N DE DEPENDENCIAS PYTHON
echo ==========================================================
echo.

REM Buscar Python en el sistema
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python no fue encontrado en el PATH del sistema.
    echo Aseg?rese de tener Python 3.10 o superior instalado y agregado al PATH.
    pause
    exit /b 1
)

REM Crear entorno virtual si no existe
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creando entorno virtual .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Fall? la creaci?n del entorno virtual .venv.
        pause
        exit /b 1
    )
    echo Entorno virtual creado exitosamente.
) else (
    echo [1/3] Entorno virtual .venv ya existe.
)

REM Instalar / actualizar dependencias
echo [2/3] Instalando librer?as desde requirements.txt...
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Fall? la instalaci?n de librer?as. Revise su conexi?n a Internet.
    pause
    exit /b 1
)

REM Inicializar bases de datos SQLite si no existen
echo [3/3] Verificando e inicializando bases de datos SQLite...
.\.venv\Scripts\python.exe scripts\setup_db.py
.\.venv\Scripts\python.exe -c "import core; core.setup_est_db()"
.\.venv\Scripts\python.exe -c "import core; core.setup_logistica_db()"
.\.venv\Scripts\python.exe -c "import core; core.setup_comercial_db()"

echo.
echo ==========================================================
echo   Instalaci?n completada exitosamente.
echo ==========================================================
echo.
pause
