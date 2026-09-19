<#
.SYNOPSIS
    Configura el Backend API de SADE Web para que inicie automáticamente con Windows.
.DESCRIPTION
    Crea una Tarea Programada en el Programador de Tareas de Windows (Task Scheduler)
    que se ejecuta al arrancar el servidor con la cuenta SYSTEM (en segundo plano y sin ventana).
#>

param (
    [string]$NombreTarea = "SADEWeb_Backend_API",
    [string]$RutaBackend = "$PSScriptRoot\02_Backend_API"
)

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "Este script debe ejecutarse como Administrador."
    exit 1
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Configurando Servicio Automático para el Backend API" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$RutaCompleta = [System.IO.Path]::GetFullPath($RutaBackend)
$BatchFile = Join-Path $RutaCompleta "iniciar_backend.bat"

if (-not (Test-Path $BatchFile)) {
    Write-Error "No se encontró el archivo batch: $BatchFile"
    exit 1
}

# 1. Definir acción (ejecutar iniciar_backend.bat)
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BatchFile`"" -WorkingDirectory "$RutaCompleta"

# 2. Definir desencadenador (Al arrancar el equipo)
$Trigger = New-ScheduledTaskTrigger -AtStartup

# 3. Definir configuración de la tarea (reinicio en caso de fallo, sin límite de tiempo)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 0)

# 4. Registrar la tarea con cuenta SYSTEM
Unregister-ScheduledTask -TaskName $NombreTarea -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $NombreTarea -Action $Action -Trigger $Trigger -Settings $Settings -User "NT AUTHORITY\SYSTEM" -RunLevel Highest | Out-Null

Write-Host "  -> Tarea Programada registrada: '$NombreTarea'" -ForegroundColor Green

# 5. Iniciar la tarea de inmediato
Start-ScheduledTask -TaskName $NombreTarea
Write-Host "  -> Backend iniciado en segundo plano." -ForegroundColor Green
Write-Host ""
Write-Host "El backend ahora se ejecutará automáticamente cada vez que inicie el servidor." -ForegroundColor Cyan
Write-Host "Puedes verificar el estado en el Programador de Tareas de Windows o probando: http://127.0.0.1:8000/health" -ForegroundColor White
Write-Host ""
