# Script de instalacion del servicio VMO en segundo plano (24/7) bajo SYSTEM
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Red
    Write-Host " [ALERTA] SE REQUIEREN PRIVILEGIOS DE ADMINISTRADOR" -ForegroundColor Red
    Write-Host "==========================================================" -ForegroundColor Red
    Write-Host "Por favor cierre esta ventana y ejecute el archivo haciendo:" -ForegroundColor Yellow
    Write-Host "  -> Clic DERECHO en 'instalar_servicio_persistente_24_7.bat'" -ForegroundColor Yellow
    Write-Host "  -> 'Ejecutar como administrador'" -ForegroundColor Yellow
    Write-Host "==========================================================" -ForegroundColor Red
    Write-Host ""
    return
}

$dir = $PSScriptRoot.TrimEnd('\')
$py = if (Test-Path "$dir\.venv\Scripts\python.exe") { "$dir\.venv\Scripts\python.exe" } else { "python.exe" }
$runScript = "$dir\run_server.py"

Write-Host "Carpeta de instalacion : $dir" -ForegroundColor Gray
Write-Host "Interprete Python      : $py" -ForegroundColor Gray
Write-Host ""

try {
    # 1. Detener procesos previos en puerto 8000
    Write-Host "[1/4] Verificando puerto 8000..." -ForegroundColor Cyan
    Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "      Liberando puerto 8000 (PID: $($_.OwningProcess))..." -ForegroundColor Yellow
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }

    # 2. Configurar la accion de la tarea
    Write-Host "[2/4] Configurando tarea del sistema..." -ForegroundColor Cyan
    $action = New-ScheduledTaskAction -Execute $py -Argument "run_server.py" -WorkingDirectory $dir
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 365) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

    # 3. Registrar o actualizar tarea
    Write-Host "[3/4] Registrando tarea 'VMO_Backend_8000' bajo cuenta SYSTEM..." -ForegroundColor Cyan
    Unregister-ScheduledTask -TaskName "VMO_Backend_8000" -Confirm:$false -ErrorAction SilentlyContinue
    Register-ScheduledTask -TaskName "VMO_Backend_8000" -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

    # 4. Iniciar la tarea de inmediato
    Write-Host "[4/4] Iniciando servicio..." -ForegroundColor Cyan
    Start-ScheduledTask -TaskName "VMO_Backend_8000"
    Start-Sleep -Seconds 4

    # 5. Comprobar conexion en puerto 8000
    $conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    Write-Host ""
    if ($conn) {
        Write-Host "==========================================================" -ForegroundColor Green
        Write-Host " [OK] SERVICIO VMO INSTALADO Y ESCUCHANDO EN PUERTO 8000" -ForegroundColor Green
        Write-Host "==========================================================" -ForegroundColor Green
        Write-Host "  * La aplicacion corre ahora bajo la cuenta SYSTEM (Sesion 0)." -ForegroundColor Cyan
        Write-Host "  * Ya puedes CERRAR tu sesion RDP con total tranquilidad:" -ForegroundColor Cyan
        Write-Host "    la aplicacion seguira funcionando hacia afuera 24/7." -ForegroundColor Cyan
        Write-Host "  * Si el servidor se reinicia, arrancara automaticamente." -ForegroundColor Cyan
        Write-Host "==========================================================" -ForegroundColor Green
    } else {
        Write-Host "==========================================================" -ForegroundColor Yellow
        Write-Host " [AVISO] Tarea registrada en el Programador de Tareas." -ForegroundColor Yellow
        Write-Host " Verifique si inicio correctamente con ver_estado.bat" -ForegroundColor Yellow
        Write-Host "==========================================================" -ForegroundColor Yellow
    }
} catch {
    Write-Host ""
    Write-Host "[ERROR AL INSTALAR LA TAREA] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "$($_.Exception.ToString())" -ForegroundColor DarkRed
}
