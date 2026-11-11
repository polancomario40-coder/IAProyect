@echo off
chcp 65001 >nul
cd /d "%~dp0"
title VMO - Instalar Servicio Persistente 24/7 (Independiente de RDP)

echo ==========================================================
echo    VMO - INSTALAR SERVICIO PERSISTENTE 24/7 EN WINDOWS
echo ==========================================================
echo.
echo Este script configurará VMO como una tarea del sistema 'SYSTEM':
echo   1. Correrá 24/7 en segundo plano permanente.
echo   2. NO se cerrará cuando salgas o cierres tu sesión de Remote Desktop (RDP).
echo   3. Arrancará automáticamente al encender o reiniciar el servidor.
echo   4. Si por alguna razón se detuviera, Windows lo reiniciará solo.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "& {
    $dir = '%~dp0'.TrimEnd('\')
    $py = if (Test-Path \"$dir\.venv\Scripts\python.exe\") { \"$dir\.venv\Scripts\python.exe\" } else { 'python.exe' }
    
    # 1. Detener proceso previo en puerto 8000 si existiera
    Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    
    # 2. Configurar accion con directorio de trabajo y privilegios SYSTEM
    $action = New-ScheduledTaskAction -Execute $py -Argument 'run_server.py' -WorkingDirectory $dir
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId 'NT AUTHORITY\SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 365) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    
    # 3. Registrar o actualizar tarea
    Register-ScheduledTask -TaskName 'VMO_Backend_8000' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    
    # 4. Iniciar la tarea de inmediato
    Start-ScheduledTask -TaskName 'VMO_Backend_8000'
    Start-Sleep -Seconds 4
    
    $conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        Write-Host '[OK] Servicio VMO_Backend_8000 instalado e iniciado correctamente en el puerto 8000.' -ForegroundColor Green
        Write-Host 'Ya puedes cerrar tu sesion RDP con total tranquilidad: la aplicacion seguira activa 24/7.' -ForegroundColor Cyan
    } else {
        Write-Host '[AVISO] La tarea fue registrada en el Programador de Tareas.' -ForegroundColor Yellow
        Write-Host 'Puede verificar el estado ejecutando ver_estado.bat.' -ForegroundColor Yellow
    }
}"

echo.
echo ==========================================================
pause
