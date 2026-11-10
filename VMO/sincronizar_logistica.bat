@echo off
chcp 65001 >nul
title VMO - Sincronizacion Directa ERP
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    .\.venv\Scripts\python.exe scripts\sync_erp_logistica.py %*
) else (
    python scripts\sync_erp_logistica.py %*
)
pause
