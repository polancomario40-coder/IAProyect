param(
    [string]$RutaBackend = "$PSScriptRoot\02_Backend_API",
    [string]$NombreTarea = "SADEWeb_Backend_API"
)

$batPath = Join-Path $RutaBackend "iniciar_backend.bat"
if (-not (Test-Path $batPath)) {
    Write-Error "No se encontro iniciar_backend.bat en $RutaBackend"
    exit 1
}

# 1. Detener tarea previa si existe
Stop-ScheduledTask -TaskName $NombreTarea -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# 2. Cerrar cualquier proceso residual escuchando en el puerto 8000
$conns = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($p in $conns) {
    if ($p -and $p -gt 0) {
        Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
    }
}

$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$batPath`"" -WorkingDirectory $RutaBackend
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $NombreTarea -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $NombreTarea
Write-Host "  -> Servicio Backend reiniciado y registrado como Tarea Programada ('$NombreTarea')." -ForegroundColor Green
