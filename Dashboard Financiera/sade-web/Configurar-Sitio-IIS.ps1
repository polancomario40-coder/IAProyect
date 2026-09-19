<#
.SYNOPSIS
    Configuración automática del Sitio Web SADE Web en IIS (Internet Information Services).
.DESCRIPTION
    Este script debe ejecutarse en PowerShell como Administrador en el servidor donde se publicará SADE Web.
#>

param (
    [string]$NombreSitio = "SADEWeb",
    [int]$Puerto = 8080,
    [string]$RutaFrontend = "$PSScriptRoot\03_Frontend_SitioWeb",
    [string]$NombreAppPool = "SADEWebAppPool"
)

# Requiere privilegios de Administrador
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "Este script debe ejecutarse como Administrador. Haz clic derecho en PowerShell y selecciona 'Ejecutar como administrador'."
    exit 1
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Configuración de Sitio Web en IIS - SADE Web" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verificar módulo WebAdministration
Import-Module WebAdministration -ErrorAction SilentlyContinue
if (-not (Get-Module -Name WebAdministration)) {
    Write-Host "[!] El servicio IIS no parece estar instalado o el módulo WebAdministration no está disponible." -ForegroundColor Yellow
    Write-Host "    Asegúrate de instalar IIS desde 'Activar o desactivar las características de Windows'." -ForegroundColor Yellow
    exit 1
}

# 2. Habilitar Proxy en ARR (Application Request Routing) si está instalado
try {
    Write-Host "[1/5] Habilitando Reverse Proxy en IIS..." -ForegroundColor White
    Set-WebConfigurationProperty -pspath 'MACHINE/WEBROOT/APPHOST' -filter 'system.webServer/proxy' -name 'enabled' -value 'True' -ErrorAction SilentlyContinue
    Write-Host "  -> Reverse Proxy habilitado correctamente." -ForegroundColor Green
} catch {
    Write-Host "  [!] Nota: Asegúrate de tener instalado 'Application Request Routing (ARR)' y 'URL Rewrite' en IIS." -ForegroundColor Yellow
}

# 3. Validar ruta física del Frontend
$RutaCompleta = [System.IO.Path]::GetFullPath($RutaFrontend)
if (-not (Test-Path $RutaCompleta)) {
    Write-Error "La ruta del Frontend no existe: $RutaCompleta"
    exit 1
}
Write-Host "[2/5] Ruta física del sitio web: $RutaCompleta" -ForegroundColor White

# 4. Asignar permisos a IIS_IUSRS e IUSR
Write-Host "[3/5] Configurando permisos de lectura para usuarios de IIS..." -ForegroundColor White
icacls "$RutaCompleta" /grant "IIS_IUSRS:(OI)(CI)RX" /t /q
icacls "$RutaCompleta" /grant "IUSR:(OI)(CI)RX" /t /q
Write-Host "  -> Permisos asignados." -ForegroundColor Green

# 5. Crear o actualizar Application Pool (No Managed Code)
Write-Host "[4/5] Configurando Application Pool '$NombreAppPool'..." -ForegroundColor White
if (Test-Path "IIS:\AppPools\$NombreAppPool") {
    Write-Host "  -> El AppPool '$NombreAppPool' ya existe. Reutilizando..." -ForegroundColor Gray
} else {
    New-Item "IIS:\AppPools\$NombreAppPool" | Out-Null
}
# Configurar sin runtime de .NET (No Managed Code para archivos estáticos)
Set-ItemProperty "IIS:\AppPools\$NombreAppPool" -Name "managedRuntimeVersion" -Value ""
Set-ItemProperty "IIS:\AppPools\$NombreAppPool" -Name "startMode" -Value "AlwaysRunning"
Write-Host "  -> AppPool listo." -ForegroundColor Green

# 6. Crear o actualizar el Sitio Web
Write-Host "[5/5] Configurando Sitio Web '$NombreSitio' en el puerto $Puerto..." -ForegroundColor White
if (Test-Path "IIS:\Sites\$NombreSitio") {
    Write-Host "  -> El sitio '$NombreSitio' ya existe. Actualizando configuración..." -ForegroundColor Yellow
    Set-ItemProperty "IIS:\Sites\$NombreSitio" -Name "physicalPath" -Value "$RutaCompleta"
    Set-ItemProperty "IIS:\Sites\$NombreSitio" -Name "applicationPool" -Value "$NombreAppPool"
} else {
    New-Website -Name $NombreSitio -Port $Puerto -PhysicalPath "$RutaCompleta" -ApplicationPool "$NombreAppPool" | Out-Null
    Write-Host "  -> Sitio web creado exitosamente." -ForegroundColor Green
}

# Iniciar sitio
Start-Website -Name $NombreSitio -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "   ¡Instalación en IIS Completada con Éxito!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "Sitio web disponible en: http://localhost:$Puerto" -ForegroundColor Cyan
Write-Host "Asegúrate de que el Backend API esté ejecutándose en http://127.0.0.1:8000" -ForegroundColor White
Write-Host ""
